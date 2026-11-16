// API da loja Uniqee: catálogo, pedidos e o painel de gestão.
// Roda na Cloudflare (Worker + D1 + R2); a loja e o painel são os arquivos de ../loja.
// Pagamento e frete continuam simulados até o Mercado Pago e o Melhor Envio serem ligados.

const json = (dados, status = 200, cab = {}) =>
  new Response(JSON.stringify(dados), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...cab } });
const erro = (msg, status = 400) => json({ erro: msg }, status);
const agora = () => new Date().toISOString();

// ---------- sessão do painel: "<expira>.<assinatura>" num cookie que o navegador não deixa o JS ler ----------
const DURACAO_SESSAO = 30 * 24 * 3600 * 1000;
async function assinar(texto, segredo) {
  const chave = await crypto.subtle.importKey('raw', new TextEncoder().encode(segredo), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', chave, new TextEncoder().encode(texto));
  return btoa(String.fromCharCode(...new Uint8Array(sig))).replace(/[+/=]/g, c => ({ '+': '-', '/': '_', '=': '' }[c]));
}
function iguais(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
async function sessaoValida(req, env) {
  const m = (req.headers.get('cookie') || '').match(/(?:^|;\s*)sessao=([^;]+)/);
  if (!m || !env.SEGREDO) return false;
  const [exp, sig] = m[1].split('.');
  return +exp > Date.now() && iguais(sig || '', await assinar(exp, env.SEGREDO));
}
const cookieSessao = (valor, maxAge) => `sessao=${valor}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`;

// ---------- arquivos (fotos de produto e mockups dos pedidos) no R2 ----------
const aleatorio = (n = 10) => [...crypto.getRandomValues(new Uint8Array(n))].map(b => 'abcdefghijkmnpqrstuvwxyz23456789'[b % 32]).join('');
const EXTENSOES = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' };
async function guardarDataUrl(env, prefixo, dataUrl) {
  const m = /^data:(image\/(?:png|jpeg|webp));base64,(.+)$/.exec(dataUrl || '');
  if (!m) return null;
  const bytes = Uint8Array.from(atob(m[2]), c => c.charCodeAt(0));
  const chave = `${prefixo}-${aleatorio()}.${EXTENSOES[m[1]]}`;
  await env.ARQUIVOS.put(chave, bytes, { httpMetadata: { contentType: m[1] } });
  return 'api/arquivos/' + chave;
}

// ---------- produtos ----------
const lerProduto = (linha) => ({ ...JSON.parse(linha.dados), id: linha.id, ativo: !!linha.ativo, ordem: linha.ordem });
async function listarProdutos(env, soAtivos) {
  const { results } = await env.DB.prepare(`SELECT * FROM produtos ${soAtivos ? 'WHERE ativo = 1' : ''} ORDER BY ordem, rowid`).all();
  return results.map(lerProduto);
}
const slug = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);

function limparProduto(p) {
  const nome = String(p.nome || '').trim();
  const preco = Math.round(Number(p.preco) * 100) / 100;
  if (!nome) throw new Error('Falta o nome do produto.');
  if (!(preco > 0)) throw new Error('O preço precisa ser maior que zero.');
  if (!p.img) throw new Error('Falta a foto do produto.');
  const { id, ativo, ordem, ...dados } = p;
  return { ...dados, nome, preco, momentos: Array.isArray(p.momentos) ? p.momentos : [] };
}

// ---------- pedidos ----------
const ETAPA_PAGO = 1;
function codigoPedido() { return 'UQ-' + aleatorio(6).toUpperCase(); }
// o que o cliente vê do próprio pedido (sem CPF nem anotações internas)
function visaoCliente(p) {
  const { cliente, notas, ...resto } = p;
  return { ...resto, cliente: { nome: cliente.nome, email: cliente.email, zap: cliente.zap } };
}
async function lerPedido(env, codigo) {
  const linha = await env.DB.prepare('SELECT * FROM pedidos WHERE codigo = ?').bind(codigo).first();
  return linha && { ...JSON.parse(linha.dados), codigo: linha.codigo, etapa: linha.etapa };
}
async function gravarPedido(env, p, novo = false) {
  const sql = novo
    ? 'INSERT INTO pedidos (codigo, criado, email, etapa, total, dados, atualizado) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)'
    : 'UPDATE pedidos SET criado = ?2, email = ?3, etapa = ?4, total = ?5, dados = ?6, atualizado = ?7 WHERE codigo = ?1';
  await env.DB.prepare(sql).bind(p.codigo, p.data, p.cliente.email.toLowerCase(), p.etapa, p.total, JSON.stringify(p), agora()).run();
}

async function criarPedido(req, env) {
  const b = await req.json().catch(() => null);
  if (!b || !Array.isArray(b.itens) || !b.itens.length) return erro('Pedido sem itens.');
  const c = b.cliente || {};
  if (!c.nome || !c.email || !c.zap) return erro('Faltam dados do cliente.');
  const catalogo = Object.fromEntries((await listarProdutos(env, true)).map(p => [p.id, p]));
  const codigo = codigoPedido();
  const itens = [];
  for (const [n, i] of b.itens.entries()) {
    const prod = catalogo[i.id];
    if (!prod) return erro(`O produto "${i.nome}" não está mais na loja.`);
    const qtd = Math.max(1, Math.min(99, Math.floor(+i.qtd || 1)));
    // preço vem do catálogo; peça do provador pode somar a estampa das costas
    const preco = Math.max(prod.preco, Math.round(+i.preco * 100) / 100 || 0);
    const mockup = i.mockup ? await guardarDataUrl(env, `pedidos/${codigo}/item${n + 1}`, i.mockup) : null;
    itens.push({ id: prod.id, nome: prod.nome, img: prod.img, preco, qtd, opcoes: i.opcoes || {}, detalhes: (i.detalhes || []).map(String), mockup });
  }
  const subtotal = itens.reduce((s, i) => s + i.preco * i.qtd, 0);
  const frete = { id: String(b.frete?.id || ''), nome: String(b.frete?.nome || ''), valor: Math.max(0, +b.frete?.valor || 0), prazo: b.frete?.prazo };
  const data = agora();
  const pedido = {
    codigo, data, cliente: { nome: c.nome, zap: c.zap, email: c.email, cpf: c.cpf, cep: c.cep },
    endereco: b.endereco || {}, frete, pagamento: b.pagamento === 'cartao' ? 'cartao' : 'pix', obs: String(b.obs || ''),
    itens, subtotal, total: subtotal + frete.valor, etapa: 0,
    historico: [{ etapa: 0, quando: data }], notas: '',
  };
  // simulação: cartão sai aprovado na hora; o Pix espera o botão "simular pagamento"
  if (pedido.pagamento === 'cartao') { pedido.etapa = ETAPA_PAGO; pedido.historico.push({ etapa: ETAPA_PAGO, quando: data }); }
  await gravarPedido(env, pedido, true);
  return json(visaoCliente(pedido), 201);
}

// ---------- painel ----------
async function rotasPainel(req, env, url, partes) {
  const [, , , recurso, id, acao] = partes; // /api/admin/<recurso>/<id>/<acao>
  const metodo = req.method;

  if (recurso === 'entrar' && metodo === 'POST') {
    const { senha } = await req.json().catch(() => ({}));
    if (!env.ADMIN_SENHA || !env.SEGREDO) return erro('O painel ainda não tem senha configurada.', 503);
    if (!senha || !iguais(await assinar(senha, env.SEGREDO), await assinar(env.ADMIN_SENHA, env.SEGREDO))) return erro('Senha errada.', 401);
    const exp = String(Date.now() + DURACAO_SESSAO);
    return json({ ok: true }, 200, { 'set-cookie': cookieSessao(`${exp}.${await assinar(exp, env.SEGREDO)}`, DURACAO_SESSAO / 1000) });
  }
  if (recurso === 'sair') return json({ ok: true }, 200, { 'set-cookie': cookieSessao('', 0) });
  if (!(await sessaoValida(req, env))) return erro('Entre com a senha do painel.', 401);
  if (recurso === 'eu') return json({ ok: true });

  if (recurso === 'produtos') {
    if (!id && metodo === 'GET') return json(await listarProdutos(env, false));
    if (id && metodo === 'PUT') {
      const b = await req.json().catch(() => null);
      if (!b) return erro('Dados inválidos.');
      let dados;
      try { dados = limparProduto(b); } catch (e) { return erro(e.message); }
      const novoId = id === 'novo' ? slug(b.id || b.nome) : id;
      if (!novoId) return erro('Nome inválido.');
      if (id === 'novo' && await env.DB.prepare('SELECT 1 FROM produtos WHERE id = ?').bind(novoId).first()) return erro('Já existe um produto com esse nome. Mude o nome.');
      const ordem = Number.isFinite(+b.ordem) ? +b.ordem
        : ((await env.DB.prepare('SELECT MAX(ordem) m FROM produtos').first())?.m ?? 0) + 1;
      await env.DB.prepare(`INSERT INTO produtos (id, dados, ativo, ordem, atualizado) VALUES (?1, ?2, ?3, ?4, ?5)
        ON CONFLICT(id) DO UPDATE SET dados = ?2, ativo = ?3, ordem = ?4, atualizado = ?5`)
        .bind(novoId, JSON.stringify(dados), b.ativo === false ? 0 : 1, ordem, agora()).run();
      return json(lerProduto(await env.DB.prepare('SELECT * FROM produtos WHERE id = ?').bind(novoId).first()));
    }
    if (id && metodo === 'DELETE') {
      await env.DB.prepare('DELETE FROM produtos WHERE id = ?').bind(id).run();
      return json({ ok: true });
    }
  }

  if (recurso === 'foto' && metodo === 'POST') {
    const tipo = (req.headers.get('content-type') || '').split(';')[0];
    if (!EXTENSOES[tipo]) return erro('Envie a foto em JPG, PNG ou WEBP.');
    const bytes = await req.arrayBuffer();
    if (bytes.byteLength > 8 * 1024 * 1024) return erro('A foto passou de 8 MB. Envie uma menor.');
    const chave = `produtos/${aleatorio()}.${EXTENSOES[tipo]}`;
    await env.ARQUIVOS.put(chave, bytes, { httpMetadata: { contentType: tipo } });
    return json({ img: 'api/arquivos/' + chave });
  }

  if (recurso === 'pedidos') {
    if (!id && metodo === 'GET') {
      const { results } = await env.DB.prepare('SELECT codigo, criado, etapa, total, dados FROM pedidos ORDER BY criado DESC LIMIT 300').all();
      return json(results.map(l => {
        const p = JSON.parse(l.dados);
        return { codigo: l.codigo, data: l.criado, etapa: l.etapa, total: l.total, cliente: p.cliente.nome, frete: p.frete, pagamento: p.pagamento,
          itens: p.itens.map(i => ({ nome: i.nome, qtd: i.qtd, img: i.mockup || i.img })) };
      }));
    }
    const p = id && await lerPedido(env, id);
    if (!p) return erro('Pedido não encontrado.', 404);
    if (metodo === 'GET') return json(p);
    if (metodo === 'PATCH') {
      const b = await req.json().catch(() => ({}));
      if (Number.isInteger(b.etapa) && b.etapa !== p.etapa) {
        if (b.etapa < 0 || b.etapa > 6) return erro('Etapa inválida.');
        p.etapa = b.etapa;
        p.historico = [...(p.historico || []), { etapa: b.etapa, quando: agora() }];
      }
      if (typeof b.notas === 'string') p.notas = b.notas.slice(0, 4000);
      await gravarPedido(env, p);
      return json(p);
    }
  }
  return erro('Caminho não encontrado.', 404);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    // atrás de um proxy (link de teste da Ratoeira) o endereço chega com um caminho na frente, ex.: /uniqee-loja/
    const prefixo = (req.headers.get('x-forwarded-prefix') || '').replace(/\/$/, '');
    let caminho = url.pathname;
    if (prefixo && caminho === prefixo) return new Response(null, { status: 301, headers: { location: prefixo + '/' + url.search } });
    if (prefixo && caminho.startsWith(prefixo + '/')) caminho = caminho.slice(prefixo.length);
    if (!caminho.startsWith('/api/')) {
      const sem = new URL(url); sem.pathname = caminho;
      return env.ASSETS.fetch(new Request(sem, req));
    }
    const partes = caminho.split('/'); // ['', 'api', ...]
    try {
      if (partes[2] === 'admin') return await rotasPainel(req, env, url, partes);

      if (partes[2] === 'produtos' && req.method === 'GET')
        return json(await listarProdutos(env, true)); // sem cache: o que muda no painel aparece na hora

      if (partes[2] === 'pedidos') {
        const codigo = (partes[3] || '').toUpperCase();
        if (!codigo && req.method === 'POST') return await criarPedido(req, env);
        // o cliente vê o próprio pedido com o código e o e-mail da compra
        const p = codigo && await lerPedido(env, codigo);
        const email = (url.searchParams.get('email') || '').trim().toLowerCase();
        if (!p || !email || p.cliente.email.toLowerCase() !== email) return erro('Pedido não encontrado.', 404);
        if (req.method === 'GET' && !partes[4]) return json(visaoCliente(p));
        // simulação: enquanto o Mercado Pago não está ligado, o cliente "paga" pelo botão da página
        if (req.method === 'POST' && partes[4] === 'simular-pagamento' && p.etapa === 0) {
          p.etapa = ETAPA_PAGO;
          p.historico = [...(p.historico || []), { etapa: ETAPA_PAGO, quando: agora() }];
          await gravarPedido(env, p);
          return json(visaoCliente(p));
        }
      }

      if (partes[2] === 'arquivos' && req.method === 'GET') {
        const obj = await env.ARQUIVOS.get(partes.slice(3).map(decodeURIComponent).join('/'));
        if (!obj) return new Response('Não encontrado', { status: 404 });
        return new Response(obj.body, { headers: { 'content-type': obj.httpMetadata?.contentType || 'application/octet-stream', 'cache-control': 'public, max-age=31536000, immutable' } });
      }
      return erro('Caminho não encontrado.', 404);
    } catch (e) {
      console.error(e);
      return erro('Deu um problema no servidor. Tente de novo.', 500);
    }
  },
};
