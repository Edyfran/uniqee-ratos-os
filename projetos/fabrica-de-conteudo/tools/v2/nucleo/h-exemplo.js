/* Tela de exemplo (1920×1080), só pra prévia: é o fundo das peças alfa no
   visualizador e o conteúdo do h_zoom quando não vem ?img=. Neutra de
   propósito: imita um app qualquer, não segue a linguagem v2. */
window.telaExemplo = function (el) {
  const barra = w => `<div style="width:${w}px;height:12px;border-radius:6px;background:#E1E3E8"></div>`;
  const no = (x, cor, rot) => `<div style="position:absolute;left:${x}px;top:430px;width:220px;height:130px;border-radius:14px;background:#fff;border:2px solid #D5D8DE;box-shadow:0 2px 6px rgba(0,0,0,.06);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px"><div style="width:44px;height:44px;border-radius:10px;background:${cor}"></div><div style="font:600 20px/1 system-ui,sans-serif;color:#3B3F4A">${rot}</div></div>`;
  el.innerHTML = `<div style="position:absolute;inset:0;background:radial-gradient(circle,#D9DCE2 1.5px,transparent 2px) 0 0/28px 28px,#F3F4F6;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#1F2430;overflow:hidden">
    <div style="position:absolute;left:0;top:0;right:0;height:72px;background:#fff;border-bottom:1px solid #E1E3E8;display:flex;align-items:center;gap:16px;padding:0 28px">
      <div style="width:34px;height:34px;border-radius:9px;background:#FF6D5A"></div>
      <div style="font:600 22px/1 system-ui,sans-serif">Fluxo · vendas do dia</div>
      <div style="flex:1"></div>${barra(120)}<div style="width:40px;height:40px;border-radius:50%;background:#E1E3E8"></div>
    </div>
    <div style="position:absolute;left:0;top:72px;bottom:0;width:260px;background:#fff;border-right:1px solid #E1E3E8;padding:32px 26px;display:flex;flex-direction:column;gap:26px">
      ${[150, 118, 176, 132, 104, 140].map(w => `<div style="display:flex;gap:12px;align-items:center"><div style="width:22px;height:22px;border-radius:6px;background:#E1E3E8"></div>${barra(w)}</div>`).join('')}
    </div>
    <div style="position:absolute;left:310px;top:108px;font:700 34px/1 system-ui,sans-serif">Fluxo de vendas</div>
    <div style="position:absolute;left:310px;top:158px">${barra(380)}</div>
    <div style="position:absolute;left:1530px;top:100px;width:300px;height:68px;border-radius:10px;background:#FF6D5A;color:#fff;display:flex;align-items:center;justify-content:center;font:600 24px/1 system-ui,sans-serif">Executar fluxo</div>
    <svg style="position:absolute;left:0;top:0" width="1920" height="1080"><path d="M 560 495 H 680 M 900 495 H 1020 M 1240 495 H 1360" stroke="#B8BCC6" stroke-width="3" fill="none"></path></svg>
    ${no(340, '#7C5CFF', 'Webhook')}${no(680, '#D97757', 'Agente')}${no(1020, '#1FA463', 'Planilha')}${no(1360, '#EA4335', 'E-mail')}
  </div>`;
};
