/* O TECLADO — o objeto que enche o terço de baixo quando a cena é de escrever (o pedido, o .zip que vai pro agente, o fecho).
   Papel, borda tinta e sombra dura, inclinado a -5° e sangrando pela borda de baixo; as teclas de vogal em azul. Aperta a tecla
   de cada letra que a peça escreve (a tecla desce na própria sombra e pisca o amarelo). Não é imagem: são ~30 caixas de CSS,
   então não ocupa o teto de objetos gerados e herda o papel, a tinta e o azul do núcleo.
     Teclado.monta(top = 1470)   cria o #teclado em #mundo (o y do alto dele; passa de 1920 e é cortado)
     Teclado.entra(tl, t)        sobe do pé do quadro e assenta (cue swish)
     Teclado.parado()            já está lá desde o quadro 0 (a cena que continua a anterior)
     Teclado.aperta(tl, letra, t)  a tecla da letra (ou a barra de espaço) desce em `t` e volta
   Precisa do gsap e do direcao-v2.js (D) já carregados; as peças incluem este arquivo logo depois do direcao-v2.js. */
(() => {
  const st = document.createElement('style');
  st.textContent = `#teclado{position:absolute;left:-70px;top:1470px;width:1230px;height:640px;z-index:2;transform-origin:50% 0;transform:rotate(-5deg);opacity:0}
.tk{position:absolute;width:98px;height:100px;background:var(--pp);border:5px solid var(--ink);border-radius:20px;box-shadow:8px 8px 0 var(--ink);
  font:700 40px/90px var(--fm);text-align:center;color:var(--ink)}
.tk i{position:absolute;inset:0;border-radius:15px;background:var(--mk);opacity:0}
.tk b{position:relative;font-weight:700}
.tk.ac{background:var(--ac);color:#fff}`;
  document.head.appendChild(st);
  const FILAS = [['QWERTYUIOP', 24, 0], ['ASDFGHJKL', 80, 112], ['ZXCVBNM', 136, 224]];
  const sem = c => c.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
  window.Teclado = {
    teclas: {},
    monta(top = 1470) {
      let html = '';
      FILAS.forEach(([letras, x0, y]) => [...letras].forEach((c, i) => {
        html += `<div class="tk${'AEIO'.includes(c) ? ' ac' : ''}" data-c="${c}" style="left:${x0 + i * 112}px;top:${y}px"><i></i><b>${c}</b></div>`;
      }));
      html += '<div class="tk" data-c=" " style="left:248px;top:336px;width:640px"><i></i></div>';
      html += '<div class="tk" data-c="." style="left:1008px;top:224px"><i></i><b>.</b></div>';
      const el = document.createElement('div');
      el.id = 'teclado'; el.style.top = top + 'px'; el.innerHTML = html;
      document.getElementById('mundo').appendChild(el);
      el.querySelectorAll('.tk').forEach(k => { this.teclas[k.dataset.c] = k; });
      return el;
    },
    entra(tl, t) {
      tl.fromTo('#teclado', {y: 520, opacity: 1}, {y: 0, duration: .42, ease: 'power3.out', immediateRender: true}, Math.max(0, t));
      D.cue(Math.max(0, t), 'swish');
    },
    parado() { gsap.set('#teclado', {opacity: 1}); },
    aperta(tl, letra, t) {
      const k = this.teclas[sem(letra)] || this.teclas[' '];
      if (!k) return;
      tl.to(k, {x: 6, y: 6, duration: .04, ease: 'none'}, t);
      tl.to(k, {x: 0, y: 0, duration: .09, ease: 'power2.out'}, t + .05);
      tl.fromTo(k.firstChild, {opacity: 1}, {opacity: 0, duration: .22, ease: 'power2.out', immediateRender: false}, t);
    },
  };
})();
