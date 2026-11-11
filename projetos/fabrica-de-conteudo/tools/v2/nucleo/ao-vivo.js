/* ao-vivo.js — o canal de controle da live: cliente mínimo do obs-websocket v5 (vem no
   OBS 32), sem dependência. Quem fala é o painel (vivo/painel.html, dock do OBS); quem
   ouve é a peça na fonte de navegador (?vivo=1).

     AoVivo.ouve(alvo, fn)       fn(estado) a cada CustomEvent {canal:'tinteiro', alvo, estado}
     AoVivo.manda(alvo, estado)  request BroadcastCustomEvent com o estado INTEIRO
     AoVivo.status(fn)           fn(ligado, motivo) quando conecta ou cai (o painel mostra)
     AoVivo.gatilho(cena, fn)    fn(fonte, ligada) a cada fonte ligada OU desligada na cena (o
                                 stream deck mexe na visibilidade; ver vivo/ulanzi/LEIA-ME.md)

   Liga na primeira chamada de ouve/manda/status e reconecta a cada 2 s quando o OBS fecha.
   Endereço em ?ws= (padrão ws://127.0.0.1:4455) e senha em ?senha=. A senha só vive na URL
   da fonte: não vai pra arquivo do repo nem pra log.

   Protocolo: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
     Hello (op 0) traz authentication {challenge, salt};
     secret = base64(sha256(senha + salt)); auth = base64(sha256(secret + challenge));
     Identify (op 1) com eventSubscriptions = 1 (General, onde mora o CustomEvent) | 128
     (SceneItems, o SceneItemEnableStateChanged dos gatilhos);
     Identified (op 2); Event (op 5); Request (op 6); RequestResponse (op 7). */
(function (G) {
  const Q = new URLSearchParams(G.location ? G.location.search : '');
  const ENDERECO = Q.get('ws') || 'ws://127.0.0.1:4455', SENHA = Q.get('senha') || '';
  const ouvintes = {}, avisa = [], gatilhos = {}, espera = {};
  let ws = null, ligado = false, n = 0;
  const TINTA = {amber: 'ambar', amethyst: 'ametista', emerald: 'esmeralda', ruby: 'rubi', sapphire: 'safira', steel: 'aco'};

  /* SHA-256 em JS puro: o esquema http://absolute/ do OBS pode não ser contexto seguro,
     e aí não existe crypto.subtle. As constantes saem das raízes dos primos (FIPS 180-4). */
  function sha256(b) {
    const K = [], H = [], fr = x => ((x - Math.floor(x)) * 4294967296) >>> 0;
    for (let p = 2, i = 0; i < 64; p++) {
      let primo = true;
      for (let d = 2; d * d <= p; d++) if (p % d === 0) { primo = false; break; }
      if (!primo) continue;
      if (i < 8) H[i] = fr(Math.sqrt(p));
      K[i++] = fr(Math.cbrt(p));
    }
    const L = b.length, T = ((L + 9 + 63) >> 6) << 6, m = new Uint8Array(T);
    m.set(b); m[L] = 0x80;
    const dv = new DataView(m.buffer), W = new Array(64), r = (x, k) => (x >>> k) | (x << (32 - k));
    dv.setUint32(T - 8, Math.floor(L / 0x20000000)); dv.setUint32(T - 4, (L << 3) >>> 0);
    for (let o = 0; o < T; o += 64) {
      for (let i = 0; i < 64; i++) {
        if (i < 16) { W[i] = dv.getUint32(o + i * 4) | 0; continue; }
        const a = W[i - 15], c = W[i - 2];
        W[i] = (W[i - 16] + (r(a, 7) ^ r(a, 18) ^ (a >>> 3)) + W[i - 7] + (r(c, 17) ^ r(c, 19) ^ (c >>> 10))) | 0;
      }
      let [a, bb, c, d, e, f, g, h] = H;
      for (let i = 0; i < 64; i++) {
        const t1 = (h + (r(e, 6) ^ r(e, 11) ^ r(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + W[i]) | 0;
        const t2 = ((r(a, 2) ^ r(a, 13) ^ r(a, 22)) + ((a & bb) ^ (a & c) ^ (bb & c))) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = bb; bb = a; a = (t1 + t2) | 0;
      }
      [a, bb, c, d, e, f, g, h].forEach((x, i) => { H[i] = (H[i] + x) | 0; });
    }
    const out = new DataView(new ArrayBuffer(32));
    H.forEach((x, i) => out.setUint32(i * 4, x >>> 0));
    return new Uint8Array(out.buffer);
  }
  async function sha(txt) {
    const b = new TextEncoder().encode(txt), s = G.crypto && G.crypto.subtle;
    return s ? new Uint8Array(await s.digest('SHA-256', b)) : sha256(b);
  }
  const b64 = u8 => btoa(String.fromCharCode(...u8));
  async function auth(senha, salt, challenge) {
    return b64(await sha(b64(await sha(senha + salt)) + challenge));
  }

  function muda(v, motivo) {
    ligado = v;
    avisa.forEach(fn => fn(v, motivo));
  }
  function liga() {
    if (ws) return;
    const s = ws = new WebSocket(ENDERECO);
    s.onmessage = async ev => {
      const m = JSON.parse(ev.data);
      if (m.op === 0) {
        const d = {rpcVersion: 1, eventSubscriptions: 1 | 128};
        const a = m.d.authentication;
        if (a) d.authentication = await auth(SENHA, a.salt, a.challenge);
        s.send(JSON.stringify({op: 1, d}));
      } else if (m.op === 2) muda(true);
      else if (m.op === 5 && m.d.eventType === 'CustomEvent') {
        const e = m.d.eventData || {};
        if (e.canal === 'tinteiro') (ouvintes[e.alvo] || []).forEach(fn => fn(e.estado || {}));
      } else if (m.op === 5 && m.d.eventType === 'SceneItemEnableStateChanged') {
        // o evento só traz o id do item: o nome da fonte vem da lista da cena
        const {sceneName, sceneItemId, sceneItemEnabled} = m.d.eventData, fns = gatilhos[sceneName];
        if (!fns) return;
        const r = await pede('GetSceneItemList', {sceneName});
        const it = r && r.sceneItems.find(i => i.sceneItemId === sceneItemId);
        if (it) fns.forEach(fn => fn(it.sourceName, sceneItemEnabled));
      } else if (m.op === 7 && espera[m.d.requestId]) {
        espera[m.d.requestId](m.d.requestStatus.result ? m.d.responseData : null);
        delete espera[m.d.requestId];
      }
    };
    // 4009 = senha errada (WebSocketCloseCode.AuthenticationFailed)
    s.onclose = ev => {
      ws = null;
      muda(false, ev.code === 4009 ? 'senha' : 'fora');
      setTimeout(liga, 2000);
    };
  }

  function pede(requestType, requestData) {
    if (!ligado) return Promise.resolve(null);
    const requestId = 'tt' + (++n);
    ws.send(JSON.stringify({op: 6, d: {requestType, requestId, requestData}}));
    return new Promise(r => {
      espera[requestId] = r;
      setTimeout(() => { delete espera[requestId]; r(null); }, 3000);
    });
  }

  G.AoVivo = {
    ouve(alvo, fn) { (ouvintes[alvo] = ouvintes[alvo] || []).push(fn); liga(); },
    manda(alvo, estado) {
      liga();
      if (!ligado) return false;   // o painel reenvia a cada 2 s; nada se perde
      ws.send(JSON.stringify({op: 6, d: {requestType: 'BroadcastCustomEvent', requestId: 'tt' + (++n),
        requestData: {eventData: {canal: 'tinteiro', alvo, estado}}}}));
      return true;
    },
    status(fn) { avisa.push(fn); fn(ligado); liga(); },
    gatilho(cena, fn) { (gatilhos[cena] = gatilhos[cena] || []).push(fn); liga(); },
    // a tinta do Lorcana (nome em inglês, como a API e o painel escrevem) → token do núcleo
    tinta: t => TINTA[t] ? `var(--t-${TINTA[t]})` : '',
    TINTAS: Object.keys(TINTA),
    // "Nome - Versão" (ou só o nome) → {nome, versao, img, tintas, custo}, no índice
    // vivo/cartas.js (window.CARTAS) que a página carregou; null se não achar
    carta(txt) {
      const C = G.CARTAS, k = (txt || '').trim().toLowerCase();
      if (!C || !k) return null;
      const l = C.c.find(c => (c[1] ? `${c[0]} - ${c[1]}` : c[0]).toLowerCase() === k) || C.c.find(c => c[0].toLowerCase() === k);
      return l && {nome: l[0], versao: l[1], img: /^https?:/.test(l[2]) ? l[2] : C.img + l[2],
        tintas: l[3].split(',').filter(Boolean), custo: l[4]};
    },
    // medida comum das peças l_: encolhe a letra até caber na largura e em `linhas` linhas
    // (o D.cabe do núcleo só encolhe e nunca quebra; texto que o dono digita ao vivo quebra)
    encolhe(el, min, linhas = 1) {
      el.style.fontSize = '';
      let px = parseFloat(getComputedStyle(el).fontSize);
      const cheio = () => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > parseFloat(getComputedStyle(el).lineHeight) * linhas + 2;
      while (px > min && cheio()) { px -= 2; el.style.fontSize = px + 'px'; }
    },
    auth, _sha256: sha256,
  };
})(typeof window !== 'undefined' ? window : globalThis);
