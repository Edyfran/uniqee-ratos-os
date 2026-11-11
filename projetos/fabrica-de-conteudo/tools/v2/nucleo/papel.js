/* O papel das peças de anúncio em pé: o branco pontilhado com as três luzes (o amarelo do marcador no alto à
   direita, o azul embaixo à esquerda, outro amarelo no alto à esquerda) e, se a peça quiser, a grade fina atrás
   do que se monta. Estava copiado em quatro peças (k_objeto, k_pedido, k_edita, k_fecho); daqui pra frente a
   peça nova chama isto, e quem for mexer nas outras troca a cópia por esta chamada.

     Papel.monta(svg, W, H, o)   o.grade = [y, altura] liga a grade mascarada · o.luz = {a:[cx,cy], b:[cx,cy], c:[cx,cy]}
     Papel.anda(tl, dur, o)      as luzes andam devagar, do começo ao fim da peça (o.a, o.c: pra onde vão)

   Cor e padrão são do núcleo (var(--pp), var(--mk), var(--ac), var(--ink)): nada aqui redeclara cor. */
(function () {
const $ = s => typeof s === 'string' ? document.querySelector(s) : s;
window.Papel = {
  monta(svg, W, H, o = {}) {
    const el = $(svg), L = {a: [860, 520], b: [120, 1180], c: [170, 280], ...(o.luz || {})};
    const escala = H / 1920;                      // a luz acompanha o quadro (o 4:5 é mais baixo)
    const gr = o.grade ? `<defs>
      <pattern id="gr" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0H0V60" fill="none" style="stroke:var(--ink)" stroke-opacity=".2" stroke-width="1.6"/></pattern>
      <radialGradient id="gm" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff"/><stop offset=".6" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
      <mask id="gk"><rect x="-40" y="${o.grade[0]}" width="${W + 80}" height="${o.grade[1]}" fill="url(#gm)"/></mask></defs>
      <rect x="-40" y="${o.grade[0]}" width="${W + 80}" height="${o.grade[1]}" fill="url(#gr)" mask="url(#gk)"/>` : '';
    el.setAttribute('width', W); el.setAttribute('height', H);
    el.innerHTML = `<defs>
      <pattern id="pt" width="36" height="36" patternUnits="userSpaceOnUse"><circle cx="18" cy="18" r="2.2" fill="rgba(11,13,18,.07)"/></pattern>
      <radialGradient id="la"><stop offset="0" style="stop-color:var(--mk);stop-opacity:.42"/><stop offset=".55" style="stop-color:var(--mk);stop-opacity:.14"/><stop offset="1" style="stop-color:var(--mk);stop-opacity:0"/></radialGradient>
      <radialGradient id="lb2"><stop offset="0" style="stop-color:var(--ac);stop-opacity:.16"/><stop offset="1" style="stop-color:var(--ac);stop-opacity:0"/></radialGradient>
      <radialGradient id="lc"><stop offset="0" style="stop-color:var(--mk);stop-opacity:.30"/><stop offset="1" style="stop-color:var(--mk);stop-opacity:0"/></radialGradient></defs>
      <rect width="${W}" height="${H}" style="fill:var(--pp)"/>
      <circle id="luz-a" cx="${L.a[0]}" cy="${L.a[1] * escala}" r="${760 * escala + 120}" fill="url(#la)"/>
      <circle id="luz-b" cx="${L.b[0]}" cy="${L.b[1] * escala}" r="${640 * escala + 100}" fill="url(#lb2)"/>
      <circle id="luz-c" cx="${L.c[0]}" cy="${L.c[1] * escala}" r="${520 * escala + 80}" fill="url(#lc)"/>
      <rect width="${W}" height="${H}" fill="url(#pt)"/>${gr}`;
    window.__escalaLuz = escala;
  },
  anda(tl, dur, o = {}) {
    const e = window.__escalaLuz || 1, a = o.a || [780, 610], c = o.c || [230, 360];
    tl.to('#luz-a', {attr: {cx: a[0], cy: a[1] * e}, duration: dur, ease: 'sine.inOut'}, 0);
    tl.to('#luz-c', {attr: {cx: c[0], cy: c[1] * e}, duration: dur, ease: 'sine.inOut'}, 0);
  },
};
})();
