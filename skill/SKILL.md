---
name: organizar-drive
description: Organiza uma pasta do Google Drive com vídeos/fotos soltos da câmera em pastas de conteúdo, lendo a transcrição, o horário de gravação e a imagem de cada arquivo. Renomeia com resumo curto, põe a transcrição na descrição, gera planilha de-para + log e avisa no WhatsApp. Use quando o usuário pedir /organizar-drive, ou pedir para separar/organizar vídeos de uma pasta do Drive por conteúdo/assunto.
argument-hint: <link da pasta do Drive> <conteúdo 1>, <conteúdo 2>, ...
---

# /organizar-drive

Entrada: link de uma pasta do Google Drive + lista de conteúdos (ex.: "1. Workshop, 2. Relato da aluna X, 3. Convite da professora Y"). Se faltar algum dos dois, pergunte antes de começar.

Tudo roda em backend pela API do Drive. O navegador só entra no fim, para o aviso no WhatsApp.

## Ambiente

- Repositório: `{{REPO}}` (`R` abaixo). Python com as dependências: `{{PY}}` (`VPY`). Use sempre esse Python, em qualquer sistema (Windows, macOS, Linux, SteamOS).
- Configuração: `R/config.json` (`remote`, `whisper_model`, `utc_offset`, `whatsapp_chat`). Antes do passo 4, defina a variável de ambiente `UTC_OFFSET` com o valor de `utc_offset` (bash: `export UTC_OFFSET=-3`; PowerShell: `$env:UTC_OFFSET=-3`).
- O remote do rclone (padrão `gdrive`) precisa usar **uma credencial OAuth própria** do Google Cloud (README, passo 2). A credencial compartilhada do rclone vive dando 403 rateLimitExceeded.
- Se `rclone lsf <remote>:` reclamar do token: `rclone config reconnect <remote>:` (abre o login do Google; o usuário clica em Permitir).

## Passos

1. **Apontar para a pasta.** Pegue o ID do link (`/folders/<ID>`) e rode `rclone config update <remote> root_folder_id=<ID>`. Crie a pasta de trabalho `RUN=R/runs/<AAAA-MM-DD>_<nome-curto>`. Rode `rclone lsf <remote>:` e diga ao usuário quantos vídeos, fotos e outros arquivos existem, e se já há subpastas. Os scripts só movem o que está na raiz.
2. **Áudio:** `VPY -I R/extract_audio.py <remote> $RUN` (em background). Baixa só os bytes de áudio dos MP4/MOV e gera um WAV 16 kHz por vídeo.
3. **Transcrição:** `VPY -I R/transcribe.py $RUN <whisper_model>` (em background; cerca de 15 min para 40 min de vídeo numa CPU de notebook). Gera um `<nome>.json` por vídeo.
4. **Sinais:** `VPY -I R/inspect_media.py <remote> $RUN`. Gera `signals.json` (hora local, duração, volume, transcrição, imagem) e as folhas de contato `sheet_videos_N.jpg` / `sheet_fotos_N.jpg`. **Abra as folhas de contato com Read e olhe.** A imagem faz parte da decisão.
5. **Classificar** (é você que faz). Leia todas as transcrições em ordem de horário e as folhas de contato. Lógica de decisão:
   - **Fala clara** sobre o conteúdo → classifica pela fala.
   - **Pouca ou nenhuma fala** (volume < −45 dB, ou transcrição vazia ou incoerente) → use o **horário**: gravado entre clipes do mesmo conteúdo, com poucos minutos de diferença, provavelmente é desse conteúdo. Some a isso a **imagem**: mesmo cenário, mesma pessoa, mesmas peças.
   - Horário + imagem concordam → move, confiança **alta**. Só um dos dois → move, confiança **média**. Sinais em conflito → pasta `Revisar` (só nesse caso).
   - Um bloco claramente de **outro assunto** fora da lista → pasta `N. Outros - <o que é>`, confiança alta, e não `Revisar`. Avise o usuário.
   - **Fotos:** a hora do EXIF já é local; a hora do MP4 vem em UTC e o `inspect_media` já converte. Compare horário e imagem com os blocos de vídeo.
   - Duplicados ("Cópia de …") vão para a pasta do original, com aviso no motivo.
6. **Plano:** escreva `$RUN/plan.json` no formato `{ "<nome atual>": {"pasta": "...", "novo_nome": "...", "duracao": s, "motivo": "... Confiança: alta.", "descricao": "...", "transcricao": "..."} }`.
   - `novo_nome`: nome original + `_` + resumo de 1 a 3 palavras, minúsculas, com hífen, sem acento (`C8940_dobrar-arame.MP4`). Fotos mantêm o nome (omita `novo_nome`).
   - `descricao` (vai para o campo Descrição do arquivo no Drive): `[<pasta> · confiança X] <motivo>\n\nTranscrição: <texto ou (sem fala)>`.
   - `motivo`: cite os sinais, com horário local (ex.: "Sem fala. Gravado 11h22, entre C8935 e C8937 (Workshop). Imagem: o professor na sala do workshop. Confiança: alta.").
   - Nomes de pasta: os conteúdos do usuário, numerados na ordem dele.
7. **Executar:** `VPY -I R/organize.py <remote> $RUN/plan.json`. Cria as pastas, move, renomeia, grava a descrição, registra em `$RUN/log.jsonl` e confere pasta por pasta. Se aparecer "FALTANDO", rode de novo (é idempotente).
8. **Planilha:** `VPY -I R/make_sheet.py $RUN "$RUN/De-para.xlsx"` e depois `rclone copyto "$RUN/De-para.xlsx" "<remote>:De-para videos e fotos.xlsx" --drive-import-formats xlsx` (o rclone converte para Planilha Google). Link: `rclone lsjson <remote>: --files-only` → `https://docs.google.com/spreadsheets/d/<ID>`.
9. **WhatsApp** (se `whatsapp_chat` estiver preenchido e o Claude in Chrome conectado): abra uma aba nova em web.whatsapp.com, busque o chat e clique no resultado pelo `ref` do `find` (clique por coordenada já abriu conversa errada). Mande uma linha só: total movido + erros, contagem por pasta, link da planilha. Feche a aba.
10. **Responder ao usuário:** tabela pasta → quantidade, o que ficou com confiança média ou baixa, duplicados, e o comando para desfazer.

## Desfazer

`VPY -I R/organize.py <remote> --undo $RUN/log.jsonl` devolve cada arquivo à pasta de origem, com o nome original, de trás para frente. As pastas criadas ficam vazias.

## Regras

- Nunca troque o nome original da câmera, só acrescente o resumo.
- Não mande para a lixeira nem apague arquivos do usuário. Pode mandar para a lixeira só pastas vazias ou arquivos que você mesmo criou.
- Se o usuário disse para executar o fluxo inteiro, não peça aprovação antes de mover. Caso contrário, mostre o plano primeiro.
