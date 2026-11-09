---
name: novo-projeto
description: >
  Cria a pasta de um projeto ou cliente com contexto próprio (AGENTS.md, contexto.md,
  andamento.md) e registra no mapa de pastas da raiz. Ou liga uma pasta que já existe ao
  sistema ("/novo-projeto link <pasta>"). Antes de criar, confere se vale pasta mesmo.
  Use quando o usuário chamar /novo-projeto, disser "novo cliente", "novo projeto", "cria a
  pasta do X", "vou começar um projeto", ou quiser organizar um trabalho novo em pasta separada.
---

# /novo-projeto · pasta de projeto com contexto

Toda pasta nasce **simples**: `AGENTS.md` curto + `CLAUDE.md` ponteiro + `contexto.md` +
`andamento.md` + o trabalho. Ninguém escolhe "nível" na criação. Quando a pasta precisar sair
daqui (cliente, sócio, parceiro), o `/compartilhar` completa ela pra viajar.

## Passo 1 · vale uma pasta?

Antes de criar, três perguntas, respondidas por você a partir do que o usuário contou (só
perguntar o que não dá pra deduzir):

1. Vai ter mais de um arquivo?
2. Vai durar mais que uma sessão?
3. Alguém (você incluso, daqui a um mês) precisa achar isso sem lembrar onde está?

Menos de dois "sim": não é pasta, é um arquivo dentro de uma pasta que já existe. Dizer isso e
propor o lugar: *"isso cabe num arquivo em `conteudo/`, não precisa de pasta. Quer que eu crie
só o arquivo?"*.

## Passo 2 · entender o projeto

Uma pergunta por vez, pulando o que já foi respondido:

1. "Qual é o nome do projeto? (cliente, produto ou site)"
2. "Que tipo é?" cliente (entrega pra alguém) · produto próprio (site, app, curso, loja) ·
   conteúdo (canal, série, newsletter) · interno (processo, ferramenta)
3. "Me explica em poucas palavras o que é e o que precisa ser entregue."
4. "Tem prazo, orçamento ou ferramenta específica?"
5. "Esse projeto tem identidade visual ou tom de voz próprios, diferentes da sua marca?" (cliente
   costuma ter; produto próprio costuma herdar)

## Passo 3 · onde fica

Sugerir pelo tipo e pelo mapa de pastas do `AGENTS.md` da raiz (respeitar a estrutura que o
`/setup` criou): cliente → `clientes/<nome>/` · produto ou interno → `projetos/<nome>/` ·
conteúdo → `conteudo/<nome>/`. Nome em minúsculas, sem espaço nem acento.

> "Sugiro `clientes/acme/`. Faz sentido ou prefere outro lugar?"

## Passo 4 · criar

`mkdir -p` na pasta e quatro arquivos. Nada de subpasta que o usuário não pediu; nada nasce vazio.

**`AGENTS.md`** (curto, cresce com o uso, menos de 30 linhas):

```markdown
# [Nome do projeto]

Quem abre esta pasta de dentro do sistema: as regras da raiz continuam valendo. Os gatilhos
abaixo dizem o que ler antes de agir.

## O que é
[1-2 frases] · **Tipo:** [cliente / produto / conteúdo / interno]

## Antes de agir
- Pra saber do projeto: `contexto.md` (o que ele é, quem é quem, o que foi combinado) e
  `andamento.md` (onde está, pendências).
- Antes de escrever texto ou peça que sai pra fora: a marca em `../../_contexto/marca/`
  [ou, se tem própria: `marca/` desta pasta].
- Antes de salvar arquivo: a tabela de destinos em `../../AGENTS.md`. Trabalho deste projeto
  fica aqui; fato sobre o negócio e decisão vão pros lugares da raiz (o `/atualizar` cuida).
- Habilidades desta pasta, se houver: `.claude/skills/<nome>/SKILL.md` (ler antes de usar quando
  a sessão foi aberta na raiz).

## Regras deste projeto
- (cresce com o uso)
```

`CLAUDE.md`: exatamente uma linha, `@AGENTS.md`.

**`contexto.md`**: escopo, o que precisa ser entregue, prazo/orçamento/ferramentas, contato (se
cliente), o que foi combinado. É onde material bruto (transcrição, PDF, email) é destilado depois.

**`andamento.md`**:

```markdown
# Andamento · [nome]

## Onde está (AAAA-MM-DD)
Pasta criada. Próximo passo: [o primeiro passo que o usuário citou].

## Pendências
- [ ] [entrega 1]

## Feito
```

Se tem marca própria (pergunta 5): criar `marca/design-guide.md` **dentro da pasta** (mesmo modelo do
guia de design da raiz, em branco; o mapa diz onde ele mora) e o gatilho do `AGENTS.md` aponta pra ela.

## Passo 5 · registrar na raiz

Acrescentar uma linha no **mapa de pastas** (seção 9) do `AGENTS.md` da raiz, embaixo da pasta-mãe
ou no fim: ``- `clientes/acme/` · [uma frase do que é]``. Só isso: cliente novo em `empresa.md` e
a decisão de abrir o projeto são coisa do `/atualizar`, no fim da sessão.

## Passo 6 · confirmar

> "Criado: `clientes/acme/` com AGENTS.md, contexto.md e andamento.md, e a linha no mapa da raiz.
> Pra trabalhar nele, é só falar: eu leio a pasta quando tocar nela."

## Modo link · pasta que já existe

`/novo-projeto link <pasta>` (ou o usuário dizendo "essa pasta já existe, liga ela"): não criar
nada por cima. Ler o que tem, gerar só o que falta (`AGENTS.md`, `CLAUDE.md`, `contexto.md`,
`andamento.md`), preencher o `contexto.md` com o que dá pra deduzir dos arquivos, mostrar antes de
salvar, e registrar no mapa da raiz. Nunca mover nem renomear o que está dentro.

## Regras

- Tom direto, sem cerimônia.
- Nunca mover pasta existente sem perguntar.
- Não criar `.claude/skills/` vazia: a pasta de skills nasce com a primeira skill.
- Caminho de marca, scripts e modelos vem do mapa da raiz, não de memória.
