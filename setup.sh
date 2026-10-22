#!/usr/bin/env bash
# Instala o drive-video-sorter: venv com as dependências, config.json e a skill /organizar-drive.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"

for cmd in python3 ffmpeg ffprobe rclone; do
  command -v "$cmd" >/dev/null || { echo "Falta instalar: $cmd"; exit 1; }
done

python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" install -q --upgrade pip
"$REPO/.venv/bin/pip" install -q -r "$REPO/requirements.txt"

[ -f "$REPO/config.json" ] || cp "$REPO/config.example.json" "$REPO/config.json"

# a skill aponta para esta pasta
SKILL_DIR="$HOME/.claude/skills/organizar-drive"
mkdir -p "$SKILL_DIR"
sed -e "s|{{REPO}}|$REPO|g" -e "s|{{PY}}|$REPO/.venv/bin/python|g" "$REPO/skill/SKILL.md" > "$SKILL_DIR/SKILL.md"

echo "Pronto. Skill instalada em $SKILL_DIR"
rclone listremotes | grep -q '^gdrive:$' || echo "Falta criar o remote gdrive: no rclone (veja o README, passo 2)."
