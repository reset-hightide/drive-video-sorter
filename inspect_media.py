#!/usr/bin/env python3
"""Junta os sinais para classificar: horário, duração, áudio, quadros e fotos.

Rodar com o Python do venv (precisa de Pillow) depois do transcribe.py.
Gera em <pasta de trabalho>:
  files.json        listagem do Drive (id, nome, tamanho)
  signals.json      um item por arquivo, em ordem de gravação, com hora local
                    (UTC_OFFSET, padrão -3 = Brasília), duração, volume, transcrição e caminho da imagem
  sheet_videos_N.jpg / sheet_fotos_N.jpg   folhas de contato rotuladas

Uso: inspect_media.py <remote rclone> <pasta de trabalho>
"""
import io
import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

API = "https://www.googleapis.com/drive/v3/files/{}?alt=media"
VIDEO = (".mp4", ".mov")
PHOTO = (".jpg", ".jpeg", ".png", ".heic")
UTC_OFFSET = float(os.environ.get("UTC_OFFSET", "-3"))  # fuso local; Brasília = -3


def token(remote):
    subprocess.run(["rclone", "lsf", "--max-depth", "1", f"{remote}:"],
                   capture_output=True, check=True)
    cfg = json.loads(subprocess.run(["rclone", "config", "dump"],
                                    capture_output=True, check=True).stdout)
    return json.loads(cfg[remote.split(",")[0]]["token"])["access_token"]


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 12 * len(text) + 8, 28], fill="black")
    d.text((4, 3), text, fill="yellow", font_size=22)
    return im


def video_signals(f, tok, work):
    url = API.format(f["ID"])
    hdr = f"Authorization: Bearer {tok}\r\n"
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-headers", hdr, "-show_entries",
         "format=duration:format_tags=creation_time", "-of", "json", url],
        capture_output=True, text=True).stdout or "{}").get("format", {})
    dur = float(probe.get("duration", 0))
    ct = probe.get("tags", {}).get("creation_time")
    # MP4 da câmera grava em UTC; mostramos no fuso local (UTC_OFFSET)
    when = (datetime.fromisoformat(ct.replace("Z", "+00:00")) + timedelta(hours=UTC_OFFSET)
            ).strftime("%H:%M:%S") if ct else None
    stem = Path(f["Name"]).stem
    frame = work / "frames" / f"{stem}.jpg"
    if not frame.exists():
        jpg = subprocess.run(["ffmpeg", "-v", "error", "-headers", hdr, "-ss", str(dur / 2),
                              "-i", url, "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg",
                              "pipe:1"], capture_output=True).stdout
        if jpg:
            im = Image.open(io.BytesIO(jpg))
            im.thumbnail((400, 400))
            label(im, f"{stem[:12]} {when[:5] if when else '?'}").save(frame)
    vol = None
    wav = work / f"{stem}.wav"
    if wav.exists():
        out = subprocess.run(["ffmpeg", "-i", str(wav), "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        vol = next((float(l.split(":")[1].split()[0]) for l in out.splitlines()
                    if "mean_volume" in l), None)
    tr = work / f"{stem}.json"
    text = json.loads(tr.read_text())["text"] if tr.exists() else ""
    return {"arquivo": f["Name"], "tipo": "video", "hora_local": when,
            "duracao": round(dur), "volume_medio_db": vol, "transcricao": text,
            "imagem": str(frame) if frame.exists() else None}


def photo_signals(f, tok, work):
    req = urllib.request.Request(API.format(f["ID"]), headers={"Authorization": f"Bearer {tok}"})
    im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=120).read()))
    ex = im.getexif()
    dt = ex.get_ifd(0x8769).get(36867) or ex.get(306)  # EXIF já vem em horário local
    when = dt[11:19] if dt else None
    thumb = work / "frames" / f"{Path(f['Name']).stem}.jpg"
    im.thumbnail((400, 400))
    label(im.convert("RGB"), f"{Path(f['Name']).stem[:12]} {when[:5] if when else '?'}").save(thumb)
    return {"arquivo": f["Name"], "tipo": "foto", "hora_local": when,
            "imagem": str(thumb)}


def contact_sheets(items, work, prefix, per_sheet=30, cols=6, cell=330):
    paths = []
    for k in range(0, len(items), per_sheet):
        chunk = [i for i in items[k:k + per_sheet] if i["imagem"]]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cell * cols, cell * rows), "black")
        for n, it in enumerate(chunk):
            im = Image.open(it["imagem"])
            im.thumbnail((cell, cell))
            sheet.paste(im, ((n % cols) * cell, (n // cols) * cell))
        path = work / f"{prefix}_{k // per_sheet + 1}.jpg"
        sheet.save(path, quality=85)
        paths.append(str(path))
    return paths


def main():
    remote, work = sys.argv[1], Path(sys.argv[2])
    (work / "frames").mkdir(parents=True, exist_ok=True)
    files = json.loads(subprocess.run(["rclone", "lsjson", "--files-only", f"{remote}:"],
                                      capture_output=True, check=True).stdout)
    (work / "files.json").write_text(json.dumps(files, ensure_ascii=False))
    tok = token(remote)
    with ThreadPoolExecutor(8) as ex:
        vids = list(ex.map(lambda f: video_signals(f, tok, work),
                           [f for f in files if f["Name"].lower().endswith(VIDEO)]))
        fotos = list(ex.map(lambda f: photo_signals(f, tok, work),
                            [f for f in files if f["Name"].lower().endswith(PHOTO)]))
    key = lambda i: (i["hora_local"] or "99", i["arquivo"])
    vids.sort(key=key)
    fotos.sort(key=key)
    (work / "signals.json").write_text(json.dumps(vids + fotos, ensure_ascii=False, indent=1))
    outros = [f["Name"] for f in files if not f["Name"].lower().endswith(VIDEO + PHOTO)]
    print(f"{len(vids)} vídeos, {len(fotos)} fotos, {len(outros)} outros {outros[:10]}")
    for p in contact_sheets(vids, work, "sheet_videos") + contact_sheets(fotos, work, "sheet_fotos"):
        print(p)


if __name__ == "__main__":
    main()
