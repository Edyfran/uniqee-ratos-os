// Gera semente.sql com os produtos de ../loja/js/dados.js, pra encher o banco na primeira vez.
// Uso: node semente.mjs && npx wrangler d1 execute uniqee-loja --local --file=semente.sql
import { readFileSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';

const contexto = { window: {} };
vm.runInNewContext(readFileSync(new URL('../loja/js/dados.js', import.meta.url), 'utf8'), contexto);
const { PRODUTOS } = contexto.window.UNIQEE;

const texto = (s) => `'${String(s).replace(/'/g, "''")}'`;
const agora = new Date().toISOString();
// só na primeira vez: produto apagado no painel não volta quando o servidor reinicia
const linhas = PRODUTOS.map(({ id, ...dados }, i) =>
  `INSERT OR IGNORE INTO produtos (id, dados, ativo, ordem, atualizado) SELECT ${texto(id)}, ${texto(JSON.stringify(dados))}, 1, ${i + 1}, ${texto(agora)} WHERE NOT EXISTS (SELECT 1 FROM semeado);`);
linhas.push(`INSERT INTO semeado (quando) SELECT ${texto(agora)} WHERE NOT EXISTS (SELECT 1 FROM semeado);`);
writeFileSync(new URL('./semente.sql', import.meta.url), linhas.join('\n') + '\n');
console.log(`${PRODUTOS.length} produtos em semente.sql`);
