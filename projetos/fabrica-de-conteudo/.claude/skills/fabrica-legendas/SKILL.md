---
name: fabrica-legendas
description: Use ao pôr legenda num vídeo da Fábrica de Conteúdo com IA, ou quando o usuário pedir legenda, "duas letras", palavra em destaque ou palavra atrás da pessoa, ou reclamar que a legenda cobre a boca, quebra a frase no meio, some no celular ou cai na legenda do Instagram. Diz qual legenda cada estilo usa e o critério que a fábrica cobra.
---

# Legendas

Entre parênteses, onde a regra mora nesta pasta: o código que cobra ou o arquivo que a
define. *direção* marca a regra de direção de arte que nenhum código cobra: confira no
quadro.

## Qual legenda

| Estilo | Legenda | Quem desenha |
|---|---|---|
| `reel-editorial` | a fala em duas letras, na voz editorial | a peça `e_editorial` (`r.fala`, `r.vozes` no plano) |
| `reel-camera`, `reel-avatar`, `criativo` | a legenda viral: cadência, ênfase, palavra-herói | `cards_da_fala.py` faz os cards, `captions_viral.py` queima |

No reel editorial a legenda não é recurso do estilo: quem escreve a fala na tela é a peça
(`estilo.py`, comentário do `reel-editorial`). Não ligue as duas no mesmo vídeo.

## Duas letras (reel editorial)

- **Fala:** sans (Inter) em negrito, minúscula, apertada. Corte seco, uma ou duas palavras
  por cartão, que acumula e recentra (`tools/v2/nucleo/editorial.css`; `e_editorial.html`,
  parâmetro `fala`).
- **Rótulo:** serifa itálica (Instrument Serif) em caixa alta. Narra o que está no painel
  (`editorial.css`).
- **Bloco:** duas linhas sobrepostas, sans e serifa, com degradê dentro da letra. A
  **chamada** usa a mesma sobreposição, em cromo, parada até o fim (`editorial.css`).
- Nada de borda, caixa ou pílula na letra. Sombra só difusa, e só sobre o rosto
  (`editorial.css`).
- Dentro da janela de um rótulo, bloco, título ou chamada, a fala cala (`e_editorial.html`,
  parâmetro `vozes`).

## A palavra marcada

- **Uma ênfase por frase.** Duas ênfases numa frase é nenhuma ênfase (*direção*).
- Na legenda viral, no máximo três palavras `punch` no vídeo inteiro: "quatro punches é zero
  punch" (`captions_viral.py`, lint).
- A cor da palavra acesa é do estilo, não do plano: `ac`, o azul do bloco, ou `mk`, o amarelo
  do marcador, em `desenho.destaque` (`estilo.py`). Nas peças, `*palavra` vai para o amarelo
  (`g_gancho`, `k_frase` em `tools/v2/catalogo.json`).
- **O que já virou peça não vira legenda também.** Legenda que repete embaixo o que a peça
  diz em cima é cobertura, não reforço. Quem decide é a sobreposição: uma legenda que começa
  dois quadros antes da peça e roda debaixo dela está dentro da peça (*direção*).
- **Palavra atrás da pessoa** só em estilo com `desenho.atras` (hoje, o `reel-camera`); nos
  outros a fábrica recusa o card (`fabrica.py`, `_direcao`). O card leva `"atras": true`, fica
  no centro e guarda 5 s do herói anterior (`captions_viral.py`, lint).

## Zona segura do Instagram

- No reel editorial, letra nenhuma desce abaixo do y 1450 (num quadro de 1920): ali fica a
  legenda do Instagram. O `confere` recusa a peça ou imagem que desce até lá, e a fala sobe
  para 1400 sozinha (`estilo.py`, `desenho.legenda_ig`; `reel_editorial.py`, `confere` e `CSS`).
- Na legenda viral, o y do card foge do movimento da cena: o texto não senta na boca
  (`captions_viral.py`, topo).

## Quebra de linha

- A quebra cai na pontuação e na pausa da fala (0,24 s), nunca no meio de um sintagma. O
  card não termina em palavra átona ("e", "do", "que", "é"): ela passa para o seguinte
  (`cards_da_fala.py`, topo e `ATONAS`).
- Até quatro palavras cheias por card, e uns 22 caracteres por linha. Card com mais de 40
  caracteres quebra em três linhas, e o lint avisa (`cards_da_fala.py`; `captions_viral.py`,
  lint).
- Na voz editorial, `palavra|` força a quebra depois da palavra (`e_editorial.html`).
- O card não atravessa uma troca de cena ou de painel: nasceria num tratamento e morreria
  noutro (`captions_viral.py`, lint).

## Tempo de leitura

- Card de frase fica pelo menos 0,35 s; card de uma palavra, 0,14 s. Entrar não é estar
  legível: o que conta é o tempo com a frase inteira parada na tela (`captions_viral.py`,
  lint; `cards_da_fala.py`, `piso_do_card`).
- A legenda sai do áudio **final**, depois dos cortes. Mudou o corte, a legenda muda junto
  (`fabrica.py`, `_fala_no_corte`).
- O transcript vem do `transcribe.py <vídeo> --model large-v3 --language pt`. Nome que o
  Whisper parte em dois se junta no plano: `junta` no reel editorial, `funde` no criativo
  (`reel_editorial.py` e `criativo.py`, topo).

## Legível no celular

- Quase todo mundo assiste no celular. Nada que carregue informação fica abaixo de 58 px num
  painel de 1440, ou de 44 px numa tela cheia de 1080 (`tools/v2/nucleo/direcao-v2.css`,
  `--piso`; *direção*).
- Confira baixando o quadro para 400 px de largura, não olhando o PNG inteiro (*direção*).

## Antes de renderizar

```bash
uv run python tools/video-use/helpers/captions_viral.py --lint <cards.json>   # legenda viral, em 1 s
uv run python tools/video-use/helpers/fabrica.py <plano.json> --seco          # o reel editorial passa pelo confere
```
