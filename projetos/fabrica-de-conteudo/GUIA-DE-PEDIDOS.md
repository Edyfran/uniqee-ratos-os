# Guia de pedidos

Abra o seu agente de IA dentro da pasta `fabrica-de-conteudo`, copie o pedido e troque o que
está entre `< >`. O agente escreve o plano, confere sem renderizar (o `--seco`), mostra o que
vai custar e só gasta depois do seu sim. Antes do vídeo final ele mostra o storyboard: cada
overlay numerado, com o quadro. Você corrige pelo número ("nº 4: tira") e só com o seu ok ele renderiza. O critério que ele segue está nas skills de edição,
em `.agents/skills/`.

## Para começar

```
/onboarding
```

No Codex, escreva `onboarding`. Uma página abre no seu navegador, com uma escolha por tela: o estilo,
as cores, as letras, o logo e a legenda, cada um com a prévia na hora. Leva uns 10 minutos. Cada escolha
fica salva sozinha, e o agente não precisa ficar esperando. No fim, volte à conversa e diga "terminei o
onboarding": o agente aplica tudo na fábrica. Aqui você não manda vídeo: ele vem depois, no seu pedido.

Prefere sem a página? Este pedido só prepara o computador:

```
Esta pasta é a Fábrica de Conteúdo com IA. Siga a seção "Primeira vez nesta
máquina" do INSTALAR.md, que está nesta pasta: instale o que faltar no meu
computador, rode a conferência até passar e me diga no fim o que fez. Se algo pedir
senha de administrador, me avise antes.
```

Sai: o computador pronto e o arquivo `.fabrica-ok` na pasta. Mais no `INSTALAR.md`.

```
confere os exemplos dos módulos sem gastar nada
```

Sai: com o Crie seu Clone de IA, a cadeia do reel editorial; com o Cenas de Cinema com IA, a do criativo
(`exemplos/`). As duas param no passo que cobra.

Os pedidos marcados "Módulo" pedem o módulo instalado (a skill dele em `.agents/skills/`).
Sem ele, o agente avisa e não pede chave.

## Os tipos de vídeo

### Reel editorial

Módulo: Crie seu Clone de IA (`fabrica-clone`).

```
faz um reel editorial de 30 segundos sobre <assunto>, com o meu avatar e a minha voz clonada. A palavra da chamada é <PALAVRA>
```

Sai: `videos/topo/<slug>.mp4`, 1080×1920. Painel em cima, o seu rosto num cartão embaixo,
a fala em duas letras, peças entrando com a fala e trilha. Precisa da voz clonada na
ElevenLabs, de um avatar seu na HeyGen treinado com fundo removível, da placa do seu look
(o fundo atrás do rosto) e de uma trilha. Cobra: a narração (ElevenLabs) e o rosto (HeyGen,
gerado pelo seu agente com os créditos do seu plano, depois do seu sim).

### Reel do vídeo que você já gerou

```
na pasta videos/<pasta> tem a minha voz e o vídeo do meu avatar que eu gerei na HeyGen. Edita esse vídeo pra reel: corta as pausas, põe legenda, arruma a tela e faz a capa
```

Sai: `videos/topo/<slug>.mp4` e a capa ao lado, 1080×1920. O mesmo molde do reel editorial,
com o rosto que você já tem: a fala em duas letras, o fundo atrás de você trocando com o que
a voz diz (as cenas do seu banco de cenas, em `videos/banco-de-cenas/`), o gancho no
primeiro quadro, a chamada no fim e trilha. Serve também o vídeo do celular exportado sem
fundo (webm). Não cobra nada: roda no seu computador.

### Reel com avatar, na voz que você gravou

Módulo: Crie seu Clone de IA (`fabrica-clone`).

```
transforma o áudio que eu gravei em <caminho> num reel com o meu avatar, legenda e b-roll
```

Sai: `videos/reels/<slug>.mp4`, com a legenda viral e a trilha. Antes da HeyGen, o áudio
passa pelo portão: as pausas saem, o nível é medido, e nada gera sem você ouvir e aprovar.
Cobra: o rosto (HeyGen).

### Reel do celular

```
corta o vídeo que eu gravei no celular em <caminho> e põe legenda
```

Sai: `videos/reels/<slug>.mp4`, com o silêncio cortado, a legenda viral queimada e, se você
mandar, b-roll por cima. Não leva trilha. Não cobra nada: roda no seu computador.

### Reel do celular, igual a uma referência

```
edita o meu igual a esta referência: <link do reel ou caminho do vídeo>. O meu vídeo é <caminho>
```

Exemplo:

```
edita o meu igual a esta referência: https://www.instagram.com/reel/<código>/. O meu vídeo é videos/meu-reel/gravacao.mov
```

O agente tira os quadros e a fala da referência, mede o corte, as pausas, o som e o motion (o
layout, as peças e os eventos por segundo), e escolhe o layout, a legenda e o estilo mais próximos
da fábrica: referência com tela dividida e peças vira o layout dividido, com as peças feitas do que
você disse. Edita o seu vídeo e entrega `videos/reels/<slug>.mp4` com uma folha lado a lado
(`videos/<slug>/referencia/lado-a-lado.png`): a referência em cima, o seu vídeo embaixo. Diz o que
ficou parecido, a densidade de motion dos dois e o que o kit não copia: o rosto, a marca, o texto e
a música dela, a tela gravada e a cena gerada que você não tem. Link só
de post público; de post privado, mande o arquivo. Não cobra nada: roda no seu computador.

### Criativo de cinema

Módulo: Cenas de Cinema com IA (`fabrica-cinema`).

```
faz um criativo de câmera escondida sobre <produto>, com cenas geradas na Higgsfield e narração na ElevenLabs
```

Sai: `videos/criativos/<slug>.mp4`. Voz em off sobre cenas do banco de cenas, cada cena no
trecho da fala que ilustra, com o acabamento de filmagem achada: `cctv`, `telejornal`,
`documentario`, `filmadora` ou `celular`. Para o feed, peça "a versão pro Reels". Antes de
gerar, o agente escreve com você o cartão de conceito. Cobra: as cenas (Higgsfield, uns
US$ 0,30 cada, com o preço perguntado antes) e a narração (ElevenLabs, do Crie seu Clone de IA; sem ele,
a voz é a sua, gravada).

### Vídeo longo do YouTube

Módulo: Kit de Edição para YouTube (`fabrica-youtube`).

```
edita o vídeo longo que eu gravei deitado em <caminho>: corta o silêncio e os erros, põe a trilha e me dá o pacote do YouTube
```

Sai: `videos/<slug>/<slug>.mp4`, 1920×1080, só com a fala: o silêncio sai sozinho, e erro e
repetição o agente acha no transcript e tira. A trilha fica embaixo da fala. Junto, em
`videos/<slug>/youtube/`: 3 títulos e 3 capas pro teste A/B do YouTube, a descrição com
capítulos e o Short em pé, tirado do mesmo vídeo. Não cobra nada: roda no seu computador. A
capa com IA é opcional e cobra na OpenAI, com o preço antes.

### Aula gravada

Módulo: Kit de Edição para YouTube (`fabrica-youtube`).

```
edita a aula que eu gravei: a tela no OBS em <caminho da tela> e eu no celular em <caminho do celular>, com uma palma no começo
```

Sai: `videos/<slug>/<slug>.mp4`, 1920×1080: a tela numa janela sobre o papel e você num
cartão ao lado, acertados pela palma, com o silêncio cortado e os cartões que explicam o termo
no tempo da fala. Não cobra nada: roda no seu computador.

### Aula narrada

Módulo: Kit de Edição para YouTube (`fabrica-youtube`) e Crie seu Clone de IA (`fabrica-clone`).

```
faz uma aula narrada com a minha voz clonada sobre a gravação de tela em <caminho>, a partir deste roteiro: <roteiro>
```

Sai: `videos/<slug>/<slug>.mp4`, 1920×1080: a tela de verdade, em blocos, com a sua voz clonada
lendo cada trecho do roteiro e os cartões no tempo da fala. Você não grava a voz. Cobra: a
narração (ElevenLabs), com o preço de cada bloco antes.

## As oito técnicas

### Do bruto ao pronto

```
corta o silêncio do vídeo <caminho> e tira as frases que eu errei ou repeti
```

Sai: o vídeo só com a fala. O silêncio sai sozinho; erro e repetição o agente acha no
transcript e tira como drop. No reel com avatar, a voz chega aparada antes de gerar o rosto.

### Motion explicativo

```
quando eu falar <a ideia ou o número>, mostra na tela com uma peça: contador, lista ou passos
```

Sai: uma peça da biblioteca (`tools/v2`) entrando no tempo da fala. No reel editorial.

### Recorte de fundo

```
de <início> a <fim>, tira o fundo de trás de mim e põe <xadrez | o painel | esta imagem: caminho>
```

Sai: o seu rosto recortado sobre outra coisa, só naquele trecho. Pede o avatar gerado com
fundo removível. No reel editorial.

```
põe a palavra <PALAVRA> grande, passando atrás de mim
```

Sai: a palavra-herói atrás de você, recortada no seu computador. Só no reel do celular, que
não troca de fundo.

### Inserção de imagens

```
mostra o print de <endereço da página> quando eu falar <frase>, e o logo da <ferramenta> no começo
```

Sai: a captura da página com grifo e o logo, no instante da frase. Só página pública, sem
login. No reel editorial. No reel do celular, um vídeo seu entra por cima como b-roll: `põe
<vídeo> por cima quando eu falar <frase>`.

### Ícones animados

```
põe um ícone animado em cada ideia do roteiro
```

Sai: sticker, contador, rabisco (seta, x, círculo), carimbo ou passos que viram ✓, entrando
quando a palavra é dita. No reel editorial.

### Legenda

```
põe a legenda de duas letras, uma palavra por vez
```

Sai: a fala em sans, uma ou duas palavras por vez, e o rótulo em serifa itálica. É a
legenda do reel editorial.

```
põe legenda com a palavra <PALAVRA> em destaque
```

Sai: a legenda viral, até quatro palavras por card, quebrada na pausa da fala, com a palavra
acesa. No reel do celular, no reel com avatar e no criativo.

### Cenas geradas por IA

Módulo: Cenas de Cinema com IA (`fabrica-cinema`).

```
gera <n> cenas de <câmera de segurança | plantão | documentário> pro criativo sobre <produto>
```

Sai: o lote. Primeiro o preço, perguntado à API sem gastar; com o seu sim, as cenas baixam
no banco, cada uma com a ficha. Você assiste cada cena e acerta o melhor trecho (a janela).
Cobra na Higgsfield.

### Seu avatar, sua voz

Módulo: Crie seu Clone de IA (`fabrica-clone`).

```
grava esse roteiro com o meu avatar e a minha voz clonada: <roteiro>
```

Sai: a narração na sua voz clonada e o vídeo do seu avatar, que o agente gera na HeyGen pela
conexão oficial dela, depois de dizer quanto gasta. A montagem segue sozinha. Cobra: a narração
(ElevenLabs) e o rosto (HeyGen, créditos do plano).

## Etapa por etapa

### Roteiro

```
escreve o roteiro de um reel editorial de 30 segundos sobre <assunto>, com gancho no primeiro quadro e a chamada "comenta <PALAVRA>" só no fim
```

Sai: a `narracao` do plano, escrita como se fala: sem sigla, sem marca de emoção, e só a
palavra da chamada em caixa alta. Não cobra.

```
escreve o cartão de conceito e os trechos de um criativo sobre <produto>
```

Sai: o cartão (a premissa, o quadro-chave, a regra, a mensagem) e os `trechos` do plano,
cada fala com a cena que a cobre. Não cobra.

### Voz

Módulo: Crie seu Clone de IA (`fabrica-clone`).

```
gera a narração do reel
```

Sai: `voz.wav` na pasta do vídeo, na sua voz clonada. Cobra na ElevenLabs, por caractere, no
máximo três gerações por vídeo. Clonar a voz você faz uma vez, no site da ElevenLabs.

```
confere o áudio que eu gravei em <caminho> antes de mandar pra HeyGen
```

Sai: o áudio aparado e medido pelo portão, que só libera depois que você ouvir. A conferência
de ouvido por IA é opcional e custa centavos (OpenRouter).

### Rosto

Módulo: Crie seu Clone de IA (`fabrica-clone`).

```
prepara o áudio do avatar
```

Sai: `avatar/geracao.wav`, só com os trechos de rosto, e o custo na HeyGen. Com o seu sim, o
agente sobe o áudio, gera o rosto sem fundo pelo MCP da HeyGen e baixa em `avatar/rosto.webm`; a
montagem segue. Cobra na HeyGen, nos créditos do plano, por minuto gerado.

```
liga a HeyGen em você
```

Sai: o passo a passo pra ligar a HeyGen no seu agente (o MCP oficial, por login, sem chave), no
app do Claude, no Claude Code ou no Codex. Uma vez só. Não cobra.

```
acha o meu look na HeyGen e guarda
```

Sai: os seus looks, pelo nome, e o `HEYGEN_LOOK` preenchido com o que você escolher. Precisa
da HeyGen ligada no agente. Não gera vídeo. A placa do look (o fundo atrás do rosto) a HeyGen
não entrega: o jeito de fazer está na skill `fabrica-clone`.

### Montagem

```
confere o plano sem renderizar
```

Sai: a cadeia de comandos e o que cada passo cobra. Nada roda.

```
pode renderizar
```

Sai: o final na pasta do estilo. No reel editorial, também uma folha de quadros
(`folha-1fps.png`) para conferir sem assistir.

```
refaz só a partir do desenho
```

Sai: o render de novo, sem refazer o que já está em disco. As etapas: corte, render,
desenho, composicao, trilha, entrega.

```
põe um efeito sonoro de whoosh quando entra o título e um ding no número
```

Sai: o vídeo com os sons onde você pediu. As animações já tocam os sons delas sozinhas; este
pedido é para o que você quiser a mais. Os nomes dos sons estão em `tools/v2/sfx/sfx.json`.

### Capa

```
faz a capa do reel com a minha foto <caminho>, título "<linha 1>|<linha 2>" e "<trecho>" em destaque
```

Sai: `videos/topo/<slug>/capa-nick.jpg`, 1080×1920, ao lado do reel editorial, com a sua foto
sem fundo, o título, o logo e dois ícones. Não cobra.

```
faz só uma capa, sem vídeo, com a minha foto <caminho>: título "<linha 1>|<linha 2>", "<trecho>" em destaque, "<ferramenta>" no topo e os ícones <mic> e <onda> nos lados. Usa a função capa_nick do tools/video-use/helpers/capa.py e salva em <pasta>/capa.jpg
```

Sai: `<pasta>/capa.jpg`, o mesmo JPEG de 1080×1920, para um vídeo que você editou fora da
fábrica. Os ícones: `mic`, `onda`, `claquete`, `filme`, `robo`, `rec` ou `cel`. Não cobra.

### Versão do YouTube

```
faz a versão do YouTube, com a chamada "o link tá na descrição"
```

Sai: `videos/topo/<slug>-yt.mp4`. O mesmo reel, com a última frase trocada e um cartão com
seta para baixo no lugar do "comenta". A frase nova cobra na ElevenLabs (Crie seu Clone de IA). Só no
reel editorial.

### Ajuste

```
no segundo <t>, <o que está errado>. Ajusta e refaz só o que mudou
```

Sai: o plano corrigido e o render refeito a partir da etapa que mudou.

## O que cobra

O corte, as peças, a legenda, a capa e a mixagem rodam no seu computador, de graça, e a
transcrição também, a menos que você ponha a chave da ElevenLabs no `.env.local`: aí ela vai para
a nuvem e gasta crédito da sua conta. Nos módulos, cobram a narração (ElevenLabs) e o rosto (HeyGen), no Crie seu Clone de IA, e as
cenas (Higgsfield), no Cenas de Cinema com IA; no Kit de Edição para YouTube, só a capa com IA (OpenAI), que é
opcional; a conferência de ouvido (OpenRouter) é opcional. Em
todo passo pago a fábrica para, mostra o comando e espera. A tabela de cada um está na skill
do módulo.
