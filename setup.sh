#!/usr/bin/env bash
# Instala o drive-video-sorter (macOS, Linux, SteamOS): venv com as dependências,
# config.json e a skill /organizar-drive.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"

falta() { echo "Falta: $1"; echo "  $2"; exit 1; }

command -v python3 >/dev/null || falta "python3" "Veja a tabela do passo 1 do README."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' ||
  falta "Python 3.10 ou mais novo (este é $(python3 --version 2>&1))" \
        "macOS: brew install python e abra um terminal novo. Linux: instale pelo gerenciador de pacotes."
command -v ffmpeg >/dev/null || falta "ffmpeg" "Veja a tabela do passo 1 do README."
command -v ffprobe >/dev/null || falta "ffprobe (vem junto com o ffmpeg)" "Veja a tabela do passo 1 do README."
if ! command -v rclone >/dev/null; then
  if [ -x "$HOME/.local/bin/rclone" ]; then
    falta "~/.local/bin no PATH" "Rode: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc e abra um terminal novo."
  fi
  falta "rclone" "Veja a tabela do passo 1 do README."
fi

python3 -m venv "$REPO/.venv" 2>/dev/null ||
  falta "módulo venv do Python" "Ubuntu/Debian: sudo apt install python3-venv"
"$REPO/.venv/bin/python" -m pip install -q --upgrade pip
"$REPO/.venv/bin/python" -m pip install -q -r "$REPO/requirements.txt"

[ -f "$REPO/config.json" ] || cp "$REPO/config.example.json" "$REPO/config.json"

# a skill aponta para esta pasta e para o Python do venv
SKILL_DIR="$HOME/.claude/skills/organizar-drive"
mkdir -p "$SKILL_DIR"
sed -e "s|{{REPO}}|$REPO|g" -e "s|{{PY}}|$REPO/.venv/bin/python|g" "$REPO/skill/SKILL.md" > "$SKILL_DIR/SKILL.md"

echo "Pronto. Skill instalada em $SKILL_DIR"
rclone listremotes | grep -q '^gdrive:$' || echo "Próximo passo: criar o remote gdrive: no rclone (README, passos 3 e 4)."
