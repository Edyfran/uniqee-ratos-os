/* receitas-core.js — o desenho das receitas de talking head, tirado da prévia
   aprovada (design_handoff_talking_head_receitas). Canvas 2D puro.

   O que mudou do verbatim, e por quê:
   - Resolução: as medidas continuam em unidades de 540×960 (W, H), mas os canvas
     internos têm S vezes isso em px. Sem isso o render 1080×1920 sairia da prévia
     esticada 2× e borrada. Todo canvas interno nasce com o contexto já em escala S,
     e todo canvas interno é desenhado com tamanho explícito (W, H) — `cheio()`.
   - Textos e números fixos viraram parâmetro: `cena(..., p)`. Sem `p`, cai no
     texto da prévia, então o protótipo continua reproduzível.
   - As receitas fora da lib (3 punch, 8 órbita, 9 aponta, 15 sticker) saíram.
   - Freeze, grade da escala, enquadramento da janela (crop02) e cues ficaram
     expostos para a página controlar: o render pode pedir qualquer quadro fora
     de ordem e sair igual.
   - Atualização 2 do designer (ATUALIZACAO-2.md): janela com crop parado e
     pop-out, número acima da cabeça, tela dividida com menos zoom, e os cinco
     ganchos novos (17–21), todos com texto vindo de `p`.
   - `r.ocupaCena`: depois de desenhar, as áreas que a cena ocupou nesse quadro
     (receitas 2 e 20), pra a legenda v3 não sentar em cima. A página zera antes.
   - `r.state.legOn`: a legenda v3 está ligada. Desligada (padrão), tudo igual a antes.

   Contrato por quadro — quem chama preenche, antes de desenhar:
     r.F      quadro COMPLETO: placa de fundo + avatar por cima
     r.P      só o avatar (RGBA; alfa do .webm da HeyGen)
     r.M2     a máscara (o que vale é o alfa) = r.P serve
     r.face   {x,y,w,h}   caixa do rosto em unidades de W×H, suavizada (EMA 0,35)
     r.FB, r.faceB        só o match-cut: o quadro e o rosto do take B
   Depois: r.cena(i, ctx, lt, ts, dd, p)
     i   índice INTERNO da receita (NOMES abaixo)
     lt  0..1  progresso na janela · ts s desde o início · dd s duração da janela
     p   parâmetros da receita (os do plano.json)
*/
class Receitas {
  // nome no plano → índice interno. A numeração da lib visível (01–13) é a ordem daqui.
  static NOMES = {'tese': 0, 'janela': 1, 'numero': 2, 'volta': 4, 'tela-dividida': 5, 'pergunta': 6,
    'pop-out': 7, 'mito': 10, 'antes-depois': 11, 'escala': 12, 'capitulo': 13, 'pausa': 14, 'match-cut': 16,
    'loop': 17, 'censura': 18, 'close': 19, 'notificacoes': 20, 'interrupcao': 21};

  constructor(W = 540, H = 960, S = 1) {
    this.W = W; this.H = H; this.S = S;
    this.C = {ink: '#0B0D12', ac: '#0640fb', mk: '#F2C744', papel: '#FFFFFF', no: '#E1432F'};
    this.state = {legOn: false};   // legOn: a legenda v3 manda (a tela dividida não desenha a própria)
    this.ocupaCena = null;
    this.face = {x: 190, y: 250, w: 160, h: 190};
    const cru = (w, h) => typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(w, h) : Object.assign(document.createElement('canvas'), {width: w, height: h});
    // canvas interno: S× em px, contexto já em escala S — quem desenha nele pensa em 540
    const cv = (w = W, h = H) => { const c = cru(Math.round(w * S), Math.round(h * S)); c.getContext('2d').setTransform(S, 0, 0, S, 0, 0); return c; };
    this.cv = cv;
    this.F = cv(); this.P = cv(); this.M2 = cv(); this.T1 = cv(); this.T2 = cv(); this.T3 = cv(); this.N = cv(); this.X = cv();
    this.pontos = cv(24, 24); { const g = this.pontos.getContext('2d'); g.fillStyle = '#000'; g.beginPath(); g.arc(12, 12, 4.5, 0, 7); g.fill(); }
    // grão com semente fixa: o render é igual toda vez. Fica 270×480 cru, como na
    // prévia: esticado ao quadro, o grão tem o mesmo tamanho relativo nos dois.
    let sd = 1234567; const rnd = () => (sd = (sd * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    this.grao = [0, 1, 2, 3].map(() => { const c = cru(270, 480), g = c.getContext('2d'), d = g.createImageData(270, 480); for (let i = 0; i < d.data.length; i += 4) { const n = rnd() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = n; d.data[i + 3] = 255; } g.putImageData(d, 0, 0); return c; });
  }

  // canvas interno inteiro, no tamanho lógico (senão sai S× maior)
  cheio(ctx, c, x = 0, y = 0) { ctx.drawImage(c, x, y, this.W, this.H); }
  // recorte de canvas interno: a origem é em px reais, então ×S
  recorte(ctx, c, sx, sy, sw, sh, dx, dy, dw, dh) { const S = this.S; ctx.drawImage(c, sx * S, sy * S, sw * S, sh * S, dx, dy, dw, dh); }
  // captura real em "cover" dentro da caixa (quem chama já recortou)
  captura(ctx, img, x, y, w, h) {
    const iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height, s = Math.max(w / iw, h / ih);
    ctx.drawImage(img, x + (w - iw * s) / 2, y + (h - ih * s) / 2, iw * s, ih * s);
  }
  grao_(ctx, t, a) { ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.globalAlpha = a; ctx.drawImage(this.grao[Math.floor(t * 12) % 4], 0, 0, this.W, this.H); ctx.restore(); }

  pintaMascara(dst, cor, m = this.M2) { const g = dst.getContext('2d'); g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, this.W, this.H); this.cheio(g, m); g.globalCompositeOperation = 'source-in'; g.fillStyle = cor; g.fillRect(0, 0, this.W, this.H); g.globalCompositeOperation = 'source-over'; return dst; }
  // adesivo: sombra dura + contorno pela máscara dilatada, corpo por cima
  adesivo(ctx, borda, sombra, r = 5, sh = 12, corpo = this.P, sombraCor = this.C.ink, mascara = this.M2) {
    const tinta = this.pintaMascara(this.T1, sombraCor, mascara), cor = borda ? this.pintaMascara(this.T2, borda, mascara) : null;
    const dirs = 12;
    if (sombra) for (let i = 0; i < dirs; i++) { const a = i / dirs * 6.283; this.cheio(ctx, tinta, sh + Math.cos(a) * r, sh + Math.sin(a) * r); }
    if (borda) for (let i = 0; i < dirs; i++) { const a = i / dirs * 6.283; this.cheio(ctx, cor, Math.cos(a) * r, Math.sin(a) * r); }
    this.cheio(ctx, corpo);
  }
  pontilhado(ctx, cor, alfa, passo = 24) {
    ctx.save(); ctx.globalAlpha = alfa; ctx.fillStyle = cor;
    for (let y = passo / 2; y < this.H; y += passo) for (let x = passo / 2; x < this.W; x += passo) { ctx.beginPath(); ctx.arc(x, y, 1.6, 0, 6.3); ctx.fill(); }
    ctx.restore();
  }
  texto(ctx, s, x, y, px, cor, sombra, sh = 8, fam = '"Space Grotesk"', peso = 700, alinha = 'center', maxW = 510) {
    ctx.font = `${peso} ${px}px ${fam}`; let w = ctx.measureText(s).width;
    if (w > maxW) { px = px * maxW / w; ctx.font = `${peso} ${px}px ${fam}`; }
    ctx.textAlign = alinha; ctx.textBaseline = 'alphabetic';
    if (sombra) { ctx.fillStyle = sombra; ctx.fillText(s, x + sh, y + sh); }
    ctx.fillStyle = cor; ctx.fillText(s, x, y);
    return px;
  }
  caixa(ctx, x, y, w, h, fundo, sh = 10, sombra = this.C.ink, bw = 5, r = 12) {
    ctx.fillStyle = sombra; this.rr(ctx, x + sh, y + sh, w, h, r); ctx.fill();
    ctx.fillStyle = fundo; this.rr(ctx, x, y, w, h, r); ctx.fill();
    ctx.lineWidth = bw; ctx.strokeStyle = this.C.ink; this.rr(ctx, x, y, w, h, r); ctx.stroke();
  }
  rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  mola(p) { const c1 = 1.9, c3 = c1 + 1; return p <= 0 ? 0 : p >= 1 ? 1 : 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); }
  tag(ctx, s, x, y, fundo, cor, px = 26, rot = 0) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.font = `700 ${px}px "IBM Plex Mono"`;
    const w = ctx.measureText(s).width + px * 1.1, h = px * 1.7;
    this.caixa(ctx, 0, -h / 2, w, h, fundo, 6, this.C.ink, 4, 7);
    ctx.fillStyle = cor; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(s, px * .55, 2);
    ctx.restore(); return w;
  }

  // o intervalo do freeze de cada receita, em s locais: [chave, de, até]. A página
  // usa isto pra congelar o quadro certo mesmo quando pula quadros.
  congelaDe(i, dd, p = {}) {
    if (i === 6) return ['perg', 0, p.congela ?? 1.4];
    if (i === 14) return ['pausa', p.congela ?? Math.min(.8, dd * .15), Infinity];
    if (i === 21) return ['int', 0, p.congela ?? .45];
    return null;
  }
  // o enquadramento do cartão da janela: tirado UMA vez, com o rosto do primeiro
  // quadro da cena, e parado. Seguir o track quadro a quadro fazia o cartão tremer.
  enquadra02() {
    const {W, H} = this, f = this.face, fcx = f.x + f.w / 2, fcy = f.y + f.h / 2, cw = 250, ch = 300;
    const shh = f.h * 2.3, sw = shh * cw / ch;
    this.crop02 = {sw, shh, sx: Math.max(0, Math.min(W - sw, fcx - sw / 2)), sy: Math.max(0, Math.min(H - shh, fcy - shh * .45)), fcx, fw: f.w};
    return this.crop02;
  }
  // notificações: o passo entre uma e outra, em s
  passoNotif(dd, p = {}) { const n = p.n ?? 5; return p.a_cada ?? .55 * dd / n; }
  // a grade da escala: calculada UMA vez, com o rosto do primeiro quadro da
  // janela — recalcular a cada quadro faz a ordem piscar
  calculaLivres(n = 43) {
    const {W} = this, f = this.face, fcx = f.x + f.w / 2, fcy = f.y + f.h / 2;
    const cs = [], t = 64, g = 12, cols = 7, rows = 12, x0 = (W - (cols * t + (cols - 1) * g)) / 2;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cs.push({x: x0 + c * (t + g), y: 20 + r * (t + g)});
    this.livres = cs.filter(c => !(Math.abs(c.x + 32 - fcx) < f.w * 1.25 && c.y + 64 > f.y - 20)).map(c => ({...c, d: Math.hypot(c.x + 32 - fcx, c.y + 32 - fcy)})).sort((a, b) => a.d - b.d).slice(0, n);
  }
  // a transição tese → janela: a próxima cena aparece através da silhueta, que
  // cresce de 1 a 10× a partir do queixo. `prog` 0..1 nos últimos 0,35 s.
  silhueta(ctx, prog, proxima) {
    const {W, H} = this, f = this.face, k = 1 + Math.pow(prog, 2) * 9, cx = f.x + f.w / 2, cy = f.y + f.h * .9;
    proxima(this.N.getContext('2d'));
    const X = this.X.getContext('2d'); X.globalCompositeOperation = 'source-over'; X.clearRect(0, 0, W, H);
    X.save(); X.translate(cx, cy); X.scale(k, k); X.translate(-cx, -cy); this.cheio(X, this.M2); X.restore();
    X.globalCompositeOperation = 'source-in'; this.cheio(X, this.N); X.globalCompositeOperation = 'source-over';
    this.cheio(ctx, this.X);
  }

  // SFX de cada receita, no contrato de overlays/CUES.md, em s locais da janela.
  cues(i, dd, p = {}) {
    const c = [], pop = (t, tipo = 'pop') => { if (t >= 0 && t < dd) c.push({t: +t.toFixed(3), tipo}); };
    if (i === 0) { const n = (p.batidas || Receitas.PADRAO.batidas).length; for (let k = 0; k < n; k++) pop(k * dd / n); }
    else if (i === 1) { pop(0, 'swish'); pop(.35 * dd); }
    else if (i === 2) { const n = (p.passos || Receitas.PADRAO.passos).length; for (let k = 0; k < n; k++) pop(k * dd * .7 / n); pop(.7 * dd, 'ding'); }
    else if (i === 4) { pop(0, 'whoosh'); pop(.35 * dd); }
    else if (i === 5) { const ws = this.state.legOn ? [] : this.palavras(p.legenda ?? Receitas.PADRAO.legenda); pop(0, 'swish'); for (let j = 1; j < ws.length; j++) pop(j / (ws.length * 1.4) * dd, 'click'); }
    else if (i === 6) { (p.linhas || Receitas.PADRAO.linhas).forEach((_, j) => pop(.15 + j * .3)); }
    else if (i === 7) { pop(0, 'whoosh'); pop(.25 * dd); }
    else if (i === 10) { pop(.53, 'stamp'); pop(.85, 'swish'); }
    else if (i === 11) { pop(0, 'swish'); pop(.2 * dd); pop(.3 * dd); }
    else if (i === 12) { c.push({t: +(.08 * dd).toFixed(3), tipo: 'tick-roll', dur: +(.62 * dd).toFixed(3)}); pop(.7 * dd, 'ding'); }
    else if (i === 13) { pop(0, 'whoosh'); pop(.08 * dd, 'impact'); pop(.18 * dd); pop(.26 * dd); }
    else if (i === 14) { pop(this.congelaDe(14, dd, p)[1], 'whoosh-out'); }
    else if (i === 16) { const cada = p.cada ?? .9; for (let t = cada; t < dd; t += cada) pop(t, 'click'); }
    else if (i === 17) { pop(0, 'impact'); pop(.06 * dd, 'swish'); (p.itens || Receitas.PADRAO.itens).forEach((_, k) => pop((.25 + k * .22) * dd)); }
    else if (i === 18) { pop(0); pop(.15 * dd, 'swish'); pop(.82 * dd, 'ding'); }
    else if (i === 19) { pop(.08, 'whoosh'); pop(.47, 'impact'); pop(.52); }
    else if (i === 20) { const passo = this.passoNotif(dd, p); for (let k = 0; k < (p.n ?? 5); k++) pop(.2 + k * passo); }
    else if (i === 21) { const fim = this.congelaDe(21, dd, p)[2]; pop(0, 'impact'); pop(fim, 'whoosh'); pop(.55 * dd, 'whoosh-out'); }
    return c;
  }
  palavras(l) { return Array.isArray(l) ? l : String(l).split(/\s+/).filter(Boolean); }

  // os textos da prévia: o que sai quando o plano não diz nada
  static PADRAO = {
    batidas: [['EU', 'DEMITI'], ['E CONTRATEI'], ['4', 'AGENTES']],
    passos: [4500, 9000, 18000, 36000, 54000],
    legenda: ['ELE', 'FEZ', 'ISSO', 'SOZINHO'],
    linhas: ['E SE', 'VOCÊ NÃO', 'PRECISASSE', 'PROGRAMAR?'],
    itens: ['ANÚNCIOS', 'SUPORTE', 'CONTEÚDO'],
    interrompe: ['VOCÊ TÁ', 'FAZENDO', 'ERRADO'],
  };

  cena(i, ctx, lt, ts, dd, p = {}) {
    const {W, H, C} = this, f = this.face, fcx = f.x + f.w / 2, fcy = f.y + f.h / 2, D = Receitas.PADRAO;
    ctx.save(); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.filter = 'none';
    const base = ctx.getTransform();   // a escala de quem chamou: é pra ela que se volta, não pra identidade
    if (i === 0) {
      ctx.fillStyle = C.ac; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, '#fff', .16);
      const z = 1 + .04 * lt; ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-W / 2, -H / 2);
      const batidas = p.batidas || D.batidas;
      const k = Math.min(batidas.length - 1, Math.floor(lt * batidas.length));
      const tb = ts - k * dd / batidas.length, pop = this.mola(Math.min(1, tb / .22));
      ctx.save(); ctx.translate(W / 2, p.y ?? 330); ctx.scale(.75 + .25 * pop, .75 + .25 * pop); ctx.globalAlpha = Math.min(1, tb / .06);
      const ls = [].concat(batidas[k]);
      ls.forEach((l, j) => this.texto(ctx, l, 0, (j - (ls.length - 1) / 2) * 175 + 60, l.length <= 2 ? 230 : 170, '#fff', C.ink, 10));
      ctx.restore();
      this.adesivo(ctx, '#fff', true, 6, 14);
    } else if (i === 1) {
      ctx.fillStyle = C.mk; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, C.ink, .14);
      // janela 16:9: sobe devagar, gira pouco — camada de trás do parallax
      const wy = 110 - 14 * lt, wx = 34;
      ctx.save(); ctx.translate(wx + 236, wy + 150); ctx.rotate((-1.8 + 1.2 * lt) * Math.PI / 180); ctx.translate(-(wx + 236), -(wy + 150));
      this.caixa(ctx, wx, wy, 472, 300, '#fff', 12);
      ctx.fillStyle = C.ink; ctx.fillRect(wx + 2.5, wy + 2.5, 467, 34);
      ctx.fillStyle = C.mk; ctx.font = '700 15px "IBM Plex Mono"'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(p.rotulo ?? 'PAINEL DE ANÚNCIOS', wx + 16, wy + 20);
      ctx.save(); this.rr(ctx, wx + 3, wy + 37, 466, 260, 9); ctx.clip();
      if (p.captura) this.captura(ctx, p.captura, wx + 3, wy + 37, 466, 260);
      else {
        for (let y = wy + 37; y < wy + 300; y += 22) { ctx.fillStyle = (Math.floor((y - wy) / 22) % 2) ? '#E9E6DF' : '#F4F2EC'; ctx.fillRect(wx, y, 472, 22); }
        const barra = (ts * .5) % 1;
        ctx.fillStyle = '#fff'; ctx.fillRect(wx + 70, wy + 200, 332, 24); ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.strokeRect(wx + 70, wy + 200, 332, 24);
        ctx.fillStyle = C.ac; ctx.fillRect(wx + 72, wy + 202, 328 * barra, 20);
        ctx.fillStyle = '#7C808B'; ctx.font = '600 16px "IBM Plex Mono"'; ctx.textAlign = 'center'; ctx.fillText('CAPTURA REAL AQUI', wx + 236, wy + 150);
      }
      ctx.restore(); ctx.restore();
      const selo = p.selo ?? 'PLANO PRONTO';
      if (selo && lt > .35) { const q = this.mola(Math.min(1, (lt - .35) / .08)); ctx.save(); ctx.translate(330, wy + 300); ctx.scale(q, q); this.tag(ctx, selo, -20, 0, C.ink, C.mk, 22, -.05); ctx.restore(); }
      // cartão do rosto: enquadramento PARADO (crop02, tirado no começo da cena) —
      // camada da frente do parallax. Quem não zerou crop02 (a prévia da silhueta) recalcula.
      const cw = 250, ch = 300, cx0 = 44, cy0 = 560 + 16 * lt;
      const q = this.crop02 || this.enquadra02(), {sx, sy, sw, shh} = q, k = ch / shh;
      ctx.save(); ctx.translate(cx0 + cw / 2, cy0 + ch / 2); ctx.rotate(2.5 * Math.PI / 180); ctx.translate(-(cx0 + cw / 2), -(cy0 + ch / 2));
      // a borda de cima desce 5% do cartão: o enquadramento não muda, só sobra mais cabeça pra fora
      const topo = cy0 + ch * .05, alt = cy0 + ch - topo;
      const hx = cx0 + (q.fcx - sx) * (cw / sw), hw = q.fw * (cw / sw) * 2.1;
      this.caixa(ctx, cx0, topo, cw, alt, '#000', 12, C.ac, 6, 14);
      ctx.save(); this.rr(ctx, cx0 + 3, topo + 3, cw - 6, alt - 6, 11); ctx.clip(); this.recorte(ctx, this.F, sx, sy, sw, shh, cx0, cy0, cw, ch); ctx.restore();
      ctx.lineWidth = 6; ctx.strokeStyle = C.ink; this.rr(ctx, cx0, topo, cw, alt, 14); ctx.stroke();
      // pop-out: acima da moldura só o recorte (r.P), com a fonte estendida até o topo
      // do quadro — a ponta do cabelo não é cortada pela borda do cartão
      const ext = sy, mapa = img => this.recorte(ctx, img, sx, sy - ext, sw, shh + ext, cx0, cy0 - ext * k, cw, ch + ext * k);
      ctx.save(); ctx.beginPath(); ctx.rect(hx - hw / 2, 0, hw, topo - 4); ctx.clip(); ctx.translate(10, 10); mapa(this.pintaMascara(this.T1, C.ink)); ctx.restore();
      ctx.save(); ctx.beginPath(); ctx.rect(hx - hw / 2, 0, hw, topo + 8); ctx.clip(); mapa(this.P); ctx.restore();
      ctx.restore();
    } else if (i === 2) {
      ctx.fillStyle = C.papel; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, C.ink, .12);
      const passos = p.passos || D.passos;
      const k = Math.min(passos.length - 1, Math.floor(Math.min(.99, lt / .7) * passos.length));
      const tb = ts - k * (dd * .7) / passos.length, pop = this.mola(Math.min(1, tb / .16));
      const v = passos[k], num = typeof v === 'number' ? v.toLocaleString('pt-BR') : String(v);
      // o número mora no vão ACIMA da cabeça (antes ficava atrás dela, escondido)
      const nb = Math.max(205, Math.min(400, f.y - 110));
      this.ocupaCena = [[0, nb - 195, 540, nb + 78]];
      ctx.save(); ctx.translate(W / 2, nb); ctx.scale(.85 + .15 * pop, .85 + .15 * pop);
      this.texto(ctx, num, 0, 0, p.tam ?? 230, C.ink, C.mk, 12, '"Space Grotesk"', 700, 'center', p.largura ?? 700);
      ctx.restore();
      const unidade = p.unidade ?? 'R$', rotulo = p.rotulo ?? 'POR ANO', fator = p.fator ?? '× 12 MESES';
      if (unidade) this.texto(ctx, unidade, 60, nb - 170, 70, C.ac, null, 0, '"Space Grotesk"', 700, 'left');
      // corpo em duotone tinta/amarelo, com retícula
      const d = this.T3.getContext('2d'); d.globalCompositeOperation = 'source-over'; d.clearRect(0, 0, W, H);
      d.filter = 'grayscale(1) contrast(1.45) brightness(1.08)'; this.cheio(d, this.P); d.filter = 'none';
      d.globalCompositeOperation = 'multiply'; d.fillStyle = C.mk; d.fillRect(0, 0, W, H);
      // o padrão vive no espaço do contexto (já ×S): desfaz a escala, senão a retícula dobra de passo
      const pt = d.createPattern(this.pontos, 'repeat'); pt.setTransform(new DOMMatrix([1 / this.S, 0, 0, 1 / this.S, 0, 0]));
      d.globalCompositeOperation = 'source-atop'; d.globalAlpha = .22; d.fillStyle = pt; d.fillRect(0, 0, W, H); d.globalAlpha = 1;
      d.globalCompositeOperation = 'destination-in'; this.cheio(d, this.M2); d.globalCompositeOperation = 'source-over';
      this.adesivo(ctx, null, true, 3, 14, this.T3);
      // a linha de baixo do número: rótulo à esquerda, fator encostado à direita. Os dois
      // POR CIMA do corpo — na prévia o rótulo ia atrás, e com o rosto no centro o corpo o cobria
      if (rotulo && lt > .7) { const q = this.mola(Math.min(1, (lt - .7) / .06)); ctx.save(); ctx.translate(44, nb + 54); ctx.scale(q, q); this.tag(ctx, rotulo, 0, 0, C.mk, C.ink, 30, -.03); ctx.restore(); }
      if (fator) { ctx.font = '700 22px "IBM Plex Mono"'; const fw = ctx.measureText(fator).width + 22 * 1.1; this.tag(ctx, fator, W - 30 - fw, nb + 54, C.ink, '#fff', 22, .04); }
    } else if (i === 4) {
      const z = 1 + .05 * lt; ctx.translate(W / 2, H * .4); ctx.scale(z, z); ctx.translate(-W / 2, -H * .4);
      this.cheio(ctx, this.F); ctx.setTransform(base);
      // luz vazada quente, uma vez, na volta
      if (ts < .6) {
        const a = Math.sin(Math.min(1, ts / .6) * Math.PI), xx = -150 + ts / .6 * 840;
        ctx.globalCompositeOperation = 'screen';
        [[xx, 300, 420, 'rgba(255,170,60,'], [xx - 120, 700, 360, 'rgba(242,199,68,'], [xx + 90, 120, 260, 'rgba(255,240,200,']].forEach(([x, y, r, c]) => {
          const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, c + (.95 * a) + ')'); g.addColorStop(1, c + '0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
        });
        ctx.globalCompositeOperation = 'source-over';
      }
      if (lt > .35) {
        const q = this.mola(Math.min(1, (lt - .35) / .1)), verbo = p.verbo ?? 'comenta', palavra = '"' + (p.palavra ?? 'AGENTE') + '"';
        ctx.save(); ctx.translate(W / 2, 800); ctx.scale(q, q);
        ctx.font = '700 40px "Space Grotesk"'; const a1 = ctx.measureText(verbo).width; ctx.font = '700 44px "Space Grotesk"'; const a2 = ctx.measureText(palavra).width;
        const w = a1 + a2 + 70, h = 88;
        this.caixa(ctx, -w / 2, -h / 2, w, h, '#fff', 10);
        ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.fillStyle = C.ink; ctx.font = '700 40px "Space Grotesk"'; ctx.fillText(verbo, -w / 2 + 22, 2);
        ctx.fillStyle = C.mk; ctx.fillRect(-w / 2 + 32 + a1, -26, a2 + 18, 52); ctx.fillStyle = C.ink; ctx.font = '700 44px "Space Grotesk"'; ctx.fillText(palavra, -w / 2 + 41 + a1, 3);
        ctx.restore();
      }
    } else if (i === 5) {
      const L = Math.round(H * .46), bh = H - L;
      ctx.fillStyle = C.mk; ctx.fillRect(0, 0, W, L); this.pontilhado(ctx, C.ink, .14);
      this.janela(ctx, 28, 34 - 10 * lt, 484, L - 84, p.rotulo ?? 'O QUE ELE FEZ', ts, p.captura);
      // o rosto CENTRADO na metade de baixo, com folga: 3,4 alturas de rosto no quadro
      let ch = Math.min(H, f.h * 3.4), cw = ch * W / bh; if (cw > W) { cw = W; ch = cw * bh / W; }
      const sx = Math.max(0, Math.min(W - cw, fcx - cw / 2)), sy = Math.max(0, Math.min(H - ch, fcy - ch * .5));
      this.recorte(ctx, this.F, sx, sy, cw, ch, 0, L, W, bh);
      ctx.fillStyle = C.ink; ctx.fillRect(0, L - 9, W, 18); ctx.fillStyle = C.mk; ctx.fillRect(0, L - 3, W, 6);
      // com a legenda v3 ligada, a junção é dela
      const ws = this.state.legOn ? [] : this.palavras(p.legenda ?? D.legenda);
      if (ws.length) {
        const n = Math.min(ws.length, 1 + Math.floor(lt * ws.length * 1.4)), frase = ws.slice(0, n).join(' ');
        ctx.font = '700 40px "Space Grotesk"'; const tw = ctx.measureText(frase).width + 44;
        this.caixa(ctx, W / 2 - tw / 2, L - 34, tw, 68, '#fff', 8);
        ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(frase, W / 2, L + 2);
      }
    } else if (i === 6) {
      const [kz, , fim] = this.congelaDe(6, dd, p), fz = this.congela(kz, ts < fim);
      ctx.fillStyle = C.ink; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, '#fff', .1);
      const linhas = p.linhas || D.linhas;
      linhas.forEach((l, j) => {
        const cor = j === linhas.length - 1 ? C.mk : '#fff';
        const t0 = .15 + j * .3; if (ts < t0) return;
        const q = this.mola(Math.min(1, (ts - t0) / .2));
        ctx.save(); ctx.translate(W / 2, (p.y ?? 190) + j * (p.passo ?? 118)); ctx.scale(.7 + .3 * q, .7 + .3 * q); ctx.globalAlpha = Math.min(1, (ts - t0) / .05);
        this.texto(ctx, l, 0, 0, 104, cor, C.ac, 8); ctx.restore();
      });
      const corpo = fz ? fz.P : this.P, mask = fz ? fz.M : this.M2;
      ctx.save(); if (fz) { const z = 1 + .06 * Math.min(1, ts / fim), c = fz.face; ctx.translate(c.x + c.w / 2, c.y + c.h / 2); ctx.scale(z, z); ctx.translate(-(c.x + c.w / 2), -(c.y + c.h / 2)); }
      this.adesivo(ctx, '#fff', true, 5, 14, corpo, C.ac, mask); ctx.restore();
      const tg = p.tag ?? 'PAUSA';
      if (fz && tg) this.tag(ctx, tg, 30, 900, C.mk, C.ink, 22, -.04);
    } else if (i === 7) {
      ctx.fillStyle = C.mk; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, C.ink, .14);
      // a borda desce só até a testa: o que sai da moldura é o alto da cabeça, e o
      // microfone com o braço ficam inteiros DENTRO do cartão (se a borda passasse
      // abaixo da boca, o braço sairia flutuando sobre o amarelo)
      const e = this.mola(Math.min(1, lt / .18)), alvo = Math.min(H - 300, f.y + f.h * .28);
      const topo = 70 + (alvo - 70) * e, x0 = 44, x1 = W - 44, base_ = H - 70;
      ctx.fillStyle = C.ink; this.rr(ctx, x0 + 14, topo + 14, x1 - x0, base_ - topo, 16); ctx.fill();
      ctx.save(); this.rr(ctx, x0, topo, x1 - x0, base_ - topo, 16); ctx.clip(); this.cheio(ctx, this.F); ctx.restore();
      ctx.lineWidth = 7; ctx.strokeStyle = C.ink; this.rr(ctx, x0, topo, x1 - x0, base_ - topo, 16); ctx.stroke();
      // o que fica acima da borda de cima SAI da moldura: a sombra dura só fora do
      // cartão (dentro ela vira mancha sobre o vídeo), e o recorte cobre a borda
      // inteira, pra cabeça passar NA FRENTE dela
      const saida = () => { ctx.beginPath(); ctx.rect(fcx - f.w * 1.1, 0, f.w * 2.2, topo - 4); ctx.clip(); };
      ctx.save(); saida(); this.cheio(ctx, this.pintaMascara(this.T1, C.ink), 12, 12); ctx.restore();
      ctx.save(); ctx.beginPath(); ctx.rect(fcx - f.w * 1.1, 0, f.w * 2.2, topo + 8); ctx.clip(); this.cheio(ctx, this.P); ctx.restore();
      // `titulo`: linhas no vão de cima, acima da cabeça (a borda desce até a testa)
      [].concat(p.titulo || []).forEach((l, j) => {
        const t0 = .12 + j * .08; if (lt < t0) return;
        const q = this.mola(Math.min(1, (lt - t0) / .08));
        ctx.save(); ctx.translate(W / 2, (p.y ?? 92) + j * (p.passo ?? 66)); ctx.scale(.7 + .3 * q, .7 + .3 * q);
        this.texto(ctx, l, 0, 0, p.tam ?? 60, j === [].concat(p.titulo).length - 1 ? C.ac : C.ink, '#fff', 6);
        ctx.restore();
      });
      const tg = p.tag ?? 'SEM UMA LINHA DE CÓDIGO';
      if (tg && lt > .25) { const q = this.mola(Math.min(1, (lt - .25) / .08)); ctx.save(); ctx.translate(x0 + 20, base_ - 50); ctx.scale(q, q); this.tag(ctx, tg, 0, 0, C.ac, '#fff', 20, -.03); ctx.restore(); }
    } else if (i === 10) {
      ctx.fillStyle = C.papel; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, C.ink, .12);
      this.duo('grayscale(1) contrast(1.7) brightness(1.05)', null);
      this.adesivo(ctx, null, true, 3, 14, this.T3);
      const t0 = .35, carimbo = p.carimbo ?? 'MITO';
      if (ts > t0) {
        const sc0 = f.w / 165, q = Math.min(1, (ts - t0) / .18), e = 1 - Math.pow(1 - q, 4);
        const sc = (2.6 - 1.6 * e) * sc0, rot = (-24 + 14 * e) * Math.PI / 180, tr = ts - t0 < .3 ? Math.sin(ts * 90) * 4 * (1 - (ts - t0) / .3) : 0;
        ctx.save(); ctx.translate(fcx + tr, f.y + f.h * .16); ctx.rotate(rot); ctx.scale(sc, sc); ctx.globalAlpha = Math.min(1, q * 3);
        ctx.font = '700 58px "IBM Plex Mono"'; const w = ctx.measureText(carimbo).width + 40, h = 86;
        ctx.fillStyle = 'rgba(255,255,255,.92)'; this.rr(ctx, -w / 2, -h / 2, w, h, 10); ctx.fill();
        ctx.lineWidth = 9; ctx.strokeStyle = C.no; this.rr(ctx, -w / 2, -h / 2, w, h, 10); ctx.stroke();
        ctx.fillStyle = C.no; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(carimbo, 0, 3); ctx.restore();
      }
      const fr = p.frase ?? 'precisa saber programar';
      if (fr) {
        ctx.font = '700 38px "Space Grotesk"'; const fw = ctx.measureText(fr).width + 50;
        this.caixa(ctx, W / 2 - fw / 2, 820, fw, 76, '#fff', 10);
        ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(fr, W / 2, 860);
        if (ts > t0 + .5) { const q = Math.min(1, (ts - t0 - .5) / .3); ctx.fillStyle = C.no; ctx.fillRect(W / 2 - fw / 2 + 16, 853, (fw - 32) * q, 12); }
      }
    } else if (i === 11) {
      const s = .66, ox1 = W * .25 - W / 2 * s, ox2 = W * .75 - W / 2 * s, oy = H - H * s;
      const antes = {rotulo: 'ANTES', valor: '10–12h', ...p.antes}, depois = {rotulo: 'DEPOIS', valor: '< 4h', ...p.depois};
      ctx.fillStyle = '#E4E0D6'; ctx.fillRect(0, 0, W / 2, H); ctx.fillStyle = C.mk; ctx.fillRect(W / 2, 0, W / 2, H); this.pontilhado(ctx, C.ink, .1);
      this.duo('grayscale(1) contrast(1.1) brightness(1.15)', null);
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W / 2, H); ctx.clip(); ctx.translate(ox1, oy); ctx.scale(s, s); ctx.globalAlpha = .9; this.adesivo(ctx, null, true, 0, 12, this.T3); ctx.restore();
      if (lt > .2) { const q = this.mola(Math.min(1, (lt - .2) / .08)); ctx.save(); ctx.beginPath(); ctx.rect(W / 2, 0, W / 2, H); ctx.clip(); ctx.translate(W * .75, H); ctx.scale(q, q); ctx.translate(-W * .75, -H); ctx.translate(ox2, oy); ctx.scale(s, s); this.adesivo(ctx, '#fff', true, 5, 14); ctx.restore(); }
      ctx.fillStyle = C.ink; ctx.fillRect(W / 2 - 6, 0, 12, Math.min(1, lt / .15) * H);
      this.tag(ctx, antes.rotulo, 22, 70, '#fff', '#7C808B', 20, -.03);
      this.texto(ctx, antes.valor, W * .25, 230, 70, '#7C808B', null, 0, '"Space Grotesk"', 700, 'center', 230);
      if (lt > .3) { this.tag(ctx, depois.rotulo, W / 2 + 22, 70, C.ink, C.mk, 20, .03); this.texto(ctx, depois.valor, W * .75, 230, 92, C.ink, '#fff', 6, '"Space Grotesk"', 700, 'center', 230); }
    } else if (i === 12) {
      const n = p.n ?? 43, dest = p.destaques ?? 4, rotulo = p.rotulo ?? 'AGENTES';
      ctx.fillStyle = C.ac; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, '#fff', .14);
      if (!this.livres) this.calculaLivres(n);
      const tot = this.livres.length, janela = .62 * dd, acesas = Math.max(0, Math.min(tot, Math.floor((ts - .08 * dd) / janela * tot)));
      this.livres.forEach((c, k) => {
        if (k >= acesas) return;
        const age = ts - .08 * dd - k * janela / tot, q = this.mola(Math.min(1, age / .2));
        ctx.save(); ctx.translate(c.x + 32, c.y + 32); ctx.scale(q, q); this.caixa(ctx, -32, -32, 64, 64, k < dest ? C.mk : '#fff', 5, C.ink, 4, 8);
        if (k < dest) { ctx.fillStyle = C.ink; ctx.font = '700 22px "IBM Plex Mono"'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(k + 1).padStart(2, '0'), 0, 2); }
        // `icones`: um por azulejo, em rodízio — a quantidade ganha cara de cargo, não de contagem
        else if (p.icones && p.icones.length) { ctx.font = '30px "Apple Color Emoji","Noto Color Emoji",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(p.icones[(k - dest) % p.icones.length], 0, 2); }
        ctx.restore();
      });
      this.adesivo(ctx, '#fff', true, 5, 14);
      // a placa mede pelo total, não pelo contador: senão ela cresce a cada azulejo.
      // Rosto grande deixa menos de n células livres; o contador chega a n mesmo assim.
      ctx.font = '700 44px "Space Grotesk"'; const w = ctx.measureText(n + ' ' + rotulo).width + 50;
      this.caixa(ctx, W / 2 - w / 2, 850, w, 78, C.mk, 10);
      ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText((tot ? Math.round(acesas / tot * n) : 0) + ' ' + rotulo, W / 2, 890);
    } else if (i === 13) {
      const numero = p.numero ?? 2, total = p.total ?? 5, titulo = p.titulo ?? 'OS AGENTES', atual = Number(numero) - 1;
      ctx.fillStyle = C.ac; ctx.fillRect(0, 0, W, H);
      const e = 1 - Math.pow(1 - Math.min(1, lt / .1), 3); ctx.fillStyle = C.mk; ctx.fillRect(0, 0, W * e, H); this.pontilhado(ctx, C.ink, .12 * e);
      if (lt > .08) { const q = this.mola(Math.min(1, (lt - .08) / .08)); ctx.save(); ctx.translate(W / 2, 560); ctx.scale(.6 + .4 * q, .6 + .4 * q); this.texto(ctx, String(numero).padStart(2, '0'), 0, 0, 470, '#fff', C.ink, 16, '"Space Grotesk"', 700, 'center', 900); ctx.restore(); }
      this.adesivo(ctx, '#fff', true, 5, 14);
      // 5 segmentos de 88 com passo 98 na prévia; outro total divide a mesma faixa
      const passo = 490 / total, sw = passo - 10;
      for (let k = 0; k < total; k++) {
        const x = 30 + k * passo; ctx.fillStyle = C.ink; ctx.fillRect(x + 5, 45, sw, 18);
        ctx.fillStyle = k < atual ? C.ink : '#fff'; ctx.fillRect(x, 40, sw, 18); ctx.strokeStyle = C.ink; ctx.lineWidth = 4; ctx.strokeRect(x, 40, sw, 18);
        if (k === atual) { ctx.fillStyle = C.ac; ctx.fillRect(x + 2, 42, (sw - 4) * Math.min(1, lt / .6), 14); }
      }
      if (lt > .18) { const q = this.mola(Math.min(1, (lt - .18) / .08)); ctx.save(); ctx.translate(30, 110); ctx.scale(q, q); this.tag(ctx, p.tag ?? 'CAPÍTULO ' + numero, 0, 0, C.ink, C.mk, 26, -.03); ctx.restore(); }
      if (titulo && lt > .26) { const q = this.mola(Math.min(1, (lt - .26) / .08)); ctx.save(); ctx.translate(W / 2, 880); ctx.scale(q, q); this.texto(ctx, titulo, 0, 0, 84, C.ink, '#fff', 7); ctx.restore(); }
    } else if (i === 14) {
      const [kz, t0] = this.congelaDe(14, dd, p), fz = this.congela(kz, ts >= t0);
      const k = fz ? Math.min(1, (ts - t0) / Math.max(.5, dd - t0 - .2)) : 0, e = k * k * (3 - 2 * k);
      const fonte = fz ? fz.F : this.F, fc = fz ? fz.face : f, cx = fc.x + fc.w / 2, cy = fc.y + fc.h / 2;
      ctx.save(); const z = 1 + .28 * e; ctx.translate(cx, cy); ctx.scale(z, z); ctx.translate(-cx, -cy);
      ctx.filter = 'grayscale(' + e + ') contrast(' + (1 + .25 * e) + ')'; this.cheio(ctx, fonte); ctx.filter = 'none'; ctx.restore();
      const g = ctx.createRadialGradient(W / 2, H * .42, H * .18, W / 2, H * .42, H * .7); g.addColorStop(0, 'rgba(11,13,18,0)'); g.addColorStop(1, 'rgba(11,13,18,' + (.88 * e) + ')'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      const bar = 70 * Math.min(1, k * 3); ctx.fillStyle = C.ink; ctx.fillRect(0, 0, W, bar); ctx.fillRect(0, H - bar, W, bar);
      if (fz) this.grao_(ctx, ts, .2 * e);
    } else if (i === 16) {
      const cada = p.cada ?? .9, alinha = p.alinha ?? true, rot = p.rotulos ?? ['TAKE A', 'TAKE B'];
      const take = Math.floor(ts / cada) % 2;
      if (take === 0 || !this.FB) this.cheio(ctx, this.F);
      else {
        ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
        const fb = this.faceB; ctx.save();
        if (alinha && fb) { const k = f.h / fb.h; ctx.translate(fcx, fcy); ctx.scale(k, k); ctx.translate(-(fb.x + fb.w / 2), -(fb.y + fb.h / 2)); }
        this.cheio(ctx, this.FB); ctx.restore();
      }
      if (rot[take]) this.tag(ctx, rot[take], 24, 70, take ? C.mk : '#fff', C.ink, 20, 0);
    } else if (i === 17) {
      // loop aberto: o número da promessa atrás dele e as casas vazias até o item ser dito
      const itens = p.itens || D.itens, numero = String(p.numero ?? itens.length), titulo = p.titulo ?? 'AGENTES QUE FAZEM MEU TRABALHO';
      ctx.fillStyle = C.ac; ctx.fillRect(0, 0, W, H); this.pontilhado(ctx, '#fff', .14);
      const p0 = this.mola(Math.min(1, lt / .12));
      ctx.save(); ctx.translate(W / 2, 520); ctx.scale(.6 + .4 * p0, .6 + .4 * p0); this.texto(ctx, numero, 0, 0, 560, '#fff', C.ink, 18, '"Space Grotesk"', 700, 'center', 900); ctx.restore();
      this.adesivo(ctx, '#fff', true, 5, 14);
      if (titulo && lt > .06) { const q = this.mola(Math.min(1, (lt - .06) / .08)); ctx.save(); ctx.translate(30, 80); ctx.scale(q, q); this.tag(ctx, titulo, 0, 0, C.ink, C.mk, 20, -.02); ctx.restore(); }
      itens.forEach((txt, k) => {
        const y = 700 + k * 78, x = 40, w = 460, t0 = .25 + k * .22, on = lt > t0, q = on ? this.mola(Math.min(1, (lt - t0) / .07)) : 0;
        ctx.save(); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        if (on) { this.caixa(ctx, x, y, w * (.3 + .7 * q), 62, C.mk, 6, C.ink, 4, 10); ctx.globalAlpha = q; ctx.fillStyle = C.ink; ctx.font = '700 30px "Space Grotesk"'; ctx.fillText((k + 1) + '. ' + txt, x + 20, y + 33); }
        else { ctx.setLineDash([10, 8]); ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(255,255,255,.85)'; this.rr(ctx, x, y, w, 62, 10); ctx.stroke(); ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.font = '700 26px "IBM Plex Mono"'; ctx.fillText((k + 1) + '. ???', x + 20, y + 33); }
        ctx.restore();
      });
    } else if (i === 18) {
      // censura: o dado existe mas está borrado; no fim ABRE (a revelação é obrigatória)
      const rotulo = p.rotulo ?? 'FATURAMENTO', dado = p.dado ?? 'R$ 1 MILHÃO', promessa = p.promessa ?? 'NO FINAL EU MOSTRO', revela = p.revela ?? 'TÁ AQUI';
      this.cheio(ctx, this.F);
      const rev = lt > .82, pr = rev ? Math.min(1, (lt - .82) / .08) : 0, x = 60, y = 110, w = 420, h = 200, q = this.mola(Math.min(1, lt / .1));
      ctx.save(); ctx.translate(W / 2, y + h / 2); ctx.rotate(-.03); ctx.scale(q, q); ctx.translate(-W / 2, -(y + h / 2));
      this.caixa(ctx, x, y, w, h, '#fff', 10, C.ink, 5, 12);
      ctx.save(); this.rr(ctx, x + 3, y + 3, w - 6, h - 6, 9); ctx.clip(); ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = C.ink; ctx.font = '700 26px "IBM Plex Mono"'; ctx.fillText(rotulo, x + 24, y + 48);
      // o blur do filtro é em px do contexto: ×S pra ter o mesmo peso da prévia
      ctx.filter = 'blur(' + ((1 - pr) * 14 * this.S) + 'px)'; this.texto(ctx, dado, x + 24, y + 150, 80, C.ac, null, 0, '"Space Grotesk"', 700, 'left', w - 48); ctx.filter = 'none';
      ctx.restore(); ctx.restore();
      if (promessa && !rev && lt > .15) { const pp = this.mola(Math.min(1, (lt - .15) / .08)); ctx.save(); ctx.translate(W / 2 - 130, y + h + 34); ctx.scale(pp, pp); this.tag(ctx, promessa, 0, 0, C.mk, C.ink, 22, .04); ctx.restore(); }
      if (revela && rev) { ctx.save(); ctx.globalAlpha = pr; this.tag(ctx, revela, W / 2 + 40, y + h + 34, C.ink, C.mk, 22, -.04); ctx.restore(); }
    } else if (i === 19) {
      // zoom-out do close extremo: colado na boca, abre em 0,38 s, clarão e a frase bate
      const e = ts < .08 ? 0 : 1 - Math.pow(1 - Math.min(1, (ts - .08) / .38), 4);
      const z = 2.8 - 1.8 * e, cx = fcx, cy = f.y + f.h * .78, px = cx + (W / 2 - cx) * e, py = cy + (H / 2 - cy) * e;
      ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(z, z); ctx.translate(-px, -py); this.cheio(ctx, this.F); ctx.restore();
      if (e < 1) { ctx.save(); ctx.globalAlpha = 1 - e; ctx.strokeStyle = C.mk; ctx.lineWidth = 8; [[30, 30, 1, 1], [W - 30, 30, -1, 1], [30, H - 30, 1, -1], [W - 30, H - 30, -1, -1]].forEach(([x, y, sx, sy]) => { ctx.beginPath(); ctx.moveTo(x, y + sy * 60); ctx.lineTo(x, y); ctx.lineTo(x + sx * 60, y); ctx.stroke(); }); ctx.restore(); }
      if (Math.abs(ts - .47) < .04) { ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fillRect(0, 0, W, H); }
      const frase = p.frase ?? 'EU NÃO PROGRAMO';
      if (frase && ts > .52) { const q = this.mola(Math.min(1, (ts - .52) / .16)); ctx.save(); ctx.translate(30, 90); ctx.scale(q, q); this.tag(ctx, frase, 0, 0, C.mk, C.ink, 30, -.03); ctx.restore(); }
    } else if (i === 20) {
      // notificações caindo acima da cabeça, pilha de 3, contador de vendas
      const n = p.n ?? 5, passo = this.passoNotif(dd, p), cx = Math.max(200, Math.min(W - 200, fcx)), y0 = Math.max(90, f.y - 240);
      const titulo = p.titulo ?? 'Venda aprovada', valor = p.valor ?? 'R$ 197,00', quando = p.quando ?? 'agora';
      const cont = [].concat(p.contador ?? ['VENDA HOJE', 'VENDAS HOJE']);
      this.cheio(ctx, this.F);
      const chegou = [...Array(n).keys()].filter(k => ts > .2 + k * passo);
      this.ocupaCena = [[cx - 200, y0 - 60, cx + 200, y0 + 210]];
      chegou.forEach(k => {
        const idade = ts - (.2 + k * passo), q = this.mola(Math.min(1, idade / .28)), ordem = chegou.length - 1 - k;
        if (ordem > 2) return;
        const w = 380, h = 62, x = cx - w / 2, yy = y0 + ordem * 72 - (1 - q) * 60;
        ctx.save(); ctx.globalAlpha = Math.min(1, idade / .1) * (ordem === 2 ? .6 : 1);
        this.caixa(ctx, x, yy, w, h, '#fff', 6, C.ink, 4, 12);
        ctx.fillStyle = '#17A354'; this.rr(ctx, x + 10, yy + 10, 42, 42, 8); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = '700 24px "Space Grotesk"'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('$', x + 31, yy + 32);
        ctx.textAlign = 'left'; ctx.fillStyle = C.ink; ctx.font = '700 20px "Space Grotesk"'; ctx.fillText(titulo, x + 64, yy + 22);
        ctx.font = '600 20px "IBM Plex Mono"'; ctx.fillText(valor, x + 64, yy + 44);
        if (quando) { ctx.fillStyle = '#7C808B'; ctx.font = '600 14px "IBM Plex Mono"'; ctx.textAlign = 'right'; ctx.fillText(quando, x + w - 14, yy + 22); }
        ctx.restore();
      });
      if (chegou.length && cont.length) this.tag(ctx, chegou.length + ' ' + (chegou.length > 1 ? cont[cont.length - 1] : cont[0]), cx - 190, Math.max(40, y0 - 42), C.mk, C.ink, 20, -.03);
    } else if (i === 21) {
      // interrupção: clarão de 2 quadros, congela em P&B, a frase bate e depois sai
      const [kz, , fim] = this.congelaDe(21, dd, p), fz = this.congela(kz, ts < fim), fonte = fz ? fz.F : this.F;
      const tr = ts > fim && ts < fim + .3 ? Math.sin(ts * 70) * 8 * (1 - (ts - fim) / .3) : 0;
      ctx.save(); ctx.translate(tr, 0); if (fz) ctx.filter = 'grayscale(1) contrast(1.3)'; this.cheio(ctx, fonte); ctx.filter = 'none'; ctx.restore();
      if (fz) { ctx.fillStyle = 'rgba(11,13,18,.45)'; ctx.fillRect(0, 0, W, H); }
      if (ts < .06) { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); }   // 2 quadros a 30 fps (a prévia usava .07)
      const sai = lt > .55 ? Math.min(1, (lt - .55) / .08) : 0, linhas = p.linhas || D.interrompe;
      if (sai < 1) {
        ctx.save(); ctx.translate(-sai * W, 0);
        linhas.forEach((l, j) => {
          const t0 = j * .08; if (ts < t0) return;
          const q = 1 - Math.pow(1 - Math.min(1, (ts - t0) / .12), 4);
          ctx.save(); ctx.translate(W / 2, (p.y ?? 300) + j * (p.passo ?? 120)); ctx.scale(1.4 - .4 * q, 1.4 - .4 * q); this.texto(ctx, l, 0, 0, 120, j === linhas.length - 1 ? C.mk : '#fff', C.ink, 10); ctx.restore();
        });
        ctx.restore();
      }
    }
    ctx.restore();
  }

  duo(filtro, cor) {
    const W = this.W, H = this.H, d = this.T3.getContext('2d');
    d.globalCompositeOperation = 'source-over'; d.clearRect(0, 0, W, H);
    d.filter = filtro; this.cheio(d, this.P); d.filter = 'none';
    if (cor) { d.globalCompositeOperation = 'multiply'; d.fillStyle = cor; d.fillRect(0, 0, W, H); }
    d.globalCompositeOperation = 'destination-in'; this.cheio(d, this.M2); d.globalCompositeOperation = 'source-over';
  }
  congela(k, ativo) {
    this.fzs = this.fzs || {};
    if (!ativo) { delete this.fzs[k]; return null; }
    if (!this.fzs[k]) {
      const o = {F: this.cv(), P: this.cv(), M: this.cv(), face: {...this.face}};
      this.cheio(o.F.getContext('2d'), this.F); this.cheio(o.P.getContext('2d'), this.P); this.cheio(o.M.getContext('2d'), this.M2);
      this.fzs[k] = o;
    }
    return this.fzs[k];
  }
  janela(ctx, x, y, w, h, rot, ts, img) {
    const C = this.C;
    this.caixa(ctx, x, y, w, h, '#fff', 12);
    ctx.fillStyle = C.ink; ctx.fillRect(x + 2.5, y + 2.5, w - 5, 34);
    ctx.fillStyle = C.mk; ctx.font = '700 15px "IBM Plex Mono"'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(rot, x + 16, y + 20);
    ctx.save(); this.rr(ctx, x + 3, y + 37, w - 6, h - 40, 9); ctx.clip();
    if (img) this.captura(ctx, img, x + 3, y + 37, w - 6, h - 40);
    else {
      for (let yy = y + 37; yy < y + h; yy += 22) { ctx.fillStyle = (Math.floor((yy - y) / 22) % 2) ? '#E9E6DF' : '#F4F2EC'; ctx.fillRect(x, yy, w, 22); }
      const b = (ts * .5) % 1, bw = w * .7, bx = x + (w - bw) / 2, by = y + h * .66;
      ctx.fillStyle = '#fff'; ctx.fillRect(bx, by, bw, 24); ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.strokeRect(bx, by, bw, 24);
      ctx.fillStyle = C.ac; ctx.fillRect(bx + 2, by + 2, (bw - 4) * b, 20);
      ctx.fillStyle = '#7C808B'; ctx.font = '600 16px "IBM Plex Mono"'; ctx.textAlign = 'center'; ctx.fillText('CAPTURA REAL AQUI', x + w / 2, y + h * .45);
    }
    ctx.restore();
  }
}
if (typeof module !== 'undefined') module.exports = {Receitas};
if (typeof window !== 'undefined') window.Receitas = Receitas;
