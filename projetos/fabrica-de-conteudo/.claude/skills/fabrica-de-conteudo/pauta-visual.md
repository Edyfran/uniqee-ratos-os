# A pauta visual: a prova de cada batida

Você escreve o `visual.json` **depois do corte e da densidade**, lendo a fala cortada **uma vez**.
Uma **batida** é o trecho da fala que pede uma prova. Para cada uma, responda: o que o espectador,
de mudo, precisaria ver para acreditar nisso? Se a resposta é "nada, só a pessoa", a batida é
`rosto` (sem cartão). Frase que só repete a anterior não ganha batida nova.

## A tarefa

Entrada: **só a lista de frases com tempo** (`transcript.py frases <fala_cortada.json>`, uma linha `[início-fim] texto`),
mais a densidade (`intensa`, `media` ou `calma`). Saída: **um arquivo, `visual.json`**, no formato do fim deste texto.
Você não abre vídeo, não busca nada e não escolhe peça: escolhe a **prova**, e o código a transforma na peça da tabela.

## Mostrar, não dizer: a escada da prova

Pra cada batida, desça a escada e **pare no primeiro degrau que existe**:

1. **A mídia da própria fonte que a fala cita** (`origem: midia`, com a `url` da fonte). A foto de um post público do X (o código
   lê o JSON público do post, sem login), uma imagem do README do repositório, a imagem de capa do site (`og:image`). Se a fala
   cita um post, repositório ou site, **a imagem dele vem antes de qualquer desenho**. `n` escolhe qual imagem (0 é a primeira);
   `recorte` (`[x0, y0, x1, y1]`, fração da imagem) separa um pedaço, quando a foto traz o antes e o depois lado a lado.
   **A mídia de uma fonte já citada serve toda batida que fala da mesma coisa**, não só a primeira: se o vídeo já mostra a foto do post
   (batida 1), a batida que fala da TV com a tela inicial nova usa a mesma foto, com outro `recorte` (o "depois"). O validador
   **reprova** `i_tv` (`limpa` ou `instala`) como prova quando o vídeo já cita um post do X: a foto vai na prova, o `i_tv` na `alternativa`.
2. **O que o aluno mandar**: print, gravação, a tela dele (`origem: aluno` ou `arquivo`).
3. **Foto de licença livre** (`origem: busca_imagem`).
4. **A demonstração animada da biblioteca**: a coisa acontecendo na tela, desenhada com peças do kit (`origem: peca`): a TV
   perdendo os anúncios, o terminal digitando o comando, a linha que sobe, a grade que enche. **Desenho só quando não há imagem
   real**: um mockup desenhado no lugar da foto que o post já traz é erro.
5. **Texto**, só como último recurso, e com o `porque` escrito. O validador **reprova** mais de 1 painel de texto puro num vídeo
   de até 45 s (1 por 45 s acima disso). Texto num `rosto` (gancho, chamada final) não conta.

Imagem real entra **por peça**: antes e depois (`origem: par`), o cartão da `dividida`, ou a `r_print` na `cheia`. **Nunca crua em
tela cheia.** A `alternativa` de uma batida de mídia real é a demonstração (degrau 4), não texto.

Número dito vira **gráfico ou contador animado**, nunca só o algarismo. "50 mil estrelas" é a linha das estrelas subindo (ou o
número contando de 0 até 50 mil), não o texto "50 mil". **O gráfico e o contador duram a batida inteira**, nunca 1 s e parado:
não escreva `dl` nem `dc`, que deixam a peça usar o tempo da batida. Painel de texto com o que a fala já diz é o erro mais comum:
pergunte "o que eu mostro que a fala não precisa repetir?".

## Prever antes de render: a confiança de cada batida

Antes de entregar, **julgue cada batida: vai ficar bom?** O código calcula a confiança por regra (`visual.py`, função
`confianca`); você só precisa saber o que ela conta:

| confiança | o que é | exemplo |
|---|---|---|
| **forte** | a prova real da fonte que a fala cita, ou do aluno | `midia`/`url` de um post, repositório ou site citado; `aluno`/`arquivo`; `numero` com `github_repo` |
| **média** | uma demonstração que mostra **exatamente a ação dita** (você escreve em `casa` o que da peça é o que a fala diz) | `i_terminal` com o pedido que a fala conta, `d_grade` com o número dito |
| **fraca** | `texto`, **logo solto** (`marca`), foto livre genérica, ou demonstração sem `casa` (genérica) | "No *Claude*" com o logo; um painel com a frase da fala |

**Logo solto não é prova.** Logo só vale junto de uma ação (o terminal com o pedido, o antes e depois) e então a prova é a ação, não o logo.

Batida **fraca** não vai pra tela no escuro. Faça uma destas duas coisas:

1. **Melhore a prova** até virar média ou forte (veja "Fala sem fonte pública", abaixo).
2. **Pergunte ao aluno**: preencha na batida `"pergunta": {"x": "<o que ele pode ter: um print, um vídeo>", "demo": "<a demonstração concreta que você sugere>"}`.
   O `acha.py` junta tudo na **pergunta única** (no máximo 5 itens, com a dos prints), neste formato:

   > No trecho “agente de IA consegue fazer tudo isso” (0:12), o que você quer mostrar? 1) um print/vídeo seu de um pedido ao agente, 2) o terminal com “edita meu vídeo pra reel” e o Reel pronto, 3) um trecho do seu próprio vídeo, 4) deixa comigo

   Sem resposta (ou “deixa comigo”) entra a **melhor opção que não é texto**: por isso a `fonte` de uma batida perguntada é a demonstração
   (`animacao`), nunca `texto`, e o texto fica só na `alternativa`. O validador reprova a perguntada que cai em `texto`.

O validador **reprova** mais de **1 batida fraca sem pergunta por 45 s** de vídeo (logo solto conta como fraca). Mais de 5 perguntas não cabem:
as 5 de maior tempo contam; melhore as outras.

**A `casa` só conta se a peça mostra a AÇÃO exata da frase**, não o assunto dela. O código confere o que dá (a peça tem de repetir
alguma palavra da fala; senão a batida cai pra fraca), e você confere o resto. Duas casas falsas:

- Fala: "a tua produção ainda tá parada, esperando teu editor responder". `i_terminal` com `claude "edita meu vídeo pra reel"` e
  `casa: "o pedido de edição"`. A frase é sobre **esperar**, o terminal mostra **pedir**: é decoração, não prova. Fraca.
- Fala: "dá pra fazer no Claude e no ChatGPT". Outro `i_terminal` com `rot: "ChatGPT"` e um comando inventado, `casa: "o produto que
  a fala nomeia"`. O nome do produto no rótulo não faz o que a fala diz. Fraca.

Casa verdadeira: fala "desativou 25 pacotes inúteis" e `i_terminal` com `claude "desative os pacotes inúteis"` e `n: 25`: o comando e o
número são os da fala.

## Variedade e prova real (regras do `visual.py`)

- **O mesmo tipo de peça** (a `peca` da biblioteca: `i_terminal`, `d_grade`...) **no máximo 2 vezes seguidas e em 40% das batidas** (a
  rodada de 21/10 trouxe 5 terminais seguidos num vídeo de celular). Troque por outra peça, por print real, ou pelo antes×depois.
- **Com menos de 30% das batidas com prova forte (real), a pergunta ao aluno é obrigatória**: preencha `pergunta` em pelo menos 3
  batidas sem prova forte (até 5 itens no vídeo). Em vez de marcar tudo "média" e não perguntar, pergunte. A Fábrica põe sozinha em
  cada item a opção forte: **o antes×depois do próprio vídeo do aluno** (o bruto × o editado, que ela já tem), no formato da tabela
  "Fala sem fonte pública".
- **O vídeo de 8 s ou mais termina em `rosto` de pelo menos 2,8 s**: é onde entra a chamada final (`g_comenta`, que a proposta de
  movimento põe). Se a fala não traz a palavra e a promessa, pergunte ao aluno numa frase; não invente.
- **Carimbo e palavra gigante não levam negação** ("SEM EDITAR", "NÃO"): o leitor entende o contrário. Use a palavra forte da frase.

## Fala sem fonte pública

Quando a fala não cita post, site nem repositório, não há “fonte” pra buscar. Não escreva a frase na tela: ache o padrão.

| a fala diz | a prova | como escrever | exemplo |
|---|---|---|---|
| benefício ou resultado (“fica pronto em minutos”, “sem editor”) | **o antes×depois do PRÓPRIO vídeo do aluno**: o bruto × o editado (a Fábrica tem os dois) | `par` com `arquivo` nas duas pontas: o quadro do bruto (`ffmpeg -ss <t> -i <bruto> -frames:v 1 antes.png`) e o do rascunho (`_trabalho/.../rascunho/*.mp4`). Forte | `{"origem":"par","antes":{"origem":"arquivo","caminho":"antes.png"},"depois":{"origem":"arquivo","caminho":"depois.png"}}` |
| “o agente edita / faz X” | **a demonstração da ação**: o terminal com o pedido, e o resultado do aluno como segunda batida (antes×depois acima) | `i_terminal` com `cmd` = o pedido que a fala conta, `casa` = “o pedido que a fala conta”. Média | `{"origem":"peca","peca":"i_terminal","q":{"cmd":"claude \"edita meu vídeo pra reel\"@0.3"}}` |
| dor ou situação (“produção parada esperando editor”) | algo que **mostra** a situação: o próprio bruto parado, ou uma demonstração com o número da dor | `d_linha`/`d_grade` com o número dito; ou **pergunta** (“um print seu de ...”) | `pergunta: {"x":"a pasta de brutos esperando edição","demo":"a grade de vídeos parados enchendo"}` |
| nomeia produto (“no Claude e no ChatGPT”) | **a ação com o produto**, não o logo: o terminal/o chat dele rodando o pedido | `i_terminal` com `rot` = o nome do produto e o pedido; o logo sozinho é fraca | `{"origem":"peca","peca":"i_terminal","q":{"rot":"Claude Code","cmd":"claude \"edita meu vídeo\"@0.3"}}` |
| chamada, gancho, virada | `rosto`, sem cartão | | |

O kit hoje **não tem peça de celular nem de linha do tempo** para a pauta (o validador só aceita `i_terminal`, `i_tv`, `d_grade`, `d_linha`).
O “Reel aparecendo” vem do vídeo do aluno (`par`/`arquivo`), não de uma peça.

**Animação inteira.** Toda peça termina a animação **pelo menos 0,5 s antes do fim da batida** (o espectador vê o fim, depois o corte).
O `acha.py` acelera a animação até caber (`dc`, `dl`, `t_marca`, o ritmo do terminal); se nem assim cabe, imprime e põe no storyboard
“animação não termina: batida nº X”. Resposta: dê mais tempo à batida (um terminal com 25 pacotes pede uns 6 s) ou tire o número.

## A tabela de provas

Cada linha: o que a fala diz, a prova real (degraus 1 a 3), a demonstração da biblioteca (degrau 4) com os parâmetros dela, um exemplo.
Os parâmetros de cada peça são o contrato dela (`python tools/v2/v2.py info <peca>`). Peças que o kit leva pra demonstrar:
`i_terminal`, `i_tv`, `d_grade`, `d_linha`; e as de apoio `e_dividida` (o painel em cima, na `dividida`) e `r_print` (o print em tela
cheia: janela, zoom na frase e marca). Print **nunca** vai cru em tela cheia: a `cheia` de um print é sempre a `r_print`.

| a fala diz | prova real (`fonte`) | demonstração da biblioteca (`origem: peca`) | exemplo |
|---|---|---|---|
| cita um post, site, repositório, prompt | `print`: a imagem da fonte (`origem: midia`, `url`, `n`) ou a página (`origem: url`, `url` que você acha na pesquisa, `frase` a grifar, `ancora`) | (não há: a imagem é a prova) | `{"origem":"midia","url":"https://x.com/fulano/status/123"}` · `{"origem":"url","url":"https://github.com/a/b","frase":"Quick start","ancora":"Quick start"}` |
| um comando, um pedido ao agente, "um comando só" | `demo`: `origem: aluno` ou `arquivo` (o terminal dele) | `i_terminal`: `cmd` (`texto@segundo;texto@segundo`), `rot` | `{"origem":"peca","peca":"i_terminal","q":{"cmd":"claude \"volte tudo como era\"@0.3"}}` |
| "desativou 25 pacotes", "removeu N coisas" | `demo`: o terminal dele | `i_terminal` com `n` e `nrot`: a grade desliga um a um e o contador sobe até `n` | `{"origem":"peca","peca":"i_terminal","q":{"cmd":"claude \"desative os pacotes inúteis\"@0.3","n":25,"nrot":"pacotes desativados"}}` |
| a TV, a tela, o aparelho mudando (anúncio some, tela limpa aparece, app instalado) | `antes_depois` (`origem: par`): as fotos do post citado (`midia` com `recorte` do antes e do depois), ou duas telas dele | `i_tv`: `modo=limpa` (anúncio some), `modo=instala` (tela inicial nova), `modo=compat` (selos `sel=Android TV;Google TV`); `rot`, `antes`, `depois`, `tit`, `t_troca` | `{"origem":"par","antes":{"origem":"midia","url":"https://x.com/a/status/1","recorte":[0.04,0.3,0.46,0.73]},"depois":{"origem":"midia","url":"https://x.com/a/status/1","recorte":[0.515,0.3,0.96,0.73]}}` (a demonstração `i_tv` vai na `alternativa`) |
| "mais de 400 modelos", "dezenas de lojas": uma quantidade de coisas iguais | (a lista real, em print) | `d_grade`: `n`, `suf`, `rot`, `cel` (cartões de amostra), `ic` (`tv`, `app`, `ponto`) | `{"origem":"peca","peca":"d_grade","q":{"n":400,"suf":"+","rot":"modelos de TV","cel":96}}` |
| um número que cresce (estrelas, seguidores, vendas) | `numero` com `github_repo` (o código lê o histórico público do star-history e desenha a linha crescendo a batida inteira, rótulo “estrelas no GitHub”); senão `de` com a URL da fonte | `d_linha`: `pts` (os pontos, da fonte), `x`, `rot`, `pre`, `suf`, `selo`; sem série, o `numero` vira contador subindo | `{"origem":"numero","valor":"50","sufixo":"mil","rotulo":"estrelas no GitHub","github_repo":"a/b","de":"API do GitHub"}` |
| diz um número solto (ano, preço, prazo) | `numero`, `de: "fala"` | contador do `numero`: sobe de 0 até o valor dito | `{"origem":"numero","valor":"400","sufixo":"+","rotulo":"modelos","de":"fala"}` |
| nomeia um produto ou empresa | `marca`: `origem: marca`, `nome` (o logo) | (o logo é a prova) | `{"origem":"marca","nome":"GitHub"}` |
| fala de uma coisa que se vê (o Android TV, o Google TV) | `print` com `origem: midia` e a `url` do site oficial (a imagem de capa mostra a tela de verdade), ou `busca_imagem` (foto de licença livre) | `i_tv` ou `d_grade`, se for tela ou conjunto | `{"origem":"midia","url":"https://tv.google/"}` |
| não há prova possível | `texto`: `texto` (`*grifo*` vira marcador), `porque`, `tag` opcional | (esgotou a escada) | `{"tipo":"texto","texto":"Comenta *TV*","porque":"chamada final"}` |
| gancho, virada, chamada final | `layout: rosto`, sem cartão | | idem |

`dividida` = cartão em cima com o visual e a pessoa recortada embaixo (prova pequena, que se lê rápido; a demonstração toca dentro
do painel). `cheia` = o visual na tela toda, sem a pessoa (prova que precisa de tela: terminal, lista, grade, antes e depois). `rosto` =
a pessoa sozinha. O `tipo` de uma demonstração da biblioteca é `animacao` (ou `demo`, se mostra um comando).

## Regras

1. **Toda batida que depende de rede ou do aluno leva `alternativa`**: `{"tipo": "texto", "layout": ..., "texto": "..."}`
   (`tag` opcional: "CITAÇÃO · @fulano" para frase de tweet). É o que entra se o visual não vier. A validação reprova sem ela.
2. **O terminal é demonstração, não prova.** `i_terminal` mostra **os comandos** que a fala conta e nada que ela não disse: sem
   saída, sem lista de pacotes, sem IP, sem número que ninguém falou (o `25` do contador só entra se a fala disse 25). A prova de
   verdade do terminal é a tela do aluno (`aluno`/`arquivo`), e `tela_aluno` só vem dele. Na `alternativa` de uma batida que depende de
   rede ou do aluno, prefira `{"tipo":"animacao","layout":...,"fonte":{"origem":"peca",...}}` a um painel de texto.
3. **Sem prova inventada.** Número vem da fala ou de uma fonte; nunca seu.
4. **Densidade** (a gravada em `movimento.py ler`): vão máximo entre mudanças, intensa 2 s, média 3,5 s, calma 6 s. Batida
   mais longa que o vão diz em `muda` o que muda por dentro ("rola", "zoom no grifo"). Batida alvo: intensa 1,5 a 3,5 s.
   Pelo menos 80% do tempo com prova; nunca 3 `cheia` nem 3 `dividida` seguidas; dois `cheia` seguidos somam menos de 7 s.
5. **Âncora na fala:** `t0` e `t1` são a palavra dita, `{"palavra": "Wi-Fi", "n": 1}` (a n-ésima vez), não segundos cravados.
6. **Uma prova por batida.** Duas provas na mesma frase viram duas batidas.

## O exemplo-ouro (a fala de um vídeo de 46 s, "limpei a TV com o Claude Code")

```json
{"versao": 1, "densidade": "intensa", "batidas": [
 {"id": 1, "t0": {"palavra": "Tem", "n": 1}, "t1": {"palavra": "tirando", "n": 1},
  "fala": "Tem gente limpando a própria TV com o Claude Code",
  "prova": "a TV dele antes (com anúncio) e depois (limpa), as fotos do post", "tipo": "antes_depois", "layout": "dividida",
  "fonte": {"origem": "par",
            "antes": {"origem": "midia", "url": "https://x.com/gathint/status/2111379569030939102", "recorte": [0.04, 0.30, 0.46, 0.73]},
            "depois": {"origem": "midia", "url": "https://x.com/gathint/status/2111379569030939102", "recorte": [0.515, 0.30, 0.96, 0.73]}},
  "alternativa": {"tipo": "animacao", "layout": "dividida",
                  "fonte": {"origem": "peca", "peca": "i_tv", "q": {"modo": "limpa", "rot": "sua TV", "antes": "COM ANÚNCIO", "depois": "SEM ANÚNCIO"}}}},
 {"id": 2, "t0": {"palavra": "Começou", "n": 1}, "t1": {"palavra": "Ele", "n": 1},
  "fala": "começou quando um cara no X passou o modelo da TV pro Claude Code",
  "prova": "o tweet dele", "tipo": "print", "layout": "dividida",
  "fonte": {"origem": "url", "url": "https://x.com/gathint/status/2111379569030939102"},
  "alternativa": {"tipo": "texto", "layout": "dividida", "texto": "Um cara no X passou o *modelo da TV* pro Claude Code", "tag": "CITAÇÃO · @gathint"}},
 {"id": 3, "t0": {"palavra": "Ele", "n": 1}, "t1": {"palavra": "ainda", "n": 1},
  "fala": "ele achou a TV no Wi-Fi e desativou 25 pacotes",
  "prova": "o pedido no terminal e os 25 pacotes sendo desligados um a um", "tipo": "animacao", "layout": "cheia",
  "casa": "o pedido de achar a TV e desativar os pacotes, e o 25 que a fala diz",
  "fonte": {"origem": "peca", "peca": "i_terminal", "q": {"cmd": "claude \"ache a minha TV no Wi-Fi\"@0.3;claude \"desative os pacotes inúteis\"@1.8", "n": 25, "nrot": "pacotes desativados"}},
  "muda": "os pacotes são desligados um a um e o contador sobe até 25"},
 {"id": 4, "t0": {"palavra": "ainda", "n": 1}, "t1": {"palavra": "isso", "n": 2},
  "fala": "e ainda montou uma tela inicial nova do zero",
  "prova": "a TV com a tela inicial nova, a foto do 'depois' do mesmo post", "tipo": "print", "layout": "dividida",
  "fonte": {"origem": "midia", "url": "https://x.com/gathint/status/2111379569030939102", "recorte": [0.515, 0.30, 0.96, 0.73]},
  "alternativa": {"tipo": "animacao", "layout": "dividida",
                  "fonte": {"origem": "peca", "peca": "i_tv", "q": {"modo": "instala", "rot": "tela inicial", "antes": "INSTALANDO", "depois": "PRONTA"}}}},
 {"id": 5, "t0": {"palavra": "isso", "n": 2}, "t1": {"palavra": "cinquenta", "n": 1},
  "fala": "virou um repositório grátis no GitHub",
  "prova": "a página do repositório", "tipo": "print", "layout": "dividida",
  "fonte": {"origem": "url", "url": "https://github.com/Gathin23/cleanyourtv", "frase": "Quick start", "ancora": "Quick start"},
  "alternativa": {"tipo": "texto", "layout": "dividida", "texto": "Virou um repositório *grátis* no GitHub"}},
 {"id": 6, "t0": {"palavra": "cinquenta", "n": 1}, "t1": {"palavra": "É", "n": 1},
  "fala": "50 mil estrelas",
  "prova": "as estrelas subindo, no histórico real do repositório", "tipo": "numero", "layout": "cheia",
  "fonte": {"origem": "numero", "valor": "50", "sufixo": "mil", "rotulo": "estrelas no GitHub", "github_repo": "Gathin23/cleanyourtv", "de": "API do GitHub"}},
 {"id": 7, "t0": {"palavra": "Então", "n": 1}, "t1": {"palavra": "aqui", "n": 1},
  "fala": "então, se quiser testar, comenta TV aqui embaixo",
  "prova": "chamada final: a pessoa", "tipo": "texto", "layout": "rosto",
  "texto": "Comenta *TV*", "porque": "chamada final, a prova é a própria pessoa"}
]}
```

Nenhuma batida é só texto: a foto da TV, o terminal e o gráfico mostram o que a fala conta. A validação confere tudo isso.

## O formato exato do `visual.json` (saída)

`{"versao": 1, "densidade": "<a gravada>", "batidas": [ ... ]}`. Cada batida, todos estes campos:

- `id` (1, 2, 3…), `t0` e `t1`: `{"palavra": "<palavra da fala>", "n": <qual vez ela aparece>}` (ou segundos do vídeo cortado)
- `fala`: a frase; `prova`: em uma frase, o que isto prova; `tipo` (`print`, `marca`, `numero`, `antes_depois`, `demo`, `animacao`, `tela_aluno`, `texto`) e `layout`: da tabela; `fonte`: da tabela
- `alternativa`: `{"tipo": "texto", "layout": "<o mesmo ou outro>", "texto": "...", "tag": "..."}` (obrigatória quando a fonte
  depende de rede ou do aluno: é o que entra se o visual não vier; `tag` só em citação)
- `casa` (batida de demonstração): em uma frase, o que da peça é exatamente o que a fala diz. Sem ele a demonstração é fraca
- `pergunta` (batida fraca): `{"x": "...", "demo": "..."}` — vira item da pergunta única; no máximo 5 no vídeo
- `muda` (quando a batida passa do vão da densidade): o que muda por dentro. Só `texto` leva `texto` e `porque`.

## O passo, em ordem

1. `fala_cortada.json` do rascunho do storyboard (`find videos/<slug> -name fala_cortada.json`) e
   `uv run python tools/video-use/helpers/transcript.py frases <fala_cortada.json>`: leia **uma vez**.
2. Escreva `videos/<slug>/visual.json` (ao lado do `reel.json`; a fábrica o acha sozinha).
3. **Um comando valida e busca:**

   ```bash
   uv run python tools/video-use/helpers/acha.py videos/<slug>/visual.json --fala <fala_cortada.json> --trab videos/<slug>/_trabalho
   ```

   Se reprovar, ele lista o que corrigir: corrija e rode de novo. Se achar tudo, não há o que perguntar.
   Se faltar tela do aluno ou houver batida fraca com `pergunta`, ele imprime **a pergunta única**, pronta.
4. **Faça essa pergunta ao aluno, uma vez, de uma vez** (no máximo 5 itens, cada um com a queda se ele não tiver).
   Ele manda os arquivos ou diz "não tenho". Para cada arquivo, troque a `fonte` da batida por
   `{"origem": "arquivo", "caminho": "<o arquivo>"}`. Para o que ele não tem, não faça nada: a `alternativa` já entra.
   Rode o `acha.py` de novo (a rede vem do cache). **Nunca pergunte em rodadas.**
   Resposta 1 (o aluno manda arquivo): `fonte` vira `arquivo`. Resposta 2: a demonstração sugerida já está na batida. Resposta 3: o
   quadro do vídeo dele (`par`/`arquivo`). Resposta 4 ou nada: fica a `fonte` da batida (a melhor opção que não é texto).
5. Rode o `--storyboard` de novo: a proposta de movimento só completa os vãos que a pauta não cobriu.
