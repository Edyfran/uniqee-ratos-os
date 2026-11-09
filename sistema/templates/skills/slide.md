---
name: slide
description: >
  Cria um slide ou card visual em HTML pra apresentação, deck ou post, com a identidade da marca
  do usuário.
  Use quando o usuário pedir "faz um slide", "cria um card", "quero um visual pra apresentação",
  "frame pra deck", ou pedir um slide sobre algum tema específico.
---

# /slide · slide ou card

## O que ler antes

A marca (a linha "marca" do mapa do `AGENTS.md`; se o projeto tem `marca/` própria, vale a dela):
logo, cores e fontes. Se o texto vai pra fora, o jeito de falar com o cliente também.

## 1. Entender o pedido

O tema e o formato. Se o formato não está claro, perguntar: card 1:1 (1080×1080), slide 16:9
(1920×1080) ou story 9:16 (1080×1920).

## 2. Fazer

Um HTML único, no tamanho exato do formato, que funcione como print: tudo dentro da área, sem
rolagem, legível de longe. CSS no próprio arquivo; fonte externa, só do Google Fonts.

A composição você decide pelo conteúdo: um número, uma frase, uma comparação e um fluxo pedem
desenhos diferentes. A marca entra com cores, fontes e, quando fizer sentido, o logo (a versão
certa pro fundo). Sem guia de design preenchido: visual limpo, sem inventar uma marca.

## 3. Salvar e mostrar

Na pasta de conteúdo do mapa de pastas do `AGENTS.md` (ou na do projeto), com o tema e a data no
nome. Se tem Playwright, renderizar em PNG e mostrar.

## Regras

- Vários slides: fazer o primeiro, mostrar, e seguir com o ok.
