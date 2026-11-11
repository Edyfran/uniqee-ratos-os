# Fábrica de Conteúdo com IA — Instalação

O jeito mais curto: arraste o ZIP para a conversa do seu agente e peça "instala e me
explica".

**Para o agente que recebeu o ZIP numa conversa aberta fora da pasta:**

1. Se a conversa já abriu numa pasta de projeto vazia, fora do iCloud, OneDrive e Google
   Drive, descompacte nela. Senão, descompacte perto do ZIP (em geral Downloads) ou na
   pasta pessoal. Nunca numa pasta temporária, que o sistema apaga; é ali que o aluno vai
   trabalhar todo dia. Se o ZIP está no iCloud Drive, no OneDrive ou no Google Drive,
   descompacte na pasta pessoal, porque a nuvem tira arquivo do disco no meio da
   instalação. Se já descompactou numa pasta temporária, mova você mesmo, antes de instalar.
2. Leia o `AGENTS.md` da pasta nova e siga a partir dele, rodando todo comando da raiz dela.
3. No fim, diga ao aluno o caminho da pasta e continue nesta mesma conversa: o próximo
   pedido dele (o vídeo) roda daqui. Não peça para ele mover nada nem abrir outra
   conversa agora. Para as próximas conversas, diga que é só escolher essa pasta ao
   abrir uma conversa nova no agente. Diga também que, se ele quiser escolher estilo, cores, letras,
   logo e legenda antes do primeiro vídeo, é só pedir `/onboarding` (uns 10 minutos, numa página).
   E que o `biblioteca.html`, na raiz da pasta, mostra tudo o que a fábrica anima: dois cliques
   e abre no navegador.

Prefere descompactar você mesmo? Descompacte onde quiser, fora da nuvem (Downloads ou a
pasta pessoal servem), abra o seu agente **dentro** da pasta `fabrica-de-conteudo` e cole
este pedido:

```
Esta pasta é a Fábrica de Conteúdo com IA. Siga a seção "Primeira vez nesta
máquina" do INSTALAR.md, que está nesta pasta: instale o que faltar no meu
computador, rode a conferência até passar e me diga no fim o que fez. Se algo
pedir senha de administrador, me avise antes.
```

O agente descobre o seu sistema (Mac, Windows ou Linux) e instala o que falta.
Leva uns 10 minutos; se não há chave da ElevenLabs, baixar o modelo de transcrição (~3 GB)
soma mais alguns, conforme a sua internet. Se a conferência acusar um defeito do pacote, ele avisa e
segue; mande o arquivo `conferencia.txt`, que a conferência grava na pasta, num
Chamado da Academy.

Sai versão nova toda semana. Para atualizar depois, baixe o ZIP novo na aula da Fábrica e peça ao agente,
com a pasta instalada aberta, `/atualizar` (no Codex: "atualiza a fábrica"). A marca, as chaves e os vídeos
ficam como estão, e a cópia do que mudou fica em `.fabrica/copia/`.

## Qual agente

Qualquer agente de IA que rode comandos no seu computador e leia skills. As
skills moram em `.agents/skills/`, a pasta do padrão aberto de skills, que o Codex
lê; o Claude Code acha a cópia delas em `.claude/skills/`. As instruções da pasta
estão no `AGENTS.md`, e o `CLAUDE.md` e o `GEMINI.md` apontam para ele.

O Claude Code pede o Claude Pro ou acima; o Codex, o ChatGPT Plus ou acima.

**No Codex, troque as permissões para Acesso total antes de colar o pedido** (no
terminal: `codex --sandbox danger-full-access`). A fábrica abre um navegador para
desenhar as peças, e o modo padrão do Codex bloqueia: três testes da conferência
falham com `Permission denied`. Com Acesso total o Codex roda comandos sem pedir
licença, então use nesta pasta.

Outro agente que leia `.agents/skills/` deve achar o pacote do mesmo jeito, mas não
foi testado.

Sem chave da ElevenLabs, a transcrição roda na sua máquina e o modelo dela (~3 GB) baixa
agora, na instalação, uma vez só: o primeiro vídeo não espera por ele. Com a chave, a
transcrição vai para a nuvem e não baixa nada.

## As chaves

Toda chave (só os módulos pedem chave) mora num arquivo só: o `.env.local`, na raiz da pasta. Ele é seu e
não vai para ninguém. O `.env.local.exemplo` diz o que preencher.

## O que cobra, e onde

Nada, se você não puser a chave da ElevenLabs. O corte, as peças, a legenda, a capa e a
mixagem rodam na sua máquina, de graça, e a transcrição também; você só precisa do agente
(o Claude Pro ou o ChatGPT Plus, acima). A trilha, sem a sua, é uma das três faixas CC0 de
`exemplos/trilhas/`.

Se você puser `ELEVENLABS_API_KEY` no `.env.local`, a transcrição vai para a nuvem da
ElevenLabs e gasta crédito da sua conta, a cada vídeo. Não pôs a chave, não gasta.

A voz clonada e o avatar (módulo Crie seu Clone de IA) e as cenas geradas por IA (módulo Cenas de
Cinema) usam ferramentas pagas nos sites delas. Quem tem o módulo acha o que cada uma
cobra na skill dele (`fabrica-clone`, `fabrica-cinema`), e a fábrica nunca gasta sozinha:
num passo pago ela para, mostra o comando e espera você.

## Primeira vez nesta máquina

Se existe `.fabrica-ok` na raiz, pule esta seção. Se não, faça isto antes de qualquer
vídeo, sem parar a cada passo.

**No Mac e no Windows nada aqui pede senha: nunca rode `sudo` nem instale o Homebrew.**
Se algo pedir senha mesmo assim (no Linux, o `apt`), mande o comando ao usuário (no
Claude Code, `! <comando>`) e diga, na mesma mensagem, que a senha não aparece enquanto
ele digita e que, quando terminar, ele escreve **pronto** aqui: você não vê sozinho o fim
de um comando que ele rodou.

Os comandos desta seção são de bash. Num terminal que não é bash (o PowerShell do
Windows), rode o equivalente.

**1. Sistema.** `uname -sm`. No Windows, pelo Git Bash, a resposta começa com `MINGW64`.

**2. O que falta.**

| Sistema | Comandos |
|---|---|
| Mac | o bloco abaixo, sempre, mesmo com Homebrew: o ffmpeg do Homebrew vem sem a legenda |
| Windows | confira `ffmpeg -version`, `ffprobe -version` e `uv --version` e instale só o que faltar: `winget install -e --id Gyan.FFmpeg`, `winget install -e --id astral-sh.uv` e `winget install -e --id Python.Python.3.12`; depois `setx PYTHONUTF8 1` e, nesta sessão, `export PYTHONUTF8=1` |
| Linux | `sudo apt install ffmpeg` (Fedora: `sudo dnf install ffmpeg`) e `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

No Mac, tudo na pasta do usuário, sem senha (uns 2 minutos):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
a=$(uname -m | sed s/x86_64/amd64/)
for b in ffmpeg ffprobe; do
  curl -fsSL "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$a/release/$b.zip" -o "/tmp/$b.zip"
  unzip -qo "/tmp/$b.zip" -d ~/.local/bin
done
export PATH="$HOME/.local/bin:$PATH" && ffmpeg -version | head -1 && uv --version
```

O instalador do uv grava o `~/.local/bin` no perfil, para as próximas conversas. Nesta, se
um comando não achar `uv` ou `ffmpeg`, comece-o com `export PATH="$HOME/.local/bin:$PATH" &&`.

Depois, na raiz:

```bash
uv sync                               # Python 3.10+ e as dependências do pyproject.toml
uv run playwright install chromium    # no Linux: install --with-deps chromium
[ -f .env.local ] || cp .env.local.exemplo .env.local   # as chaves o usuário preenche depois
```

Se o uv não instalar de jeito nenhum: `python -m venv .venv`, as dependências do
`pyproject.toml` pelo `pip` desse `.venv`, e `.venv/bin/python` (Windows:
`.venv/Scripts/python`) no lugar de `uv run python` daqui em diante.

**3. Conferência.** Um comando só. Não chama ferramenta paga e não lê chave.

```bash
uv run python tools/video-use/helpers/confere.py
```

O padrão é a conferência rápida (uns 15 segundos). Para rodar a suíte inteira (uns 10 minutos),
use `--tudo`.

Passou: ele grava o `.fabrica-ok` e diz "Pronto". Falhou: ele imprime o conserto em
português; aplique e rode de novo, até passar. Se disser "defeito do pacote": nunca edite
teste ou helper, nunca apague arquivo do pacote. Leia o teste que falhou e o erro. Se a causa
é da máquina (um programa que falta, como o git, uma permissão, o PATH), conserte e rode de
novo. Se é do pacote, diga ao usuário numa frase o que falhou, peça que mande o
`conferencia.txt` (na raiz desta pasta) num Chamado da Academy e siga com o que ele pediu:
o onboarding e o primeiro vídeo não esperam o Chamado. A mesma falha depois de três
consertos também vai pro Chamado. Com um módulo instalado, faça também a conferência
dele, na skill do módulo (abaixo).

Para conferir de novo (pacote novo, computador novo), apague o `.fabrica-ok`.

**4. O modelo de transcrição.** Pule este passo se

```bash
uv run python tools/video-use/helpers/confere_env.py ELEVENLABS_API_KEY
```

disser `preenchida`: com a chave a transcrição vai para a nuvem e não baixa nada. Se disser
`vazia`, avise o usuário numa frase: "vou baixar o modelo de transcrição, uns 3 GB, uma vez só".
Depois baixe, transcrevendo a música de exemplo (leva alguns minutos, conforme a internet):

```bash
uv run python tools/video-use/helpers/transcribe.py exemplos/reel-editorial/trilha.m4a --edit-dir .fabrica/aquecimento
```

Se a rede cair no meio, rode o mesmo comando de novo. Se o usuário pedir para
não baixar agora, o modelo baixa no primeiro vídeo e esse vídeo demora mais.

## Depois

Com a conferência passando, é pedir:

```
corta o vídeo que eu gravei no celular em ~/Downloads/gravacao.mp4 e põe legenda
```

O agente escreve o plano, confere sem renderizar e mostra o que vai custar antes
de qualquer passo pago. O `GUIA-DE-PEDIDOS.md` tem um pedido pronto para cada tipo
de vídeo, técnica e etapa.

Para ver tudo o que a fábrica anima (abertura, frase na tela, número, chamada, efeito), abra o
`biblioteca.html`, na raiz da pasta, com dois cliques. O botão "copiar" de cada animação dá o
pedido pronto para colar no agente.
