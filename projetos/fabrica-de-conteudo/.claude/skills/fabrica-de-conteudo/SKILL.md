---
name: fabrica-de-conteudo
description: Use quando o usuário pedir um reel (vertical 9:16) do vídeo que ele gravou no celular ou de um vídeo que ele já tem (o avatar que gerou na HeyGen, o webm sem fundo), legenda queimada, trilha, capa, ou quando um plano da fábrica der erro. Também quando ele pedir voz clonada, avatar, cena gerada por IA ou criativo de cinema, para saber se o módulo está instalado. Na primeira vez nesta pasta, confere e adequa a máquina antes de tudo. Roda a Fábrica de Conteúdo com IA desta pasta.
---

# Fábrica de Conteúdo com IA

A **fábrica** recebe **estilo** e **plano** e devolve o **final**. O plano diz o que é
daquele vídeo (a voz, o texto, as peças). O estilo diz o que vale para todo vídeo
daquele tipo (corte, voz, imagem, desenho, trilha, entrega). Rode tudo da raiz
desta pasta, com `uv run python`.

```bash
uv run python tools/video-use/helpers/estilo.py                 # os estilos
uv run python tools/video-use/helpers/estilo.py reel-editorial  # um inteiro, eixo a eixo
uv run python tools/video-use/helpers/fabrica.py plano.json --seco   # confere, não renderiza
uv run python tools/video-use/helpers/fabrica.py plano.json          # renderiza e entrega
uv run python tools/video-use/helpers/fabrica.py plano.json --desde desenho
```

Sem `.fabrica-ok` na raiz, faça antes a seção "Primeira vez nesta máquina" do `INSTALAR.md`, inteira, e volte para cá.

## Os tipos

**Receita curta** — "corta o vídeo que gravei e põe legenda" (vídeo do celular):

1. Escreva `videos/<slug>/reel.json` com só o vídeo: `{"fonte": "<arquivo>.mov"}`. Estilo,
   slug, transcrição e normalização do celular (HEVC, taxa variável, giro) a fábrica completa.
2. `uv run python tools/video-use/helpers/fabrica.py videos/<slug>/reel.json --seco`
3. **Antes do primeiro `--storyboard`: o movimento que ele quer.** Leia o que já está gravado:

   ```bash
   uv run python tools/video-use/helpers/movimento.py ler
   ```

   Ele devolve `densidade`, `efeitos`, `vetos` e `falta`. Se `falta` lista `densidade` ou `efeitos`,
   pergunte ao usuário, uma vez, em português comum, e grave a resposta na hora. Se já está gravado, ou
   se ele já disse no pedido ("quero intenso, com zoom e whoosh"), não pergunte: grave o que ele disse.
   Uma pergunta de densidade, com três opções, a **intensa primeiro e como a recomendada para o
   primeiro vídeo** ("no ritmo dos anúncios": é o que faz o primeiro vídeo impressionar):

   - **intensa (recomendada)**: algo muda a cada 2 s, no máximo, no ritmo dos anúncios;
   - **média**: algo muda a cada 3 s e meio, no máximo;
   - **calma**: a fala manda e o vídeo respira; algo muda na tela a cada 6 s, no máximo.

   Se ele disser "tanto faz" ou não souber, grave intensa, com todos os efeitos, sem perguntar mais:
   `movimento.py grava --padrao`. Se ele escolher, pergunte também quais efeitos quer: zoom da câmera,
   transição, palavra grande atrás da cabeça, troca de layout (o rosto passa pro fundo trocado),
   peças (painel, número, chamada), linhas e efeitos sonoros. Grave:

   ```bash
   uv run python tools/video-use/helpers/movimento.py grava --densidade intensa --efeitos zoom,transicao,palavra_atras,layout,pecas,sons
   ```

   Os efeitos são `zoom`, `transicao`, `palavra_atras`, `layout`, `pecas`, `linhas` e `sons`. A resposta
   vale para os próximos vídeos dele: nunca pergunte a mesma coisa duas vezes.
4. `uv run python tools/video-use/helpers/fabrica.py videos/<slug>/reel.json --storyboard`: transcreve, corta num
   rascunho barato e escreve a fala cortada (`_trabalho/.../rascunho/fala_cortada.json`). **O caminho padrão
   não tem pauta visual**: o comando decide as legendas, **propõe o movimento que a pauta não cobriu pela densidade gravada** (zoom, palavra atrás, número,
   chamada no fim, troca de layout) e termina numa linha: `storyboard: N peças · N avisos · revisão em
   <caminho>`. É essa linha que você lê, não o `storyboard.md`. A pauta visual (4b) só entra com `--pauta`, e só
   se o aluno pediu.
   **Antes de renderizar, leia os avisos do storyboard.** Dois não são enfeite: `chamada-final` (vídeo de 8 s ou mais termina no
   `g_comenta`; se a fala não traz a palavra e a promessa, pergunte ao aluno numa frase: "que palavra as pessoas comentam, e o que
   recebem?", e nunca invente uma chamada que ele não disse) e `carimbo-sem-negacao` (carimbo e palavra gigante não levam "sem",
   "não" ou "nunca": ficam com a palavra forte da frase, porque o leitor entende o contrário do produto).
4b. **A pauta visual: opcional, fora do caminho do primeiro vídeo.** Ofereça só se o aluno pedir "prova na tela" ou
   "tela dividida"; não ofereça por conta própria, nem pergunte sobre ela, e pule este passo inteiro no caso normal. Com
   `--pauta`, sem o `videos/<slug>/visual.json` ao lado do plano o `--storyboard` para antes do storyboard, numa linha
   que começa com `pauta:` (ela não é erro: é este passo). Cada ideia dita
   ganha a **prova** na tela: o print do que foi citado, o logo, o número, o antes e depois, com a pessoa recortada
   embaixo. Ordem, quando pedida: **densidade (3) → corte e fala (4) → pauta (aqui) → busca e pergunta única → storyboard → revisão → render.**
   1. Leia **`pauta-visual.md`** (nesta pasta, autossuficiente: a tarefa, a tabela de provas, o exemplo e o formato
      de saída) e a saída de `transcript.py frases <fala_cortada.json>`. Escreva `videos/<slug>/visual.json`
      **você mesmo, lendo só** `pauta-visual.md`, as frases e as respostas do aluno (o Codex não escolhe modelo por subagente: não
      abra mais nada para esta etapa, pra não gastar contexto à toa).
   2. Rode `acha.py` (valida e busca no mesmo comando). Regras que não mudam: toda batida que depende de rede ou do
      aluno leva `alternativa`; **mostrar, não dizer** (primeiro a imagem real da fonte que a fala cita: foto do post,
      imagem do README, capa do site, `origem: midia`; depois o que o aluno mandar, foto livre, a demonstração animada
      da biblioteca, `i_tv`, `i_terminal`, `d_grade`, `d_linha`, e só então texto: mais de 1 painel de texto num vídeo
      de até 45 s reprova; mais de 1 batida de confiança fraca sem pergunta por 45 s também reprova, e logo solto conta como fraca); o terminal é demonstração, só com os comandos que a fala conta.
   3. A pergunta única: o que o `acha.py` imprime em "PERGUNTA AO ALUNO" (prints que só o aluno tem **e** as batidas de confiança
      fraca: texto, logo solto, demonstração genérica; no máximo 5 itens). **Você precisa prever se uma batida vai ficar ruim e perguntar
      ao aluno o que ele quer ver.** Pergunte tudo de uma vez, com a queda de cada um ("não tenho" / “deixa comigo” gera a
      melhor opção que não é texto). Depois de cada resposta, grave o `arquivo` na `fonte` e rode o `acha.py` de novo.
   4. Rode o `--storyboard --pauta` de novo. A proposta de movimento só completa os vãos que a pauta não cobriu.
5. **O storyboard (com a pauta do 4b, se o aluno a pediu) vem com a proposta de movimento; ajuste só o que não fizer sentido na fala.** Não monte do
   zero e não escreva `pecas` no `reel.json` quando a proposta serve: leia a fala com
   `transcript.py frases <transcript.json>` (o `videos/<slug>/_trabalho/.../transcripts/*.json`, ou o
   `fala_cortada.json` do rascunho), nunca o JSON cru, confira os itens da proposta contra ela e troque
   ou tire só o que destoa (`--texto <slug>.storyboard N "X"`, `--tira <slug>.storyboard N`). **Só peça
   do cardápio**: `uv run python tools/v2/v2.py cardapio` imprime de uma vez as peças, uma linha cada, com
   os parâmetros e um exemplo. Não rode `lista` nem `info`. Se o aviso `casca-de-pagina` recusar uma peça,
   ele já lista na mesma linha as trocas do cardápio: escolha uma de uma vez e rode o `--storyboard`
   uma só vez. Se a proposta saiu vazia (fala curta demais, ou o aluno vetou quase tudo), ou se ele
   quer o movimento escolhido à mão, vale o caminho manual: escreva no `reel.json`, ao lado de `fonte`
   (o que o plano traz à mão dispensa a proposta):

   ```json
   {"fonte": "meu-video.mov",
    "pecas": [{"peca": "g_gancho", "q": {"l": "Pare de editar à mão"}, "em": "pare", "dur": 2.5},
              {"peca": "g_contador", "q": {"de": "0", "para": "30", "rot": "vídeos prontos"},
               "em": "trinta", "dur": 3}]}
   ```

   `em` é a palavra dita onde a peça entra (a primeira ocorrência; `"#2"` pega a segunda,
   `"palavra+0.2"` desloca) ou um segundo do vídeo já cortado. `dur` é quanto ela fica na tela.
   Duas peças não se sobrepõem. Rode o `--storyboard` de novo.
6. **O storyboard que vai pro aluno tem pelo menos 2 peças.** Confira na linha de resumo do passo 4
   (`N peças`); com menos de 2, proponha mais e rode o `--storyboard` de novo. Diga onde está a
   `<slug>.storyboard/revisao.html` e peça que ele a abra (dois cliques): é a página única, com os avisos de
   ritmo no topo e, em cada cartão, o clipe do trecho, a peça tocando por cima dele, a fala do instante e o
   aviso do item. Ele dá play no clipe e vê a peça animada, sem render.
7. O usuário marca Manter, Talvez ou Tirar em cada cartão, escreve uma nota se quiser, clica em **Copiar
   revisão** e cola aqui: uma linha por item, como `4 tirar`, `9 texto: novo texto` e `7 talvez: entra mais
   cedo`. **Aplique de uma vez**, com um comando só:
   `uv run python tools/video-use/helpers/storyboard.py --aplica <slug>.storyboard -`, passando o texto colado
   na entrada (ou o caminho de um arquivo com ele). Ele tira e troca o texto sozinho e imprime, em lista curta,
   só o que sobrou pra você: os `talvez`, as notas e o que não entendeu. Resolva só esses itens, pela
   nota (zoom e som não têm texto; trocar o texto de uma peça ou palavra atrás da cabeça é
   `--texto <slug>.storyboard 7 "X"`), e rode o `--storyboard` de novo: ele refaz só os itens que mudaram.
   Repita até ele dar o ok. Se ele só disser "tira o nº 4" no chat, `--tira <slug>.storyboard 4` vale
   igual. Os campos do `reel.json` (`pecas`, `camera`, `palavras_atras`, `fundo`, `sons`) entram só na primeira
   rodada que os traz; depois vale o `decisoes.json`, e o que ele tirou não volta.
   **Correção de gosto vira escolha gravada, na hora**, antes de rodar de novo: "tira o raio" é
   `movimento.py grava --veta e_raio`; "menos zoom" ou "sem zoom" é `--veta zoom` (e "pode voltar o zoom",
   `--perdoa zoom`); "mais calmo" é `--densidade calma`. O nome é o da peça (`e_raio`) ou o tipo de
   efeito (`zoom`, `transicao`, `palavra_atras`, `pecas`, `linhas`, `sons`). Sem isto, o próximo vídeo
   põe de volta o que ele já mandou tirar, e ele corrige tudo outra vez.
8. Só com o ok: o mesmo comando, sem `--seco` nem `--storyboard`, renderiza com as decisões
   corrigidas. Mostre o MP4 ao usuário.
   O `--storyboard` já mediu o que dá pra prever do `sem-flash` e do `quadro-vazio` (o que já está no
   corte): se avisou, resolva antes do render, para não renderizar duas vezes. O salto que a própria peça
   ou o fundo trocado causam só existe no render final.
   **Se o render imprimir a linha `recorte: fundo poluído (...)`**, a trava reprovou o recorte da pessoa e o trecho já caiu
   pro cartão: nada muda de layout sem a resposta do aluno. Faça a pergunta da linha numa frase, junto da pergunta única se
   ela ainda não foi feita ("seguir com você no cartão, com o seu fundo, ou regravar com fundo liso?"). Grave a escolha em
   `onboarding/escolhas.json`, na chave `fundo` (`"cartao"` ou `"regravar"`); com `"cartao"` já gravado, não pergunte de novo.
   Se ele for regravar, dê as 3 dicas: parede lisa a 1 m atrás, luz de frente, nada colado na cabeça.
   **Conferência final: a linha `checks:` que o render imprime.** Com `0 falharam`, o vídeo está
   conferido: não abra imagem, não monte folha de quadros, não rode `estilo pedidos`. Se alguma linha
   `CHECK` aparecer, olhe só o quadro do segundo que ela aponta.
9. **A capa é a última coisa, e só depois do vídeo aprovado.** O primeiro vídeo não leva capa. Com o
   vídeo aprovado e pronto pra postar, **pergunte numa frase**: "Quer uma capa? Se tiver uma ideia de
   frase ou de foto, me diz; se não, eu proponho uma." Só com a resposta, faça a capa pelo comando de
   um passo da skill `fabrica-estilo` ("Capa"). Não investigue o `capa.py` nem rode a peça à mão.
10. Ajuste de estilo (música, cor, letra) vem no pedido seguinte, não antes do primeiro vídeo.

O modelo de transcrição (~3 GB) baixa na instalação; se o aluno pulou esse passo, baixa no primeiro
vídeo e leva uns minutos, uma vez só. **Sem vídeo gravado, não rode nada**: nem exemplo, nem vídeo de
outra pessoa. Editar o que não é dele não ensina nada. Peça que ele grave uns 30 s no celular, falando
do que faz, e mande o arquivo; quando chegar, siga a receita acima.

Todo vídeo sai pela **cadeia**: um plano num estilo, o `--seco`, o render. Todo plano tem
`estilo`, `slug` (o nome do final) e `fonte`, e mora na pasta do vídeo
(`videos/<slug>/reel.json`, ao lado do material). Escolha o tipo pelo que o usuário já tem:

| Ele tem | Tipo | Estilo |
|---|---|---|
| o webm do avatar gerado na HeyGen com fundo removível, ou o vídeo do celular exportado sem fundo (webm com alfa); com ou sem a voz à parte | Reel do webm pronto | `reel-editorial` |
| o vídeo do celular com o fundo dele | Reel do celular | `reel-camera` |

Todo reel sai com **trilha** (regra 6); a **capa** vem por último, perguntando (passo 9, regra 7). Com o
**banco de cenas** na pasta, o fundo atrás do rosto vem dele (abaixo).

**Efeito sonoro** a Fábrica tem, e nunca diga o contrário. Cada peça toca os sons dela sozinha,
onde entra. O que o usuário pedir a mais ("um whoosh quando entra o título", "um ding no número")
vai no `sons` do plano, em segundos do vídeo já cortado (o `fala_cortada.json` do rascunho dá o
tempo de cada palavra):

```json
"sons": [{"tipo": "whoosh", "t": 1.0}, {"tipo": "ding", "t": 6.0},
         {"arquivo": "meu-som.mp3", "t": 9.5, "ganho": 0.5}]
```

Os nomes são os de `tools/v2/sfx/sfx.json` (pop, click, whoosh, ding, impact, type, moeda…); o
`arquivo` é um som do usuário, ao lado do plano. Som de cinema (riser, boom, sub-drop, hit…), no
máximo três por vídeo.

**Movimento pela densidade.** Depois de gravada a densidade (passo 3), monte o plano assim:

- Cada **batida** (um momento da fala que ganha efeito) tem um **peso**: 1 é leve (um zoom suave, um
  som, um chip), 2 é médio (uma peça, uma palavra marcada), 3 é a batida que para tudo (palavra enorme
  atrás da cabeça com o fundo trocado, zoom que crava). No máximo **um quarto** das batidas, e do
  tempo do vídeo, em peso 3. Ponha `"peso": 3` na peça que for.
- **Vão máximo** entre uma mudança na tela e a seguinte: intensa 2 s, média 3 s e meio, calma 6 s.
  Peça, zoom, palavra atrás e troca de layout contam; som não. O `--storyboard` e o `--seco` avisam o maior vão.
- **Troca de layout**: o rosto sai da tela cheia e passa pro fundo trocado atrás da palavra forte (a
  `palavras_atras` com `fundo`) e volta. Conta como movimento e tem mínimo: intensa uma a cada 12 s,
  média uma a cada 20 s, calma nenhuma. O aviso `pouca-variacao` acusa a falta. A proposta automática
  já a põe.
- **Sons à mão: de 1 a 3**, nas batidas de peso 3 (`hit`, `tape-stop`, `boom`, `whoosh`, `ding`; os
  nomes de `tools/v2/sfx/sfx.json`). Peça que já toca o som dela leva `"mudo": true` se um som à mão
  cobre o mesmo instante.
- **Nada de casca de página**: contador N/M, rótulo de canto, chip parado, barra de progresso,
  título digitado. Ocupam a tela e não movem o vídeo. O aviso `casca-de-pagina` acusa.
- **Recorte da pessoa sempre pelo `rembg`**, que roda no Windows, no Mac e no Linux. Não troque por
  outro recorte nem pule o recorte: a palavra atrás da cabeça e a peça atrás dela dependem dele.
  A câmera fica em 1,0 enquanto há palavra atrás da cabeça (aviso `camera-atras`).
- Respeite o que ele escolheu: efeito que não está em `efeitos`, ou que está em `vetos`, não entra no
  plano (aviso `veto`).

Os campos do `reel.json` (todos opcionais; `em`, `ate` e `t` são um segundo do vídeo já cortado ou uma
palavra dita, como nas peças):

```json
{"fonte": "meu-video.mov",
 "pecas": [{"peca": "g_gancho", "q": {"l": "Pare de editar à mão"}, "em": "pare", "dur": 2.5, "peso": 2}],
 "camera": [{"em": "pare", "dur": 1.2, "zoom": [1.0, 1.25], "ease": "sine"},
            {"em": "trinta", "dur": 0.4, "zoom": [1.0, 1.32], "ease": "crava", "borrao": 4}],
 "palavras_atras": [{"em": "trinta", "texto": "TRINTA", "dur": 0.8, "cor": "#F2C744"}],
 "fundo": {"de": "pare", "ate": "trinta"},
 "sons": [{"tipo": "hit", "t": "trinta"}]}
```

`camera` é o zoom (`zoom: [de, até]`; `"ease": "crava"` é o zoom que crava, com `borrao`);
`palavras_atras` é a palavra enorme atrás da cabeça, e cobre a legenda do instante; `fundo` troca o
fundo atrás dessas palavras no trecho `de`..`ate`. A peça pode levar `"atras": true` (atrás da cabeça,
só no `reel-camera`), `"mudo": true` e `"peso": 1|2|3`. O que o plano traz entra no `decisoes.json`
na primeira rodada do `--storyboard`, com número.

**Igual a uma referência** — o usuário manda um vídeo (arquivo ou link) e pede "edita o meu igual
a esse". Siga a skill `fabrica-referencia`: ela lê a referência (layout, peças e motion também), escolhe
o layout, o estilo e a legenda mais próximos, edita o vídeo dele e entrega a folha lado a lado. Não é
estilo novo: é o `reel-camera` com os ajustes que a referência pede, e, se a referência tem tela
dividida e peças, o layout dividido por cima do corte.

## Os módulos

A voz clonada, o avatar, as cenas geradas por IA e todo vídeo deitado (16:9) não são desta skill: vêm em módulos, cada um
com a skill dele em `.agents/skills/`. Antes de um pedido desses, veja se a pasta existe:

| Pedido | Módulo | Skill |
|---|---|---|
| reel editorial narrado pela voz clonada, reel com avatar, a narração, o áudio pro HeyGen, o look | Crie seu Clone de IA | `fabrica-clone` |
| cena gerada por IA (Higgsfield), o lote, o banco de cenas, o criativo de cinema | Cenas de Cinema com IA | `fabrica-cinema` (e a `fabrica-cenas`, a câmera de cada cena) |
| vídeo deitado (16:9): o vídeo longo do YouTube, a aula gravada ou narrada, e o pacote dele (títulos, capas, descrição com capítulos, o Short) | Kit de Edição para YouTube | `fabrica-youtube` (a aula narrada pede o Clone também) |

Com a pasta, siga a skill do módulo. Sem ela, diga ao usuário que esse tipo vem no módulo,
pago à parte, e ofereça o que esta skill faz: editar o vídeo que ele gravou. Não monte o
caminho do módulo à mão: a fábrica recusa o plano que chama helper que não está na pasta.

**Reel do webm pronto** — estilo `reel-editorial`, sem nada pago: o rosto já
existe. É o pedido "edita esse vídeo pra reel: corta as pausas, põe legenda, arruma a tela e
faz a capa". O plano parte do molde `exemplos/reel-do-webm/reel.json`:

- `fonte` é a voz que foi pra HeyGen; sem ela à parte, o próprio webm. `avatar.alinha`
  (`true`) acha cada pedaço da voz no áudio do webm, e o rosto acompanha a voz. Onde a voz
  fala e o webm não tem rosto, o passo `alinha` recusa a base e diz onde o rosto existe. O
  buraco curto no meio da fala vira um trecho `congela` que começa ainda no rosto: o quadro
  para, como a pose da capa. O fim sem rosto (a chamada gravada depois) vai sobre uma `cena`
  do banco, com a peça da chamada.
- **Corta as pausas:** a voz é o relógio. Transcreva antes do plano (`transcribe.py <voz>
  --model large-v3 --language pt --edit-dir videos/<slug>`). Vão de mais de 0,6 s entre
  palavras é pausa: `apara_pausas.py <voz> --transcript videos/<slug>/transcripts/<voz>.json -o
  <voz>-aparada.wav`, e a aparada vira a `fonte`; o `alinha` leva o rosto junto. Voz sem vão
  assim fica como está.
- **Põe legenda:** a fala em duas letras sai sozinha do transcript da voz.
- **Arruma a tela:** a `base` trecho a trecho, o rosto `cheio` sobre o fundo do banco que
  troca na fala (`fabrica-composicao`), o gancho parado no quadro 0 e a chamada só no fim.
- **Faz a capa:** o bloco `capa`, com `foto` `["<o webm>", <segundo>]`, um quadro do rosto já
  sem fundo.
- Voz que traz várias chamadas no fim vira `fechos`, um final por chamada
  (`reel_editorial.py`, topo). O primeiro da lista é o final que se posta: no reel, o que pede
  para comentar a `palavra`. "Toca em saiba mais" é de anúncio (o botão só existe lá), e "rola
  aí" é da página.

Pronto é: o render até o fim, o final terminando na chamada da `palavra`, e a folha
(`_trabalho/folha-1fps.png`) com o rosto em todo trecho que tem fala dele, o fundo trocando
onde a voz nomeia o lugar e a capa ao lado do final.

**Reel do celular** — estilo `reel-camera`, bruto `camera`. Corta o silêncio e a palavra
repetida do que ele gravou, acerta a cor sem filtro, põe legenda e b-roll, e a legenda pode passar
atrás da pessoa. O plano mínimo é só a `fonte` (o vídeo), no estilo que o onboarding gravou como
`_padrao` em `marca/estilos.json` (sem ele, `reel-camera`), com a `lofi-calma` de
`exemplos/trilhas/` por baixo quando ele não pediu música. A fábrica transcreve (na nuvem da ElevenLabs, se há
`ELEVENLABS_API_KEY`; senão no computador, com o `large-v3` de ~3 GB, baixado na instalação) e corta
por palavra sozinha. Quando ele quer mais, soma `drops` (o que sai à mão) e
`broll`; com `janelas` ou `transcript` no plano, o corte é o do plano e a fábrica não transcreve.

## O banco de cenas

O **banco de cenas** é a pasta com o `cenas.json`, a ficha de cada cena (`id`, `arquivo`,
`acabamento`, `janela`, `ilustra`); a do usuário fica em `videos/banco-de-cenas/`. O reel do
webm pronto escolhe a cena pelo `ilustra`, o que ela mostra, e a põe atrás do rosto, no trecho
em que a voz fala daquilo (`"fundo": "@../banco-de-cenas/<arquivo>"`; `fabrica-composicao`,
"O fundo atrás do rosto").

O pacote não traz cenas: o banco é dele. Sem o módulo Cenas de Cinema com IA, o banco são vídeos que
ele mesmo gravou, com a ficha escrita à mão; com o módulo, quem gera as cenas é o lote
(skill `fabrica-cinema`).

## As skills de edição

Esta skill diz como rodar a fábrica. O critério de edição mora em cinco skills ao lado
desta, na mesma pasta. Antes de escrever ou mexer num plano, leia a que cobre o que
você vai decidir:

| Skill | Decide |
|---|---|
| `fabrica-legendas` | qual legenda, duas letras, palavra marcada, zona segura do Instagram, quebra de linha |
| `fabrica-composicao` | tela dividida, cartão com a cabeça saindo, 40/60 com cena, o fundo atrás do rosto |
| `fabrica-movimento` | o que vira peça, no tempo da fala, uma ênfase por peça, tela nunca vazia |
| `fabrica-ritmo` | corte de silêncio, cortes e zoom, gancho no primeiro quadro, chamada só no fim |
| `fabrica-estilo` | tema claro ou tinta, trilha até o fim, capa, versão do YouTube, entrega |

O `GUIA-DE-PEDIDOS.md`, na raiz, traz o pedido pronto para cada tipo de vídeo, técnica e
etapa. Quando o usuário colar um deles, faça o que ele promete, nem mais nem menos.

## Regras

1. **Sempre `--seco` primeiro.** Mostre ao usuário a cadeia, o que custa e o tempo. Só renderize
   depois que ele confirmar.
   **Todo vídeo passa pelo storyboard antes do render final.** Sem o ok do usuário num
   storyboard visto, não renderize.
2. **Nada pago roda sozinho.** Voz, avatar e cena nova (dos módulos) viram passo que
   **cobra**: a fábrica para e imprime o comando. Quem decide gastar é o usuário: mostre o
   custo e espere o sim antes de rodar.
3. **Chave só no `.env.local`**, na raiz. Nunca imprima o valor de uma chave, e nunca abra o
   arquivo: nada de `grep`, `cat` nem `Read` nele. Para saber quais chaves estão preenchidas,
   só `uv run python tools/video-use/helpers/confere_env.py` ("preenchida" ou "vazia").
4. **O fundo atrás do rosto é do usuário:** a placa do lugar dele (`imagem.fundo`) ou as
   cenas do banco dele, trecho a trecho (`fundo`). Sem placa, `imagem.fundo` fica com a do
   exemplo (`exemplos/reel-editorial/fundo.png`, neutra) e todo trecho de rosto leva o seu
   `fundo` do banco.
5. **Ferramenta paga é de módulo.** Esta fábrica edita sem nenhuma: não peça chave de
   ElevenLabs, HeyGen nem Higgsfield, nem mande o usuário assinar, se a skill do módulo
   (`fabrica-clone`, `fabrica-cinema`) não estiver em `.agents/skills/`.
6. **Trilha sempre.** A do usuário (a da ElevenLabs Music, ou outra com licença) vai em
   `trilha.faixa`, com o caminho do arquivo. Sem a dele, uma das três de `exemplos/trilhas/`,
   pelo tom da fala: `lofi-calma`, `groove-leve` ou `animada` (CC0; a licença no `LEIA-ME.md`
   de lá). `"nenhuma"` só quando ele disser que põe a música pelo app do Instagram.
7. **Capa por último, perguntando.** Nada de capa antes do vídeo aprovado; então pergunte numa frase se
   ele tem ideia de frase ou de foto (passo 9) e faça pelo comando de um passo (`fabrica-estilo`,
   "Capa"). Exceção: no reel do webm pronto, o pedido "faz a capa" já é a resposta, e vale o bloco
   `capa` do plano (sem foto dele, um quadro do webm: `"foto": ["<o webm>", <segundo>]`).
8. Tipo de vídeo novo é **estilo novo** herdando de um que chega perto (`herda` no
   `ESTILOS` do `estilo.py`, ou no `marca/estilos.json` se for da marca do usuário),
   não script novo.

## Peças

O que vai por cima do vídeo (gancho, chip, painel, chamada) é **peça** de `tools/v2`.
O reel escolhe do cardápio: `uv run python tools/v2/v2.py cardapio`. Peça nova entra em `tools/v2/pecas/`
e no catálogo (`v2.py catalogo`), nunca como HTML solto na pasta do vídeo.

## Gasto

Cada vídeo come parte da semana do usuário no Claude ou no ChatGPT, e a maior parte vai em esperar e em olhar à toa.

- **Render e espera num comando só.** Rode o comando longo até o fim (no Claude Code, pelo `executor`) e
  não consulte o andamento de minuto em minuto: cada consulta paga a conversa inteira de novo.
- **O teste antes da imagem.** O `--seco`, os `AVISO` do `--storyboard` e os `CHECK` do fim do render medem
  o vídeo. Olhe uma imagem só quando eles não bastam.
- **Conferência é o `checks:` do fim.** Sem `CHECK` falhando, nada de imagem nem folha; com ele, só o quadro apontado.
- **Folha no lugar de quadro solto**, quando precisa olhar. `uv run python tools/economia/olhar.py <vídeo ou pasta de imagens>`
  junta os quadros numa folha (`folha1.jpg`) e escreve o `RESUMO.md`: leia os dois. Num arquivo grande,
  `uv run python tools/economia/mapa.py <arquivo>` mostra o que há em cada linha, e você lê só o trecho. No
  Claude Code, o porteiro (um hook de `.claude/settings.json`) já troca a leitura inteira por isso; no Codex,
  faça você.
- **Uma conversa por vídeo.** Entregou o vídeo, a próxima conversa é nova: a velha carrega tudo o que leu.

## Quando dá erro

Leia a mensagem: a fábrica recusa antes do primeiro comando e diz o campo que falta.
Corrija o plano e rode `--seco` de novo. Depois de um passo que já rodou, use
`--desde <etapa>` (`corte`, `render`, `desenho`, `composicao`, `trilha`, `entrega`)
para não refazer o que está em disco. Para conferir que a fábrica segue inteira:

```bash
uv run python tools/video-use/helpers/test_fabrica.py
```

Os finais saem em `videos/`, na pasta que o estilo manda (`estilo.py`, eixo `entrega`).

**`CHECK` no fim do render não é erro.** O vídeo já saiu; cada linha `CHECK <nome>` mede o
final (pico de áudio, quadro vazio, flash, tela parada). Tente uma vez o conserto que a linha
aponta, com `--desde <etapa>`. Se ficar, entregue o vídeo e diga ao usuário, numa frase e sem
número, o que ele vai notar e se dá pra postar. Nunca peça relatório nem Chamado por causa de
`CHECK`: o Chamado é só da conferência da instalação (`INSTALAR.md`).
