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

-- marca que os produtos iniciais (semente.mjs) já entraram: depois disso, quem manda é o painel
CREATE TABLE IF NOT EXISTS semeado (quando TEXT NOT NULL);

-- clientes: nascem sozinhos com o primeiro pedido da loja ou são cadastrados no painel (venda pelo WhatsApp)
CREATE TABLE IF NOT EXISTS clientes (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  email TEXT,                   -- minúsculo; serve pra ligar o cliente aos pedidos
  zap TEXT,                     -- só números
  dados TEXT NOT NULL,          -- cpf, endereço, datas que importam, origem, anotações
  criado TEXT NOT NULL,
  atualizado TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS clientes_email ON clientes (email);
CREATE INDEX IF NOT EXISTS clientes_zap ON clientes (zap);
