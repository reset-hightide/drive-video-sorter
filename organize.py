#!/usr/bin/env python3
"""Organiza uma pasta do Google Drive conforme um plano (arquivo -> subpasta).

Cria as subpastas, move cada arquivo, acrescenta um resumo ao nome
(C8940.MP4 -> C8940_dobrar-arame.MP4), grava a descrição (transcrição) e
registra tudo em log.jsonl. Rodar de novo é seguro: o que
já está no lugar é pulado. No fim confere pasta por pasta.

Uso:
  organize.py <remote rclone> plan.json        aplica o plano
  organize.py <remote rclone> --undo log.jsonl  devolve tudo para a pasta raiz
"""
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://www.googleapis.com/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"


class Drive:
    def __init__(self, remote):
        self.remote = remote
        self.refresh()
        cfg = json.loads(subprocess.run(["rclone", "config", "dump"],
                                        capture_output=True, check=True).stdout)
        self.root = cfg[remote]["root_folder_id"]

    def refresh(self):
        # qualquer chamada do rclone renova o token se precisar
        subprocess.run(["rclone", "lsf", "--max-depth", "1", f"{self.remote}:"],
                       capture_output=True, check=True)
        cfg = json.loads(subprocess.run(["rclone", "config", "dump"],
                                        capture_output=True, check=True).stdout)
        self.tok = json.loads(cfg[self.remote]["token"])["access_token"]
        self.tok_time = time.time()

    def call(self, method, url, body=None):
        if time.time() - self.tok_time > 1800:
            self.refresh()
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(6):
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.tok}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                if e.code in (403, 429, 500, 502, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"{e.code}: {e.read()[:300]!r}")

    def children(self, parent):
        out, page = [], None
        while True:
            q = {"q": f"'{parent}' in parents and trashed=false",
                 "fields": "nextPageToken,files(id,name,mimeType,parents)",
                 "pageSize": 1000}
            if page:
                q["pageToken"] = page
            r = self.call("GET", f"{API}?{urllib.parse.urlencode(q)}")
            out += r["files"]
            page = r.get("nextPageToken")
            if not page:
                return out

    def ensure_folder(self, name, existing):
        for f in existing:
            if f["name"] == name and f["mimeType"] == FOLDER:
                return f["id"]
        r = self.call("POST", f"{API}?fields=id",
                      {"name": name, "mimeType": FOLDER, "parents": [self.root]})
        return r["id"]

    def move(self, fid, src, dst, description=None, name=None):
        q = urllib.parse.urlencode({"addParents": dst, "removeParents": src,
                                    "fields": "id,parents"})
        body = {"description": description} if description else {}
        if name:
            body["name"] = name
        return self.call("PATCH", f"{API}/{fid}?{q}", body)


def log_line(log, **kw):
    kw["quando"] = datetime.now().isoformat(timespec="seconds")
    log.write(json.dumps(kw, ensure_ascii=False) + "\n")
    log.flush()


def apply(drive, plan_path):
    plan = json.loads(Path(plan_path).read_text())  # {nome: {"pasta": ..., "descricao": ...}}
    top = drive.children(drive.root)
    folders = {name: drive.ensure_folder(name, top)
               for name in sorted({p["pasta"] for p in plan.values()})}
    by_name = {f["name"]: f for f in top if f["mimeType"] != FOLDER}
    with open(Path(plan_path).with_name("log.jsonl"), "a") as log:
        for name, p in plan.items():
            f = by_name.get(name)
            if not f:
                continue  # já movido numa rodada anterior
            dst = folders[p["pasta"]]
            try:
                new = p.get("novo_nome") or name
                drive.move(f["id"], drive.root, dst, p.get("descricao"), new)
                log_line(log, arquivo=name, novo_nome=new, id=f["id"], de=drive.root,
                         para=dst, pasta=p["pasta"], status="ok")
            except RuntimeError as e:
                log_line(log, arquivo=name, id=f["id"], pasta=p["pasta"],
                         status="erro", erro=str(e))
                print(f"ERRO {name}: {e}", flush=True)
    # conferência
    ok = True
    for pasta, fid in folders.items():
        have = {f["name"] for f in drive.children(fid)}
        want = {p.get("novo_nome") or n for n, p in plan.items() if p["pasta"] == pasta}
        missing = want - have
        print(f"{pasta}: {len(want & have)}/{len(want)}"
              + (f"  FALTANDO: {sorted(missing)}" if missing else ""))
        ok &= not missing
    return ok


def undo(drive, log_path):
    # de trás para frente: um arquivo pode ter sido movido mais de uma vez
    for line in reversed(Path(log_path).read_text().splitlines()):
        e = json.loads(line)
        if e.get("status") == "ok":
            drive.move(e["id"], e["para"], e["de"], name=e["arquivo"])
            print("devolvido:", e["arquivo"])


def main():
    drive = Drive(sys.argv[1])
    if sys.argv[2] == "--undo":
        undo(drive, sys.argv[3])
    else:
        sys.exit(0 if apply(drive, sys.argv[2]) else 1)


if __name__ == "__main__":
    main()
