-- Banco da loja Uniqee (D1). Produto e pedido guardam o objeto inteiro em JSON,
-- no mesmo formato que a loja usa em js/dados.js e na finalização da compra.

CREATE TABLE IF NOT EXISTS produtos (
  id TEXT PRIMARY KEY,
  dados TEXT NOT NULL,          -- nome, preço, foto, categoria, coleção, como se vende...
  ativo INTEGER NOT NULL DEFAULT 1,  -- 0 = escondido da loja
  ordem INTEGER NOT NULL DEFAULT 0,
  atualizado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
  codigo TEXT PRIMARY KEY,
  criado TEXT NOT NULL,
  email TEXT NOT NULL,
  etapa INTEGER NOT NULL DEFAULT 0,
  total REAL NOT NULL,
  dados TEXT NOT NULL,          -- cliente, endereço, frete, itens com mockup, histórico
  atualizado TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pedidos_criado ON pedidos (criado DESC);
