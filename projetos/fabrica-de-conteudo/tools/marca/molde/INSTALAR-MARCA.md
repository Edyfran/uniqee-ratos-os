# Instalar a marca na fábrica

Para o agente. O usuário colou um pedido assim:

```
instala a minha marca na fábrica: o zip está em <caminho>
```

Siga os passos em ordem, sem pular. No primeiro que falhar, pare e vá ao passo 7. Os
comandos são de bash, rodados da raiz da fábrica (a pasta com o `AGENTS.md`). No
PowerShell do Windows, rode o equivalente.

**Nunca mostre o conteúdo do `.env.local` na conversa, nem o valor de uma chave.** Não
abra o arquivo com `cat`, não leia com ferramenta de leitura, não cole trecho dele.

## 1. A fábrica

Na raiz tem que existir `.fabrica-ok`. Se não existe, siga primeiro a "Primeira vez
nesta máquina" (`AGENTS.md`) até o fim e volte para cá.

## 2. A pasta da marca

```bash
mkdir -p /tmp/marca-nova && unzip -o "<caminho do zip>" -d /tmp/marca-nova
```

O zip traz uma pasta `marca/`. Se a fábrica já tem uma `marca/`, guarde a velha com a
data antes, sem apagar nada:

```bash
[ -d marca ] && mv marca "marca-$(date +%F)"
mv /tmp/marca-nova/marca ./marca
```

## 3. Os ids e a conferência

```bash
uv run python marca/instala.py
```

Ele junta o `VOZ_ID` e o `HEYGEN_LOOK` do pacote no `.env.local` sem tocar nas outras
linhas, e confere: o kit, os estilos, a letra, a placa, os ids e a chave. Também roda o
`--seco` de um reel no estilo da marca, que não gasta nada. Termina com
`ok  a marca está instalada` ou com a lista do que corrigir.

## 4. A chave da ElevenLabs

Se a lista disser que falta a `ELEVENLABS_API_KEY`, abra o `.env.local` no editor de
texto do usuário (Mac: `open -e .env.local`; Windows: `notepad .env.local`) e peça que
ele cole a chave na linha `ELEVENLABS_API_KEY=` e salve. A chave é a que ele mesmo criou
na conta dele (a aula 02 mostra onde). Depois:

```bash
uv run python marca/instala.py --chave
```

Isso abre a voz dele com a chave, sem gastar crédito. Tem que aparecer
`ok  a chave abre a voz "<nome da voz>"`.

## 5. Os estilos

```bash
uv run python tools/video-use/helpers/estilo.py
```

Os estilos da marca (os nomes que estão em `marca/estilos.json`) aparecem na lista, junto
com os do kit.

## 6. A cara

```bash
uv run python marca/instala.py --amostra
```

Abra `marca/_confere/amostra.jpg` para o usuário (Mac: `open`; Windows: `start`). É uma
peça da fábrica com a cor e a letra da marca dele. Pergunte se está certo.

Pronto. Diga ao usuário, em três linhas: a marca está instalada, os pedidos prontos estão
em `marca/PEDIDOS.md`, e o primeiro vídeo sai colando um deles.

## 7. Se um passo falhou

Pare. Não edite o pacote, os testes nem os helpers para passar. Escreva para o usuário
uma mensagem pronta para colar no WhatsApp da Ninja Academy (https://wa.me/5521923675575),
neste formato:

```
Instalação da marca travou.
Passo: <número e nome do passo>
Sistema: <saída de uname -sm>
Erro: <as linhas exatas do erro, sem nenhuma chave>
```
