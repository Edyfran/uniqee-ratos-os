// Painel da Uniqee: pedidos (ver e avançar a etapa) e produtos (cadastrar, editar, esconder).
// Fala com a API do servidor em /api/admin; a sessão fica num cookie que o servidor cria ao entrar.
(function () {
  const { MOMENTOS, CATEGORIAS, COLECOES, etapasDo } = window.UNIQEE;
  const app = document.getElementById('app');
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const brl = (v) => (+v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const foto = (img) => /^(\/|https?:|data:)/.test(img || '') ? img : '../img/' + img;
  const data = (iso, hora = true) => new Date(iso).toLocaleString('pt-BR', hora ? { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: '2-digit', year: 'numeric' });
  const TIPOS_PROVADOR = [['caneca', 'Caneca (3D)'], ['azulejo', 'Azulejo'], ['camiseta', 'Camiseta']];

  const toast = $('#toast');
  let tToast;
  function avisar(msg) { toast.textContent = msg; toast.classList.add('on'); clearTimeout(tToast); tToast = setTimeout(() => toast.classList.remove('on'), 3200); }

  async function api(caminho, opcoes = {}) {
    const corpo = opcoes.corpo;
    const ehArquivo = corpo instanceof Blob;
    let r;
    try {
      r = await fetch('/api/admin/' + caminho, {
        method: opcoes.metodo || (corpo ? 'POST' : 'GET'), credentials: 'same-origin',
        headers: ehArquivo ? { 'content-type': corpo.type } : { 'content-type': 'application/json' },
        body: corpo === undefined ? undefined : ehArquivo ? corpo : JSON.stringify(corpo),
      });
    } catch { throw new Error('Sem conexão com a loja. Confira a internet.'); }
    const d = await r.json().catch(() => ({}));
    if (r.status === 401 && caminho !== 'entrar') { telaEntrar(); throw new Error('sessao'); }
    if (!r.ok) throw new Error(d.erro || 'Deu um problema. Tente de novo.');
    return d;
  }
  const falhou = (e) => { if (e.message !== 'sessao') avisar(e.message); };

  // ---------- entrar ----------
  function telaEntrar() {
    $('#topo').hidden = true;
    app.innerHTML = `<div class="pn-entrar">
      <img src="../img/logo-uniqee.png" alt="">
      <h1>Painel da Uniqee</h1>
      <p class="sub" style="margin:0 auto">Pedidos e produtos da loja.</p>
      <form class="caixa" id="fEntrar">
        <div class="grupo"><label class="rot" for="senha">Senha</label><input class="campo" id="senha" name="senha" type="password" autocomplete="current-password" required></div>
        <p class="pn-erro" id="eEntrar" hidden></p>
        <button class="botao rose cheio-largo" style="margin-top:6px">Entrar</button>
      </form>
    </div>`;
    $('#senha').focus();
    $('#fEntrar').onsubmit = async (e) => {
      e.preventDefault();
      try { await api('entrar', { corpo: { senha: e.target.senha.value } }); location.hash = location.hash || '#/pedidos'; rota(); }
      catch (err) { $('#eEntrar').hidden = false; $('#eEntrar').textContent = err.message; }
    };
  }
  $('#sair').onclick = async () => { await api('sair', { corpo: {} }).catch(() => {}); telaEntrar(); };

  // ---------- pedidos ----------
  const etapaNome = (p, i = p.etapa) => etapasDo(p)[i]?.[0] || '';
  const etapaClasse = (p) => p.etapa === 0 ? 'e0' : p.etapa === 1 ? 'e1' : p.etapa >= etapasDo(p).length - 1 ? 'fim' : '';
  let filtroPedidos = 'abertos';

  async function telaPedidos() {
    app.innerHTML = `<div class="pn-titulo"><h1>Pedidos</h1></div><div class="pn-vazio">Carregando…</div>`;
    let lista;
    try { lista = await api('pedidos'); } catch (e) { return falhou(e); }
    const FILTROS = [
      ['abertos', 'Em aberto', p => p.etapa >= 1 && p.etapa < etapasDo(p).length - 1],
      ['pagar', 'Aguardando pagamento', p => p.etapa === 0],
      ['producao', 'Arte e produção', p => p.etapa >= 2 && p.etapa <= 4],
      ['enviar', 'Enviados ou prontos', p => p.etapa === 5],
      ['entregues', 'Entregues', p => p.etapa === 6],
      ['todos', 'Todos', () => true],
    ];
    const desenhar = () => {
      const filtro = FILTROS.find(f => f[0] === filtroPedidos);
      const vistos = lista.filter(filtro[2]);
      const aReceber = lista.filter(p => p.etapa === 0).reduce((s, p) => s + p.total, 0);
      app.innerHTML = `<div class="pn-titulo"><h1>Pedidos</h1>${aReceber ? `<span class="pn-selo">Aguardando pagamento: ${brl(aReceber)}</span>` : ''}</div>
        <div class="pn-filtros">${FILTROS.map(([id, nome, f]) => `<button class="filtro" data-f="${id}" aria-pressed="${id === filtroPedidos}">${nome}<b>${lista.filter(f).length}</b></button>`).join('')}</div>
        <div class="pn-lista">${vistos.length ? vistos.map(p => `<a class="pn-linha" href="#/pedido/${p.codigo}">
          <span class="fotos">${p.itens.slice(0, 3).map(i => `<img src="${foto(i.img)}" alt="">`).join('')}</span>
          <span class="meio"><b>${esc(p.cliente)}</b><small>${esc(p.codigo)} · ${data(p.data)} · ${p.itens.reduce((s, i) => s + i.qtd, 0)} ${p.itens.length === 1 && p.itens[0].qtd === 1 ? 'item' : 'itens'} · ${esc(p.frete?.nome || '')}</small></span>
          <span class="fim"><b>${brl(p.total)}</b><span class="pn-etapa ${etapaClasse(p)}">${etapaNome(p)}</span></span>
        </a>`).join('') : `<div class="pn-vazio">Nenhum pedido aqui.</div>`}</div>`;
      $$('[data-f]').forEach(b => b.onclick = () => { filtroPedidos = b.dataset.f; desenhar(); });
    };
    desenhar();
  }

  async function telaPedido(codigo) {
    app.innerHTML = `<div class="pn-vazio">Carregando…</div>`;
    let p;
    try { p = await api('pedidos/' + encodeURIComponent(codigo)); } catch (e) { app.innerHTML = `<a class="pn-volta" href="#/pedidos">← Pedidos</a><div class="pn-vazio">${esc(e.message)}</div>`; return; }
    const etapas = etapasDo(p);
    const quando = Object.fromEntries((p.historico || []).map(h => [h.etapa, h.quando]));
    const zap = String(p.cliente.zap || '').replace(/\D/g, '');
    const e = p.endereco || {};
    const ultima = p.etapa >= etapas.length - 1;
    app.innerHTML = `<a class="pn-volta" href="#/pedidos">← Pedidos</a>
      <div class="pn-titulo"><h1>${esc(p.codigo)}</h1><span class="pn-etapa ${etapaClasse(p)}">${etapaNome(p)}</span></div>
      <div class="pn-grade">
        <div style="display:grid;gap:14px">
          <div class="caixa"><h2>Itens</h2><div class="pn-itens">${p.itens.map(i => `<div class="pn-item">
            <a class="amplia" href="${esc(foto(i.mockup || i.img))}" target="_blank" rel="noopener"><img src="${esc(foto(i.mockup || i.img))}" alt="${i.mockup ? 'Mockup montado pelo cliente' : ''}"></a>
            <div><b>${i.qtd}x ${esc(i.nome)}</b> <span style="color:var(--preco);font-weight:600">${brl(i.preco * i.qtd)}</span>
              ${(i.detalhes?.length ? i.detalhes : Object.entries(i.opcoes || {}).map(([k, v]) => `${k}: ${v}`)).map(d => `<small>${esc(d)}</small>`).join('')}
              ${i.mockup ? '<small style="color:var(--rose-2)">Mockup do provador. Toque pra ampliar.</small>' : ''}</div>
          </div>`).join('')}</div>
          <div class="pn-contas" style="margin-top:14px">
            <div><span>Produtos</span><span>${brl(p.subtotal)}</span></div>
            <div><span>${esc(p.frete?.nome)}</span><span>${p.frete?.valor ? brl(p.frete.valor) : 'Grátis'}</span></div>
            <div class="total"><span>Total · ${p.pagamento === 'pix' ? 'Pix' : 'cartão'}</span><span>${brl(p.total)}</span></div>
          </div></div>
          <div class="caixa"><h2>Cliente</h2><div class="pn-dados">
            <b>${esc(p.cliente.nome)}</b>
            <div><span>WhatsApp:</span> ${esc(p.cliente.zap)}</div>
            <div><span>E-mail:</span> ${esc(p.cliente.email)}</div>
            <div><span>CPF:</span> ${esc(p.cliente.cpf)}</div>
            <div><span>Entrega:</span> ${esc(e.rua)}, ${esc(e.numero)}${e.complemento ? ', ' + esc(e.complemento) : ''}, ${esc(e.bairro)}, ${esc(e.cidade)}/${esc(e.uf)} · CEP ${esc(e.cep)}</div>
            ${p.obs ? `<div><span>Recado do cliente:</span> ${esc(p.obs)}</div>` : ''}
            <div><span>Feito em:</span> ${data(p.data)}</div>
          </div>
          ${zap ? `<a class="botao zap" style="margin-top:14px" href="https://wa.me/55${zap.replace(/^55(?=\d{10,11}$)/, '')}?text=${encodeURIComponent(`Olá, ${p.cliente.nome.split(' ')[0]}! Aqui é da Uniqee, sobre o pedido ${p.codigo}.`)}" target="_blank" rel="noopener">Chamar no WhatsApp</a>` : ''}
          </div>
        </div>
        <div style="display:grid;gap:14px">
          <div class="caixa"><h2>Andamento</h2>
            <ol class="pn-passos">${etapas.map(([t], i) => `<li class="${i < p.etapa ? 'feito' : i === p.etapa ? 'atual' : ''}"><i>${i < p.etapa ? '✓' : ''}</i>${t}${quando[i] ? `<small>${data(quando[i])}</small>` : ''}</li>`).join('')}</ol>
            ${ultima ? '<p class="sub" style="margin:0">Pedido concluído.</p>' : `<button class="botao rose cheio-largo" id="avancar">Avançar pra: ${etapas[p.etapa + 1][0]}</button>`}
            ${p.etapa > 0 ? `<button class="botao leve" id="voltar" style="margin-top:6px">Voltar pra: ${etapas[p.etapa - 1][0]}</button>` : ''}
            <p class="sub" style="font-size:13px;margin:10px 0 0">O cliente vê essa etapa na página do pedido.</p>
          </div>
          <div class="caixa"><h2>Anotações</h2>
            <textarea class="campo" id="notas" placeholder="Só você vê. Ex.: arte enviada pro cliente, falta a foto 2…">${esc(p.notas || '')}</textarea>
            <button class="botao contorno" id="salvarNotas" style="margin-top:10px">Salvar anotação</button>
          </div>
        </div>
      </div>`;
    const mudar = async (dados, msg) => {
      try { await api('pedidos/' + encodeURIComponent(p.codigo), { metodo: 'PATCH', corpo: dados }); avisar(msg); telaPedido(codigo); }
      catch (e) { falhou(e); }
    };
    $('#avancar')?.addEventListener('click', () => mudar({ etapa: p.etapa + 1 }, `Pedido em: ${etapas[p.etapa + 1][0]}.`));
    $('#voltar')?.addEventListener('click', () => mudar({ etapa: p.etapa - 1 }, `Pedido voltou pra: ${etapas[p.etapa - 1][0]}.`));
    $('#salvarNotas').onclick = () => mudar({ notas: $('#notas').value }, 'Anotação salva.');
  }

  // ---------- produtos ----------
  let produtos = [];
  const comoVende = (p) => p.provador ? 'provador' : p.pede ? 'whatsapp' : 'pronto';
  const NOME_VENDA = { pronto: 'Pronto', provador: 'Provador', whatsapp: 'Foto pelo WhatsApp' };

  async function telaProdutos() {
    app.innerHTML = `<div class="pn-titulo"><h1>Produtos</h1></div><div class="pn-vazio">Carregando…</div>`;
    try { produtos = await api('produtos'); } catch (e) { return falhou(e); }
    const visiveis = produtos.filter(p => p.ativo).length;
    app.innerHTML = `<div class="pn-titulo"><h1>Produtos</h1><span class="pn-selo">${visiveis} na loja${produtos.length > visiveis ? ` · ${produtos.length - visiveis} escondido${produtos.length - visiveis > 1 ? 's' : ''}` : ''}</span><a class="botao rose" href="#/produto/novo">+ Novo produto</a></div>
      <div class="pn-lista">${produtos.map(p => `<a class="pn-linha${p.ativo ? '' : ' oculto'}" href="#/produto/${encodeURIComponent(p.id)}">
        <span class="fotos"><img src="${esc(foto(p.img))}" alt=""></span>
        <span class="meio"><b>${esc(p.nome)}</b>
          <span><span class="pn-selo forte">${NOME_VENDA[comoVende(p)]}</span>${p.colecao && COLECOES[p.colecao] ? `<span class="pn-selo">${esc(COLECOES[p.colecao].nome)}</span>` : ''}${p.ativo ? '' : '<span class="pn-selo">Escondido</span>'}</span></span>
        <span class="fim"><b>${brl(p.preco)}</b></span>
      </a>`).join('')}</div>`;
  }

  // reduz a foto no aparelho antes de enviar (foto de celular passa de 5 MB fácil)
  async function prepararFoto(arquivo, max = 1600) {
    const img = await createImageBitmap(arquivo).catch(() => null);
    if (!img) throw new Error('Não consegui abrir essa foto. Envie em JPG ou PNG.');
    const s = Math.min(1, max / Math.max(img.width, img.height));
    const c = document.createElement('canvas'); c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    const blob = await new Promise(ok => c.toBlob(ok, 'image/webp', .88));
    return blob && blob.type === 'image/webp' ? blob : new Promise(ok => c.toBlob(ok, 'image/jpeg', .9));
  }

  async function telaProduto(id) {
    if (!produtos.length) { try { produtos = await api('produtos'); } catch (e) { return falhou(e); } }
    const novo = id === 'novo';
    const p = novo ? { nome: '', preco: '', cat: 'canecas', momentos: [], ativo: true, peso: .5, desc: '' } : produtos.find(x => x.id === id);
    if (!p) { app.innerHTML = `<a class="pn-volta" href="#/produtos">← Produtos</a><div class="pn-vazio">Produto não encontrado.</div>`; return; }
    const venda = comoVende(p);
    const opcoes = p.opcoes || [];
    app.innerHTML = `<a class="pn-volta" href="#/produtos">← Produtos</a>
      <div class="pn-titulo"><h1>${novo ? 'Novo produto' : esc(p.nome)}</h1></div>
      <form class="pn-form" id="fProd" novalidate>
        <div>
          <label class="pn-foto" id="caixaFoto">${p.img ? `<img src="${esc(foto(p.img))}" alt="">` : '<span>Toque pra escolher<br>a foto do produto</span>'}<input type="file" accept="image/*" id="arqFoto" aria-label="Foto do produto"></label>
          <p class="sub" style="font-size:13px;margin:8px 0 0">Foto quadrada fica melhor na vitrine.</p>
          <label class="check" style="margin-top:14px;color:var(--tinta);font-size:15px"><input type="checkbox" name="ativo" ${p.ativo ? 'checked' : ''}><span>Mostrar na loja</span></label>
        </div>
        <div class="caixa">
          <div class="grupo"><label class="rot" for="nome">Nome</label><input class="campo" id="nome" name="nome" value="${esc(p.nome)}" required></div>
          <div class="pn-duas">
            <div class="grupo"><label class="rot" for="preco">Preço (R$) <small>do PreçoArte</small></label><input class="campo" id="preco" name="preco" inputmode="decimal" value="${p.preco === '' ? '' : String(p.preco).replace('.', ',')}" required></div>
            <div class="grupo"><label class="rot" for="etiqueta">Etiqueta <small>opcional</small></label><input class="campo" id="etiqueta" name="etiqueta" maxlength="20" placeholder="Ex.: Lançamento" value="${esc(p.etiqueta || '')}"></div>
            <div class="grupo"><label class="rot" for="cat">Categoria</label><select class="campo" id="cat" name="cat">${CATEGORIAS.filter(c => c[0] !== 'todos').map(([v, n]) => `<option value="${v}" ${p.cat === v ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
            <div class="grupo"><label class="rot" for="colecao">Coleção</label><select class="campo" id="colecao" name="colecao"><option value="">Nenhuma</option>${Object.entries(COLECOES).map(([v, c]) => `<option value="${v}" ${p.colecao === v ? 'selected' : ''}>${esc(c.nome)}</option>`).join('')}</select></div>
          </div>
          <div class="grupo"><span class="rot">Ocasiões</span><div class="pn-marcas">${MOMENTOS.map(m => `<label><input type="checkbox" name="momentos" value="${m.id}" ${p.momentos.includes(m.id) ? 'checked' : ''}>${m.nome}</label>`).join('')}</div></div>

          <div class="grupo"><span class="rot">Como se vende</span><div class="pn-venda">
            <label><input type="radio" name="venda" value="pronto" ${venda === 'pronto' ? 'checked' : ''}><span><b>Pronto</b><small>O cliente compra como está, sem mandar foto nem texto.</small></span></label>
            <label><input type="radio" name="venda" value="provador" ${venda === 'provador' ? 'checked' : ''}><span><b>Personalizável no provador</b><small>O cliente envia a arte e vê o mockup antes de comprar.</small></span></label>
            <div class="pn-sub" data-se="provador"><label class="rot" for="provador">Peça do provador</label><select class="campo" id="provador" name="provador">${TIPOS_PROVADOR.map(([v, n]) => `<option value="${v}" ${p.provador === v ? 'selected' : ''}>${n}</option>`).join('')}</select></div>
            <label><input type="radio" name="venda" value="whatsapp" ${venda === 'whatsapp' ? 'checked' : ''}><span><b>Personalizado pelo WhatsApp</b><small>O cliente escreve o nome ou a frase e manda as fotos depois da compra.</small></span></label>
            <div class="pn-sub" data-se="whatsapp"><div class="pn-duas">
              <div class="grupo"><label class="rot" for="pedeTexto">O que pedir ao cliente</label><input class="campo" id="pedeTexto" name="pedeTexto" placeholder="Ex.: Nome de quem vai receber" value="${esc(p.pede?.texto || '')}"></div>
              <div class="grupo"><label class="rot" for="pedeFotos">Quantas fotos</label><input class="campo" id="pedeFotos" name="pedeFotos" type="number" min="0" max="20" value="${p.pede?.fotos ?? 1}"></div>
            </div></div>
          </div></div>

          <div class="grupo"><span class="rot">Opções que o cliente escolhe <small>ex.: Tamanho: P, M, G, GG</small></span>
            <div id="opcoes">${opcoes.map(o => linhaOpcao(o.nome, o.valores.join(', '))).join('')}</div>
            <button type="button" class="botao leve" id="maisOpcao" style="padding:4px 0">+ Adicionar opção</button></div>
          <div class="grupo"><label class="rot" for="desc">Descrição</label><textarea class="campo" id="desc" name="desc" rows="6">${esc(p.desc || '')}</textarea></div>
          <div class="pn-duas">
            <div class="grupo"><label class="rot" for="peso">Peso com embalagem (kg) <small>pro frete</small></label><input class="campo" id="peso" name="peso" inputmode="decimal" value="${String(p.peso ?? .5).replace('.', ',')}"></div>
            <div class="grupo"><label class="rot" for="ordem">Posição na vitrine <small>menor aparece antes</small></label><input class="campo" id="ordem" name="ordem" type="number" value="${p.ordem ?? ''}" placeholder="no fim"></div>
          </div>
        </div>
        <div class="pn-rodape" style="grid-column:1/-1">
          <button class="botao rose" id="bSalvar">${novo ? 'Cadastrar produto' : 'Salvar'}</button>
          <p class="pn-erro" id="eProd" hidden></p>
          ${novo ? '' : `<a class="botao leve" href="../#/produto/${encodeURIComponent(p.id)}" target="_blank" rel="noopener">Ver na loja</a><button type="button" class="botao perigo direita" id="bApagar">Apagar</button>`}
        </div>
      </form>`;

    function linhaOpcao(nome = '', valores = '') {
      return `<div class="pn-opcao"><input class="campo" data-o="nome" placeholder="Tamanho" value="${esc(nome)}"><input class="campo" data-o="valores" placeholder="P, M, G, GG" value="${esc(valores)}"><button type="button" class="botao leve" data-tirar aria-label="Tirar opção">✕</button></div>`;
    }
    const f = $('#fProd');
    const mostrarSub = () => $$('[data-se]').forEach(d => d.hidden = f.venda.value !== d.dataset.se);
    $$('input[name=venda]').forEach(r => r.onchange = mostrarSub); mostrarSub();
    $('#maisOpcao').onclick = () => $('#opcoes').insertAdjacentHTML('beforeend', linhaOpcao());
    $('#opcoes').onclick = (e) => { if (e.target.closest('[data-tirar]')) e.target.closest('.pn-opcao').remove(); };

    let img = p.img;
    $('#arqFoto').onchange = async (e) => {
      const arq = e.target.files[0]; e.target.value = '';
      if (!arq) return;
      const caixa = $('#caixaFoto');
      caixa.querySelector('img, span')?.remove();
      caixa.insertAdjacentHTML('afterbegin', '<span>Enviando a foto…</span>');
      try {
        const r = await api('foto', { corpo: await prepararFoto(arq) });
        img = r.img;
        caixa.querySelector('span').remove();
        caixa.insertAdjacentHTML('afterbegin', `<img src="${esc(img)}" alt="">`);
      } catch (err) {
        caixa.querySelector('span').textContent = err.message === 'sessao' ? '' : err.message;
        if (img) caixa.insertAdjacentHTML('afterbegin', `<img src="${esc(foto(img))}" alt="">`);
      }
    };

    const numero = (v) => parseFloat(String(v).replace(/\./g, '').replace(',', '.'));
    f.onsubmit = async (e) => {
      e.preventDefault();
      const erro = $('#eProd');
      const preco = numero(f.preco.value);
      const falta = [];
      if (!f.nome.value.trim()) falta.push('nome');
      if (!(preco > 0)) falta.push('preço');
      if (!img) falta.push('foto');
      if (f.venda.value === 'whatsapp' && !f.pedeTexto.value.trim()) falta.push('o que pedir ao cliente');
      if (falta.length) { erro.hidden = false; erro.textContent = 'Falta: ' + falta.join(', ') + '.'; return; }
      erro.hidden = true;
      // mantém o que o formulário não mostra (cores e costas da camiseta, por exemplo)
      const { provador, pede, opcoes: _o, etiqueta, colecao, ...resto } = p;
      const dados = {
        ...resto, nome: f.nome.value.trim(), preco, img, cat: f.cat.value,
        momentos: $$('input[name=momentos]:checked').map(c => c.value),
        desc: f.desc.value.trim(), peso: numero(f.peso.value) || .5, ativo: f.ativo.checked,
      };
      if (f.ordem.value !== '') dados.ordem = +f.ordem.value; else delete dados.ordem;
      if (f.etiqueta.value.trim()) dados.etiqueta = f.etiqueta.value.trim();
      if (f.colecao.value) dados.colecao = f.colecao.value;
      if (f.venda.value === 'provador') dados.provador = f.provador.value;
      if (f.venda.value === 'whatsapp') dados.pede = { texto: f.pedeTexto.value.trim(), ...(+f.pedeFotos.value > 0 ? { fotos: +f.pedeFotos.value } : {}) };
      const ops = $$('.pn-opcao').map(l => ({ nome: $('[data-o=nome]', l).value.trim(), valores: $('[data-o=valores]', l).value.split(',').map(v => v.trim()).filter(Boolean) })).filter(o => o.nome && o.valores.length);
      if (ops.length) dados.opcoes = ops;
      const b = $('#bSalvar'); b.disabled = true;
      try {
        const salvo = await api('produtos/' + (novo ? 'novo' : encodeURIComponent(p.id)), { metodo: 'PUT', corpo: dados });
        produtos = [];
        avisar(novo ? 'Produto cadastrado. Já está na loja.' : 'Produto salvo.');
        location.hash = '#/produto/' + encodeURIComponent(salvo.id);
        if (!novo) telaProduto(salvo.id);
      } catch (err) { if (err.message !== 'sessao') { erro.hidden = false; erro.textContent = err.message; } }
      finally { b.disabled = false; }
    };

    // apagar pede um segundo toque (sem janela de confirmação do navegador)
    $('#bApagar')?.addEventListener('click', async function () {
      if (!this.classList.contains('confirma')) {
        this.classList.add('confirma'); this.textContent = 'Toque de novo pra apagar';
        setTimeout(() => { this.classList.remove('confirma'); this.textContent = 'Apagar'; }, 4000);
        return;
      }
      try { await api('produtos/' + encodeURIComponent(p.id), { metodo: 'DELETE' }); produtos = []; avisar('Produto apagado.'); location.hash = '#/produtos'; }
      catch (e) { falhou(e); }
    });
  }

  // ---------- rotas ----------
  async function rota() {
    const [p0, p1] = (location.hash.slice(1) || '/pedidos').split('/').filter(Boolean).map(decodeURIComponent);
    try { await api('eu'); } catch (e) { if (e.message !== 'sessao') app.innerHTML = `<div class="pn-vazio">${esc(e.message)}</div>`; return; }
    $('#topo').hidden = false;
    const aba = p0 === 'produto' || p0 === 'produtos' ? 'produtos' : 'pedidos';
    $$('[data-aba]').forEach(a => { if (a.dataset.aba === aba) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    window.scrollTo(0, 0);
    if (p0 === 'pedido' && p1) telaPedido(p1);
    else if (p0 === 'produtos') telaProdutos();
    else if (p0 === 'produto' && p1) telaProduto(p1);
    else telaPedidos();
  }
  window.addEventListener('hashchange', rota);
  rota();
})();
