# Reels · Azulejo com realidade aumentada · Semana do formando

Linha tradicional · Instagram · Reels de uns 25 segundos.
Produto: azulejo personalizado que vem com uma tag de QR code. Primeiro a pessoa escaneia o QR code
da tag; depois aponta a câmera pro azulejo, e aparece um vídeo da formanda com uma mensagem pra
professora.

**Objetivo:** alcance e compartilhamento (quem assiste manda pra amiga que vai se formar)
**Ideia:** o vídeo segue a professora fazendo os dois passos, a tag e o azulejo, até a formanda
aparecer falando com ela. O instante em que o vídeo começa a tocar em cima do azulejo é o que
segura quem está assistindo.

Em todo o vídeo: só mãos, bancada, prensa e peças. O vídeo da formanda que aparece no azulejo é
criado por IA, com uma pessoa fictícia (sem parecer com nenhuma aluna ou professora de verdade).
Ao postar, ligar o rótulo de IA nas configurações avançadas do Instagram.

---

## Gancho (primeiros 2 segundos)

Três opções de texto na tela pra abrir. Recomendo a primeira.

1. "Esse azulejo tem uma mensagem escondida"
2. "Aponte o celular e veja o que acontece"
3. "Ela não conseguiu dizer obrigada na formatura. Então fez assim"

---

## Roteiro

| tempo | o que aparece | texto na tela |
|---|---|---|
| 0–2s | azulejo no cavalete, com a tag em pé ao lado | "Esse azulejo tem uma mensagem escondida" |
| 2–5s | mão com o celular escaneia o QR code da tag | "Primeiro, o QR code da tag" |
| 5–8s | o celular sobe e aponta pro azulejo (filmado por trás do ombro, mostrando a tela) | "Depois, a câmera no azulejo" |
| 8–15s | na tela do celular, o vídeo da formanda toca em cima do azulejo, com a voz dela | (sem texto: deixar a voz da formanda falar) |
| 15–19s | mãos tirando o azulejo da prensa, revelando a arte | "Arte, foto e um vídeo só de vocês" |
| 19–22s | mão coloca a tag ao lado do azulejo pronto | "Um presente que fala com quem recebe" |
| 22–25s | azulejo e tag lado a lado, com o celular apontado e o vídeo tocando | "Encomende o seu · link na bio" |

**Áudio:** a voz da formanda é o centro do vídeo. Trilha suave bem baixa por baixo, que some
enquanto ela fala. Sem narração.

**Fala da formanda** (de 5 a 7 segundos):

```
Prô, a senhora acreditou em mim quando nem eu acreditava. Essa formatura também é sua. Obrigada por tudo.
```

---

## Capa

Azulejo com a tag ao lado e o celular apontado, com o vídeo aparecendo na tela.
Texto: **"O azulejo que fala"**, em Radio Canada Big.

---

## Legenda

Tem obrigado que não cabe num cartão. 🎓

Esse azulejo foi feito pra uma professora. Ela escaneia o QR code da tag que acompanha o presente, aponta a câmera do celular pro azulejo e aparece um vídeo da formanda com uma mensagem só pra ela.

Aqui na Uniqee, a gente une a arte personalizada com a realidade aumentada pra transformar o agradecimento em lembrança que fica na estante e pode ser vista de novo sempre que der saudade.

Vai se formar e quer homenagear quem esteve do seu lado? Chame a gente no WhatsApp pelo link da bio e encomende com antecedência.

Vídeo ilustrativo. No seu azulejo, a mensagem é gravada por você.

#presentedeformatura #formatura2026 #formandos2026 #presenteparaprofessora #azulejopersonalizado #realidadeaumentada #presentepersonalizado #uniqeepersonalizados

---

## Observações

- Pode sair como **Reels de teste** (Trial Reels), como os outros da semana.
- Sem preço, como o resto da semana. Se quiser divulgar um valor, me passe qual.
- O QR code que a IA desenha na tag é de enfeite e não abre nada. Se alguém tentar escanear pelo
  vídeo, não funciona. Se preferir um que funcione (levando pro WhatsApp, por exemplo), coloque o
  QR code real na tag antes de gerar a imagem base.

---

## Prompts pro Gemini (Veo)

Cada vídeo do Gemini tem até 8 segundos e já sai com som. Por isso cada cena é um prompt.
Os textos da tela entram depois, na edição (CapCut), e não no prompt: a IA erra letra.

**Ordem de trabalho**

1. Gerar a **imagem base** com o mockup do azulejo e a tag. Ela vai anexada nas cenas 1, 2, 3 e 6,
   pra o azulejo e a tag serem os mesmos em todas.
2. Gerar a **cena 4** (a formanda) e a **cena 3** primeiro: são as que mais importam, e o plano do
   Gemini limita quantos vídeos saem por dia.
3. Na cena 3, a tela do celular sai com um retângulo verde em cima do azulejo. No CapCut, a cena 4
   vai por cima dele com "Remover fundo › Chroma key".
4. A cena final (22–25s) reaproveita o fim da cena 3, mais aberta, mostrando a tag.

Se o vídeo sair deitado (16:9), pedir de novo reforçando "vertical 9:16", ou cortar no CapCut.

### Imagem base · anexar a tag (imagem 1) e o mockup do azulejo (imagem 2)

```
Use as duas imagens anexadas. Mantenha a segunda imagem do jeito que está: o azulejo com a arte "Prof, gratidão por tudo" no cavalete de madeira, sobre a bancada, com o ateliê desfocado ao fundo. Acrescente, em pé sobre a bancada, apoiada do lado direito do cavalete, a tag da primeira imagem impressa em papel cartão fosco, no formato vertical e bem menor que o azulejo, do tamanho de um cartão. Não mude nenhuma letra, cor ou desenho da tag nem do azulejo. No quadrado branco da tag, coloque um QR code preto simples. A tag recebe a mesma luz de janela da cena, com uma sombra suave na bancada. Fotografia realista, formato vertical 9:16, com espaço livre na bancada à frente das peças.
```

### Cena 1 · azulejo e tag (0–2s) · anexar a imagem base

```
Vídeo vertical 9:16, realista, a partir desta imagem. A câmera se aproxima bem devagar do azulejo no cavalete e da tag ao lado, sobre a bancada de madeira. Luz natural de janela, clima acolhedor de ateliê. Sem pessoas, sem texto novo na tela, sem música. Som ambiente baixo de um ateliê silencioso.
```

### Cena 2 · escaneando o QR code da tag (2–5s) · anexar a imagem base

```
Vídeo vertical 9:16, realista, a partir desta imagem, filmado por trás do ombro de uma mulher de uns 50 anos, sem mostrar o rosto dela. A mão dela, com uma aliança, entra no quadro segurando um celular e aproxima a câmera traseira da tag em pé ao lado do azulejo, apontando para o QR code. A tela do celular mostra o QR code em foco, com um quadrado de leitura em volta dele, e um leve toque de confirmação. A mão fica firme, com um movimento natural. Luz de janela suave. Sem música, sem texto novo na tela.
```

### Cena 3 · celular apontado pro azulejo (5–8s e 22–25s) · anexar a imagem base

```
Vídeo vertical 9:16, realista, a partir desta imagem, filmado por trás do ombro de uma mulher de uns 50 anos, sem mostrar o rosto dela. A mão dela, com uma aliança, segura um celular, sai da tag ao lado e sobe devagar até apontar a câmera traseira para o azulejo no cavalete. Na tela do celular aparece o azulejo e, por cima dele, um retângulo verde liso e uniforme, sem nada escrito. A mão para firme, com um leve movimento natural. Luz de janela suave. Sem música, sem texto na tela.
```

### Cena 4 · a formanda falando (8–15s)

```
Vídeo vertical 9:16, realista, com cara de vídeo gravado na câmera frontal do celular. Uma jovem brasileira de uns 23 anos, de beca preta de formatura, segurando o capelo nas mãos, olha direto para a câmera, sorrindo e emocionada, com os olhos marejados. Fundo desfocado de um salão de formatura com luzes quentes. Ela fala em português do Brasil, com voz suave e sotaque do Nordeste: "Prô, a senhora acreditou em mim quando nem eu acreditava. Essa formatura também é sua. Obrigada por tudo." Sem música, sem legendas, sem texto na tela.
```

### Cena 5 · saindo da prensa (15–19s) · anexar o mockup do azulejo

Essa dá pra filmar de verdade, na sua prensa, só com as mãos.

```
Vídeo vertical 9:16, realista, close nas mãos, sem mostrar rosto. Numa bancada de ateliê, mãos com luvas térmicas abrem uma prensa térmica plana e retiram um azulejo branco quadrado. Em seguida puxam devagar a folha de papel de sublimação de cima dele, revelando a arte da imagem anexada impressa no azulejo. Um vapor leve sobe. Luz natural, clima de feito à mão. Som do clique da prensa e do papel sendo puxado. Sem música, sem texto novo na tela.
```

### Cena 6 · a tag ao lado do azulejo (19–22s) · anexar o mockup do azulejo e a tag

```
Vídeo vertical 9:16, realista. O azulejo da segunda imagem está no cavalete de madeira sobre a bancada. Uma mão feminina, sem mostrar o rosto, coloca em pé ao lado dele a tag da primeira imagem, impressa em papel cartão, com um QR code preto no quadrado branco. Não mude as letras nem os desenhos da tag e do azulejo. A câmera faz um movimento lento de lado. Luz de janela suave, ateliê desfocado ao fundo. Sem música, som baixo do papel.
```
