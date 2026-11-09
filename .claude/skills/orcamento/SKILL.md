---
name: orcamento
description: >
  Escreve a resposta de orçamento da Uniqee pro WhatsApp, pronta pra colar: a partir da mensagem
  ou do print do cliente e do valor que o Edyfran tirou do PreçoArte. Se faltar informação, escreve
  antes a mensagem perguntando ao cliente. Use sempre que o Edyfran chamar /orcamento ou disser
  "responde esse orçamento", "o cliente pediu orçamento", "monta a mensagem do orçamento", "como
  respondo esse cliente", "deu tanto no PreçoArte, manda pro cliente", ou mandar um print de
  WhatsApp com cliente pedindo preço de caneca, azulejo, camiseta ou outra peça.
---

# Orçamento no WhatsApp

O preço já vem calculado do PreçoArte. O que esta skill faz é transformar o pedido do cliente e esse
valor numa mensagem clara, completa e no tom da Uniqee, pra o Edyfran só copiar e colar.

## Antes de começar

- `_contexto/preferencias.md`: como falar com o Edyfran aqui no chat.
- O tom de voz da marca (pasta da marca, ver o mapa do `AGENTS.md`): é como a Uniqee fala com o
  cliente. Hoje: trata por "você", registro formal, acolhedor, nunca promete o extraordinário e
  nunca cita o nome do Edyfran (a mensagem fala como "a Uniqee" ou "a gente").

## Condições de sempre da Uniqee

- **Entrada:** 50% do valor pra começar; o restante na entrega ou retirada
- **Pagamento:** Pix
- **Prazo:** até 5 dias úteis
- **Entrega ou retirada:** a combinar com o cliente; entrega sem taxa

Se o Edyfran disser outra condição pra um caso específico, vale a dele naquele orçamento.

## Passo a passo

1. **Ler o pedido do cliente** (texto ou print) e separar: peça, quantidade, como quer a arte e,
   se disse, pra quando precisa.
2. **Valor:** é o Edyfran quem passa, vindo do PreçoArte. Se ele não passou, pedir. Nunca calcular
   nem estimar preço aqui.
3. **Faltou informação do cliente?** Escrever primeiro uma mensagem curta e gentil pedindo só o que
   falta (por exemplo: a foto em boa resolução, a frase, a data em que precisa). Entregar essa
   mensagem e parar ali até o cliente responder.
4. **Com tudo em mãos, escrever a resposta do orçamento:** cumprimento, o que foi pedido (peça,
   quantidade, arte, em poucas palavras), o valor total e, se for mais de uma unidade, o valor por
   unidade; as condições de sempre (50% de entrada via Pix, prazo, entrega sem taxa ou retirada) e
   um fechamento convidando a confirmar. Se o cliente precisa pra uma data que não cabe no prazo,
   avisar o Edyfran antes, em vez de prometer.
5. **Chave Pix:** não escrever chave nenhuma. Deixar o lugar marcado como `[chave Pix]` pro Edyfran
   colar a dele.

Jeito da mensagem: texto de WhatsApp, curto, em parágrafos pequenos, fácil de ler no celular.
Emoji com moderação (um ou dois, se combinar), sem exagero de exclamação, sem superlativo. Formal,
mas caloroso: é um presente pra alguém especial, e isso pode aparecer numa frase.

Entregar a mensagem num bloco fácil de copiar. Se fizer sentido, oferecer uma versão mais curta.

## Depois

- **Cliente aprovou e mandou a entrada:** oferecer registrar com o `/pedido`, já com os dados do
  orçamento (só falta conferir o contato e o prazo combinado).
- **Cliente achou caro:** ajudar o Edyfran a responder com respeito, mostrando o que está incluso.
  Desconto só se ele decidir; a skill não oferece por conta.

O orçamento em si não vira arquivo: quem guarda o que foi fechado é o pedido.
