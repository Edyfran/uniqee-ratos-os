# Loja Uniqee (teste)

Link de teste da loja própria da Uniqee e do painel (`/painel/`), pedido pelo Edyfran em 2026-11-16.
O código é o de `projetos/loja-uniqee/` (loja em `loja/`, servidor em `servidor/`); esta pasta só sobe ele no Docker.

- Atualizar depois de mexer no código: `sudo docker compose -p play-uniqee-loja up -d --build`
- Senha do painel: no `.env` desta pasta (fora do git).
- Banco e fotos: no volume `play-uniqee-loja_dados` (pedidos de teste somem só se apagar o volume).
- Pagamento e frete continuam simulados.
