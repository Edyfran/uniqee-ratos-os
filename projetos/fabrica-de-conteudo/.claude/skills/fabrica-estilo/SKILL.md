---
name: fabrica-estilo
description: Use ao decidir a cara de um vídeo da Fábrica de Conteúdo com IA — tema claro ou tinta, cor, letra, trilha, capa, versão do YouTube e onde o final é entregue —, ou quando o usuário pedir outro visual, outra música, a capa, a versão do YouTube ou um tipo de vídeo novo. A cara mora no estilo e no núcleo da biblioteca, não no plano.
---

# Estilo

Entre parênteses, onde a regra mora nesta pasta: o código que cobra ou o arquivo que a
define.

O **estilo** é o conjunto de escolhas que vale para todo vídeo daquele tipo: corte, voz,
imagem, desenho, trilha, entrega. O **plano** só ajusta um vídeo. Para ver um estilo inteiro:

```bash
uv run python tools/video-use/helpers/estilo.py reel-editorial
```

## O tema: claro ou tinta

- O chão é `claro` (papel branco pontilhado) ou `tinta` (escuro, com a sombra dura em
  amarelo). Quem escolhe é o estilo, em `desenho.tema`, e a peça sai no tema que ele mandar
  (`estilo.py`; `tools/v2/nucleo/direcao-v2.css`, `html.tinta`). No reel editorial, cada
  cena do painel diz `claro` ou `tinta` (`e_editorial.html`, parâmetro `cenas`).
- O azul `#0640fb` é o bloco: o que carrega a informação. O amarelo `#F2C744` é o marcador:
  a palavra grifada, a etiqueta, o foco que anda. Verde e vermelho só como sinal (verde
  confirma, vermelho marca custo ou perda), nunca enfeite (`direcao-v2.css`, topo).
- Borda grossa e sombra dura, sem blur. Letra Space Grotesk, e IBM Plex Mono no código
  (`direcao-v2.css`).
- A voz editorial é a exceção declarada, só na peça `e_editorial`: Inter e Instrument Serif,
  nada de borda na letra, sombra difusa só sobre o rosto (`tools/v2/nucleo/editorial.css`).
- **A marca do usuário** é o terceiro tema: `marca`. Com a pasta `marca/` na raiz, os
  estilos dela (`marca/estilos.json`) pedem `desenho.tema` = `marca`, e toda peça carrega
  `marca/tema.css` por cima do núcleo: as cores e a letra dele no lugar das daqui, inclusive
  na voz editorial e na capa. A letra da legenda viral é `desenho.fonte`, o caminho do
  arquivo a partir da raiz (`marca/fontes/x.ttf`). Para mudar a cara de um cliente, mexa na
  pasta `marca/`, nunca no núcleo.
- Peça não redeclara cor, fonte nem medida. Se faltar um token, ele entra no núcleo; o
  `v2.py qa` avisa cor ou fonte fora dele (`direcao-v2.css`, topo; `tools/v2/nucleo/qa.js`).
- Sem selo "feito com IA" na tela: o aviso vai na legenda do post e no rótulo da rede. O
  plano com selo é recusado (`reel_editorial.py`, `confere`).

## A marca feita aqui

Quando o usuário pede para adaptar a fábrica à marca dele (o pedido do
`docs/guia-de-estilos.md`: um estilo, as cores, a letra), a pasta `marca/` nasce do molde,
nesta ordem:

1. Leia no guia o estilo que ele pediu. O tema daquele estilo é
   `docs/guia-de-estilos/<estilo>.css`. Já existe `marca/`? Guarde a velha antes:
   `mv marca "marca-$(date +%F)"`.
2. `cp -R tools/marca/molde marca` e `cp docs/guia-de-estilos/<estilo>.css marca/tema.css`.
   Apague `marca/ids.env` e `marca/INSTALAR-MARCA.md`: a voz e o avatar dele ficam no
   `.env.local`, e o roteiro de instalação é do pacote de marca que a gente monta.
3. As quatro cores no `tema.css`, pelo papel, não pela ordem em que ele mandou: `--pp` o
   chão, `--ink` a letra e a borda, `--ac` o bloco, `--mk` o marcador (a tabela do guia,
   "As quatro cores"). O bloco leva letra branca e o marcador leva a letra `--ink`: se uma
   cor dele não dá leitura, diga qual e proponha o tom mais perto que dá, antes de seguir.
   Nos estilos de chão escuro (tech, luxo, cyberpunk, pixel, vaporwave, lousa), `--pp` é a
   cor escura e `--ink` a clara; o cartão (`--sur`) e a letra que senta no marcador
   (`--ink9`) saem do chão sozinhos, e o marcador tem que ser claro.
4. As letras são os `url(fontes/...)` do topo do `tema.css`: copie cada arquivo de
   `tools/video-use/assets/fontes/` pra `marca/fontes/`, com o `<Família>-OFL.txt` ao lado
   (o `LICENCAS.md` da pasta diz qual licença vai com qual arquivo). Pediu outra letra?
   Troque a face `'Marca'` (títulos) ou `'MarcaApoio'` (apoio) no `tema.css`, procurando
   antes em `tools/video-use/assets/fontes/`. Fora dela, só fonte livre do Google Fonts, do
   repositório deles, pasta `ofl/<nome>`, com o `OFL.txt` da mesma pasta. O `font-weight`
   do `@font-face` prende a letra num peso (o editorial e o luxo saem leves assim): copie o
   do tema, ou o `peso` que veio do onboarding.
5. `estilos.json`: `TROQUE-SLUG` vira o slug dele (minúsculo, sem espaço) e `TROQUE.ttf` o
   arquivo da face `'Marca'`. Sem `marca/placa.png`, apague a linha `imagem` do `-reel`: a
   placa vem no plano de cada vídeo.
6. `MARCA.md` e `PEDIDOS.md` com o que ele contou. O que faltar (o que vende, pra quem, o
   tom), pergunte numa mensagem só. Nada inventado: campo que ele não respondeu sai do
   arquivo.
7. Confira e mostre: `uv run python marca/instala.py --amostra` (sem a chave da ElevenLabs
   ou sem `VOZ_ID` no `.env.local` ainda: `--sem-voz --amostra`). Abra
   `marca/_confere/amostra.jpg` para ele. Um vídeo curto da marca, sem custo:

```bash
uv run python tools/v2/v2.py render o_pacote "hd=O seu conteúdo, <b>com a sua cara</b>." "it=Roteiro|pronto pra gravar@0.3;Reel editado|corte e legenda@0.6;Capa|nas suas cores@0.9" "fecho=Feito pela sua fábrica" t_fecho=1.2 dur=4 --tema marca --opaco --out marca/_confere/amostra.mp4
```

Os estilos dele aparecem no `estilo.py` junto com os do kit, e todo vídeo pedido num deles
sai com a cara nova. Para mudar depois, só a pasta `marca/` muda. Mudou o `tema.css`, rode
`uv run python tools/v2/v2.py biblioteca`: o `biblioteca.html` da raiz não se atualiza sozinho.

## Trilha até o fim

- A trilha é a do usuário (a da ElevenLabs Music, ou outra com licença) em `trilha.faixa`.
  Sem a dele, entra uma das três CC0 de `exemplos/trilhas/`, e `"nenhuma"` quando ele põe a
  música pelo app do Instagram, que sai só com voz e efeitos (`fabrica-de-conteudo`, regra 6).
  Reel editorial sem `trilha.faixa` é recusado (`reel_editorial.py`, `confere`).
- Dois jeitos, e quem escolhe é o estilo (`estilo.py`, `RECURSOS`, recurso `trilha`):
  - **cama**: a trilha sob a voz o vídeo inteiro, e a voz abaixa a música no ataque de cada
    frase (reel editorial, reel com avatar, criativo) (`mixa.py`, topo);
  - **fecho**: a trilha no piso sob a fala e, com um vídeo de fecho (`trilha.outro`), subindo
    nele. Nenhum estilo do pacote usa; o plano pode pedir em `adaptadores` (`fabrica.py`,
    `trilha_cmd`).
- A trilha mais curta que o vídeo dá a volta, e o áudio vai até o fim da imagem: o fade fecha
  antes dela, nunca corta seco (`mixa.py`, topo; `fabrica.py`, `trilha_cmd`).
- Trilha com final composto (o "ta-da" depois da última palavra) pede `fade_fim` curto: o
  longo abafa justo o final. O reel editorial usa 0,6 s, o criativo 0,3 s, e o criativo do
  feed sai mais devagar, 1,2 s (`mixa.py`, topo; `estilo.py`).
- Para tocar um trecho da faixa em cada parte do vídeo: `trilha.pedacos` (`reel_editorial.py`,
  topo).
- O reel do celular não leva trilha (`estilo.py`, `reel-camera`), a não ser que o usuário mande uma
  referência com música: aí o plano liga o recurso (`fabrica-referencia`).

## Capa

- No reel editorial, com o bloco `capa` no plano: a foto da pessoa do peito para cima (o
  fundo sai sozinho) ou um quadro do webm do avatar (`"foto": ["avatar/rosto.webm", 5.0]`), o título em duas linhas (`"linha 1|linha 2"`) com o `destaque` na
  faixa, o `topo` (o nome da ferramenta), o `logo` e dois ícones nos `lados`: `mic`, `onda`,
  `claquete`, `filme`, `robo`, `rec` ou `cel` (`capa.py`, topo; peça `g_capa_nick`).
- Sai em `videos/topo/<slug>/capa-nick.jpg`, 1080×1920, ao lado do final. Não cobra
  (`fabrica.py`, `_entregas`).
- **A capa é um processo à parte, a última coisa**: só com o vídeo aprovado e pronto pra postar, e
  depois de perguntar numa frase se o aluno tem ideia de frase ou de foto (senão, proponha uma). Um
  comando: escreva o bloco num JSON ao lado da foto (`videos/<slug>/capa.json`; para uma foto tirada
  do próprio vídeo, `"foto": ["<o vídeo>", <segundo>]`) e rode (`capa.py`, topo, descreve o bloco):

```bash
uv run python tools/video-use/helpers/capa.py videos/<slug>/capa.json videos/<slug>/capa.jpg
```

  Exemplo de bloco: `{"foto": "eu.jpg", "titulo": "70 cenas|nenhuma filmada", "destaque": "nenhuma filmada", "topo": "Higgsfield", "lados": "robo,claquete"}`.
  Abra o JPEG uma vez só, pra mostrar ao aluno. Não leia o `capa.py` nem monte a peça à mão.

## Versão do YouTube

- No YouTube não há automação de DM, então pedir a palavra-chave fica sem resposta. Com o
  bloco `youtube` no plano (`fala`, `chamada`, `tema`), a última frase vira a `fala` nova, e
  o rosto que diria a chamada dá lugar a um cartão de tela cheia com a `chamada` e uma seta
  para baixo. O resto é o mesmo reel, quadro a quadro (`reel_editorial.py`, topo).
- Sai `<slug>-yt.mp4` ao lado do final. A frase nova cobra na ElevenLabs (módulo Crie seu Clone de IA; `fabrica.py`,
  `_editorial` e `_entregas`).

## Entrega e tipo novo

- O final sai na pasta do estilo: o reel editorial em `videos/topo/`, os outros reels em
  `videos/reels/`, o criativo em `videos/criativos/` (`estilo.py`, eixo `entrega`;
  `videos/LEIA-ME.md`).
- Ajuste de um vídeo só vai no plano, como sobrescrita do eixo. Quando ele se repete, vira
  estilo novo herdando do mais próximo (`herda` no `ESTILOS`), não script novo (`estilo.py`;
  `fabrica-de-conteudo`, regra 8).
