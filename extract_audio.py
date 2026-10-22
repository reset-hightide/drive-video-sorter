#!/usr/bin/env python3
"""Baixa só o áudio de vídeos MP4 de uma pasta do Google Drive.

Para áudio PCM (câmeras Sony e afins), lê o índice (moov) do MP4 por range
requests, descobre em quais bytes estão os pedaços de áudio e baixa só esses
bytes. Para áudio comprimido (AAC de celular), o ffmpeg lê o vídeo pelo link.
Gera um WAV 16 kHz mono por vídeo, pronto para o Whisper.

Uso: extract_audio.py <remote rclone> <pasta de saída>
"""
import json
import struct
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://www.googleapis.com/drive/v3/files/{}?alt=media"
MERGE_GAP = 256 * 1024  # junta pedaços de áudio separados por menos que isso
CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}


def token(remote):
    # qualquer chamada do rclone renova o token se precisar
    subprocess.run(["rclone", "lsf", "--max-depth", "1", f"{remote}:"],
                   capture_output=True, check=True)
    cfg = json.loads(subprocess.run(["rclone", "config", "dump"],
                                    capture_output=True, check=True).stdout)
    return json.loads(cfg[remote]["token"])["access_token"]


def fetch(fid, tok, start, end):
    req = urllib.request.Request(API.format(fid), headers={
        "Authorization": f"Bearer {tok}", "Range": f"bytes={start}-{end}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if attempt == 4:
                raise


def boxes(data, base=0):
    i = 0
    while i + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[i:i + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = len(data) - i
        yield kind, base + i, hdr, size
        i += size


def find_moov(fid, tok, filesize):
    pos = 0
    while pos < filesize:
        head = fetch(fid, tok, pos, min(pos + 15, filesize - 1))
        size, kind = struct.unpack(">I4s", head[:8])
        if size == 1:
            size = struct.unpack(">Q", head[8:16])[0]
        elif size == 0:
            size = filesize - pos
        if kind == b"moov":
            return fetch(fid, tok, pos, pos + size - 1)
        pos += size
    raise ValueError("moov não encontrado")


def audio_tables(moov):
    """Devolve (offsets dos chunks, tamanhos dos chunks, sample entry) do trak de áudio."""
    def walk(data, base_off):
        for kind, off, hdr, size in boxes(data):
            body = data[off + hdr:off + size]
            if kind == b"trak":
                t = {}
                collect(body, t)
                if t.get("hdlr") == b"soun":
                    return t
            elif kind in CONTAINERS:
                r = walk(body, 0)
                if r:
                    return r
        return None

    def collect(data, t):
        for kind, off, hdr, size in boxes(data):
            body = data[off + hdr:off + size]
            if kind in CONTAINERS:
                collect(body, t)
            elif kind == b"hdlr":
                t["hdlr"] = body[8:12]
            else:
                t[kind.decode("latin1")] = body

    t = walk(moov, 0)
    if not t:
        return None
    # stco / co64
    if "co64" in t:
        n = struct.unpack(">I", t["co64"][4:8])[0]
        offsets = struct.unpack(f">{n}Q", t["co64"][8:8 + 8 * n])
    else:
        n = struct.unpack(">I", t["stco"][4:8])[0]
        offsets = struct.unpack(f">{n}I", t["stco"][8:8 + 4 * n])
    # stsz
    ssize, scount = struct.unpack(">II", t["stsz"][4:12])
    sizes = None if ssize else struct.unpack(f">{scount}I", t["stsz"][12:12 + 4 * scount])
    # stsc -> amostras por chunk
    m = struct.unpack(">I", t["stsc"][4:8])[0]
    runs = [struct.unpack(">III", t["stsc"][8 + 12 * k:20 + 12 * k]) for k in range(m)]
    chunk_bytes = []
    sample = 0
    for k, (first, per_chunk, _) in enumerate(runs):
        last = runs[k + 1][0] - 1 if k + 1 < m else len(offsets)
        for _ in range(first, last + 1):
            if sizes is None:
                chunk_bytes.append(per_chunk * ssize)
            else:
                chunk_bytes.append(sum(sizes[sample:sample + per_chunk]))
            sample += per_chunk
    return list(offsets), chunk_bytes


def probe(fid, tok):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-headers", f"Authorization: Bearer {tok}\r\n",
         "-select_streams", "a:0", "-show_entries",
         "stream=codec_name,sample_rate,channels", "-of", "json", API.format(fid)],
        capture_output=True, text=True).stdout
    streams = json.loads(out or "{}").get("streams", [])
    return streams[0] if streams else None


def extract(item, tok, outdir):
    fid, name, filesize = item["ID"], item["Name"], item["Size"]
    outdir.mkdir(parents=True, exist_ok=True)
    wav = outdir / (Path(name).stem + ".wav")
    if wav.exists():
        return name, "já existe"
    info = probe(fid, tok)
    if not info:
        return name, "sem áudio"
    fmt = {"pcm_s16be": "s16be", "pcm_s16le": "s16le",
           "pcm_s24be": "s24be", "pcm_s24le": "s24le"}.get(info["codec_name"])
    if not fmt:
        # áudio comprimido (AAC de celular etc.): o ffmpeg lê pelo link e decodifica
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-headers", f"Authorization: Bearer {tok}\r\n",
                        "-i", API.format(fid), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                       check=True)
        return name, f"{info['codec_name']} via ffmpeg ({filesize / 2**20:.0f} MB de vídeo)"
    tables = audio_tables(find_moov(fid, tok, filesize))
    if not tables:
        return name, "sem trilha de áudio"
    offsets, lengths = tables
    # junta chunks próximos em poucas requisições grandes
    spans = []
    for off, ln in sorted(zip(offsets, lengths)):
        if spans and off - spans[-1][1] <= MERGE_GAP:
            spans[-1][2].append((off, ln))
            spans[-1][1] = max(spans[-1][1], off + ln)
        else:
            spans.append([off, off + ln, [(off, ln)]])
    pcm = bytearray()
    with ThreadPoolExecutor(24) as ex:
        blobs = ex.map(lambda s: fetch(fid, tok, s[0], s[1] - 1), spans)
        for (start, _, parts), blob in zip(spans, blobs):
            for off, ln in parts:
                pcm += blob[off - start:off - start + ln]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", fmt,
                    "-ar", str(info["sample_rate"]), "-ac", str(info["channels"]),
                    "-i", "pipe:0", "-ac", "1", "-ar", "16000", str(wav)],
                   input=bytes(pcm), check=True)
    return name, f"{len(pcm) / 2**20:.1f} MB de áudio ({filesize / 2**20:.0f} MB de vídeo)"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows usa cp1252 em pipes
    remote, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    items = json.loads(subprocess.run(
        ["rclone", "lsjson", "--files-only", f"{remote}:"],
        capture_output=True, check=True).stdout)
    items = [i for i in items if i["Name"].lower().endswith((".mp4", ".mov"))]
    tok = token(remote)
    with ThreadPoolExecutor(4) as ex:
        for name, status in ex.map(lambda i: extract(i, tok, outdir), items):
            print(f"{name}: {status}", flush=True)


if __name__ == "__main__":
    main()
