---
name: fabrica-movimento
description: Use ao escolher e pôr as peças de motion de um vídeo da Fábrica de Conteúdo com IA (painel, contador, sticker, chip, print, rabisco, carimbo), ou quando o usuário pedir motion, ícone animado, "mostra isso na tela", ou reclamar de tela parada, poluída ou de peça fora do tempo da fala. Diz o que vira peça, quando ela entra e o que a biblioteca já anima sozinha.
---

# Movimento

Entre parênteses, onde a regra mora nesta pasta: o código que cobra ou o arquivo que a
define. *direção* marca a regra de direção de arte que nenhum código cobra: confira no
quadro.

## O que vira peça

- **Vira:** dor, quebra de crença, dado, promessa, instrução de ação. **Nunca vira:**
  transição, conectivo. A ideia que não cabe em nenhuma peça não vira peça: vira fala
  (*direção*).
- Item entra com substantivo e número. Lista de check com adjetivo ("aulas gravadas",
  "atualizações inclusas") afirma que existe produto sem mostrar nenhum (*direção*).
- Toda peça sai da biblioteca. Peça nova entra em `tools/v2/pecas/` e no catálogo, nunca como
  HTML solto na pasta do vídeo (`fabrica-de-conteudo`, "Peças"; `tools/v2/catalogo.json`).

```bash
uv run python tools/v2/v2.py cardapio   # as peças do reel, uma linha cada, com os parâmetros e um exemplo
```

Escolha só do cardápio; ele já deixa de fora a casca de página (contador, chip parado, rótulo,
progresso, título digitado).

- Logo e captura da ferramenta de que o vídeo fala entram: ancoram o que a fala diz. A
  captura é de página pública, sem login (`capturas` no plano; `reel_editorial.py`, topo).
  Logo de marca que não é o assunto fica fora (*direção*).

## No tempo da fala

- A peça entra quando a palavra é dita. O tempo do plano é o tempo da voz, lido no
  transcript, nunca chutado (`reel_editorial.py`, topo: "tempos em segundos do reel = tempos
  da voz").
- O tempo da peça é quando ela **está na tela**, não quando começa a se mexer: o núcleo
  antecipa a entrada sozinho. Não desconte nada (`tools/v2/nucleo/direcao-v2.js`, `D.at`).
- No painel editorial, o gráfico troca a cada substantivo (`e_editorial.html`, parâmetro
  `graficos`).
- Duas peças seguidas se encostam ou deixam pelo menos 0,5 s entre elas. Um vão menor mostra
  o vídeo cru por três quadros e parece erro (`captions_viral.py`, lint).
- A peça traz os próprios sons e eles tocam sozinhos onde ela entra. Som à mão (`sons` no
  plano) é só o que nenhuma peça pediu, e só com nome que existe em `tools/v2/sfx/sfx.json`
  (`reel_editorial.py`, `confere`).

## Uma ênfase por peça

- Um herói, uma palavra marcada, um movimento de câmera por peça. Duas ênfases numa frase é
  nenhuma ênfase (*direção*).
- A mola é curta e só no herói (*direção*; `direcao-v2.js`, `D.pousa`).

## Tela nunca vazia

- O primeiro quadro já tem peça: o título do gancho entra parado no quadro 0. Plano sem nada
  em 0 é recusado (`reel_editorial.py`, `confere`).
- Tela cheia sem rosto se enche de camadas até não sobrar fundo; o render reprova faixa vazia
  grande (`fabrica-composicao`; `reel_editorial.py`, `confere` e `VAZIO_MAX`).

## O que a biblioteca já faz

Não reescreva nada disto no plano nem numa peça nova:

- A peça cai e a sombra dura aparece quando ela toca o chão. O texto sobe palavra a palavra.
  A saída é mais rápida que a entrada (`tools/v2/nucleo/direcao-v2.js`).
- Peça não declara cor, fonte nem medida: usa o núcleo. Todo movimento mora na timeline da
  peça; animação em CSS ou relógio próprio reprova (`tools/v2/nucleo/qa.js`).

```bash
uv run python tools/v2/v2.py qa <peça>   # falha: texto vazando, som sem arquivo, animação fora da timeline
```
