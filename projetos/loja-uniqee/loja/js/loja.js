// Loja Uniqee: páginas, carrinho, finalização, pedido e orçamento.
// Pagamento (Mercado Pago) e frete (Melhor Envio) estão simulados até as contas serem ligadas.
(function () {
  const { CONFIG, PRODUTOS, MOMENTOS, CATEGORIAS, COLECOES, etapasDo } = window.UNIQEE;
  const app = document.getElementById('app');
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const brl = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const zapUrl = (msg) => `https://wa.me/${CONFIG.zap}?text=${encodeURIComponent(msg)}`;
  const produto = (id) => PRODUTOS.find(p => p.id === id);
  // foto do produto: as da loja ficam em img/; as cadastradas pelo painel vêm do servidor (api/arquivos/...)
  const foto = (img) => /^(\/|https?:|data:|api\/)/.test(img || '') ? img : 'img/' + img;

  // ---------- servidor (Cloudflare). Sem ele, como na prévia da Ratoeira, a loja usa js/dados.js ----------
  let servidor = false;
  async function api(caminho, opcoes = {}) {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), opcoes.espera || 8000);
    try {
      const r = await fetch(caminho, { ...opcoes, signal: ctl.signal, headers: opcoes.body ? { 'content-type': 'application/json' } : {} });
      const dados = await r.json().catch(() => null);
      return { ok: r.ok && !!dados, status: r.status, dados };
    } catch { return { ok: false, status: 0, dados: null }; }
    finally { clearTimeout(t); }
  }
  async function carregarCatalogo() {
    if (window.origin === 'null' || location.protocol === 'file:') return; // prévia sem servidor
    const r = await api('api/produtos', { espera: 4000 });
    if (!r.ok || !Array.isArray(r.dados) || !r.dados.length) return;
    servidor = true;
    PRODUTOS.splice(0, PRODUTOS.length, ...r.dados);
  }
  const ICON = {
    zap: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.3c0-.1-.2-.2-.4-.3z"/></svg>',
    seta: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    coracao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
    presente: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="13" rx="2"/><path d="M12 8v13M3 12h18M12 8c-2-4-6-4-6-1.5S10 8 12 8zm0 0c2-4 6-4 6-1.5S14 8 12 8z"/></svg>',
    caminhao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
    foto: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 8"/></svg>',
    relogio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    escudo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="m9 12 2 2 4-4"/></svg>',
  };

  // ---------- armazenamento (a moldura da Ratoeira bloqueia o do navegador: aí fica só na memória) ----------
  const guarda = (() => {
    const mem = {};
    let ls = null;
    try { ls = window.localStorage; ls.setItem('_t', '1'); ls.removeItem('_t'); } catch { ls = null; }
    return {
      ler(k, padrao) { try { const v = ls ? ls.getItem(k) : mem[k]; return v ? JSON.parse(v) : padrao; } catch { return padrao; } },
      gravar(k, v) { const s = JSON.stringify(v); try { if (ls) ls.setItem(k, s); else mem[k] = s; } catch { mem[k] = s; } },
    };
  })();

  // ---------- carrinho ----------
  let carrinho = guarda.ler('uniqee-carrinho', []);
  const salvarCarrinho = () => { guarda.gravar('uniqee-carrinho', carrinho); desenharGaveta(); };
  const qtdItens = () => carrinho.reduce((s, i) => s + i.qtd, 0);
  const subtotal = () => carrinho.reduce((s, i) => s + i.preco * i.qtd, 0);
  const pesoTotal = (itens = carrinho) => itens.reduce((s, i) => s + (produto(i.id)?.peso || .5) * i.qtd, 0);
  function adicionar(item) {
    item.chave = item.chave || `${item.id}-${Date.now().toString(36)}`;
    // item sem personalização própria soma com o mesmo produto e as mesmas opções
    const igual = !item.mockup && carrinho.find(i => !i.mockup && i.id === item.id && JSON.stringify(i.opcoes) === JSON.stringify(item.opcoes) && JSON.stringify(i.detalhes) === JSON.stringify(item.detalhes));
    if (igual) igual.qtd = Math.min(99, igual.qtd + item.qtd); else carrinho.push(item);
    salvarCarrinho();
  }

  function parcelamento(v) {
    const n = Math.min(CONFIG.parcelasSemJuros, Math.max(1, Math.floor(v / CONFIG.parcelaMinima)));
    return n > 1 ? `ou ${n}x de ${brl(v / n)} no cartão` : 'ou no cartão de crédito';
  }

  // ---------- frete (simulação até o Melhor Envio ser ligado) ----------
  const NE = ['AL', 'BA', 'CE', 'MA', 'PE', 'PI', 'RN', 'SE'];
  async function consultarCep(cep) {
    cep = String(cep).replace(/\D/g, '');
    if (cep.length !== 8) throw new Error('cep');
    // na faixa de Sousa a entrega é combinada, então vale até CEP que não é de rua (ex.: 58800-000)
    const deSousa = +cep >= CONFIG.cepSousa[0] && +cep <= CONFIG.cepSousa[1];
    try {
      const r = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      const d = await r.json();
      if (d.erro && deSousa) return { cep, rua: '', bairro: '', cidade: 'Sousa', uf: 'PB' };
      if (d.erro) throw new Error('cep');
      return { cep, rua: d.logradouro, bairro: d.bairro, cidade: d.localidade, uf: d.uf };
    } catch (e) {
      if (e.message === 'cep') throw e;
      return { cep, rua: '', bairro: '', cidade: '', uf: '' }; // sem internet: segue sem preencher o endereço
    }
  }
  function cotarFrete(end, peso) {
    const n = +end.cep;
    if (n >= CONFIG.cepSousa[0] && n <= CONFIG.cepSousa[1]) {
      return [
        { id: 'retirada', nome: 'Retirar com a Uniqee, em Sousa', prazo: 'Local e horário combinados pelo WhatsApp', valor: 0, dias: 0 },
        { id: 'entrega-sousa', nome: 'Entrega em Sousa', prazo: 'Combinada pelo WhatsApp', valor: 0, dias: 0 },
      ];
    }
    const uf = end.uf || '';
    const prim = String(end.cep)[0];
    const regiao = uf === 'PB' ? 'pb' : NE.includes(uf) || (!uf && prim === '5') || (!uf && prim === '4') ? 'ne' : 'longe';
    const base = { pb: [19.9, 29.9, [3, 5], [1, 2]], ne: [24.9, 39.9, [5, 8], [2, 4]], longe: [32.9, 54.9, [7, 12], [3, 6]] }[regiao];
    const extra = Math.max(0, Math.ceil((peso - .5) * 2) / 2);
    return [
      { id: 'pac', nome: 'Correios PAC', valor: +(base[0] + extra * 4).toFixed(2), dias: base[2][1], prazo: `${base[2][0]} a ${base[2][1]} dias úteis de entrega` },
      { id: 'sedex', nome: 'Correios SEDEX', valor: +(base[1] + extra * 7).toFixed(2), dias: base[3][1], prazo: `${base[3][0]} a ${base[3][1]} dias úteis de entrega` },
    ];
  }

  // ---------- aviso flutuante e gaveta ----------
  const toast = $('#toast');
  let toastTimer;
  function avisar(msg, botao, acao) {
    toast.innerHTML = `<span>${esc(msg)}</span>${botao ? `<button>${esc(botao)}</button>` : ''}`;
    if (botao) toast.querySelector('button').onclick = () => { toast.classList.remove('on'); acao(); };
    toast.classList.add('on');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 5000);
  }
  function abrirGaveta() { toast.classList.remove('on'); document.body.classList.add('gaveta-aberta'); desenharGaveta(); $('#gaveta').setAttribute('aria-hidden', 'false'); }
  function fecharGaveta() { document.body.classList.remove('gaveta-aberta'); $('#gaveta').setAttribute('aria-hidden', 'true'); }
  $('#abrirCarrinho').onclick = abrirGaveta;
  $('#fecharCarrinho').onclick = fecharGaveta;
  $('.gaveta-fundo').onclick = fecharGaveta;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') fecharGaveta(); });
  function desenharGaveta() {
    const n = qtdItens();
    $('#contaCarrinho').textContent = n;
    $('#contaCarrinho').hidden = n === 0;
    const box = $('#gavetaItens'), rod = $('#gavetaRodape');
    if (!carrinho.length) {
      box.innerHTML = `<div class="vazio" style="margin-top:20px">Seu carrinho está vazio.<br><br><a href="#/presentes" data-fecha>Escolher um presente</a></div>`;
      rod.hidden = true;
    } else {
      box.innerHTML = carrinho.map(i => `
        <div class="item-car" data-chave="${i.chave}">
          <img src="${i.mockup || foto(i.img)}" alt="">
          <div>
            <div class="nome">${esc(i.nome)}</div>
            ${i.detalhes?.length ? `<div class="det">${i.detalhes.map(esc).join('<br>')}</div>` : ''}
            <div class="rodape">
              <div class="qtd"><button data-a="menos" aria-label="Menos">−</button><input value="${i.qtd}" inputmode="numeric" aria-label="Quantidade"><button data-a="mais" aria-label="Mais">+</button></div>
              <span class="v">${brl(i.preco * i.qtd)}</span>
            </div>
            <button class="remover" data-a="remover">Remover</button>
          </div>
        </div>`).join('');
      rod.hidden = false;
      $('#gavetaSubtotal').textContent = brl(subtotal());
    }
    $$('[data-fecha]', box).forEach(a => a.onclick = fecharGaveta);
    $$('.item-car', box).forEach(el => {
      const item = carrinho.find(i => i.chave === el.dataset.chave);
      el.querySelector('[data-a=menos]').onclick = () => { item.qtd = Math.max(1, item.qtd - 1); salvarCarrinho(); };
      el.querySelector('[data-a=mais]').onclick = () => { item.qtd = Math.min(99, item.qtd + 1); salvarCarrinho(); };
      el.querySelector('input').onchange = (e) => { item.qtd = Math.max(1, Math.min(99, parseInt(e.target.value) || 1)); salvarCarrinho(); };
      el.querySelector('[data-a=remover]').onclick = () => { carrinho = carrinho.filter(i => i !== item); salvarCarrinho(); };
    });
  }
  $('#irFinalizar').onclick = () => { fecharGaveta(); location.hash = '#/finalizar'; };

  // ---------- pedaços de página ----------
  function cardProduto(p) {
    return `<a class="card" href="#/produto/${p.id}">
      <div class="foto"><img src="${foto(p.img)}" alt="${esc(p.nome)}" loading="lazy">${p.etiqueta ? `<span class="etiqueta">${p.etiqueta}</span>` : ''}</div>
      <div class="info">
        <span class="nome">${esc(p.nome)}</span>
        <span class="preco"><b>${brl(p.preco)}</b><em>no Pix</em></span>
        <span class="acao">${p.provador ? 'Personalizar' : 'Ver detalhes'} ${ICON.seta}</span>
      </div></a>`;
  }
  function diasProNatal() {
    const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
    let natal = new Date(hoje.getFullYear(), 11, 25);
    if (hoje > natal) natal = new Date(hoje.getFullYear() + 1, 11, 25);
    return Math.round((natal - hoje) / 86400000);
  }
  function cardsMomentos() {
    const d = diasProNatal();
    return MOMENTOS.map(m => {
      const destaque = m.id === 'natal' && d <= 60;
      const dica = m.id === 'natal' ? (d === 0 ? 'É hoje!' : `Faltam ${d} dias. Peça com antecedência.`) : m.dica;
      return `<a class="momento${destaque ? ' destaque' : ''}" href="#/presentes?momento=${m.id}">
        <span class="emo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${m.icone}</svg></span>
        <b>${m.nome}</b><small>${dica}</small></a>`;
    }).join('');
  }
  const migalha = (...partes) => `<nav class="migalha" aria-label="Você está em"><a href="#/">Início</a>${partes.map(p => `<span>›</span>${p}`).join('')}</nav>`;

  // ---------- páginas ----------
  const paginas = {};

  paginas.inicio = (q) => {
    app.innerHTML = `
    <div class="abertura"><div class="miolo">
      <div>
        <h1>Presentes que <span class="mao">contam histórias.</span></h1>
        <p>A gente transforma o momento de vocês num presente pra guardar. Com foto, com nome, com aquela frase que só vocês entendem.</p>
        <div class="acoes">
          <a class="botao rose" href="#/presentes">Escolher um presente</a>
          <a class="botao contorno" href="#/personalizar">Quero personalizar o meu</a>
        </div>
        <div class="selos">
          <div>${ICON.coracao}Feito com carinho em Sousa-PB</div>
          <div>${ICON.presente}Embalagem pra presentear</div>
          <div>${ICON.caminhao}Envio pra todo o Brasil</div>
        </div>
      </div>
      <div class="mural" aria-hidden="true">
        <div class="polaroide p2"><img src="img/kit-canecas-avos.webp" alt=""><span>pros avós</span></div>
        <div class="polaroide p1"><img src="img/kit-avos-almofada.webp" alt=""><span>amor de família</span></div>
        <div class="polaroide p3"><img src="img/caneca-personalizada.webp" alt=""><span>com a sua foto</span></div>
      </div>
    </div></div>

    <section id="momentos"><div class="miolo">
      <h2 class="titulo">Pra qual momento?</h2>
      <p class="sub">Escolha a ocasião e a gente mostra os presentes que combinam.</p>
      <div class="momentos">${cardsMomentos()}</div>
    </div></section>

    <section style="padding-top:8px"><div class="miolo">
      <h2 class="titulo">Os mais pedidos</h2>
      <p class="sub">Todos feitos aqui, peça por peça.</p>
      <div class="produtos">${PRODUTOS.slice(0, 8).map(cardProduto).join('')}</div>
      <p style="text-align:center;margin-top:22px"><a class="botao contorno" href="#/presentes">Ver todos os presentes</a></p>
    </div></section>

    <section><div class="miolo">
      <div class="personalize">
        <div class="texto">
          <h2 class="titulo">Veja como fica <span class="mao" style="color:#f4c7c2">antes</span> de pedir</h2>
          <p class="sub">No nosso provador você monta o presente do seu jeito e vê na hora como ele vai chegar.</p>
          <ol>
            <li><b>1</b><span>Escolha a peça: caneca, azulejo ou camiseta.</span></li>
            <li><b>2</b><span>Envie a foto e escreva o nome ou a frase.</span></li>
            <li><b>3</b><span>Confira cada detalhe e coloque no carrinho.</span></li>
          </ol>
          <div class="acoes">
            <a class="botao rose" href="#/personalizar/caneca-personalizada">Caneca</a>
            <a class="botao contorno" href="#/personalizar/azulejo-15">Azulejo</a>
            <a class="botao contorno" href="#/personalizar/camisa-poliester">Camiseta</a>
          </div>
        </div>
        <div class="cena" aria-hidden="true">
          <div class="tela">
            <div class="caneca-mini"><svg viewBox="0 0 120 100" fill="none"><rect x="20" y="16" width="62" height="70" rx="8" fill="#fff" stroke="#5e5045" stroke-width="3"/><path d="M82 32h8a14 14 0 0 1 0 28h-8" stroke="#5e5045" stroke-width="3"/><rect x="28" y="28" width="46" height="34" rx="4" fill="#c57e84" opacity=".35"/><path d="M51 52s-9-5.5-9-11a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 5.5-9 11-9 11z" fill="#c57e84"/><text x="51" y="76" text-anchor="middle" font-family="Caveat" font-size="11" fill="#5e5045">pra sempre</text></svg></div>
            <div class="barra c"></div><div class="barra"></div>
          </div>
        </div>
      </div>
    </div></section>

    <section><div class="miolo ra">
      <div>
        <span class="selo-novo">NOVIDADE</span>
        <h2 class="titulo">O azulejo que <span class="mao">toca um vídeo</span></h2>
        <p class="sub">Grave uma mensagem, uma dança, um parabéns. O azulejo vai com uma tag especial e, quando a pessoa aponta o celular, o vídeo de vocês aparece em cima da foto. Um presente que fala.</p>
        <a class="botao rose" href="${zapUrl('Olá! Quero saber do azulejo com realidade aumentada, o que toca vídeo.')}" target="_blank" rel="noopener">Quero o meu</a>
      </div>
      <div class="ra-passos">
        <div class="ra-passo"><span class="n">1</span><div><b>Você manda a foto e o vídeo</b><span>Pelo WhatsApp, do jeito que gravou.</span></div></div>
        <div class="ra-passo"><span class="n">2</span><div><b>A gente faz o azulejo e a tag</b><span>Tudo pronto pra presentear.</span></div></div>
        <div class="ra-passo"><span class="n">3</span><div><b>A pessoa aponta o celular</b><span>E o vídeo toca em cima do azulejo.</span></div></div>
      </div>
    </div></section>

    <section><div class="miolo">
      <h2 class="titulo">Coleções</h2>
      <p class="sub">Pra cada jeito de ser, uma coleção.</p>
      <div class="colecoes">${Object.entries(COLECOES).map(([id, c]) => `<a class="colecao${c.classe ? ' ' + c.classe : ''}" href="#/presentes?colecao=${id}"><img src="img/${c.img}" alt="${esc(c.alt)}"><div><b>${esc(c.nome)}</b><span>${esc(c.desc)}</span></div></a>`).join('')}</div>
    </div></section>

    <section><div class="miolo">
      <h2 class="titulo">Como funciona</h2>
      <p class="sub">Do pedido até a sua casa, a gente acompanha você.</p>
      ${blocoPassos()}
      <p style="margin-top:18px"><a class="botao leve" href="#/como-comprar">Ver o passo a passo completo ${ICON.seta}</a></p>
    </div></section>

    <section style="padding-top:8px"><div class="miolo">
      <div class="chamada-orc">
        <div>
          <h2 class="titulo">Precisa de um orçamento especial?</h2>
          <p class="sub" style="margin-bottom:14px">Lembrancinha de festa, brinde de empresa, kit de formatura ou uma peça que não está aqui. Conta pra gente o que você imagina.</p>
          <ul class="lista-ok">
            <li>${ICON.ok}Preço especial pra quantidade</li>
            <li>${ICON.ok}Arte criada pra sua ocasião</li>
            <li>${ICON.ok}Resposta pelo WhatsApp</li>
          </ul>
        </div>
        <div style="display:grid;gap:10px">
          <a class="botao rose" href="#/orcamento">Montar meu orçamento</a>
          <a class="botao zap" href="${zapUrl('Olá! Queria um orçamento especial.')}" target="_blank" rel="noopener">${ICON.zap} Falar direto no WhatsApp</a>
        </div>
      </div>
    </div></section>

    <section id="perguntas"><div class="miolo">
      <h2 class="titulo">Perguntas frequentes</h2>
      <p class="sub">Se a sua dúvida não estiver aqui, chame a gente no WhatsApp.</p>
      ${blocoPerguntas()}
    </div></section>`;
    if (q.s) setTimeout(() => document.getElementById(q.s)?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  function blocoPassos() {
    return `<div class="passos">
      <div class="passo-card"><div class="ic">${ICON.coracao}</div><b>Escolha o presente</b><p>Pela ocasião, pela pessoa ou pela peça.</p></div>
      <div class="passo-card"><div class="ic">${ICON.foto}</div><b>Conte a história</b><p>Envie a foto, o nome e a frase. Pode ser no provador ou no WhatsApp.</p></div>
      <div class="passo-card"><div class="ic">${ICON.ok}</div><b>Aprove a arte</b><p>Você vê como vai ficar antes de a gente produzir.</p></div>
      <div class="passo-card"><div class="ic">${ICON.caminhao}</div><b>Receba em casa</b><p>Produção em até ${CONFIG.prazoProducao} dias úteis, mais o prazo do frete.</p></div>
    </div>`;
  }
  function blocoPerguntas() {
    return `<div class="perguntas">
      <details><summary>Qual é o prazo de produção?</summary><p>Até ${CONFIG.prazoProducao} dias úteis, contados a partir da confirmação do pagamento. O prazo do frete é somado a ele.</p></details>
      <details><summary>Vocês entregam pra todo o Brasil?</summary><p>Sim. O frete é calculado pelo seu CEP. Em Sousa, a entrega ou a retirada é combinada com a gente, sem taxa.</p></details>
      <details><summary>Como eu mando a foto?</summary><p>No provador do site, na hora de personalizar, ou pelo WhatsApp depois da compra. Quanto maior a foto, melhor fica a impressão.</p></details>
      <details><summary>Vou ver a arte antes de ficar pronta?</summary><p>Sim. Antes de produzir, a gente manda a arte pra você aprovar.</p></details>
      <details><summary>Quais são as formas de pagamento?</summary><p>Pix e cartão de crédito, pelo Mercado Pago.</p></details>
      <details><summary>Posso usar qualquer imagem?</summary><p>A imagem precisa ser sua ou você precisa ter autorização pra usar. A gente pode recusar imagens que desrespeitem direitos de terceiros.</p></details>
    </div>`;
  }

  paginas.presentes = (q) => {
    const momento = MOMENTOS.find(m => m.id === q.momento);
    const cat = CATEGORIAS.find(c => c[0] === q.cat) ? q.cat : 'todos';
    const termo = (q.q || '').trim();
    const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const lista = PRODUTOS.filter(p =>
      (cat === 'todos' || p.cat === cat) &&
      (!momento || p.momentos.includes(momento.id)) &&
      (!q.colecao || p.colecao === q.colecao) &&
      (!termo || norm(p.nome + ' ' + p.desc + ' ' + p.cat).includes(norm(termo))));
    const link = (mud) => {
      const n = { momento: q.momento, cat, colecao: q.colecao, q: termo, ...mud };
      const s = Object.entries(n).filter(([k, v]) => v && !(k === 'cat' && v === 'todos')).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
      return '#/presentes' + (s ? '?' + s : '');
    };
    const colecao = COLECOES[q.colecao];
    const titulo = momento ? `Presentes de ${momento.nome}` : colecao ? esc(colecao.nome) : termo ? `Resultados pra “${esc(termo)}”` : 'Nossos presentes';
    const vazio = colecao
      ? `Os modelos desta coleção estão chegando.<br>Enquanto isso, <a href="${zapUrl(`Olá! Quero ver os modelos da coleção ${colecao.nome}.`)}" target="_blank" rel="noopener">peça pelo WhatsApp</a> ou <a href="#/personalizar">personalize o seu</a>.`
      : `Ainda não temos peça pronta pra essa busca.<br>Mas a gente cria: <a href="#/orcamento">monte um orçamento</a> ou <a href="${zapUrl('Olá! Procurei no site e não achei o que queria. Estou pensando em...')}" target="_blank" rel="noopener">fale no WhatsApp</a>.`;
    app.innerHTML = `<div class="pagina"><div class="miolo">
      ${migalha('Presentes')}
      <h1 class="titulo">${titulo}</h1>
      <p class="sub">${colecao ? esc(colecao.desc) + ' Toque num modelo pra ver os detalhes.' : 'Toque num presente pra ver os detalhes e personalizar.'}</p>
      <form class="busca-grande" id="formBusca"><input class="campo" name="q" placeholder="Procurar: caneca, azulejo, avós…" value="${esc(termo)}"><button class="botao noite">Procurar</button></form>
      <div class="filtros">${CATEGORIAS.map(([id, nome]) => `<a class="filtro" href="${link({ cat: id })}" aria-pressed="${cat === id}">${nome}</a>`).join('')}</div>
      <div class="filtros">${MOMENTOS.map(m => `<a class="filtro mom" href="${link({ momento: q.momento === m.id ? '' : m.id })}" aria-pressed="${q.momento === m.id}">${m.nome}</a>`).join('')}
        ${(momento || q.colecao || termo) ? `<a class="filtro-ativo" href="#/presentes" style="color:var(--rose-2);font-weight:600">limpar filtros</a>` : ''}</div>
      <div class="produtos">${lista.length ? lista.map(cardProduto).join('') : `<div class="vazio">${vazio}</div>`}</div>
    </div></div>`;
    $('#formBusca').onsubmit = (e) => { e.preventDefault(); location.hash = link({ q: e.target.q.value.trim() }); };
  };

  paginas.produto = (q, id) => {
    const p = produto(id);
    if (!p) return paginas.naoEncontrada();
    const sel = {};
    const relacionados = PRODUTOS.filter(x => x.id !== p.id && x.momentos.some(m => p.momentos.includes(m))).slice(0, 4);
    app.innerHTML = `<div class="pagina"><div class="miolo">
      ${migalha(`<a href="#/presentes?cat=${p.cat}">${CATEGORIAS.find(c => c[0] === p.cat)[1]}</a>`, esc(p.nome))}
      <div class="produto">
        <div class="galeria"><div class="principal"><img src="${foto(p.img)}" alt="${esc(p.nome)}">${p.etiqueta ? `<span class="etiqueta">${p.etiqueta}</span>` : ''}</div></div>
        <div>
          <h1>${esc(p.nome)}</h1>
          <div class="preco-grande"><b>${brl(p.preco)}</b><small>no Pix · ${parcelamento(p.preco)}</small></div>
          ${p.provador ? `
            <div class="bloco nota"><b>Monte no provador:</b> envie a foto, escreva a frase e veja ${p.provador === 'caneca' ? 'a caneca girando' : p.provador === 'camiseta' ? 'a camiseta pronta' : 'o azulejo pronto'} antes de pedir.</div>
            <div class="linha-compra"><a class="botao rose cheio-largo" href="#/personalizar/${p.id}">Personalizar e ver como fica</a></div>
            <p style="font-size:14px;color:var(--tinta-2);margin:10px 0 0">Prefere mandar a foto depois? <button class="botao leve" id="semProvador" style="padding:0">Comprar e enviar pelo WhatsApp</button></p>` : `
            ${(p.opcoes || []).map((o, i) => `<div class="bloco"><span class="rot">${o.nome}</span><div class="opcoes-lista" data-op="${i}">${o.valores.map(v => `<button class="opcao" data-v="${v}" aria-pressed="false">${v}</button>`).join('')}</div></div>`).join('')}
            ${p.pede ? `<div class="bloco grupo"><label class="rot" for="pTexto">${esc(p.pede.texto)}</label><input class="campo" id="pTexto" maxlength="80"></div>
              ${p.pede.fotos ? `<div class="nota">${ICON.foto.replace('<svg', '<svg style="width:18px;height:18px;vertical-align:-4px;margin-right:6px"')}Depois da compra, a gente chama você no WhatsApp pra receber ${p.pede.fotos === 1 ? 'a foto' : `as fotos (até ${p.pede.fotos})`}.</div>` : ''}` : ''}
            <div class="bloco"><span class="rot">Quantidade</span><div class="qtd"><button id="pMenos" aria-label="Menos">−</button><input id="pQtd" value="1" inputmode="numeric" aria-label="Quantidade"><button id="pMais" aria-label="Mais">+</button></div></div>
            <p class="erro-msg" id="pFalta" hidden></p>
            <div class="linha-compra">
              <button class="botao rose" id="pAdd">Adicionar ao carrinho</button>
              <button class="botao noite" id="pComprar">Comprar agora</button>
            </div>
            ${p.pede ? '' : `<p style="font-size:14px;color:var(--tinta-2);margin:10px 0 0">Quer uma peça com a sua foto ou a sua arte? <a class="botao leve" href="#/personalizar" style="padding:0">Quero personalizar o meu</a></p>`}`}
          <div class="bloco caixa" style="padding:16px">
            <span class="rot">Calcular frete e prazo</span>
            <form class="frete-calc" id="fFrete"><input class="campo" name="cep" placeholder="Seu CEP" inputmode="numeric" maxlength="9"><button class="botao contorno">Calcular</button></form>
            <div class="frete-res" id="fRes"></div>
          </div>
          <div class="bloco garantias">
            <div>${ICON.relogio}Produção em até ${CONFIG.prazoProducao} dias úteis após o pagamento</div>
            <div>${ICON.ok}Você aprova a arte antes de produzir</div>
            <div>${ICON.presente}Embalagem pra presentear</div>
            <div>${ICON.escudo}Pagamento seguro pelo Mercado Pago</div>
          </div>
          <div class="bloco"><h2 style="font-size:19px;color:var(--marrom);margin:0 0 6px">Sobre o presente</h2><p class="descricao">${esc(p.desc)}</p></div>
          <a class="botao zap" style="margin-top:8px" href="${zapUrl(`Olá! Tenho uma dúvida sobre "${p.nome}" (${brl(p.preco)}).`)}" target="_blank" rel="noopener">${ICON.zap} Tirar dúvida no WhatsApp</a>
        </div>
      </div>
      ${relacionados.length ? `<section style="padding-bottom:0"><h2 class="titulo">Combina também</h2><div class="produtos" style="margin-top:16px">${relacionados.map(cardProduto).join('')}</div></section>` : ''}
    </div></div>`;

    $$('[data-op]').forEach(box => {
      const o = p.opcoes[+box.dataset.op];
      $$('.opcao', box).forEach(b => b.onclick = () => { sel[o.nome] = b.dataset.v; $$('.opcao', box).forEach(x => x.setAttribute('aria-pressed', x === b)); });
    });
    const qtd = $('#pQtd');
    if (qtd) {
      $('#pMenos').onclick = () => qtd.value = Math.max(1, (+qtd.value || 1) - 1);
      $('#pMais').onclick = () => qtd.value = Math.min(99, (+qtd.value || 1) + 1);
      const montarItem = () => {
        const falta = (p.opcoes || []).filter(o => !sel[o.nome]).map(o => `escolha o ${o.nome.toLowerCase()}`);
        if (falta.length) { $('#pFalta').hidden = false; $('#pFalta').textContent = 'Falta pouco: ' + falta.join(', ') + '.'; return null; }
        $('#pFalta').hidden = true;
        const detalhes = Object.entries(sel).map(([k, v]) => `${k}: ${v}`);
        const t = $('#pTexto')?.value.trim();
        if (t) detalhes.push(`${p.pede.texto.split(' (')[0]}: ${t}`);
        if (p.pede?.fotos) detalhes.push('Fotos: enviar pelo WhatsApp');
        return { id: p.id, nome: p.nome, img: p.img, preco: p.preco, qtd: Math.max(1, Math.min(99, parseInt(qtd.value) || 1)), opcoes: sel, detalhes };
      };
      $('#pAdd').onclick = () => { const it = montarItem(); if (!it) return; adicionar(it); avisar('Presente no carrinho.', 'Ver carrinho', abrirGaveta); };
      $('#pComprar').onclick = () => { const it = montarItem(); if (!it) return; adicionar(it); location.hash = '#/finalizar'; };
    }
    const sp = $('#semProvador');
    if (sp) sp.onclick = () => {
      adicionar({ id: p.id, nome: p.nome, img: p.img, preco: p.preco, qtd: 1, opcoes: {}, detalhes: ['Foto e texto: enviar pelo WhatsApp'] });
      avisar('Presente no carrinho. Depois da compra a gente chama você no WhatsApp.', 'Ver carrinho', abrirGaveta);
    };
    ligarCalculoFrete($('#fFrete'), $('#fRes'), () => p.peso || .5);
  };

  function mascaraCep(input) {
    input.addEventListener('input', () => {
      const d = input.value.replace(/\D/g, '').slice(0, 8);
      input.value = d.length > 5 ? d.slice(0, 5) + '-' + d.slice(5) : d;
    });
  }
  function ligarCalculoFrete(form, res, peso) {
    mascaraCep(form.cep);
    form.onsubmit = async (e) => {
      e.preventDefault();
      res.innerHTML = '<span style="color:var(--tinta-2)">Calculando…</span>';
      try {
        const end = await consultarCep(form.cep.value);
        const ops = cotarFrete(end, peso());
        res.innerHTML = (end.cidade ? `<span style="color:var(--tinta-2)">${esc(end.cidade)}/${esc(end.uf)}</span>` : '') +
          ops.map(o => `<div><span><b>${o.nome}</b><br><small style="color:var(--tinta-2)">${o.prazo}</small></span><b style="color:var(--preco)">${o.valor ? brl(o.valor) : 'Grátis'}</b></div>`).join('') +
          `<small style="color:var(--tinta-2)">Some ${CONFIG.prazoProducao} dias úteis de produção. Valores de simulação.</small>`;
      } catch { res.innerHTML = '<span class="erro-msg">CEP não encontrado. Confira os números.</span>'; }
    };
  }

  // provador dentro da loja
  let provadorAtivo = null;
  // sem peça escolhida: o cliente escolhe o que quer personalizar
  paginas.escolherPeca = () => {
    const pecas = PRODUTOS.filter(p => p.provador);
    const NOME = { caneca: 'Caneca', azulejo: 'Azulejo', camiseta: 'Camisa' };
    const DICA = { caneca: 'Gire a caneca e veja sua foto nela', azulejo: 'Veja seu azulejo pronto no suporte', camiseta: 'Estampe a frente e as costas' };
    app.innerHTML = `<div class="pagina"><div class="miolo">
      ${migalha('Quero personalizar o meu')}
      <h1 class="titulo">O que você quer <span class="mao">personalizar?</span></h1>
      <p class="sub">Escolha a peça, envie a sua foto ou a sua arte e veja como fica antes de pedir.</p>
      <div class="produtos escolher-peca">${pecas.map(p => `<a class="card" href="#/personalizar/${p.id}">
        <div class="foto"><img src="${foto(p.img)}" alt="${esc(p.nome)}" loading="lazy"></div>
        <div class="info">
          <span class="nome"><b>${NOME[p.provador]}</b></span>
          <span class="dica">${DICA[p.provador]}</span>
          <span class="preco"><em style="margin:0 4px 0 0">a partir de</em><b>${brl(p.preco)}</b></span>
          <span class="acao">Personalizar ${ICON.seta}</span>
        </div></a>`).join('')}</div>
      <p class="sub" style="margin-top:22px">Quer outra peça, como almofada, squeeze ou um kit? <a href="#/orcamento" style="color:var(--rose-2);font-weight:600">Monte um orçamento</a>.</p>
    </div></div>`;
  };

  paginas.personalizar = (q, id) => {
    if (!id) return paginas.escolherPeca();
    const p = produto(id);
    if (!p || !p.provador) return paginas.naoEncontrada();
    app.innerHTML = `<div class="pagina"><div class="miolo">
      ${migalha('<a href="#/personalizar">Quero personalizar o meu</a>', esc(p.nome))}
      <h1 class="titulo">Veja como fica <span class="mao">antes</span> de pedir</h1>
      <p class="sub">Envie uma foto, escreva um nome ou uma frase e veja o presente pronto, do jeito que vai chegar.</p>
      <div class="filtros">${PRODUTOS.filter(x => x.provador).map(x => `<a class="filtro" href="#/personalizar/${x.id}" aria-pressed="${x.id === p.id}">${{ caneca: 'Caneca', azulejo: 'Azulejo', camiseta: 'Camiseta' }[x.provador]}</a>`).join('')}</div>
      <div id="provador"></div>
    </div></div>`;
    provadorAtivo = window.Provador.montar($('#provador'), {
      tipo: p.provador, produto: p,
      aoAdicionar: (d) => {
        adicionar({ id: p.id, nome: p.nome, img: p.img, preco: d.preco ?? p.preco, qtd: d.qtd, opcoes: d.opcoes, detalhes: d.detalhes, mockup: d.mockup });
        avisar('Presente no carrinho, do jeitinho que você montou.', 'Ver carrinho', abrirGaveta);
      },
    });
  };

  // finalizar compra
  paginas.finalizar = () => {
    if (!carrinho.length) {
      app.innerHTML = `<div class="pagina"><div class="miolo">${migalha('Finalizar compra')}<div class="vazio">Seu carrinho está vazio.<br><br><a class="botao rose" href="#/presentes" style="color:#fff">Escolher um presente</a></div></div></div>`;
      return;
    }
    const salvo = guarda.ler('uniqee-cliente', {});
    app.innerHTML = `<div class="pagina"><div class="miolo">
      ${migalha('Finalizar compra')}
      <h1 class="titulo">Finalizar compra</h1>
      <p class="sub">Falta pouco pro seu presente começar a ser feito.</p>
      <form class="finalizar" id="fCompra" novalidate>
        <div style="display:grid;gap:14px">
          <div class="caixa">
            <h2><span class="n">1</span> Seus dados</h2>
            <div class="grupo"><label class="rot" for="cNome">Nome completo</label><input class="campo" id="cNome" name="nome" autocomplete="name" required value="${esc(salvo.nome)}"></div>
            <div class="duas">
              <div class="grupo"><label class="rot" for="cZap">WhatsApp</label><input class="campo" id="cZap" name="zap" inputmode="tel" autocomplete="tel" placeholder="(83) 9 0000-0000" required value="${esc(salvo.zap)}"></div>
              <div class="grupo"><label class="rot" for="cEmail">E-mail</label><input class="campo" id="cEmail" name="email" type="email" autocomplete="email" required value="${esc(salvo.email)}"></div>
            </div>
            <div class="grupo" style="margin:0"><label class="rot" for="cCpf">CPF <small>(pedido pelo Mercado Pago e pela transportadora)</small></label><input class="campo" id="cCpf" name="cpf" inputmode="numeric" placeholder="000.000.000-00" required value="${esc(salvo.cpf)}"></div>
          </div>
          <div class="caixa">
            <h2><span class="n">2</span> Entrega</h2>
            <div class="grupo"><label class="rot" for="cCep">CEP</label><div class="frete-calc"><input class="campo" id="cCep" name="cep" inputmode="numeric" maxlength="9" required value="${esc(salvo.cep)}"><button type="button" class="botao contorno" id="bCep">Buscar</button></div><p class="erro-msg" id="eCep" hidden></p></div>
            <div id="blocoEndereco" hidden>
              <div class="tres">
                <div class="grupo"><label class="rot" for="cRua">Rua</label><input class="campo" id="cRua" name="rua" autocomplete="address-line1" required></div>
                <div class="grupo"><label class="rot" for="cNum">Número</label><input class="campo" id="cNum" name="numero" required></div>
                <div class="grupo"><label class="rot" for="cComp">Complemento</label><input class="campo" id="cComp" name="complemento"></div>
              </div>
              <div class="tres">
                <div class="grupo"><label class="rot" for="cBairro">Bairro</label><input class="campo" id="cBairro" name="bairro" required></div>
                <div class="grupo"><label class="rot" for="cCidade">Cidade</label><input class="campo" id="cCidade" name="cidade" required></div>
                <div class="grupo"><label class="rot" for="cUf">UF</label><input class="campo" id="cUf" name="uf" maxlength="2" required></div>
              </div>
              <span class="rot">Como você quer receber?</span>
              <div id="opcoesFrete"></div>
            </div>
          </div>
          <div class="caixa">
            <h2><span class="n">3</span> Pagamento</h2>
            <label class="radio-card"><input type="radio" name="pag" value="pix" checked><span class="t"><b>Pix</b><small>Aprovação na hora. O código aparece na próxima tela.</small></span></label>
            <label class="radio-card"><input type="radio" name="pag" value="cartao"><span class="t"><b>Cartão de crédito</b><small id="txtParcelas"></small></span></label>
            <div class="grupo" style="margin-top:12px"><label class="rot" for="cObs">Observações <small>(opcional: data que precisa receber, recado pro cartão…)</small></label><textarea class="campo" id="cObs" name="obs" maxlength="400"></textarea></div>
            <label class="check"><input type="checkbox" id="cTermo" required><span>Li e aceito as <a href="#/trocas" target="_blank">trocas e devoluções</a> e a <a href="#/privacidade" target="_blank">política de privacidade</a>.</span></label>
          </div>
        </div>
        <aside class="caixa resumo-lateral">
          <h2>Resumo</h2>
          ${carrinho.map(i => `<div class="item-mini"><img src="${i.mockup || foto(i.img)}" alt=""><span>${i.qtd}x ${esc(i.nome)}</span><b>${brl(i.preco * i.qtd)}</b></div>`).join('')}
          <div class="contas">
            <div><span>Produtos</span><span>${brl(subtotal())}</span></div>
            <div><span>Frete</span><span id="rFrete">informe o CEP</span></div>
            <div class="total"><span>Total</span><span id="rTotal">${brl(subtotal())}</span></div>
          </div>
          <p class="erro-msg" id="eForm" hidden></p>
          <button class="botao rose cheio-largo" style="margin-top:14px" id="bFinalizar">Finalizar pedido</button>
          <p class="nota simulacao" style="margin:12px 0 0">Versão de teste: o pagamento e o frete são simulados. Nenhuma cobrança é feita.</p>
        </aside>
      </form>
    </div></div>`;

    const f = $('#fCompra');
    let frete = null, endereco = null;
    mascaraCep(f.cep);
    f.cpf.addEventListener('input', () => {
      const d = f.cpf.value.replace(/\D/g, '').slice(0, 11);
      f.cpf.value = d.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})\.(\d{3})(\d)/, '$1.$2.$3').replace(/(\d{3})\.(\d{3})\.(\d{3})(\d)/, '$1.$2.$3-$4');
    });
    const atualizarTotais = () => {
      const total = subtotal() + (frete ? frete.valor : 0);
      $('#rFrete').textContent = frete ? (frete.valor ? brl(frete.valor) : 'Grátis') : 'informe o CEP';
      $('#rTotal').textContent = brl(total);
      const n = Math.min(CONFIG.parcelasSemJuros, Math.max(1, Math.floor(total / CONFIG.parcelaMinima)));
      $('#txtParcelas').textContent = n > 1 ? `Em até ${n}x de ${brl(total / n)} sem juros.` : 'À vista no cartão.';
    };
    atualizarTotais();
    async function buscarCep() {
      $('#eCep').hidden = true;
      try {
        endereco = await consultarCep(f.cep.value);
        $('#blocoEndereco').hidden = false;
        if (endereco.rua) f.rua.value = endereco.rua;
        if (endereco.bairro) f.bairro.value = endereco.bairro;
        if (endereco.cidade) f.cidade.value = endereco.cidade;
        if (endereco.uf) f.uf.value = endereco.uf;
        const ops = cotarFrete(endereco, pesoTotal());
        $('#opcoesFrete').innerHTML = ops.map((o, i) => `<label class="radio-card"><input type="radio" name="frete" value="${o.id}" ${i === 0 ? 'checked' : ''}><span class="t"><b>${o.nome}</b><small>${o.prazo}</small></span><span class="v">${o.valor ? brl(o.valor) : 'Grátis'}</span></label>`).join('')
          + `<p style="font-size:13px;color:var(--tinta-2);margin:4px 0 0">Some ${CONFIG.prazoProducao} dias úteis de produção.</p>`;
        frete = ops[0];
        $$('[name=frete]').forEach(r => r.onchange = () => { frete = ops.find(o => o.id === r.value); atualizarTotais(); });
        atualizarTotais();
        (endereco.rua ? f.numero : f.rua).focus();
      } catch {
        $('#eCep').hidden = false; $('#eCep').textContent = 'CEP não encontrado. Confira os números.';
      }
    }
    $('#bCep').onclick = buscarCep;
    f.cep.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); buscarCep(); } });
    f.cep.addEventListener('input', () => { if (f.cep.value.replace(/\D/g, '').length === 8) buscarCep(); });
    if (salvo.cep) buscarCep();

    f.onsubmit = async (e) => {
      e.preventDefault();
      if ($('#bFinalizar').disabled) return;
      const erros = [];
      $$('.campo', f).forEach(c => c.classList.remove('invalido'));
      const marcar = (campo, msg) => { campo.classList.add('invalido'); erros.push(msg); };
      if (f.nome.value.trim().split(/\s+/).length < 2) marcar(f.nome, 'nome completo');
      if (f.zap.value.replace(/\D/g, '').length < 10) marcar(f.zap, 'WhatsApp com DDD');
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.value.trim())) marcar(f.email, 'e-mail');
      if (!cpfValido(f.cpf.value)) marcar(f.cpf, 'CPF válido');
      if (!frete) marcar(f.cep, 'CEP');
      else for (const c of ['rua', 'numero', 'bairro', 'cidade', 'uf']) if (!f[c].value.trim()) marcar(f[c], 'endereço completo');
      if (!$('#cTermo').checked) erros.push('aceite das trocas e da privacidade');
      const ef = $('#eForm');
      if (erros.length) { ef.hidden = false; ef.textContent = 'Confira: ' + [...new Set(erros)].join(', ') + '.'; f.querySelector('.invalido')?.focus(); return; }
      ef.hidden = true;
      const cliente = { nome: f.nome.value.trim(), zap: f.zap.value.trim(), email: f.email.value.trim(), cpf: f.cpf.value, cep: f.cep.value };
      guarda.gravar('uniqee-cliente', cliente);
      const pedido = {
        codigo: 'UQ-' + Date.now().toString(36).toUpperCase().slice(-6),
        data: new Date().toISOString(),
        cliente,
        endereco: { rua: f.rua.value.trim(), numero: f.numero.value.trim(), complemento: f.complemento.value.trim(), bairro: f.bairro.value.trim(), cidade: f.cidade.value.trim(), uf: f.uf.value.trim().toUpperCase(), cep: f.cep.value },
        frete, pagamento: f.pag.value, obs: f.obs.value.trim(),
        itens: carrinho.map(i => ({ ...i })),
        subtotal: subtotal(), total: subtotal() + frete.valor,
        etapa: f.pag.value === 'cartao' ? 1 : 0,
      };
      if (servidor) {
        const b = $('#bFinalizar'); b.disabled = true; b.textContent = 'Enviando o pedido…';
        const r = await api('api/pedidos', { method: 'POST', body: JSON.stringify(pedido), espera: 30000 });
        b.disabled = false; b.textContent = 'Finalizar pedido';
        if (!r.ok) { ef.hidden = false; ef.textContent = r.dados?.erro || 'Não consegui enviar o pedido. Confira a internet e tente de novo.'; return; }
        Object.assign(pedido, r.dados, { online: true });
      }
      const pedidos = guarda.ler('uniqee-pedidos', {});
      pedidos[pedido.codigo] = pedido;
      guarda.gravar('uniqee-pedidos', pedidos);
      carrinho = []; salvarCarrinho();
      location.hash = '#/pedido/' + pedido.codigo;
    };
  };
  function cpfValido(v) {
    const d = v.replace(/\D/g, '');
    if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
    for (const t of [9, 10]) {
      let s = 0;
      for (let i = 0; i < t; i++) s += +d[i] * (t + 1 - i);
      if (((s * 10) % 11) % 10 !== +d[t]) return false;
    }
    return true;
  }

  // pedido
  function qrFalso(texto) {
    // desenho de QR só pra simulação; na versão final o QR vem do Mercado Pago
    let h = 0; for (const c of texto) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const n = 25, cel = []; const rnd = () => (h = (h * 1103515245 + 12345) >>> 0) / 4294967296;
    const olho = (x, y) => `<rect x="${x}" y="${y}" width="7" height="7" fill="#0b1220"/><rect x="${x + 1}" y="${y + 1}" width="5" height="5" fill="#fff"/><rect x="${x + 2}" y="${y + 2}" width="3" height="3" fill="#0b1220"/>`;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if ((x < 8 && y < 8) || (x > n - 9 && y < 8) || (x < 8 && y > n - 9)) continue;
      if (rnd() > .52) cel.push(`<rect x="${x}" y="${y}" width="1" height="1"/>`);
    }
    return `<svg viewBox="-1 -1 ${n + 2} ${n + 2}" width="130" height="130" shape-rendering="crispEdges"><g fill="#0b1220">${cel.join('')}</g>${olho(0, 0)}${olho(n - 7, 0)}${olho(0, n - 7)}</svg>`;
  }
  paginas.pedido = async (q, codigo) => {
    const pedidos = guarda.ler('uniqee-pedidos', {});
    let p = pedidos[codigo];
    const email = q.email || p?.cliente.email;
    if (servidor && email && (!p || p.online)) {
      const hash = location.hash;
      app.innerHTML = `<div class="pagina"><div class="miolo"><div class="vazio">Buscando o pedido…</div></div></div>`;
      const r = await api(`api/pedidos/${encodeURIComponent(codigo)}?email=${encodeURIComponent(email)}`);
      if (location.hash !== hash) return;
      if (r.ok) { p = pedidos[codigo] = { ...r.dados, online: true }; guarda.gravar('uniqee-pedidos', pedidos); }
    }
    if (!p) {
      app.innerHTML = `<div class="pagina"><div class="miolo">${migalha('Pedido')}<div class="vazio">Não encontrei o pedido ${esc(codigo)} neste aparelho.<br><br><a href="#/acompanhar">Acompanhar por código e e-mail</a></div></div></div>`;
      return;
    }
    const etapas = etapasDo(p);
    const precisaFotos = p.itens.some(i => (i.detalhes || []).some(d => /WhatsApp/.test(d)));
    const pixCodigo = `00020126580014BR.GOV.BCB.PIX0136simulacao-uniqee-${p.codigo}5204000053039865406${p.total.toFixed(2)}5802BR`;
    const primeiroNome = p.cliente.nome.split(' ')[0];
    app.innerHTML = `<div class="pagina"><div class="miolo" style="max-width:860px">
      ${migalha('Pedido ' + esc(p.codigo))}
      <h1 class="titulo">${p.etapa === 0 ? `Quase lá, ${esc(primeiroNome)}!` : `Obrigado, ${esc(primeiroNome)}!`}</h1>
      <p class="sub">Pedido <b>${esc(p.codigo)}</b>, feito em ${new Date(p.data).toLocaleDateString('pt-BR')}. Guarde este código pra acompanhar.</p>
      <div style="display:grid;gap:14px">
        ${p.etapa === 0 && p.pagamento === 'pix' ? `
        <div class="caixa">
          <h2>Pague com Pix</h2>
          <div class="pix">
            <div class="qr">${qrFalso(pixCodigo)}</div>
            <div>
              <p style="margin:0 0 8px">Abra o app do seu banco, escolha Pix e leia o QR Code, ou copie o código abaixo. Total: <b style="color:var(--preco)">${brl(p.total)}</b></p>
              <div class="codigo-pix" id="pixCod">${pixCodigo}</div>
              <div class="linha" style="margin-top:10px"><button class="botao contorno" id="copiarPix">Copiar código</button></div>
            </div>
          </div>
          <p class="nota simulacao" style="margin:14px 0 0">Simulação: este código não cobra nada. <button class="botao leve" id="simularPago" style="padding:0">Simular pagamento aprovado</button></p>
        </div>` : ''}
        ${precisaFotos && p.etapa >= 1 ? `
        <div class="caixa" style="border:1.5px dashed var(--rose)">
          <h2>Mande as fotos do presente</h2>
          <p style="margin:0 0 12px;color:var(--tinta-2)">Alguns itens do seu pedido precisam das suas fotos. Mande pelo WhatsApp com o código do pedido.</p>
          <a class="botao zap" href="${zapUrl(`Olá! Sou ${p.cliente.nome}, do pedido ${p.codigo}. Vou mandar as fotos do presente.`)}" target="_blank" rel="noopener">${ICON.zap} Enviar as fotos</a>
        </div>` : ''}
        <div class="caixa">
          <h2>Andamento</h2>
          <ol class="linha-tempo">${etapas.map(([t, d], i) => `<li class="${i < p.etapa ? 'feito' : i === p.etapa ? 'atual' : ''}"><span class="bola">${i < p.etapa ? ICON.ok.replace('<svg', '<svg width="14" height="14"') : ''}</span><div><b>${t}</b>${i === p.etapa ? `<small>${d}</small>` : ''}</div></li>`).join('')}</ol>
          ${!p.online && p.etapa > 0 && p.etapa < etapas.length - 1 ? `<p class="nota simulacao" style="margin:4px 0 0">Simulação: <button class="botao leve" id="avancar" style="padding:0">avançar pra próxima etapa</button>. Na loja de verdade, quem avança é a Uniqee, pelo painel.</p>` : ''}
        </div>
        <div class="caixa resumo-lateral">
          <h2>Itens</h2>
          ${p.itens.map(i => `<div class="item-mini"><img src="${i.mockup || foto(i.img)}" alt=""><span>${i.qtd}x ${esc(i.nome)}${i.detalhes?.length ? `<br><small style="color:var(--tinta-2)">${i.detalhes.map(esc).join(' · ')}</small>` : ''}</span><b>${brl(i.preco * i.qtd)}</b></div>`).join('')}
          <div class="contas">
            <div><span>Produtos</span><span>${brl(p.subtotal)}</span></div>
            <div><span>${esc(p.frete.nome)}</span><span>${p.frete.valor ? brl(p.frete.valor) : 'Grátis'}</span></div>
            <div class="total"><span>Total</span><span>${brl(p.total)}</span></div>
          </div>
          <p style="font-size:14px;color:var(--tinta-2);margin:12px 0 0">Entrega: ${esc(p.endereco.rua)}, ${esc(p.endereco.numero)}${p.endereco.complemento ? ', ' + esc(p.endereco.complemento) : ''}, ${esc(p.endereco.bairro)}, ${esc(p.endereco.cidade)}/${esc(p.endereco.uf)}. Pagamento: ${p.pagamento === 'pix' ? 'Pix' : 'cartão de crédito'}.</p>
        </div>
        <a class="botao zap" href="${zapUrl(`Olá! Sou ${p.cliente.nome}, do pedido ${p.codigo}.`)}" target="_blank" rel="noopener" style="justify-self:start">${ICON.zap} Falar sobre este pedido</a>
      </div>
    </div></div>`;
    const salvar = () => { pedidos[p.codigo] = p; guarda.gravar('uniqee-pedidos', pedidos); paginas.pedido(q, codigo); };
    const simularNoServidor = async () => {
      const r = await api(`api/pedidos/${encodeURIComponent(p.codigo)}/simular-pagamento?email=${encodeURIComponent(p.cliente.email)}`, { method: 'POST' });
      if (r.ok) { Object.assign(p, r.dados); salvar(); } else avisar('Não consegui falar com a loja. Tente de novo.');
    };
    $('#copiarPix')?.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(pixCodigo); avisar('Código copiado.'); }
      catch { const r = document.createRange(); r.selectNodeContents($('#pixCod')); getSelection().removeAllRanges(); getSelection().addRange(r); avisar('Selecionei o código: é só copiar.'); }
    });
    $('#simularPago')?.addEventListener('click', () => { if (p.online) simularNoServidor(); else { p.etapa = 1; salvar(); } });
    $('#avancar')?.addEventListener('click', () => { p.etapa++; salvar(); });
  };

  paginas.acompanhar = () => {
    app.innerHTML = `<div class="pagina"><div class="miolo" style="max-width:560px">
      ${migalha('Acompanhar pedido')}
      <h1 class="titulo">Acompanhar pedido</h1>
      <p class="sub">Digite o código do pedido (começa com UQ-) e o e-mail usado na compra.</p>
      <form class="caixa" id="fAcomp">
        <div class="grupo"><label class="rot" for="aCod">Código do pedido</label><input class="campo" id="aCod" name="cod" placeholder="UQ-XXXXXX" required></div>
        <div class="grupo"><label class="rot" for="aEmail">E-mail</label><input class="campo" id="aEmail" name="email" type="email" required></div>
        <p class="erro-msg" id="eAcomp" hidden></p>
        <button class="botao rose cheio-largo">Ver andamento</button>
      </form>
    </div></div>`;
    $('#fAcomp').onsubmit = async (e) => {
      e.preventDefault();
      const cod = e.target.cod.value.trim().toUpperCase(), email = e.target.email.value.trim().toLowerCase();
      const p = guarda.ler('uniqee-pedidos', {})[cod];
      if (servidor && (await api(`api/pedidos/${encodeURIComponent(cod)}?email=${encodeURIComponent(email)}`)).ok) location.hash = `#/pedido/${cod}?email=${encodeURIComponent(email)}`;
      else if (p && p.cliente.email.toLowerCase() === email) location.hash = '#/pedido/' + cod;
      else { $('#eAcomp').hidden = false; $('#eAcomp').textContent = 'Não achei esse pedido com esse e-mail. Confira os dados ou chame a gente no WhatsApp.'; }
    };
  };

  // orçamento em passos
  const orc = { passo: 0, ocasiao: '', pecas: {}, ideia: '', arte: '', data: '', flexivel: false, entrega: '', cidade: '', nome: '' };
  const OCASIOES = [['Natal', ''], ['Aniversário', ''], ['Dia das Mães', ''], ['Dia dos Pais', ''], ['Dia dos Avós', ''], ['Namorados', ''], ['Formatura', ''], ['Casamento', 'lembrancinha'], ['Festa infantil', 'lembrancinha'], ['Empresa', 'brinde, fim de ano'], ['Igreja e grupos', 'encontro, retiro'], ['Outra', '']];
  const PECAS = ['Canecas', 'Azulejos', 'Camisetas', 'Squeezes', 'Almofadas', 'Ecobags', 'Copos', 'Kits', 'Outra peça'];
  paginas.orcamento = () => {
    const total = 6;
    const progresso = `<div class="progresso">${Array.from({ length: total }, (_, i) => `<span class="${i <= orc.passo ? 'on' : ''}"></span>`).join('')}</div>`;
    const navega = (podeVoltar = true, rotulo = 'Continuar') => `<div class="navega">${podeVoltar && orc.passo > 0 ? '<button class="botao contorno" data-nav="-1">Voltar</button>' : '<span></span>'}<button class="botao rose" data-nav="1">${rotulo}</button></div>`;
    let corpo = '';
    if (orc.passo === 0) corpo = `<h2 class="titulo" style="font-size:24px">Pra qual ocasião?</h2><div class="escolhas">${OCASIOES.map(([o, s]) => `<button class="escolha" data-oc="${o}" aria-pressed="${orc.ocasiao === o}">${o}${s ? `<small>${s}</small>` : ''}</button>`).join('')}</div>${navega(false)}`;
    if (orc.passo === 1) corpo = `<h2 class="titulo" style="font-size:24px">Quais peças e quantas?</h2><p class="sub">Marque as peças e ajuste a quantidade de cada uma.</p>
      ${PECAS.map(pc => `<div class="peca-qtd ${orc.pecas[pc] ? 'on' : ''}"><label class="check" style="color:var(--marrom);font-size:16px;font-weight:500"><input type="checkbox" data-pc="${pc}" ${orc.pecas[pc] ? 'checked' : ''}><span>${pc}</span></label><div class="qtd"><button data-pm="${pc}" data-d="-1" aria-label="Menos">−</button><input data-pq="${pc}" value="${orc.pecas[pc] || 0}" inputmode="numeric" aria-label="Quantidade de ${pc}"><button data-pm="${pc}" data-d="1" aria-label="Mais">+</button></div></div>`).join('')}${navega()}`;
    if (orc.passo === 2) corpo = `<h2 class="titulo" style="font-size:24px">Como você imagina?</h2><p class="sub">Conte a ideia: tema, cores, frase, nomes. Quanto mais detalhe, mais certeiro o orçamento.</p>
      <textarea class="campo" id="oIdeia" maxlength="600" placeholder="Ex.: canecas brancas com a foto da turma e a frase Formandos 2026, letra dourada">${esc(orc.ideia)}</textarea>
      <div class="rot" style="margin-top:16px">Sobre a arte</div>
      ${['Já tenho a foto ou a arte pronta', 'Quero que vocês criem a arte', 'Ainda não sei'].map(a => `<label class="radio-card"><input type="radio" name="arte" value="${a}" ${orc.arte === a ? 'checked' : ''}><span class="t"><b>${a}</b></span></label>`).join('')}${navega()}`;
    if (orc.passo === 3) corpo = `<h2 class="titulo" style="font-size:24px">Pra quando você precisa?</h2><p class="sub">A produção leva até ${CONFIG.prazoProducao} dias úteis, mais a entrega. Pedido grande pode precisar de mais tempo.</p>
      <div class="grupo"><input class="campo" type="date" id="oData" value="${orc.data}" style="max-width:240px"></div>
      <label class="check"><input type="checkbox" id="oFlex" ${orc.flexivel ? 'checked' : ''}><span>A data é flexível</span></label>${navega()}`;
    if (orc.passo === 4) corpo = `<h2 class="titulo" style="font-size:24px">Como vai receber?</h2>
      ${['Retirar em Sousa', 'Entrega em Sousa', 'Enviar pra outra cidade'].map(a => `<label class="radio-card"><input type="radio" name="ent" value="${a}" ${orc.entrega === a ? 'checked' : ''}><span class="t"><b>${a}</b></span></label>`).join('')}
      <div class="grupo" id="oCidadeG" ${orc.entrega === 'Enviar pra outra cidade' ? '' : 'hidden'}><label class="rot" for="oCidade">Cidade e estado</label><input class="campo" id="oCidade" value="${esc(orc.cidade)}" placeholder="Ex.: Recife/PE"></div>${navega()}`;
    if (orc.passo === 5) {
      const msg = mensagemOrcamento();
      corpo = `<h2 class="titulo" style="font-size:24px">Tudo pronto!</h2><p class="sub">Confira a mensagem e envie pelo WhatsApp. A gente responde com o valor e o prazo.</p>
        <div class="grupo"><label class="rot" for="oNome">Seu nome</label><input class="campo" id="oNome" value="${esc(orc.nome)}" autocomplete="name"></div>
        <div class="msg-pronta" id="oMsg">${esc(msg)}</div>
        <div class="navega"><button class="botao contorno" data-nav="-1">Voltar</button><a class="botao zap" id="oEnviar" href="${zapUrl(msg)}" target="_blank" rel="noopener">${ICON.zap} Enviar pelo WhatsApp</a></div>`;
    }
    app.innerHTML = `<div class="pagina"><div class="miolo assistente">
      ${migalha('Orçamento')}
      <h1 class="titulo">Monte seu orçamento</h1>
      <p class="sub">Seis perguntas rápidas. No fim, a mensagem vai pronta pro nosso WhatsApp.</p>
      ${progresso}<div class="caixa" style="padding:22px">${corpo}<p class="erro-msg" id="oErro" hidden></p></div>
    </div></div>`;

    $$('[data-oc]').forEach(b => b.onclick = () => { orc.ocasiao = b.dataset.oc; paginas.orcamento(); });
    $$('[data-pc]').forEach(c => c.onchange = () => { orc.pecas[c.dataset.pc] = c.checked ? Math.max(1, orc.pecas[c.dataset.pc] || 10) : 0; paginas.orcamento(); });
    $$('[data-pm]').forEach(b => b.onclick = () => { const k = b.dataset.pm; orc.pecas[k] = Math.max(0, Math.min(9999, (orc.pecas[k] || 0) + +b.dataset.d)); paginas.orcamento(); });
    $$('[data-pq]').forEach(i => i.onchange = () => { orc.pecas[i.dataset.pq] = Math.max(0, Math.min(9999, parseInt(i.value) || 0)); paginas.orcamento(); });
    $$('[name=ent]').forEach(r => r.onchange = () => { orc.entrega = r.value; $('#oCidadeG').hidden = r.value !== 'Enviar pra outra cidade'; });
    const nome = $('#oNome');
    if (nome) nome.oninput = () => { orc.nome = nome.value; const m = mensagemOrcamento(); $('#oMsg').textContent = m; $('#oEnviar').href = zapUrl(m); };
    $$('[data-nav]').forEach(b => b.onclick = () => {
      const d = +b.dataset.nav;
      // guarda o que foi digitado antes de trocar de passo
      if ($('#oIdeia')) orc.ideia = $('#oIdeia').value.trim();
      const arte = $('[name=arte]:checked'); if (arte) orc.arte = arte.value;
      if ($('#oData')) { orc.data = $('#oData').value; orc.flexivel = $('#oFlex').checked; }
      if ($('#oCidade')) orc.cidade = $('#oCidade').value.trim();
      if (d > 0) {
        const erro = [
          () => !orc.ocasiao && 'Escolha a ocasião.',
          () => !Object.values(orc.pecas).some(v => v > 0) && 'Marque pelo menos uma peça.',
          () => !orc.ideia && 'Conte um pouco da ideia.',
          () => !orc.data && !orc.flexivel && 'Informe a data ou marque que é flexível.',
          () => (!orc.entrega && 'Escolha como vai receber.') || (orc.entrega === 'Enviar pra outra cidade' && !orc.cidade && 'Informe a cidade.'),
        ][orc.passo]?.();
        if (erro) { $('#oErro').hidden = false; $('#oErro').textContent = erro; return; }
      }
      orc.passo = Math.max(0, Math.min(5, orc.passo + d));
      paginas.orcamento();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  };
  function mensagemOrcamento() {
    const pecas = Object.entries(orc.pecas).filter(([, v]) => v > 0).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(', ');
    const data = orc.data ? new Date(orc.data + 'T12:00').toLocaleDateString('pt-BR') : '';
    return [
      'Olá, Uniqee! Quero um orçamento.', '',
      `*Ocasião:* ${orc.ocasiao}`,
      `*Peças:* ${pecas}`,
      `*Ideia:* ${orc.ideia}`,
      orc.arte ? `*Arte:* ${orc.arte}` : null,
      `*Pra quando:* ${[data, orc.flexivel && 'data flexível'].filter(Boolean).join(', ')}`,
      `*Entrega:* ${orc.entrega}${orc.entrega === 'Enviar pra outra cidade' && orc.cidade ? ` (${orc.cidade})` : ''}`,
      orc.nome.trim() ? `*Nome:* ${orc.nome.trim()}` : null,
      '', '(enviado pelo site)',
    ].filter(l => l !== null).join('\n');
  }

  // páginas de texto
  const REVISAR = '<p class="revisar">Rascunho: revisar com contador ou advogado antes de publicar, principalmente o direito de arrependimento nos produtos personalizados e a identificação de quem vende.</p>';
  const TEXTOS = {
    sobre: ['Sobre a Uniqee', `
      <p>A Uniqee nasceu em Sousa, no sertão da Paraíba, a cidade dos dinossauros, com uma ideia simples: presente bom é presente que conta uma história.</p>
      <p>A gente transforma foto, nome, data e aquela frase que só vocês entendem em canecas, azulejos, camisetas, squeezes, almofadas e kits. Cada peça é feita aqui, uma por uma, com sublimação, DTF ou impressão 3D, e passa pelas nossas mãos antes de chegar nas suas.</p>
      <p>Mais do que a técnica, o que importa pra gente é a emoção de quem recebe. Por isso você aprova a arte antes de produzir, e por isso cada presente sai embalado pra ser entregue.</p>
      <h2>Fale com a gente</h2>
      <p>WhatsApp ${CONFIG.zapVisivel} · Instagram <a href="https://instagram.com/${CONFIG.instagram}" target="_blank" rel="noopener">@${CONFIG.instagram}</a> · Sousa, Paraíba.</p>`],
    'como-comprar': ['Como comprar', `
      <h2>1. Escolha o presente</h2><p>Procure pela ocasião (Natal, Avós, Mães…), pela peça ou pela busca. Toque no presente pra ver fotos, preço e detalhes.</p>
      <h2>2. Personalize</h2><p>Nas peças com provador (caneca, azulejo e camiseta), você envia a foto, escreve o texto e vê como fica antes de pôr no carrinho. Nas outras, você escreve o nome ou a frase e manda as fotos pelo WhatsApp depois da compra.</p>
      <h2>3. Finalize</h2><p>No carrinho, informe seus dados e o CEP. O frete aparece na hora. Pague com Pix (aprovação imediata) ou cartão de crédito, pelo Mercado Pago.</p>
      <h2>4. Aprove a arte</h2><p>Antes de produzir, a gente manda a arte pelo WhatsApp pra você conferir. Só depois do seu ok o presente vai pra produção.</p>
      <h2>5. Receba</h2><p>A produção leva até ${CONFIG.prazoProducao} dias úteis depois do pagamento, mais o prazo da entrega. Em Sousa, a entrega ou a retirada é combinada com a gente, sem taxa. Você acompanha tudo pela página do pedido, com o código que começa com UQ-.</p>
      <h2>Pedido grande ou peça diferente?</h2><p><a href="#/orcamento">Monte um orçamento</a> e a gente responde pelo WhatsApp.</p>`],
    trocas: ['Trocas e devoluções', `${REVISAR}
      <h2>Produto com defeito</h2><p>Se o presente chegar com defeito de fabricação, avise a gente em até 90 dias do recebimento, com fotos. A gente refaz a peça ou devolve o valor pago, como você preferir.</p>
      <h2>Erro na personalização</h2><p>Se a peça sair diferente da arte que você aprovou, a gente refaz sem custo. Se o erro estiver na informação que foi aprovada (um nome escrito errado na arte aprovada, por exemplo), a refação é cobrada.</p>
      <h2>Dano no transporte</h2><p>Se a embalagem chegar violada ou a peça quebrada, recuse a entrega quando possível ou avise a gente em até 7 dias, com fotos da caixa e da peça.</p>
      <h2>Desistência da compra</h2><p>Compras feitas pela internet podem ser canceladas em até 7 dias do recebimento, como garante o Código de Defesa do Consumidor (art. 49). Pra produtos personalizados, feitos com a sua foto e o seu texto, o pedido de cancelamento antes da produção é atendido com devolução integral.</p>
      <h2>Como pedir</h2><p>Fale com a gente pelo WhatsApp ${CONFIG.zapVisivel}, com o código do pedido.</p>`],
    privacidade: ['Política de privacidade', `${REVISAR}
      <p>Esta política explica que dados a Uniqee recebe quando você compra, pra que eles servem e como você pode pedir que sejam apagados, conforme a Lei Geral de Proteção de Dados (Lei 13.709/2018).</p>
      <h2>O que a gente recebe</h2><ul><li>Nome, e-mail, WhatsApp e CPF, pra identificar o pedido, emitir a cobrança e falar com você.</li><li>Endereço, pra calcular o frete e entregar.</li><li>Fotos, textos e artes da personalização, só pra produzir o seu presente.</li></ul>
      <h2>Com quem compartilha</h2><ul><li>Mercado Pago, pra processar o pagamento.</li><li>Melhor Envio e a transportadora escolhida, pra entregar.</li></ul><p>A gente não vende nem empresta seus dados.</p>
      <h2>Suas fotos</h2><p>As fotos que você envia são usadas só pra fazer o seu presente. A gente não publica nenhuma foto sua nem a peça com a sua foto sem a sua autorização. Os arquivos são apagados em até 90 dias depois da entrega.</p>
      <h2>Armazenamento no navegador</h2><p>O site guarda no seu próprio navegador o carrinho e os dados do último pedido, pra você não precisar digitar de novo. Não usamos cookies de propaganda.</p>
      <h2>Seus direitos</h2><p>Você pode pedir pra ver, corrigir ou apagar seus dados a qualquer momento, pelo WhatsApp ${CONFIG.zapVisivel}.</p>`],
    termos: ['Termos de uso', `${REVISAR}
      <h2>Imagens enviadas</h2><p>Ao enviar uma foto ou arte, você confirma que ela é sua ou que tem autorização pra usar. A Uniqee pode recusar um pedido com imagem que desrespeite direitos de terceiros, com devolução do valor.</p>
      <h2>Cores e aparência</h2><p>O provador mostra uma simulação. As cores impressas podem variar um pouco em relação à tela do celular ou do computador.</p>
      <h2>Prazos</h2><p>O prazo de produção conta a partir da confirmação do pagamento e da aprovação da arte. O prazo de entrega é o informado pela transportadora.</p>
      <h2>Preços</h2><p>Os preços podem mudar sem aviso, mas o pedido já pago vale pelo preço da compra.</p>`],
  };
  paginas.texto = (q, chave) => {
    const [titulo, html] = TEXTOS[chave];
    app.innerHTML = `<div class="pagina"><div class="miolo texto-longo">${migalha(titulo)}<h1 class="titulo">${titulo}</h1>${html}</div></div>`;
  };

  paginas.naoEncontrada = () => {
    app.innerHTML = `<div class="pagina"><div class="miolo"><div class="vazio"><h1 class="titulo">Página não encontrada</h1><p>O endereço pode ter mudado.</p><a class="botao rose" href="#/" style="color:#fff">Voltar ao início</a></div></div></div>`;
  };

  // ---------- rotas ----------
  function rota() {
    if (provadorAtivo) { provadorAtivo.desmontar(); provadorAtivo = null; }
    const [caminho, busca = ''] = (location.hash.slice(1) || '/').split('?');
    const q = Object.fromEntries(new URLSearchParams(busca));
    const partes = caminho.split('/').filter(Boolean);
    const [p0, p1] = partes;
    fecharGaveta();
    toast.classList.remove('on');
    $('#menu').classList.remove('aberto');
    $$('header.cab nav a').forEach(a => a.removeAttribute('aria-current'));
    const atual = $(`header.cab nav a[href^="#/${p0 || ''}"]`); if (p0 && atual) atual.setAttribute('aria-current', 'page');
    if (!p0) paginas.inicio(q);
    else if (p0 === 'presentes') paginas.presentes(q);
    else if (p0 === 'produto') paginas.produto(q, p1);
    else if (p0 === 'personalizar') paginas.personalizar(q, p1);
    else if (p0 === 'finalizar') paginas.finalizar(q);
    else if (p0 === 'pedido') paginas.pedido(q, p1);
    else if (p0 === 'acompanhar') paginas.acompanhar(q);
    else if (p0 === 'orcamento') paginas.orcamento(q);
    else if (TEXTOS[p0]) paginas.texto(q, p0);
    else paginas.naoEncontrada();
    if (!q.s) window.scrollTo(0, 0);
    document.title = ($('h1', app)?.textContent.trim() || 'Uniqee') + ' · Uniqee Personalizados';
    if (!p0) document.title = 'Uniqee Personalizados · Presentes que contam histórias';
  }
  window.addEventListener('hashchange', rota);

  // cabeçalho, rodapé e WhatsApp
  $('#formBuscaCab').onsubmit = (e) => { e.preventDefault(); location.hash = '#/presentes?q=' + encodeURIComponent(e.target.q.value.trim()); };
  $('#botaoMenu').onclick = () => $('#menu').classList.toggle('aberto');
  $$('[data-zap]').forEach(a => { a.href = zapUrl(a.dataset.zap); a.target = '_blank'; a.rel = 'noopener'; });
  $('#ano').textContent = new Date().getFullYear();
  desenharGaveta();
  carregarCatalogo().finally(rota);
})();
