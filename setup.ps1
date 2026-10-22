# Instala o drive-video-sorter no Windows: venv com as dependencias, config.json e a skill /organizar-drive.
# Rode com: powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
$Repo = $PSScriptRoot

function Falta($o, $como) { Write-Host "Falta: $o"; Write-Host "  $como"; exit 1 }

# "py" e o lancador oficial; "python" pode ser so o atalho da Microsoft Store
$Python = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $Python = @("py", "-3") }
elseif ((Get-Command python -ErrorAction SilentlyContinue) -and
        ((Get-Command python).Source -notlike "*WindowsApps*")) { $Python = @("python") }
if (-not $Python) { Falta "Python" "winget install Python.Python.3.13 e abra um PowerShell novo." }
$Exe, $PyArgs = $Python
& $Exe @PyArgs -c "import sys; sys.exit(sys.version_info < (3, 10))"
if ($LASTEXITCODE -ne 0) { Falta "Python 3.10 ou mais novo" "winget install Python.Python.3.13 e abra um PowerShell novo." }

foreach ($cmd in "ffmpeg", "ffprobe", "rclone") {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Falta $cmd "Instale pela tabela do passo 1 do README e abra um PowerShell novo."
    }
}

& $Exe @PyArgs -m venv "$Repo\.venv"
if ($LASTEXITCODE -ne 0) { Falta "venv" "Reinstale o Python: winget install Python.Python.3.13" }
$VenvPy = "$Repo\.venv\Scripts\python.exe"
& $VenvPy -m pip install -q --upgrade pip
& $VenvPy -m pip install -q -r "$Repo\requirements.txt"
if ($LASTEXITCODE -ne 0) { Falta "dependencias do Python" "Veja o erro do pip acima." }

if (-not (Test-Path "$Repo\config.json")) { Copy-Item "$Repo\config.example.json" "$Repo\config.json" }

# a skill aponta para esta pasta e para o Python do venv (UTF-8 sem BOM, senao o Claude Code nao le o cabecalho)
$SkillDir = "$HOME\.claude\skills\organizar-drive"
New-Item -ItemType Directory -Force $SkillDir | Out-Null
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Skill = [IO.File]::ReadAllText("$Repo\skill\SKILL.md", $Utf8)
$Skill = $Skill.Replace("{{REPO}}", ($Repo -replace '\\', '/')).Replace("{{PY}}", ($VenvPy -replace '\\', '/'))
[IO.File]::WriteAllText("$SkillDir\SKILL.md", $Skill, $Utf8)

Write-Host "Pronto. Skill instalada em $SkillDir"
if (-not (rclone listremotes | Select-String '^gdrive:$')) {
    Write-Host "Proximo passo: criar o remote gdrive: no rclone (README, passos 3 e 4)."
}
