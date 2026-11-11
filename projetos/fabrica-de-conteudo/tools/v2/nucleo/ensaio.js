/* Vídeo-ensaio: a pessoa recortada (alfa) fica ENTRE duas camadas da peça.
     ?camada=tras    só o que fica atrás dela
     ?camada=frente  só o que fica na frente
     sem camada      tudo (quando não há recorte)
   O compositor empilha fundo/vídeo → tras → pessoa (alfa) → frente, tudo no
   mesmo t. Um elemento é de uma camada pelo atributo data-c="tras|frente";
   quem não tem data-c sai nas duas.

   window.__pessoa  onde a peça espera a pessoa {lado, x, y, w, h}, em px de
                    1920×1080. ?lado=esq|centro|dir troca o lado.
                    O take é gravado com a pessoa NO CENTRO e aberto: o compositor
                    reenquadra (recorta/desliza o take) até esse lugar em 0,6 s
                    na entrada da peça e volta ao centro nos 0,6 s finais
                    (ease-in-out cúbico). Com lado=centro, não mexe.
   window.__video   efeitos na camada da pessoa/vídeo, que o compositor aplica:
                    [{t0, t1, efeito, ...}]
                      congela                   segura o quadro de t0
                      pb                        preto e branco
                      zoom      {de, para, entra, curva}  aproxima (ease-out cúbico em `entra` s;
                                curva 'reta': velocidade constante, pra deriva entre dois cortes)
                      empurra   {valor}            aproxima `valor` em 0,5 s e volta até t1; multiplica o zoom
                      dessatura {valor, entra}     tira `valor` (0–1) da saturação, em rampa
                      desfoca   {px, entra, sai}   desfoca SÓ O FUNDO (pelo recorte), em rampa
                      cartao    {x, y, w, h, raio, escala, topo}  o take reduzido (escala, topo em y)
                                num cartão de cantos redondos, por cima da camada tras; a pessoa
                                só entra ACIMA do cartão (a cabeça que passa da borda). e_editorial */
(function () {
  const Q = new URLSearchParams(location.search), R = document.documentElement;
  const c = Q.get('camada');
  if (c) R.classList.add('c-' + c);
  window.__video = [];
  const W = 700, H = 1242;
  window.E = {
    pessoa(lado) {
      lado = Q.get('lado') || lado;
      const l = lado === 'esq' ? 60 : lado === 'centro' ? 610 : 1160;
      window.__pessoa = {lado, x: l, y: 1160 - H, w: W, h: H};
      return {lado, l, r: l + W, cx: l + W / 2, w: W, h: H};
    },
    video(t0, t1, efeito, extra = {}) {
      window.__video.push({t0: Math.round(t0 * 1000) / 1000, t1: Math.round(t1 * 1000) / 1000, efeito, ...extra});
    },
  };
})();
