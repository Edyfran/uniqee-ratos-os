---
name: setup
description: >
  Configura o RatosOS pro seu negócio: entrevista curta (quem você é, o que faz, o que usa,
  onde suas coisas moram na internet, como a sua marca é), preenche a memória do sistema,
  cria as pastas de trabalho, prepara este computador e termina com a página bem-vindo.html,
  o resumo do que ele aprendeu.
  Use quando o usuário chamar /setup, quando _contexto/empresa.md tiver <!-- NOT CONFIGURED -->,
  ou quando disser "configurar o sistema", "primeira vez", "setup", "começar do zero".
---

# /setup · configurar o sistema

Como esta skill se comporta: uma pergunta por vez, em conversa, esperando a resposta. Nunca
despejar a lista. Resposta vaga ganha **uma** pergunta de acompanhamento e segue (insistir cansa e
a pessoa abandona). Gera os arquivos todos de uma vez no fim, não durante as perguntas. Caminho de
pasta vem do mapa do `AGENTS.md`; os citados aqui são os de uma instalação nova.

## Passo 0 · ambiente (silencioso, antes de tudo)

Fazer sem alardear; só reportar no fim se algo falhar.

1. **A ponte pro Codex.** Este kit roda no Claude Code e no Codex; os dois precisam enxergar as
   skills. Rodar o script da ponte, que mora na pasta de scripts do sistema (`sistema/scripts/`):
   ```bash
   bash sistema/scripts/sync-ponte.sh                                     # Mac / Linux
   ```
   ```powershell
   powershell -ExecutionPolicy Bypass -File sistema\scripts\sync-ponte.ps1   # Windows, sempre este
   ```
   Detectar o sistema: `uname` respondendo `Linux` ou `Darwin` usa o `.sh`; qualquer cenário
   Windows (inclusive Git Bash, onde `uname` responde `MINGW*`/`MSYS*`) usa o `.ps1`. No Mac/Linux
   vira symlink e reflete as skills sozinho; no Windows vira junction, e só cai pra cópia se nem
   isso der (aí skill nova precisa re-sincronizar: o `/mapear` e o `/atualizar` rodam o script).
2. **A estrutura mínima existe?** `_memoria/diario/`, `_memoria/recados/` (com `.gitkeep`),
   `_memoria/decisoes.md`, `_contexto/marca/`, `.ratosos`. O kit já traz tudo; se algo faltar
   (alguém apagou), recriar em silêncio.

## Verificação inicial

Se `_contexto/empresa.md` já tem conteúdo real (sem `<!-- NOT CONFIGURED -->`), o setup já rodou.
Dizer isso e perguntar se quer refazer tudo ou só atualizar uma parte (aí ir direto à pergunta certa).

## Entrevista

Abrir com uma frase:

> "Boa. Vou te fazer algumas perguntas pra configurar o sistema pro seu negócio. Quanto mais
> específico, melhor ele trabalha pra você."

### 1 · Nome
"Qual é o seu nome e o nome do seu negócio?"

### 2 · O que você já tem
"Você já usa o Claude Code ou o Codex há algum tempo, ou é a primeira vez?"

- **Já usa:** "Quer que eu tente carregar o que você já tem configurado em outros projetos, ou
  prefere do zero?" Se quiser carregar: ler `~/.claude/CLAUDE.md` e a memória em
  `~/.claude/projects/` (e `~/.codex/` se existir), montar um resumo (nome, negócio, o que faz, tom,
  ferramentas), mostrar e pedir confirmação. Pular as perguntas já respondidas.
- **Primeira vez:** "Você usa outro assistente com frequência (ChatGPT, Claude na web, Gemini)? Se
  sim, dá pra puxar o contexto de lá." Se sim, mostrar este prompt pra ele colar lá e trazer a
  resposta:

  ```
  Preciso exportar o contexto do meu negócio das nossas conversas pra configurar uma ferramenta
  nova. Responda com o que sabe sobre mim, deixando em branco o que não souber:
  NOME · NEGÓCIO · O QUE FAZ (pra quem, 1-2 frases) · PRINCIPAIS ATIVIDADES · CLIENTES
  (externos, uso interno, os dois) · EQUIPE · FERRAMENTAS QUE USO · ONDE MEU SITE/EMAIL/LOJA
  ESTÃO HOSPEDADOS · IDENTIDADE VISUAL (cores, fontes, estilo) · COMO EU ESCREVO · O QUE EVITAR
  EM TEXTO DE IA · OUTROS DETALHES
  ```
  Com a resposta, extrair, mostrar o resumo, confirmar, pular o que já veio.

### 3 · O que você produz
"O que você mais produz no dia a dia? Pode ser mais de uma coisa." *(conteúdo, propostas,
relatórios, código, emails, apresentações...)*

### 4 · Pra quem
"Você atende clientes externos, usa o sistema pro seu próprio negócio, ou os dois?"

### 5 · Foco
"Qual é o seu principal foco agora? O que você está tentando fazer ou resolver nos próximos
meses?" *(lançamento, crescer um canal, fechar clientes, organizar a operação...)*

### 6 · Ferramentas
"Quais ferramentas você usa hoje no trabalho? Cita as principais." Depois, os sete assuntos que
todo negócio tem, em conversa (não como formulário):

> "E o que você usa hoje pra cada uma dessas coisas? Pode responder 'nada', é resposta: mensagem
> com cliente, tarefa e prazo, email, agenda, dinheiro entrando e saindo, ficha do cliente, reunião."

Isso vira o `_contexto/integracoes.md`. O que ele não tem fica como **não ligada**: é assim que
o agente sabe depois que aquilo é possível e está faltando, em vez de achar que não dá. Não ligar
nada ainda; é só o mapa.

### 7 · Onde suas coisas moram
"Onde ficam as suas coisas na internet: site, domínio, email, loja, área de membros, banco de
dados? Só o nome do serviço (Hostinger, Vercel, Shopify, Kiwify, Google Workspace...). Nada de
senha." Isso vira o `_contexto/infra.md`. Se não tem nada, tudo bem: a tabela fica vazia.

### 8 · Identidade visual
"Sua marca tem identidade visual? Se sim, como prefere compartilhar?"

> "Pode me mandar o link do site, jogar uns prints na pasta da marca (`_contexto/marca/`) e me
> dizer os nomes, descrever em texto (cores, estilo, fontes), ou dizer que ainda não tem."

- **URL:** buscar com WebFetch e tirar só a identidade: a cor principal, fundo, texto, as fontes e o
  logo, mais uma linha de clima. Nada de arredondamento, sombra, botão ou estrutura de página: o site
  é uma peça da marca, não a regra de todas. Mostrar antes de preencher: *"Vi no seu site: principal
  X, fundo Y, títulos em Z. Bate?"*
- **Prints:** ler como imagem, tirar o mesmo, mostrar antes de preencher.
- **Texto:** usar direto.
- **Não tem:** o guia fica em branco e cada peça escolhe um visual limpo até lá. Dizer isso em uma frase.

**Design system (só se existir):** se ele mandou um manual de marca, um Figma, um design system, ou
disse com todas as letras que quer tudo igual ao site, perguntar se as peças devem seguir aquilo à
risca. Com o sim, o resumo dos componentes vai pra parte 2 do guia (e o arquivo, se tiver, fica na
pasta da marca). Sem isso, a parte 2 fica vazia: é ela que separa "a marca" de "um molde".

**Logo (sempre):** "Tem o logo em PNG ou SVG? Se tiver, joga na pasta da marca e me diz o nome. Se
tiver versão pra fundo claro e escuro, manda as duas." Registrar na seção Logo do guia.

**A metade verbal (sempre):** "E quando eu escrever no seu lugar, pro seu cliente: trato por tu ou
por você? Pode ser informal ou tem que ser mais sério? Tem palavra ou promessa que você nunca
faria?" Se ele tiver um texto que ficou bom (email, proposta antiga), pedir pra colar: exemplo
real vale mais que descrição. Isso vira `_contexto/marca/tom-de-voz.md`.

### 9 · Como falar com você
"Como você prefere que eu escreva pra você aqui no chat? O que mais te incomoda em texto de IA?"
*("direto, sem enrolação" / "odeio travessão e 'mergulhe de cabeça'" / "pode ser informal")*.
Isso é `preferencias.md` (como o agente fala **com você**), diferente da 8 (como a marca fala com
o cliente).

### 10 · Equipe e máquinas
"Tem equipe ou é você que toca tudo? E você vai usar este sistema em mais de um computador?"

- Toca sozinho, um computador: **não perguntar mais nada**; a origem desta máquina é `dono`.
- Tem sócio, equipe, robô, ou mais de um computador: "Como você quer chamar este computador aqui?
  Um nome curto (ex: `mac-do-joao`, `notebook`). Quando outra pessoa ou outra máquina escrever no
  sistema, cada uma assina com o nome dela, e nada se atropela." Se este é o computador principal
  dele, a origem segue `dono`; o nome serve pros outros.

## Processamento

Detectar o perfil principal: `agencia` (vários clientes, processo de entrega) · `freelancer` (solo,
atende clientes) · `solopreneur` (negócio próprio, audiência/produto; inclui criador) · `empresa`
(equipe por setor). Um perfil pode ter traço de outro: usar o que descreve o uso principal.

## O que gerar

### 1. `AGENTS.md`: só os dois blocos que são seus

O `AGENTS.md` do kit é a constituição (boot, mapa, tabela, contrato). **Não reescrever o arquivo.**
Ler o trecho do perfil em `sistema/templates/perfis/agents-md-<perfil>.md` e preencher:

- o título (`# [Nome do negócio] · RatosOS`) e a frase de instalação (apagar "Se você acabou de
  instalar: rode /setup...");
- **seção 1, "O que é este sistema":** o bloco do perfil, com os colchetes preenchidos pelo que
  ele contou (4 a 8 linhas). Sem lista de ferramentas nem tom de voz: têm casa própria;
- **seção 9, "Mapa de pastas":** acrescentar as pastas de trabalho abaixo do comentário, uma linha
  por pasta ("`clientes/` · uma pasta por cliente").

`CLAUDE.md` tem que continuar com uma linha só: `@AGENTS.md`. Se estiver diferente, corrigir.

### 2. `_contexto/` (remover o `<!-- NOT CONFIGURED -->` de cada um que preencher)

- **`empresa.md`:** nome, negócio, o que faz, perfil, atende clientes, equipe, principais
  entregas, contexto adicional. Ferramentas **não** ficam aqui.
- **`estrategia.md`:** fase, prioridade principal, o que pode esperar, contexto com prazo (data
  absoluta).
- **`preferencias.md`:** tom no chat, o que evitar, estilo geral.
- **`integracoes.md`:** uma linha por ferramenta citada e uma por assunto dos sete (mesmo que
  "nada"). Colunas: pra quê · como o agente alcança (a decidir no passo 5) · estado (`não ligada`
  por padrão) · última checagem (hoje, AAAA-MM-DD).
- **`infra.md`:** uma linha por coisa hospedada. Sem chave, sem senha.
- **`agora.md`:** o estado inicial, pro primeiro `/iniciar` já mostrar algo:
  ```markdown
  ## Onde paramos
  Acabei de configurar o sistema com o /setup (AAAA-MM-DD). Próximo passo: /mapear.
  ## Pendências
  - Rodar /mapear pra criar as primeiras skills do dia a dia.
  ## Quente agora
  [vazio]
  ```
  Não inventar além disso: o `agora.md` é preenchido pelo uso, via `/atualizar`.

### 3. `_contexto/marca/`

`design-guide.md` com o que foi dito: a parte 1 (identidade) com logo, cores, fontes e clima; a parte
2 só se ele tem design system (pergunta 8). Campo sem resposta fica em branco. `tom-de-voz.md` novo, curto:
tratamento (tu/você), registro (formal/informal), o que nunca dizer, e o exemplo colado, se houver.

### 4. Pastas de trabalho

Antes de criar, **mostrar** a estrutura do perfil e deixar ajustar:

> "Com base no que você contou, a estrutura de **[perfil]** faz mais sentido. Ficaria assim:
> [lista]. Tenho outros modelos (por cliente · por tipo de conteúdo · por setor), ou montamos uma
> personalizada. Qual prefere?"

Criar cada pasta com `mkdir -p` e um `.gitkeep` dentro (git não guarda pasta vazia). Nada de
`tarefas.md` nem `dados/`: pendência vai pro `agora.md`, material bruto vai pra pasta do projeto.

### 5. `.origem`

Um arquivo na raiz, uma linha: `dono` ou o nome da máquina (minúsculas, sem espaço). Fica fora do
git de propósito: cada computador tem o seu.

### 6. Conectores (MCPs)

Ler o catálogo em `sistema/templates/integracoes/catalogo.md` e cruzar com a pergunta 6. Pra cada
ferramenta que tem conector: dizer o que ele faz, mostrar o comando, perguntar se instala agora.
Instalar só com o sim específico daquele conector; "faz tudo" não vale pra instalar nada.
Instalou: `integracoes.md` ganha `ligada` + "MCP" na coluna de alcance. Ficou pra depois: uma
pendência no `agora.md` com o comando. Ferramenta fora do catálogo: "não tenho conector pronto pra
X; se achar um em mcp.so, me passa que eu instalo".

### 7. `bem-vindo.html`

Ler `sistema/templates/bem-vindo.template.html`, preencher e salvar `bem-vindo.html` na raiz.

A página tem a cara da Ratos de IA (quem fez o kit), não a da marca dele: cor, fonte e layout já
estão no modelo, e as imagens moram em `sistema/templates/bem-vindo/`. O comentário do topo fica no
arquivo final: é ele que avisa que a página não é referência pras peças do negócio.

- `DATA`: hoje, `DD/MM/AAAA`.
- `NOME` (só o primeiro nome), `NEGOCIO`, `RESUMO` (uma frase do que ele faz, nas palavras dele).
- `SABERES`: 4 a 6 `<li>` com pedaços reais das respostas ("70% do seu movimento vem de
  arquiteto"), não "contexto configurado". Cada um em uma ou duas frases.
- `PASTAS`: as pastas de trabalho, uma por pasta, no formato
  `<div class="no meu"><b>clientes/</b><p>uma pasta por cliente</p></div>`.
- `PASSOS`: três
  `<div class="passo"><div class="n">1</div><div><b>...</b><p>...</p></div></div>`: rodar
  `/mapear`; pedir a primeira tarefa de verdade, algo que ele faz toda semana (citar uma das
  entregas que ele contou); fechar a sessão com `/atualizar`. Comando vai em `<code>`.
- `LOGO`: se ele tem logo, `<div class="logo-cliente"><img src="_contexto/marca/<arquivo>" alt=""></div>`;
  vazio se não.
- Texto na voz dele (`preferencias.md`), frases curtas, **sem travessão**, sem "mergulhe",
  "desbloqueie", "jornada". Nada que ele não tenha dito.
- Conferir que não sobrou `{{` no arquivo: `grep -c '{{' bem-vindo.html` tem que dar 0.

### 8. Teste de aceite (na frente dele)

Reler **do disco** os três arquivos do boot e o `AGENTS.md`, como se fosse uma sessão nova, e
provar que funcionou com três fatos concretos:

> "Pra conferir: se eu entendi, você [fato 1 de empresa.md], o que mais pesa agora é [foco de
> estrategia.md], e comigo você quer [uma preferência]. Bateu?"

Errou algo: corrigir no arquivo e mostrar a linha. Conferência silenciosa junto: nenhum dos três
do boot ainda tem `<!-- NOT CONFIGURED -->`; `.origem` existe; `bem-vindo.html` sem `{{`. O setup
não escreve nada sobre `/syncar` no `AGENTS.md`: quem faz isso é o próprio `/syncar`, quando ligar.

## Mensagem final

> "[Nome], seu sistema está configurado. Abre o `bem-vindo.html` que está na pasta: é o resumo
> do que eu aprendi sobre você.
>
> O que existe agora: `AGENTS.md` (as regras e o mapa) · `_contexto/` (negócio, preferências,
> foco, ferramentas, infra, marca) · `_memoria/` (vai enchendo sozinha a cada sessão) · pastas de
> [perfil] · [N] conectores instalados, [N] anotados pra depois.
>
> Chave de API vai sempre num arquivo `.env`, que nunca sai daqui. Se um dia você quiser cópia na
> nuvem ou usar o sistema em outro computador, o `/syncar` liga o GitHub em 2 minutos. Se não
> quiser, tudo bem: eu não volto no assunto.
>
> Próximo passo: `/mapear`, pra eu entender o seu dia a dia e criar skills pra ele."

## Regras

- Tom direto e humano, sem entusiasmo de vendedor.
- Perguntas em conversa, nunca em lista com bullets.
- Não inventar dado; campo que ele não respondeu fica em branco.
- Não reescrever o `AGENTS.md` inteiro; só os dois blocos dele.
- Depois de gerar, a mensagem final resumida; não listar cada linha de cada arquivo.
