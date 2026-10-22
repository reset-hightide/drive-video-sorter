# drive-video-sorter

Organiza vídeos e fotos soltos da câmera em pastas do Google Drive, separados por conteúdo, sem precisar assistir a horas de gravação.

Você informa o link da pasta e a lista de conteúdos ("1. Workshop, 2. Depoimento da aluna, 3. Convite"). O Claude Code transcreve os vídeos, verifica os horários de gravação e analisa um quadro de cada arquivo para decidir onde cada um deve ficar. Depois, organiza tudo no Drive:

```
22-08 Workshop/
├── 1. Workshop/
│   ├── C8940_dobrar-arame.MP4       ← nome da câmera + resumo
│   ├── C8944_efeito-orvalho.MP4
│   └── DSC01402.JPG
├── 2. Depoimento aluna/
│   └── C8952_relato-aluna.MP4
├── 3. Convite/
│   └── C8980_convite-cursos.MP4
├── 4. Outros - joias de miçanga/    ← assunto que não estava na lista
└── De-para videos e fotos           ← planilha: arquivo, pasta, motivo, transcrição
```

A transcrição de cada vídeo também fica no campo **Descrição** do Drive. Assim, você pode encontrar um arquivo pesquisando por algo que foi dito nele.

Na primeira execução, foram organizados 52 vídeos e 58 fotos (25 GB), totalizando 110 arquivos, sem erros e em cerca de 25 minutos.

## Como decide

A classificação considera três sinais, nesta ordem:

1. **Fala.** O Whisper transcreve o áudio localmente.
2. **Horário de gravação.** Um clipe sem fala gravado entre dois clipes do mesmo conteúdo, com poucos minutos de diferença, provavelmente pertence a esse conteúdo. Nas fotos, vale o horário registrado no EXIF.
3. **Imagem.** Um quadro do meio de cada vídeo e uma miniatura de cada foto são reunidos numa folha de contato para comparar cenários, pessoas e peças.

Quando o horário e a imagem apontam para o mesmo conteúdo, a confiança é alta. Se apenas um deles indica o conteúdo, é média. Se os sinais se contradizem, o arquivo vai para `Revisar`. O motivo e o nível de confiança ficam registrados na planilha e na descrição do arquivo.

**O script não baixa os 25 GB inteiros.** Nos vídeos de câmera com áudio PCM, um índice indica em quais bytes está o áudio. O script baixa apenas esses trechos: um vídeo de 6,2 GB, por exemplo, vira 97 MB. Nos vídeos de celular com áudio AAC, o ffmpeg lê o áudio diretamente do link. Mover e renomear arquivos no Drive é instantâneo, pois eles não precisam ser reenviados.

## Instalação

O projeto funciona em **Windows, macOS, Linux e SteamOS** (Steam Deck no modo Desktop). Os comandos variam conforme o sistema operacional.

### 1. Instalar os programas

Você vai precisar de [Claude Code](https://claude.com/claude-code), Git, Python 3.10+, `ffmpeg` e `rclone`.

Use os comandos da coluna correspondente ao seu sistema:

| | Windows (PowerShell) | macOS | Linux | SteamOS |
|---|---|---|---|---|
| Claude Code | `irm https://claude.ai/install.ps1 \| iex` | `curl -fsSL https://claude.ai/install.sh \| bash` | igual ao macOS | igual ao macOS |
| Git | `winget install Git.Git` | `xcode-select --install` | `sudo apt install git` | já vem instalado |
| Python | `winget install Python.Python.3.13` | `brew install python` | já vem instalado | já vem instalado |
| ffmpeg | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` | já vem instalado |
| rclone | `winget install Rclone.Rclone` | `brew install rclone` | `sudo apt install rclone` | veja abaixo |

No SteamOS, o sistema é somente leitura. Por isso, instale o rclone na sua pasta pessoal:

```bash
mkdir -p ~/.local/bin && cd /tmp
curl -LO https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip -j rclone-current-linux-amd64.zip '*/rclone' -d ~/.local/bin
```

### 2. Baixar o projeto

Execute os comandos abaixo no terminal. No Windows, use o PowerShell; no macOS, Linux e SteamOS, use o terminal do sistema.

```bash
git clone https://github.com/reset-hightide/drive-video-sorter.git
cd drive-video-sorter
./setup.sh          # macOS, Linux e SteamOS
.\setup.ps1         # Windows (PowerShell)
```

O instalador cria o ambiente `.venv` com as dependências, copia `config.example.json` para `config.json` e instala a skill `/organizar-drive` em `~/.claude/skills/`.

### 3. Criar a sua credencial do Google (uma vez, uns 5 minutos)

A credencial padrão do rclone é compartilhada por todos e costuma estourar a cota, causando o erro 403. Com uma credencial própria, você tem uma cota exclusiva.

1. Acesse [console.cloud.google.com](https://console.cloud.google.com/projectcreate) e crie um projeto.
2. Em **APIs e serviços → Biblioteca**, ative a **Google Drive API**.
3. Em **Google Auth Platform**, clique em **Vamos começar** e preencha o nome e o e-mail. Em Público, escolha **Interno** se a conta for Google Workspace (o login não expira) ou **Externo** se for Gmail pessoal (adicione o seu e-mail como usuário de teste).
4. Em **Clientes → Criar cliente**, escolha **App para computador** e copie o ID do cliente e a chave secreta.

### 4. Conectar o rclone ao Drive

Execute o comando no terminal. Ele é o mesmo nos quatro sistemas:

```bash
rclone config create gdrive drive scope=drive client_id=SEU_ID.apps.googleusercontent.com client_secret=SUA_CHAVE
```

O navegador será aberto. Escolha a conta que tem acesso às pastas e clique em **Permitir**.

## Uso

No Claude Code, execute o comando abaixo, substituindo o link pela URL da sua pasta e informando os conteúdos que deseja separar. Os conteúdos mudam a cada pasta: nada fica fixo, e as pastas são criadas com os nomes que você passar, na ordem informada.

```
/organizar-drive https://drive.google.com/drive/folders/XXXX 1. Workshop, 2. Depoimento da aluna, 3. Convite
```

Ao terminar, o Claude envia um resumo pelo WhatsApp para o chat definido em `config.json` (`whatsapp_chat`). Para receber o aviso, o [Claude in Chrome](https://claude.com/chrome) precisa estar conectado e o WhatsApp Web deve estar logado. Deixe o campo vazio se não quiser receber avisos.

### Desfazer

Cada execução fica registrada em `runs/<data>_<nome>/`, com um arquivo `log.jsonl`. Para restaurar os arquivos e seus nomes originais, use o comando correspondente ao seu sistema:

```bash
.venv/bin/python organize.py gdrive --undo runs/<data>_<nome>/log.jsonl            # macOS, Linux, SteamOS
.venv\Scripts\python.exe organize.py gdrive --undo runs/<data>_<nome>/log.jsonl   # Windows
```

## Em outra máquina

1. Repita os passos 1, 2 e 4 da instalação. Use a mesma credencial, disponível em **Google Auth Platform → Clientes** no seu projeto. Como a chave secreta só aparece durante a criação, guarde-a num gerenciador de senhas ou crie uma nova chave no mesmo cliente.
2. Pronto. As execuções anteriores (`runs/`) não são incluídas no Git, pois contêm transcrições e IDs do seu Drive.

## Os scripts

| Arquivo | O que faz |
|---|---|
| `extract_audio.py` | baixa apenas o áudio de cada vídeo e gera um WAV 16 kHz |
| `transcribe.py` | transcreve com faster-whisper (CPU) |
| `inspect_media.py` | coleta horários e volume, extrai um quadro de cada vídeo, lê o EXIF das fotos e gera folhas de contato |
| `organize.py` | cria pastas, move e renomeia arquivos, grava descrições, registra as operações e confere o resultado; `--undo` desfaz as alterações |
| `make_sheet.py` | gera a planilha de-para com as abas De-para e Log |
| `skill/SKILL.md` | define o roteiro que o Claude Code segue em `/organizar-drive` |

A única etapa que não é feita por um script é a decisão de qual pasta deve receber cada vídeo. O Claude analisa as transcrições e as folhas de contato e monta o `plan.json`.

## Limites

- A transcrição roda na CPU. No Steam Deck, leva cerca de 15 minutos para processar 40 minutos de vídeo. O tempo depende da duração dos vídeos, não do tamanho em GB.
- Os scripts só trabalham com os arquivos que estão na raiz da pasta, sem entrar nas subpastas.
- Fuso horário: o MP4 da câmera registra a hora em UTC, enquanto o EXIF da foto usa a hora local. O padrão é Brasília (`utc_offset: -3` em `config.json`).

## Licença

MIT
