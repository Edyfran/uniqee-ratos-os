---
name: mapear
description: >
  Entrevista o usuário sobre seus processos repetitivos e cria pastas e skills
  personalizadas pro dia a dia dele. Rodar depois do /setup.
  Use quando o usuário chamar /mapear, quando disser "quero organizar meus processos",
  "quero criar skills", "mapear tarefas", ou "personalizar o ambiente".
---

# /mapear: Mapeamento de Processos

## Contexto

Essa skill é o segundo passo depois do `/setup`. O setup configurou quem o usuário é. Agora vamos entender **o que ele faz no dia a dia** e criar a estrutura certa pra isso.

## Antes de começar

1. Ler `_contexto/empresa.md` pra entender o negócio
2. Ler `_contexto/estrategia.md` pra saber o foco atual
3. Ler `_contexto/integracoes.md` (o que está ligado aqui) e o catálogo de ferramentas do kit (linha "modelos e scripts" do mapa; numa instalação nova, `sistema/templates/integracoes/catalogo.md`) pra saber o que dá pra usar
4. Ler o catálogo de skills externas do kit (`sistema/templates/skills/catalogo.md` numa instalação nova)
5. Listar as pastas que já existem no workspace (pra não criar duplicatas)
6. Listar os modelos de skill do kit (`sistema/templates/skills/` numa instalação nova), pra saber o que já temos pronto

## Fase 1: Descoberta

Começar com uma pergunta aberta:

> "Me conta: quais são as coisas que você faz toda semana (ou todo mês) no seu trabalho que tomam tempo? Pode ser qualquer coisa: criar conteúdo, mandar propostas, fazer relatórios, responder clientes, montar apresentações..."

Deixar o usuário responder livremente. Depois, fazer perguntas de aprofundamento conforme necessário:

- "Esse [processo X] segue sempre o mesmo passo a passo ou muda muito?"
- "O resultado final é um arquivo? Se sim, onde você guarda hoje?"
- "Tem alguma coisa que você faz antes de começar esse processo? Tipo juntar informações, ler algo?"
- "Com que frequência você faz isso?"

O objetivo é montar uma lista clara de processos repetitivos. Pra cada um, entender:
- **O que é** (em uma frase)
- **Frequência** (diário, semanal, por demanda)
- **Se gera um entregável** (arquivo, documento, post) ou é só um processo
- **Se segue um passo a passo consistente** ou varia muito

## Fase 2: Apresentar o mapa

Quando tiver entendido o suficiente (geralmente 3-6 processos), apresentar o mapa:

> "Beleza, identifiquei esses processos no seu dia a dia:
>
> 1. **[nome do processo]** · [frequência] · [gera entregável / é um fluxo]
> 2. **[nome do processo]** · [frequência] · [gera entregável / é um fluxo]
> 3. ...
>
> Qual você quer organizar primeiro?"

Aguardar o usuário escolher. Mapear um por vez.

## Fase 3: Organizar cada processo

Para o processo escolhido, seguir esta lógica:

### 3.1: Verificar se já tem algo pronto

Verificar em duas fontes, nessa ordem:

**1. Modelos de skill do kit** (a pasta de modelos do mapa; `sistema/templates/skills/`): skills editáveis que vão ser instaladas no projeto.

**2. Catálogo de skills externas** (`catalogo.md` na mesma pasta de modelos): skills globais ou nativas que já estão prontas. **Antes de recomendar ou criar, consultar também o catálogo vivo da Ratos** (`curl -s -H "Accept: text/markdown" https://ratosdeia.com.br/skills/`): se existir versão completa do que o usuário precisa, apresentar as duas opções (a completa, que ele pega no site conforme o acesso que tem; ou o modelo simples do kit) e deixar ele decidir. Sem internet ou página fora do ar: seguir só com o catálogo local.

**Se encontrar template compatível:**

> "Tenho um template pronto pra isso: [nome do template].
> Deixa eu te mostrar o que ele faz:"

Mostrar um resumo curto do fluxo do template (não o arquivo inteiro). Depois perguntar:

> "Esse fluxo faz sentido pro seu caso? Quer ajustar alguma coisa?"

Adaptar conforme o feedback antes de instalar.

**Se encontrar skill externa compatível (do catálogo):**

> "Já existe uma skill pronta pra isso: [nome]. Ela [o que faz em uma frase]. Você pode usar ela direto com `/[nome]` sem precisar criar nada. Quer testar?"

Se o usuário quiser adaptar o comportamento, criar uma skill local que complementa ou substitui a externa.

**Se não encontrar nada:**

> "Não tenho nada pronto pra isso, mas consigo criar uma skill do zero com base no que você me contou."

Seguir pra criação manual (3.3).

### 3.2: Decidir a estrutura

Analisar as pastas que já existem no workspace e decidir:

**Se o processo gera entregáveis (arquivos):**
- Verificar se já existe uma pasta onde faz sentido guardar (ex: `conteudo/`, `propostas/`, `clientes/`)
- Se sim, usar a pasta existente. Não criar pasta nova.
- Se não, criar uma pasta nova com nome claro

**Se o processo é só um fluxo (não gera arquivo em lugar fixo):**
- Não criar pasta nova. Só a skill basta.

**Se o processo gera entregáveis E tem passo a passo:**
- Criar pasta (se necessário) + skill que aponta pra essa pasta

Antes de criar qualquer coisa, mostrar o plano:

> "Pra esse processo, vou fazer o seguinte:
>
> - [Criar pasta `conteudo/newsletters/` pra guardar os resultados] (se aplicável)
> - [Instalar a skill `/newsletter` em .claude/skills/newsletter/SKILL.md] (se aplicável)
> - [A skill vai salvar os arquivos em `conteudo/newsletters/`] (se aplicável)
>
> Bora?"

Só criar depois que o usuário confirmar.

### 3.3: Criar a skill personalizada

Antes de criar, ler `_contexto/integracoes.md` e o catálogo de ferramentas do kit, e verificar se alguma ferramenta disponível resolve parte do fluxo que o usuário descreveu. Por exemplo:

- O processo envolve publicar em rede social? → verificar se Post for Me ou Canva MCP ajudam
- Precisa gerar imagem? → verificar Gemini ou DALL-E
- Parte de um vídeo do YouTube? → verificar yt-dlp
- Gera HTML visual? → incorporar Playwright pra renderizar em PNG
- Precisa ler conteúdo de sites? → usar WebFetch ou Jina Reader

Se encontrar ferramenta relevante, incorporar na skill e avisar o usuário:

> "Pra essa skill funcionar completa, você vai precisar configurar [ferramenta]. [Instrução curta de como configurar]. Quer que eu configure agora ou prefere fazer depois?"

A partir daqui o fluxo se divide em dois caminhos, dependendo do que aconteceu na 3.1:

#### Caminho A: Adaptar template existente

Quando a 3.1 encontrou um modelo compatível, criar a skill diretamente a partir dele. Garantir:

1. O frontmatter tem `name` e `description` claros
2. A skill lê o contexto relevante (`_contexto/preferencias.md`; se for visual, o guia de design da marca, citado pelo nome, nunca por caminho fixo: o mapa do `AGENTS.md` resolve)
3. O passo a passo reflete o que o usuário descreveu, não um fluxo genérico. A skill fixa o que tem
   que sair sempre igual (o que entra, onde salva, o que não pode faltar) e deixa a forma pro modelo:
   sem esqueleto de seções nem layout escrito, a não ser que o usuário peça um formato fixo
4. Se gera arquivo, a skill indica onde salvar
5. O tom e formato seguem as preferências do usuário
6. Se usa ferramenta do catálogo, inclui as instruções de uso dentro da skill

#### Caminho B: Criar do zero (delegar pra skill-creator)

Quando a 3.1 não encontrou nem template nem skill externa que sirva, **invocar a skill-creator nativa do Claude Code via Skill tool** ao invés de tentar escrever a skill na mão. A skill-creator é especialista em estruturar skills com os princípios certos (concisão, degrees of freedom, anatomia correta de bundled resources).

Antes de invocar, montar um briefing completo com tudo que você já sabe da entrevista e do contexto do projeto:

- **O processo**: o que o usuário descreveu, em uma frase
- **Frequência e gatilhos**: quando ele faz isso, o que dispara
- **Passo a passo**: o fluxo que ele descreveu, sem inventar etapas
- **Entregável**: se gera arquivo, qual formato e onde salvar
- **Ferramentas relevantes**: o que de `_contexto/integracoes.md` e do catálogo do kit se aplica
- **Contexto do negócio**: pontos de `_contexto/empresa.md` e `_contexto/preferencias.md` que importam (tom de voz, estilo, restrições)
- **Identidade visual**: se for skill que gera output visual, apontar pra "o guia de design da marca (ver mapa do `AGENTS.md`)", nunca caminho fixo. A skill aplica logo, cores e fontes e decide a composição a cada peça; layout fixo só se o usuário pediu que saia sempre igual
- **Onde salvar**: `.claude/skills/nome-da-skill/SKILL.md`

Passar esse briefing pra skill-creator e deixar ela estruturar a skill. Depois que ela retornar, **revisar o resultado** antes de finalizar:

- O frontmatter ficou claro?
- O tom da skill bate com as preferências do usuário?
- A skill lê os arquivos de contexto certos no início?
- Os triggers (palavras que disparam a skill) fazem sentido pro vocabulário do usuário?

Ajustar o que precisar ajustar antes de mostrar pro usuário. Se algo crítico ficou de fora, pedir pra skill-creator complementar ou editar direto.

#### Estrutura final (vale pros dois caminhos)

Salvar em `.claude/skills/nome-da-skill/SKILL.md` na raiz. Se a skill é de **uma pasta de projeto** (só faz sentido lá, ou vai viajar com ela), salvar em `<pasta>/.claude/skills/nome-da-skill/SKILL.md` e acrescentar a linha dela no `AGENTS.md` daquela pasta ("Habilidades desta pasta").

Se a skill precisar de arquivos de apoio (referências, exemplos de output), criar dentro da mesma pasta:

```
.claude/skills/nome-da-skill/
  SKILL.md              ← instruções principais
  referencia.md         ← material de referência (se aplicável)
  template.html         ← só se o usuário quer a peça sempre igual (ex: relatório semanal com formato fixo)
```

Template HTML trava todas as peças daquela skill no mesmo esqueleto. Sem pedido de formato fixo, não criar.

Depois de criar, **sincronizar a ponte pro Codex enxergar a skill nova** (symlink/junction refletem
sozinhos; só cópia precisa re-sincronizar de fato). Rodar o script: é idempotente:

```bash
bash sistema/scripts/sync-ponte.sh        # Mac/Linux, nunca no Windows, mesmo em Git Bash
```
```powershell
powershell -ExecutionPolicy Bypass -File sistema\scripts\sync-ponte.ps1   # Windows, sempre este
```

Depois, confirmar:

> "Pronto, a skill `/[nome]` tá instalada. Você pode rodar ela agora se quiser testar, ou a gente segue pro próximo processo."

## Fase 4: Continuar ou encerrar

Depois de cada processo mapeado, perguntar:

> "Quer mapear o próximo da lista?"

Se sim, voltar pra Fase 3 com o próximo processo.

Se não, anotar os processos que ainda não foram mapeados nas **pendências do `_contexto/agora.md`** (uma linha: "mapear: [processo]").

Mensagem final:

> "[N] processos mapeados, [N] skills criadas.
> Os que ficaram pendentes estão nas pendências do agora.md. Quando quiser continuar, é só rodar /mapear de novo."

## Regras

- Tom direto, conversa natural, sem formalidade
- Uma pergunta por vez durante a entrevista. Não listar 5 perguntas de uma vez
- Sempre verificar o que já existe antes de criar pasta ou skill nova
- Sempre mostrar o plano antes de criar qualquer coisa
- Nunca criar skill que o usuário não confirmou
- Se o usuário descrever um processo vago demais, pedir mais detalhes antes de continuar
- Se o processo do usuário for muito simples (tipo "mando um email pro cliente"), sugerir que talvez não precise de skill: "Isso parece simples o bastante pra fazer direto. Quer criar uma skill mesmo assim ou seguimos pro próximo?"
