/* qa.js — inspeção de peça. A MESMA regra no Estúdio (navegador) e no `v2.py qa`
   (Playwright): o que passa aqui passa no render.

   V2QA.estatico(fonte)          lê o HTML: contrato da timeline, tokens, documentação
   V2QA.dinamico(win, sons, o)   com a peça PRONTA (__ready): duração, cues com arquivo,
                                 texto que vaza/é cortado pela caixa, texto fora do quadro,
                                 zona do rosto (16:9), faixa do player (16:9), entrada e
                                 saída (peças alfa)
     o = {alfa, sai, rosto: [x0, y0, x1, y1] | null, player: y0 | null (sem: 16:9 → 896 em 1080)}

   Faixa do player: no 16:9, de y0 até o pé é da barra de progresso e dos controles do
   YouTube. Texto, imagem, svg, canvas ou caixa (.nb) que entra ali reprova; o que cobre
   o quadro inteiro (fundo) não conta. Fundo puro que desce até o pé: data-qa="fundo".

   Achado: {nivel: 'falha'|'aviso'|'nota', tipo, msg}
   Pra excluir um trecho de propósito (letreiro que corre, texto de guia): data-qa="ignora".
   Pra declarar a intenção da peça inteira: <html data-qa="entra-seco fica fundo cena">. */
(function (G) {
  const TOKENS = new Set(['#ebca88', '#22170e', '#0b0d12', '#0640fb', '#f2c744', '#ffffff', '#fff', '#f4f2ec', '#17a354', '#e1432f',
    '#3b3f4a', '#7c808b', '#d9d4c8', '#dce4ff', '#c9d6ff', '#ffe0d9', '#000', '#000000', '#e9e6df']);
  // a faixa do player no 16:9: 184 de 1080 (y 896 em diante). Medida no LEIA-ME, "Faixa do player";
  // a mesma conta do D.PE (direcao-v2.js), que a peça usa pra ficar acima dela.
  const PE_PLAYER = 184 / 1080;
  const FONTE_FORA = /\b(Inter|Roboto|Arial|Helvetica|Archivo|JetBrains|Montserrat|Poppins|Fraunces)\b/;

  function estatico(src) {
    const A = [], add = (nivel, tipo, msg) => A.push({nivel, tipo, msg});
    const cab = (src.match(/<!--([\s\S]*?)-->/) || ['', ''])[1];
    const cod = src.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
    const css = (cod.match(/<style[^>]*>[\s\S]*?<\/style>/gi) || []).join('\n');
    if (/@keyframes|[\s;{]animation\s*:/.test(css)) add('falha', 'contrato', 'animação em CSS: roda fora da timeline e não sai no render quadro a quadro');
    if (/requestAnimationFrame|setInterval\s*\(/.test(cod)) add('falha', 'contrato', 'relógio próprio (requestAnimationFrame/setInterval): o render busca a timeline, não espera');
    const cores = new Set();
    for (const m of cod.matchAll(/(?::\s*|,\s*|\(\s*|['"])(#[0-9a-f]{3,8})(?=[\s;,)'"}!])/gi)) {
      const h = m[1].toLowerCase();
      if ([4, 5, 7, 9].includes(h.length) && !TOKENS.has(h)) cores.add(h);
    }
    if (cores.size) add('aviso', 'token', 'cor fora do núcleo: ' + [...cores].slice(0, 5).join(' '));
    const f = cod.match(FONTE_FORA);
    if (f) add('aviso', 'token', 'fonte fora do núcleo: ' + f[1]);
    // D.cabe embrulha cada linha do alvo num <span>: regra "alvo span" pega o embrulho também
    const alvos = [...cod.matchAll(/D\.cabe\(\s*['"]([^'"]+)['"]/g)].map(m => m[1].trim().split(/\s+/).pop());
    const regras = [...css.matchAll(/([^{}]+?)\s+span\s*\{/g)].map(m => m[1].trim().split(/\s+/).pop());
    const pega = regras.filter(r => alvos.some(a => r === a || r.endsWith(a)));
    if (pega.length) add('nota', 'css', 'regra "' + pega[0] + ' span" num alvo do D.cabe: também pega o embrulho de linha (use "' + pega[0] + ' > span")');
    if (!/^\s*\?\S/m.test(cab)) add('nota', 'doc', 'cabeçalho sem linha de exemplo (?…): o catálogo fica sem exemplo');
    if (/D\.[nq]\(\s*'t'\s*,/.test(cod)) add('nota', 'api', 'lê ?t= (antigo); as peças novas usam ?t0=');
    return A;
  }

  function opac(w, el) {
    let a = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = w.getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 0;
      a *= parseFloat(cs.opacity);
      if (a < .04) return 0;
    }
    return a;
  }
  // o retângulo que um pai recorta: overflow ≠ visible, ou clip-path inset()
  function caixaCorte(w, e, cs) {
    const b = e.getBoundingClientRect(), m = cs.clipPath && cs.clipPath.match(/inset\(([^)]*)\)/);
    if (!m) return b;
    const v = m[1].split(/\s+round\s+/)[0].trim().split(/\s+/);
    const [t, r, bo, l] = v.length === 1 ? [v[0], v[0], v[0], v[0]] : v.length === 2 ? [v[0], v[1], v[0], v[1]] : v.length === 3 ? [v[0], v[1], v[2], v[1]] : v;
    const px = (s, tot) => /%$/.test(s) ? parseFloat(s) / 100 * tot : parseFloat(s) || 0;
    return {left: b.left + px(l, b.width), right: b.right - px(r, b.width), top: b.top + px(t, b.height), bottom: b.bottom - px(bo, b.height)};
  }
  // o que sobra visível do texto depois dos pais que cortam (até `ate`, exclusive)
  function recorta(w, el, r, ate) {
    let x0 = r.left, y0 = r.top, x1 = r.right, y1 = r.bottom;
    for (let e = el; e && e.nodeType === 1 && e !== w.document.body && e !== ate; e = e.parentElement) {
      const cs = w.getComputedStyle(e);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || (cs.clipPath && cs.clipPath !== 'none')) {
        const b = caixaCorte(w, e, cs);
        x0 = Math.max(x0, b.left); y0 = Math.max(y0, b.top); x1 = Math.min(x1, b.right); y1 = Math.min(y1, b.bottom);
        if (x1 - x0 < 1 || y1 - y0 < 1) return null;
      }
    }
    return {left: x0, top: y0, right: x1, bottom: y1};
  }
  function textos(w) {
    const d = w.document, rg = d.createRange(), tw = d.createTreeWalker(d.body, 4), out = [];
    let n;
    while ((n = tw.nextNode())) {
      const tx = n.textContent.replace(/\s+/g, ' ').trim();
      if (!tx) continue;
      const el = n.parentElement;
      if (!el || el.closest('script,style,noscript,[data-qa="ignora"]')) continue;
      rg.selectNodeContents(n);
      const b = rg.getBoundingClientRect();
      if (b.width < 1 || b.height < 1) continue;
      const a = opac(w, el);
      if (!a) continue;
      // o retângulo do texto é a caixa da linha, não a tinta: tira o respiro do
      // ascendente/descendente (em display gigante com entrelinha < 1 ele sobra muito)
      const fs = parseFloat(w.getComputedStyle(el).fontSize) || 16;
      const r = {left: b.left, right: b.right, top: b.top + fs * .22, bottom: b.bottom - fs * .1};
      if (r.bottom <= r.top) { r.top = b.top; r.bottom = b.bottom; }
      const vis = recorta(w, el, r, null);
      if (vis) out.push({el, tx, r, vis, a, fs, n});
    }
    return out;
  }
  // posicionado de propósito (etiqueta na borda, carimbo que sobra): não é vazar
  function solto(w, el, ate) {
    for (let e = el; e && e !== ate; e = e.parentElement) {
      const p = w.getComputedStyle(e).position;
      if (p === 'absolute' || p === 'fixed') return true;
    }
    return false;
  }
  // dentro de máscara em degradê (lista que corre): o corte é o desenho
  function mascarado(w, el) {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = w.getComputedStyle(e);
      if ((cs.maskImage && cs.maskImage !== 'none') || (cs.webkitMaskImage && cs.webkitMaskImage !== 'none')) return true;
    }
    return false;
  }
  const dentro = (r, W, H) => r.right > 0 && r.left < W && r.bottom > 0 && r.top < H;

  function mede(w, W, H, o) {
    const out = [];
    for (const {el, tx, r, vis, fs} of textos(w)) {
      if (mascarado(w, el)) continue;
      const cx = el.closest('.nb');
      if (cx && !solto(w, el, cx)) {
        const rr = recorta(w, el, r, cx);       // os pais DENTRO da caixa que cortam (rolo de dígitos, máscara de palavra)
        if (rr) {
          const b = cx.getBoundingClientRect(), cs = w.getComputedStyle(cx), bw = parseFloat(cs.borderLeftWidth) || 0;
          const px = Math.max(b.left + bw - rr.left, rr.right - (b.right - bw), 0), py = Math.max(b.top - rr.top, rr.bottom - b.bottom, 0);
          if (px > Math.max(3, fs * .05) || py > 10) {
            const corta = cs.overflowX !== 'visible' || cs.overflowY !== 'visible';
            if (!corta) out.push({tipo: 'vaza', tx: tx.slice(0, 36), px: Math.round(Math.max(px, py))});
            else out.push({tipo: 'cortado', tx: tx.slice(0, 36), px: Math.round(Math.max(px, py))});
          }
        }
      }
      if (dentro(vis, W, H)) {
        const f = Math.max(-r.left, r.right - W, -r.top, r.bottom - H);
        if (f > 4) out.push({tipo: 'fora', tx: tx.slice(0, 36), px: Math.round(f)});
        if (o.rosto) {
          const [x0, y0, x1, y1] = o.rosto;
          if (vis.right > x0 && vis.left < x1 && vis.bottom > y0 && vis.top < y1) out.push({tipo: 'rosto', tx: tx.slice(0, 36), px: 0});
        }
        if (o.player != null && vis.bottom > o.player + 2) out.push({tipo: 'player', tx: tx.slice(0, 36), px: Math.round(vis.bottom - o.player)});
      }
    }
    if (o.player != null) out.push(...noPe(w, W, H, o.player));
    return out;
  }
  // o que não é texto e desce até a faixa do player: imagem, desenho, caixa
  function noPe(w, W, H, y0) {
    const out = [];
    for (const el of w.document.body.querySelectorAll('img,svg,canvas,video,.nb')) {
      if (el.closest('[data-qa="ignora"],[data-qa="fundo"]') || (el.tagName.toLowerCase() === 'svg' && el.parentElement.closest('svg'))) continue;
      if (!opac(w, el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || (r.width >= W * .9 && r.height >= H * .9)) continue;
      const vis = recorta(w, el, {left: r.left, top: r.top, right: r.right, bottom: r.bottom}, null);
      if (!vis || !dentro(vis, W, H) || vis.bottom <= y0 + 2) continue;
      const nome = el.id ? '#' + el.id : el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : '');
      out.push({tipo: 'player', tx: nome, px: Math.round(Math.min(vis.bottom, H) - y0)});
    }
    return out;
  }

  /* Geometria: o que o `mede` acusa mais as medidas cruas, no instante em que a timeline está
     (quem chama busca o tempo). Por texto: caixa em px do quadro, linhas e se está na zona segura,
     no rosto ou na faixa do player. Um "texto" é o bloco (primeiro ancestral que não é inline),
     então <br> e quebra automática contam como linhas do mesmo bloco.
     o = {seguro: [x0, y0, x1, y1] | null, rosto: [x0, y0, x1, y1] | null, player: y0 | null} */
  function geometria(w, o) {
    o = o || {};
    const W = w.innerWidth, H = w.innerHeight, rg = w.document.createRange(), gr = new Map();
    const dentroDe = (v, z) => v.left >= z[0] - 1 && v.top >= z[1] - 1 && v.right <= z[2] + 1 && v.bottom <= z[3] + 1;
    for (const {el, tx, r, vis, fs, n} of textos(w)) {
      if (mascarado(w, el)) continue;
      let g = el;
      while (g.parentElement && w.getComputedStyle(g).display === 'inline') g = g.parentElement;
      if (!gr.has(g)) gr.set(g, {el: g, tx: [], tops: [], l: 1e9, t: 1e9, r: -1e9, b: -1e9, fs, v: {left: 1e9, top: 1e9, right: -1e9, bottom: -1e9}});
      const x = gr.get(g);
      x.tx.push(tx);
      rg.selectNodeContents(n);
      for (const q of rg.getClientRects()) if (q.width > 1) x.tops.push(q.top);
      x.l = Math.min(x.l, r.left); x.t = Math.min(x.t, r.top); x.r = Math.max(x.r, r.right); x.b = Math.max(x.b, r.bottom);
      x.v = {left: Math.min(x.v.left, vis.left), top: Math.min(x.v.top, vis.top), right: Math.max(x.v.right, vis.right), bottom: Math.max(x.v.bottom, vis.bottom)};
    }
    const R = n => Math.round(n * 10) / 10;
    const textosG = [...gr.values()].map(x => {
      const tops = x.tops.sort((a, b) => a - b);
      let linhas = 0, ult = -1e9;
      for (const t of tops) if (t - ult > x.fs * .5) { linhas++; ult = t; }
      const v = x.v;
      return {tx: x.tx.join(' ').slice(0, 60), cls: typeof x.el.className === 'string' ? x.el.className : '', linhas, fs: R(x.fs),
        rect: {x: R(x.l), y: R(x.t), w: R(x.r - x.l), h: R(x.b - x.t)},
        seguro: o.seguro ? dentroDe(v, o.seguro) : null,
        rosto: !!o.rosto && v.right > o.rosto[0] && v.left < o.rosto[2] && v.bottom > o.rosto[1] && v.top < o.rosto[3],
        player: o.player != null && v.bottom > o.player + 2};
    });
    // a caixa visível da peça: o texto mais o que não é texto e desenha (imagem, svg, canvas, .nb)
    let u = null;
    const une = b => { u = u ? {l: Math.min(u.l, b.left), t: Math.min(u.t, b.top), r: Math.max(u.r, b.right), b: Math.max(u.b, b.bottom)} : {l: b.left, t: b.top, r: b.right, b: b.bottom}; };
    gr.forEach(x => une({left: x.v.left, top: x.v.top, right: x.v.right, bottom: x.v.bottom}));
    for (const el of w.document.body.querySelectorAll('img,svg,canvas,video,.nb')) {
      if (el.closest('[data-qa="ignora"],[data-qa="fundo"]') || (el.tagName.toLowerCase() === 'svg' && el.parentElement.closest('svg')) || !opac(w, el)) continue;
      const b = el.getBoundingClientRect();
      if (b.width < 2 || b.height < 2 || (b.width >= W * .9 && b.height >= H * .9)) continue;
      const v = recorta(w, el, b, null);
      if (v && dentro(v, W, H)) une(v);
    }
    const achados = mede(w, W, H, {rosto: o.rosto || null, player: o.player ?? null});
    return {caixa: u && {x: R(u.l), y: R(u.t), w: R(u.r - u.l), h: R(u.b - u.t)}, textos: textosG,
      overflow: achados.filter(a => a.tipo === 'vaza' || a.tipo === 'cortado' || a.tipo === 'fora'), achados};
  }

  function dinamico(w, sons, o) {
    o = o || {};
    const tl = w.__tl, dur = +w.__duration, cues = (w.__cues || []).slice(), A = [];
    const add = (nivel, tipo, msg) => A.push({nivel, tipo, msg});
    const W = w.innerWidth, H = w.innerHeight;
    if (!(dur > 0 && dur < 90)) add('falha', 'duracao', 'duração declarada inválida: ' + dur);
    const tld = tl.duration();
    if (tld > dur + .05) add('aviso', 'duracao', `a timeline tem ${tld.toFixed(2)}s e a peça declara ${dur.toFixed(2)}s: o render corta o fim`);
    const faltam = [...new Set(cues.filter(c => !sons[c.tipo]).map(c => c.tipo))];
    if (faltam.length) add('falha', 'som', 'cue sem arquivo na biblioteca: ' + faltam.join(', '));
    const depois = cues.filter(c => c.t > dur + .05);
    if (depois.length) add('aviso', 'som', `${depois.length} cue(s) depois do fim: ${depois.map(c => c.tipo + '@' + c.t).join(', ')}`);
    if (w.document.fonts && !w.document.fonts.check('700 40px "Space Grotesk"')) add('aviso', 'fonte', 'Space Grotesk não carregou: o render sai com a fonte do sistema');
    // data-qa no <html>: "entra-seco" (gancho que bate no 1º quadro), "fica" (segura até o corte),
    // "fundo" (fundo puro: pode descer até a faixa do player), "cena" (moldura de cena da live)
    const decl = w.document.documentElement.getAttribute('data-qa') || '';
    if (o.player === undefined) o = {...o, player: W * 9 === H * 16 ? Math.round(H * (1 - PE_PLAYER)) : null};
    // "cena": moldura de cena da live (l_placar, l_treino), com a geometria em que o OBS encaixa as
    // fontes; fica fora da faixa até o dono decidir redesenhar (07/10/2026). Não use em peça nova.
    if (/fundo|cena/.test(decl)) o = {...o, player: null};
    // layout: dois instantes em que tudo já entrou e nada saiu
    const vistos = new Map();
    [dur * .5, Math.max(0, dur - .55)].forEach(t => {
      tl.time(t, false);
      mede(w, W, H, o).forEach(p => { const k = p.tipo + '|' + p.tx; if (!vistos.has(k)) vistos.set(k, {...p, t}); });
    });
    const ROT = {vaza: 'texto vaza da caixa', cortado: 'texto cortado pela caixa', fora: 'texto sai do quadro', rosto: 'texto na zona do rosto', player: 'na faixa do player do YouTube (barra e controles)'};
    // a faixa do player sai numa linha só: a mais funda e quantas coisas entram
    const pe = [...vistos.values()].filter(p => p.tipo === 'player');
    pe.forEach(p => vistos.delete(p.tipo + '|' + p.tx));
    if (pe.length) {
      const f = pe.reduce((m, p) => p.px > m.px ? p : m);
      add('falha', 'layout', `${ROT.player} em ${f.px}px (y ${o.player}+): "${f.tx}"${pe.length > 1 ? ` e mais ${pe.length - 1}` : ''} (${f.t.toFixed(2)}s)`);
    }
    vistos.forEach(p => add(p.tipo === 'fora' || p.tipo === 'rosto' ? 'aviso' : 'falha', 'layout',
      `${ROT[p.tipo]}${p.px ? ' em ' + p.px + 'px' : ''}: "${p.tx}" (${p.t.toFixed(2)}s)`));
    if (o.alfa) {
      tl.time(0, false);
      const v0 = /entra-seco/.test(decl) ? [] : textos(w).filter(x => x.a > .3 && dentro(x.vis, W, H));
      if (v0.length) add('aviso', 'entrada', `já está na tela no quadro 0: "${v0[0].tx.slice(0, 32)}" (entra sem animação)`);
      if (o.sai !== false && !/fica/.test(decl)) {
        tl.time(dur, false);
        const vf = textos(w).filter(x => x.a > .3 && dentro(x.vis, W, H));
        if (vf.length) add('aviso', 'saida', `ainda na tela no último quadro: "${vf[0].tx.slice(0, 32)}" (a peça não sai)`);
      }
    }
    const mv = movimento(w);
    A.push(...mv.achados);
    return {dur, tl: +tld.toFixed(3), ncues: cues.length, sons: [...new Set(cues.map(c => c.tipo))], achados: A};
  }

  /* Movimento: os 12 princípios que dá pra medir lendo a timeline (window.__tl) e buscando o tempo
     (pesquisa/animacao-principios/ESTUDO.md). Nota do dono "molde-igual", 12/10/2026: "cara de molde
     montado com peça pronta" (docs/checks-do-dono.md). Só aviso: pega o jeito, não o gosto.
     Os limites (MOV) saíram da varredura das peças do catálogo como estavam, aprovadas (o núcleo de
     antes, pesquisa/animacao-principios/calibra_qa.py): cada um fica no p95 delas ou acima, e só acusa
     o caso que foge (a tabela da calibração no ESTUDO).
     Intenção declarada no elemento: data-qa="linear" (barra, deriva), data-qa="reta" (trilho),
     data-qa="heroi" (herói feito à mão, sem o D.heroi). */
  const MOV = {
    linMin: .2, linMax: 26 / 30,  // ease linear num movimento de .2 s a 26 quadros (acima é deriva, que o motionmaxxing aceita linear)
    juntos: 4,                    // mais que isso de peças entrando no MESMO quadro (aprovadas: p95 2, máx 6)
    unica: .8, unicaMin: 8,       // 80 % dos tweens com uma duração só, contando 8 ou mais (aprovadas: p95 .87)
    freio: 1.5, secos: 2,         // inclinação no fim da entrada (linear = 1; power2.in = 2); acusa acima de 2 (p95 1)
    reta: 80, desvio: .015, retas: 3,   // caminho de 80 px que não sai 1,5 % da reta; acusa acima de 3 (p95 3)
    antecipa: .01,                // o herói recua ao menos 1 % do que vai crescer
  };
  const RESERVADAS = new Set(['duration', 'ease', 'delay', 'repeat', 'repeatDelay', 'yoyo', 'yoyoEase', 'stagger', 'onUpdate',
    'onStart', 'onComplete', 'onRepeat', 'onReverseComplete', 'onUpdateParams', 'onCompleteParams', 'callbackScope',
    'immediateRender', 'lazy', 'data', 'startAt', 'overwrite', 'paused', 'id', 'inherit', 'runBackwards', 'keyframes',
    'transformOrigin', 'force3D', 'parent', 'clearProps']);
  const ESPACO = /^(x|y|xPercent|yPercent|scale|scaleX|scaleY|left|top|rotation)$/;

  function movimento(w, o) {
    o = o || {};
    const tl = w.__tl, g = w.gsap, A = [], cru = {};
    const add = (tipo, msg) => A.push({nivel: 'aviso', tipo, msg});
    if (!tl || !g) return {achados: A, cru};
    const tws = tl.getChildren(true, true, false);
    const ini = tw => { let s = tw.startTime(); for (let p = tw.parent; p && p !== tl; p = p.parent) s += p.startTime(); return s; };
    const ease = tw => { try { const e = tw.vars.ease; return typeof e === 'function' ? e : g.parseEase(e || 'power1.out') || (p => p); } catch (e) { return p => p; } };
    const props = tw => Object.keys(tw.vars).filter(k => !RESERVADAS.has(k));
    const els = tw => (tw.targets() || []).filter(x => x && x.nodeType === 1);
    const marca = (el, q) => el.closest && el.closest(`[data-qa~="${q}"],[data-qa~="ignora"]`);
    const linear = e => Math.abs(e(.25) - .25) < .01 && Math.abs(e(.75) - .75) < .01;
    const repete = tw => (tw.vars.repeat || 0) !== 0;
    const entrada = tw => { const s = tw.vars.startAt || (tw.vars.runBackwards ? tw.vars : null);
      return !!s && (s.opacity === 0 || s.autoAlpha === 0); };
    const t0 = tl.time();

    // 6. linear num movimento: "the fastest way to make a render look like a render" (@flxrnc)
    const lin = tws.filter(tw => !repete(tw) && tw.duration() >= MOV.linMin && tw.duration() <= MOV.linMax
      && props(tw).some(k => ESPACO.test(k) && k !== 'rotation') && linear(ease(tw)) && els(tw).some(el => !marca(el, 'linear')));
    cru.linear = lin.length;
    if (lin.length) add('movimento', `ease linear em ${lin.length} movimento(s) de ${MOV.linMin}–${MOV.linMax.toFixed(2)} s (${props(lin[0]).join(',')} em ${ini(lin[0]).toFixed(2)}s): reta no gráfico de velocidade; ease-out na entrada, ease-in na saída`);

    // 3. tudo no mesmo quadro: "everything fading in at once" (@flxrnc, proibido por nome)
    const quadros = new Map();
    const passo = tw => { const s = tw.vars.stagger, n = els(tw).length;
      return !s ? 0 : typeof s === 'number' ? s : s.each ?? (n > 1 ? (s.amount || 0) / (n - 1) : 0); };
    tws.filter(tw => entrada(tw)).forEach(tw => els(tw).forEach((el, i) => {
      const q = Math.round((ini(tw) + i * passo(tw)) * 30);
      if (!quadros.has(q)) quadros.set(q, new Set());
      quadros.get(q).add(el);
    }));
    let pior = [0, 0];
    quadros.forEach((s, q) => { if (s.size > pior[1]) pior = [q, s.size]; });
    cru.juntos = pior[1];
    if (pior[1] > MOV.juntos) add('movimento', `${pior[1]} elementos entram no mesmo quadro (${(pior[0] / 30).toFixed(2)}s): escalone 1–3 quadros (D.pousa já faz com vários alvos)`);

    // 9. duração única: o "molde" é uma duração pra tudo
    const durs = tws.filter(tw => !repete(tw) && tw.duration() >= .1 && props(tw).some(k => ESPACO.test(k) || k === 'opacity'))
      .map(tw => Math.round(tw.duration() * 100));
    const conta = new Map(); durs.forEach(d => conta.set(d, (conta.get(d) || 0) + 1));
    const [dmais, nmais] = [...conta.entries()].reduce((m, x) => x[1] > m[1] ? x : m, [0, 0]);
    cru.unica = durs.length ? +(nmais / durs.length).toFixed(2) : 0; cru.ndurs = durs.length;
    if (durs.length >= MOV.unicaMin && nmais / durs.length >= MOV.unica)
      add('movimento', `${Math.round(nmais / durs.length * 100)} % dos ${durs.length} movimentos duram ${(dmais / 100).toFixed(2)} s: tempo por papel e por peso (D.T)`);

    // 6. entrada sem freio: chega com a velocidade no máximo e para seco, sem amassar nem assentar
    const seco = tws.filter(tw => entrada(tw) || (tw.vars.startAt && props(tw).some(k => ESPACO.test(k)))).filter(tw => {
      if (repete(tw) || !props(tw).some(k => ESPACO.test(k) && k !== 'rotation') || tw.duration() < .1) return false;
      const e = ease(tw), v = (e(1) - e(.95)) / .05;
      if (v <= MOV.freio) return false;
      const fim = ini(tw) + tw.duration();
      return !els(tw).some(el => g.getTweensOf(el).some(x => x !== tw && ini(x) >= fim - .01 && ini(x) <= fim + 2 / 30
        && Object.keys(x.vars).some(k => /^scale/.test(k))));
    });
    cru.seco = seco.length;
    if (seco.length > MOV.secos) add('movimento', `${seco.length} entrada(s) chegam em velocidade e param seco (${ini(seco[0]).toFixed(2)}s): freie (ease-out) ou amasse no impacto (D.amassa)`);

    // 7. reta onde devia ser arco: x e y no mesmo tween, com a mesma curva, andam em linha reta
    const amostra = (el, a, b) => Array.from({length: 9}, (_, i) => {
      tl.time(a + (b - a) * i / 8, false);
      return [g.getProperty(el, 'x'), g.getProperty(el, 'y')];
    });
    let retas = 0, ex = null;
    tws.filter(tw => !repete(tw) && tw.duration() >= .15 && ['x', 'y'].every(k => k in tw.vars)).forEach(tw => els(tw).forEach(el => {
      if (marca(el, 'reta')) return;
      const p = amostra(el, ini(tw), ini(tw) + tw.duration());
      const [x0, y0] = p[0], [x1, y1] = p[8], L = Math.hypot(x1 - x0, y1 - y0);
      if (L < MOV.reta) return;
      const d = Math.max(...p.map(([x, y]) => Math.abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / L));
      if (d / L < MOV.desvio) { retas++; ex = ex || ini(tw); }
    }));
    cru.reta = retas;
    if (retas > MOV.retas) add('movimento', `${retas} movimento(s) em linha reta (${ex.toFixed(2)}s): o caminho é um arco (D.arco; Lasseter: "straight inbetweens can completely kill the essence of an action")`);

    // 2. o herói sem antecipação: cresce direto, sem recuar antes
    let semAnt = 0;
    w.document.querySelectorAll('[data-heroi],[data-qa~="heroi"]').forEach(el => {
      const meus = g.getTweensOf(el).filter(x => props(x).some(k => /^scale/.test(k)));
      if (!meus.length) return;
      const a = Math.min(...meus.map(ini)), s = [];
      for (let t = a; t <= a + .6; t += 1 / 30) { tl.time(t, false); s.push(g.getProperty(el, 'scaleY')); }
      const fim = s[s.length - 1], sobe = Math.sign(fim - s[0]) || 1, faixa = Math.abs(fim - s[0]) || 1;
      if (!s.some(v => (v - s[0]) * sobe < -MOV.antecipa * faixa)) semAnt++;
    });
    cru.heroiSemAntecipacao = semAnt;
    if (semAnt) add('movimento', `${semAnt} herói(s) sem antecipação: cresce direto (D.heroi recua e segura antes de estourar)`);
    tl.time(t0, false);
    return {achados: A, cru};
  }

  G.V2QA = {estatico, dinamico, mede, geometria, movimento, MOV, PE_PLAYER, versao: 4};
})(typeof window !== 'undefined' ? window : globalThis);
