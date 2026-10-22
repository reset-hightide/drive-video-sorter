# Instala o drive-video-sorter no Windows: venv com as dependências, config.json e a skill /organizar-drive.
$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot

foreach ($cmd in "python", "ffmpeg", "ffprobe", "rclone") {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "Falta instalar: $cmd"; exit 1 }
}

python -m venv "$Repo\.venv"
& "$Repo\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$Repo\.venv\Scripts\python.exe" -m pip install -q -r "$Repo\requirements.txt"

if (-not (Test-Path "$Repo\config.json")) { Copy-Item "$Repo\config.example.json" "$Repo\config.json" }

# a skill aponta para esta pasta e para o Python do venv
$SkillDir = "$HOME\.claude\skills\organizar-drive"
New-Item -ItemType Directory -Force $SkillDir | Out-Null
$Py = "$Repo\.venv\Scripts\python.exe" -replace '\\', '/'
(Get-Content "$Repo\skill\SKILL.md" -Raw).Replace("{{REPO}}", ($Repo -replace '\\', '/')).Replace("{{PY}}", $Py) |
    Set-Content -Encoding utf8 "$SkillDir\SKILL.md"

Write-Host "Pronto. Skill instalada em $SkillDir"
if (-not (rclone listremotes | Select-String '^gdrive:$')) { Write-Host "Falta criar o remote gdrive: no rclone (veja o README, passo 3)." }
