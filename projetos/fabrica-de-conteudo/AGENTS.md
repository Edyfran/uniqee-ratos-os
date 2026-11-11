# Fábrica de Conteúdo com IA

Esta pasta é a Fábrica de Conteúdo com IA: o vídeo que o usuário gravou vira reel editado
(corte, legenda, peças, trilha e capa), a partir de um plano, sem ferramenta paga. Rode tudo
da raiz desta pasta.

- **Responda sempre em português do Brasil**, inclusive as linhas de status do começo
  ("conferindo o uv e o ffmpeg…"). Nada de inglês na conversa com o usuário; só nomes de
  comando, arquivo e campo ficam como são. Frase curta, palavra simples, sem jargão. Toda
  resposta diz o que você fez, o que vem agora e quanto tempo leva.
- **Chaves:** o `.env.local` nunca é aberto, lido nem buscado: nada de `grep`, `cat`,
  `head`, `sed`, `Read` ou busca de arquivo nele, que imprimem o valor no log da sessão.
  Para saber o que está preenchido, rode só
  `uv run python tools/video-use/helpers/confere_env.py` (diz "preenchida" ou "vazia", nunca
  o valor; aceita nomes: `... confere_env.py VOZ_ID`). Nunca leia chave de fora desta pasta
  (`~/.hermes`, `~/.config`, o ambiente de outro projeto).

- **Resolva antes de devolver.** Todo erro tem causa: leia a mensagem, ache a causa e conserte
  você mesmo (instale o programa que falta, peça a permissão, rode de novo) antes de levar ao
  usuário. Ele só ouve o que só ele pode fazer: senha, chave, uma escolha, aprovar algo pago.
  O limite: nunca edite teste nem helper do pacote, nem apague arquivo dele. Falha que mora no
  pacote vira Chamado da Academy, e o resto do trabalho segue.

- **A conversa começou fora desta pasta** (o usuário arrastou o ZIP): siga o bloco do
  agente que recebeu o ZIP, no topo do `INSTALAR.md`. A pasta fica ao lado do ZIP (ou dentro
  da pasta de projeto vazia onde a conversa abriu), todo comando roda da raiz dela, e o
  trabalho segue nesta mesma conversa.
- Antes de qualquer vídeo, leia a skill `fabrica-de-conteudo`, em
  `.agents/skills/fabrica-de-conteudo/SKILL.md`. Se não existe o arquivo `.fabrica-ok`
  na raiz, comece pela seção "Primeira vez nesta máquina" do `INSTALAR.md`.
- Se o usuário pedir onboarding, começar ou configurar a fábrica, siga a skill
  `fabrica-onboarding` (`.agents/skills/fabrica-onboarding/SKILL.md`); no Claude Code é o
  comando `/onboarding`. É uma página local com uma escolha por tela (estilo, cores, letras, logo,
  legenda), uns 10 minutos, que salva sozinha. Suba a página e fique livre: quando o aluno disser que
  terminou, aplique as escolhas. Ela não pede vídeo, tipo de vídeo nem roteiro.
- **Use os comandos da Fábrica.** Todo vídeo sai pela cadeia: um plano num estilo, conferido e
  renderizado pelo `fabrica.py`. Não monte vídeo nem a base dele com `ffmpeg` à mão, e não
  escreva script por fora: o que falta à cadeia ela recusa e diz o campo.
- **Antes de todo render**, rode
  `uv run python tools/video-use/helpers/fabrica.py plano.json --seco`. Mostre ao usuário o total
  e o tempo de cada passo (a saída diz se o tempo é "medido" ou "estimado") e espere o ok. O
  comando inteiro de cada passo só aparece com `--detalhe`. No render, repasse a ele a linha de
  progresso de cada passo (`passo k/n · nome · s · faltam ~m min`).
- **Leia curto.** A fala vem de `transcript.py frases <transcript.json>` (com `--de S --ate S`
  para um trecho), nunca do JSON cru. As peças, de `v2.py lista --curta`. Os dois moram em
  `tools/video-use/helpers/` e `tools/v2/`.
- **Depois do primeiro vídeo**, rode `estilo.py pedidos <estilo do vídeo> --marca marca` (em
  `tools/video-use/helpers/`) e ofereça ao usuário os 3 pedidos prontos que ele imprime.
- **Com o Claude Code**, comando longo da Fábrica (render, transcrição, conferência) vai para o
  subagente `executor`, que devolve em até 5 linhas se deu certo, o tempo e onde está a saída.
  A leitura de um trecho da fala, para escolher cortes e peças, vai para o `trecho`, que devolve
  só o JSON. No Codex e no Gemini, rode direto.
- O critério de edição está nas outras skills `fabrica-*`, na mesma pasta. O
  `GUIA-DE-PEDIDOS.md` tem um pedido pronto para cada tipo de vídeo.
- O usuário mandou um vídeo de referência (arquivo ou link) e pediu "edita o meu igual a esse"? Siga a
  skill `fabrica-referencia` (`.agents/skills/fabrica-referencia/SKILL.md`): lê a referência (inclusive o
  layout e a densidade de motion), escolhe o layout, o estilo e a legenda mais próximos, edita o vídeo dele e
  entrega a folha lado a lado. Referência com painel e peças não se entrega só com a legenda dela.
- A voz clonada e o avatar (módulo Crie seu Clone de IA, skill `fabrica-clone`), as cenas geradas
  por IA (módulo Cenas de Cinema com IA, skill `fabrica-cinema`) e o vídeo deitado, 16:9 (módulo YouTube
  Completo, skill `fabrica-youtube`) vêm em módulos. Sem a pasta da skill
  em `.agents/skills/`, o módulo não está instalado: diga isso ao usuário e não peça chave.
- Nada pago roda sozinho: voz, avatar e cena param no passo que cobra e esperam o sim
  do usuário.
- Se existe a pasta `marca/` na raiz, ela é a marca do usuário e vale em todo vídeo:
  antes de escrever roteiro, leia `marca/MARCA.md` (quem ele é, o que vende, o tom, o
  que nunca falar); use os estilos dela (`marca/estilos.json`, que o `estilo.py` lista
  junto com os do kit) e os pedidos prontos de `marca/PEDIDOS.md`. Para instalar ou
  conferir uma marca, siga `marca/INSTALAR-MARCA.md`.
- Para criar a marca do usuário a partir de um estilo, das cores e da letra (o pedido do
  `docs/guia-de-estilos.md`), siga a seção "A marca feita aqui" da skill `fabrica-estilo`.
- **Atualizar a Fábrica.** Se o usuário disser `/atualizar` ou "atualiza a fábrica", ou mandar um ZIP novo
  da Fábrica com esta pasta já instalada (existe o `.fabrica-ok`), é atualização e não instalação: não
  descompacte por cima nem refaça a instalação. Siga `.claude/commands/atualizar.md` (no Codex, leia o
  arquivo e siga): `tools/video-use/helpers/atualiza.py`, primeiro com `--seco`, depois de verdade, e a
  conferência no fim. Ele guarda a cópia do que troca em `.fabrica/copia/` e não toca no `.env.local`,
  na `marca/`, no `onboarding/` nem em `videos/`.
- **No começo de cada conversa**, se existe o `.fabrica-ok`, rode
  `uv run python tools/video-use/helpers/atualiza.py --aviso`. Se ele imprimir uma frase, abra a
  primeira resposta com ela. Só avise; não atualize sem o usuário pedir.
- Módulo novo (o ZIP de um order bump, como o Crie seu Clone de IA ou o Sistema de Postagens Automáticas): da raiz desta pasta,
  `unzip -o <caminho do zip> -d .` (no Windows, `tar -xf <caminho do zip>`), e depois o
  `test_*.py` que veio nele e o `uv run python tools/v2/v2.py biblioteca` (o módulo do YouTube
  põe as animações 16:9 no `biblioteca.html`). A skill do módulo fica em `.agents/skills/` com as outras, e o
  `/onboarding` passa a mostrar a tela dele. O Codex pode deixar `.agents/` só para leitura: se o
  comando não gravar lá, rode o mesmo comando de novo pedindo permissão para sair do sandbox (o
  usuário aprova). Só diga que instalou quando existir `.agents/skills/<módulo>/SKILL.md`.
- Estilo do Pack de Estilos de Edição (`pack-<estilo>.zip` ou `pack-todos.zip`): descompacte como um
  módulo e rode `uv run python .agents/skills/fabrica-momentos/scripts/instala.py`. O estilo entra no
  `marca/estilos.json` e aparece no `estilo.py`. Depois rode `uv run python tools/v2/v2.py biblioteca`:
  o estilo entra no `biblioteca.html`, no filtro Estilos do Pack. "Faz no <estilo>" é a skill `fabrica-<estilo>`.
