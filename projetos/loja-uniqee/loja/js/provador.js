// Provador: o cliente envia a foto, escreve o texto e vê a peça pronta.
// Provador.montar(elemento, { tipo, produto, aoAdicionar }) devolve { desmontar }.
// Medidas em centímetro, as mesmas da /ajustar-arte e das preferências.
window.Provador = (function () {
  const TIPOS = {
    caneca: {
      area: { w: 21, h: 9.8 }, tituloCor: 'Fundo da caneca', rotuloCor: 'Fundo', dica: 'Arraste pra girar a caneca', corPadrao: '#ffffff', fundo: true,
      cores: [['Branco', '#ffffff'], ['Creme', '#f3ebe2'], ['Rosa clarinho', '#fdf0e9'], ['Rosé', '#c57e84'], ['Azul', '#cfe2ea'], ['Petróleo', '#457981'], ['Preto', '#1c1c1e']],
      texto: { y: .3, tam: 1.8 }, alturaEditor: 260, lados: ['frente'],
    },
    camiseta: {
      area: { w: 28, h: 35 }, tituloCor: 'Cor da camiseta', rotuloCor: 'Cor', dica: '', corPadrao: '#f4f4f2', fundo: false,
      cores: [['Branca', '#f4f4f2'], ['Preta', '#111113'], ['Cinza mescla', '#b3b5b8'], ['Azul-marinho', '#1d2740'], ['Verde-militar', '#4a5032'], ['Off-white', '#ece4d4']],
      texto: { y: .36, tam: 3.4 }, alturaEditor: 380, lados: ['frente', 'costas'],
    },
    azulejo: {
      area: { w: 15.7, h: 15.7 }, tituloCor: 'Fundo do azulejo', rotuloCor: 'Fundo', dica: 'Azulejo 15x15 no suporte', corPadrao: '#ffffff', fundo: true,
      cores: [['Branco', '#ffffff'], ['Creme', '#f3ebe2'], ['Rosa clarinho', '#fdf0e9'], ['Rosé', '#c57e84'], ['Azul', '#cfe2ea'], ['Preto', '#1c1c1e']],
      texto: { y: .36, tam: 1.6 }, alturaEditor: 320, lados: ['frente'],
    },
  };
  // Onde fica a área de impressão nas fotos da camiseta (js/camiseta-fotos.js), medido numa escala de 1000 px:
  // cx é o centro, topo é o começo da estampa e k é quantos pixels valem 1 cm.
  const FOTOS_CAMISA = {
    frente: { cx: 495, topo: 200, k: 8.6 },
    costas: { cx: 493, topo: 165, k: 8.6 },
  };
  const FONTES = [
    { id: 'Caveat', nome: 'Manuscrita', css: '700 {px} "Caveat"' },
    { id: 'Radio Canada Big', nome: 'Moderna', css: '700 {px} "Radio Canada Big"' },
    { id: 'Playfair Display', nome: 'Elegante', css: 'italic 600 {px} "Playfair Display"' },
  ];
  const CORES_TEXTO = [
    ['Azul-noite', '#0b1220'], ['Marrom café', '#5e5045'], ['Rosé', '#c57e84'],
    ['Branco', '#ffffff'], ['Petróleo', '#457981'], ['Dourado', '#b8892b'],
  ];
  const NOME_LADO = { frente: 'Frente', costas: 'Costas' };
  const ICONE_ENVIAR = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>';

  // ---------- camiseta: fotos, mapas de sombra e de brilho (carregados uma vez) ----------
  let camisaPronta = null;
  function carregarCamisa() {
    if (camisaPronta) return camisaPronta;
    camisaPronta = Promise.all(Object.entries(FOTOS_CAMISA).map(async ([lado, f]) => {
      const img = new Image(); img.src = window.UNIQEE_CAMISA[lado]; await img.decode();
      const N = img.naturalWidth;
      const base = document.createElement('canvas'); base.width = base.height = N;
      const bg = base.getContext('2d'); bg.drawImage(img, 0, 0);
      const px = bg.getImageData(0, 0, N, N).data;
      // sombra: o branco da foto vira 1 e as dobras escurecem um pouco mais que no original
      const sombra = document.createElement('canvas'); sombra.width = sombra.height = N;
      const brilho = document.createElement('canvas'); brilho.width = brilho.height = N;
      const sd = sombra.getContext('2d').createImageData(N, N), hd = brilho.getContext('2d').createImageData(N, N);
      for (let i = 0; i < px.length; i += 4) {
        const l = (.299 * px[i] + .587 * px[i + 1] + .114 * px[i + 2]) / 255;
        const s = Math.max(0, Math.min(1, 1 - (0.97 - l) * 1.35)) * 255;
        sd.data[i] = sd.data[i + 1] = sd.data[i + 2] = s; sd.data[i + 3] = px[i + 3];
        hd.data[i] = hd.data[i + 1] = hd.data[i + 2] = 255;
        hd.data[i + 3] = px[i + 3] * Math.max(0, Math.min(1, (l - .80) * 4.5));
      }
      sombra.getContext('2d').putImageData(sd, 0, 0);
      brilho.getContext('2d').putImageData(hd, 0, 0);
      return [lado, { ...f, N, base, sombra, brilho }];
    })).then(Object.fromEntries);
    return camisaPronta;
  }
  const luminancia = (hex) => { const n = parseInt(hex.slice(1), 16); return ((n >> 16) * .299 + ((n >> 8) & 255) * .587 + (n & 255) * .114) / 255; };

  function montar(raiz, { tipo, produto, aoAdicionar }) {
    const T = TIPOS[tipo];
    const A = T.area;
    const brl = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const opcoesProduto = produto.opcoes || [];
    const ehCamisa = tipo === 'camiseta';

    raiz.innerHTML = `
      <div class="prov-grade">
        <div>
          <div class="prov-palco${ehCamisa ? ' escuro' : ''}" role="img" aria-label="Como vai ficar">
            <div class="prov-vista prov-3d" data-v="3d" hidden><div class="carregando">Preparando a caneca…</div></div>
            <canvas class="prov-vista" data-v="camisa" hidden></canvas>
            <div class="prov-vista prov-azulejo" data-v="azulejo" hidden><div class="placa"><canvas></canvas><div class="suporte"><i></i><i></i></div></div></div>
            ${T.lados.length > 1 ? `<div class="lados" role="tablist">${T.lados.map(l => `<button role="tab" data-lado="${l}" aria-selected="${l === 'frente'}">${NOME_LADO[l]}</button>`).join('')}</div>` : ''}
            ${T.dica ? `<p class="dica">${T.dica}</p>` : ''}
          </div>
          ${ehCamisa ? '<div class="miniaturas" data-c="miniaturas"></div>' : ''}
        </div>
        <div class="prov-painel">
          ${ehCamisa ? `<div class="prov-passo prov-cabeca">
            <h1>${produto.nome}</h1>
            <div class="preco"><b>${brl(produto.preco)}</b><small>no Pix</small></div>
            <div class="rotulo-peq">COR <span data-c="nomeCor"></span></div>
            <div class="cores-chip" data-c="coresPeca"></div>
            ${opcoesProduto.map((o, i) => `<div class="rotulo-peq">${o.nome.toUpperCase()}</div><div class="opcoes-lista" data-opcao="${i}">${o.valores.map(v => `<button class="opcao" data-v="${v}" aria-pressed="false">${v}</button>`).join('')}</div>`).join('')}
          </div>` : ''}
          <div class="prov-passo">
            <h2><span>1</span> Sua foto${ehCamisa ? ` <em class="lado-atual" data-c="ladoAtual">na frente</em>` : ''}</h2>
            <div class="linha">
              <label class="botao rose enviar"><input type="file" data-c="arquivo" accept="image/*">${ICONE_ENVIAR} Enviar foto</label>
              <button class="botao leve" data-c="exemplo">Usar foto de exemplo</button>
            </div>
            <div class="qualidade" data-c="qualidade" role="status"><i></i><span></span></div>
            <div class="editor-caixa"><canvas class="prov-editor" data-c="editor" aria-label="Área de impressão"></canvas></div>
            <p class="medida">Área de impressão: ${String(A.w).replace('.', ',')} x ${String(A.h).replace('.', ',')} cm. Arraste pra posicionar; com dois dedos, aumenta e gira.</p>
            <div class="ajustes" data-c="ajustes" hidden>
              <label class="ajuste">Tamanho <input type="range" data-c="zoom" min="0.3" max="3" step="0.01" value="1"></label>
              <label class="ajuste">Girar <input type="range" data-c="giro" min="-180" max="180" step="1" value="0"></label>
              <div class="linha">
                <button class="botao contorno" data-c="preencher">Preencher a área</button>
                <button class="botao contorno" data-c="encaixar">Mostrar inteira</button>
                <button class="botao leve" data-c="remover">Tirar a foto</button>
              </div>
            </div>
          </div>
          <div class="prov-passo">
            <h2><span>2</span> Nome ou frase</h2>
            <input class="campo" data-c="texto" maxlength="30" placeholder="Ex.: Pra sempre minha mãe" autocomplete="off">
            <div class="rotulo-peq">Letra</div>
            <div class="linha" data-c="fontes"></div>
            <div class="rotulo-peq">Cor da letra</div>
            <div class="linha" data-c="coresTexto"></div>
            <div class="ajustes"><label class="ajuste">Tamanho <input type="range" data-c="tamTexto" min="0.8" max="6" step="0.05"></label></div>
          </div>
          ${ehCamisa ? '' : `<div class="prov-passo">
            <h2><span>3</span> ${T.tituloCor}${opcoesProduto.length ? ' e tamanho' : ''}</h2>
            <div class="cores-chip" data-c="coresPeca"></div>
            ${opcoesProduto.map((o, i) => `<div class="rotulo-peq">${o.nome}</div><div class="opcoes-lista" data-opcao="${i}">${o.valores.map(v => `<button class="opcao" data-v="${v}" aria-pressed="false">${v}</button>`).join('')}</div>`).join('')}
          </div>`}
          <div class="prov-passo prov-final">
            ${ehCamisa ? '' : `<div class="preco-prov"><span>${produto.nome}</span><b>${brl(produto.preco)}</b></div>`}
            <div class="linha" style="justify-content:space-between">
              <span class="rot" style="margin:0">Quantidade</span>
              <div class="qtd"><button data-c="menos" aria-label="Menos">−</button><input data-c="qtd" type="number" min="1" max="99" value="1" aria-label="Quantidade"><button data-c="mais" aria-label="Mais">+</button></div>
            </div>
            <label class="check"><input type="checkbox" data-c="termo"><span>A imagem é minha ou tenho autorização pra usar. Fotos com personagem ou marca de terceiros não podem ser impressas.</span></label>
            <p class="erro-msg" data-c="falta" hidden></p>
            <button class="botao rose cheio-largo" data-c="adicionar">Adicionar ao carrinho</button>
          </div>
        </div>
      </div>`;

    const q = (c) => raiz.querySelector(`[data-c="${c}"]`);
    const vista3d = raiz.querySelector('[data-v="3d"]');
    const vc = raiz.querySelector('[data-v="camisa"]');
    const vAz = raiz.querySelector('[data-v="azulejo"]');
    const azCanvas = vAz.querySelector('canvas');
    ({ caneca: vista3d, camiseta: vc, azulejo: vAz })[tipo].hidden = false;

    // cada lado da peça tem a sua arte; cor, tamanho e quantidade são da peça
    const novaArte = () => ({ foto: null, fx: 0, fy: 0, fs: 1, fr: 0, texto: '', fonte: 'Caveat', corTexto: '#5e5045', tam: T.texto.tam, tx: 0, ty: A.h * T.texto.y });
    const artes = Object.fromEntries(T.lados.map(l => [l, novaArte()]));
    let lado = 'frente', st = artes.frente;
    const peca = { cor: T.corPadrao, opcoes: {} };
    const temArte = (a) => !!(a.foto || a.texto.trim());

    // ---------- desenho da estampa ----------
    const fonteCss = (a, px) => FONTES.find(f => f.id === a.fonte).css.replace('{px}', px.toFixed(2) + 'px');
    const larg = (img) => img.naturalWidth || img.width;
    const alt = (img) => img.naturalHeight || img.height;
    function medidaFoto(a = st) {
      const f = a.foto, cover = Math.max(A.w / f.nw, A.h / f.nh);
      return { w: f.nw * cover * a.fs, h: f.nh * cover * a.fs, cmPorPx: cover * a.fs };
    }
    function desenharEstampa(ctx, ox, oy, k, { fundo = true, full = false, arte = st } = {}) {
      const a = arte;
      ctx.save();
      ctx.beginPath(); ctx.rect(ox, oy, A.w * k, A.h * k); ctx.clip();
      if (fundo && T.fundo) { ctx.fillStyle = peca.cor; ctx.fillRect(ox, oy, A.w * k, A.h * k); }
      if (a.foto) {
        const m = medidaFoto(a);
        ctx.save();
        ctx.translate(ox + (A.w / 2 + a.fx) * k, oy + (A.h / 2 + a.fy) * k);
        ctx.rotate(a.fr * Math.PI / 180);
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(full ? a.foto.full : a.foto.prev, -m.w * k / 2, -m.h * k / 2, m.w * k, m.h * k);
        ctx.restore();
      }
      if (a.texto.trim()) {
        ctx.font = fonteCss(a, a.tam * k);
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillStyle = a.corTexto;
        ctx.fillText(a.texto, ox + (A.w / 2 + a.tx) * k, oy + (A.h / 2 + a.ty) * k);
      }
      ctx.restore();
    }
    function caixaTexto() {
      if (!st.texto.trim()) return null;
      const c = document.createElement('canvas').getContext('2d');
      c.font = fonteCss(st, 100);
      const w = c.measureText(st.texto).width / 100 * st.tam, h = st.tam * 0.9;
      return { x: st.tx - w / 2, y: st.ty - h / 2, w, h };
    }

    // ---------- editor 2D ----------
    const ed = q('editor'), edc = ed.getContext('2d');
    let ek = 1, alvo = null;
    function medirEditor() {
      const caixa = ed.parentElement.clientWidth - 20;
      if (caixa <= 0) return;
      ek = Math.min(caixa / A.w, T.alturaEditor / A.h);
      const dpr = window.devicePixelRatio || 1;
      ed.style.width = Math.round(A.w * ek) + 'px';
      ed.style.height = Math.round(A.h * ek) + 'px';
      ed.width = Math.round(A.w * ek * dpr); ed.height = Math.round(A.h * ek * dpr);
      edc.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function desenharEditor() {
      const W = A.w * ek, H = A.h * ek;
      edc.clearRect(0, 0, W, H);
      edc.fillStyle = peca.cor; edc.fillRect(0, 0, W, H);
      desenharEstampa(edc, 0, 0, ek);
      if (!temArte(st)) {
        edc.fillStyle = luminancia(peca.cor) < .45 ? 'rgba(255,255,255,.6)' : 'rgba(15,23,42,.45)';
        edc.font = '500 15px "Radio Canada Big"';
        edc.textAlign = 'center'; edc.textBaseline = 'middle';
        edc.fillText(ehCamisa && lado === 'costas' ? 'Toque aqui pra estampar as costas' : 'Toque aqui pra enviar sua foto', W / 2, H / 2);
      }
      if (alvo === 'texto') {
        const b = caixaTexto();
        if (b) {
          edc.save(); edc.setLineDash([5, 4]); edc.strokeStyle = '#c57e84'; edc.lineWidth = 1.5;
          edc.strokeRect((A.w / 2 + b.x) * ek - 4, (A.h / 2 + b.y) * ek - 4, b.w * ek + 8, b.h * ek + 8);
          edc.restore();
        }
      }
      if (tipo === 'caneca') {
        edc.fillStyle = 'rgba(15,23,42,.05)';
        edc.fillRect(0, 0, 1.2 * ek, H); edc.fillRect(W - 1.2 * ek, 0, 1.2 * ek, H);
      }
      edc.strokeStyle = 'rgba(15,23,42,.25)'; edc.lineWidth = 1; edc.strokeRect(.5, .5, W - 1, H - 1);
    }
    const toques = new Map();
    let gesto = null;
    function emCm(e) {
      const r = ed.getBoundingClientRect();
      return { x: (e.clientX - r.left) / ek - A.w / 2, y: (e.clientY - r.top) / ek - A.h / 2 };
    }
    ed.addEventListener('pointerdown', (e) => {
      ed.setPointerCapture(e.pointerId);
      toques.set(e.pointerId, emCm(e));
      if (toques.size === 1) {
        const p = emCm(e), b = caixaTexto();
        const noTexto = b && p.x >= b.x - .6 && p.x <= b.x + b.w + .6 && p.y >= b.y - .6 && p.y <= b.y + b.h + .6;
        alvo = noTexto ? 'texto' : (st.foto ? 'foto' : null);
        if (!alvo) { q('arquivo').click(); return; }
        gesto = { tipo: 'mover', p, ox: alvo === 'texto' ? st.tx : st.fx, oy: alvo === 'texto' ? st.ty : st.fy };
      } else if (toques.size === 2) {
        const [a, b] = [...toques.values()];
        const d = Math.hypot(b.x - a.x, b.y - a.y);
        gesto = alvo === 'texto' ? { tipo: 'pinca-texto', d, tam: st.tam }
          : { tipo: 'pinca', d, ang: Math.atan2(b.y - a.y, b.x - a.x), fs: st.fs, fr: st.fr };
      }
      atualizar();
    });
    ed.addEventListener('pointermove', (e) => {
      if (!toques.has(e.pointerId) || !gesto) return;
      toques.set(e.pointerId, emCm(e));
      if (gesto.tipo === 'mover' && toques.size === 1) {
        const p = emCm(e);
        const nx = gesto.ox + p.x - gesto.p.x, ny = gesto.oy + p.y - gesto.p.y;
        if (alvo === 'texto') { st.tx = nx; st.ty = ny; } else { st.fx = nx; st.fy = ny; }
      } else if (toques.size === 2) {
        const [a, b] = [...toques.values()];
        const d = Math.hypot(b.x - a.x, b.y - a.y);
        if (gesto.tipo === 'pinca') {
          st.fs = Math.min(3, Math.max(.3, gesto.fs * d / gesto.d));
          st.fr = ((gesto.fr + (Math.atan2(b.y - a.y, b.x - a.x) - gesto.ang) * 180 / Math.PI + 540) % 360) - 180;
          q('zoom').value = st.fs; q('giro').value = st.fr;
        } else if (gesto.tipo === 'pinca-texto') {
          st.tam = Math.min(6, Math.max(.8, gesto.tam * d / gesto.d));
          q('tamTexto').value = st.tam;
        }
      }
      atualizar();
    });
    const soltar = (e) => {
      toques.delete(e.pointerId);
      if (toques.size === 0) gesto = null;
      else if (toques.size === 1 && gesto) {
        const p = [...toques.values()][0];
        gesto = { tipo: 'mover', p, ox: alvo === 'texto' ? st.tx : st.fx, oy: alvo === 'texto' ? st.ty : st.fy };
      }
    };
    ed.addEventListener('pointerup', soltar);
    ed.addEventListener('pointercancel', soltar);

    // ---------- caneca em 3D (three.js só carrega quando a peça é caneca) ----------
    let tres = null;
    async function iniciarCaneca() {
      const THREE = await import('three');
      const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
      const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
      if (desmontado) return;
      const R = 4.1, H = 9.6, VOLTA = 2 * Math.PI * R, TW = 2048, TH = Math.round(TW * H / VOLTA);
      const texCanvas = document.createElement('canvas'); texCanvas.width = TW; texCanvas.height = TH;
      const texCtx = texCanvas.getContext('2d');
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      const cena = new THREE.Scene();
      cena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
      cena.environmentIntensity = 0.9;
      const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);
      const ang0 = Math.PI + 1.0;
      camera.position.set(Math.sin(ang0) * 33, 7, Math.cos(ang0) * 33);
      const controles = new OrbitControls(camera, renderer.domElement);
      controles.enablePan = false; controles.minDistance = 20; controles.maxDistance = 45;
      controles.minPolarAngle = 0.35; controles.maxPolarAngle = 1.75;
      controles.target.set(0, -0.3, 1.2); controles.update();
      const tex = new THREE.CanvasTexture(texCanvas);
      tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      const ceramica = { roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 };
      const branco = new THREE.MeshPhysicalMaterial({ color: 0xffffff, ...ceramica });
      const g = new THREE.Group();
      // a costura da textura fica atrás da alça (+z); o centro da estampa fica do lado oposto
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(R, R, H, 128, 1, true), new THREE.MeshPhysicalMaterial({ map: tex, ...ceramica })));
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(R - .24, R - .24, H, 96, 1, true), new THREE.MeshPhysicalMaterial({ color: 0xffffff, side: THREE.BackSide, ...ceramica })));
      const borda = new THREE.Mesh(new THREE.RingGeometry(R - .24, R, 128), branco); borda.rotation.x = -Math.PI / 2; borda.position.y = H / 2; g.add(borda);
      const fd = new THREE.Mesh(new THREE.CircleGeometry(R - .24, 96), branco); fd.rotation.x = -Math.PI / 2; fd.position.y = -H / 2 + .7; g.add(fd);
      const ff = new THREE.Mesh(new THREE.CircleGeometry(R, 96), branco); ff.rotation.x = Math.PI / 2; ff.position.y = -H / 2; g.add(ff);
      const alca = new THREE.Mesh(new THREE.TorusGeometry(2.55, .46, 24, 72, Math.PI), branco);
      alca.rotation.set(0, -Math.PI / 2, -Math.PI / 2, 'YXZ'); alca.scale.set(1, 1.12, 1); alca.position.set(0, .15, R - .25);
      g.add(alca); cena.add(g);
      const sc = document.createElement('canvas'); sc.width = sc.height = 256;
      const sg = sc.getContext('2d'), rg = sg.createRadialGradient(128, 128, 20, 128, 128, 128);
      rg.addColorStop(0, 'rgba(60,45,30,.35)'); rg.addColorStop(1, 'rgba(60,45,30,0)'); sg.fillStyle = rg; sg.fillRect(0, 0, 256, 256);
      const sombra = new THREE.Mesh(new THREE.CircleGeometry(6.5, 64), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
      sombra.rotation.x = -Math.PI / 2; sombra.position.y = -H / 2 - .01; cena.add(sombra);
      const luz = new THREE.DirectionalLight(0xffffff, 1.1); luz.position.set(-8, 14, -10); cena.add(luz);
      cena.add(new THREE.HemisphereLight(0xffffff, 0xe9e0d2, 1.1));
      let pedido = false;
      const render = () => { if (pedido) return; pedido = true; requestAnimationFrame(() => { pedido = false; renderer.render(cena, camera); }); };
      controles.addEventListener('change', render);
      vista3d.innerHTML = ''; vista3d.appendChild(renderer.domElement);
      tres = {
        medir() {
          const w = vista3d.clientWidth, h = vista3d.clientHeight;
          if (!w || !h) return;
          renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render();
        },
        atualizar() {
          const k = TW / VOLTA;
          texCtx.fillStyle = '#ffffff'; texCtx.fillRect(0, 0, TW, TH);
          desenharEstampa(texCtx, (VOLTA / 2 - A.w / 2) * k, (TH - A.h * k) / 2, k);
          tex.needsUpdate = true; render();
        },
        foto() { renderer.render(cena, camera); return renderer.domElement; },
        fim() { controles.dispose(); renderer.dispose(); renderer.forceContextLoss(); },
      };
      tres.medir(); tres.atualizar();
    }

    // ---------- camiseta: foto lisa tingida na cor escolhida, com a estampa por baixo das dobras ----------
    let fotos = null;
    function pintarCamisa(destino, ladoCamisa, cor, tamanho) {
      const F = fotos[ladoCamisa], N = tamanho, s = N / 1000;
      destino.width = destino.height = N;
      const g = destino.getContext('2d');
      g.clearRect(0, 0, N, N);
      // 1. a silhueta na cor da camisa
      g.globalCompositeOperation = 'source-over';
      g.fillStyle = cor; g.fillRect(0, 0, N, N);
      g.globalCompositeOperation = 'destination-in';
      g.drawImage(F.base, 0, 0, N, N);
      // 2. a estampa, presa dentro da camisa
      const arte = artes[ladoCamisa];
      if (temArte(arte)) {
        g.globalCompositeOperation = 'source-atop';
        const k = F.k * s;
        desenharEstampa(g, F.cx * s - A.w * k / 2, F.topo * s, k, { fundo: false, arte });
      }
      // 3. as dobras escurecem tudo (tecido e estampa) e 4. o brilho volta nas partes altas
      g.globalCompositeOperation = 'multiply';
      g.drawImage(F.sombra, 0, 0, N, N);
      g.globalCompositeOperation = 'screen';
      g.globalAlpha = luminancia(cor) < .35 ? .2 : .12;
      g.drawImage(F.brilho, 0, 0, N, N);
      g.globalAlpha = 1;
      g.globalCompositeOperation = 'destination-in';
      g.drawImage(F.base, 0, 0, N, N);
      g.globalCompositeOperation = 'source-over';
      return destino;
    }
    function desenharCamisa() {
      if (!fotos) return;
      const dpr = window.devicePixelRatio || 1, W = vc.clientWidth;
      if (!W) return;
      const N = Math.min(1000, Math.round(W * dpr));
      pintarCamisa(vc, lado, peca.cor, N);
    }
    let timerMinis = null;
    function desenharMiniaturas() {
      clearTimeout(timerMinis);
      timerMinis = setTimeout(() => {
        const box = q('miniaturas'); if (!box || !fotos) return;
        if (!box.children.length) {
          box.innerHTML = T.cores.map(([nome, hex]) => `<button class="mini" data-cor="${hex}" title="${nome}" aria-label="${nome}"><canvas></canvas><span>${nome}</span></button>`).join('');
          box.querySelectorAll('.mini').forEach(b => b.onclick = () => { peca.cor = b.dataset.cor; montarCores(); atualizar(); });
        }
        box.querySelectorAll('.mini').forEach(b => {
          b.setAttribute('aria-pressed', b.dataset.cor === peca.cor);
          pintarCamisa(b.querySelector('canvas'), lado, b.dataset.cor, 180);
        });
      }, 250);
    }
    if (ehCamisa) carregarCamisa().then(f => { fotos = f; atualizar(); });

    // ---------- azulejo (placa com leve perspectiva) ----------
    function desenharAzulejo() {
      const dpr = window.devicePixelRatio || 1, W = azCanvas.clientWidth;
      if (!W) return;
      azCanvas.width = W * dpr; azCanvas.height = W * dpr;
      const g = azCanvas.getContext('2d');
      // a face visível é 15x15; os 0,35 cm de cada lado são sangria
      const k = azCanvas.width / 15, o = -.35 * k;
      desenharEstampa(g, o, o, k);
    }

    // ---------- qualidade da foto (mesma conta de 300 dpi da /ajustar-arte) ----------
    function avisar(msg, classe = 'ruim') {
      const qq = q('qualidade'); qq.className = 'qualidade on ' + classe; qq.querySelector('span').textContent = msg;
    }
    function atualizarQualidade() {
      if (!st.foto) { q('qualidade').className = 'qualidade'; return; }
      const dpi = 2.54 / medidaFoto().cmPorPx;
      if (dpi >= 220) avisar('Qualidade ótima pra impressão.', 'otima');
      else if (dpi >= 150) avisar('Qualidade boa. Se tiver a foto maior, melhor ainda.', 'boa');
      else avisar('A foto é pequena pra esse tamanho e pode sair borrada. Diminua a foto ou envie uma maior.', 'ruim');
    }

    let quadro = false;
    function atualizar() {
      if (quadro) return;
      quadro = true;
      requestAnimationFrame(() => {
        quadro = false;
        if (desmontado) return;
        desenharEditor();
        if (tipo === 'caneca') tres && tres.atualizar();
        else if (ehCamisa) { desenharCamisa(); desenharMiniaturas(); }
        else desenharAzulejo();
        atualizarQualidade();
      });
    }

    // ---------- controles ----------
    function montarCores() {
      const box = q('coresPeca'); box.innerHTML = '';
      for (const [nome, hex] of T.cores) {
        const b = document.createElement('button');
        b.className = 'cor-chip'; b.innerHTML = `<i style="background:${hex}"></i>${nome}`;
        b.setAttribute('aria-pressed', peca.cor === hex);
        b.onclick = () => { peca.cor = hex; montarCores(); atualizar(); };
        box.appendChild(b);
      }
      const nc = q('nomeCor'); if (nc) nc.textContent = '· ' + (T.cores.find(c => c[1] === peca.cor)?.[0] || '');
    }
    function montarTexto() {
      const fb = q('fontes'); fb.innerHTML = '';
      for (const f of FONTES) {
        const b = document.createElement('button');
        b.className = 'chip'; b.textContent = f.nome; b.style.font = f.css.replace('{px}', '18px');
        b.setAttribute('aria-pressed', st.fonte === f.id);
        b.onclick = () => { st.fonte = f.id; alvo = 'texto'; montarTexto(); atualizar(); };
        fb.appendChild(b);
      }
      const cb = q('coresTexto'); cb.innerHTML = '';
      for (const [nome, hex] of CORES_TEXTO) {
        const b = document.createElement('button');
        b.className = 'cor'; b.style.background = hex; b.title = nome; b.setAttribute('aria-label', nome);
        b.setAttribute('aria-pressed', st.corTexto === hex);
        b.onclick = () => { st.corTexto = hex; montarTexto(); atualizar(); };
        cb.appendChild(b);
      }
    }
    // os controles mostram sempre a arte do lado que está aberto
    function sincronizarControles() {
      q('texto').value = st.texto;
      q('tamTexto').value = st.tam;
      q('zoom').value = st.fs; q('giro').value = st.fr;
      q('ajustes').hidden = !st.foto;
      const la = q('ladoAtual'); if (la) la.textContent = lado === 'frente' ? 'na frente' : 'nas costas';
      raiz.querySelectorAll('[data-lado]').forEach(b => b.setAttribute('aria-selected', b.dataset.lado === lado));
      montarTexto();
    }
    raiz.querySelectorAll('[data-lado]').forEach(b => b.onclick = () => {
      lado = b.dataset.lado; st = artes[lado]; alvo = null;
      sincronizarControles(); atualizar();
    });
    raiz.querySelectorAll('[data-opcao]').forEach(box => {
      const o = opcoesProduto[+box.dataset.opcao];
      box.querySelectorAll('.opcao').forEach(b => b.onclick = () => {
        peca.opcoes[o.nome] = b.dataset.v;
        box.querySelectorAll('.opcao').forEach(x => x.setAttribute('aria-pressed', x === b));
      });
    });

    // ---------- foto ----------
    const carregarImagem = (src) => new Promise((ok, erro) => { const i = new Image(); i.onload = () => ok(i); i.onerror = erro; i.src = src; });
    const lerComoDataUrl = (a) => new Promise((ok, erro) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = erro; r.readAsDataURL(a); });
    // Lê a foto sem endereço blob: (a moldura da Ratoeira e alguns celulares bloqueiam)
    async function abrirArquivo(a) {
      if (window.createImageBitmap) {
        try { return await createImageBitmap(a, { imageOrientation: 'from-image' }); } catch {}
        try { return await createImageBitmap(a); } catch {}
      }
      return carregarImagem(await lerComoDataUrl(a));
    }
    function reduzida(img, max = 1800) {
      const s = Math.min(1, max / Math.max(larg(img), alt(img)));
      if (s === 1) return img;
      const c = document.createElement('canvas');
      c.width = Math.round(larg(img) * s); c.height = Math.round(alt(img) * s);
      const g = c.getContext('2d'); g.imageSmoothingQuality = 'high'; g.drawImage(img, 0, 0, c.width, c.height);
      return c;
    }
    function usarImagem(img, nome) {
      st.foto = { full: img, prev: reduzida(img), nw: larg(img), nh: alt(img), nome };
      st.fx = 0; st.fy = 0; st.fs = 1; st.fr = 0; alvo = 'foto';
      q('zoom').value = 1; q('giro').value = 0; q('ajustes').hidden = false;
      atualizar();
    }
    q('arquivo').addEventListener('change', async (e) => {
      const f = e.target.files[0]; e.target.value = '';
      if (!f) return;
      avisar('Abrindo a foto…', 'boa');
      try { usarImagem(await abrirArquivo(f), f.name); }
      catch {
        const heic = /\.(heic|heif)$/i.test(f.name) || /hei[cf]/i.test(f.type);
        avisar(heic ? 'Essa foto está no formato HEIC, que o navegador não abre. No celular, compartilhe a foto como JPG ou tire um print dela e envie de novo.'
          : 'Não consegui abrir essa imagem. Tente outra foto, em JPG ou PNG.');
      }
    });
    q('exemplo').onclick = async () => usarImagem(await carregarImagem(fotoExemplo()), 'exemplo.png');
    q('zoom').oninput = (e) => { st.fs = +e.target.value; alvo = 'foto'; atualizar(); };
    q('giro').oninput = (e) => { st.fr = +e.target.value; alvo = 'foto'; atualizar(); };
    q('preencher').onclick = () => { st.fs = 1; st.fx = 0; st.fy = 0; st.fr = 0; q('zoom').value = 1; q('giro').value = 0; atualizar(); };
    q('encaixar').onclick = () => {
      const f = st.foto, cover = Math.max(A.w / f.nw, A.h / f.nh), contain = Math.min(A.w / f.nw, A.h / f.nh);
      st.fs = contain / cover; st.fx = 0; st.fy = 0; st.fr = 0; q('zoom').value = st.fs; q('giro').value = 0; atualizar();
    };
    q('remover').onclick = () => { st.foto = null; alvo = null; q('ajustes').hidden = true; atualizar(); };
    q('texto').oninput = (e) => { st.texto = e.target.value; alvo = 'texto'; atualizar(); };
    q('tamTexto').oninput = (e) => { st.tam = +e.target.value; alvo = 'texto'; atualizar(); };
    const qtd = q('qtd');
    q('menos').onclick = () => { qtd.value = Math.max(1, (+qtd.value || 1) - 1); };
    q('mais').onclick = () => { qtd.value = Math.min(99, (+qtd.value || 1) + 1); };

    function fotoExemplo() {
      const c = document.createElement('canvas'); c.width = 2400; c.height = 1600;
      const g = c.getContext('2d'), ceu = g.createLinearGradient(0, 0, 0, 1600);
      ceu.addColorStop(0, '#f6c58f'); ceu.addColorStop(.55, '#f29e7c'); ceu.addColorStop(1, '#7d6a8f');
      g.fillStyle = ceu; g.fillRect(0, 0, 2400, 1600);
      g.fillStyle = '#ffe9b8'; g.beginPath(); g.arc(1500, 820, 260, 0, Math.PI * 2); g.fill();
      g.fillStyle = '#5b4a6b'; g.beginPath(); g.moveTo(0, 1150); g.quadraticCurveTo(600, 900, 1200, 1120); g.quadraticCurveTo(1800, 1320, 2400, 1050); g.lineTo(2400, 1600); g.lineTo(0, 1600); g.fill();
      g.fillStyle = '#3b3048'; g.beginPath(); g.moveTo(0, 1350); g.quadraticCurveTo(900, 1180, 2400, 1380); g.lineTo(2400, 1600); g.lineTo(0, 1600); g.fill();
      g.fillStyle = '#e4572e'; g.save(); g.translate(1060, 760); g.scale(5, 5);
      g.beginPath(); g.moveTo(0, 30); g.bezierCurveTo(-40, 0, -25, -30, 0, -12); g.bezierCurveTo(25, -30, 40, 0, 0, 30); g.fill(); g.restore();
      return c.toDataURL('image/png');
    }

    // ---------- adicionar ao carrinho ----------
    function miniatura(origem, lado = 360, fundo = '#f6efe8') {
      const c = document.createElement('canvas'); c.width = c.height = lado;
      const g = c.getContext('2d'); g.fillStyle = fundo; g.fillRect(0, 0, lado, lado);
      const w = origem.width, h = origem.height, s = Math.min(lado / w, lado / h);
      g.drawImage(origem, (lado - w * s) / 2, (lado - h * s) / 2, w * s, h * s);
      return c.toDataURL('image/jpeg', .82);
    }
    function mockupAzulejo() {
      const c = document.createElement('canvas'); c.width = c.height = 600;
      const g = c.getContext('2d'); g.fillStyle = '#f6efe8'; g.fillRect(0, 0, 600, 600);
      g.save(); g.shadowColor = 'rgba(60,45,30,.3)'; g.shadowBlur = 30; g.shadowOffsetY = 14;
      g.fillStyle = '#fff'; g.fillRect(110, 90, 380, 380); g.restore();
      desenharEstampa(g, 110 - .35 * 380 / 15, 90 - .35 * 380 / 15, 380 / 15);
      g.fillStyle = '#1d1d1f'; g.fillRect(170, 470, 50, 26); g.fillRect(380, 470, 50, 26);
      return c;
    }
    function mockupCamisa() {
      // frente e, se tiver arte, as costas lado a lado
      const comCostas = artes.costas && temArte(artes.costas);
      const c = document.createElement('canvas'); c.width = comCostas ? 1200 : 600; c.height = 600;
      const g = c.getContext('2d'); g.fillStyle = '#0d0d0f'; g.fillRect(0, 0, c.width, c.height);
      g.drawImage(pintarCamisa(document.createElement('canvas'), 'frente', peca.cor, 600), 0, 0);
      if (comCostas) g.drawImage(pintarCamisa(document.createElement('canvas'), 'costas', peca.cor, 600), 600, 0);
      return c;
    }
    function descreverArte(a) {
      const d = [];
      if (a.texto.trim()) d.push(`texto "${a.texto.trim()}" (${FONTES.find(f => f.id === a.fonte).nome.toLowerCase()})`);
      if (a.foto) d.push(`foto ${a.foto.nome}, ${Math.round(2.54 / medidaFoto(a).cmPorPx)} dpi`);
      return d.join(', ');
    }
    q('adicionar').onclick = () => {
      const falta = [];
      if (!T.lados.some(l => temArte(artes[l]))) falta.push('envie uma foto ou escreva um texto');
      for (const o of opcoesProduto) if (!peca.opcoes[o.nome]) falta.push(`escolha o ${o.nome.toLowerCase()}`);
      if (T.lados.some(l => artes[l].foto) && !q('termo').checked) falta.push('confirme que pode usar a imagem');
      if (ehCamisa && !fotos) falta.push('espere a camiseta carregar');
      const fm = q('falta');
      if (falta.length) { fm.hidden = false; fm.textContent = 'Falta pouco: ' + falta.join(', ') + '.'; return; }
      fm.hidden = true;
      const origem = tipo === 'caneca' ? tres.foto() : ehCamisa ? mockupCamisa() : mockupAzulejo();
      const corNome = T.cores.find(c => c[1] === peca.cor)?.[0];
      const detalhes = [`${T.rotuloCor}: ${corNome}`];
      for (const o of opcoesProduto) detalhes.push(`${o.nome}: ${peca.opcoes[o.nome]}`);
      for (const l of T.lados) if (temArte(artes[l])) detalhes.push((T.lados.length > 1 ? NOME_LADO[l] + ': ' : 'Arte: ') + descreverArte(artes[l]));
      aoAdicionar({
        qtd: Math.max(1, Math.min(99, +qtd.value || 1)),
        opcoes: { ...peca.opcoes, [T.rotuloCor]: corNome },
        detalhes, mockup: miniatura(origem, 360, ehCamisa ? '#0d0d0f' : '#f6efe8'),
        // Na versão final, a foto original e o arquivo de impressão de cada lado sobem pro servidor com o pedido.
        arquivosImpressao: () => Object.fromEntries(T.lados.filter(l => temArte(artes[l])).map(l => {
          const kp = 300 / 2.54, c = document.createElement('canvas');
          c.width = Math.round(A.w * kp); c.height = Math.round(A.h * kp);
          desenharEstampa(c.getContext('2d'), 0, 0, kp, { full: true, arte: artes[l] });
          return [l, c];
        })),
      });
    };

    // ---------- início e fim ----------
    let desmontado = false;
    function medirTudo() { medirEditor(); if (tres) tres.medir(); atualizar(); }
    window.addEventListener('resize', medirTudo);
    montarCores(); sincronizarControles(); medirEditor();
    if (tipo === 'caneca') iniciarCaneca().catch(() => { vista3d.innerHTML = '<div class="carregando">Não consegui carregar a caneca em 3D. Verifique a internet e recarregue a página.</div>'; });
    atualizar();
    document.fonts.ready.then(() => Promise.all(FONTES.map(f => document.fonts.load(f.css.replace('{px}', '20px'))))).then(atualizar).catch(() => {});

    return {
      desmontar() {
        desmontado = true;
        clearTimeout(timerMinis);
        window.removeEventListener('resize', medirTudo);
        if (tres) tres.fim();
      },
    };
  }

  return { montar, TIPOS };
})();
