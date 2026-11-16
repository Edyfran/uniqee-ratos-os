# Andamento · Loja Uniqee

## Onde está (2026-11-16)
Loja (lado do cliente) pronta em `loja/index.html`, com pagamento e frete simulados.
Painel de gestão, primeira parte, em `loja/painel/`: entrar com senha, pedidos (lista, detalhe com mockups, avançar etapa, anotações) e produtos (cadastrar com foto, editar, esconder, apagar).
Servidor em `servidor/` (Cloudflare Worker + banco D1 + arquivos R2): a loja lê os produtos e grava os pedidos nele; sem servidor (prévia da Ratoeira), a loja usa `loja/js/dados.js`.
Rodar aqui na VPS: `cd servidor && npm run banco` (primeira vez) e `npm run dev` (abre em 127.0.0.1:8787; senha do painel no `.dev.vars`, fora do git). Prints do painel em `prints/`.
Link de teste (só com login da Ratoeira): https://apps.srv2142624.hstgr.cloud/uniqee-loja/ e o painel em `/uniqee-loja/painel/`. Roda no Docker a partir de `../../playground/uniqee-loja/` (pasta de publicados da área, fora deste repositório); senha do painel no `.env` de lá. Depois de mexer no código: `sudo docker compose -p play-uniqee-loja up -d --build` naquela pasta.
Próximo passo: o Edyfran ver o painel e dizer o que falta; depois, clientes, orçamentos e financeiro no painel, e a compra de verdade (etapa 3).

## Pendências
- [ ] Modelos das coleções Sousa (brasão da pegada, T-Rex Doomsday) e Gospel: nome, foto, preço e tamanhos de cada camisa. A Gospel está vazia e mostra "modelos chegando".
- [ ] Edyfran navegar pela loja inteira e listar os ajustes (textos, fotos, ordem, opções).
- [ ] Revisar com contador ou advogado os textos de trocas, privacidade e termos (estão como rascunho).
- [ ] Confirmar opções dos produtos (tamanhos da camisa, acabamento da caneca, cores) que não deu pra ler do Brinderoz.
- [ ] Ver com contador ou advogado como vender online sem CNPJ e sendo servidor público (quem fica como titular, que dado aparece no site).
- [ ] Pedir ao Brinderoz pra tirar do rodapé o número de 11 dígitos que aparece como CNPJ.
- [ ] Criar conta de vendedor no Melhor Envio e conferir se o Mercado Pago está liberado pra receber.
- [ ] Fotos das peças lisas (ou gerar).
- [ ] Prints das telas do Brinderoz que o Edyfran usa e pedido de exportação dos dados.
- [ ] Painel: entrada por Face ID (passkey) no lugar da senha; clientes, orçamentos com PDF, estoque e financeiro.
- [ ] Levar a loja pra conta da Cloudflare do Edyfran (o link de teste é provisório).
- [ ] Decidir se o custo vem do PreçoArte digitado à mão ou importado.

## Feito
- 2026-11-16: servidor da loja (Worker + D1 + R2) e painel, primeira parte: entrada com senha, pedidos com etapa que o cliente vê, produtos com foto e "como se vende" (pronto, provador, WhatsApp). Testado de ponta a ponta: compra na loja, pedido no painel, etapa avançada aparece pro cliente, produto novo aparece na coleção, escondido some.
- 2026-11-15: todo card de coleção abre a página da coleção com os modelos (antes, Sousa e Gospel iam pro WhatsApp); Luan Santana entrou na coleção Sousa. Botão "Quero personalizar o meu" (abertura, menu Personalize e produtos prontos) leva à escolha da peça (caneca, azulejo, camisa) e daí ao provador.
- 2026-11-15: aviso de pouco contraste no provador (texto com cor parecida com o que está atrás; imagem com cor parecida com a da peça). Corrigida a foto da peça que não ficava parada ao rolar o provador no computador.
- 2026-11-15: decisões aplicadas no código: azulejo 15x15 a R$ 35,00; camisa de poliéster só branca (foto nova, sem miniaturas de cor); 4 camisetas com personagem ou pessoa famosa e a coleção Geek; FAQ, termos e aceite do provador sem a frase de que personagem não pode ser impresso.
- 2026-11-15: costas da camiseta com preço: pequena (28 x 10 cm) + R$ 15,00 e grande (28 x 35 cm) + R$ 25,00. Conta: filme DTF 30 x 100 cm a R$ 40 (R$ 0,40 por cm de altura), custo R$ 4 e R$ 14. Decidido pelo Edyfran.
- 2026-11-15: provador da camiseta no estilo da página de produto da Montink: foto realista (gerada pelo ChatGPT, originais em `base-camiseta/`) tingida na cor escolhida, fundo preto, frente e costas com arte própria, miniaturas por cor, botões de cor com nome, tamanhos em caixa.
- 2026-11-15: estrutura completa da loja: início, presentes com busca e filtros, página de produto (opções, texto, frete), provador integrado (caneca 3D, azulejo, camiseta) com carrinho, gaveta do carrinho, finalizar (dados, CEP pelo ViaCEP, frete simulado, Pix e cartão simulados), página do pedido com andamento, acompanhar pedido, orçamento em 6 passos com mensagem pro WhatsApp, páginas sobre, como comprar, trocas, privacidade e termos. Testado de ponta a ponta dentro da moldura da Ratoeira.
- 2026-11-15: catálogo da loja atual salvo em `migracao/` (21 produtos, preços, opções, fotos).
- 2026-11-15: vitrine v1 em `loja/index.html` (momentos, presentes com filtro, provador, azulejo RA, coleções, como funciona, orçamento, perguntas).
- 2026-11-15: provador com a paleta da loja atual; foto lida sem blob (funciona na moldura da Ratoeira).
- 2026-11-15: provador v1 (caneca 3D, camiseta, foto, texto, aviso de 300 dpi, termo de uso, arquivo de impressão).
- 2026-11-15: plano, etapas e escopo combinados (ver `contexto.md`).
