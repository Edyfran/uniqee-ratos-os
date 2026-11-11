/* legendas-core.js — legenda viral v3 (prévia no navegador).

   O PRINCÍPIO: a legenda não disputa atenção com os outros elementos. Ela é
   discreta o vídeo inteiro — pequena, sem pulo, sem cor — e só se sobressai no
   MOMENTO DRAMÁTICO: uma a três vezes por vídeo, na frase que vira o argumento.
   Nesse instante a legenda de base sai e entra um preset de drama.

   Duas camadas:
     base   "suave" · "faixa" · "contorno" — a palavra falada só ganha opacidade
     drama  "golpe" · "etiqueta" · "sublinhado" · "sozinha" · "contador"
            escolhido por momento (a IA sugere) ou fixo pra todos

   Quem marca o drama é o LLM (máx. 1 a cada ~15 palavras, 3 no vídeo), com
   início e tamanho (1–3 palavras) e o preset sugerido. Número pode ir direto
   pro "contador".

   Canvas 2D na escala 540×960 das receitas.

   No pipeline (receita.html) este arquivo entra verbatim do handoff. Só liga
   quando o plano pede "legenda": {"versao": 3, ...}; os tempos vêm do Whisper
   (plano), nunca do `Legendas.tempos` por energia, e `marcaIA` não é chamado
   no render — sem LLM, os momentos saem de `Legendas.regras` ou do plano. */
(function () {
  const C = {ink: '#0B0D12', ac: '#0640fb', mk: '#F2C744', br: '#FFFFFF', no: '#E1432F'};
  const mola = p => { const c1 = 1.9, c3 = c1 + 1; return p <= 0 ? 0 : p >= 1 ? 1 : 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
  const suave = p => { p = Math.max(0, Math.min(1, p)); return p * p * (3 - 2 * p); };
  const expo = p => p >= 1 ? 1 : 1 - Math.pow(2, -10 * Math.max(0, p));
  const BASES = {
    suave: {fonte: '600 {px}px "Space Grotesk"', px: 29, maius: false},
    faixa: {fonte: '600 {px}px "Space Grotesk"', px: 28, maius: false},
    contorno: {fonte: '800 {px}px "Montserrat"', px: 27, maius: true},
  };
  const DRAMAS = ['golpe', 'etiqueta', 'sublinhado', 'sozinha', 'contador'];

  /* ONDE A LEGENDA MORA. Por padrão logo abaixo da boca (o track do rosto diz
     onde é). Na tela dividida, no meio da tela, na junção. E ela NUNCA senta em
     cima do que a receita está mostrando: cada receita declara as áreas que
     ocupa, e o bloco procura o lugar livre mais perto de onde queria estar. Se
     não houver, some — legenda por cima do gráfico é pior que legenda nenhuma. */
  function lugar(i, lt) {
    switch (i) {
      case 0: return {ocupa: [[0, 150, 540, 575]]};                         // a tese gigante atrás da cabeça
      case 1: return {y: 488, ocupa: [[20, 80, 520, 425], [30, 575, 322, 885]]};   // janela e cartão: o meio entre os dois   // janela e cartão: o meio entre os dois
      case 2: return {};                                                    // número: a cena manda o que ocupa (ele segue a cabeça)
      case 4: return lt > .33 ? {oculta: 1} : {};                            // a CTA na tela = a legenda sai
      case 5: return {y: 442, fixo: 1};                                      // tela dividida: no meio, na junção
      case 6: return {oculta: 1};                                            // a pergunta já é o texto
      case 7: return {ocupa: [[40, 800, 440, 885]]};                         // a tag do cartão
      case 10: return {ocupa: [[30, 805, 510, 905]]};                        // a frase do mito
      case 11: return {y: 900, fixo: 1};                                     // as duas cópias: no pé
      case 12: return {ocupa: [[70, 845, 470, 935]]};                        // a placa do contador
      case 13: return {ocupa: [[0, 30, 540, 140], [0, 820, 540, 945], [0, 380, 540, 640]]};   // barra, título, número gigante
      case 17: return {ocupa: [[0, 50, 540, 110], [0, 250, 540, 690], [30, 690, 510, 945]]};  // o 3 e as casas
      case 18: return {ocupa: [[40, 90, 500, 375]]};                        // o cartão censurado e a etiqueta
      case 19: return {ocupa: [[20, 55, 400, 125]]};                        // a frase que bate quando abre
      case 20: return {};                                                   // as notificações: a cena manda
      case 21: return lt < .63 ? {oculta: 1} : {};                          // a frase da interrupção é o texto
      default: return {};
    }
  }
  const LIMPA = new Set([-1, 3, 4, 14, 16, 19]);   // receitas sem gráfico: o drama "sozinha" só entra nelas
  function resolve(L, face, alto, largo, folga = 10) {
    if (L.oculta) return null;
    let y = L.y;
    if (y == null) y = face ? face.y + face.h * 1.0 + alto / 2 + 12 : 700;   // logo abaixo da boca
    if (L.fixo) return y;
    const cx = L.x ?? 270;
    const bate = yy => (L.ocupa || []).some(([x0, y0, x1, y1]) => cx + largo / 2 > x0 && cx - largo / 2 < x1 && yy + alto / 2 + folga > y0 && yy - alto / 2 - folga < y1);
    for (let d = 0; d < 420; d += 6) {
      for (const yy of [y + d, y - d]) if (yy - alto / 2 > 50 && yy + alto / 2 < 930 && !bate(yy)) return yy;
    }
    return null;
  }

  class Legendas {
    constructor() { this.base = 'suave'; this.drama = 'auto'; this.words = []; this.cards = []; this.momentos = []; this._lay = new Map(); }

    setWords(ws, momentos) {
      this.words = ws.map(w => ({...w}));
      this.momentos = (momentos || []).map(m => ({...m}));
      this.momentos.forEach(m => {
        const a = this.words[m.i], b = this.words[Math.min(this.words.length - 1, m.i + (m.n || 1) - 1)];
        if (!a) return;
        m.t0 = a.t0 - .04; m.t1 = b.t1 + .55; m.palavras = this.words.slice(m.i, m.i + (m.n || 1));
      });
      this.cards = this.agrupa(this.words);
      this._lay.clear();
    }

    agrupa(ws) {
      const cards = []; let cur = [];
      const fecha = () => { if (cur.length) cards.push({words: cur}); cur = []; };
      ws.forEach((w, i) => {
        const prev = ws[i - 1], chars = cur.reduce((a, x) => a + x.tx.length + 1, 0) + w.tx.length;
        if (cur.length && (w.t0 - prev.t1 > .3 || /[.!?]$/.test(prev.tx) || cur.length >= 5 || chars > 28)) fecha();
        cur.push(w);
      });
      fecha();
      cards.forEach((c, k) => {
        c.t0 = c.words[0].t0 - .05; const prox = cards[k + 1];
        c.t1 = Math.min(c.words[c.words.length - 1].t1 + .4, prox ? prox.words[0].t0 - .05 : Infinity); c.k = k;
      });
      return cards;
    }

    fnt(px, b = this.base) { return BASES[b].fonte.replace('{px}', px); }
    tx(s, maius) { s = s.replace(/[,;:]$/, ''); return maius ? s.toUpperCase() : s; }
    rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
    caixa(ctx, x, y, w, h, fundo, sh, r = 10, bw = 4) {
      ctx.fillStyle = C.ink; this.rr(ctx, x + sh, y + sh, w, h, r); ctx.fill();
      ctx.fillStyle = fundo; this.rr(ctx, x, y, w, h, r); ctx.fill();
      ctx.lineWidth = bw; ctx.strokeStyle = C.ink; this.rr(ctx, x, y, w, h, r); ctx.stroke();
    }
    num(w, v) { const s = w.casas ? v.toFixed(w.casas).replace('.', ',') : Math.round(v).toLocaleString('pt-BR'); return (w.prefixo || '') + s + (w.sufixo || ''); }

    diagrama(ctx, card, maxW = 440) {
      const k = this.base + ':' + card.k + ':' + maxW; if (this._lay.has(k)) return this._lay.get(k);
      const B = BASES[this.base]; let px = B.px;
      ctx.font = this.fnt(px);
      const ws = card.words.map(w => ({w, s: this.tx(w.tx, B.maius)}));
      let sp = ctx.measureText(' ').width;
      ws.forEach(o => { o.l = ctx.measureText(o.s).width; });
      const linhas = []; let ln = [], lw = 0;
      ws.forEach(o => { const ext = o.l + (ln.length ? sp : 0); if (ln.length && lw + ext > maxW) { linhas.push({it: ln, w: lw}); ln = []; lw = 0; } ln.push(o); lw += ln.length > 1 ? o.l + sp : o.l; });
      if (ln.length) linhas.push({it: ln, w: lw});
      const lh = px * 1.28, total = linhas.length * lh;
      linhas.forEach((l, j) => { let x = -l.w / 2; l.it.forEach(o => { o.cx = x + o.l / 2; o.cy = -total / 2 + lh * (j + .5); x += o.l + sp; }); });
      const lay = {ws, linhas, total, largura: Math.max(...linhas.map(l => l.w)), px};
      this._lay.set(k, lay); return lay;
    }

    momentoEm(t) { return this.momentos.find(m => t >= m.t0 && t < m.t1); }

    desenha(ctx, t, info = {}) {
      const i = info.receita ?? -1, L = {...lugar(i, info.lt ?? 0)};
      if (info.ocupa) L.ocupa = (L.ocupa || []).concat(info.ocupa);
      if (L.oculta) return;
      const m = this.momentoEm(t);
      if (m) {
        let tipo = this.drama === 'auto' ? m.preset : this.drama;
        if (tipo === 'sozinha' && !LIMPA.has(i)) tipo = 'golpe';   // apagar o quadro por cima de um gráfico é conflito
        if (tipo === 'contador' && !m.palavras.some(w => w.valor != null)) tipo = 'golpe';
        const alto = {golpe: m.palavras.length * 104, etiqueta: 96, contador: 230, sozinha: 140, sublinhado: 0}[tipo];
        if (tipo !== 'sublinhado') {
          const y = tipo === 'sozinha' ? 470 : resolve(L, info.face, alto, 500, 14);
          if (y != null) this.desenhaDrama(ctx, t, m, tipo, y);
          return;
        }
      }
      const card = this.cards.find(c => t >= c.t0 && t < c.t1); if (!card) return;
      const lay = this.diagrama(ctx, card, L.maxW || 440), y = resolve(L, info.face, lay.total + 14, lay.largura + 28);
      if (y != null) this.desenhaBase(ctx, t, card, y, m, L);
    }

    /* A BASE: entra o bloco inteiro de uma vez, sobe 6px e ganha opacidade em
       0,18s; sai em 0,1s. Nenhuma palavra pula. A falada vai a 100%, as outras
       ficam a 70% — é o único "karaokê", e é quase subliminar. */
    desenhaBase(ctx, t, card, y, m, L = {}) {
      const lay = this.diagrama(ctx, card, L.maxW || 440), B = BASES[this.base];
      const pe = suave((t - card.t0) / .18), ps = suave((card.t1 - t) / .1), a = Math.min(pe, ps);
      if (a <= 0) return;
      ctx.save(); ctx.translate(L.x ?? 270, y + 6 * (1 - pe)); ctx.globalAlpha = a;
      ctx.font = this.fnt(lay.px); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      if (this.base === 'faixa') {
        ctx.fillStyle = 'rgba(11,13,18,.58)'; this.rr(ctx, -lay.largura / 2 - 14, -lay.total / 2 - 7, lay.largura + 28, lay.total + 14, 9); ctx.fill();
      }
      const sub = m && (this.drama === 'auto' ? m.preset : this.drama) === 'sublinhado' ? m : null;
      lay.ws.forEach(o => {
        const dita = t >= o.w.t0 - .02, destaque = sub && sub.palavras.includes(o.w);
        ctx.save(); ctx.globalAlpha *= dita ? 1 : .7;
        if (destaque) {
          // o drama mais leve: a palavra cresce um pouco, fica amarela e ganha
          // um sublinhado que se desenha — o resto da legenda nem se mexe
          const p = suave((t - sub.t0) / .25);
          ctx.translate(o.cx, o.cy); ctx.scale(1 + .14 * p, 1 + .14 * p);
          const u = o.l * expo((t - sub.t0 - .05) / .35);
          ctx.fillStyle = C.ink; ctx.fillRect(-o.l / 2 + 2, lay.px * .52 + 2, u, 6); ctx.fillStyle = C.mk; ctx.fillRect(-o.l / 2, lay.px * .5, u, 5);
          this.pintaBase(ctx, o.s, 0, 0, C.mk);
        } else this.pintaBase(ctx, o.s, o.cx, o.cy, C.br);
        ctx.restore();
      });
      ctx.restore();
    }
    pintaBase(ctx, s, x, y, cor) {
      if (this.base === 'contorno') { ctx.lineJoin = 'round'; ctx.lineWidth = 5; ctx.strokeStyle = '#000'; ctx.strokeText(s, x, y); }
      else if (this.base === 'suave') { ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 2; }
      ctx.fillStyle = cor; ctx.fillText(s, x, y); ctx.shadowColor = 'transparent';
    }

    /* O DRAMA. Cada preset é uma forma de parar o olho — e todos saem rápido. */
    desenhaDrama(ctx, t, m, tipo, yc) {
      const lt = t - m.t0, sai = suave((m.t1 - t) / .14);
      const pal = m.palavras, frase = pal.map(w => this.tx(w.tx, true)).join(' ');
      const num = pal.find(w => w.valor != null);
      ctx.save(); ctx.globalAlpha = sai; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      if (tipo === 'golpe') {
        // as palavras batem uma a uma, grandes, com tranco
        const y0 = yc;
        const visiveis = pal.filter(w => t >= w.t0 - .04);
        visiveis.forEach((w, j) => {
          const p = Math.min(1, (t - w.t0 + .04) / .16), e = 1 - Math.pow(1 - p, 4);
          const s = this.tx(w.tx, true); let px = 104; ctx.font = `700 ${px}px "Space Grotesk"`; const l = ctx.measureText(s).width; if (l > 500) { px *= 500 / l; ctx.font = `700 ${px}px "Space Grotesk"`; }
          const tr = t - w.t0 < .28 ? Math.sin(t * 80) * 5 * (1 - (t - w.t0) / .28) : 0;
          ctx.save(); ctx.translate(270 + tr, y0 + (j - (pal.length - 1) / 2) * px * 1.02); ctx.scale(1.5 - .5 * e, 1.5 - .5 * e); ctx.globalAlpha *= Math.min(1, p * 3);
          ctx.fillStyle = C.ink; ctx.fillText(s, 7, 8); ctx.fillStyle = j === pal.length - 1 ? C.mk : C.br; ctx.fillText(s, 0, 0); ctx.restore();
        });
      } else if (tipo === 'etiqueta') {
        const p = mola(Math.min(1, lt / .3));
        ctx.font = '700 58px "Space Grotesk"'; let l = ctx.measureText(frase).width, px = 58; if (l > 460) { px *= 460 / l; ctx.font = `700 ${px}px "Space Grotesk"`; l = 460; }
        ctx.save(); ctx.translate(270, yc); ctx.rotate(-.045); ctx.scale(p, p);
        this.caixa(ctx, -l / 2 - 22, -px * .72, l + 44, px * 1.44, C.mk, 9, 10, 5);
        ctx.fillStyle = C.ink; ctx.fillText(frase, 0, 3); ctx.restore();
      } else if (tipo === 'sozinha') {
        // o resto do quadro apaga; a palavra fica sozinha no meio
        const p = suave(lt / .2);
        ctx.fillStyle = `rgba(11,13,18,${.62 * p * sai})`; ctx.fillRect(0, 0, 540, 960);
        let px = 132; ctx.font = `700 ${px}px "Space Grotesk"`; let l = ctx.measureText(frase).width; if (l > 480) { px *= 480 / l; ctx.font = `700 ${px}px "Space Grotesk"`; l = 480; }
        const e = expo(lt / .45);
        ctx.save(); ctx.translate(270, 470); ctx.scale(.84 + .16 * e, .84 + .16 * e);
        ctx.fillStyle = C.mk; ctx.fillRect(-l / 2 - 12, -px * .5, (l + 24) * expo((lt - .12) / .3), px * 1.02);
        ctx.fillStyle = C.br; ctx.fillText(frase, 0, 4);
        ctx.globalCompositeOperation = 'source-atop'; ctx.fillStyle = C.ink; ctx.fillRect(-l / 2 - 12, -px * .5, (l + 24) * expo((lt - .12) / .3), px * 1.02);
        ctx.restore();
      } else if (tipo === 'contador' && num) {
        const v = num.valor * expo(lt / .6), s = this.num(num, v);
        let px = 150; ctx.font = `700 ${px}px "Space Grotesk"`; const l = ctx.measureText(s).width; if (l > 500) { px *= 500 / l; ctx.font = `700 ${px}px "Space Grotesk"`; }
        const p = mola(Math.min(1, lt / .25)); ctx.save(); ctx.translate(270, yc - 30); ctx.scale(.7 + .3 * p, .7 + .3 * p);
        ctx.fillStyle = C.ink; ctx.fillText(s, 9, 10); ctx.fillStyle = C.br; ctx.fillText(s, 0, 0); ctx.restore();
        const resto = pal.filter(w => w !== num).map(w => this.tx(w.tx, true)).join(' ');
        if (resto) { ctx.font = '700 30px "IBM Plex Mono"'; const lw = ctx.measureText(resto).width; this.caixa(ctx, 270 - lw / 2 - 14, yc + 70 - 24, lw + 28, 48, C.mk, 5, 7, 3); ctx.fillStyle = C.ink; ctx.fillText(resto, 270, yc + 72); }
      }
      ctx.restore();
    }
  }

  Legendas.tempos = async function (url, texto) {
    const ab = await (await fetch(url)).arrayBuffer();
    const buf = await new OfflineAudioContext(1, 1, 44100).decodeAudioData(ab);
    const d = buf.getChannelData(0), sr = buf.sampleRate, passo = Math.round(sr * .01), rms = [];
    for (let i = 0; i < d.length; i += passo) { let s = 0; for (let j = i; j < Math.min(d.length, i + passo); j++) s += d[j] * d[j]; rms.push(Math.sqrt(s / passo)); }
    const ord = [...rms].sort((a, b) => a - b), lim = Math.max(.008, (ord[Math.floor(ord.length * .9)] || .1) * .16);
    let seg = [], ini = null;
    rms.forEach((v, i) => { if (v > lim && ini === null) ini = i; if (v <= lim && ini !== null) { seg.push([ini, i]); ini = null; } });
    if (ini !== null) seg.push([ini, rms.length]);
    const j = []; seg.forEach(s => { const u = j[j.length - 1]; if (u && s[0] - u[1] < 14) u[1] = s[1]; else j.push([...s]); });
    seg = j.filter(s => s[1] - s[0] > 8).map(s => [s[0] / 100, s[1] / 100]); if (!seg.length) seg = [[0, buf.duration]];
    const pal = texto.trim().split(/\s+/).filter(Boolean), peso = pal.map(p => Math.max(1, (p.match(/[aeiouáéíóúâêôãõà]/gi) || []).length) + .4);
    const tot = peso.reduce((a, b) => a + b, 0), fala = seg.reduce((a, s) => a + s[1] - s[0], 0);
    const em = x => { for (const s of seg) { const l = s[1] - s[0]; if (x <= l) return s[0] + x; x -= l; } return seg[seg.length - 1][1]; };
    let acc = 0;
    return pal.map((tx, i) => { const a = acc / tot * fala; acc += peso[i]; return {tx, t0: em(a + .001), t1: em(acc / tot * fala - .001)}; });
  };

  /* sem IA: o número mais alto vira o drama "contador" */
  Legendas.regras = function (ws) {
    ws.forEach(w => {
      const m = w.tx.match(/^(R\$)?(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d+))?(%|h|k)?[,.!?]?$/i);
      if (m) { w.valor = parseFloat(m[2].replace(/\./g, '') + (m[3] ? '.' + m[3] : '')); w.casas = m[3] ? m[3].length : 0; w.prefixo = m[1] ? 'R$ ' : ''; w.sufixo = m[4] || ''; }
    });
    const nums = ws.map((w, i) => [w, i]).filter(([w]) => w.valor != null).sort((a, b) => b[0].valor - a[0].valor);
    return nums.length ? [{i: nums[0][1], n: Math.min(3, ws.length - nums[0][1]), preset: 'contador', porque: 'o maior número dito'}] : [];
  };

  Legendas.marcaIA = async function (ws) {
    const lista = ws.map((w, i) => i + ':' + w.tx).join(' ');
    const sys = 'Você edita legenda de vídeo curto (reels/VSL) em português. A legenda é DISCRETA o vídeo inteiro e só se sobressai nos momentos dramáticos. ' +
      'Escolha os momentos dramáticos: a frase curta (1 a 3 palavras) que vira o argumento, o número que choca, a promessa, a quebra de crença. ' +
      'No máximo 1 momento a cada 15 palavras e 3 no total. Nunca marque conectivo, artigo ou a frase inteira. ' +
      'Para cada um, sugira o preset: "golpe" (palavras grandes batendo, pra frase de impacto), "etiqueta" (bloco amarelo com borda, pra nome/promessa/benefício), ' +
      '"sublinhado" (o mais leve: a palavra fica amarela e sublinhada na própria legenda, pra ênfase que não pede pausa), ' +
      '"sozinha" (o quadro escurece e a palavra fica sozinha no centro, pra a frase mais forte do vídeo, no máximo 1), ' +
      '"contador" (só se houver número: o número sobe grande). Se houver número, inclua valor numérico, prefixo ("R$ ") e sufixo ("%", "h", " mil"). ' +
      'Responda SÓ com JSON: {"momentos":[{"i":0,"n":2,"preset":"golpe","porque":"...","numero":{"i":3,"valor":4,"prefixo":"","sufixo":""}}]}.';
    const r = await window.claude.complete({system: sys, max_tokens: 1200, messages: [{role: 'user', content: lista}]});
    const j = JSON.parse((r.match(/\{[\s\S]*\}/) || ['{}'])[0]);
    return (j.momentos || []).slice(0, 3).map(m => {
      if (m.numero && ws[m.numero.i]) Object.assign(ws[m.numero.i], {valor: +m.numero.valor, prefixo: m.numero.prefixo || '', sufixo: m.numero.sufixo || '', casas: (String(m.numero.valor).split('.')[1] || '').length});
      return {i: m.i, n: Math.max(1, Math.min(3, m.n || 1)), preset: DRAMAS.includes(m.preset) ? m.preset : 'golpe', porque: m.porque || ''};
    });
  };

  Legendas.resolve = resolve;
  Legendas.DRAMAS = DRAMAS; Legendas.BASES = Object.keys(BASES); Legendas.lugar = lugar;
  window.Legendas = Legendas;
})();
