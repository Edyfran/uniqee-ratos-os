"""Storyboard de overlays de um vídeo da fábrica, pro dono revisar ANTES de aprovar o render (dono, 16/10: "daqui pra frente
vc vai me gerar um storyboard com todos os overlays antes de renderizar qualquer coisa").

Cada peça do plano vira uma linha numerada: tempo no final, bloco, peça, o conteúdo, o que ele fala naquele instante (do .srt)
e o quadro do vídeo no meio da peça. Sai o `revisao.html` (a página única) e um .md, pra ele responder "nº 12: troca X".

    python storyboard.py <plano.json> <video.mp4> <saida_dir> [--srt legenda.srt]
    python storyboard.py --rascunho <plano.json> <saida_dir> [--srt legenda.srt]
    python storyboard.py --rascunho --animada <plano.json> <saida_dir> [--srt legenda.srt]   # clipes com voz por linha e a peça animada por cima (06/11); o vídeo grande, na linha inteira (clipe de 1280 px)
    (a página que o dono abre é o revisao.html; `--celular` junta um storyboard.pdf, só pra quem está no celular)

Com `--rascunho` o vídeo e os cortes são os de `fabrica.py <plano.json> --rascunho` (`<trabalho>/rascunho/`).

O vídeo do celular (plano mínimo, um bruto só) tem outro caminho: `fabrica.py <plano.json> --storyboard` corta em
720 p, decide a legenda e chama `do_celular`, que grava `<slug>.storyboard/` ao lado do plano:

    decisoes.json    o que o render final desenha: a legenda em cards e as peças que o plano traz em `pecas`
                     ([{"peca": "g_contador", "q": {...}, "em": "palavra dita" ou segundos, "dur": 2.5}])
    revisao.html     a página única: um cartão por overlay, com os avisos de ritmo no topo
    storyboard.md    a mesma lista em texto (os testes leem)
    chaves.json      a chave de conteúdo de cada quadro e clipe: a rodada seguinte só refaz o item que mudou

No `revisao.html` cada cartão tem o clipe do trecho (360 px, com a voz), a peça da biblioteca tocando por cima dele no
navegador (iframe de `tools/v2`, sem render), Manter, Talvez ou Tirar e uma nota. Abre com dois cliques, sem servidor.
"Copiar revisão" põe no clipboard uma linha por item marcado ("4 tirar", "7 talvez: entra mais cedo").

Quem aplica a revisão mexe no `decisoes.json` pelo número, e o render final o lê no lugar de decidir de novo:

    python storyboard.py --aplica <slug>.storyboard "<texto colado>"   # ou arquivo, ou - (entrada): tira e troca o texto;
                                                                       # imprime só o que precisa de decisão (talvez, notas)
    python storyboard.py --tira <slug>.storyboard 4
    python storyboard.py --texto <slug>.storyboard 7 "o texto novo"   # numa peça, troca o texto principal dela

Depois `fabrica.py <plano.json> --storyboard` de novo mostra o corrigido (os números não mudam), e sem a flag renderiza.
O `--storyboard` termina numa linha: "storyboard: N peças · N avisos · revisão em <caminho>".

O plano é o da fábrica (`blocos` com `nome`; cada bloco tem `<pasta>/<plano>.json` com `brolls` e
`trabalho-<x>/<nome>/corte.mp4`). Sem render: o tempo vem da duração dos cortes; o quadro, do vídeo que já existe
(prévia ou render anterior). Com o render novo ainda por fazer, a coluna do quadro mostra o anterior — o texto da linha
é o que vale.
"""
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

import checks
import ff


def _dur(p: Path) -> float:
    try:
        return ff.dur(p)
    except Exception:
        return 0.0


def _conteudo(q: dict, raiz: str) -> str:
    for k in ("txt", "l", "termo", "it", "itens", "nome", "pt", "hd", "kick", "rot", "url", "img"):
        v = q.get(k)
        if v:
            v = str(v).replace(raiz, "")
            v = re.sub(r"@\d+(\.\d+)?", "", v)          # tempos de batida do k_frase
            v = v.split("/")[-1] if v.startswith(("/", "@/")) else v
            # a 2ª linha da peça (kick do k_frase, def do r_termo, sub da tarja) — é ela que o dono costuma cortar
            extra = "".join(f" · {q[x]}" for x in ("kick", "def", "sub") if x != k and q.get(x))
            carta = Path(str(q["img"])).stem + ": " if k != "img" and q.get("img") else ""
            return " ".join((carta + v + extra).split())[:140]
    return ""


def _srt(p: Path | None) -> list[tuple[float, float, str]]:
    if not p or not p.exists():
        return []
    ts = lambda s: sum(float(x) * m for x, m in zip(s.replace(",", ".").split(":"), (3600, 60, 1)))
    out = []
    for bl in p.read_text(encoding="utf-8").split("\n\n"):
        ls = bl.strip().splitlines()
        if len(ls) >= 3 and "-->" in ls[1]:
            a, b = ls[1].split(" --> ")
            out.append((ts(a), ts(b), " ".join(ls[2:])))
    return out


def _abre(plano) -> tuple[dict, Path, str]:
    """(documento, pasta, nome) do plano, que vem como arquivo ou, já lido pela fábrica, como dict com `_dir`."""
    if isinstance(plano, dict):
        return plano, Path(plano.get("_dir", ".")), plano.get("slug", "plano")
    return json.loads(plano.read_text(encoding="utf-8")), plano.parent, plano.stem


def _trab(plano, rascunho: bool = False) -> Path:
    doc, pasta, nome = _abre(plano)
    trab = Path(doc.get("trabalho") or pasta / f"trabalho-{nome}")
    trab = trab if trab.is_absolute() else pasta / trab
    return trab / "rascunho" if rascunho else trab


def _corte(trab: Path, nome: str) -> Path:
    """O corte do bloco: o do render, ou o do rascunho (`trecho.mp4`, sem peça)."""
    c = trab / nome / "corte.mp4"
    return c if c.exists() else trab / nome / "trecho.mp4"


def _dur_bloco(trab: Path, b: dict) -> float:
    """Quanto o bloco dura no vídeo: o corte (ou trecho) dele, senão a soma das janelas do plano. Sem nenhum dos dois o
    tempo de tudo que vem depois sai errado — por isso avisa (19/10: storyboard com tudo fora de ordem)."""
    c = _corte(trab, b["nome"])
    if c.exists():
        return _dur(c)
    j = b.get("janelas") or []
    if j:
        return sum(e - a for a, e in j)
    print(f"aviso: bloco {b['nome']} sem corte nem janelas em {trab}", file=sys.stderr)
    return 0.0


def linhas(plano, rascunho: bool = False, cortes: Path | None = None) -> list[dict]:
    doc, pasta, _ = _abre(plano)
    trab = cortes or _trab(plano, rascunho)
    t, out = 0.0, []
    for b in doc["blocos"]:
        p = pasta / b["plano"] if b.get("plano") else None
        if p and p.exists():
            for x in json.loads(p.read_text(encoding="utf-8")).get("brolls", []):
                q = x.get("q", {})
                out.append({"t0": t + x["t0"], "t1": t + x["t1"], "bloco": b["nome"], "peca": x.get("peca", "?"),
                            "conteudo": _conteudo(q, str(pasta)) + (" · no canto direito de cima" if x.get("peca") == "g_contador" and x.get("x") else ""), "_q": q, "ar": x.get("ar"), "_tema": x.get("tema") or _tema_do_estilo(doc), "pede": x.get("pede"), "_dx": x.get("x") or 0})
        t += _dur_bloco(trab, b)
    return sorted(out, key=lambda r: r["t0"])


def _soma_cortes(plano, rascunho: bool = False, cortes: Path | None = None) -> float:
    doc = _abre(plano)[0]
    trab = cortes or _trab(plano, rascunho)
    return sum(_dur_bloco(trab, b) for b in doc["blocos"])


def no_video(plano, dv: float, cortes: Path | None = None) -> list[dict]:
    """As peças do plano no tempo de um vídeo já renderizado de `dv` s, cada uma com `m`, o instante em que o
    storyboard a fotografa (`_instante`). O render come uns décimos por emenda: a soma dos cortes é escalada pro vídeo."""
    ls, soma = linhas(plano, False, cortes), _soma_cortes(plano, False, cortes)
    fator = dv / soma if soma else 1.0
    for r in ls:
        r["t0"], r["t1"] = r["t0"] * fator, r["t1"] * fator
        r["m"] = r["t0"] + _instante(r)
    return ls


def fmt_s(s: float) -> str:
    return f"{s:.1f}".replace(".", ",")


def fmt(s: float) -> str:
    s = round(s, 1)   # 59,97 virava "0:60.0"
    return f"{int(s // 60)}:{s % 60:04.1f}"


AR_VERTICAL = "1080x1920"   # o tamanho em que a biblioteca desenha a peça do vídeo do celular


def _tema_do_estilo(doc: dict) -> str | None:
    """O tema que a fábrica usa na peça sem tema próprio (fabrica._peca: e.eixos["desenho"]["tema"]).
    Sem ele a peça sai no tema padrão da biblioteca, não no do canal (dono, 19/10: "ta sem o estilo do canal")."""
    try:
        import estilo as es
        return es.estilo(doc["estilo"]).eixos["desenho"]["tema"]
    except Exception:  # noqa: BLE001
        return None


def _instante(r: dict) -> float:
    """Segundos depois do t0 em que o quadro de fundo e a peça são fotografados: ~55% da duração, no máximo 3 s.
    Os dois no mesmo instante; antes o fundo saía no meio e a peça em 3 s, e o placar de 42 s mostrava outro valor."""
    return min(max(0.3, (r["t1"] - r["t0"]) * 0.55), 3.0)


def _sobrepoe(r: dict, quadro: Path, larg: int = 960) -> None:
    """Põe a peça `r` (parada no `_instante`) por cima do `quadro`, que sai com `larg` px. Falha de peça vira aviso no quadro, não erro."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v2"))
    import v2
    from PIL import Image, ImageDraw
    w, h = (int(x) for x in str(r.get("ar") or "1920x1080").split("x"))
    png = quadro.with_suffix(".peca.png")
    q = r.get("_q", {})
    t = _instante(r)
    try:
        v2.quadro(r["peca"], [f"{k}={v}" for k, v in q.items()], png, tema=r.get("_tema"), t=t, tam=(w, h), alfa=True)
        base = Image.open(quadro).convert("RGBA").resize((w, h))
        peca = Image.open(png).convert("RGBA").resize((w, h))
        if r.get("_dx"):   # o render desloca a camada a partir do centro (`x` do b-roll, em px de um quadro de 1080): o placar do longo no canto
            fundo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            fundo.paste(peca, (int(r["_dx"] * w / 1080), 0))   # k = largura / W_REF, como o render
            peca = fundo
        base.alpha_composite(peca)
        base.convert("RGB").resize((larg, round(larg * h / w))).save(quadro, quality=88)
    except (Exception, SystemExit) as e:  # noqa: BLE001  (o v2.quadro recusa peça desconhecida com sys.exit)
        img = Image.open(quadro).convert("RGB")
        ImageDraw.Draw(img).text((12, 12), f"peça não fotografou: {e}"[:90], fill=(255, 80, 80))
        img.save(quadro)
    png.unlink(missing_ok=True)


def _notas(plano: dict) -> list[str]:
    """As notas do dono (`checks.antes`, com as do projeto) que o plano descumpre: vão no topo do storyboard."""
    return [f"NOTA {r.id}: {r.mediu} — {r.nota}" for r in checks.antes(plano) if r.ok is False]


def _escreve(ls: list[dict], saida: Path, avisos: list[str] = (), notas: list[str] = ()) -> None:
    """O `storyboard.md` (o que os testes leem) de linhas já com quadro (`q`) e fala. `notas`: as notas do dono que o plano
    descumpre, no topo. `avisos`: frases no fim (o ritmo contra o que o aluno pediu). A página é uma só, o `revisao.html`
    (`_revisao`), e leva os mesmos avisos e notas."""
    # duas peças na tela ao mesmo tempo: o dono reprovou carta por cima de lista e tarja por cima de tarja (20/10)
    for r in ls:
        # a legenda corre por baixo de toda peça: só peça com peça é defeito
        r["sobre"] = [o["n"] for o in checks.sobre(r, ls)]
        if r["sobre"]:
            r["conteudo"] += f"  ⚠ junto com nº {', '.join(map(str, r['sobre']))}"
    for r in ls:       # a fala da seguinte cortou a peça abaixo do tempo de ler: o dono escolhe segurar ou enxugar o texto
        if r.get("pede"):
            r["conteudo"] += f"  ⚠ {fmt_s(r['t1'] - r['t0'])} s; pede {fmt_s(r['pede'])} s"
    md = [f"⚠ {a}\n" for a in notas] + ["| nº | tempo | bloco | peça | conteúdo | ele fala |", "|---|---|---|---|---|---|"]
    md += [f"| {r['n']} | {fmt(r['t0'])}–{fmt(r['t1'])} | {r['bloco']} | {r['peca']} | {r['conteudo']} | {r['fala']} |" for r in ls]
    md += [f"\n⚠ {a}" for a in avisos]
    (saida / "storyboard.md").write_text("\n".join(md) + "\n", encoding="utf-8")


# ── A página de revisão: Manter, Talvez ou Tirar em cada item, e o texto pronto pra colar no chat ───────────────
# O dono pediu no estilo da revisão do millee (29/10). Só a mecânica é parecida: aqui é uma página estática, sem Artifact
# nem servidor, porque o aluno roda no Claude Code ou no Codex, no Windows, no Mac ou no Linux.

PAGINA = r"""<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>Revisão — @@NOME@@</title>
<style>
:root{--ink:#0B0D12;--mut:#3B3F4A;--ac:#0640fb;--ac2:#DCE4FF;--mk:#F2C744;--ok:#17A354;--no:#E1432F;--no2:#FFE0D9}
*{box-sizing:border-box}
body{margin:0;font:17px/1.4 'Space Grotesk',system-ui,sans-serif;color:var(--ink);background:#fff;
  background-image:radial-gradient(circle,rgba(11,13,18,.10) 2px,transparent 2.6px);background-size:36px 36px}
.w{max-width:1000px;margin:0 auto;padding:12px 12px 40px}
h1{margin:6px 0;font-size:28px;line-height:1.1;letter-spacing:-.03em}
h2{margin:0 0 10px;font-size:22px}
.sub{margin:0 0 14px;color:var(--mut)}
button{font:inherit;font-weight:700;color:var(--ink);background:#fff;border:3px solid var(--ink);padding:8px 14px;min-height:46px;cursor:pointer}
button:focus-visible,textarea:focus-visible{outline:3px solid var(--ac);outline-offset:2px}
.barra{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;justify-content:space-between;
  background:#fff;border:3px solid var(--ink);box-shadow:4px 4px 0 var(--ink);padding:6px 6px 6px 12px;margin:0 6px 18px 0}
.barra button[aria-pressed=true]{background:var(--ink);color:#fff}
#feitos{background:var(--mk);padding:0 6px}
.c{display:grid;grid-template-columns:minmax(0,360px) 1fr;gap:14px;align-items:start;background:#fff;
  border:3px solid var(--ink);box-shadow:6px 6px 0 var(--ink);padding:12px;margin:0 6px 22px 0}
.c[data-m=manter]{box-shadow:6px 6px 0 var(--ok)}
.c[data-m=talvez]{box-shadow:6px 6px 0 var(--mk)}
.c[data-m=tirar]{box-shadow:6px 6px 0 var(--no);background:var(--no2)}
body.faltam .c[data-m]{display:none}
.pl{position:relative;overflow:hidden;line-height:0;background:#000;border:3px solid var(--ink)}
.pl video,.pl img{width:100%;display:block}
.pl img{display:none}
.pl.falhou video{display:none}
.pl.falhou img,.pl.so img{display:block}
.pl iframe{position:absolute;left:0;top:0;border:0;transform-origin:0 0;pointer-events:none;background:transparent}
.pl:fullscreen{border:0}
.pl:fullscreen video,.pl:fullscreen img{height:100%;object-fit:contain}
.pl video::-webkit-media-controls-fullscreen-button{display:none}
.fs{min-height:36px;padding:0 10px;font-size:15px}
.g.w{max-width:1280px}
.g .c{grid-template-columns:minmax(0,1fr)}
.g .pl{max-width:min(1200px,calc(88vh*var(--ar)))}
.g .tb{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,420px);gap:0 18px;align-items:start}
.av{margin:6px 0 0;padding:4px 8px;background:#FFF1C9;border-left:5px solid var(--mk);font-size:15px;font-weight:700}
.nota{margin:0 0 8px;padding:6px 10px;background:var(--no2);border-left:5px solid var(--no);font-weight:700}
.avisos{margin:0 6px 18px 0}
.cab{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.n{background:var(--ac);color:#fff;font-size:24px;padding:0 10px}
.t{font-weight:700;font-variant-numeric:tabular-nums}
.p{background:var(--ac2);padding:1px 6px;font-size:15px}
.ct{margin:8px 0 4px;font-weight:700}
.fala{margin:4px 0 12px;color:var(--mut);font-size:15px}
.bt{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 10px}
.bt button[aria-pressed=true][data-v=manter]{background:var(--ok);color:#fff}
.bt button[aria-pressed=true][data-v=talvez]{background:var(--mk)}
.bt button[aria-pressed=true][data-v=tirar]{background:var(--no);color:#fff}
textarea{width:100%;min-height:64px;font:inherit;font-size:16px;color:var(--ink);background:#fff;border:3px solid var(--ink);padding:8px;resize:vertical}
.fim{background:var(--ac2);border:3px solid var(--ink);box-shadow:6px 6px 0 var(--ink);padding:16px;margin:30px 6px 0 0}
#copia{background:var(--ac);color:#fff;font-size:18px;box-shadow:4px 4px 0 var(--ink)}
#saida{min-height:210px;margin-top:12px;font-size:14px}
@media(max-width:700px){.c{grid-template-columns:1fr}}
@media(max-width:900px){.g .tb{grid-template-columns:minmax(0,1fr)}}
</style>
<div class="w @@MODO@@">
<h1>Revisão do storyboard</h1>
<p class="sub"><b>@@NOME@@</b> · @@N@@ itens. Dê play no vídeo: a peça aparece por cima no instante dela. <b>Manter</b> deixa como está, <b>Talvez</b> muda pela nota, <b>Tirar</b> corta a peça.</p>
@@AVISOS@@
<div class="barra"><span><b id="feitos">0</b> de @@N@@ revisados</span><button type="button" id="faltam" aria-pressed="false">Só os que faltam</button></div>
@@CARTOES@@
<section class="fim"><h2>Terminou?</h2><button type="button" id="copia">Copiar revisão</button>
<p id="status" aria-live="polite"></p><textarea id="saida" readonly hidden aria-label="Texto da revisão"></textarea>
<p>Cole no Claude e ele aplica. Nada é renderizado antes disso.</p></section>
</div>
<script>
(() => {
  const M = @@MOLDE@@;
  const $ = (id) => document.getElementById(id);
  const cs = [...document.querySelectorAll(".c")];
  // A peça da biblioteca toca por cima do clipe, sem render: um iframe com o HTML dela (?vivo=1: a timeline toca sozinha, uma vez),
  // fundo transparente (?alfa=1), na escala do clipe. Nasce quando o clipe chega no instante dela. file:// não deixa a página
  // mexer no iframe, então sincronizar é recriá-lo: ao pausar ou pular, ele sai. Se falhar, o cartão mostra o quadro parado.
  document.querySelectorAll(".pl[data-src]").forEach((pl) => {
    const v = pl.querySelector("video"), W = +pl.dataset.w, H = +pl.dataset.h, ini = Math.max(0, +pl.dataset.off - 0.25);
    let f = null, feito = false, id = 0;
    const cabe = () => {      // a peça acompanha o vídeo: mesma escala e, em tela cheia (o vídeo fica contido), o mesmo recuo
      if (!f) return;
      const cw = pl.clientWidth, ch = pl.clientHeight, s = Math.min(cw / W, ch / H);
      f.style.transform = "translate(" + (cw - W * s) / 2 + "px," + (ch - H * s) / 2 + "px) scale(" + s + ")";
    };
    const tira = () => { if (f) { f.remove(); f = null; } };
    const falha = () => { tira(); clearInterval(id); pl.classList.add("falhou"); };
    const poe = () => {
      f = document.createElement("iframe");
      f.width = W; f.height = H; f.tabIndex = -1; f.setAttribute("aria-hidden", "true"); f.setAttribute("allowtransparency", "true");
      f.onerror = falha; f.src = pl.dataset.src; pl.appendChild(f); cabe();
    };
    const tic = () => {
      const t = v.currentTime;
      if (t < ini - 0.05) feito = false;
      else if (!feito && t >= ini) { feito = true; poe(); }
    };
    const solta = () => { clearInterval(id); id = 0; tira(); feito = v.currentTime > ini + 0.4; };   // já passou do começo: a peça não entra no meio
    v.addEventListener("play", () => { if (!id) id = setInterval(tic, 40); tic(); });
    ["pause", "ended", "seeking"].forEach((e) => v.addEventListener(e, solta));
    new ResizeObserver(cabe).observe(pl);      // janela, layout ou tela cheia mudaram o tamanho do vídeo
  });
  // Tela cheia é do contêiner (vídeo + peça): a do <video> levaria só o vídeo, sem a peça (que é uma camada da página).
  document.querySelectorAll(".fs").forEach((b) => {
    if (!document.fullscreenEnabled) { b.hidden = true; return; }
    b.onclick = () => document.fullscreenElement ? document.exitFullscreen() : b.closest(".c").querySelector(".pl").requestFullscreen();
  });
  let est = {};
  try { est = JSON.parse(localStorage.getItem(M.chave) || "{}"); } catch (e) {}   // sem localStorage a página funciona, só não lembra
  const guarda = () => { try { localStorage.setItem(M.chave, JSON.stringify(est)); } catch (e) {} };
  const de = (c) => est[c.dataset.n] || (est[c.dataset.n] = {});
  const pinta = (c) => {
    const v = de(c).v;
    if (v) c.dataset.m = v; else delete c.dataset.m;
    c.querySelectorAll("[data-v]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
  };
  const conta = () => { $("feitos").textContent = cs.filter((c) => c.dataset.m).length; };
  const muda = (c) => { guarda(); pinta(c); conta(); };
  cs.forEach((c) => {
    const ta = c.querySelector("textarea");
    ta.value = de(c).nota || "";
    c.querySelectorAll("[data-v]").forEach((b) => { b.onclick = () => { de(c).v = de(c).v === b.dataset.v ? "" : b.dataset.v; muda(c); }; });
    ta.oninput = () => { de(c).nota = ta.value; if (!de(c).v && ta.value.trim()) de(c).v = "talvez"; muda(c); };   // nota sem marca é um talvez
    pinta(c);
  });
  conta();
  $("faltam").onclick = (ev) => { ev.currentTarget.setAttribute("aria-pressed", String(document.body.classList.toggle("faltam"))); };
  const texto = () => [M.cab, ...cs.filter((c) => c.dataset.m).sort((a, b) => a.dataset.n - b.dataset.n).map((c) => {
    const nota = (de(c).nota || "").trim().replace(/\s+/g, " ");
    return c.dataset.n + " " + c.dataset.m + (nota ? ": " + nota : "");
  }), M.fim].join("\n");
  $("copia").onclick = async () => {
    if (!cs.some((c) => c.dataset.m)) { $("status").textContent = "Marque pelo menos um item."; return; }
    const t = texto(), out = $("saida");
    out.hidden = false; out.value = t;
    out.style.height = "auto"; out.style.height = out.scrollHeight + 6 + "px";      // o texto inteiro à vista, sem rolar dentro da caixa
    let ok = false;
    try { await navigator.clipboard.writeText(t); ok = true; }
    catch (e) {                                       // o file:// pode recusar a API: seleciona o texto e copia no braço
      out.focus(); out.select(); out.setSelectionRange(0, t.length);
      try { ok = document.execCommand("copy"); } catch (e2) {}
    }
    $("status").textContent = ok ? "Copiado. Cole no Claude." : "Não deu pra copiar sozinho: o texto está aí embaixo, selecione e copie.";
  };
})();
</script>
"""


def _chaves(saida: Path) -> dict:
    """O que já foi feito por item: `chaves.json` guarda, por número, a chave do conteúdo de cada quadro (`q`) e clipe (`c`)."""
    try:
        return json.loads((saida / "chaves.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _marca(ls: list[dict], video: Path | None, sal: str = "") -> None:
    """Dá a cada linha a chave do que a desenha: número, início, fim, peça, texto (com os parâmetros) e o vídeo de origem. Mudou
    um, mudou a chave; o resto das linhas fica como estava. Chamado antes do `_escreve`, que acrescenta avisos ao `conteudo`."""
    v = Path(video) if video else None
    id_v = [str(v), v.stat().st_size, int(v.stat().st_mtime)] if v and v.exists() else []
    for r in ls:
        dados = [r["n"], round(r["t0"], 3), round(r["t1"], 3), r["peca"], r["conteudo"], r.get("_q"), r.get("_tema"),
                 r.get("ar"), id_v, sal]
        r["_k"] = hashlib.sha1(json.dumps(dados, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _varre(pasta: Path, fica: set[str]) -> None:
    """Apaga o órfão: arquivo de `pasta` que nenhuma linha de agora pede."""
    for f in pasta.iterdir():
        if f.name not in fica:
            f.unlink(missing_ok=True)


def _janela(r: dict) -> tuple[float, float]:
    """A janela do clipe: a da peça com um respiro, no máximo 5 s. O instante da peça cai em `t0 - a0` s do começo do clipe."""
    a0 = max(0.0, r["t0"] - 0.3)
    return a0, min(max(r["t1"], r["t0"] + 1.0) + 0.4, a0 + 5.0)


SEM_VIVO = ("l_chamada",)   # com ?vivo=1 ela fica vazia, esperando o OBS: no clipe animado (viva) a peça vai queimada nele


def _queima(r: dict, arq: Path, a0: float, larg: int) -> None:
    """A peça que não toca por cima no navegador entra no próprio clipe: o v2 a renderiza em alfa (com o cache dele) e o ffmpeg a põe no instante dela."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v2"))
    import v2
    mov, com = arq.with_suffix(".peca.mov"), arq.with_suffix(".com.mp4")
    v2.render(r["peca"], [f"{k}={v}" for k, v in r["_q"].items()], mov, ar=str(r.get("ar") or "1920x1080"), tema=r.get("_tema"))
    ff.run(["ffmpeg", "-v", "error", "-y", "-i", arq, "-i", mov, "-filter_complex",
            f"[1:v]scale={larg}:-2,setpts=PTS+{r['t0'] - a0:.3f}/TB[p];[0:v][p]overlay=eof_action=pass[v]",
            "-map", "[v]", "-map", "0:a?", "-c:v", ff.CODEC_VIDEO, "-crf", "30", "-preset", "veryfast", "-pix_fmt", ff.PIX_FMT,
            "-c:a", "copy", "-movflags", "+faststart", com], quiet=True, check=False)
    mov.unlink(missing_ok=True)
    if com.exists():
        com.replace(arq)


def _larg(video: Path, grande: bool = False) -> int:
    """A largura do clipe: 360 px (celular em pé) ou 640 px. `grande` (a folha animada, com o vídeo na linha inteira do
    notebook): o clipe nasce do tamanho em que aparece, 720 px em pé e 1280 px na paisagem."""
    retrato = ff.probe(video).retrato
    return (720 if retrato else 1280) if grande else (360 if retrato else 640)


def _clipes(ls: list[dict], video: Path, saida: Path, viva: bool = False, grande: bool = False) -> None:
    """Um clipe leve de cada linha, cortado da prévia: `clipes/NNN.mp4`, H.264 com a voz, na largura de `_larg`.
    A janela é a da peça com um respiro (`_janela`); o som, que é um instante, ganha 1 s. Só refaz o clipe cuja chave
    mudou (`_marca`) ou que sumiu, e apaga os órfãos. O que o ffmpeg não cortar fica sem arquivo, e o cartão mostra o quadro.
    `viva`: o corte seco não traz peça; as que o navegador não toca (`SEM_VIVO`) vão queimadas no clipe."""
    (saida / "clipes").mkdir(exist_ok=True)
    ch = _chaves(saida)
    feitos = ch.setdefault("c", {})
    larg = _larg(video, grande)
    for r in ls:
        arq = saida / "clipes" / f"{r['n']:03d}.mp4"
        if feitos.get(str(r["n"])) == r["_k"] and arq.exists():
            continue
        feitos.pop(str(r["n"]), None)
        arq.unlink(missing_ok=True)
        a0, a1 = _janela(r)
        ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a0:.2f}", "-i", video, "-t", f"{a1 - a0:.2f}",
                "-vf", f"scale={larg}:-2", "-c:v", ff.CODEC_VIDEO, "-crf", "30", "-preset", "veryfast",
                "-pix_fmt", ff.PIX_FMT, "-c:a", ff.CODEC_AUDIO, "-b:a", "64k", "-ac", "1", "-movflags", "+faststart",
                arq], quiet=True, check=False)
        if viva and r["peca"] in SEM_VIVO and "_q" in r and arq.exists():
            _queima(r, arq, a0, larg)
        if arq.exists():
            feitos[str(r["n"])] = r["_k"]
    _varre(saida / "clipes", {f"{r['n']:03d}.mp4" for r in ls})
    ch["c"] = {k: v for k, v in feitos.items() if int(k) in {r["n"] for r in ls}}
    (saida / "chaves.json").write_text(json.dumps(ch), encoding="utf-8")


def _peca_viva(r: dict, saida: Path) -> str | None:
    """O endereço da peça pra tocar por cima do clipe: o HTML dela na biblioteca (`tools/v2`), por caminho relativo à pasta da
    revisão (a página abre por file://; em outro disco, o endereço file:// inteiro), com os parâmetros do plano e `alfa=1&vivo=1`. None quando não dá (peça sem arquivo,
    desconhecida ou deslocada pelo `x` do b-roll): o cartão fica com o quadro parado."""
    if "_q" not in r or r.get("_dx") or r["peca"] in SEM_VIVO:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v2"))
    try:
        import v2
        p, qv = v2.acha(r["peca"])
        arq = v2.AQUI / p["arquivo"]
        if not arq.exists():
            return None
        q = v2._query(qv, [f"{k}={v}" for k, v in r["_q"].items()],
                      {"ar": str(r.get("ar") or "1920x1080"), "tema": r.get("_tema"), "alfa": "1", "vivo": "1"})
    except (Exception, SystemExit):  # noqa: BLE001  (v2.acha sai com sys.exit na peça desconhecida)
        return None
    try:
        ref = urllib.parse.quote(os.path.relpath(arq, saida.resolve()).replace(os.sep, "/"))
    except ValueError:       # Windows: a pasta do aluno e a biblioteca em discos diferentes, sem caminho relativo
        ref = arq.resolve().as_uri()
    return ref + "?" + q


def _molde(nome: str, pasta: str | None, ls: list[dict]) -> dict:
    """O que a página escreve em volta das linhas marcadas, pro Claude saber o que fazer com elas. `chave` guarda a marcação
    no navegador (F5 não perde nada) e muda quando o storyboard muda: a rodada nova começa em branco. `pasta`: o
    `decisoes.json` existe (vídeo do celular) e o número de cada item é estável, então tirar é `--tira`."""
    chave = hashlib.sha1(json.dumps([[r["n"], r["peca"], r["conteudo"], round(r["t0"], 1)] for r in ls],
                                    ensure_ascii=False).encode()).hexdigest()[:8]
    if pasta:
        fim = (f'Aplique de uma vez: storyboard.py --aplica {pasta} "<as linhas acima, sem esta>" (ou - pra ler da entrada). '
               "Ele tira e troca o texto sozinho e lista só o que precisa de você (talvez e notas): resolva esses. "
               "Depois rode fabrica.py <plano> --storyboard pra eu conferir. Não renderize antes de eu aprovar.")
    else:
        fim = ("Aplique assim: tirar = tire essa peça do plano; talvez = ajuste pela nota; manter e o que não tem marca ficam "
               "como estão. Os números são os desta lista; gere o storyboard de novo pra eu conferir. Não renderize antes de eu aprovar.")
    return {"chave": f"revisao:{nome}:{chave}", "cab": f'Revisão do storyboard "{nome}":',
            "fim": fim}


def _revisao(ls: list[dict], saida: Path, video: Path | None, nome: str, avisos: list[str] = (), notas: list[str] = (),
             viva: bool = False, grande: bool = False) -> None:
    """O `revisao.html`, a única página do storyboard: um cartão por número, com o clipe do trecho, Manter, Talvez ou Tirar e
    uma nota. No topo vão as notas do dono e os avisos de ritmo; no cartão, o aviso do item (peça sobre peça, tempo de ler).
    Estática, abre com dois cliques e sem servidor. "Copiar revisão" põe no clipboard uma linha por item marcado
    ("4 tirar", "7 talvez: entra mais cedo") e o que fazer com elas. `viva`: o clipe não traz as peças (rascunho do celular),
    então cada peça toca por cima dele, no navegador (`_peca_viva`), e a tela cheia é do contêiner (vídeo + peça): o botão
    do próprio `<video>` levaria só o vídeo. Sem `video` (o corte seco não tem peça pra cortar) o cartão fica com o quadro,
    que já leva a peça por cima. `grande`: a folha animada, com o vídeo na linha inteira (até 1200 px) e o texto embaixo."""
    if video:
        _clipes(ls, video, saida, viva, grande)
    e = html.escape
    cartoes = []
    for r in ls:
        clipe = (saida / "clipes" / f"{r['n']:03d}.mp4").exists()
        src = _peca_viva(r, saida) if viva and clipe else None
        corpo, _, aviso = r["conteudo"].partition("  ⚠ ")
        w, h = (int(x) for x in str(r.get("ar") or "1920x1080").split("x"))
        tag = (f'<video controls{" controlslist=nofullscreen" if viva else ""} playsinline preload="none" '
               f'poster="{r["q"]}" src="clipes/{r["n"]:03d}.mp4"></video>')
        if src:
            a0, _a1 = _janela(r)
            midia = (f'<div class="pl" data-src="{e(src)}" data-w="{w}" data-h="{h}" data-off="{r["t0"] - a0:.2f}" '
                     f'style="--ar:{w / h:.4f}">{tag}<img src="{r["q"]}" alt=""></div>')
        elif clipe:
            midia = f'<div class="pl" style="--ar:{w / h:.4f}">{tag}</div>'
        else:
            midia = f'<div class="pl so" style="--ar:{w / h:.4f}"><img src="{r["q"]}" alt=""></div>'
        tela = '<button type="button" class="fs">Tela cheia</button>' if viva and clipe else ""
        cartoes.append(
            f'<article class="c" id="i{r["n"]}" data-n="{r["n"]}">{midia}'
            f'<div class="tb"><div class="tx"><div class="cab"><b class="n">{r["n"]}</b><span class="t">{fmt(r["t0"])}–{fmt(r["t1"])}</span>'
            f'<code class="p">{e(r["peca"])}</code>{tela}</div><p class="ct">{e(corpo)}</p>'
            + (f'<p class="av">⚠ {e(aviso)}</p>' if aviso else "")
            + (f'<p class="fala">“{e(r["fala"])}”</p>' if r["fala"] else "")
            + '</div><div class="dc"><div class="bt" role="group" aria-label="Sua decisão">'
            '<button type="button" data-v="manter" aria-pressed="false">Manter</button>'
            '<button type="button" data-v="talvez" aria-pressed="false">Talvez</button>'
            '<button type="button" data-v="tirar" aria-pressed="false">Tirar</button></div>'
            f'<textarea aria-label="Nota do item {r["n"]}" placeholder="Nota (opcional): o que mudar"></textarea></div></div></article>')
    topo = (f'<div class="avisos">' + "".join(f'<p class="nota">⚠ {e(a)}</p>' for a in notas)
            + "".join(f'<p class="av">⚠ {e(a)}</p>' for a in avisos) + "</div>") if (notas or avisos) else ""
    pasta = saida.name if (saida / "decisoes.json").exists() else None
    molde = json.dumps(_molde(nome, pasta, ls), ensure_ascii=False).replace("<", "\\u003c")     # nada fecha o <script>
    (saida / "revisao.html").write_text(
        PAGINA.replace("@@NOME@@", e(nome)).replace("@@N@@", str(len(ls))).replace("@@MOLDE@@", molde)
        .replace("@@MODO@@", "g" if grande else "").replace("@@AVISOS@@", topo).replace("@@CARTOES@@", "".join(cartoes)),
        encoding="utf-8")


# ── O vídeo do celular: as decisões num arquivo que o storyboard lê e o render respeita ─────────────────────────

def _pdf_celular(ls: list[dict], saida: Path, avisos: list[str] = (), notas: list[str] = ()) -> Path:
    """O `storyboard.pdf`, só pro dono que está no celular (o app Arquivos não abre o html): um cartão por número, com o
    quadro (q/NNN.jpg), tempo, peça, conteúdo e fala. No computador a página é o `revisao.html`; o PDF não substitui ela."""
    from html import escape as e
    topo = "".join(f"<p class=a>⚠ {e(a)}</p>" for a in [*notas, *avisos])
    cartoes = "".join(
        f"<div class=c><img src='q/{r['n']:03d}.jpg'><b>{r['n']}</b> {fmt(r['t0'])}–{fmt(r['t1'])} · {e(str(r['peca']))}<br>"
        f"{e(str(r['conteudo']))}<br><small>{e(str(r.get('fala', '')))}</small></div>" for r in ls if (saida / f"q/{r['n']:03d}.jpg").exists())
    pagina = saida / "_pdf.html"
    pagina.write_text("<meta charset=utf-8><style>body{font:22px system-ui;margin:0 20px}.c{page-break-after:always;padding-top:20px}"
                      "img{width:100%;max-height:1400px;object-fit:contain;display:block;background:#000;margin-bottom:10px}"
                      ".a{color:#a00}small{color:#555}</style>" + topo + cartoes, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(); pg.goto(pagina.resolve().as_uri()); pg.wait_for_load_state("networkidle")
        pg.pdf(path=str(saida / "storyboard.pdf"), width="900px", height="1700px", print_background=True); b.close()
    pagina.unlink()
    return saida / "storyboard.pdf"


def pasta(plano: dict) -> Path:
    """`<slug>.storyboard/`, ao lado do plano: o storyboard e o `decisoes.json` que o render final lê."""
    return Path(plano.get("_dir", ".")) / f"{plano['slug']}.storyboard"


def _corte_sha(edl_texto: str) -> str:
    """Quem é este corte. As decisões valem pro corte em que nasceram: outro `drops`, outro bruto, outro tempo."""
    return hashlib.sha1(json.dumps(json.loads(edl_texto)["ranges"], sort_keys=True).encode()).hexdigest()[:12]


def decisoes(plano: dict, edl_texto: str, refaz: bool = False) -> Path | None:
    """O `decisoes.json` do storyboard deste vídeo, se existe e é deste corte; senão None (a fábrica decide).
    Num corte que mudou, o render final recusa e o `--storyboard` (`refaz`) começa de novo."""
    arq = pasta(plano) / "decisoes.json"
    if not (arq.exists() and edl_texto):
        return None
    if json.loads(arq.read_text(encoding="utf-8")).get("corte") == _corte_sha(edl_texto):
        return arq
    if refaz:
        print(f"aviso: o corte mudou desde o último storyboard; as decisões e as correções dele ficam de lado ({arq.name})")
        return None
    raise ValueError(f"o storyboard {pasta(plano).name}/ é de outro corte (o vídeo ou o `drops` mudou). "
                     "Rode de novo com --storyboard, confira, e só então renderize")


LISTAS = ("cards", "pecas", "camera", "sons", "visual")     # o que o `decisoes.json` guarda e o aluno corrige pelo número


def _itens(doc: dict) -> list[dict]:
    """Tudo o que o dono corrige pelo número: os cards da legenda, as peças, os zooms da câmera e os sons."""
    return [i for k in LISTAS for i in doc.get(k, [])]


def _t(i: dict) -> float:
    return float(i["t0"] if "t0" in i else i["t"])      # o som tem um instante (`t`), o resto tem começo e fim


def numera(doc: dict) -> dict:
    """Dá número a quem ainda não tem, na ordem do tempo. O número nunca muda depois: tirar o 4 deixa o 5 no 5,
    porque o dono corrige olhando uma lista que ele já viu."""
    nu = max([x.get("n", 0) for x in _itens(doc)] + [0])
    for x in sorted((i for i in _itens(doc) if "n" not in i), key=_t):
        nu += 1
        x["n"] = nu
    return doc


def _acha(doc: dict, n: int) -> dict:
    for x in _itens(doc):
        if x.get("n") == n:
            return x
    raise KeyError(f"não existe o nº {n} neste storyboard (os números são: "
                   f"{', '.join(str(x['n']) for x in sorted(_itens(doc), key=lambda i: i['n']))})")


def tira(arq: Path, n: int) -> None:
    """\"nº 4: tira\": o card sai do `decisoes.json`, e o render final não o desenha."""
    doc = json.loads(arq.read_text(encoding="utf-8"))
    x = _acha(doc, n)
    next(doc[k] for k in LISTAS if x in doc.get(k, [])).remove(x)
    arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


TEXTOS = ("txt", "l", "l1", "termo", "nome", "pt", "hd", "rot")   # o texto de uma peça, na ordem em que a gente o procura


def troca_texto(arq: Path, n: int, texto: str) -> None:
    """\"nº 7: troca o texto pra X\": a legenda passa a dizer X. As palavras novas dividem o tempo do card em partes iguais."""
    doc = json.loads(arq.read_text(encoding="utf-8"))
    x = _acha(doc, n)
    if "layout" in x and "tipo" in x:   # o visual de uma batida
        raise ValueError("o visual da batida não troca de texto pelo número: tire (e a batida volta pro rosto), ou corrija o visual.json")
    if "peca" in x:                     # a peça: o texto principal dela (o 1º campo de texto que o `q` tem)
        campo = next((k for k in TEXTOS if k in x["q"]), None)
        if not campo:
            raise ValueError(f"a peça {x['peca']} não tem texto pra trocar: tire com --tira e ponha a nova no plano")
        x["q"][campo] = texto
        arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return
    if "words" not in x:
        raise ValueError("só a legenda e a peça têm texto: o zoom e o som saem com --tira")
    ws, novas = x["words"], texto.split()
    if not novas:
        raise ValueError("texto vazio: pra tirar a legenda use --tira")
    a, b = ws[0]["t0"], ws[-1]["t1"]
    passo = (b - a) / len(novas)
    x["words"] = [{**ws[min(i, len(ws) - 1)], "tx": (w.upper() if ws[0]["tx"].isupper() else w),
                   "t0": round(a + i * passo, 2), "t1": round(a + (i + 1) * passo, 2)}
                  for i, w in enumerate(novas)]
    arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _corrige(a: list[str]) -> None:
    """`--tira <pasta> N` e `--texto <pasta> N "texto"`. Depois: `fabrica.py <plano> --storyboard` pra ver."""
    try:
        arq = Path(a[1]) / "decisoes.json"
        n = int(a[2])
        tira(arq, n) if a[0] == "--tira" else troca_texto(arq, n, a[3])
    except (IndexError, ValueError, KeyError, OSError) as e:
        sys.exit(f"não deu: {e.args[0] if e.args else e}\nuso: storyboard.py --tira <slug>.storyboard N | "
                 "--texto <slug>.storyboard N \"texto novo\"")
    print(f"nº {a[2]} corrigido em {arq}. Rode `fabrica.py <plano> --storyboard` pra conferir.")


def linhas_decisoes(doc: dict) -> list[dict]:
    """As linhas do storyboard do celular: cada card do `decisoes.json`, no tempo do final."""
    ls = [{"n": x["n"], "t0": float(x["t0"]), "t1": float(x["t1"]), "bloco": "vídeo",
           "peca": "palavra atrás" if x.get("atras") else "legenda" if x.get("camada", "legenda") == "legenda" else x["camada"],
           "conteudo": " ".join(w["tx"] for w in x["words"]),
           "legenda": x.get("camada", "legenda") == "legenda"} for x in doc.get("cards", [])]
    # a peça: `_q`, `ar` e `_tema` são o que o `_sobrepoe` lê pra fotografá-la por cima do quadro
    ls += [{"n": x["n"], "t0": float(x["t0"]), "t1": float(x["t1"]), "bloco": "vídeo", "peca": x["peca"],
            "conteudo": _conteudo(x["q"], ""), "legenda": False, "_q": x["q"], "ar": AR_VERTICAL,
            "_tema": doc.get("tema")} for x in doc.get("pecas", [])]
    # a câmera e o som também levam número, pro aluno tirar o zoom ou o som que não quer; `leve`: não é peça sobre peça
    ls += [{"n": x["n"], "t0": float(x["t0"]), "t1": float(x["t1"]), "bloco": "vídeo", "peca": "câmera", "legenda": False,
            "leve": True, "conteudo": ("crava " if x.get("ease") == "crava" else "zoom ")
            + "→".join(f"{z:.2f}".replace(".", ",") for z in x.get("zoom", [1.0, 1.0]))} for x in doc.get("camera", [])]
    ls += [{"n": x["n"], "t0": float(x["t"]), "t1": float(x["t"]), "bloco": "vídeo", "peca": "som", "legenda": False,
            "leve": True, "conteudo": x.get("tipo") or Path(x["arquivo"]).name} for x in doc.get("sons", [])]
    # o visual por batida (visual.json): o quadro sai do rascunho, que já traz o cartão com a prova no lugar; a batida que
    # caiu na alternativa leva o aviso na linha, e quem a tira pelo número a tira do render (`tela_dividida --decisoes`)
    ls += [{"n": x["n"], "t0": float(x["t0"]), "t1": float(x["t1"]), "bloco": "vídeo", "peca": f"visual · {x['layout']}",
            "conteudo": f"{x['tipo']}: {x['prova']} ({x['de'] or x['motivo']})" + (" [ALTERNATIVA]" if x["status"] == "alternativa" else ""),
            "legenda": False, "leve": True} for x in doc.get("visual", [])]
    return sorted(ls, key=lambda r: r["t0"])


def _ancoras(cadeia: Path, dur: float):
    """Um segundo, ou uma âncora na fala (`ancora.py`: "meia hora", "labs>", "#2"), no tempo do vídeo cortado."""
    import ancora
    import transcript as tr
    fala = cadeia / "fala_cortada.json"
    palavras = tr.carrega(fala)["words"] if fala.exists() else []

    def tempo(a, onde: str) -> float:
        if a is None:
            raise ValueError(f"{onde}: falta o segundo ou a âncora (`em`)")
        try:
            return float(ancora.tempo(palavras, a, fim=dur))
        except (KeyError, TypeError, ancora.Faltou) as e:
            raise ValueError(f"{onde}: {e}") from None
    return tempo


def _pecas_do_plano(plano: dict, cadeia: Path, dur: float) -> list[dict]:
    """As peças que o plano pede, no tempo do vídeo cortado: `em` é um segundo ou uma âncora, e a peça fica `dur` s na tela.
    `mudo` (a peça não soa), `atras` (por trás da cabeça) e `peso` (1 a 3, pro ritmo) seguem com ela."""
    tempo = _ancoras(cadeia, dur)
    out = []
    for p in plano.get("pecas") or []:
        t0 = tempo(p.get("em"), f"a peça {p.get('peca', '?')}")
        out.append({"peca": p["peca"], "q": dict(p.get("q") or {}), "t0": t0,
                    "t1": round(min(t0 + float(p.get("dur", 2.5)), dur), 3),
                    **{k: p[k] for k in ("mudo", "atras", "peso") if k in p}})
    return out


# o card de palavra enorme atrás da cabeça, como o plano aprovado de 23/10 o desenhou à mão
ATRAS = {"fonte": "bebas", "layout": "topo", "atras": True, "quebra": "palavra", "modo": "pop", "largura": 0.97,
         "entrelinha": 0.9, "contorno": {"largura": 9, "cor": "#0B0D12"},
         "efeito": {"offset": {"dx": 12, "dy": 12, "cor": "#0B0D12"}}}
FUNDO = {"forma": "circulo", "cor": "ac", "x": 540, "y": 1100, "tam": 900}      # q do e_fundo


def _entra_do_plano(plano: dict, doc: dict, cadeia: Path, dur: float) -> None:
    """O que o plano pede além da legenda entra no `decisoes.json` uma vez, com número: as peças (`pecas`), o zoom da câmera
    (`camera`), os sons (`sons`), as palavras atrás da cabeça (`palavras_atras`) e o fundo trocado atrás delas (`fundo`).
    Depois o `decisoes.json` manda, e o que o aluno tirou pelo número não volta. Plano sem a chave não grava a dele."""
    tempo = _ancoras(cadeia, dur)
    if "pecas" not in doc and plano.get("pecas"):
        doc["pecas"] = _pecas_do_plano(plano, cadeia, dur)
    if "camera" not in doc and plano.get("camera"):
        doc["camera"] = []
        for c in plano["camera"]:
            t0 = tempo(c.get("em", c.get("t0")), "a câmera")
            t1 = tempo(c["ate"], "a câmera") if "ate" in c else t0 + float(c.get("dur", 1.0))
            doc["camera"].append({**{k: v for k, v in c.items() if k not in ("em", "ate", "dur", "t0", "t1")},
                                  "t0": round(t0, 3), "t1": round(min(t1, dur), 3)})
    if "sons" not in doc and plano.get("sons"):
        doc["sons"] = [{**s, "t": round(tempo(s["t"], "o som"), 3)} for s in plano["sons"]]
    if plano.get("palavras_atras") and not doc.get("atras_entrou"):
        f = plano.get("fundo")
        de = ate = None
        if f:
            de, ate = tempo(f.get("de", 0), "o fundo"), tempo(f.get("ate", dur), "o fundo")
            doc["fundo"] = {"peca": "e_fundo", "q": {**FUNDO, **(f.get("q") or {}), "dur": round(ate - de + 0.3, 2)}}
        for h in plano["palavras_atras"]:
            t0 = tempo(h.get("em"), f"a palavra {h.get('texto', '?')}")
            t1 = round(min(t0 + float(h.get("dur", 0.8)), dur), 3)
            # a palavra enorme cobre a legenda do instante: o card de baixo sai, e não sobram duas falas na tela
            doc["cards"] = [c for c in doc.get("cards", []) if c.get("atras") or not t0 <= (c["t0"] + c["t1"]) / 2 <= t1]
            card = {"t0": t0, "t1": t1, **ATRAS, "words": [
                {"tx": str(h["texto"]).upper(), "t0": t0, "t1": round(t1 - 0.05, 3), "cor": h.get("cor", "#FFFFFF"),
                 "corpo": h.get("corpo", 250), "track": h.get("track", 0.1)}]}
            if f and de <= t0 < ate:
                card["tela"] = {"fundo": True, "larg": 1.0, "raio": 0, "sombra": False, "x": 0, "y": 0,
                                "inicio": round(t0 - de, 3)}
            doc.setdefault("cards", []).append(card)
        doc["cards"].sort(key=lambda c: c["t0"])
        doc["atras_entrou"] = True


CAMPOS_DO_PLANO = ("pecas", "camera", "palavras_atras", "sons")     # o movimento que o plano pode trazer à mão


def eventos(doc: dict) -> list[dict]:
    """O que muda na tela, do `decisoes.json`, no formato do `checks.ritmo`. A legenda comum não entra: ela corre o vídeo todo."""
    ev = [{"t0": float(p["t0"]), "t1": float(p["t1"]), "tipo": checks.tipo_do_efeito(p["peca"]), "peca": p["peca"],
           **({"peso": p["peso"]} if "peso" in p else {})} for p in doc.get("pecas", [])]
    ev += [{"t0": float(c["t0"]), "t1": float(c["t1"]), "tipo": "zoom", "zoom": c.get("zoom")} for c in doc.get("camera", [])]
    ev += [{"t0": float(c["t0"]), "t1": float(c["t1"]), "tipo": "palavra_atras", "peso": 3}
           for c in doc.get("cards", []) if c.get("atras")]
    # a troca de layout: o rosto passa pro fundo trocado (a palavra atrás da cabeça com `tela.fundo`) e volta
    ev += [{"t0": float(c["t0"]), "t1": float(c["t1"]), "tipo": "layout"}
           for c in doc.get("cards", []) if c.get("atras") and (c.get("tela") or {}).get("fundo")]
    # cada batida do visual é uma troca de layout (tela dividida ou cheia): conta pro vão e pra variação
    ev += [{"t0": float(v["t0"]), "t1": float(v["t1"]), "tipo": "layout"} for v in doc.get("visual", [])]
    ev += [{"t0": float(s["t"]), "t1": float(s["t"]), "tipo": "sons"} for s in doc.get("sons", [])]
    return ev


def avisos(doc: dict, dur: float) -> list:
    """O plano decidido contra o que o aluno pediu (`movimento.py`) e contra a casca de página: lista de `checks.Resultado`."""
    import movimento
    return checks.ritmo(eventos(doc), dur, movimento.le())


def avisos_do_plano(plano: dict, cadeia: Path, dur: float) -> list:
    """Os mesmos avisos antes do storyboard: do `decisoes.json` se ele já existe, senão do próprio plano. Âncora que a fala
    ainda não mediu (o primeiro `--storyboard` não rodou) deixa o vão sem medir, em vez de chutar."""
    arq = pasta(plano) / "decisoes.json"
    if arq.exists():
        return avisos(json.loads(arq.read_text(encoding="utf-8")), dur)
    doc = {"cards": []}
    try:
        _entra_do_plano(plano, doc, cadeia, dur)
    except ValueError as e:
        return [checks.Resultado("ritmo-vao", None, f"{e} (o storyboard mede depois que a fala é cortada)")]
    return avisos(doc, dur)


def _quadros_legendados(doc: dict, cadeia: Path, video: Path, tempos: list[float], para: Path) -> dict[float, Path]:
    """O quadro de `video` em cada instante de `tempos` com a legenda das `decisoes` desenhada por cima (`captions_viral
    --quadros`): o storyboard mostra o que o final vai mostrar sem queimar a legenda no vídeo inteiro. A peça, a
    câmera e o fundo trocado não entram (o rascunho nunca os desenhou). Quadro que não saiu fica de fora."""
    if not tempos:
        return {}
    plano = {**doc, "brolls": [], "camera": [], "cards": [{k: v for k, v in c.items() if k != "tela"} for c in doc.get("cards", [])]}
    arq = cadeia / "quadros.json"
    arq.write_text(json.dumps(plano, ensure_ascii=False), encoding="utf-8")
    dv = cadeia / "tela_dividida" / "dividida.json"
    chaves = sorted({f"{t:.3f}" for t in tempos})
    ff.run([sys.executable, str(Path(__file__).resolve().with_name("captions_viral.py")), str(video), "--plan", arq,
            "--quadros", ",".join(chaves), "-o", para, *(["--dividida", dv] if dv.exists() else [])], quiet=True, check=False)
    return {t: para / f"{t:.3f}.jpg" for t in tempos if (para / f"{t:.3f}.jpg").exists()}


def do_celular(plano: dict, cadeia: Path, video: Path, trechos: list[dict]) -> Path:
    """O fim de `fabrica.py <plano> --storyboard`: `video` é o rascunho 720 p, sem a legenda queimada (queimar custava
    2 min a rodada), `cadeia` a pasta onde a fábrica decidiu (`cards.json`). Grava o `decisoes.json` (uma vez: as correções
    do dono sobrevivem a uma nova rodada) e o storyboard, com o quadro do `video` no instante de cada overlay, a legenda
    desenhada só nesse quadro."""
    saida = pasta(plano)
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / "decisoes.json"
    edl = json.dumps({"ranges": trechos})
    if not arq.exists() or json.loads(arq.read_text(encoding="utf-8")).get("corte") != _corte_sha(edl):
        feito = json.loads((cadeia / "cards.json").read_text(encoding="utf-8")) if (cadeia / "cards.json").exists() else {}
        feito = {"cards": feito} if isinstance(feito, list) else feito
        if not feito.get("cards"):
            sys.exit("a fábrica não decidiu nenhum overlay neste vídeo (sem fala ou sem legenda no estilo): nada a mostrar")
        arq.write_text(json.dumps({**feito, "corte": _corte_sha(edl)}, ensure_ascii=False, indent=1), encoding="utf-8")
    doc = json.loads(arq.read_text(encoding="utf-8"))
    duracao = sum(t["end"] - t["start"] for t in trechos)
    proposta = ""
    if not doc.get("proposta") and not doc.get("pecas") and not any(plano.get(k) for k in CAMPOS_DO_PLANO) \
            and (cadeia / "fala_cortada.json").exists():
        # plano sem movimento: a Fábrica propõe pela densidade gravada (propoe.py), e o agente ajusta o que não fizer sentido
        import movimento
        import propoe
        ach = cadeia / "visual" / "achados.json"
        cobertos = [(a["t0"], a["t1"]) for a in json.loads(ach.read_text(encoding="utf-8")) if a["status"] != "rosto"] if ach.exists() else []
        frag, proposta = propoe.do_arquivo(cadeia / "fala_cortada.json", duracao, movimento.le(), checks._cardapio(), cobertos)
        plano = {**plano, **frag}
        doc["proposta"] = True
    _entra_do_plano(plano, doc, cadeia, duracao)
    achados = cadeia / "visual" / "achados.json"
    if "visual" not in doc and achados.exists():
        doc["visual"] = [{k: a[k] for k in ("id", "t0", "t1", "layout", "tipo", "prova", "status", "de", "motivo")}
                         | {k: a[k] for k in ("confianca", "aviso") if a.get(k)}
                         for a in json.loads(achados.read_text(encoding="utf-8")) if a["status"] != "rosto"]
    doc["tema"] = _tema_do_estilo({"estilo": plano.get("estilo")})
    doc = numera(doc)
    arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    (saida / "q").mkdir(exist_ok=True)
    sonda = ff.probe(video)
    larg = 540 if sonda.retrato else 960
    ls = linhas_decisoes(doc)
    for r in ls:
        r["q"] = f"q/{r['n']:03d}.jpg"
        r["_k"] = None
    dv = cadeia / "tela_dividida" / "dividida.json"
    sal = hashlib.sha1(json.dumps([doc.get("cards"), dv.read_text(encoding="utf-8") if dv.exists() else ""],
                                  ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]
    _marca(ls, video, sal)  # antes do `_escreve`, que acrescenta avisos ao texto; a legenda entra na chave (ela não está no vídeo)
    ch = _chaves(saida)
    feitos = ch.setdefault("q", {})
    novos = [r for r in ls if not (feitos.get(str(r["n"])) == r["_k"] and (saida / r["q"]).exists())]     # nada mudou nos outros
    instante = {r["n"]: round(min(r["t0"] + 0.65 * (r["t1"] - r["t0"]), sonda.duracao - 0.1), 3) for r in novos}
    com_legenda = _quadros_legendados(doc, cadeia, video, list(instante.values()), cadeia / "quadros")
    for r in novos:
        m = instante[r["n"]]
        if m in com_legenda:
            from PIL import Image
            img = Image.open(com_legenda[m]).convert("RGB")
            img.resize((larg, round(img.height * larg / img.width))).save(saida / r["q"], quality=88)
        else:       # a legenda não saiu: o quadro sem ela, e o dono vê que falta
            print(f"aviso: o quadro {r['n']} saiu sem a legenda")
            ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{m:.2f}", "-i", video, "-frames:v", "1",
                    "-vf", f"scale={larg}:-2", "-q:v", "3", saida / r["q"]], quiet=True, check=False)
        if "_q" in r:           # a peça não está no rascunho: fotografa e põe por cima do quadro
            _sobrepoe(r, saida / r["q"])
        feitos[str(r["n"])] = r["_k"]
    _varre(saida / "q", {Path(r["q"]).name for r in ls})
    ch["q"] = {k: v for k, v in feitos.items() if int(k) in {r["n"] for r in ls}}
    (saida / "chaves.json").write_text(json.dumps(ch), encoding="utf-8")
    for r in ls:        # a fala em volta: o card sozinho já é a fala, e o dono quer o contexto pra decidir
        r["fala"] = " ".join(o["conteudo"] for o in ls if not o.get("leve")
                            and o["t1"] >= r["t0"] - 1.0 and o["t0"] <= r["t1"] + 1.0)[:160]
    falhas = [r for r in avisos(doc, duracao) if r.ok is False]
    # o que o fim do render mediria e dá pra prever: o salto de brilho e o quadro vazio que já estão no corte. O que
    # a peça e o fundo trocado causam só existe no render final (o rascunho não os desenha): isso não se prevê aqui.
    try:
        st = checks._stats(video)
        falhas += [r for r in (checks.sem_flash(st), checks.quadro_vazio(st)) if r.ok is False]
    except (OSError, RuntimeError, KeyError, ValueError, IndexError):
        pass
    textos, notas = [f"{r.id}: {r.nota} — {r.mediu}" for r in falhas], _notas(plano)
    # a trava do recorte (tela_dividida.py): máscara fraca troca a pessoa recortada pelo vídeo no cartão, e o dono fica sabendo
    av = cadeia / "tela_dividida" / "avisos.json"
    textos = (json.loads(av.read_text(encoding="utf-8")) if av.exists() else []) + textos
    # no topo da folha: onde a prova ficou fraca, pro dono ver rápido
    textos = [f"visual: a batida {v['id']} ({v['t0']:.1f}–{v['t1']:.1f} s) caiu na alternativa: {v['motivo']}"
              for v in doc.get("visual", []) if v["status"] == "alternativa"] \
        + [v["aviso"] for v in doc.get("visual", []) if v.get("aviso")] + textos
    _escreve(ls, saida, textos, notas)
    _revisao(ls, saida, video, plano["slug"], textos, notas, viva=True)
    for r in falhas:
        print(f"AVISO {r.id}: {r.nota}\n       mediu: {r.mediu}")
    if proposta:
        print(proposta + ": ajuste só o que não fizer sentido na fala (tira pelo número, ou troca o texto)")
    if not doc.get("pecas"):
        print("nenhuma peça: proponha 2 a 4 (skill fabrica-movimento), ponha em `pecas` no plano e rode --storyboard de novo")
    # a linha que o agente lê: não precisa abrir o storyboard.md
    print(f"storyboard: {len(doc.get('pecas', []))} peças · {len(falhas) + len(notas)} avisos · revisão em {saida / 'revisao.html'}")
    return saida / "revisao.html"


# ── A revisão aplicada de uma vez: o texto que o aluno colou ─────────────────────────────────────────────────────

LINHA = re.compile(r"^(\d+)\s+(manter|talvez|tirar|texto)\s*(?::\s*(.*))?$", re.IGNORECASE)


def aplica(arq: Path, texto: str) -> tuple[list[str], list[str]]:
    """Aplica no `decisoes.json` tudo o que é certo no texto colado do "Copiar revisão" ("4 tirar", "9 texto: novo texto",
    "7 talvez: entra mais cedo"): tirar e trocar o texto. Devolve (feito, pendente): `pendente` é o que pede decisão do agente
    (talvez, nota em manter, número que não existe, linha que não entendi). O cabeçalho e o rodapé da página são ignorados."""
    feito, pendente = [], []
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith(("Revisão do storyboard", "Aplique ")):
            continue
        m = LINHA.match(linha)
        if not m:
            pendente.append(f"linha que não entendi: {linha!r}")
            continue
        n, acao, nota = int(m[1]), m[2].lower(), (m[3] or "").strip()
        try:
            if acao == "tirar":
                tira(arq, n)
                feito.append(f"nº {n} tirado")
            elif acao == "texto" or (acao == "talvez" and re.match(r"texto\s*:", nota, re.IGNORECASE)):
                novo = nota if acao == "texto" else nota.split(":", 1)[1].strip()
                if not novo:
                    pendente.append(f"nº {n}: texto vazio")
                    continue
                troca_texto(arq, n, novo)
                feito.append(f"nº {n} texto trocado")
            else:
                _acha(json.loads(arq.read_text(encoding="utf-8")), n)       # só confere que o número existe
                if acao == "talvez" or nota:
                    pendente.append(f"nº {n} {acao}: {nota or '(sem nota)'}")
        except (KeyError, ValueError) as e:
            pendente.append(f"nº {n}: {e.args[0] if e.args else e}")
    return feito, pendente


def _aplica(a: list[str]) -> None:
    """`--aplica <slug>.storyboard <texto | arquivo | ->`: imprime o que aplicou e, numa lista curta, só o que sobra pro agente."""
    try:
        arq = Path(a[0]) / "decisoes.json"
        if not arq.exists():
            raise OSError(f"não achei {arq}")
        fonte = a[1]
        texto = sys.stdin.read() if fonte == "-" else Path(fonte).read_text(encoding="utf-8") if Path(fonte).is_file() else fonte
    except (IndexError, OSError) as e:
        sys.exit(f"não deu: {e.args[0] if e.args else e}\nuso: storyboard.py --aplica <slug>.storyboard \"<texto colado>\" | arquivo | -")
    feito, pendente = aplica(arq, texto)
    print(f"aplicado: {len(feito)}" + (f" ({'; '.join(feito)})" if feito else ""))
    if pendente:
        print(f"precisa de você ({len(pendente)}):")
        for p in pendente:
            print(f"  - {p}")
    print("depois: fabrica.py <plano> --storyboard pra conferir")


def main() -> None:
    if {"-h", "--help"} & set(sys.argv[1:]):
        return print(__doc__)
    if len(sys.argv) > 1 and sys.argv[1] in ("--tira", "--texto"):
        return _corrige(sys.argv[1:])
    if len(sys.argv) > 1 and sys.argv[1] == "--aplica":
        return _aplica(sys.argv[2:])
    rasc = "--rascunho" in sys.argv
    anim = "--animada" in sys.argv   # com --rascunho: um clipe com a voz por linha, cortado do corte seco, e a peça tocando por cima no navegador (sem render de peça)
    srt = Path(sys.argv[sys.argv.index("--srt") + 1]) if "--srt" in sys.argv else None
    cortes = Path(sys.argv[sys.argv.index("--cortes") + 1]) if "--cortes" in sys.argv else None
    a = [x for x in sys.argv[1:] if not x.startswith("--") and x not in (str(srt), str(cortes))]
    if rasc:
        plano, saida = Path(a[0]), Path(a[1])
        video = _trab(plano, True) / "seco.mp4"
    else:
        plano, video, saida = Path(a[0]), Path(a[1]), Path(a[2])
    if not Path(video).exists():
        sys.exit(f"não achei o vídeo base {video}: passe o vídeo do corte seco/prévia explicitamente")
    import shutil
    shutil.rmtree(saida / "q", ignore_errors=True)        # nunca compor por cima de quadro de rodada anterior
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "q").mkdir(exist_ok=True)
    fala = _srt(srt)
    ls = linhas(plano, rasc, cortes)
    # o render come uns décimos por emenda (J/L-cut, ponte): a soma dos cortes passa do vídeo. Escala pra não errar o quadro
    soma = _soma_cortes(plano, rasc, cortes)
    dv = _dur(video)
    if not soma or abs(dv - soma) / dv > 0.04:
        sys.exit(f"os blocos somam {soma:.1f} s e o vídeo tem {dv:.1f} s: o tempo das peças sairia errado. "
                 "Confira o vídeo base e --cortes (a pasta com <bloco>/corte.mp4 desse vídeo).")
    fator = dv / soma
    for r in ls:
        r["t0"], r["t1"] = r["t0"] * fator, r["t1"] * fator
    qlarg = max(960, _larg(video, True)) if anim else 960      # na folha animada o vídeo aparece grande: o quadro (poster) acompanha
    for i, r in enumerate(ls, 1):
        m = r["t0"] + _instante(r)                      # o mesmo instante em que a peça é fotografada
        r["n"], r["q"] = i, f"q/{i:03d}.jpg"
        ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{m:.2f}", "-i", video, "-frames:v", "1",
               "-vf", f"scale={qlarg}:-2", "-q:v", "3", saida / r["q"]], quiet=True, check=False)
        if rasc or "--pecas" in sys.argv:
            # corte seco não tem peça: fotografa a peça (PNG transparente, v2.quadro) e põe por cima do quadro
            _sobrepoe(r, saida / r["q"], qlarg)
            r["fala"] = " ".join(x[2] for x in fala if x[1] >= r["t0"] - 0.3 and x[0] <= r["t1"])[:160]
            continue
        # o trecho animado, recortado da prévia que já existe (sem render de peça): 480p, 15 qps, mudo, até 5 s
        r["v"] = f"q/{i:03d}.mp4"
        a0, a1 = max(0.0, r["t0"] - 0.2), min(r["t1"] + 0.3, r["t0"] + 5.0)
        ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a0:.2f}", "-i", video, "-t", f"{a1 - a0:.2f}", "-an",
               "-vf", "scale=854:-2,fps=15", "-c:v", ff.CODEC_HW, "-b:v", "900k", "-pix_fmt", ff.PIX_FMT,
               "-movflags", "+faststart", saida / r["v"]], quiet=True, check=False)
        r["fala"] = " ".join(x[2] for x in fala if x[1] >= r["t0"] - 0.3 and x[0] <= r["t1"])[:160]
    try:   # etiqueta de carta sem lugar medido cai sobre a carta: avisa antes do dono ver (o kit não leva o encaixe_carta)
        import encaixe_carta
        aviso = encaixe_carta.sem_encaixe(plano)
    except ImportError:
        aviso = []
    doc = {**json.loads(plano.read_text(encoding="utf-8")), "_dir": str(plano.parent)}
    notas = _notas(doc)
    sem_clipe = (rasc or "--pecas" in sys.argv) and not anim
    _marca(ls, None if sem_clipe else video, "grande" if anim else "")     # o tamanho do clipe entra na chave: a folha grande refaz os de 640 px
    _escreve(ls, saida, aviso, notas)
    _revisao(ls, saida, None if sem_clipe else video, doc.get("slug") or plano.stem, aviso, notas, viva=anim, grande=anim)
    for velho in ("storyboard.html", "storyboard.pdf"):   # sobra de rodada antiga: o link é o revisao.html, o PDF só com --celular
        (saida / velho).unlink(missing_ok=True)
    if "--celular" in sys.argv:
        print(f"storyboard: PDF pro celular em {_pdf_celular(ls, saida, aviso, notas)}")
    print(f"storyboard: {len(ls)} overlays · {len(aviso) + len(notas)} avisos · revisão em {saida / 'revisao.html'}")


if __name__ == "__main__":
    main()
