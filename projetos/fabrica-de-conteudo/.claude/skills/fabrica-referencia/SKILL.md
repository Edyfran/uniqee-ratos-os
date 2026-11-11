---
name: fabrica-referencia
description: Use quando o usuário mandar um vídeo de referência (arquivo ou link de Instagram, YouTube, TikTok) e pedir para editar o vídeo dele "igual a esse", "no estilo desse reel", "copia a legenda e o ritmo desse vídeo". Lê a referência (quadros, fala, medidas, layout e densidade de motion), escolhe o estilo, o layout e a legenda mais próximos da fábrica (inclusive a tela dividida com painéis e peças), edita o vídeo do usuário e entrega uma folha lado a lado, dizendo o que ficou parecido, a densidade de motion de cada um e o que o kit não copia.
---

# Edita o meu igual a esta referência

O usuário manda uma referência e o vídeo dele. Você copia a **mecânica** da referência (corte,
legenda, zoom, layout, painéis e peças, trilha) no vídeo **dele**. Legenda parecida com o resto
diferente não é cópia: a referência com painel e peças tem **motion**, e o resultado tem que ter o dele. Rosto, marca, texto, música e filmagem da
referência nunca entram no final: ela só diz como editar. Não gasta nada e não pede chave.

Rode da raiz da pasta, com `uv run python`. Antes de tudo, `fabrica-de-conteudo` (a primeira vez
nesta máquina e as regras). O vídeo do usuário é o do celular: o corte é do `reel-camera`, e o
layout é o que a referência pedir (passo 3).

## 1. Ler a referência

```bash
uv run python tools/video-use/helpers/referencia.py le "<arquivo ou link>" -o videos/<slug>/referencia
```

Link: o `le` baixa pelo yt-dlp, só post público. Post privado, ou que pede login, não baixa:
peça o arquivo. O comando imprime as medidas (`medidas.json`) e escreve `folha-1.png`,
`folha-2.png` (14 quadros, o primeiro a 0,1 s) e `plano-longo.png` (o maior trecho sem corte,
em 6 quadros, para ver zoom). O campo `video` das medidas é o caminho da referência. Em 9:16 ele
mede também o **layout** (cada quadro é rosto cheio, tela dividida ou só painel: `layout`,
`layout_trechos` com o de/até de cada um), as **peças** (`pecas`, `pecas_por_s`: cada conteúdo novo do
painel), a `cobertura_de_pecas` (a fração do tempo com painel) e os **eventos de motion** por segundo
(corte, peça nova e troca de layout).

Transcreva na língua da referência: leia a legenda da folha e passe `pt`, `en` ou `es`. O Whisper
forçado na língua errada traduz sem avisar, e o `auto` erra em clipe curto com música (já deu
galês). Leva uns minutos; leia o texto:

```bash
uv run python tools/video-use/helpers/transcribe.py <video das medidas> --model large-v3 --language <pt|en|es> --edit-dir videos/<slug>/referencia
```

Abra as folhas e o `plano-longo.png` com o Read. Descreva o que vê, não o que supõe.

## 2. Descrever: a ficha

Escreva `videos/<slug>/referencia/leitura.md`, uma linha por campo. Sem o que ver, escreva "não vi".

| Campo | O que anotar | De onde sai |
|---|---|---|
| Formato | 9:16 ou 16:9, duração, fps | `medidas.json` |
| Legenda: letra | sans, serifa, condensada, manuscrita ou mono; peso; caixa alta ou minúscula | folha |
| Legenda: tamanho e lugar | altura do preenchimento da maiúscula (sem contorno) ÷ altura do quadro, em %; onde fica: topo, centro, faixa ou rodapé | folha |
| Legenda: cor e destaque | cor da letra e da palavra marcada (hex aproximado); marca por cor, caixa atrás, sublinhado, serifa ou escala | folha |
| Legenda: palavras e movimento | quantas palavras por vez (conte em 4 quadros seguidos); corte seco, sobe, mola, máscara | folha, transcrição |
| Ritmo | trocas de imagem por segundo; maior trecho sem troca; pausas e a maior pausa; palavras por minuto | `medidas.json`; palavras da transcrição ÷ minutos |
| Zoom | o rosto cresce ou encolhe de um quadro para o outro? De quanto (1,0 para 1,1)? Em que momento (ênfase, cada frase, gancho)? Se o plano mais longo não tem rosto (é b-roll), compare dois quadros da folha com rosto | `plano-longo.png`, folha |
| Layout | rosto cheio, tela dividida (painel em cima e o rosto num cartão embaixo, o molde Saraev) ou só painel; a ordem e o tempo de cada trecho; o painel é claro ou de tinta | `layout`, `layout_trechos`, folha |
| Peças e motion: densidade | quantas peças, por segundo, quanto do tempo tem painel, eventos por segundo, trocas de layout. Dois números que decidem o passo 3: `cobertura_de_pecas` e `pecas_por_s` | `medidas.json` |
| Peças e motion: quais | cada coisa por cima do rosto ou no painel: diagrama, lista, página, terminal, e-mail, mascote, contador, seta, título, tela gravada, b-roll, cena gerada; as vozes na tela (rótulo, bloco, título, palavra gigante); o segundo e a duração | folha |
| Trilha | `distancia_fala_piso_db`: abaixo de 22 há música ou ambiente sob a fala, e quanto menor, mais alta ela está. É indício: você não ouve o arquivo | `medidas.json` |
| Gancho e fecho | o quadro 0,1 s tem título? O final tem chamada ou tela final? | folha |
| Cor | claro ou escuro, quente ou frio, contraste | folha |

`trocas de imagem` conta corte seco, painel que entra e cena nova (pico entre dois quadros). Mão
que mexe e peça que desliza não contam. Imagem escura marca pouco: confira na folha. O layout vem da
textura (painel é liso, rosto com cenário não é): confira os `layout_trechos` na folha, e se um
trecho veio errado, a folha manda.

## 3. Escolher: do que viu ao plano

**Não crie estilo para este vídeo.** Escolha o estilo que existe, o preset de legenda que existe
e ajuste eixo no plano. Se existe a pasta `marca/`, o estilo dela é o ponto de partida.

```bash
uv run python tools/video-use/helpers/estilo.py                       # os estilos
uv run python tools/video-use/helpers/referencia.py presets           # as legendas, com a letra e o uso de cada uma
```

**O layout.** Decide o resto, então vem antes da legenda. Olhe a `cobertura_de_pecas` da leitura:

| A referência | O que fazer |
|---|---|
| menos de 25% do tempo com painel (rosto cheio, no máximo uma peça por cima) | layout cheio: `reel-camera` com a legenda e o zoom dela (passo 4) |
| 25% ou mais com painel (tela dividida, peças, diagramas, só painel) | **layout dividido**: `reel-camera` só para o corte e `referencia.py esboco` + `dividida` para o resto (passo 4b). A e_editorial desenha a fala na tela, então o corte vai sem legenda |
| tem o webm do avatar | `reel-editorial` (`fabrica-de-conteudo`): é o mesmo molde, com o avatar no lugar do vídeo de câmera |
| deitada (16:9) para um reel vertical | copie ritmo e legenda, não o quadro |

Mandar só a legenda quando a referência tem painel e peças entrega um vídeo com a cara da referência
e nada do motion dela. O `compara` acusa (passo 5), e você não entrega calado.

**A legenda** (layout cheio; no dividido a fala é a da e_editorial: sans e a palavra de peso em serifa
itálica). Escolha pelo olho, entre estes, e escreva na ficha por que:

| A referência tem | Preset |
|---|---|
| caixa alta grossa com contorno, 2 a 3 palavras, uma em cor forte | `contorno` |
| pílula clara com letra preta, 2 palavras, corte seco | `caixa-branca` |
| minúscula branca com sombra mole, a palavra longa em cor | `sombra-chave` |
| caixa de cor atrás da palavra falada | `caixa-cor` |
| a frase acende palavra a palavra, a cor troca a cada cartão | `karaoke-ciclo` |
| condensada em caixa alta com sombra dura | `condensada` |
| sans minúscula com a palavra-chave em serifa itálica | `editorial` |
| letra de mão, palavra sublinhada | `manuscrita` |
| faixa de cor atrás da linha | `fita` |
| sans branca sem caixa, palavra sublinhada | `minimal` |
| uma palavra enorme por vez | `gigante` |
| trailer, documentário, thriller, revista ou comédia (palavra-chave que crava atrás de quem fala) | `trailer`, `documentario`, `thriller`, `revista`, `comedia` |
| nenhuma bate | `padrao`, e diga na ficha o que muda |

A cor da palavra marcada é do preset. O plano não troca: se a cor da referência é outra, diga.

**Os ajustes de eixo**, todos no `reel.json` do vídeo:

| A referência | No plano |
|---|---|
| onde a legenda fica | `"desenho": {"legenda_layout": "topo" \| "centro" \| "faixa_criativo" \| "faixa" \| "rodape"}`. É uma zona, não uma altura, e a legenda encosta no pé dela: `topo` até 40% da altura, `centro` até 70% (cobre olho e boca num celular com o rosto no alto), `faixa_criativo` até 68% (o peito, a 66% na prática), `faixa` até 76% (a 77%: dentro da interface do Reels), `rodape` até 93%. Copie o lugar na pessoa, não no quadro: referência com a legenda no peito é `faixa_criativo`. Confira na folha que não cobre olho nem boca |
| a letra é outra | `"desenho": {"fonte": "<nome>"}`: um da lista `letras` do `referencia.py presets` (a letra do preset sai trocada) |
| uma ou duas palavras por cartão | `"desenho": {"legenda_palavras": 2}` (palavras cheias: as átonas não contam) |
| pausa: emenda colada, ou respiro | `"janelas"`, da voz medida no áudio (passo 4, "O corte"). Não use `corte.ajuste`: o corte pelo texto herda o erro do Whisper |
| fala rápida e o lint recusa card curto | `"desenho": {"ritmo": [0.167, 0.033]}` |
| imagem mais contrastada ou mais quente | `"graduacao": {"preset": "neutral_punch"}` (`subtle`, `warm_cinematic`, `none`) |
| tem música sob a fala | `"recursos": {"+": ["trilha"]}`, `"adaptadores": {"trilha": "cama"}` e `"trilha": {"faixa": "<a música dele, ou uma de exemplos/trilhas/ pelo tom>", "cama": -22.0}` |
| zoom | só se a referência tem. Não é campo do plano: vai no `camera` do `cards.json` (passo 4) |
| fps | `"imagem": {"fps": 30}` (a legenda e o zoom terminam a 30 fps, então 30 evita duas conversões) |
| volume final | `"entrega": {"alvo": <o lufs da referência>}`: com a `cama` o final fecha em -16 LUFS, e as referências ficam perto de -14 |

**A trilha.** O reel do celular não leva trilha (`fabrica-de-conteudo`, regras 6 e 7); aqui ela só
entra se a referência tem música. A `cama` deixa a música sob a voz o vídeo todo e abaixa no
ataque de cada frase; `trilha.cama` é o nível em LUFS (-24 baixo, -21 presente). Compare a
`distancia_fala_piso_db` do resultado com a da referência, no `compara`, e mexa de 3 em 3 dB, no
máximo duas vezes (6 dB de `cama` mexem uns 3,6 dB na distância). Pare em -19: mais alta, a música disputa com a voz (você não ouve o arquivo), e
a distância da referência pode não se alcançar (entrevista com ruído de sala). O `sob_fala` do
estilo (0,03) é a música quase muda: não serve para copiar música audível.

**Quantas trocas.** O alvo é `trocas por s da referência × duração do final`. O corte do silêncio
é o mesmo plano, mas a medida conta a emenda e o degrau de zoom: rode o `compara` antes de
acrescentar peça. As trocas vêm de mudança de imagem: peça da biblioteca
(`fabrica-movimento`), b-roll que o usuário tem e, só se a referência dá zoom, zoom. Referência
sem zoom, final sem zoom. Nunca corte no meio da palavra.

## 4. Montar e editar

Transcreva o vídeo do usuário:

```bash
uv run python tools/video-use/helpers/transcribe.py <video> --model large-v3 --language pt --edit-dir videos/<slug>
```

**O corte.** Depois de uma pausa, o Whisper marca o começo da palavra dentro do silêncio, e cortar
pelo texto guarda de 0,3 a 0,5 s de vão em cada emenda. Corte pela voz medida no áudio:

```bash
uv run python tools/video-use/helpers/referencia.py vozes <video> --pausa 0.15 --transcript videos/<slug>/transcripts/<video>.json -o videos/<slug>/janelas.json --alinha videos/<slug>/transcripts/<video>.alinhada.json
```

Cole a lista em `janelas` e aponte `transcript` para a `.alinhada.json`: sem ela, a palavra que o
Whisper pôs antes da voz cai fora da janela e some da legenda. `--pausa` é o menor vão que o corte
tira: vão menor fica dentro da fala. 0,15 tira quase todo vão (referência com `pausas` 0); 0,35
deixa passar o respiro curto (referência com `maior_pausa_s` perto de 0,3 a 0,4). Janela sem
palavra (respiração, ruído) já sai da lista. Pausa longa no meio e frase solta no fim do bruto o
`vozes` não resolve: tire à mão com `drops` e diga ao usuário.

Escreva `videos/<slug>/reel.json`. `fonte`, `transcript` e `legenda` partem da pasta do plano;
`trilha.faixa` parte da raiz do kit.

```json
{
 "estilo": "reel-camera",
 "slug": "<slug>",
 "fonte": "<o vídeo do usuário>",
 "transcript": "transcripts/<video>.alinhada.json",
 "janelas": [[1.12, 3.37], [3.73, 5.81]],
 "desenho": {"legenda": "<preset>", "legenda_layout": "<topo|centro|faixa|rodape>"},
 "recursos": {"-": ["broll"], "+": ["trilha"]}
}
```

(O `-` só cala o aviso de b-roll; tire se ele mandar b-roll em `broll`. O `+` só vale se a
referência tem música.) Junte os ajustes da tabela acima. Confira e renderize, como nas regras da `fabrica-de-conteudo`: nada aqui
cobra, então renderize logo depois do `--seco`; se ele mostrar passo que cobra, pare.

```bash
uv run python tools/video-use/helpers/fabrica.py videos/<slug>/reel.json --seco
uv run python tools/video-use/helpers/fabrica.py videos/<slug>/reel.json
uv run python tools/video-use/helpers/captions_viral.py --lint videos/reels/_trabalho/<slug>/cards.json
```

O `checks` não vê a legenda: o lint vê. Erro de "card curto" é fala mais rápida que o ritmo da
legenda: `"desenho": {"ritmo": [0.167, 0.033]}` ou menos palavras por cartão.

**Zoom.** A primeira rodada deixa `videos/reels/_trabalho/<slug>/cards.json`, no tempo do vídeo já
cortado (o `edl.json` da mesma pasta lista os trechos: a soma das durações até o trecho N é o
instante dele no final). Copie para `videos/<slug>/cards.json`, acrescente `camera` e aponte o
plano para ele:

```json
"camera": [{"t0": 2.5, "t1": 5.0, "zoom": [1.0, 1.1], "ease": "sine"},
           {"t0": 8.0, "t1": 10.0, "zoom": [1.1, 1.0], "ease": "solta"}]
```

No `reel.json`, `"legenda": "cards.json"`. Refaça a legenda e o que vem depois, sem cortar de
novo: `fabrica.py videos/<slug>/reel.json --desde trilha` (as etapas do `--desde` são `corte`,
`render`, `desenho`, `composicao`, `trilha` e `entrega`; a legenda mora em `trilha`). Ponha o zoom onde a referência põe (na
ênfase, no começo de cada frase) e na medida dela; até 1,12 passa por zoom suave.

**Peça por cima** (gancho, seta, contador, carimbo; a escolha é da `fabrica-movimento`). Renderize
a peça e ponha sobre o final. O texto da peça sai da fala do usuário: nunca da referência, nunca
inventado.

```bash
uv run python tools/v2/v2.py render g_gancho "l=<linha 1>|*<destaque>" pos=topo tam=96 dur=3 --fps 24 --out videos/<slug>/gancho.mov
uv run python - <<'EOF'
import sys; sys.path[:0] = ["tools/v2", "tools/video-use/helpers"]
from pathlib import Path
import v2
v2.sobre(Path("videos/reels/<slug>.mp4"), [{"arquivo": "videos/<slug>/gancho.mov", "em": 0.0, "ate": 3.0,
         "largura": 1080, "altura": 1920, "segura": False}], Path("videos/reels/<slug>-final.mp4"))
EOF
```

O `--fps` é o do final (a linha `fps` do `compara`); `ate` não passa da duração do vídeo. Com peça,
o final é o `<slug>-final.mp4` e o `<slug>.mp4` é o intermediário: diga ao usuário qual postar.
**Capa:** vale a regra 7 da `fabrica-de-conteudo` (`fabrica-estilo`, "Capa"); ela não faz parte da
cópia da referência.

**4b. Layout dividido** (a referência tem painel e peças). O molde é a `e_editorial` do `tools/v2`: o painel em cima com a
peça da vez, o seu vídeo num cartão de cantos redondos embaixo e a cabeça passando da borda do cartão, a fala em cartões de
1 a 2 palavras, as vozes (rótulo, bloco, título) em serifa itálica. O que decide o ritmo é a leitura da referência.

1. O corte, pela fábrica, **sem legenda**: no `reel.json` do passo acima ponha `"recursos": {"-": ["legenda", "broll"]}` (e `janelas` da
   voz medida). O final dela é o `take`; o `cards.json` da mesma pasta de trabalho tem cada palavra no tempo do vídeo cortado.
2. O esboço: as cenas da referência (`layout_trechos`) esticadas ao tamanho do seu vídeo, cada borda no fim de uma palavra, e as
   peças como vagas:

```bash
uv run python tools/video-use/helpers/referencia.py esboco videos/<slug>/referencia/medidas.json --cards videos/<slug>/cards.json --take <o take> -o videos/<slug>/dividida.json
```

3. Preencha cada peça (`"g": "?"` e `"_preencher"`) com **o que o usuário disse naquele trecho, e só isso** (regra 3): `g` é um de
   `mascote` (pose, chip, chip_t, cor), `term` (titulo, linhas, lt), `fluxo` (topo, meio, base, t_meio, t_base), `pagina` (url,
   legenda, marca), `lista` (titulo, itens, passo) e `email` (titulo, linhas, novo). Os `t` das peças caem na palavra que as chama.
   Junte duas peças curtas se a referência as junta. Acrescente `vozes` onde a referência tem (`rotulo`, `bloco`, `titulo`, `chamada`).
   `"marca"` é `robo` (o padrão); o ninja é a marca do dono, não do aluno. Nenhum texto, nome, número ou logo da referência entra.
4. Monte: o `dividida` recorta a pessoa do take (Vision da Apple, só macOS; sem ele o cartão sai sem a cabeça passando da borda), gera as
   camadas e compõe:

```bash
uv run python tools/video-use/helpers/referencia.py dividida videos/<slug>/dividida.json -o videos/<slug>/final.mp4
```

O plano recusa peça sem preencher, `g` desconhecido e peça fora de uma cena de painel. O final já tem a voz do take; trilha só se a
referência tem (passo 3, "A trilha").

## 5. Conferir e comparar

```bash
uv run python tools/video-use/helpers/checks.py <final.mp4>
uv run python tools/video-use/helpers/referencia.py compara <video da referência> <final.mp4> -o videos/<slug>/referencia/lado-a-lado.png
```

O `checks` lista o que falhou, com o que mediu; diga cada falha ao usuário. Falha de 0,1 dB no
`pico-audio` é borda: conte, não refaça. O `compara` põe a referência na fileira de cima e o
resultado na de baixo, nos mesmos instantes relativos, e imprime as medidas lado a lado, com a
**densidade de motion**: o layout (rosto cheio · dividida · tela), as peças e os eventos por segundo,
a referência contra o resultado. Abra a folha com o Read e compare quadro a quadro: letra, lugar, cor,
ritmo, zoom, layout, peças.

**O `compara` imprimiu `ATENÇÃO`?** O resultado tem menos da metade do painel, das peças ou dos eventos da
referência. **Não entregue calado.** Refaça no layout dela (passo 4b), ou diga ao usuário os números ("a referência tem
painel em 76% do tempo e 0,53 peça por segundo; o seu tem 0%"). Se você entrega assim, é por escolha dele, dita.

## 6. O que dizer

Em até 12 linhas, sem elogio e sem prometer "igual":

- **Parecido:** o que bate, com o número (trocas por s, pausas, lugar e tipo da legenda, e o motion: layout, peças por s, eventos por s).
- **Aproximado:** o que chegou perto e por que não bateu (o preset mais próximo, o zoom que ficou
  mais curto).
- **O kit não copia:** o que a referência tem e esta pasta não faz. Diga o que você viu de cada um.
  - a letra e a cor exatas da legenda (só os presets e as fontes de `assets/fontes/`);
  - cenário, luz, rosto e marca da referência: o fundo é o do vídeo do usuário;
  - tela gravada, cena gerada, b-roll e antes e depois com o bruto ao lado: o usuário precisa ter
    o material (cena gerada vem do módulo Cenas de Cinema com IA);
  - peça de assinatura do autor (painel 3D, animação de marca): só as da biblioteca (`v2.py lista`); o conteúdo das peças é
    o do usuário, nunca o da referência;
  - a música: o kit mede se há, não acha a faixa;
  - transição de efeito (glitch, chicote) e som a cada corte, fora do que a biblioteca traz.
- **Próximo passo:** um ajuste só, o que mais aproxima.

## Regras

1. **Nada do conteúdo da referência vai para o final**: texto, nome, logo, rosto, música. O
   arquivo dela fica em `videos/<slug>/referencia/` e nunca vai para `videos/reels/`.
2. **Estilo novo, não.** O mesmo ajuste de eixo em três vídeos vira estilo novo herdando, em
   `marca/estilos.json` (`fabrica-estilo`). Pasta nova com script, nunca. O layout dividido não é estilo
   novo: é o `reel-camera` no corte e o `dividida` por cima.
3. **Não invente fato sobre o usuário.** Gancho e peça saem do que ele disse.
4. **A ficha é do que se vê.** "Não vi" vale mais que um palpite.
5. **Um ajuste por vez** quando o resultado destoar: troque, renderize só do passo afetado
   (`--desde`), compare de novo.
6. **Legenda igual com motion diferente não é cópia.** A referência com painel e peças pede o
   layout dividido; o resultado sem eles só sai com o `ATENÇÃO` do `compara` dito ao usuário.
