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

O projeto é compatível com **Windows, macOS, Linux e SteamOS** (Steam Deck no modo Desktop).

Os passos 1 e 2 têm instruções específicas para cada sistema operacional. Os passos 3 e 4 são iguais para todos.

### 1. Instalar os programas necessários

Você vai precisar de Git, [Claude Code](https://claude.com/claude-code), Python 3.10+, `ffmpeg` e `rclone`.

Siga apenas as instruções do seu sistema operacional.

**Windows** (PowerShell):

```powershell
winget install Git.Git
winget install Python.Python.3.13
winget install Gyan.FFmpeg
winget install Rclone.Rclone
irm https://claude.ai/install.ps1 | iex
```

Ao terminar, feche e abra o PowerShell para que os programas instalados sejam reconhecidos.

**macOS** (Terminal):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git python ffmpeg rclone
curl -fsSL https://claude.ai/install.sh | bash
```

A primeira linha instala o Homebrew. Antes de executar a segunda, siga as instruções de "Next steps" exibidas ao final da instalação para adicionar o `brew` ao PATH.

**Linux** (terminal). Execute os comandos correspondentes à sua distribuição:

```bash
# Ubuntu e Debian
sudo apt update && sudo apt install git python3 python3-venv ffmpeg rclone

# Fedora (o ffmpeg completo vem do RPM Fusion)
sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install git python3 rclone
sudo dnf install ffmpeg --allowerasing

# Arch
sudo pacman -S git python ffmpeg rclone
```

Depois, instale o Claude Code, independentemente da distribuição:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**SteamOS** (Konsole, no modo Desktop). Git, Python, ffmpeg, curl e unzip já vêm instalados. Como o sistema é somente leitura, o `rclone` será instalado na sua pasta pessoal:

```bash
mkdir -p ~/.local/bin && cd /tmp
curl -LO https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip -j -o rclone-current-linux-amd64.zip '*/rclone' -d ~/.local/bin
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
curl -fsSL https://claude.ai/install.sh | bash
```

Ao terminar, feche e abra o Konsole.

### 2. Baixar e instalar o projeto

Execute os comandos correspondentes ao seu sistema operacional.

**Windows** (PowerShell):

```powershell
git clone https://github.com/reset-hightide/drive-video-sorter.git
cd drive-video-sorter
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

O `-ExecutionPolicy Bypass` permite executar este script sem alterar permanentemente a política de execução do PowerShell, que bloqueia scripts por padrão.

**macOS, Linux e SteamOS** (terminal):

```bash
git clone https://github.com/reset-hightide/drive-video-sorter.git
cd drive-video-sorter
./setup.sh
```

Em todos os sistemas, o instalador verifica se os programas necessários estão disponíveis e orienta como resolver eventuais pendências. Em seguida, ele:

1. Cria o ambiente `.venv` e instala as dependências.
2. Copia `config.example.json` para `config.json`.
3. Instala a skill `/organizar-drive` em `~/.claude/skills/`.

### 3. Criar sua credencial do Google (uma vez, uns 10 minutos)

A credencial padrão do rclone é compartilhada entre todos os usuários e pode atingir o limite de cota, causando o erro 403. Ao criar sua própria credencial, você passa a ter uma cota exclusiva. O processo é gratuito e não exige cartão.

Use a mesma conta Google que tem acesso às pastas do Drive. As instruções usam os nomes da interface em português, com os equivalentes em inglês entre parênteses.

**3.1. Criar o projeto**

1. Acesse [console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).
2. Em **Nome do projeto** (Project name), digite `drive-video-sorter`. Mantenha as demais configurações.
3. Clique em **Criar** (Create) e aguarde uns 10 segundos.
4. No seletor do topo da página, confirme que o novo projeto está selecionado.

**3.2. Ativar a Google Drive API**

1. Acesse [console.cloud.google.com/apis/library/drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com).
2. Clique em **Ativar** (Enable).

**3.3. Configurar a tela de login**

1. Acesse [console.cloud.google.com/auth/overview](https://console.cloud.google.com/auth/overview) e clique em **Vamos começar** (Get started).
2. **Informações do app** (App information): em **Nome do app**, digite `Drive Video Sorter`. Em **E-mail para suporte do usuário**, selecione seu e-mail. Clique em **Avançar** (Next).
3. **Público** (Audience): escolha conforme o tipo de conta e clique em **Avançar**.
   - **Interno** (Internal): para contas do Google Workspace (e-mail da empresa). O login não expira.
   - **Externo** (External): para contas pessoais do Gmail. O app fica em modo de teste e o login expira a cada 7 dias. Quando isso acontecer, execute `rclone config reconnect gdrive:` e clique novamente em **Permitir**.
4. **Dados de contato** (Contact information): digite seu e-mail, pressione Enter e clique em **Avançar**.
5. **Concluir** (Finish): marque **Eu concordo com a Política de Dados do Usuário dos serviços de API do Google**, clique em **Continuar** e depois em **Criar** (Create).
6. Apenas para **Externo**: no menu lateral, acesse **Público-alvo** (Audience). Em **Usuários de teste**, clique em **Adicionar usuários** (Add users) e adicione seu e-mail.

**3.4. Criar o cliente**

1. Acesse [console.cloud.google.com/auth/clients/create](https://console.cloud.google.com/auth/clients/create).
2. Em **Tipo de aplicativo** (Application type), selecione **App para computador** (Desktop app). Mantenha o nome sugerido.
3. Clique em **Criar** (Create).
4. Na janela que aparecer, copie o **ID do cliente** (Client ID) e a **Chave secreta do cliente** (Client secret). Guarde os dois em um gerenciador de senhas. A chave secreta só aparece nessa janela. Se você perdê-la, poderá criar uma nova no mesmo cliente.

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
.venv/bin/python organize.py gdrive --undo runs/<data>_<nome>/log.jsonl              # macOS, Linux, SteamOS
.\.venv\Scripts\python.exe organize.py gdrive --undo runs/<data>_<nome>/log.jsonl   # Windows (PowerShell)
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
