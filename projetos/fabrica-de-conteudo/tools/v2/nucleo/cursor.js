/* O cursor desenhado: a seta de quem está usando, nas peças em pé. O h_cursor é outra coisa, o
   halo amarelo por cima do cursor que já está na gravação deitada; aqui não há gravação, então a
   seta é o objeto, com a borda tinta e a sombra dura de todas as peças.

   Carregue DEPOIS do direcao-v2.js e chame dentro do D.monta (usa D.tl):

     D.cursor(pai, pts, o)   pts  [{x, y, t, clica}] em px do palco, no instante em que a ponta
                                  da seta ESTÁ lá (o mesmo `t` do resto do núcleo)
                             clica: a seta afunda, o anel amarelo sai da ponta e o cue `mouse` toca
                             alvo: (com clica) o que foi clicado afunda 1 quadro depois da seta
                             o.tam (84 px de altura) · o.sai (o instante em que some; sem: fica)
                             o.anel (false tira o anel) · devolve o elemento da seta

   Da referência (Skillry #199, #212): o cursor dirige cada troca de estado. A viagem freia antes
   de chegar, sem passar do ponto; quem pede a mola é a peça, não a seta.
   Os números (12/10/2026) são os medidos do motionmaxxing (references/ui-demo.md §2–3, reescritos
   aqui; pesquisa/motionmaxxing/ESTUDO.md): a seta entra grande, 1,5–2,2×, e encolhe pela ponta;
   anda em arco (D.arco, 7), com a barriga embaixo; para 2 quadros no alvo antes de apertar; aperta em
   2 quadros e volta em 3; o alvo afunda 0–1 quadro depois (ação secundária, 8). */
(function () {
const D = window.D;
const est = document.createElement('style');
est.textContent = `
.cur{position:absolute;left:0;top:0;transform-origin:0 0;opacity:0;pointer-events:none;z-index:50;
  filter:drop-shadow(calc(var(--sh)*.6) calc(var(--sh)*.6) 0 var(--sombra,var(--ink)))}
.cur svg{display:block;overflow:visible}
.cur path{fill:var(--sur);stroke:var(--ink);stroke-width:2.4;stroke-linejoin:round}
.cur-anel{position:absolute;left:0;top:0;border-radius:50%;opacity:0;pointer-events:none;z-index:49;
  border:6px solid var(--mk);box-shadow:0 0 0 3px var(--ink),inset 0 0 0 3px var(--ink)}`;
document.head.appendChild(est);

D.cursor = function (pai, pts, o = {}) {
  const tl = D.tl, p0 = D.$(pai), tam = o.tam || 84;
  if (!p0 || !pts.length) return null;
  const c = document.createElement('div');
  c.className = 'cur';
  // a seta clássica, ponta em (0,0): é a ponta que vai ao ponto, não o centro da caixa
  c.innerHTML = `<svg width="${tam * .7}" height="${tam}" viewBox="0 0 21 30"><path d="M1 1 L1 24.5 L6.6 19.4 L10.4 28 L14.6 26.2 L10.9 17.8 L18.6 17.8 Z"/></svg>`;
  p0.appendChild(c);
  const QD = D.QD;
  gsap.set(c, {x: pts[0].x, y: pts[0].y});
  tl.fromTo(c, {opacity: 0, scale: 1.8}, {opacity: 1, scale: 1, duration: .3, ease: 'power3.out'}, Math.max(0, pts[0].t - .3));
  pts.forEach((p, i) => {
    if (i > 0) {
      const q = pts[i - 1], para = p.t - (p.clica ? 2 * QD : 0);   // estaciona 2 quadros antes do clique
      const d = Math.max(.22, Math.min(.6, para - q.t - .06));
      const L = Math.hypot(p.x - q.x, p.y - q.y);
      D.arco(c, para - d, [q.x, q.y], [p.x, p.y], {dur: d, flecha: Math.min(120, Math.max(10, L * .15)), lado: Math.sign(p.x - q.x) || 1});
    }
    if (!p.clica) return;
    if (o.anel !== false) {
      const a = document.createElement('div'), r = tam * .55;
      a.className = 'cur-anel';
      Object.assign(a.style, {width: 2 * r + 'px', height: 2 * r + 'px', marginLeft: -r + 'px', marginTop: -r + 'px'});
      p0.appendChild(a);
      gsap.set(a, {x: p.x, y: p.y});
      tl.fromTo(a, {opacity: 1, scale: .35}, {opacity: 0, scale: 1.6, duration: .5, ease: 'power2.out', immediateRender: false}, p.t);
    }
    tl.to(c, {scale: .74, duration: 2 * QD, ease: 'power2.out'}, p.t);
    tl.to(c, {scale: 1, duration: 3 * QD, ease: 'power2.out'}, p.t + 2 * QD);
    if (p.alvo && D.$(p.alvo)) {
      tl.to(p.alvo, {scale: .86, duration: 2 * QD, ease: 'power2.out'}, p.t + QD);
      tl.to(p.alvo, {scale: 1, duration: 3 * QD, ease: 'power2.out'}, p.t + 3 * QD);
    }
    D.cue(p.t, 'mouse');
  });
  if (o.sai != null) tl.to(c, {opacity: 0, scale: .7, duration: .2, ease: 'power2.in'}, o.sai);
  return c;
};
})();
