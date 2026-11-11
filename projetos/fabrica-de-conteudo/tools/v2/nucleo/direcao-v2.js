/* O ritmo da VSL, v2. Mesma API do pipeline: window.__tl (pausada),
   window.__duration, window.__ready — o html_para_video.py não muda.

   O renderer BUSCA a linha do tempo quadro a quadro. Então todo movimento —
   inclusive o que flutua e respira — mora na timeline. Nada de CSS animation,
   nada de requestAnimationFrame: o que não está na timeline não sai no vídeo.

   `t` continua significando "ESTÁ NA TELA", não "começa a se mexer" (ANTECIPA).

   Um perfil de movimento (PERFIS.a). Ele muda a mola, a queda e a saída —
   nunca o tempo das falas.

   Novo:
     D.monta(fn)      espera a fonte, mede, monta a timeline e só então __ready.
                      Toda a montagem acontece DEPOIS da fonte — é o que deixa
                      medir, dividir palavra e animar na ordem certa.
     D.pousa          a peça cai e a sombra dura aparece quando ela toca o chão (sem quicar)
     D.palavras       texto sobe palavra a palavra por máscara
     D.titulo         palavras + o marcador varre a <b>
     D.carimbo        etiqueta que bate na tela
     D.desliza        um foco que anda de item em item
     D.flutua         micro-movimento contínuo (peças sobre o apresentador)
     D.sai            saída dentro da peça. ?sai=0 desliga, quando o compositor
                      já tira a peça com o `sobe` do plano. */
(function () {
const R = document.documentElement;
// Duas fontes de parâmetro: a URL e as variáveis do HyperFrames Studio (o padrão declarado em
// data-composition-variables, ou o getVariables() do runtime deles quando ele está na página).
// A URL ganha. Sem as duas, a peça sai como sempre. Quem monta a mesa é o `v2.py mesa`.
const U = new URLSearchParams(location.search);
const vars = () => {
  const hf = window.__hyperframes;
  if (hf && hf.getVariables) return hf.getVariables() || {};
  try { return Object.fromEntries(JSON.parse(R.dataset.compositionVariables || '[]').map(v => [v.id, v.default])); }
  catch (e) { return {}; }
};
const Q = {get: k => { if (U.has(k)) return U.get(k); const v = vars()[k]; return v == null ? null : String(v); }};
const DIR = 'a';   // direção fechada (2a/3c); ?dir é ignorado
R.dataset.dir = DIR;
if ((Q.get('ar') || '').startsWith('1080x1920')) R.classList.add('v');
// 920x730 — o painel da e_dividida (tela dividida): a peça desenha na medida do painel e a e_dividida a hospeda num iframe (html.pn, direcao-v2.css)
if ((Q.get('ar') || '').startsWith('920x730')) R.classList.add('pn');
// a faixa do player do YouTube no 16:9: os 184 de 1080 de baixo são da barra de progresso e dos
// controles (a conta no LEIA-ME, "Faixa do player"; o qa.js reprova o que entra). D.PE em px,
// --yt-pe no CSS: 0 fora do 16:9, então a peça que serve aos dois formatos usa sem perguntar.
const PE = innerWidth * 9 === innerHeight * 16 ? Math.round(innerHeight * 184 / 1080) : 0;
R.style.setProperty('--yt-pe', PE + 'px');
if (Q.get('k')) R.style.setProperty('--k', Q.get('k'));
// ?alfa=1 tira o papel de qualquer peça de tela cheia (renderize com --alpha)
if (Q.get('alfa') === '1') R.classList.add('alfa');
// ?chao=1 — peça transparente sobre o papel do tema, quando ela TOMA a tela (o explicador
// de aula que corta a gravação). Quem pinta o chão é o núcleo, não quem chama.
if (Q.get('chao') === '1') R.classList.remove('alfa');
// ?pip=1 — a peça de tela cheia deixa a pessoa na tela: o conteúdo encolhe pra esquerda e a
// moldura do cartão dela (direcao-h.css, html.pip) fica à direita. Quem põe o vídeo dentro é o
// v2.sobre (`pip` em helpers/estilo.py, desenho.pip): a peça só desenha a moldura.
if (Q.get('pip') === '1') R.classList.add('pip');
// ?tema=tinta — chão tinta em qualquer peça (ver direcao-v2.css)
if (Q.get('tema') === 'tinta') R.classList.add('tinta');
// ?tema=tinteiro — o canal de Lorcana (ver direcao-v2.css). A letra dele não é a das peças,
// então a fonte entra aqui; o D.monta espera a do --fd antes do primeiro quadro.
if (Q.get('tema') === 'tinteiro') {
  R.classList.add('tinteiro');
  const f = document.createElement('link');
  f.rel = 'stylesheet';
  f.href = 'https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600;700;800;900&display=block';
  // o D.monta espera ESTA folha: antes dela a regra @font-face nem existe, o fonts.load
  // volta na hora, e a medida sai com a letra substituta — o título do lote do Mercado
  // Livre encolheu na medida da letra estreita e vazou da tela com a Unbounded (29/09)
  window.__folha = new Promise(r => { f.onload = f.onerror = r; setTimeout(r, 8000); });
  document.head.appendChild(f);
}
// ?tema=marca — a marca do aluno: marca/tema.css, na raiz da fábrica (ao lado de tools/), por cima
// do núcleo. Ela redeclara os tokens em html.marca e traz a própria letra (@font-face por caminho).
// O D.monta espera a folha E as faces dela: a peça que mede o título (D.cabe) mediria a substituta.
// Fica em __tema, não em __folha, porque peça que espera a própria letra sobrescreve a __folha.
if (Q.get('tema') === 'marca') {
  R.classList.add('marca');
  const f = document.createElement('link');
  f.rel = 'stylesheet';
  f.href = new URL('../../../marca/tema.css', document.currentScript.src).href;
  window.__tema = new Promise(r => {
    f.onload = r;
    f.onerror = () => { console.error('tema marca: não achei ' + f.href); r(); };
    setTimeout(r, 8000);
  }).then(() => Promise.all([...document.fonts].map(x => x.load().catch(() => null))));
  document.head.appendChild(f);
}
// ?tema=neon — o vidro roxo do anúncio com avatar (ver direcao-v2.css). A letra entra aqui, como a
// do tinteiro, e o D.monta espera a folha antes de medir.
if (Q.get('tema') === 'neon') {
  R.classList.add('neon');
  const f = document.createElement('link');
  f.rel = 'stylesheet';
  f.href = 'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,500;9..40,700;9..40,800;9..40,900&family=JetBrains+Mono:wght@500;700;800&display=block';
  window.__folha = new Promise(r => { f.onload = f.onerror = r; setTimeout(r, 8000); });
  document.head.appendChild(f);
}
// ?tema=capa — o chão da capa do Reel (g_capa_nick): azul-marinho, grade de ladrilhos, letra pesada e faixa vermelha.
// O cartão (cartao.js, cartao.css) desenha a grade e troca marca, título e ícones; a letra (Inter 900) vem do editorial.css.
if (Q.get('tema') === 'capa') {
  R.classList.add('capa');
  const f = document.createElement('link');
  f.rel = 'stylesheet';
  f.href = new URL('editorial.css', document.currentScript.src).href;
  window.__folha = new Promise(r => { f.onload = f.onerror = r; setTimeout(r, 8000); })
    .then(() => document.fonts.load('900 100px Inter').catch(() => null));
  document.head.appendChild(f);
}
// ?i3d=contida|media|ousada — a intensidade do 3D (D.palco3d, D.espessura, D.luz, D.deriva): a lente,
// a espessura, a força da luz, o quanto a câmera anda e o quanto a pilha se abre parada. O plano
// escolhe, e pode variar entre criativos; sem o parâmetro, a média, que é a dos tokens do CSS.
// Aprovada pelo dono em 04/10/2026 ("gostei da intensidade, podemos variar"): 3D-REFERENCIA.md.
const I3DS = {contida: {persp: 2400, esp: 8, luz: .6, deriva: .5, abre: .06},
  media: {persp: 1800, esp: 10, luz: 1, deriva: .8, abre: .12},
  ousada: {persp: 1300, esp: 14, luz: 1.35, deriva: 1, abre: .2}};
const I3D = {nome: I3DS[Q.get('i3d')] ? Q.get('i3d') : 'media', ...(I3DS[Q.get('i3d')] || I3DS.media)};
if (I3DS[Q.get('i3d')]) {
  R.style.setProperty('--persp', I3D.persp + 'px');
  R.style.setProperty('--esp', I3D.esp + 'px');
}
window.__ready = false;
/* Cues de efeito sonoro: [{t, tipo, ...}], em segundos do vídeo, no instante
   em que a coisa ESTÁ na tela. O html_para_video.py salva isto em
   <saída>.cues.json ao lado do .mov. Vocabulário fixo, pra biblioteca de SFX
   ter um arquivo por nome (a lista inteira, com o uso de cada um, está em
   sfx/sfx.json): pop · click · stamp · impact · whoosh · whoosh-out · swish ·
   tick-roll · type · ding · riser* · boom · sub-drop · hit · swell* · tom ·
   shimmer · tape-stop · glitch · thud · papel · marca · mouse · notif · venda ·
   certo · erro · obturador · zoom-in      (* termina no instante do cue) */
window.__cues = [];

const PERFIS = {
  // Entra firme e freia sem passar do ponto (POUSA, o pousa e o carimbo); a mola fica pra quem
  // pede (MOLA, HEROI). Medido em 03/10: as referências chegam a 90 % em 67–200 ms e nunca passam
  // do ponto; o back.out passava 10–15 % e a queda de 48 px andava 10 px num quadro.
  a: {ENT: .50, EASE: 'power4.out', POUSA: 'expo.out', MOLA: 'back.out(1.7)', HEROI: 'back.out(2.1)',
      SAI: 'power3.in', TILT: 0, ROT: -1.2, QUEDA: 16,
      // 3D: a luz vem de cima e da esquerda, na frente (x à direita, y pra baixo, z pra quem
      // assiste); a face escurece até 55 % virando de costas pra ela e clareia até 22 % de frente
      LUZ: [-.45, -.6, .66], ESCURO: .55, CLARO: .22},
};
const P = {...PERFIS[DIR]};
P.ESCURO = Math.min(.8, P.ESCURO * I3D.luz); P.CLARO = Math.min(.35, P.CLARO * I3D.luz);
/* ── Os 12 princípios no núcleo (12/10/2026). As fontes de cada número estão em
   pesquisa/animacao-principios/ESTUDO.md: Lasseter (SIGGRAPH 1987, a seção entre parênteses), o
   "Motion Lab" do @flxrnc, a skill motion-design da LottieFiles e as medianas medidas do motionmaxxing
   (pesquisa/motionmaxxing/ESTUDO.md). As peças herdam: quem chama D.pousa, D.carimbo, D.heroi,
   D.palavras, D.desliza, D.digita, D.conta e D.sai não reimplementa nada. */
const QD = 1 / 30;   // um quadro: o render grava a 30 qps
// 10. Exagero. No celular a pose vai 10–30 % além do que parece certo, porque o feed encolhe tudo
// (@flxrnc): 1,2 em pé, 1,0 deitado. ?exagero= calibra. Só objeto exagera; texto fica natural, e é a
// régua do resto (Lasseter 2.9: "if there is an element that the audience can recognize... that
// becomes the ground for comparison").
const EX = parseFloat(Q.get('exagero')) || (innerHeight > innerWidth ? 1.2 : 1);
const $ = s => typeof s === 'string' ? document.querySelector(s) : s;
const $$ = s => typeof s === 'string' ? [...document.querySelectorAll(s)]
  : Array.isArray(s) ? s.flatMap(x => typeof x === 'string' ? [...document.querySelectorAll(x)] : [x]).filter(Boolean)
  : [s].filter(Boolean);
if (R.classList.contains('pip')) document.addEventListener('DOMContentLoaded', () =>
  document.getElementById('stage').insertAdjacentHTML('afterbegin', '<div id="pipm"></div>'));
const css = n => getComputedStyle(R).getPropertyValue(n).trim();

const D = window.D = {
  DIR, P, I3D, PE, ANTECIPA: .18, PASSO: .34, tl: null, css, $, $$, QD, EX,
  /* 9. Temporização: uma tabela por papel, não 0,5 s pra tudo (Lasseter 2.2: "timing... reflects the
     weight and size of an object"). Medianas medidas do motionmaxxing, conferidas com as faixas do
     @flxrnc e da LottieFiles:
       peso   a entrada pela área da peça no quadro: leve (pílula, etiqueta, chip) 6 quadros = .2 s,
              médio (cartão, item) 12 = .4 s, pesado (painel) 15 = .5 s. A saída de bloco dura o mesmo
              que a entrada e acelera; só a palavra sai bem mais rápido (motionmaxxing: 12 f contra
              13-14; palavra 12-15 contra 3-4) — o "saída 40–50 % mais curta" do @flxrnc vale pra texto.
       heroi  .75 s (revelação de herói 600–900 ms, @flxrnc; 11–30 f, motionmaxxing)
       item   2 quadros entre irmãos, irregular (56 % dos intervalos medidos são de 1 f, mediana 3)
       palavra 2 quadros (60–120 ms, @flxrnc), com cadência (D._cadencia)
       orcamento  a cascata inteira cabe em .5 s (LottieFiles e HyperFrames: "total stagger < 500ms") */
  T: {peso: {leve: .2, medio: .4, pesado: .5}, heroi: .75, item: 2 * QD, palavra: 2 * QD, orcamento: .5},
  // ?vivo=1 — a peça na live (fonte de navegador do OBS): pronta, a timeline TOCA em tempo
  // real, uma vez. Sem ele, a de sempre: pausada, buscável, pro render e pro qa.
  vivo: Q.get('vivo') === '1',
  // Parâmetro AUSENTE cai no exemplo; parâmetro passado VAZIO fica vazio. Antes os
  // dois caíam no exemplo, e uma citação sem fonte saía assinada "The Verge".
  q(k, d) { const v = Q.get(k); return v === null ? d : v; },
  n(k, d) { const v = Q.get(k); return parseFloat(v === null || v === '' ? d : v); },
  at(t) { return Math.max(0, t - D.ANTECIPA); },
  get SH() { return parseFloat(css('--sh')) || 10; },
  inclina(i) { return P.TILT ? (i % 2 ? P.TILT : -P.TILT) : 0; },
  brl: n => 'R$ ' + Math.round(n).toLocaleString('pt-BR'),
  // A marca oficial dentro de um texto: {claude} e {codex} viram o logo (midia/logo-*.svg), na altura da letra.
  logo: s => String(s).replace(/\{(claude|codex)\}/g, (_, n) =>
    `<img class="lg" src="../midia/logo-${n === 'claude' ? 'claude-code' : 'codex'}.svg" alt="">`),

  /* Lugar nomeado: quem chama diz `lugar=terco-dir|terco-esq|centro`, e o núcleo diz onde é.
     No 16:9, o terço é o centro a TERCO px do meio do quadro (a carta citada ao lado do rosto); a
     peça em pé centra. Sem `lugar`, vale o vocabulário antigo da peça (`lado` + `x`, com o padrão
     dela), pra plano velho sair igual. `desloc` é o x do centro em relação ao meio do quadro. */
  TERCO: 600,
  LUGARES: {'terco-dir': 1, 'terco-esq': -1, centro: 0},
  // a carta de Lorcana: a largura em que ela entra ao lado do rosto no 16:9 e a proporção dela
  CARTA: {larg: 400, prop: .717},
  desloc(padrao = 0) {
    const l = Q.get('lugar');
    if (l !== null) {
      if (!(l in D.LUGARES)) throw new Error(`lugar desconhecido: ${l} (${Object.keys(D.LUGARES).join(', ')})`);
      return D.LUGARES[l] * D.TERCO;
    }
    return (D.q('lado', 'dir') === 'esq' ? -1 : 1) * D.n('x', padrao);
  },
  /* a caixa [x, y, w, h] da carta num lugar — o alvo do rabisco, do zoom. Em pé a carta centra
     com 62 % da largura (o g_traduz); deitada, `larg` px no terço */
  carta(lugar, larg = D.CARTA.larg) {
    if (!(lugar in D.LUGARES)) throw new Error(`lugar desconhecido: ${lugar}`);
    const W = innerWidth, H = innerHeight, vert = H > W;
    const w = vert ? W * .62 : larg, h = w / D.CARTA.prop;
    return [vert ? (W - w) / 2 : W / 2 + D.LUGARES[lugar] * D.TERCO - w / 2, (H - h) / 2, w, h];
  },

  /* "Nome|detalhe@0.4;Outro|x@1.2" → [{nome, det, t}] */
  itens(k, d, campos) {
    return D.q(k, d).split(';').filter(Boolean).map(s => {
      const [resto, t] = s.split('@');
      const p = resto.split('|'), o = {t: parseFloat(t)};
      campos.forEach((c, i) => o[c] = p[i]);
      return o;
    });
  },

  cue(t, tipo, extra = {}) {
    window.__cues.push({t: Math.round(Math.max(0, t) * 1000) / 1000, tipo, ...extra});
  },

  entra(alvo, t, dy = 26) {
    return D.tl.fromTo(alvo, {opacity: 0, y: dy}, {opacity: 1, y: 0,
      duration: P.ENT, ease: P.EASE}, D.at(t));
  },

  /* leve, médio ou pesado, pela área no quadro (as classes de peso da LottieFiles: badge e ícone,
     cartão, modal e painel) */
  peso(el) {
    const a = (el.offsetWidth || 0) * (el.offsetHeight || 0) / (innerWidth * innerHeight);
    return a > .25 ? 'pesado' : a > .08 ? 'medio' : 'leve';
  },
  /* a duração cresce com a distância (LottieFiles: 100 px = 1×, 200 = 1,3×, 300 = 1,5×, 400 = 1,6×,
     a tela inteira 1,8–2×); abaixo de 100 px não encurta */
  longe(px) {
    const T = [[100, 1], [200, 1.3], [300, 1.5], [400, 1.6], [1080, 1.9]];
    if (px <= 100) return 1;
    for (let i = 1; i < T.length; i++) if (px <= T[i][0])
      return T[i - 1][1] + (T[i][1] - T[i - 1][1]) * (px - T[i - 1][0]) / (T[i][0] - T[i - 1][0]);
    return 1.9;
  },
  /* 12. Apelo: nada de gêmeos (Lasseter 2.11: "twins... gives the pose a stiff, wooden, unappealing
     quality"). Cada entrada do núcleo puxa um número desta sequência fixa (seekável, sem Math.random)
     e varia o lado e a medida do giro e o intervalo da cascata. */
  _n: 0,
  _vez() { return D._n++; },

  /* Mola como função pura do tempo (o spring() do motion.js do @flxrnc), virada ease do GSAP: dura até
     o envelope cair a 1 %. ζ é a razão de amortecimento: 1 não quica, .8 "premium", .6 quica 5–10 %
     (a tabela de mola do HyperFrames; abaixo de .55, "Don't"). f em Hz. */
  mola(zeta = .8, f = 3) {
    const w = 2 * Math.PI * f, z = Math.min(zeta, 1), dur = Math.log(100) / (z * w);
    const wd = w * Math.sqrt(Math.max(1e-6, 1 - zeta * zeta));
    const x = t => zeta >= 1 ? 1 - Math.exp(-w * t) * (1 + w * t)
      : 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + zeta * w / wd * Math.sin(wd * t));
    const fim = x(dur);
    return {dur, ease: p => p >= 1 ? 1 : x(p * dur) / fim};
  },

  /* 1. Esmagar e esticar. O volume não muda (Lasseter 2.1: "no matter how squashed or stretched out a
     particular object gets, its volume remains constant"): sx·sy = 1. Impacto em 2 quadros e volta em
     mola ζ .6 (LottieFiles: impacto 2–4 quadros, volta 4–8). O eixo é o do caminho (Lasseter: "the
     direction of the stretch should be along the path of action"): 'y' é o chão, achata em y e o pé
     fica onde tocou; 'z' é o carimbo que bate no papel — achatar na profundidade espalha x e y juntos. */
  amassa(alvo, t, a = .04, eixo = 'y') {
    const el = $(alvo); if (!el || !a) return;
    a *= EX;
    const m = D.mola(.6, 4), h = el.offsetHeight || 0, data = D._ent;
    const bate = eixo === 'z' ? {scaleX: 1 + a, scaleY: 1 + a}
      : {scaleX: 1 + a, scaleY: 1 / (1 + a), y: h * a / (1 + a) / 2};
    D.tl.to(el, {...bate, duration: 2 * QD, ease: 'power2.out', data}, t);
    D.tl.to(el, {scaleX: 1, scaleY: 1, ...(eixo === 'z' ? {} : {y: 0}), duration: m.dur, ease: m.ease, data}, t + 2 * QD);
  },
  // quanto o material cede (LottieFiles: papel 3–5 %, rígido 0; o leve, 5–15 %). Captura, vídeo,
  // objeto 3D e texto solto não cedem (Lasseter 2.1: "only the most rigid shapes... remain so")
  _material(el, peso) {
    if (!el.classList.contains('nb') || el.classList.contains('d3') || el.querySelector('img,video,canvas')) return 0;
    return peso === 'leve' ? .05 : 0;
  },

  /* 8. Ação secundária: o palco acusa o impacto. Resulta da ação principal e fica abaixo dela
     (Lasseter 2.10: "always kept subordinate to the primary action"): 40 % do deslocamento do impacto,
     2 quadros depois, noutra curva (LottieFiles: amplitude 30–50 %, 50–100 ms depois, "different
     easing"). Em y, que o D.camera não usa. */
  reage(t, px) {
    const st = $('#stage'); if (!st || !(px > .5)) return;
    const m = D.mola(.6, 5);
    D.tl.to(st, {y: px * .4, duration: 2 * QD, ease: 'power2.out'}, t + 2 * QD);
    D.tl.to(st, {y: 0, duration: m.dur, ease: m.ease}, t + 4 * QD);
  },

  /* 7. Arcos. O caminho e o tempo são curvas separadas (Lasseter 2.8: "the spline that defines the path
     of action should be separate from the spline that defines the timing"). Leva o alvo de [x0, y0] a
     [x1, y1] por uma Bézier com a flecha no meio, perpendicular: 10–20 px (LottieFiles, "10-20px
     perpendicular offset at path midpoint"; 5 no corporativo) ou o que a peça pedir em o.flecha. O
     tempo é o ease. Pra peça que atravessa a tela: x e y num tween só andam em reta. */
  arco(alvo, t, de, para, o = {}) {
    const el = $(alvo); if (!el) return;
    const [x0, y0] = de, [x1, y1] = para, L = Math.hypot(x1 - x0, y1 - y0) || 1;
    const f = (o.flecha ?? Math.min(20, Math.max(5, L * .1)) * EX) * (o.lado ?? 1);
    const cx = (x0 + x1) / 2 - (y1 - y0) / L * f * 2, cy = (y0 + y1) / 2 + (x1 - x0) / L * f * 2;
    const p = {u: 0};
    // immediateRender: false — antes de `t` o alvo fica onde está (o cursor faz vários arcos seguidos)
    return D.tl.fromTo(p, {u: 0}, {u: 1, duration: o.dur ?? D.T.peso.medio * D.longe(L), ease: o.ease || 'power3.inOut',
      immediateRender: false, data: o.data, onUpdate: () => { const u = p.u, v = 1 - u; gsap.set(el, {x: v * v * x0 + 2 * v * u * cx + u * u * x1, y: v * v * y0 + 2 * v * u * cy + u * u * y1}); }}, t);
  },

  /* A peça cai e aterrissa, em camadas (Lasseter 2.6, o jeito do keyframe em 3D: "one transformation is
     animated at a time... Not all translates, rotates and scales have extremes on the same frames"):
       y      chega com a escala de profundidade (1,02 → 1). Leve (pílula, chip, etiqueta) cai ACELERANDO
              e amassa no chão (1; a bola de Lasseter 2.1, espaçada larga no chão); médio e pesado
              pousam freando em power3.out, a curva medida de todo dia (o expo.out, que era de tudo,
              fica pro herói: motionmaxxing, softLand × snapSettle)
       sombra aterrissa 2 quadros depois do corpo (5; LottieFiles: "shadow arrives 50ms after card")
       giro   cai girando e assenta por último (7, Lasseter 2.8: "even in a straight line action, the
              object rotates"); cada peça pro seu lado e com sua medida (12: sem gêmeos)
       x      desliza noutra curva: com dx, o caminho é um arco (7). Entrada de lado (|dx| > |dy|) vai
              pelo D.arco, com a corcova pra cima
     A duração vem do peso e da distância (9). Quem pede a mola ({ease: D.P.MOLA}) leva a mola no
     corpo e não amassa. Vários alvos não caem no mesmo quadro (3, 5): cascata de 2–3 quadros. */
  pousa(alvo, t, o = {}) {
    const els = $$(alvo); if (!els.length) return;
    let at = t;
    els.forEach((el, i) => {
      D._pousa(el, at, o);
      at += Math.min(i % 3 ? D.T.item : D.T.item * 1.5, D.T.orcamento / els.length);
    });
    if (o.som) D.cue(t, o.som);
  },
  _pousa(el, t, o) {
    const n = D._vez(), s0 = D.at(t), peso = D.peso(el), rot = o.rot ?? 0;
    const dx = o.dx ?? 0, dy = o.dy ?? -P.QUEDA * EX;
    const dur = D.T.peso[peso] * D.longe(Math.hypot(dx, dy));
    const lado = !o.ease && Math.abs(dx) > Math.abs(dy);
    const cai = !o.ease && !lado && peso === 'leve' && dy < 0 && D._material(el, peso) > 0;
    const tc = cai ? 5 * QD : dur;                 // o instante do contato, a contar de s0
    const dr = o.dr ?? (n % 2 ? 1 : -1) * (2 + .6 * (n % 3)) * EX;   // 2–3,2°: o "subtle" da LottieFiles
    const data = D._ent = 'e' + n;
    D._ents.push({el, a: s0, b: s0 + tc, id: data});
    D.tl.fromTo(el, {opacity: 0}, {opacity: 1, duration: .16, ease: 'none', data}, s0);
    if (lado) {
      D.tl.fromTo(el, {scale: o.s ?? 1.02}, {scale: 1, duration: tc, ease: 'power3.out', data}, s0);
      D.arco(el, s0, [dx, dy], [0, 0], {dur, ease: 'power3.out', lado: Math.sign(dx), data});
    } else {
      D.tl.fromTo(el, {y: dy, scale: o.s ?? 1.02}, {y: 0, scale: 1, duration: tc,
        ease: o.ease || (cai ? 'power2.in' : 'power3.out'), data}, s0);
      D.tl.fromTo(el, {x: dx}, {x: 0, duration: dur, ease: o.ease || 'power2.out', data}, s0);
    }
    D.tl.fromTo(el, {rotation: rot + dr}, {rotation: rot, duration: dur + 3 * QD, ease: 'power3.out', data}, s0);
    D.tl.fromTo(el, {'--shx': '0px'}, {'--shx': D.SH + 'px', duration: tc + 2 * QD, ease: 'sine.inOut', data}, s0);
    if (cai) D.amassa(el, s0 + tc, D._material(el, peso));
    D._ent = null;
  },
  _ents: [],
  lista(alvos, t, passo, o = {}) {
    // o próximo começa com o anterior a 30–50 % (@flxrnc, "fully sequential looks robotic"): 40 %
    $$(alvos).forEach((a, i, todos) => {
      const p = passo ?? Math.min(.4 * D.T.peso[D.peso(a)], D.T.orcamento / todos.length);
      D.pousa(a, t + i * p, {rot: D.inclina(i), ...o});
    });
  },

  /* O carimbo bate (2, 1, 6, 8). Aparece, recua 3 quadros — sobe 15 % do golpe e torce 1,5° pra trás
     (2: LottieFiles, 10–20 % no sentido contrário; a tampa do fone do @flxrnc "presses 1.5 degrees...
     hold 3 frames") —, desce ACELERANDO até o papel (quem bate não freia antes: power3.in, a accelExit
     medida) e achata no impacto (eixo z). O impacto cai 1 quadro antes do cue (@flxrnc: "each hit lands
     1 frame after its picture"). A sombra só existe depois do papel, e chega 2 quadros atrasada (5).
     Carimbo grande (um quarto da largura) faz o palco acusar (8). o.de: a escala de partida (1,15);
     o.desce: o golpe (5 quadros); o.giro: quanto ele torce até assentar (3°). */
  carimbo(alvo, t, rot = P.ROT, o = {}) {
    const els = $$(alvo); if (!els.length) return;
    D.cue(t, 'stamp');
    els.forEach((el, i) => {
      const data = D._ent = 'e' + D._vez();
      const bate = Math.max(0, t + i * D.T.item - QD), desce = Math.min(o.desce ?? 5 * QD, bate);
      const de = o.de ?? 1 + .15 * EX, sobe = 1 + (de - 1) * 1.15;
      const ant = Math.min(3 * QD, bate - desce), a0 = bate - desce - ant, g = o.giro ?? 3;
      D._ents.push({el, a: a0, b: bate, id: data});
      D.tl.fromTo(el, {opacity: 0}, {opacity: 1, duration: 2 * QD, ease: 'none', data}, a0);
      if (ant >= 2 * QD) {
        D.tl.fromTo(el, {scale: de, rotation: rot - g}, {scale: sobe, rotation: rot - g * 1.5, duration: ant, ease: 'power2.out', data}, a0);
        D.tl.to(el, {scale: 1, rotation: rot, duration: desce, ease: 'power3.in', data}, a0 + ant);
      } else D.tl.fromTo(el, {scale: de, rotation: rot - g}, {scale: 1, rotation: rot, duration: Math.max(desce, QD), ease: 'power3.in', data}, a0);
      if (el.classList.contains('nb')) D.tl.fromTo(el, {'--shx': '0px'}, {'--shx': D.SH + 'px', duration: 3 * QD, ease: 'power2.out', data}, bate + 2 * QD);
      D.amassa(el, bate, .05, 'z');
      if (el.offsetWidth > innerWidth * .25) D.reage(bate, el.offsetHeight * .05 * EX);
      D._ent = null;
    });
  },

  /* O herói do painel: um por painel (2, 1, 3, 7, 8). Aparece pequeno, ENCOLHE e segura — 15 % da
     subida no sentido contrário em 4 quadros e 2 parado (LottieFiles: 10–20 %, "hold compressed
     ~50ms"; @flxrnc: 3 quadros de antecipação e a espera) —, e estoura no P.HEROI, a mola que ele
     sempre teve. A altura anda 1 quadro antes da largura: no estouro ele estica no
     sentido do caminho e no assentar as duas se alternam (1, 5). O y anda noutra curva (7). Quem ia
     entrar até 150 ms do estouro espera e entra 150 ms depois (3: @flxrnc, "everything else starts
     150 ms later"); o palco acusa a chegada (8). */
  heroi(alvo, t) {
    const els = $$(alvo); if (!els.length) return D.tl;
    D.cue(t, 'impact');
    els.forEach(el => {
      el.dataset.heroi = '1';
      const data = D._ent = 'e' + D._vez();
      const b = D.at(t), d = D.T.heroi, ant = Math.min(6 * QD, b), a0 = b - ant;
      const s0 = .55, k = .15 * EX, sa = s0 - k * (1 - s0), y0 = 50;
      D._herois.push({el, t: b});
      D.tl.fromTo(el, {opacity: 0}, {opacity: 1, duration: 2 * QD, ease: 'none', data}, a0);
      D.tl.fromTo(el, {scaleX: s0, scaleY: s0, y: y0, rotation: -P.TILT * 3},
        {scaleX: sa, scaleY: sa, y: y0 * (1 + k), duration: Math.max(ant * 2 / 3, .001), ease: 'power2.out', data}, a0);
      D.tl.to(el, {scaleY: 1, duration: d, ease: P.HEROI, data}, b);
      D.tl.to(el, {scaleX: 1, duration: d, ease: P.HEROI, data}, b + QD);
      D.tl.to(el, {y: 0, rotation: 0, duration: d * .8, ease: 'power3.out', data}, b);
      D.reage(b + d / 3.1, y0 * .12 * EX);       // o back.out(2,1) cruza o 1 a 1/3,1 do tempo
      D._ent = null;
    });
    return D.tl;
  },
  _herois: [],

  /* Divide o texto em palavras mascaradas. Anda pelos nós de texto, então <b>,
     <i> e as linhas do D.cabe continuam onde estavam. Rode DEPOIS do cabe:
     o cabe reescreve o innerHTML e jogaria fora estes nós. */
  divide(el) {
    const ws = [];
    const walk = node => [...node.childNodes].forEach(n => {
      if (n.nodeType === 3) {
        if (!n.textContent.trim()) return;
        const fr = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach(s => {
          if (!s) return;
          if (/^\s+$/.test(s)) { fr.appendChild(document.createTextNode(s)); return; }
          const m = document.createElement('span'); m.className = 'mw';
          const w = document.createElement('span'); w.className = 'w'; w.textContent = s;
          m.appendChild(w); fr.appendChild(m); ws.push(w);
        });
        n.replaceWith(fr);
      } else if (n.nodeType === 1 && !n.classList.contains('mw')) walk(n);
    });
    walk(el);
    return ws;
  },
  /* 9, 12. Cadência, não metrônomo (motionmaxxing, type.md: título com intervalos de 4–6 quadros que
     aceleram, 5,5,3,3, e antes da palavra final 1,5–2× o intervalo). O `passo` é a média: as duas
     primeiras 1,25×, as do meio 1×, a pausa antes da última 1,5×. A soma não muda, então o que a peça
     agenda depois do título continua no lugar. Devolve o instante de cada um, a partir de 0. */
  _cadencia(n, passo) {
    const pesos = Array.from({length: Math.max(0, n - 1)}, (_, i) => i === n - 2 && n > 3 ? 1.5 : i < 2 ? 1.25 : 1);
    const k = pesos.length ? passo * pesos.length / pesos.reduce((a, b) => a + b, 0) : 0;
    const ts = [0];
    pesos.forEach(p => ts.push(ts[ts.length - 1] + p * k));
    return ts;
  },
  /* Palavra sobe pela máscara em 13 quadros de power3.out (a softLand medida: palavra 12–15 f, sem
     passar do ponto), girando 5° que somem no caminho (os repos claude-motion e claude-motion-design:
     "translateY 105–118 % com tilt de 5–6°"; Lasseter 2.8). Texto não amassa nem exagera. */
  palavras(alvo, t, passo = D.T.palavra) {
    const el = $(alvo); if (!el || !el.textContent.trim()) return [];
    const ws = D.divide(el), ts = D._cadencia(ws.length, passo);
    gsap.set(el, {opacity: 1});
    // o giro é pela quina de baixo à esquerda: nenhum canto sobe acima do topo, e a palavra longa não
    // aparece pela máscara antes da hora (achado na varredura: ve_tese, ve_ato, ve_conclusao)
    ws.forEach((w, i) => D.tl.fromTo(w, {yPercent: 115, rotation: 5, transformOrigin: '0% 100%'},
      {yPercent: 0, rotation: 0, duration: 13 * QD, ease: 'power3.out'}, D.at(t) + ts[i]));
    return ws;
  },
  marca(alvo, t) {
    const bs = $$(alvo); if (!bs.length) return;
    D.tl.fromTo(bs, {backgroundSize: '0% 88%'}, {backgroundSize: '100% 88%',
      duration: .5, ease: 'power3.inOut', stagger: .12}, t);
  },
  /* a frase do painel: sobe por palavra, e o marcador varre depois da última */
  titulo(alvo, t, passo = D.T.palavra) {
    const el = $(alvo); if (!el || !el.textContent.trim()) return t;
    const ws = D.palavras(el, t, passo);
    const fim = t + ws.length * passo + .1;
    D.marca([...el.querySelectorAll('b')], fim);
    return fim;
  },

  /* Número que sobe. Chame DEPOIS do cabe, com o MAIOR valor já escrito no
     elemento — o cabe mede o que está lá. Aqui ele volta pro valor de partida.
     `expo.out` corre no começo e freia no fim: a conta acontece, o número
     assenta, e o soco de escala marca a chegada. */
  conta(alvo, de, para, t, dur = P.ENT * 1.9, fmt = D.brl) {
    const el = $(alvo), o = {v: de};
    const w = n => { el.textContent = fmt(n); };
    w(de);
    D.cue(t, 'tick-roll', {dur: +dur.toFixed(3)});
    if (!el.__c0) { el.__c0 = 1; D.tl.call(() => w(de), null, 0); }
    const tw = D.tl.to(o, {v: para, duration: dur, ease: 'expo.out',
      onUpdate: () => w(o.v)}, D.at(t));
    // 2, 10. A chegada: encolhe 3 % por 2 quadros (LottieFiles, "scale down 3% before expanding") e
    // estoura a 1,08 voltando a 1 em 4 (o "pop" do @flxrnc: 1,0 → 1,08 → 1,0 em 6 quadros)
    const s = D.at(t) + .06;
    D.tl.to(el, {scale: .97, duration: 2 * QD, ease: 'power2.out'}, s);
    D.tl.to(el, {scale: 1.08, duration: 2 * QD, ease: 'power2.out'}, s + 2 * QD);
    D.tl.to(el, {scale: 1, duration: 4 * QD, ease: 'power2.inOut'}, s + 4 * QD);
    return tw;
  },

  /* Soco de câmera (motionmaxxing, motion.md §6): no quadro t a escala vale `de`, no seguinte já andou
     60 %, e o resto é uma cauda que freia (power3.out, .45 s; medidos 0,3–0,6 s). O recuo que revela
     "estava dentro de um produto". Num contêiner da peça (o #mundo), não no #stage do D.camera: dois
     tweens de escala no mesmo alvo brigam. */
  soco(alvo, t, de = 2.5, para = 1, o = {}) {
    const el = $(alvo); if (!el) return;
    // fromTo desenha `de` já no quadro 0 (immediateRender): serve ao soco que abre a peça. Um soco no meio
    // dela (o pouso do k_objeto) ia aparecer dado desde o começo e recuar no instante t; aí vai set + to,
    // que não desenham nada antes de t e voltam ao natural na busca pra trás.
    const parte = de + (para - de) * (o.parte ?? .6);
    if (t <= QD) D.tl.fromTo(el, {scale: de}, {scale: parte, duration: QD, ease: 'none'}, t);
    else { D.tl.set(el, {scale: de}, t); D.tl.to(el, {scale: parte, duration: QD, ease: 'none'}, t); }
    D.tl.to(el, {scale: para, duration: o.cauda ?? .45, ease: 'power3.out'}, t + QD);
  },

  /* o painel inteiro respira: aproximação lenta, um movimento só. O will-change faz o
     Chromium ampliar a camada em vez de redesenhar a letra a cada escala, que andava em
     degrau (5 quadros parados em 89); a letra perde ~8 % de nitidez no fim, invisível até 5 %. */
  camera(dur, de = 1.0, para = 1.035) {
    gsap.set('#stage', {willChange: 'transform'});
    return D.tl.fromTo('#stage', {scale: de, rotation: -P.TILT * .25},
      {scale: para, rotation: P.TILT * .25, duration: dur, ease: 'none'}, 0);
  },

  /* ── 3D. A peça que gira ganha a lente, o corpo, a luz e a sombra daqui, não de si mesma.
     Medido em 04/10 contra os anúncios que escalam (tools/v2/3D-REFERENCIA.md): o que faz o 3D
     deles ler como objeto é a espessura que aparece no giro, a face que muda de luz e a câmera
     que não para; a nossa pilha era papel sem lado, com a mesma luz em qualquer ângulo, parada.
       D.palco3d(el)          a lente (--persp) e o ponto de fuga
       D.espessura(alvos, o)  os quatro lados (a borda vira espessura), as costas (o.costas) e a
                              sombra dura, que no 3D é uma placa atrás da face, deslocada pela
                              luz, sem blur; ela pousa junto com o --shx do D.pousa
       D.luz(alvos)           cada face escurece ou clareia INTEIRA conforme vira pra luz (P.LUZ),
                              a cada quadro buscado: chapada, sem degradê nem brilho difuso
       D.deriva(alvo, t0, t1, para)  a câmera não para no tempo em que a peça só fica: um giro
                              lento até `para`, que começa e termina parado */
  palco3d(el = '#stage', origem = '50% 50%') {
    const e = $(el);
    e.style.perspective = 'var(--persp)';
    e.style.perspectiveOrigin = origem;
    D._palco3d = e;
    return e;
  },
  espessura(alvos, o = {}) {
    $$(alvos).forEach(el => {
      const esp = o.esp ?? (parseFloat(css('--esp')) || 14);
      el.classList.add('d3');
      const face = (cls, st) => {
        const f = document.createElement('i');
        f.className = 'd3-face ' + cls; Object.assign(f.style, st); el.appendChild(f); return f;
      };
      // cada lado gira 90° na própria borda e vai pra trás: a normal aponta pra fora
      const lados = [
        face('', {top: 0, left: '100%', width: esp + 'px', height: '100%', transformOrigin: '0 50%', transform: 'rotateY(90deg)'}),
        face('', {top: 0, right: '100%', width: esp + 'px', height: '100%', transformOrigin: '100% 50%', transform: 'rotateY(-90deg)'}),
        face('', {left: 0, bottom: '100%', width: '100%', height: esp + 'px', transformOrigin: '50% 100%', transform: 'rotateX(90deg)'}),
        face('', {left: 0, top: '100%', width: '100%', height: esp + 'px', transformOrigin: '50% 0', transform: 'rotateX(-90deg)'}),
      ];
      if (o.costas) {
        el.style.backfaceVisibility = 'hidden';
        lados.push(face('', {inset: 0, borderRadius: 'inherit', transform: `translateZ(${-esp}px) rotateY(180deg)`,
          ...(typeof o.costas === 'string' ? {background: o.costas} : {})}));
      }
      if (o.sombra !== false) {
        // a sombra plana do .nb vira a placa: some do box-shadow e reaparece atrás do lado
        el.style.boxShadow = 'none';
        el.style.setProperty('--fundo3d', -(esp + 2) + 'px');
        face('d3-sombra', {});
      }
      D.luz([el, ...lados]);
    });
  },
  luz(alvos) {
    const novas = $$(alvos).map(el => {
      const l = document.createElement('i'); l.className = 'd3-luz'; el.appendChild(l);
      return {el, l};
    });
    if (!D._faces) { D._faces = []; D.aoQuadro(D._acende); }
    D._faces.push(...novas);
  },
  _acende() {
    const [lx, ly, lz] = P.LUZ, ln = Math.hypot(lx, ly, lz);
    const frente = lz / ln;
    D._faces.forEach(({el, l}) => {
      // a direção da face no mundo: só a parte linear das transformadas, de dentro pra fora até a lente
      let m = new DOMMatrix();
      for (let e = el; e && e !== D._palco3d && e !== document.body; e = e.parentElement) {
        const t = getComputedStyle(e).transform;
        if (t && t !== 'none') m = new DOMMatrix(t).multiply(m);
      }
      const n = m.transformPoint(new DOMPoint(0, 0, 1, 0)), nn = Math.hypot(n.x, n.y, n.z) || 1;
      const d = (n.x * lx + n.y * ly + n.z * lz) / ln / nn - frente;   // 0: de frente, como no plano
      l.classList.toggle('clara', d > 0);
      l.style.opacity = d > 0 ? Math.min(P.CLARO, d * P.CLARO * 2) : Math.min(P.ESCURO, -d * P.ESCURO * 1.4);
    });
  },
  deriva(alvo, t0, t1, para = {rotationY: 6, rotationX: -2}) {
    if (t1 - t0 < .3) return;
    D.tl.to(alvo, {...para, duration: t1 - t0, ease: 'sine.inOut'}, t0);
  },
  /* roda a cada quadro buscado, depois que a timeline assentou tudo (a luz do 3D) */
  aoQuadro(fn) { (D._quadro = D._quadro || []).push(fn); },

  /* 11. Desenho sólido. Não está no artigo de Lasseter (a lista dele tem 11; o 12º é de Thomas e
     Johnston). Em UI 2D vira coerência de volume, luz e sombra (LottieFiles: "shadow behavior matches
     implied light source"): a sombra dura é da luz, que vem de cima e da esquerda (P.LUZ), não da peça.
     A peça girada não leva a sombra junto: a cada quadro o deslocamento é girado de volta. Todo .nb
     entra sozinho (o tamanho é o --shx que o D.pousa anima); sombra própria da peça, D.solido(el, px)
     com o box-shadow lendo var(--sx) e var(--sy). */
  solido(alvo, px) { $$(alvo).forEach(el => { el.__sh = px; D._solidos.add(el); }); },
  _solidos: new Set(),
  _sombras() {
    D._solidos.forEach(el => {
      const th = (gsap.getProperty(el, 'rotation') || 0) * Math.PI / 180;
      if (Math.abs(th) < .004) { el.style.removeProperty('--sx'); el.style.removeProperty('--sy'); return; }
      const v = getComputedStyle(el).getPropertyValue('--shx').trim();
      const m = v ? parseFloat(v) : el.__sh ?? D.SH, c = Math.cos(th), s = Math.sin(th);
      el.style.setProperty('--sx', (m * (c + s)).toFixed(2) + 'px');
      el.style.setProperty('--sy', (m * (c - s)).toFixed(2) + 'px');
    });
  },

  /* Micro-movimento contínuo. yPercent, não y: y é da entrada e da saída, e
     dois tweens na mesma propriedade brigam. Termina onde começou. */
  flutua(alvos, t0, t1, amp = 2, fase = 0) {
    $$(alvos).forEach((el, i) => {
      const k = i + fase, per = 2.2 + (k % 3) * .35;
      const n = Math.floor((t1 - t0 - i * .15) / per);
      if (n < 1) return;
      D.tl.to(el, {yPercent: k % 2 ? -amp : amp, duration: per / 2, ease: 'sine.inOut',
        yoyo: true, repeat: n * 2 - 1}, t0 + i * .15);
    });
  },
  respira(alvo, t0, t1, s = 1.025) {
    const per = 1.8, n = Math.floor((t1 - t0) / per);
    if (n < 1) return;
    D.tl.to(alvo, {scale: s, duration: per / 2, ease: 'sine.inOut', yoyo: true, repeat: n * 2 - 1}, t0);
  },

  /* Um foco que ANDA: nasce no primeiro item e desliza até cada um no instante
     em que é dito. Fica atrás do item, deslocado — lê como a sombra dele virando
     marcador. Mede offset, que ignora transform: pode medir com a peça no ar. */
  /* Ao andar (2, 1, 5, 6): recua 3 quadros 12 % no sentido contrário (LottieFiles: 10–20 %), e a borda
     da frente sai 2 quadros antes da de trás (LottieFiles: filho 50–150 ms atrás do pai): o foco estica
     na viagem e encolhe ao chegar, sem passar do ponto. Curva de mover na tela, ease-in-out (@flxrnc:
     "move across the screen with ease-in-out"); a duração cresce com a distância. As quatro bordas
     moram num objeto e viram left/top/width/height a cada quadro buscado. */
  desliza(barra, alvos, tempos, o = {}) {
    const b = $(barra), els = $$(alvos); if (!b || !els.length) return;
    const off = o.off ?? D.SH * 1.9, atraso = o.atraso ?? .14;
    const caixa = el => ({l: el.offsetLeft + off, t: el.offsetTop + off,
      r: el.offsetLeft + off + el.offsetWidth, b: el.offsetTop + off + el.offsetHeight});
    const p = caixa(els[0]);
    const poe = () => gsap.set(b, {left: p.l, top: p.t, width: p.r - p.l, height: p.b - p.t});
    poe(); D.aoQuadro(poe);
    els.forEach((el, i) => {
      const t = D.at(tempos[i]) + atraso;
      if (i === 0) {
        D.tl.fromTo(b, {opacity: 0, scaleX: .15, transformOrigin: 'left center'},
          {opacity: 1, scaleX: 1, duration: .45, ease: P.EASE}, t);
        return;
      }
      const de = caixa(els[i - 1]), para = caixa(el);
      const vert = Math.abs(para.t - de.t) >= Math.abs(para.l - de.l);
      const passo = vert ? para.t - de.t : para.l - de.l;
      const frente = vert ? (passo > 0 ? 'b' : 't') : (passo > 0 ? 'r' : 'l');
      const tras = {t: 'b', b: 't', l: 'r', r: 'l'}[frente], ida = t + 3 * QD;
      // cabe antes da próxima: dois tweens da mesma borda não podem se cruzar
      const prox = i + 1 < els.length ? D.at(tempos[i + 1]) + atraso : Infinity;
      const dur = Math.max(4 * QD, Math.min(D.T.peso.medio * D.longe(Math.abs(passo)), prox - ida - 2 * QD - .01));
      const recua = {};
      ['l', 't', 'r', 'b'].forEach(k => { recua[k] = de[k] - ((k === 't' || k === 'b') === vert ? passo * .12 : 0); });
      D.tl.to(p, {...recua, duration: 3 * QD, ease: 'power2.out'}, t);
      ['l', 't', 'r', 'b'].forEach(k => D.tl.to(p, {[k]: para[k], duration: dur, ease: 'power3.inOut'}, k === tras ? ida + 2 * QD : ida));
      D.cue(ida, 'swish');
    });
  },

  /* Saída dentro da peça: levanta, perde a sombra e some, em cascata curta. */
  sai(alvos, t) {
    if (D.q('sai', '1') === '0') return;
    const el = $$(alvos); if (!el.length) return;
    (D._saidas = D._saidas || []).push({el, t});
  },

  /* Digita um texto letra a letra. Cada letra é um span que aparece por
     `display` — seekável, e o cursor anda junto sem medir nada. */
  /* 9, 12. No ritmo de mão, não de metrônomo (motionmaxxing, type.md: rajadas, pausa depois do espaço e
     da pontuação, a última palavra mais lenta). `passo` continua sendo a média e a soma não muda: o fim
     e o cue de som ficam onde estavam. A mesma frase digita sempre igual. */
  digita(alvo, t, passo = .07) {
    const el = $(alvo); if (!el) return 0;
    const tx = el.textContent; el.textContent = '';
    const ls = [...tx].map(ch => { const s = document.createElement('span'); s.className = 'l'; s.textContent = ch; s.style.display = 'none'; el.appendChild(s); return s; });
    const fimPal = tx.trimEnd().lastIndexOf(' ');
    const pesos = [...tx].map((ch, i) => i === 0 ? 0 : (/[.,!?;:…]/.test(tx[i - 1]) ? 3 : tx[i - 1] === ' ' ? 2 : i % 3 === 2 ? .5 : 1) * (fimPal >= 0 && i > fimPal ? 1.3 : 1));
    const soma = pesos.reduce((a, b) => a + b, 0), k = soma ? passo * (ls.length - 1) / soma : 0;
    let at = t;
    ls.forEach((s, i) => { at += pesos[i] * k; D.tl.set(s, {display: 'inline-block'}, at); });
    D.cue(t, 'type', {dur: +(ls.length * passo).toFixed(3)});
    return t + ls.length * passo;
  },
  /* anel que pulsa a partir de um ponto, em loop até t1 */
  pulsa(alvo, t0, t1, per = 1.1) {
    const el = $$(alvo);
    el.forEach((a, k) => {
      for (let t = t0 + k * per / el.length; t < t1 - .3; t += per) {
        D.tl.fromTo(a, {scale: .6, opacity: .95}, {scale: 1.7, opacity: 0, duration: Math.min(per * .9, t1 - t), ease: 'power2.out', immediateRender: false}, t);   // o último anel termina no t1, não depois do fim da peça
      }
    });
  },

  /* Captura real dentro da peça: ?img=url. Imagem, ou vídeo se terminar em
     .mp4/.mov/.webm (o quadro do vídeo segue a timeline; num render busca por
     busca, vídeo pode atrasar um quadro — prefira imagem, ou componha o vídeo
     por baixo). Sem url, o marcador listrado diz o que vai ali. */
  midia(caixa, url, rotulo = 'captura', ajuste = 'cover') {
    const c = $(caixa); if (!c) return null;
    if (!url) {
      c.insertAdjacentHTML('beforeend', `<div class="vazio"><span>${rotulo}</span></div>`);
      return null;
    }
    const ehVideo = /\.(mp4|mov|webm)(\?|$)/i.test(url);
    const m = document.createElement(ehVideo ? 'video' : 'img');
    m.src = url; m.className = 'mid'; m.style.objectFit = ajuste;
    if (ehVideo) { m.muted = true; m.playsInline = true; m.preload = 'auto'; D._videos.push(m); }
    c.appendChild(m);
    return m;
  },
  _videos: [],

  /* Encolhe a fonte até CADA linha caber sem quebrar — o mesmo da v1, agora
     síncrono porque roda dentro do D.monta, com a fonte já carregada.
     `alvo`: 1 (palco) · 0.4 (fração do palco) · '.fx' (ancestral) · ['.item', .36] */
  cabe(sel, minimo = 24, alvo = 1) {
    const medir = el => {
      const cx = getComputedStyle(el);
      return el.clientWidth - parseFloat(cx.paddingLeft) - parseFloat(cx.paddingRight);
    };
    const palco = medir(document.getElementById('stage'));
    document.querySelectorAll(sel).forEach(el => {
      if (!el.textContent.trim()) return;
      const [quem, fr] = Array.isArray(alvo) ? alvo : [alvo, 1];
      const caixa = typeof quem === 'string' ? el.closest(quem) : null;
      const limite = (caixa ? medir(caixa) : palco * quem) * fr;
      el.innerHTML = el.innerHTML.split(/<br\s*\/?>/i)
        .map(l => `<span style="display:block;white-space:nowrap">${l}</span>`).join('');
      const linhas = [...el.children];
      let px = parseFloat(getComputedStyle(el).fontSize);
      // mede a linha E a própria caixa: um filho maior que a coluna também vaza
      const vaza = () => linhas.some(l => l.scrollWidth > limite) || (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1);
      while (px > minimo && vaza()) {
        px -= 2;
        el.style.fontSize = px + 'px';
      }
    });
  },

  /* Espera a fonte de verdade (a do display desta direção e a mono), roda a
     montagem e só então publica __tl/__duration/__ready. `fn` devolve a
     duração; sem número, vale tl.duration(). */
  /* ?boneco=1 — a biblioteca do aluno: a peça que vai por cima do vídeo toca sobre uma pessoa de
     mentira, e ela faz o que o compositor faria com o take (ensaio.js): desliza até o __pessoa,
     entra no cartão, aproxima no zoom. ponytail: pb, congela, dessatura e desfoca não mudam nada
     num boneco cinza, e ficam de fora. */
  boneco(tl, dur) {
    const st = $('#stage') || document.body, W = st.offsetWidth, H = st.offsetHeight;
    const b = document.createElement('div');
    b.id = 'boneco'; b.className = H > W ? 'v' : '';
    b.innerHTML = '<div><div><div></div></div></div>';   // cartão > desliza > aproxima
    st.style.isolation = 'isolate'; st.prepend(b);
    // o cartão do take fica entre as camadas da peça: por cima do que é de trás, por baixo do que é da frente
    $$('[data-c=frente]').forEach(e => { e.style.zIndex = 2; });
    const [ca, de, pe] = b.querySelectorAll('div'), p = window.__pessoa, dx = p ? p.x + p.w / 2 - W / 2 : 0;
    if (dx) tl.fromTo(de, {x: 0}, {x: dx, duration: .6, ease: 'power3.inOut'}, 0)
      .to(de, {x: 0, duration: .6, ease: 'power3.inOut'}, Math.max(.6, dur - .6));
    (window.__video || []).forEach(v => {
      if (v.efeito === 'zoom') tl.fromTo(pe, {scale: v.de ?? 1}, {scale: v.para ?? 1.15, duration: v.entra ?? .5,
        ease: v.curva === 'reta' ? 'none' : 'power3.out', immediateRender: false}, v.t0).set(pe, {scale: 1}, v.t1);
      // o boneco inteiro, deitado, dentro do cartão: no reel de verdade o rosto é posto no cartão;
      // o recorte pelo `topo` mostraria só o ombro de um boneco centrado
      if (v.efeito === 'cartao') tl.set(b, {zIndex: 1, attr: {class: ''}, clipPath: `inset(${v.y}px ${W - v.x - v.w}px ${H - v.y - v.h}px ${v.x}px round ${v.raio || 0}px)`}, v.t0)
        .set(ca, {x: v.x, y: v.y, width: v.w, height: v.h}, v.t0)
        .set(b, {zIndex: -1, attr: {class: b.className}, clipPath: 'none'}, v.t1).set(ca, {x: 0, y: 0, width: W, height: H}, v.t1);
    });
  },
  monta(fn) {
    const fam = css('--fd').split(',')[0];
    const cargas = ['900 100px ', '800 100px ', '600 60px '].map(w => w + fam)
      .concat(['700 40px "IBM Plex Mono"', '600 40px "IBM Plex Mono"']);
    Promise.all([window.__folha, window.__tema])
      .then(() => Promise.all(cargas.map(f => document.fonts.load(f).catch(() => null))))
      .then(() => document.fonts.ready)
      // imagem de captura precisa estar decodificada: a peça mede a proporção dela
      // Já carregada basta (naturalWidth existe); decode() sem prazo pode nunca
      // voltar com a página em segundo plano e travava o __ready (achado na varredura).
      .then(() => Promise.all([...document.images].map(i => i.complete && i.naturalWidth ? null
        : Promise.race([i.decode ? i.decode().catch(() => null) : null, new Promise(r => { i.addEventListener('load', r, {once: true}); i.addEventListener('error', r, {once: true}); setTimeout(r, 6000); })]))))
      .then(() => Promise.all(D._videos.map(v => v.readyState >= 2 ? null : new Promise(r => { v.addEventListener('loadeddata', r, {once: true}); v.addEventListener('error', r, {once: true}); setTimeout(r, 8000); }))))
      .then(() => {
        // Buscar o vídeo no instante exato do quadro cai no quadro ANTERIOR (1 em 3 repetia: o PIP dele ficava
        // travado, "em câmera lenta"). 1/120 s pra dentro do quadro acerta (medido: 60 de 60 quadros distintos).
        const MEIO_QUADRO = 1 / 120;
        const tl = D.tl = gsap.timeline({paused: true});
        if (D._videos.length) D.aoQuadro(() => D._videos.forEach(v => { v.currentTime = Math.max(0, tl.time() + (parseFloat(v.dataset.off) || 0) + MEIO_QUADRO); }));
        const d0 = fn(tl);
        $$('.nb').forEach(el => { if (!el.classList.contains('d3')) D._solidos.add(el); });
        if (D._solidos.size) D.aoQuadro(D._sombras);
        // 3. Encenação: uma ideia por vez (Lasseter 2.4: "only one idea be seen by the audience at a
        // time"). Quem ia entrar até 150 ms do estouro de um herói espera e entra 150 ms depois dele
        // (@flxrnc: "everything else starts 150 ms later"); os tweens daquela entrada andam juntos.
        const adia = (e, d) => {
          tl.getChildren(true, true, false).forEach(tw => { if (tw.data === e.id) tw.startTime(tw.startTime() + d); });
          e.a += d; e.b += d;
        };
        D._herois.forEach(h => D._ents.forEach(e => {
          if (e.el === h.el || h.el.contains(e.el) || e.el.contains(h.el) || Math.abs(e.a - h.t) >= .15) return;
          adia(e, h.t + .15 - e.a);
        }));
        // 5. Três ou mais entrando no mesmo quadro, mesmo em chamadas separadas, viram cascata de 2–3
        // quadros, dentro do orçamento (@flxrnc: "all at once looks cheap"; motionmaxxing: irmãos a
        // 1–3 quadros, irregulares)
        const quadros = new Map();
        D._ents.forEach(e => { const q = Math.round(e.a * 30); quadros.set(q, [...(quadros.get(q) || []), e]); });
        quadros.forEach(es => {
          if (es.length < 3) return;
          let soma = 0;
          es.forEach((e, i) => { if (!i) return; soma += i % 3 ? D.T.item : D.T.item * 1.5; adia(e, Math.min(soma, D.T.orcamento)); });
        });
        const quadro = () => (D._quadro || []).forEach(f => f());
        if (D._quadro) tl.eventCallback('onUpdate', quadro);
        const dur = typeof d0 === 'number' && d0 > 0 ? d0 : tl.duration();
        /* Saídas agendadas DEPOIS de saber a duração, pra caberem nela. Antes a
           cascata (.34 s + até .28 s de stagger) passava até .17 s do fim: o render
           cortava a peça no meio da saída e o último quadro ficava com meio
           elemento na tela. Agora a cascata e o tempo de cada um encolhem até
           caber na janela que sobra. Achado pela varredura (nucleo/qa.js). */
        /* A saída de bloco dura o que a entrada durou e acelera (P.SAI, a accelExit medida: 12 f de
           entrada contra 13–14 de saída no motionmaxxing), depois de 2 quadros de recolher, a
           antecipação da partida (LottieFiles: "Departure: gather (scale 98%) → exit"). Cada uma
           sai girando pro seu lado (7, 12). */
        (D._saidas || []).forEach(({el, t}) => {
          const t0 = Math.max(0, Math.min(t, dur - .2)), jan = Math.max(.2, Math.min(.45, dur - t0 - .01));
          const cascata = Math.min(.28, .05 * (el.length - 1), jan * .4);
          const junta = jan - cascata >= .25 ? 2 * QD : 0;
          D.cue(t0, 'whoosh-out');
          if (junta) tl.to(el, {scale: .98, y: '+=3', duration: junta, ease: 'power2.out', stagger: {amount: cascata}}, t0);
          tl.to(el, {opacity: 0, y: -P.QUEDA * .7, scale: .94, '--shx': '0px', rotation: i => (i % 2 ? 1.5 : -2) * EX,
            duration: Math.min(D.T.peso[D.peso(el[0])], jan - cascata - junta), ease: P.SAI, stagger: {amount: cascata}}, t0 + junta);
        });
        if (Q.get('boneco') === '1') D.boneco(tl, dur);
        tl.to({}, {duration: .001}, Math.max(0, dur - .001));
        tl.time(0);
        quadro();
        window.__duration = dur;
        window.__cues = window.__cues.filter(c => c.t <= dur).sort((a, b) => a.t - b.t);
        window.__tl = tl;
        window.__ready = true;
        // ?repete=1 (com vivo) — a biblioteca do aluno: toca em laço, parada um instante no fim
        if (D.vivo) (Q.get('repete') === '1' ? tl.repeat(-1).repeatDelay(.6) : tl).play();
      });
  },
};
})();
