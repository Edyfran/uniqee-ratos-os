---
name: fabrica-ritmo
description: Use ao decidir o corte e o andamento de um vídeo da Fábrica de Conteúdo com IA — o silêncio, o erro e a repetição que saem, quando trocar de imagem, zoom e transição, o gancho do primeiro quadro e a chamada do fim. Também quando o usuário disser que o vídeo está lento, picotado, que uma palavra foi comida no corte, ou que o começo não prende.
---

# Ritmo

Entre parênteses, onde a regra mora nesta pasta: o código que cobra ou o arquivo que a
define. *direção* marca a regra de direção de arte que nenhum código cobra: confira no
quadro.

## Corte de silêncio

- Cada estilo tem a sua afinação, e ela é dado, não gosto (`estilo.py`, eixo `corte`;
  `clean_edl.py`, `AFINACOES`):
  - `silencio`, no reel do celular: corta pela energia do áudio; um vão de 0,04 s já vira
    emenda, com 0,06 s de folga de cada lado;
  - `tight`, na narração e na voz que vai para o avatar: zero silêncio, `sil_cut` de 0,04 s.
- Filler ("né", "sabe", "assim") só sai quando o corte cai numa pausa de verdade; senão a
  emenda fica audível. Gaguejada e recomeço saem; repetição de três ou mais, que é ênfase,
  fica (`clean_edl.py`, topo).
- A afinação `silencio` não lê o texto. Erro, retake e frase repetida do vídeo do celular
  saem como `drops` que você acha no transcript: são do vídeo, não da regra (`clean_edl.py`,
  topo; `fabrica-de-conteudo`, "Reel do celular").
- A borda do corte nunca corta voz no ar: estica até o silêncio medido (`clean_edl.py`,
  `cauda_max`).
- O Whisper escreve a frase como devia ser: apaga o falso começo e completa a palavra
  cortada. Na dúvida, ouça o trecho antes de cortar à mão. O `ouvido.py` escuta dos dois
  lados do corte (opcional, cobra centavos no OpenRouter) (`ouvido.py`, topo).
- A voz que vai para a HeyGen não tem pausa acima de 0,6 s, e o reel que termina no rosto
  não deixa cauda muda maior que isso (`pre_voo.py`, `PAUSA_MAX`; `reel_editorial.py`,
  `confere`).

## Cortes e zoom

- No reel editorial, o rosto alterna entre o cartão e o quadro cheio, em corte seco; o rosto
  cheio aceita zoom (`e_editorial.html`, parâmetro `cenas`).
- Um movimento de câmera por peça (*direção*).
- Na legenda viral, o plano de cards aceita `camera`: trechos com `zoom: [de, até]` e o
  andamento em `ease`. `sine` entra e sai macio; `solta` desacelera na chegada; `dura`
  acelera na saída; `reta` só quando o zoom cobre um corte (`captions_viral.py`,
  `camera_cenas`).
- A captura em tela cheia leva zoom lento e grifo (*direção*).
- Transição é a peça `x_corte`: os blocos atravessam o quadro e o corte do vídeo cai no
  único instante coberto (`tools/v2/catalogo.json`).
- No criativo, imagem nova a cada 2,5 a 3 s, trocando de registro, de escala e de lugar. É a
  fala que corta: cada cena dura o trecho que cobre. Trecho de fala maior que uns 5 s pede
  duas cenas; acima de 1,25x a câmera lenta aparece (`docs/linguagem-do-criativo.md`, no módulo Cenas de Cinema;
  `criativo.py`, topo). Com `"rampa": true` no trecho, só a janela da cena desacelera.
- No criativo, o corte entre cenas é seco, e o trecho pede o que muda isso: `"emenda":
  "chicote"` ou `"clarao"` no corte que entra nele, `"crava": "<palavra>"` para o zoom brusco
  que fica, e `"intensidade"` (contida, média, ousada) para o quanto (`criativo.py`, topo;
  `fabrica-cenas`, do módulo Cenas de Cinema com IA, "O que a edição faz").

## Gancho no primeiro quadro

- O título do gancho está parado no quadro 0: é a capa que o Instagram mostra. Plano sem
  nada em 0 é recusado (`reel_editorial.py`, `confere`). A peça é o `g_gancho`, que bate no
  primeiro quadro (`tools/v2/catalogo.json`).
- **Vídeo de 8 s ou mais termina com chamada** (`g_comenta`, nos últimos segundos): sem ela o espectador não sabe o próximo
  passo. Se a fala não traz a palavra e a promessa, pergunte ao aluno numa frase; não invente. O aviso `chamada-final` cobra.
- O começo é gancho visual. A chamada ("comenta PALAVRA") entra só no último trecho; antes
  disso é recusada (`reel_editorial.py`, `confere`).
- No criativo: choque cômico de 0 a 1,5 s, e prova literal (a tela real do produto, com o
  verbo dito na voz) até os 5 s. Nada de logo ou apresentação no começo, e o segredo não sai
  na primeira frase (`docs/linguagem-do-criativo.md`, no módulo Cenas de Cinema).
- Cada trecho abre uma pergunta que o seguinte responde em parte, até o fecho. Quatro
  tarefas em lista não abrem pergunta nenhuma (`docs/linguagem-do-criativo.md`, no módulo Cenas de Cinema).

## Tempo de leitura

- A legenda fica na tela o tempo de ler a frase inteira parada; os números estão em
  `fabrica-legendas`.

## Antes de renderizar

```bash
uv run python tools/video-use/helpers/fabrica.py <plano.json> --seco
```

O `--seco` mostra a cadeia com o corte e cobra as regras do gancho e da chamada.
