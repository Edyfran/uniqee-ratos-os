/* _kit_legenda.js — núcleo comum das legendas k_legenda_foco e k_legenda_foco_titulo. Não é peça: o v2 só lista os .html.
   Tudo em px de 1080x1920 e em QUADROS DA REF (30 qps): `a0` é o primeiro quadro da ref que a peça cobre, e `tq(f)` põe o quadro na timeline.
   `modo=fiel` desenha com as cores e os textos da ref (por cima do próprio vídeo dela, só pra medir); `modo=nosso` é a adaptação:
   paleta e letra da direção (docs/direcao.md), textos em português, as ferramentas com o nome delas. */
(function () {
'use strict';
const FPS = 30;
const NOSSO = D.q('modo', 'nosso') === 'nosso';
const A0 = D.n('a0', 0);
// tvoz=ref:local,...  A voz refez o tempo da janela (28/10): pontos (quadro da ref, quadro local). Entre dois pontos é linear; depois do último, a velocidade é a da ref.
// Dois pontos no mesmo quadro da ref = o efeito fica parado esses quadros; dois no mesmo quadro local = esses quadros da ref saem. Sem `tvoz`, o tempo é o da ref.
const WP = String(D.q('tvoz', '')).split(',').filter(Boolean).map(s => s.split(':').map(Number));
const loc = f => {
  if (!WP.length) return f - A0;
  let i = 0; WP.forEach((p, j) => { if (p[0] <= f) i = j; });
  const [r, o] = WP[i], nx = WP[i + 1];
  return nx && nx[0] > r ? o + (f - r) * (nx[1] - o) / (nx[0] - r) : o + (f - r);
};
const tq = f => Math.max(0, loc(f) / FPS);
const T = (en, pt) => (NOSSO ? pt : en);
const SG = "'Space Grotesk',system-ui,sans-serif", MONO = "'IBM Plex Mono',ui-monospace,monospace";
const C = NOSSO
  ? {az: '#0640fb', ink: '#0B0D12', mk: '#F2C744', cod: '#12151C', cod2: '#1C1F26', tx: '#E8EAF0', dim: '#9AA0AD', kw: '#F2C744', kwClaro: '#0640fb',
     fTit: "Inter,system-ui,sans-serif", fSerif: "'Instrument Serif',serif", fMono: MONO, glow: false, amarelo: '#F2C744', brilho: '#0640fb', papel: '#FFFFFF'}
  : {az: '#0C8AF8', ink: '#0E0F10', mk: '#FBFF67', cod: '#0b0d12', cod2: '#14171d', tx: '#f2f3f5', dim: '#8b9099', kw: '#4AA3FF', kwClaro: '#0C8AF8',
     fTit: "Inter,system-ui,sans-serif", fSerif: "'Instrument Serif',serif", fMono: MONO, glow: true, amarelo: '#FBFF67', brilho: '#0C8AF8', papel: '#FFFFFF'};
const stage = document.getElementById('stage');

/* ------------------------------------------------------------------ DOM */
function mk(parent, css, html, cls) {
  const e = document.createElement('div');
  if (cls) e.className = cls;
  if (css) e.style.cssText = css;
  if (html != null) e.innerHTML = html;
  (parent || stage).appendChild(e);
  return e;
}
function rect(parent, x0, y0, x1, y1, css, html, cls) {
  return mk(parent, `position:absolute;left:${x0}px;top:${y0}px;width:${x1 - x0}px;height:${y1 - y0}px;${css || ''}`, html, cls);
}
/* texto com a largura da tinta igual a w (a letra da ref é outra: o corpo vem da caixa medida) */
function fit(el, w, max) {
  el.style.whiteSpace = 'nowrap';
  const cur = parseFloat(getComputedStyle(el).fontSize), got = el.scrollWidth || el.getBoundingClientRect().width;
  if (got > 0) el.style.fontSize = Math.min(max || 1e4, cur * w / got) + 'px';
}
let _seed = 7;
const rnd = () => ((_seed = (_seed * 1664525 + 1013904223) % 4294967296) / 4294967296);

/* ------------------------------------------------------------------ timeline (tudo buscável: set em 0 + to com immediateRender:false) */
function kf(tl, el, props) {          // props: {prop: [[quadro, valor], ...]}; linear entre os quadros
  for (const [p, pts] of Object.entries(props)) {
    tl.set(el, {[p]: pts[0][1], immediateRender: true}, 0);
    for (let i = 1; i < pts.length; i++) {
      const [f0] = pts[i - 1], [f1, v1] = pts[i];
      if (f1 <= f0) tl.set(el, {[p]: v1, immediateRender: false}, tq(f1));
      else tl.to(el, {[p]: v1, duration: (f1 - f0) / FPS, ease: 'none', immediateRender: false}, tq(f0));
    }
  }
}
function kfBox(tl, el, boxes) {      // boxes: [[quadro, x0, y0, x1, y1], ...] -> left/top/width/height
  kf(tl, el, {left: boxes.map(b => [b[0], b[1]]), top: boxes.map(b => [b[0], b[2]]),
              width: boxes.map(b => [b[0], b[3] - b[1]]), height: boxes.map(b => [b[0], b[4] - b[2]])});
}
function kfEsc(tl, el, fin, boxes) { // janela que só escala: el já está na caixa final `fin` ([x0,y0,x1,y1]); anda x, y, scale (origem 0 0)
  const W = fin[2] - fin[0];
  el.style.transformOrigin = '0 0';
  kf(tl, el, {x: boxes.map(b => [b[0], b[1] - fin[0]]), y: boxes.map(b => [b[0], b[2] - fin[1]]), scale: boxes.map(b => [b[0], (b[3] - b[1]) / W])});
}
function vis(tl, el, f0, f1) {       // visível em [f0, f1): só `visibility`, a opacidade é de quem a anima
  const on = f0 <= A0;
  tl.set(el, {visibility: on ? 'visible' : 'hidden', immediateRender: true}, 0);
  if (!on) tl.set(el, {visibility: 'visible', immediateRender: false}, tq(f0));
  if (f1 != null) tl.set(el, {visibility: 'hidden', immediateRender: false}, tq(f1));
}
function fade(tl, el, f0, f1, de, para, ease) {   // opacidade de `de` a `para` entre f0 e f1 (fora disso, segura)
  tl.set(el, {opacity: de, immediateRender: true}, 0);
  tl.to(el, {opacity: para, duration: Math.max(1, f1 - f0) / FPS, ease: ease || 'none', immediateRender: false}, tq(f0));
}
function blurIn(tl, el, f, q) {      // a palavra chega borrada e some o desfoque em `q` quadros (3)
  tl.set(el, {opacity: 0, immediateRender: true}, 0);
  tl.fromTo(el, {opacity: 0, filter: 'blur(12px)'}, {opacity: 1, filter: 'blur(0px)', duration: (q || 3) / FPS, ease: 'power2.out', immediateRender: false}, tq(f));
}
function blurOut(tl, el, f0, f1, ease) {   // desfoca e esmaece
  tl.to(el, {opacity: 0, filter: 'blur(14px)', duration: Math.max(1, f1 - f0) / FPS, ease: ease || 'none', immediateRender: false}, tq(f0));
}
function digita(tl, parent, texto, f0, f1, css, html) {   // revela letra a letra de f0 a f1; `html` = [[texto, css]] pra trechos de outra cor
  const w = mk(parent, `white-space:pre;${css || ''}`);
  const partes = html || [[texto, '']], n = partes.reduce((s, p) => s + p[0].length, 0);
  let i = 0;
  partes.forEach(([tx, c]) => [...tx].forEach(ch => {
    const s = document.createElement('span');
    s.textContent = ch; s.style.cssText = `opacity:0;${c}`;
    w.appendChild(s);
    tl.set(s, {opacity: 1, immediateRender: false}, tq(f0 + (f1 - f0) * (i++) / n));
  }));
  return w;
}

/* ------------------------------------------------------------------ peças de interface */
const TERM = {r: '#ff5f57', y: '#febc2e', g: '#28c840'};
function moldura(o) {
  return C.glow
    ? `border:2px solid rgba(46,152,255,.92);box-shadow:0 0 14px 2px rgba(12,138,248,.55),0 0 36px 4px rgba(12,138,248,.22);`
    : `border:4px solid ${C.ink};box-shadow:10px 10px 0 ${(o && o.sombra) || C.ink};`;
}
/* janela escura de app: barra de título com 3 bolinhas, título e selo à direita */
function janela(parent, x0, y0, x1, y1, o) {
  o = o || {};
  const w = rect(parent, x0, y0, x1, y1, `background:${o.bg || C.cod};border-radius:${o.r || 20}px;overflow:hidden;${o.semMold ? '' : moldura(o)}`);
  const W = x1 - x0;
  const barra = rect(w, 0, 0, W, 44, 'border-bottom:1px solid rgba(255,255,255,.07)');
  [[22, TERM.r], [46, TERM.y], [70, TERM.g]].forEach(([x, c]) => rect(barra, x - 7, 15, x + 7, 29, `background:${c};border-radius:50%`));
  const tit = mk(barra, `position:absolute;left:0;top:0;width:${W}px;height:44px;display:flex;align-items:center;justify-content:center;gap:10px;font:600 24px ${C.fTit};color:${C.tx};white-space:nowrap`, o.titulo || '');
  return {w, barra, tit, W, H: y1 - y0};
}
const ICONE = `<span style="display:inline-block;width:24px;height:24px;border-radius:7px;background:#E6794A;position:relative;vertical-align:middle"><i style="position:absolute;left:5px;top:7px;width:4px;height:4px;background:#fff;border-radius:50%;box-shadow:7px 0 #fff,0 7px #fff,7px 7px #fff"></i></span>`;
function selo(parent, W, txt, o) {   // pílula à direita da barra: ícone + texto (`o.cor` = pílula amarela do Openverse)
  o = o || {};
  const cor = o.cor ? `background:${o.cor};color:#1a1a1a;border:0` : `background:rgba(255,255,255,.06);color:${C.tx};border:1.5px solid rgba(255,255,255,.2)`;
  return mk(parent, `position:absolute;right:14px;top:6px;height:32px;padding:0 14px;border-radius:16px;display:flex;align-items:center;gap:8px;font:600 ${o.fs || 20}px ${C.fTit};white-space:nowrap;${cor}`,
            `${o.icone === false ? '' : (o.icone || ICONE.replace(/24px/g, '20px'))}<span>${txt}</span>`);
}
function onda(parent, x, y, w, h, cor, o) {   // forma de onda em barrinhas de 3 px
  o = o || {};
  const n = Math.max(4, Math.floor(w / 4)), box = rect(parent, x, y, x + w, y + h, 'overflow:hidden');
  for (let i = 0; i < n; i++) {
    const u = i / (n - 1), env = o.pico != null ? Math.exp(-Math.pow((u - o.pico) / (o.larg || .3), 2)) : Math.sin(Math.PI * u) * .8 + .2;
    const a = Math.max(.06, Math.min(1, env * (.35 + rnd() * .65)));
    rect(box, i * 4, h * (1 - a) / 2, i * 4 + 2.4, h * (1 + a) / 2, `background:${cor};border-radius:1px`);
  }
  return box;
}
function logoTessel(parent, x, y, s, o) {     // a marca da ref (dois quadrados e um ponto vermelho) + nome
  o = o || {};
  const g = mk(parent, `position:absolute;left:${x}px;top:${y}px;display:flex;align-items:center;gap:${s * .18}px;font:700 ${s}px ${C.fTit};color:${o.cor || '#fff'};white-space:nowrap;letter-spacing:-.02em`);
  mk(g, `position:relative;width:${s * .82}px;height:${s * .82}px`,
     `<i style="position:absolute;left:0;top:0;width:${s * .38}px;height:${s * .8}px;background:#fff;border-radius:${s * .08}px"></i><i style="position:absolute;left:${s * .44}px;top:0;width:${s * .38}px;height:${s * .38}px;background:#fff;border-radius:${s * .08}px"></i><i style="position:absolute;left:${s * .44}px;top:${s * .44}px;width:${s * .38}px;height:${s * .38}px;background:#ff3b30;border-radius:50%"></i>`);
  mk(g, '', T('tessel', 'fábrica'));
  return g;
}
const PROJ = T('tessel-launch', 'lancamento'), TLINHA = 'timeline';

/* o cartão de prévia branco ("Your week doesn't fit."): título em duas linhas, caixinhas cinza de agenda e a linha vermelha */
function cartaoSemana(parent, x0, y0, x1, y1, o) {
  o = o || {};
  const W = x1 - x0, H = y1 - y0;
  const c = rect(parent, x0, y0, x1, y1, `background:#fff;border-radius:${o.r != null ? o.r : 16}px;overflow:hidden`);
  [[.04, .18, .17, .1], [.2, .08, .13, .08], [.74, .1, .16, .07], [.06, .5, .2, .12], [.55, .6, .16, .1], [.78, .42, .15, .1], [.3, .78, .2, .1], [.62, .82, .2, .1], [.02, .8, .12, .1]]
    .forEach(([a, b, w, h]) => rect(c, W * a, H * b, W * (a + w), H * (b + h), 'background:#e6e7ea;border-radius:5px;filter:blur(1.2px)'));
  rect(c, 0, H * .52, W, H * .52 + 1.5, 'background:#e8423c');
  rect(c, W * .5 - 5, H * .52 - 4, W * .5 + 5, H * .52 + 6, 'background:#e8423c;border-radius:50%');
  const t = mk(c, `position:absolute;left:0;top:${H * .1}px;width:${W}px;text-align:center;font:800 ${H * (o.fs || .34)}px/${H * .3}px ${C.fTit};color:#0E0F10;letter-spacing:-.03em;white-space:nowrap`,
               `<div style="font-size:${.62}em;font-weight:600">${T('Your week', 'Seu vídeo')}</div><div style="margin-top:${H * .03}px">${T('doesn’t fit.', 'pronto.')}</div>`);
  return {c, t};
}
function cartaoMarca(parent, x0, y0, x1, y1) {   // prévia escura com a marca (dois quadrados e um ponto)
  const W = x1 - x0, H = y1 - y0;
  const c = rect(parent, x0, y0, x1, y1, 'background:radial-gradient(ellipse at 50% 50%,#1a1b20 0%,#0a0b0e 75%);border-radius:18px;overflow:hidden;border:1px solid rgba(255,255,255,.07)');
  const s = H * .3;
  const m = mk(c, `position:absolute;left:${W / 2 - s * .55}px;top:${H / 2 - s * .55}px;width:${s * 1.1}px;height:${s * 1.1}px`,
    `<i style="position:absolute;left:0;top:0;width:${s * .52}px;height:${s * 1.1}px;background:#fff;border-radius:${s * .12}px"></i><i style="position:absolute;left:${s * .6}px;top:0;width:${s * .5}px;height:${s * .5}px;background:#fff;border-radius:${s * .12}px"></i><i style="position:absolute;left:${s * .6}px;top:${s * .6}px;width:${s * .5}px;height:${s * .5}px;background:#ff3b30;border-radius:50%"></i>`);
  return {c, m};
}
function medidor(parent, x, y, w, h, nivel, o) {   // duas barras verticais; `nivel` 0..1 de altura da parte cheia
  const g = [];
  [0, 1].forEach(i => {
    const bx = x + i * (w / 2 + 2);
    rect(parent, bx, y, bx + w / 2 - 3, y + h, 'background:#171a20;border-radius:4px');
    g.push(rect(parent, bx, y + h * (1 - nivel), bx + w / 2 - 3, y + h, `background:${o && o.grad ? 'linear-gradient(#ff3b30,#ff9f1c 30%,#1a8cff 70%)' : C.brilho};border-radius:4px;transform-origin:50% 100%`));
  });
  return g;
}
function regua(parent, x0, y, passo, n, cor) {   // 0s 2s 4s ... em mono pequeno
  for (let i = 0; i < n; i++) {
    mk(parent, `position:absolute;left:${x0 + i * passo}px;top:${y}px;font:500 ${NOSSO ? 15 : 15}px ${C.fMono};color:${cor || '#7d828c'};white-space:nowrap;padding-left:4px;border-left:1px solid rgba(255,255,255,.22);height:16px;line-height:16px`, `${i * 2}s`);
  }
}
/* trilha de vídeo com os 4 clipes da ref: branco, "doesn't fit.", logo, e dois claros */
function trilhaV1(parent, x0, y0, x1, y1, o) {
  o = o || {};
  const W = x1 - x0, H = y1 - y0, r = rect(parent, x0, y0, x1, y1, 'overflow:hidden;border-radius:6px');
  const cl = (a, b, bg, html) => rect(r, W * a, 0, W * b, H, `background:${bg};border-radius:5px;overflow:hidden`, html);
  cl(0, .085, '#f2f3f5');
  cl(.085, .5, '#fff', `<div style="position:absolute;left:0;top:${H * .05}px;width:100%;text-align:center;font:800 ${H * .26}px/1.05 ${C.fTit};color:#0E0F10;letter-spacing:-.03em;white-space:nowrap">${T('Your week', 'Seu vídeo')}<br><span style="font-size:1.7em">${T('doesn’t fit.', 'pronto.')}</span></div>`);
  cl(.5, .73, '#050608', '');
  logoTessel(r, W * .53, H * .22, H * .34);
  cl(.73, .93, '#e8ecf4', `<div style="position:absolute;left:8%;top:35%;width:84%;height:30%;background:#fff;border-radius:99px;box-shadow:0 2px 8px rgba(0,0,0,.2)"></div>`);
  cl(.93, 1, '#dfe4ee', '');
  return r;
}

/* ------------------------------------------------------------------ chip e título dos cartões "Tool Number" */
function titulo(parent, txt, x0, y0, x1, y1, cor, natural) {   // palavras em spans (cada uma entra com o seu desfoque); fiel: a tinta mede x1-x0; nosso: corpo natural, centrado
  const e = mk(parent, `position:absolute;left:${x0}px;top:${y0}px;font:${NOSSO ? 800 : 700} 76px/1 ${C.fTit};color:${cor || C.ink};white-space:nowrap;letter-spacing:-.025em;display:inline-block`);
  const ps = txt.split(' ').map((w, i) => { const s = document.createElement('span'); s.style.display = 'inline-block'; s.textContent = w; if (i) e.appendChild(document.createTextNode(' ')); e.appendChild(s); return s; });
  if (!natural) fit(e, x1 - x0, 110);
  const r = e.getBoundingClientRect();
  if (natural) e.style.left = (540 - r.width / 2) + 'px';
  e.style.top = (y0 + ((y1 - y0) - r.height) / 2) + 'px';
  return {e, ps};
}
function chip(parent, x0, y0, xf, y1, txt, o) {      // chip azul: `x0` fixo, cresce até xf (largura animada fora); texto centrado na largura final, cortado pela caixa
  o = o || {};
  const box = rect(parent, x0, y0, xf, y1, `background:${C.az};overflow:hidden;border-radius:${NOSSO ? 10 : 9}px;${NOSSO ? `border:4px solid ${C.ink};box-shadow:10px 10px 0 ${o.sombra || C.ink};` : `box-shadow:0 0 28px rgba(12,138,248,.45);`}`);
  const t = mk(box, `position:absolute;left:0;top:0;width:${xf - x0}px;height:${y1 - y0}px;display:flex;align-items:center;justify-content:center;font:italic 400 ${o.fs || 120}px/1 ${C.fSerif};color:#fff;white-space:nowrap;-webkit-text-stroke:1.6px #fff`, `<span>${txt}</span>`);
  const sp = t.firstChild;
  if (o.w && !NOSSO) fit(sp, o.w, 200);
  if (o.fitN && NOSSO) fit(sp, o.fitN, 200);
  return {box, t, sp};
}

/* ------------------------------------------------------------------ janela de navegador (Safari) e as três páginas */
function navegador(parent, x0, y0, x1, y1, url, o) {
  o = o || {};
  const W = x1 - x0, H = y1 - y0;
  const w = rect(parent, x0, y0, x1, y1, `background:#fff;border-radius:22px;overflow:hidden;${moldura(o)}`);
  const barra = rect(w, 0, 0, W, 48, `background:${o.barra || '#eceef1'};border-bottom:1px solid rgba(0,0,0,.08)`);
  [[26, TERM.r], [50, TERM.y], [74, TERM.g]].forEach(([x, c]) => rect(barra, x - 7, 17, x + 7, 31, `background:${c};border-radius:50%`));
  rect(barra, 104, 16, 122, 32, 'border:2px solid #6b6f78;border-radius:3px');
  mk(barra, `position:absolute;left:138px;top:6px;font:400 26px ${C.fTit};color:#6b6f78`, '‹');
  const campo = rect(barra, W * .2, 6, W * .8, 42, 'background:#fff;border-radius:11px;display:flex;align-items:center;justify-content:center;gap:8px', `<span style="font:600 19px ${C.fTit};color:#555">🔒</span><span style="font:500 24px ${C.fTit};color:#1c1b1a">${url}</span>`);
  [[W - 128, 18, 12], [W - 84, 18, 12], [W - 44, 18, 12]].forEach(([x, y, s]) => rect(barra, x, y, x + s + 6, y + s + 4, 'border:2px solid #6b6f78;border-radius:3px'));
  const pag = rect(w, 0, 48, W, H, 'overflow:hidden;background:#fff');
  return {w, pag, W, H: H - 48, campo};
}
function paginaOpenverse(pag, W, H) {
  rect(pag, 0, 0, W, H, 'background:#FFE033');
  mk(pag, `position:absolute;left:28px;top:20px;font:700 17px ${C.fTit};color:#111;letter-spacing:-.01em`, '●●● openverse');
  mk(pag, `position:absolute;right:30px;top:22px;font:400 11px ${C.fTit};color:#222;white-space:nowrap;word-spacing:16px`, 'About Licenses Sources Search&nbsp;help Get&nbsp;involved API Terms Privacy Feedback');
  mk(pag, `position:absolute;left:78px;top:${H * .30}px;width:520px;font:400 ${NOSSO ? 40 : 44}px/1.18 ${C.fTit === SG ? "'Inter',sans-serif" : C.fTit};color:#1c1b1a;letter-spacing:-.01em`, T('Explore more than 800 million creative works', 'Explore mais de 800 milhões de obras criativas'));
  mk(pag, `position:absolute;left:78px;top:${H * .30 + 138}px;font:400 11px ${C.fTit};color:#333`, T('An extensive library of free stock photos, images, and audio, available for free use.', 'Uma biblioteca de fotos, imagens e áudios livres, de uso gratuito.'));
  const b = rect(pag, 78, H * .30 + 168, 78 + 420, H * .30 + 206, 'background:#fff;border-radius:3px;box-shadow:0 1px 3px rgba(0,0,0,.2)');
  mk(b, `position:absolute;left:12px;top:11px;font:400 11px ${C.fTit};color:#888`, T('Search for content', 'Buscar conteúdo'));
  rect(b, 384, 0, 420, 38, 'background:#C52B9B;border-radius:0 3px 3px 0');
  [[622, .27, '#2c2c2c', '#c9c4b8'], [729, .22, '#e0553a', '#7a2d1f'], [622, .50, '#1b1b1b', '#e8e0d0'], [729, .49, '#3f6f4a', '#c9d6cf'], [622, .74, '#b36a3c', '#2b2b2b'], [729, .75, '#2f7fd0', '#e7a63d']]
    .forEach(([cx, cy, a, bb]) => rect(pag, cx - 46, H * cy - 46 + 18, cx + 46, H * cy + 46 + 18, `border-radius:50%;background:radial-gradient(circle at 40% 35%,${bb},${a});`));
  mk(pag, `position:absolute;left:28px;bottom:14px;font:400 10px ${C.fTit};color:#333`, 'Part of the ⓦ project');
}
function paginaSemResultado(pag, W, H, hl) {
  rect(pag, 0, 0, W, H, 'background:#fff');
  const f = `font:600 ${NOSSO ? 44 : 46}px/1.26 ${C.fTit === SG ? "'Inter',sans-serif" : C.fTit};color:#0E0F10;letter-spacing:-.01em`;
  const t = mk(pag, `position:absolute;left:18px;top:${H * .30}px;width:${W - 36}px;${f}`,
    `<span class="hl" style="background:linear-gradient(90deg,#f9c8c8,#f9c8c8) no-repeat 0 100%/0% 100%;padding:2px 6px;margin-left:-6px">${T('We couldn\'t find anything for', 'Não achamos nada pra')}</span> ${T('"reversed glass shatter into a soft chime".', '"vidro quebrando ao contrário num sino suave".')}`);
  mk(pag, `position:absolute;left:18px;top:${H * .30 + 190}px;width:${W - 36}px;font:400 24px/1.35 ${C.fTit === SG ? "'Inter',sans-serif" : C.fTit};color:#1c1b1a`, T('Try a different query or use one of the external sources to expand your search.', 'Tente outra busca ou use uma das fontes externas pra ampliar a pesquisa.'));
  ['ccMixter', 'SoundCloud', 'Europeana', 'Free Music Archive'].forEach((n, i) => {
    const xs = [18, 150, 292, 444], ws = [118, 132, 140, 220];
    rect(pag, xs[i], H - 138, xs[i] + ws[i], H - 86, `border:1.5px solid #cfd1d6;border-radius:6px;display:flex;align-items:center;justify-content:center;font:500 19px ${C.fTit === SG ? "'Inter',sans-serif" : C.fTit};color:#222`, n + ' ↗');
  });
  return t.querySelector('.hl');
}
function paginaEarshot(pag, W, H) {
  rect(pag, 0, 0, W, H, 'background:#fff');
  const e = mk(pag, `position:absolute;left:49px;top:161px;transform-origin:0 0;display:inline-flex;align-items:center;gap:24px;white-space:nowrap`);
  mk(e, 'width:112px;height:150px;position:relative', `<svg viewBox="0 0 100 134" width="112" height="150"><path d="M50 6C24 6 8 26 8 52v18c0 8 9 8 9 0V52C17 32 30 17 50 17s33 15 33 35c0 24-13 33-22 44-7 9-6 19-6 24 0 8-6 14-14 14" fill="none" stroke="#0a0a0a" stroke-width="10" stroke-linecap="round"/><rect x="34" y="40" width="8" height="26" rx="4" fill="#1a73e8"/><rect x="47" y="30" width="8" height="46" rx="4" fill="#1a73e8"/><rect x="60" y="44" width="8" height="20" rx="4" fill="#1a73e8"/></svg>`);
  mk(e, `font:500 ${NOSSO ? 128 : 134}px/1 ${C.fTit === SG ? "'Inter',sans-serif" : C.fTit};color:#0a0a0a;letter-spacing:-.05em;white-space:nowrap`, `earshot <span style="color:#1a73e8">0.3</span>`);
  e.style.transform = `scale(${774 / e.getBoundingClientRect().width})`;
  const url = mk(pag, `position:absolute;left:0;top:${161 + 236}px;width:${W}px;text-align:center;font:400 13px ${C.fTit};color:#666;opacity:0`, 'github.com/Leon.../earshot');
  return {e, url};
}
function editorCompacto(w, W, H, o) {   // timeline de 840x468: tira de miniaturas, régua e trilhas vazias (a 07 e o começo da 08)
  o = o || {};
  const strip = trilhaV1(w, 28, 72, W - 28, 198);
  regua(w, 30, 214, W / 8.6, 9, '#7d828c');
  const rows = rect(w, 28, 244, W - 28, H - 18, 'background:#0e1015;border-radius:10px;border:1px solid rgba(255,255,255,.05)');
  [0, 1, 2].forEach(i => rect(rows, 8, 12 + i * 62, W - 64, 12 + i * 62 + 50, 'background:#13161c;border-radius:8px'));
  mk(rows, `position:absolute;left:12px;top:14px;font:500 15px ${C.fMono};color:#6b7079`, T('motion', 'movimento'));
  return {strip, rows};
}

/* O conteúdo da peça e a caixa dele (29/10, "legenda em cima dos motions em tela cheia"). Fundo = filho direto do palco sem filho nem texto, largo ou borrado (o fundo cheio, os
   brilhos, as sombras do canto); o resto é conteúdo. `desce_tudo` (px) desce o conteúdo todo, cada filho no seu próprio invólucro (a ordem de empilhamento não muda), no mesmo
   tamanho; o fundo fica no quadro. Só as peças de tela cheia sem rosto leem: a legenda ocupa o alto da zona e a peça abre espaço. `K.caixa()` = [topo, pé] do que está visível agora. */
const fundo = e => !e.firstElementChild && !e.textContent.trim() && (e.offsetWidth >= 1000 || /blur/.test(getComputedStyle(e).filter));
const conteudo = () => [...stage.children].map(e => (e.className === 'dt' ? e.firstElementChild : e)).filter(e => !fundo(e));
const caixa = () => conteudo().reduce((b, e) => {
  const cs = getComputedStyle(e), r = e.getBoundingClientRect();
  if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity < .05 || !r.height) return b;
  return b ? [Math.min(b[0], r.top), Math.max(b[1], r.bottom)] : [r.top, r.bottom];
}, null);
const DT = D.n('desce_tudo', 0);
if (DT) {
  const monta = D.monta;
  D.monta = fn => monta.call(D, tl => {
    const r = fn(tl);
    [...stage.children].filter(e => !fundo(e)).forEach(e => {
      const w = mk(null, `position:absolute;left:0;top:0;width:1080px;height:1920px;transform:translateY(${DT}px)`, null, 'dt');
      stage.insertBefore(w, e); w.appendChild(e);
    });
    return r;
  });
}

window.K = {caixa, FPS, NOSSO, A0, tq, T, C, MONO, stage, mk, rect, fit, rnd, kf, kfBox, kfEsc, vis, fade, blurIn, blurOut, digita, TERM, moldura, janela, ICONE, selo, onda,
            logoTessel, PROJ, TLINHA, cartaoSemana, cartaoMarca, medidor, regua, trilhaV1, titulo, chip, navegador, paginaOpenverse, paginaSemResultado, paginaEarshot, editorCompacto};
})();
