<!-- Teto deste arquivo: 180 linhas. Ele carrega em toda conversa, então cada linha aqui é paga sempre.
     O que cresce vai pras pastas (o mapa da seção 3 diz qual). A /faxina avisa quando estourar. -->
# Uniqee Personalizados · RatosOS

Neste arquivo, "você" é o dono do sistema; as instruções são pro agente.

## 1. O que é este sistema

Workspace principal do Edyfran, dono da Uniqee Personalizados, que ele toca sozinho. A Uniqee faz
presentes personalizados (canecas, camisetas, almofadas, azulejos, squeezes, ecobags, com sublimação,
DTF e impressão 3D) pra quem quer presentear alguém especial, e vende pela loja, pelo Instagram e
pelo WhatsApp. Junto dela, ele vende o PreçoArte, programa de precificação pra sublimadores e artesãos.
Aqui ele cria as artes e o conteúdo do Instagram, atende e orça pelo WhatsApp, registra pedidos que
ficam fora do Brinderoz e desenvolve o PreçoArte. O que diferencia a Uniqee: presente com significado,
em que a emoção pesa mais que a técnica.

**Regras gerais**

- Este kit roda no Claude Code e no Codex. `AGENTS.md` é a fonte (este arquivo); `CLAUDE.md` tem
  uma linha só (`@AGENTS.md`). Skills moram em `.claude/skills/<nome>/SKILL.md`.
- Antes de executar uma tarefa, ver se existe skill pra ela. Se existe, seguir a skill. Se a mesma
  tarefa sem skill já apareceu antes (o diário mostra), perguntar ao terminar se vira skill.
  Tarefa pontual não ganha essa pergunta.
- Skill nova parte de um modelo do kit quando houver (ver mapa). Skill deste negócio fica em
  `.claude/skills/`; skill de uma pasta de projeto fica em `<pasta>/.claude/skills/` e viaja com ela;
  global (`~/.claude/skills/`) é só o que serve em qualquer projeto e não viaja.
- Falhou alguma coisa: falar como gente. O que aconteceu, o que continua seguro, qual o próximo passo.
  Erro cru só se pedirem. Nunca parar em silêncio.
- Pasta que nasce vazia leva um `.gitkeep`.
- Com você, o agente fala como `_contexto/preferencias.md` manda. Com o seu cliente, como a marca
  manda. São duas coisas diferentes, e não se misturam.

## 2. Boot (o que ler em toda conversa)

No início de toda conversa, ler estes três arquivos, e só eles:

1. `_contexto/empresa.md` (quem você é, o que faz, como o negócio funciona)
2. `_contexto/preferencias.md` (como falar com você, o que evitar)
3. `_contexto/agora.md` (onde paramos, pendências: a continuidade entre sessões)

Usar isso naturalmente, sem listar o que leu nem confirmar leitura. Se algum deles ainda tem
`<!-- NOT CONFIGURED -->`, o sistema não passou pelo `/setup`: dizer isso e oferecer rodar.
Todo o resto se lê quando a sessão pedir (seção 3) ou quando uma ação disparar (seção 4).
O `/iniciar` é o ritual completo por cima deste boot: anuncia recados, resume o diário de outra
origem, avisa se o `agora.md` está velho.

## 3. O mapa (pra saber X, leia Y)

| pra saber... | leia |
|---|---|
| o foco do momento, o que pode esperar | `_contexto/estrategia.md` |
| o que o negócio usa e como o agente alcança (MCP, API, CLI, conta) | `_contexto/integracoes.md` |
| que automações estão ligadas (cron, worker, rotina que roda sozinha) | `_contexto/automacoes.md` |
| onde algo está hospedado (site, domínio, servidor, banco, DNS) | `_contexto/infra.md` |
| identidade visual e como a marca fala com o cliente | `_contexto/marca/` (começa por `design-guide.md`) |
| por que algo foi decidido, ou antes de mudar uma decisão | `_memoria/decisoes.md` |
| o que aconteceu num dia, ou pra voltar no tempo | `_memoria/diario/` (mais de 90 dias: `_memoria/arquivo/`) |
| recado deixado por um robô ou por outra pessoa | `_memoria/recados/` |
| de um contato ou fornecedor recorrente (não é cliente, não é time) | `_contexto/pessoas/<nome>.md` |
| de um projeto ou cliente, pra trabalhar nele | a pasta dele: `AGENTS.md` + `contexto.md` + `andamento.md` |
| que modelos e scripts o kit traz (perfis, skills prontas, catálogos, ponte) | `sistema/templates/` e `sistema/scripts/` |

Este mapa é a única fonte de caminho do sistema. **Skill nunca escreve caminho de marca, de script ou
de modelo: ela diz "a marca", "o script da ponte", e o caminho se resolve aqui.** Se você mudou uma
pasta de lugar, atualize a linha correspondente e tudo continua funcionando. Pasta de projeto que
tem `marca/` própria usa a dela; sem isso, vale a da raiz.

## 4. Gatilhos de ação (o que ler antes de fazer)

- **Antes de escrever texto ou peça que sai pra fora** (email, proposta, post, slide, página, anúncio,
  relatório): ler a marca (a do projeto se existir, senão a da raiz). Ela dá logo, cores, fontes e tom;
  layout e composição se decidem a cada peça, pelo conteúdo, a não ser que a marca tenha design system.
  Antes de entregar, conferir logo, cores, fontes e tom.
- **Antes de salvar qualquer arquivo:** a tabela de destinos (seção 5).
- **Perguntaram "por quê", ou vai mudar algo já decidido:** `_memoria/decisoes.md`.
- **Precisa voltar no tempo** ("o que fizemos semana passada", "quando falamos disso"): `_memoria/diario/`.
- **Vai dizer "não consigo" ou "não tenho acesso":** `_contexto/integracoes.md` primeiro. Muita coisa
  que parece impossível só está desligada, e a tabela diz o que dá pra ligar.
- **Vai trabalhar numa pasta de projeto:** ler o `AGENTS.md`, o `contexto.md` e o `andamento.md` dela.
  Abrir a raiz não carrega a subpasta sozinho: é preciso ir buscar.
- **Chegou material bruto** (transcrição, PDF, email exportado): vai pra pasta do projeto certo, e o
  essencial é destilado no `contexto.md` dele, **com a data e o caminho da fonte** ("reunião
  12/08 → o arquivo: o que fechou"). Guarda-se o mapa, não uma cópia. Nada de gaveta de entrada.

## 5. Tabela de destinos (aconteceu X, escreve em Y)

Toda vez que for salvar alguma coisa, é aqui que se consulta. Quem escreve é o `/atualizar`, no fim
da sessão, numa passada só. No meio da sessão o agente não sai salvando por conta: anota e segue.
Pedido explícito ("salva isso") é exceção, e passa pela tabela do mesmo jeito.

| aconteceu na sessão | escreve em |
|---|---|
| fato novo sobre o negócio (cliente, serviço, equipe, preço) | `_contexto/empresa.md` |
| mudança de rumo, foco ou meta | `_contexto/estrategia.md` |
| correção ou preferência de trabalho ("não faça mais isso", "prefiro assim") | `_contexto/preferencias.md` |
| ferramenta nova, acesso novo, "não alcanço isso" | `_contexto/integracoes.md` |
| automação ligada, desligada ou mudada | `_contexto/automacoes.md` (nasce no primeiro registro: rotina, o que faz, onde roda, quando, origem que assina, como saber se quebrou) |
| onde algo passou a estar hospedado | `_contexto/infra.md` |
| onde paramos, pendências | `_contexto/agora.md` |
| o que foi feito hoje | `_memoria/diario/` (o arquivo da própria origem, acrescenta no fim) |
| decisão com motivo | `_memoria/decisoes.md` (acrescenta; nome do projeto na linha, se for de projeto) |
| robô quer propor ou reportar | `_memoria/recados/` (um arquivo por recado) |
| identidade visual, jeito de falar com o cliente | `_contexto/marca/` |
| trabalho de projeto ou cliente | a pasta do projeto |
| chegou transcrição, material de reunião, documento | a pasta do projeto; destilar o essencial no `contexto.md` dele, com data e caminho da fonte |
| pessoa ou empresa recorrente que não é cliente nem time | `_contexto/pessoas/<nome>.md` (a pasta nasce no primeiro arquivo) |
| coisa trivial (pergunta solta, teste, conversa sem ação) | **não salva.** Poluir o sistema é pior que perder |
| não coube em nada acima | **pergunta.** Nunca inventar gaveta nem destino em silêncio |

Formatos que não mudam: diário é `AAAA-MM-DD.md` (o dono) ou `AAAA-MM-DD-<origem>.md` (qualquer outra
origem), sempre acrescentando embaixo, nunca reescrevendo. Decisão é uma entrada nova, datada e assinada;
quando muda decisão velha, diz `substitui: <data>` em vez de editar a antiga. Toda entrada durável leva
data absoluta (nunca "semana passada"). Arquivar em vez de apagar.

## 6. Quando quem escreve não é o dono

Rotina, cron, agente autônomo, subagente, ou outra pessoa ou computador escrevendo aqui: antes de
escrever qualquer coisa, ler `sistema/contrato-robo.md`. Em uma linha: escreve no próprio diário e em
recados, e não edita `_contexto/` nem as decisões. Toda rotina ligada tem linha em `_contexto/automacoes.md`.

## 7. Regra de recall

Pergunta sobre o passado (o que foi feito, quando, por quê, o que ficou combinado): buscar no diário e
nas decisões **antes** de responder. Nunca responder de memória de sessão nem completar com suposição.
Não achou: dizer que não achou.

## 8. Fim de sessão (e a oferta ativa)

Sessão que rendeu trabalho termina com `/atualizar`. É ele que escreve o diário, o `agora.md`, as
decisões e o `_contexto/`, e fecha dizendo o que escreveu onde. Isso não depende de você lembrar:
**o agente oferece**. Sinal de encerramento na conversa ("era isso", "valeu", "até amanhã") ou
tarefa que mudou o contexto (cliente novo, ferramenta ligada, decisão tomada, correção do jeito de
trabalhar) → o agente pergunta, em uma linha, se roda o `/atualizar` agora. Correção dita no meio
("não faça mais isso", "prefiro assim") vira "anotado, salvo no fim", e a sessão nunca morre sem essa
oferta. Não oferecer em sessão trivial.

| comando | o que faz | o que não faz |
|---|---|---|
| `/iniciar` | lê o sistema e devolve onde você parou | não escreve nada |
| `/atualizar` | decide onde cada coisa mora e escreve | não manda nada pra fora |
| `/syncar` | manda pro GitHub e diz o que subiu | não decide nada |

Este sistema está no GitHub: depois do `/atualizar`, oferecer o `/syncar` na mesma linha.

## 9. Mapa de pastas

<!-- O /setup e o /novo-projeto mantêm esta lista: uma linha por pasta, com o que vai nela. -->

- `_contexto/` · o que o sistema sabe do negócio. Não apagar
- `_memoria/` · o que aconteceu e por quê: `diario/`, `decisoes.md`, `recados/`
- `sistema/` · o motor do kit (scripts e modelos). Você não precisa abrir
- `.claude/` · as habilidades (skills) deste sistema
- `.ratosos` · a versão do kit (uma linha). Não apague: é como a atualização sabe de onde você parte
<!-- pastas de trabalho abaixo, criadas pelo /setup conforme o negócio -->
- `conteudo/` · o que vai pro Instagram: `roteiros/`, `artes/`, `legendas/`
- `produtos/` · fichas de precificação e catálogo das peças da Uniqee
- `pedidos/` · pedidos que não entram no Brinderoz
- `atendimento/` · modelos de resposta pro WhatsApp e orçamentos
- `projetos/` · projetos internos, um por pasta (o PreçoArte entra aqui)
- `estudos/` · pesquisas de tendência, concorrência e referências
- `publicacoes/` · o que já foi postado, pra consultar
