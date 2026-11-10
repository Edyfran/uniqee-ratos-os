---
name: pedido
description: >
  Registra e acompanha os pedidos da Uniqee que ficam fora do Brinderoz: um arquivo por pedido,
  com cliente, contato, peça, quantidade, arte, valor, sinal e prazo. Também lista o que está em
  aberto, o que vence e quanto falta receber, e atualiza a situação ou os pagamentos. Use sempre que
  o Edyfran chamar /pedido ou disser coisas como "registra esse pedido", "fechou pedido", "novo
  pedido", "anota esse pedido", "quais pedidos estão em aberto", "o que vence essa semana", "quanto
  falta receber", "o pedido da Maria ficou pronto", "a cliente pagou o restante", "entreguei o
  pedido", ou mandar um print de conversa do WhatsApp com um pedido fechado.
---

# Pedido · registro e acompanhamento

Muitos pedidos da Uniqee não entram no Brinderoz e, até agora, não ficavam anotados em lugar
nenhum. Esta skill é esse caderno: cada pedido vira uma linha no banco **Pedidos Uniqee** do Notion
(onde o Edyfran acompanha) e, como cópia, um arquivo na pasta `pedidos/`. Dá pra saber a qualquer
hora o que está pendente, o que vence e quanto ainda falta receber.

O endereço do banco está nas integrações (linha do Notion). O Notion é a fonte principal; o arquivo
é a cópia. Os dois mudam juntos: registrou, atualizou ou arquivou num, faz no outro.

A skill não precifica. O preço vem do PreçoArte; aqui só se registra o valor combinado.

## Antes de começar

Ler `_contexto/preferencias.md`: é o jeito de falar com o Edyfran (acolhedor, formal, com o
linguajar nordestino, sem gíria e sem palavra típica de IA). Valores sempre em R$ com vírgula
(R$ 45,90) e datas no formato brasileiro na conversa (15/11/2026). No arquivo, data é AAAA-MM-DD.

Registrar pedido é pedido explícito do Edyfran, então salva na hora, sem esperar o `/atualizar`.

## Qual modo usar

Pelo que ele pediu:
- trouxe um pedido novo (texto, print, "fechou com fulano") → **registrar**
- quer saber o que tem pendente, o que vence, quanto falta receber → **listar**
- algo mudou num pedido que já existe (pagou, ficou pronto, entregou, mudou o prazo) → **atualizar**

Se não der pra saber, pergunta numa linha.

## Registrar

1. **Extrair o que veio.** O pedido chega do jeito que vier: texto solto, print da conversa do
   WhatsApp, áudio transcrito. Tirar dali os oito campos:
   - **cliente** (nome)
   - **contato** (telefone ou @)
   - **peça** (caneca, azulejo 15x15, camiseta...)
   - **quantidade**
   - **arte** (descrição curta: foto do casal com a frase tal, tema Dia das Mães...)
   - **valor** total combinado
   - **pago** (sinal já recebido; zero se ainda não pagou nada)
   - **prazo** de entrega

2. **Perguntar só o que faltou**, tudo numa mensagem só, pra não ficar no vai e vem. Não inventar
   campo nenhum: se o print não mostra o telefone, pergunta. Prazo relativo ("sexta que vem",
   "pro Dia das Mães") vira data absoluta, e a data calculada aparece no resumo pra ele conferir.

3. **Mostrar o resumo e confirmar** antes de salvar. Um resumo curto, com o que falta receber já
   calculado (valor menos pago). Pedido com mais de uma peça (ex.: 2 canecas e 1 azulejo) é um
   pedido só: a peça lista as duas coisas e o valor é o total.

4. **Salvar** em `pedidos/AAAA-MM-DD-<primeiro-nome>-<peca>.md`, com a data de hoje, tudo em
   minúsculas, sem acento, palavras separadas por hífen. Exemplo: `pedidos/2026-11-08-maria-caneca.md`.
   Se o nome já existir, acrescentar `-2`, `-3`. Formato do arquivo:

   ```markdown
   ---
   cliente: Maria Souza
   contato: (83) 99999-0000
   peca: Caneca
   quantidade: 2
   arte: Foto da família com a frase "Vó, a senhora é nosso tesouro"
   valor: 90.00
   pago: 45.00
   prazo: 2026-11-15
   situacao: aberto
   registrado: 2026-11-08
   ---

   ## Histórico
   - 2026-11-08 · registrado · sinal de R$ 45,00

   ## Observações
   ```

   Valores no arquivo usam ponto e duas casas (`90.00`), pra soma sair certa depois. Situação começa
   em `aberto`. Observações recebe qualquer detalhe que não coube nos campos (cor da alça, embalagem
   de presente, retirada ou entrega).

5. **Cadastrar no Notion**, no banco Pedidos Uniqee: Cliente, Contato, Peça, Quantidade, Arte,
   Valor, Pago, Prazo, Registrado e Situação `Aberto` (o "Falta receber" o próprio Notion calcula).
   No corpo da página, as mesmas seções `## Histórico` e `## Observações` do arquivo. Se o Notion
   falhar, o arquivo fica salvo do mesmo jeito: avisar e oferecer tentar de novo.

6. **Fechar** com uma linha dizendo onde salvou (link do Notion e arquivo) e quanto falta receber.

## Listar

Consultar o banco Pedidos Uniqee no Notion (situação diferente de Entregue e Cancelado). Se o
Notion não responder, ler os arquivos `.md` de `pedidos/` (sem entrar em `pedidos/entregues/`) e
avisar que a lista veio da cópia. Se os dois divergirem, avisar qual pedido está diferente. Com base
na data de hoje, mostrar:

- **Atrasados:** prazo já passou e a situação não é `entregue`. Vêm primeiro, bem destacados.
- **Vencem nos próximos 7 dias**
- **Os demais em aberto**, por prazo

Cada pedido numa linha: cliente, peça e quantidade, prazo, situação e quanto falta receber. No fim,
o **total a receber** (soma de valor menos pago de todos). Se ele pediu algo mais específico
("o que vence essa semana", "quanto falta receber"), responder só aquilo.

Sem nenhum pedido em aberto: dizer isso em uma linha.

## Atualizar

1. Achar o pedido pelo que ele disse (nome do cliente, peça). Se tiver mais de um que serve,
   mostrar as opções e perguntar qual.
2. Mudar o que for preciso no cabeçalho:
   - **pagamento:** somar no `pago`. Se passar do valor, avisar antes de salvar.
   - **situação:** `aberto` → `em producao` → `pronto` → `entregue`
   - **prazo** ou qualquer outro campo que mudou
3. Acrescentar uma linha no **Histórico** com a data e o que mudou
   (`- 2026-11-12 · pagou R$ 45,00 · quitado`). O histórico só cresce: nunca reescrever linha antiga.
4. Fazer a mesma mudança na página do pedido no Notion (propriedades e linha no Histórico). No
   Notion, a situação usa as opções Aberto, Em produção, Pronto, Entregue e Cancelado.
5. Ao virar `entregue`, mover o arquivo pra `pedidos/entregues/` (criar a pasta se não existir).
   No Notion, só muda a situação pra Entregue. Arquivar, nunca apagar. Se ainda falta receber,
   avisar: entregou, mas está devendo R$ X.
6. Confirmar em uma linha o que mudou.

## Cuidados

- Os arquivos têm nome e telefone de cliente. A pasta `pedidos/` fica fora do git (está no
  `.gitignore`), o banco do Notion fica privado, e nada daqui vai pra post, página ou qualquer
  coisa que saia pra fora.
- Nunca apagar arquivo de pedido. Pedido cancelado continua na pasta com `situacao: cancelado` e
  uma linha no histórico explicando; aparece na lista só se ele pedir.
- Conta de dinheiro feita com cuidado: conferir a soma antes de mostrar.
