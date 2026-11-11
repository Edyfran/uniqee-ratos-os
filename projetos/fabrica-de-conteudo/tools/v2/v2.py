#!/usr/bin/env python3
"""Biblioteca v2 — o ÚNICO ponto de entrada de motion do repo.

Tudo que desenha mora em tools/v2/pecas/ (HTML + GSAP, timeline buscável) e
herda cor, fonte e movimento de tools/v2/nucleo/. Este script lista, renderiza
e compõe. Os scripts antigos (make_reel_v3, lesson_overlays, tools/mg) viram
TRADUTORES: leem a config deles e chamam isto — não desenham mais nada.

    v2.py lista   [--familia ve] [--formato 1920x1080] [--camadas]
    v2.py info    <peca>
    v2.py cardapio                                   ← as peças do reel do aluno, uma linha cada
    v2.py catalogo                                   ← regenera o catalogo.json dos cabeçalhos
    v2.py qa      [peca ...] [--familia g] [--json rel.json] [--notas] [--ar 1920x1080]
                                                     ← inspeciona as peças (mesma regra do Estúdio);
                                                       sai com código 1 se houver falha
    v2.py mede    <peca> --q '{"l": "..."}' [--ar 1920x1080] [--t 1.0]
                                                     ← a peça sozinha com os parâmetros do plano: JSON com
                                                       caixa, texto a texto (px do quadro, linhas), zona segura
    v2.py render  <peca> [k=v ...] [--out x.mov] [--ar 1080x1920] [--tema claro|tinta]
                          [--camada tras|frente] [--fps 30] [--opaco]
                          [--mesa pasta]             ← os valores que o Studio gravou na mesa
    v2.py lote    pedidos.json                     ← vários `render` num navegador só; o JSON é a
                                                       lista dos argumentos de cada um
    v2.py mesa    <peca> [k=v ...] --pasta /tmp/mesa → a peça pronta pro HyperFrames Studio web,
                                                       com os parâmetros como variáveis
    v2.py camadas <peca> [k=v ...] --out base      → base.tras.mov, base.frente.mov, base.json
    v2.py compor  --take take.mp4 --peca base.json --em 12.4 --out saida.mp4
                  [--pessoa pessoa.mov] [--folga 1.25] [--seco]

  <peca> é o id do catalogo.json (ou um id de variante, ex.: ve_titulo_capa).
  k=v entra na query da peça, exatamente como no comentário do topo dela.

Saídas de render: .mov Animation (qtrle, sem perda, com alfa; acima de 100 MB, ProRes 4444 se
ficar menor) e, ao lado, <saida>.json com
duração, cues de som (window.__cues), onde a peça quer a pessoa
(window.__pessoa) e os efeitos que ela pede ao take (window.__video).

Requer o venv do pipeline: ~/obs-optimize/tools/video-use/.venv/bin/python
"""
from __future__ import annotations

import argparse, json, os, shutil, sys, tempfile, time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, parse_qsl

AQUI = Path(__file__).resolve().parent
CATALOGO = AQUI / "catalogo.json"
# A marca do aluno, na raiz da fábrica (ao lado de tools/): ?tema=marca carrega esta folha por cima
# do núcleo (direcao-v2.js). Ela sobrevive à atualização do kit, que só troca tools/.
MARCA_CSS = AQUI.parents[1] / "marca" / "tema.css"
HELPERS = AQUI.parent / "video-use" / "helpers"
sys.path.insert(0, str(HELPERS))
import ff  # noqa: E402 — a costura B: todo ffmpeg daqui passa por ela


# ───────────────────────── núcleo ─────────────────────────
def token(nome: str, tema: str | None = None) -> str:
    """O valor de um token do núcleo (`ac` → "#0640fb"). Quem roda fora do
    navegador — a legenda, a fábrica — lê daqui em vez de copiar o hex. Com o
    tema `marca`, o que a marca/tema.css redeclara ganha do núcleo."""
    import re
    css = (AQUI / "nucleo" / "direcao-v2.css").read_text(encoding="utf-8")
    if tema == "marca" and MARCA_CSS.is_file():
        css = MARCA_CSS.read_text(encoding="utf-8") + css
    m = re.search(rf"--{re.escape(nome)}:\s*([^;}}]+)[;}}]", css)
    if not m:
        sys.exit(f"token que o núcleo não tem: --{nome}")
    return m.group(1).strip()


# ───────────────────────── catálogo ─────────────────────────
def catalogo() -> dict:
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    # o catálogo é um só pro tronco e pro kit: peça que esta pasta não leva (no kit, as dos clones e dos anúncios) fica de fora da lista
    cat["pecas"] = [p for p in cat["pecas"] if (AQUI / p["arquivo"]).exists()]
    return cat


def acha(peca: str) -> tuple[dict, str]:
    """Devolve (entrada do catálogo, query da variante). Aceita alias."""
    cat = catalogo()
    al, qa = cat.get("aliases", {}).get(peca), ""
    if al:   # nome antigo (make_reel_v3, lesson_overlays) → peça nova + query fixa
        peca, qa = (al["peca"], al.get("query", "")) if isinstance(al, dict) else (al, "")
    for p in cat["pecas"]:
        if p["id"] == peca:
            return p, qa
        for v in p.get("variantes", []):
            if v["id"] == peca:   # variante pode trocar o formato (ex.: x_corte_16x9)
                return {**p, "formato": v.get("formato", p["formato"])}, v["query"]
    sys.exit(f"peça desconhecida: {peca}  (v2.py lista)")


def cmd_lista(a):
    curta: dict[str, list[str]] = {}
    for p in catalogo()["pecas"]:
        if a.familia and p["familia"] != a.familia:
            continue
        if a.formato and p["formato"] != a.formato:
            continue
        if a.camadas and not p["camadas"]:
            continue
        if a.curta:   # só o id, uma linha por família: o agente lê isto em vez das 380 linhas; `info <id>` abre a peça
            curta.setdefault(p["familia"], []).append(p["id"])
            continue
        marca = ("alfa " if p["alfa"] else "     ") + ("camadas " if p["camadas"] else "        ")
        print(f"{p['id']:<22} {p['formato']:<10} {marca} {p.get('nome') or ''}")
        for v in p.get("variantes", []):
            print(f"  └ {v['id']:<18} ?{v['query']}")
    for fam, ids in curta.items():
        print(f"{fam} ({len(ids)}): {' '.join(ids)}")


# O cardápio do reel do aluno: poucas peças da lista do kit (pecas-do-kit.txt), nenhuma casca de página (checks.CASCA),
# uma linha cada. `q` é o que vai no plano. O SKILL manda escolher só daqui; o aviso casca-de-pagina também aponta pra cá.
CARDAPIO = [
    ("g_gancho", "título dos 3 primeiros segundos", {"l": "Eu demiti|*4 funcionários|_e contratei agentes"}),
    ("t_headline", "frase no topo com a palavra-chave grifada", {"l": "Zero gestor. <i>Só um agente</i>."}),
    ("k_queda", "palavra que cai letra a letra", {"l1": "queda", "l2": "LIVRE"}),
    ("k_palavra_gigante", "uma palavra enorme que entra e some", {"l": "Claude Code"}),
    ("el_rabisco", "círculo, seta ou sublinhado à mão sobre algo da tela", {"tipo": "circulo", "r": "240,700,600,300", "rot": "isso aqui"}),
    ("e_mira", "quatro cantos travam em volta do que importa", {"r": "240,420,600,700", "rot": "FOCO"}),
    ("e_carimbo", "carimbo torto com poucas palavras", {"txt": "ISSO AQUI"}),
    ("d_linha", "gráfico de linha que cresce até o valor", {"pts": "12,18,26,44,58", "x": "jan,fev,mar,abr,mai", "rot": "faturamento"}),
    ("o_seta", "seta e anel apontando o botão", {"alvo": "540,1700", "de": "cima", "rot": "o botão está aqui"}),
    # as quatro que a Fábrica escolhe pela fala sozinha (propoe.pecas_da_fala): painel, toast, chip e lista
    ("i_terminal", "terminal digitando o comando que ele disse", {"cmd": "claude \"tire os anúncios da minha TV\"@0.5"}),
    ("r_notif", "notificações de venda que empilham", {"n": "Nova venda|Pagamento aprovado|agora@0.3;Nova venda|Pagamento aprovado|agora@1.2"}),
    ("r_termo", "chip com o nome da marca ou da sigla (def vazia: só a etiqueta)", {"termo": "CRM", "def": "", "x": 56, "y": 130}),
    ("t_lista_cel", "lista de até 4 itens que acendem na fala", {"hd": "Eles iam ter que...", "it": "Modelar dados@0.5;Integrar o Meta@1.5"}),
    ("g_comenta", "chamada final: digita a palavra no comentário", {"rot": "Comenta a palavra", "palavra": "AGENTE", "promessa": "que eu te mando o passo a passo"}),
]


def cmd_cardapio(a):
    print("Peças do reel (plano: {\"peca\": id, \"q\": {...}, \"em\": \"palavra\", \"dur\": 2.5}). Use só estas:")
    for i, serve, q in CARDAPIO:
        print(f"{i:<18} {serve} · q={json.dumps(q, ensure_ascii=False)}")


def cmd_info(a):
    p, q = acha(a.peca)
    print(json.dumps({**p, "query_variante": q}, ensure_ascii=False, indent=1))


def cmd_catalogo(a):
    """Regenera o catalogo.json a partir do comentário do topo de cada peça.
    Nome, linha, tipo, grupo, variantes e aliases já escritos à mão são preservados."""
    cat = gera_catalogo()
    CATALOGO.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {CATALOGO}  ({len(cat['pecas'])} peças)")


def _frase(p: dict, nome: str) -> str:
    """A frase pronta pra pedir a peça ao agente: o nome dela, na fala do aluno."""
    return f"Coloca no meu vídeo a animação \u201c{nome}\u201d, com o texto da minha fala."


def _serve(p: dict) -> str:
    """Pra que serve a peça, numa linha: o cabeçalho sem a família, sem medida nem flag."""
    import re
    d = re.sub(r"^[A-ZÀ-Ú /]+\s[—-]\s", "", (p.get("descricao") or "").strip())
    frases = [f for f in re.split(r"(?<=\.)\s+", d) if f and not re.search(r"\d{3,4}x\d{3,4}|--alpha|\?ar=|tela cheia\.?$", f)]
    return (frases[0] if frases else d).rstrip(".") + "."


def _estilos_da_biblioteca(pack: Path | None = None) -> dict[str, list[tuple]]:
    """Os estilos da biblioteca.html, por filtro: os doze do guia de estilos (a base) e os do Pack de Estilos
    de Edição descompactados em .agents/skills. Cada um: nome, linha, frase pronta, mídia, largura, altura."""
    raiz = AQUI.parents[1]
    sys.path.insert(0, str(AQUI.parent / "onboarding"))
    from onboarding import estilos as do_guia   # quem já lê o guia pro /onboarding
    base = [(e["nome"], " ".join(filter(None, (f"Combina com {e['combina']}." if e["combina"] else "", e["jeito"]))),
             f"Quero os meus vídeos no estilo {e['nome']} do guia de estilos, nas minhas cores e na minha letra.",
             raiz / e["imagem"], 1200, 1066)   # todo quadro do guia é 1200x1066
            for e in do_guia() if (raiz / e["imagem"]).is_file()]
    do_pack = []
    for arq in sorted((raiz / ".agents/skills" if pack is None else pack).glob("fabrica-*/estilos.json")):
        mp4 = arq.parent / "references/exemplo/exemplo.mp4"   # o exemplo leve que o ZIP de cada estilo leva, 9:16
        if mp4.is_file():
            do_pack += [(nome.capitalize(), d.get("_assinatura", ""), f"Faz o meu vídeo no estilo {nome.capitalize()}.", mp4, 1080, 1920)
                        for nome, d in json.loads(arq.read_text(encoding="utf-8")).items() if not nome.startswith("_")]
    return {k: v for k, v in (("Estilos", base), ("Estilos do Pack", do_pack)) if v}


def gera_biblioteca(saida: Path, marca: Path | None = None, horizontal: bool | None = None,
                    pack: Path | None = None) -> int:
    """A biblioteca.html: toda peça do kit que roda sozinha, tocando na marca do aluno (se ele tem
    marca/tema.css) e agrupada por família. Só toca o que está na tela. As peças entram por caminho
    relativo à `saida`, então a página abre com dois cliques (file://) se ficar na raiz da fábrica."""
    import html, os
    from urllib.parse import quote
    marca = MARCA_CSS if marca is None else marca
    rel = lambda alvo: os.path.relpath(Path(alvo).resolve(), saida.resolve().parent).replace(os.sep, "/")
    cat = catalogo()
    # fora: o que é do canal do dono (Tinteiro, vitrine), o que pede arquivo que o kit não leva
    # (tools/v2/midia, vivo/) e o exemplo que aponta pra imagem ou vídeo que o aluno ainda não tem
    import re
    def fora(p):
        if p["familia"] in ("l", "j", "teste") or p["id"] == "h_pareamento":   # rodadas de torneio: Tinteiro
            return True
        # midia: o rosto e o escritório dele; reels-assets: as capas dos Reels dele. O aluno não tem nenhum
        if re.search(r"midia|vivo/|reels-assets", (AQUI / p["arquivo"]).read_text(encoding="utf-8")):
            return True
        return any(re.search(r"\.(png|jpe?g|webp|mp4|mov|webm)\b", v) for _, v in parse_qsl((p.get("exemplo") or "").lstrip("?"), keep_blank_values=True))
    pecas = [p for p in cat["pecas"] if not fora(p)]
    # o 16:9 (vídeo longo, aula, painel da VSL) é do Kit de Edição para YouTube: sem o youtube.py dele,
    # só o que cabe nos 1080 de largura do 9:16. ponytail: o_comparativo e t_negativo têm ?ar=1080x1920
    # e ficam de fora assim mesmo; entram quando o exemplo de cada uma for o vertical
    if horizontal is None:
        horizontal = (AQUI.parent / "video-use/helpers/youtube.py").exists()
    if not horizontal:
        pecas = [p for p in pecas if int(p["formato"].split("x")[0]) <= 1080]
    # o nome da família em palavra de quem não edita: no crivo de 19/10, "dado", "talking head" e
    # "tipografia cinética" travaram 3 a 6 das 6 personas. Só aqui; o catálogo segue com o nome técnico.
    leigo = {"e": "efeito sobre o rosto", "d": "números e gráficos", "g": "abertura do vídeo",
             "k": "texto que se mexe", "h": "vídeo na horizontal", "ve": "vídeo na horizontal",
             "t": "frase na tela", "p": "preço e oferta", "preco": "preço e oferta", "o": "preço e oferta",
             "i": "chat e app na tela", "x": "outras",
             "s": "o que os clientes dizem", "r": "prova do que funciona", "el": "outras"}
    # a ordem dos filtros de tipo; vazia = a ordem em que os tipos aparecem no catálogo
    TIPOS = ["Abrir o vídeo", "Destacar uma frase ou palavra", "Mostrar um número ou comparar", "Listar passos, ideias e partes", "Chamar pra comprar ou comentar", "Dar efeito e trocar de cena", "Mostrar a tela, o app e o chat", "Mostrar prova e bastidores"]
    grupos: dict[str, list[dict]] = {}
    for p in pecas:
        grupos.setdefault(p.get("tipo") or leigo.get(p["familia"]) or cat["familias"].get(p["familia"], p["familia"]), []).append(p)
    if TIPOS:   # o sort é estável: tipo fora da lista fica no fim, na ordem de antes
        grupos = dict(sorted(grupos.items(), key=lambda kv: TIPOS.index(kv[0]) if kv[0] in TIPOS else len(TIPOS)))
    esc = html.escape
    chip = lambda rotulo, n: f'<button type="button" class="ch" data-t="{esc(rotulo)}" aria-pressed="{str(not rotulo).lower()}">{esc(rotulo or "Todas")}<small>{n}</small></button>'
    def cartao(rotulo, nome, linha, frase, url, w, h):
        return (f'<div class="c{" l" if w > h else ""}" data-t="{esc(rotulo)}" data-nome="{esc(nome)}" data-linha="{esc(linha)}" data-frase="{esc(frase)}">'
                f'<div class="pv" data-src="{esc(url)}" data-w="{w}" data-h="{h}"><iframe title="{esc(nome)}" loading="lazy"></iframe></div>'
                f'<div class="tx"><b>{esc(nome)}</b><div class="bt"><button type="button" class="ver">ver grande</button><button type="button" class="cp">copiar</button></div></div></div>')
    # os estilos vêm depois das animações; o quadro de cada um toca no nucleo/midia.html (imagem, ou vídeo em laço)
    estilos = _estilos_da_biblioteca(pack)
    total = len(pecas) + sum(map(len, estilos.values()))
    cards, nav = [], [chip("", total)]
    for rotulo, ps in grupos.items():
        nav.append(chip(rotulo, len(ps)))
        for p in ps:
            q = [(k, v) for k, v in parse_qsl((p.get("exemplo") or "").lstrip("?"), keep_blank_values=True) if k not in ("tema", "alfa")]
            q += [("vivo", "1"), ("repete", "1")]   # a timeline toca sozinha, em laço (D.vivo)
            w, h = map(int, p["formato"].split("x"))
            # a peça que vai por cima do vídeo toca sem papel, sobre a pessoa de mentira do núcleo
            if p["alfa"] and p["formato"] in ("1080x1920", "1920x1080"):
                q += [("alfa", "1"), ("boneco", "1")]
            if marca.is_file():
                q.append(("tema", "marca"))
            url = f"{rel(AQUI / p['arquivo'])}?{urlencode(q, quote_via=quote)}"
            nome = p.get("nome") or p["id"]
            linha = p.get("linha") or _serve(p)
            cards.append(cartao(rotulo, nome, linha, _frase(p, nome), url, w, h))
    for rotulo, es in estilos.items():
        nav.append(chip(rotulo, len(es)))
        for nome, linha, frase, midia, w, h in es:
            src = os.path.relpath(midia.resolve(), (AQUI / "nucleo").resolve()).replace(os.sep, "/")
            cards.append(cartao(rotulo, nome, linha, frase, f"{rel(AQUI / 'nucleo' / 'midia.html')}?{urlencode({'src': src}, quote_via=quote)}", w, h))
    tpl = (AQUI / "nucleo" / "biblioteca.html").read_text(encoding="utf-8")
    pagina = (tpl.replace("{{CSS}}", rel(AQUI / "nucleo" / "direcao-v2.css"))
              .replace("{{MARCA_LINK}}", f'<link rel="stylesheet" href="{rel(marca)}"><script>document.documentElement.classList.add("marca")</script>' if marca.is_file() else "")
              .replace("{{N}}", str(len(pecas))).replace("{{TOTAL}}", str(total)).replace("{{NE}}", str(total - len(pecas))).replace("{{NAV}}", "".join(nav)).replace("{{CARTOES}}", "".join(cards)))
    # letra preta ou branca sobre o azul e o amarelo da marca: a que tem mais contraste
    import re
    nucleo = (AQUI / "nucleo" / "direcao-v2.css").read_text(encoding="utf-8")
    css = marca.read_text(encoding="utf-8") if marca.is_file() else ""
    def sobre(tok):
        h = re.findall(rf"--{tok}:\s*#([0-9a-fA-F]{{6}})", css) or re.findall(rf"--{tok}:\s*#([0-9a-fA-F]{{6}})", nucleo)[:1]
        r, g, b = (int(h[0][i:i + 2], 16) / 255 for i in (0, 2, 4)) if h else (0, 0, 0)
        lum = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
        return "#0B0D12" if .2126 * lum(r) + .7152 * lum(g) + .0722 * lum(b) > .18 else "#FFFFFF"
    pagina = pagina.replace("{{SOBRE_AC}}", sobre("ac")).replace("{{SOBRE_MK}}", sobre("mk"))
    saida.write_text(pagina, encoding="utf-8")
    return len(pecas)


def cmd_biblioteca(a):
    """biblioteca.html na raiz da fábrica (ao lado de tools/ e marca/), pra abrir com dois cliques."""
    saida = Path(a.saida) if a.saida else AQUI.parents[1] / "biblioteca.html"
    n = gera_biblioteca(saida)
    print(f"wrote {saida}  ({n} peças, {'na marca' if MARCA_CSS.is_file() else 'sem marca/tema.css: direção da VSL'})")
    if a.abrir:
        import webbrowser
        webbrowser.open(saida.resolve().as_uri())


def gera_catalogo() -> dict:
    """O catálogo que os cabeçalhos das peças descrevem hoje, sem gravar."""
    import re
    velho = catalogo() if CATALOGO.exists() else {"pecas": []}
    por_id = {p["id"]: p for p in velho["pecas"]}
    novas = []
    for f in sorted((AQUI / "pecas").glob("*.html")):
        s = f.read_text(encoding="utf-8")
        c = (re.search(r"<!--([\s\S]*?)-->", s) or [None, ""])[1]
        ls = [l.strip() for l in c.splitlines() if l.strip()]
        v = por_id.get(f.stem, {})
        dims = re.search(r"(\d{3,4})x(\d{3,4})", c)
        # `?a=1` ou `rótulo: ?a=1` — peça com mais de um modo nomeia cada exemplo
        ex = next((l[l.index("?"):] for l in ls if re.match(r"(\w+:\s*)?\?", l)), "")
        novas.append({"id": f.stem, "arquivo": f"pecas/{f.name}", "familia": f.stem.split("_")[0],
                      "grupo": v.get("grupo"), "nome": v.get("nome"),
                      **{k: v[k] for k in ("linha", "tipo") if v.get(k)},   # o que o aluno lê na biblioteca
                      "formato": dims.group(0) if dims else v.get("formato", "1080x1920"),
                      "alfa": "--alpha" in c or bool(re.search(r'class="[^"]*\balfa\b', s)),
                      "camadas": 'data-c="' in s, "descricao": re.sub(r"\s+", " ", ls[0] if ls else "")[:220],
                      "exemplo": ex, **({"variantes": v["variantes"]} if v.get("variantes") else {})})
    velho.update({"pecas": novas, "gerado": time.strftime("%Y-%m-%d")})
    return velho


# ───────────────────────── qa ─────────────────────────
def cmd_qa(a):
    """Inspeciona as peças no Chromium com a MESMA regra do Estúdio (nucleo/qa.js):
    fica pronta, duração × timeline, cues com arquivo, texto que vaza ou é cortado
    pela caixa, texto fora do quadro ou na zona do rosto (16:9), o que desce até a
    faixa do player do YouTube (16:9, falha), peça alfa que
    aparece sem entrar ou não sai, contrato da timeline, cor e fonte fora do
    núcleo. Código 1 se houver falha: dá pra pôr antes de todo render.
    --ar 1920x1080 confere a peça no formato em que o vídeo a usa (a g_ deitada no longo)."""
    from playwright.sync_api import sync_playwright
    cat = catalogo()
    sons = json.loads((AQUI / "sfx" / "sfx.json").read_text(encoding="utf-8"))["sons"]
    qa_js = (AQUI / "nucleo" / "qa.js").read_text(encoding="utf-8")
    alvo = []
    for p in cat["pecas"]:
        if a.familia and p["familia"] != a.familia:
            continue
        alvo.append((p["id"], p, ""))
        alvo += [(v["id"], {**p, "formato": v.get("formato", p["formato"])}, v["query"]) for v in p.get("variantes", [])]
    if a.ar:
        alvo = [(i, {**p, "formato": a.ar}, q) for i, p, q in alvo]
    if a.pecas:
        alvo = [x for x in alvo if x[0] in a.pecas]
    rel, marca = [], {"ok": "✓", "aviso": "!", "falha": "✕"}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--force-color-profile=srgb"])
        aux = nav.new_page()
        aux.set_content("<html><body></body></html>")
        aux.add_script_tag(content=qa_js)
        for pid, p, qv in alvo:
            W, H = (int(x) for x in p["formato"].split("x"))
            pg = nav.new_page(viewport={"width": W, "height": H})
            rede_local(pg)
            erros: list[str] = []
            pg.on("pageerror", lambda e, erros=erros: erros.append(str(e)))
            q = "&".join(x for x in (qv, f"ar={p['formato']}") if x)
            r = {"id": pid, "achados": []}
            t0 = time.time()
            try:
                pg.goto((AQUI / p["arquivo"]).as_uri() + "?" + q)
                pg.wait_for_function("window.__tl && window.__ready === true", timeout=15000)
                pg.evaluate("document.fonts.ready.then(() => true)")
                r["pronta_ms"] = int((time.time() - t0) * 1000)
                pg.add_script_tag(content=qa_js)
                opc = {"alfa": p["alfa"], "sai": True,
                       "rosto": [1440, 760, 1880, 1040] if p["familia"] == "h" and p["alfa"] else None}
                d = pg.evaluate("([s, o]) => V2QA.dinamico(window, s, o)", [sons, opc])
                r["achados"] += d.pop("achados")
                r.update(d)
            except Exception as e:
                r["achados"].append({"nivel": "falha", "tipo": "pronta", "msg": "não ficou pronta: " + str(e).splitlines()[0][:160]})
            r["achados"] += [{"nivel": "falha", "tipo": "erro", "msg": m[:200]} for m in erros]
            r["achados"] += aux.evaluate("s => V2QA.estatico(s)", (AQUI / p["arquivo"]).read_text(encoding="utf-8"))
            pg.close()
            nv = {x["nivel"] for x in r["achados"]}
            r["nivel"] = "falha" if "falha" in nv else "aviso" if "aviso" in nv else "ok"
            rel.append(r)
            print(f"{marca[r['nivel']]} {pid:<24} {r.get('dur', 0):5.2f}s {r.get('ncues', 0):3d} cues")
            for x in r["achados"]:
                if x["nivel"] != "nota" or a.notas:
                    print(f"      {x['nivel']:<5} {x['tipo']:<8} {x['msg']}")
        nav.close()
    if a.json:
        Path(a.json).write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    n = {k: sum(r["nivel"] == k for r in rel) for k in ("ok", "aviso", "falha")}
    print(f"\n{len(rel)} peças · {n['ok']} ok · {n['aviso']} com aviso · {n['falha']} com falha")
    sys.exit(1 if n["falha"] else 0)


# ───────────────────────── mede ─────────────────────────
# Zona segura por formato (x0, y0, x1, y1): 16:9 com 5 % de margem e acima da faixa do player;
# 9:16 com 5 % dos lados e fora do cabeçalho e do rodapé do Reels (250 em cima, 340 embaixo).
def zona_segura(W: int, H: int) -> list[int]:
    if W * 9 == H * 16:
        return [round(W * .05), round(H * .05), round(W * .95), round(H * (1 - 184 / 1080))]
    return [round(W * .05), 250, round(W * .95), H - 340] if H > W else [round(W * .05), round(H * .05), round(W * .95), round(H * .95)]


def mede(pecas: list[tuple], t: float | None = None) -> list[dict]:
    """Mede peças sozinhas, com os parâmetros que o plano dá, num navegador só. `pecas` é a lista de
    (peca, q, ar): q é o dict de parâmetros (`{"l": "Conteúdo@0.3", "kick": ...}`), ar "1920x1080"
    (None = o da peça). Devolve, por peça, o que `V2QA.geometria` lê no instante `t` (padrão: metade da
    duração, com tudo já entrado e nada saindo, o 1º instante do `qa`): caixa visível, cada texto com
    caixa em px do quadro e linhas, achados do `qa` e overflow. Roda a regra de antes do render."""
    from playwright.sync_api import sync_playwright
    qa_js = (AQUI / "nucleo" / "qa.js").read_text(encoding="utf-8")
    out = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=NAVEGADOR)
        try:
            for peca, q, ar in pecas:
                t0 = time.time()
                p, ar, query = pedido(peca, [f"{k}={v}" for k, v in (q or {}).items()], ar)
                W, H = (int(x) for x in ar.split("x"))
                ctx = nav.new_context(viewport={"width": W, "height": H})
                rede_local(ctx)
                pg = ctx.new_page()
                r: dict = {"peca": peca, "q": q or {}, "ar": ar}
                try:
                    pg.goto((AQUI / p["arquivo"]).as_uri() + "?" + query)
                    pg.wait_for_function("window.__tl && window.__ready === true", timeout=30000)
                    carrega_fontes(pg)
                    pg.add_script_tag(content=qa_js)
                    dur = pg.evaluate("() => +window.__duration")
                    r["dur"], r["t"] = dur, round(dur * .5 if t is None else t, 3)
                    o = {"seguro": zona_segura(W, H), "player": round(H * (1 - 184 / 1080)) if W * 9 == H * 16 else None,
                         "rosto": [1440, 760, 1880, 1040] if W * 9 == H * 16 else None}
                    r["seguro"] = o["seguro"]
                    r.update(pg.evaluate("([t, o]) => { window.__tl.time(t, false); return V2QA.geometria(window, o); }", [r["t"], o]))
                except Exception as e:
                    r["erro"] = str(e).splitlines()[0][:200]
                ctx.close()
                r["ms"] = int((time.time() - t0) * 1000)
                out.append(r)
        finally:
            nav.close()
    return out


def cmd_mede(a):
    """`v2.py mede k_frase --q '{"l": "Conteúdo@0.3", "kick": "..."}' --ar 1920x1080`: JSON da `mede`."""
    r = mede([(a.peca, json.loads(a.q), a.ar)], a.t)[0]
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(1 if "erro" in r else 0)


# ───────────────────────── render ─────────────────────────
def _query(base_q: str, pares: list[str], extra: dict) -> str:
    q = dict(parse_qsl(base_q, keep_blank_values=True))
    for kv in pares:
        k, _, v = kv.partition("=")
        q[k] = v
    q.update({k: v for k, v in extra.items() if v is not None})
    return urlencode(q)


# Rastro (motion blur): cada quadro é a média de 4 de 8 subquadros (obturador de 180°), com o
# alfa pré-multiplicado — sem isso a borda que anda mistura cor com o preto do transparente e
# vira franja escura. A 120 qps o rastro sai em cópias separadas; a 240, corre (AN2, 03/10).
SUBQUADROS = 8


def pedido(peca: str, pares: list[str], ar: str | None = None, tema: str | None = None,
           camada: str | None = None) -> tuple[dict, str, str]:
    """(entrada do catálogo, formato, query inteira) de um pedido de render."""
    p, qv = acha(peca)
    ar = ar or p["formato"]
    return p, ar, _query(qv, pares, {"ar": ar, "tema": tema, "camada": camada})


def render(peca: str, pares: list[str], out: Path, ar: str | None = None, tema: str | None = None,
           camada: str | None = None, fps: int = 30, alfa: bool = True, rastro: bool = False) -> dict:
    """Renderiza a peça em `out` (.mov sem perda com alfa, ou mp4 com `alfa=False`) e grava `out.json`.
    É o lote de uma peça só: veja `render_lote`."""
    return render_lote([dict(peca=peca, pares=pares, out=out, ar=ar, tema=tema, camada=camada,
                             fps=fps, alfa=alfa, rastro=rastro)])[0]


def render_lote(pedidos: list[dict]) -> list[dict]:
    """Renderiza várias peças, cada pedido com as chaves de `render` (`peca`, `out` e as opcionais),
    e devolve o meta de cada um, na ordem.

    Por dentro: a peça com o mesmo pedido sai do cache (`CACHE`, um só pra todo vídeo), a repetida
    no lote renderiza uma vez, e o que falta abre UM navegador pro lote inteiro, com até `JUNTAS`
    peças ao mesmo tempo, cada uma dividida em até `PAGINAS` páginas."""
    import asyncio
    trabalho, falta = [], {}
    for ped in pedidos:
        peca, camada = ped["peca"], ped.get("camada")
        fps, alfa, rastro = ped.get("fps") or 30, ped.get("alfa", True), ped.get("rastro", False)
        p, ar, q = pedido(peca, ped.get("pares") or [], ped.get("ar"), ped.get("tema"), camada)
        if dict(parse_qsl(q)).get("tema") == "marca" and not MARCA_CSS.is_file():
            sys.exit(f"o tema marca pede {MARCA_CSS}, que não existe: instale o pacote de marca ou troque o tema")
        chave = chave_render(p, q, fps, alfa, rastro)
        guardado = CACHE / f"{chave}{'.mov' if alfa else '.mp4'}"
        trabalho.append((ped, guardado))
        if guardado.is_file() and guardado.with_suffix(".json").is_file():
            print(f"  {peca}: do cache ({chave})")
        elif guardado not in falta:
            W, H = (int(x) for x in ar.lower().split("x"))
            falta[guardado] = (p, q, W, H, fps, alfa, rastro, guardado, peca + (f"·{camada}" if camada else ""),
                               {"peca": peca, "query": q, "fps": fps, "formato": ar})

    async def tudo():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            nav = await _navegador(pw)
            vez = asyncio.Semaphore(JUNTAS)

            async def uma(*args):
                async with vez:
                    meta = await _captura(nav, *args[:-1])
                meta.update(args[-1])
                args[7].with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            try:
                await asyncio.gather(*[uma(*args) for args in falta.values()])
            finally:
                await nav.close()

    if falta:
        CACHE.mkdir(parents=True, exist_ok=True)
        asyncio.run(tudo())
    metas = []
    for ped, guardado in trabalho:
        out = Path(ped["out"])
        meta = json.loads(guardado.with_suffix(".json").read_text(encoding="utf-8"))
        _entrega(guardado, out)
        out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out}  ({meta['duracao']:.2f}s, {len(meta['cues'])} cues)")
        metas.append(meta)
    if falta:
        _poda_cache()
    return metas


# ───────────────────────── cache de render ─────────────────────────
# Um só pra todo vídeo: a peça igual, com o mesmo pedido, renderiza uma vez. A chave é o
# conteúdo do que desenha (o HTML da peça, os arquivos do núcleo que ela inclui, a folha da
# marca, as imagens que a query aponta) mais o pedido. O código deste arquivo NÃO entra:
# mexer no v2.py não joga fora render bom. Se o jeito de gravar o quadro mudar, sobe o FORMATO.
CACHE = Path(os.environ.get("V2_CACHE") or Path.home() / ".cache" / "obs-optimize" / "v2-pecas")
CACHE_GB = float(os.environ.get("V2_CACHE_GB", "20"))   # 40 GB encheu o disco do dono em 11/2026
FORMATO = "1"
PAGINAS = 4          # páginas do mesmo navegador dividindo os quadros de uma peça
JUNTAS = 2           # peças do lote fotografadas ao mesmo tempo: enquanto uma grava, a outra fotografa
QUADROS_POR_PAGINA = 45   # peça curta não paga abrir página à toa


def _do_nucleo(html: str, base: Path, vistos: set[Path]) -> None:
    """Os arquivos locais que um HTML ou CSS inclui (src, href, url(), import), recursivo."""
    import re
    for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"'#?]+)|url\(\s*["']?([^"')#?]+)|import\s*\(?\s*["']([^"'#?]+)""", html):
        ref = next(g for g in m.groups() if g)
        if "://" in ref or ref.startswith(("data:", "#")):
            continue
        arq = (base / ref).resolve()
        if arq in vistos or not arq.is_file():
            continue
        vistos.add(arq)
        if arq.suffix in (".css", ".js", ".html"):
            _do_nucleo(arq.read_text(encoding="utf-8", errors="replace"), arq.parent, vistos)


def dependencias(p: dict, q: str = "") -> list[Path]:
    """Todo arquivo que decide o desenho da peça: o HTML, o que ele inclui do núcleo (e o
    que esses incluem), a folha da marca no tema marca e os arquivos que a query aponta."""
    html = AQUI / p["arquivo"]
    vistos = {html.resolve()}
    _do_nucleo(html.read_text(encoding="utf-8"), html.parent, vistos)
    if dict(parse_qsl(q)).get("tema") == "marca" and MARCA_CSS.is_file():
        vistos.add(MARCA_CSS.resolve())
    for _, v in parse_qsl(q, keep_blank_values=True):
        for parte in v.split(","):
            try:
                if parte.startswith("file://"):      # a imagem do painel (e_dividida, r_print) vem como URI: entra na chave pelo conteúdo
                    from urllib.parse import urlparse
                    from urllib.request import url2pathname      # no Windows: /D:/x vira D:\x
                    parte = url2pathname(urlparse(parte).path)
                arq = Path(parte.lstrip("@"))
                if arq.is_absolute() and arq.is_file():
                    vistos.add(arq)
            except (OSError, ValueError):
                pass
    # ponytail: pasta na query (pasta=…/cartas) não entra; a imagem que a peça monta com ela, sim,
    # só se vier por caminho inteiro. Trocar a imagem no lugar, com o mesmo nome, serve o render velho.
    return sorted(vistos)


def chave_render(p: dict, q: str, fps: int, alfa: bool, rastro: bool) -> str:
    import hashlib
    h = hashlib.blake2b(digest_size=12)
    h.update(json.dumps([FORMATO, q, fps, alfa, rastro]).encode())
    for arq in dependencias(p, q):
        h.update(arq.name.encode())
        h.update(arq.read_bytes())
    return h.hexdigest()


def _entrega(guardado: Path, out: Path) -> None:
    """O render vai pro lugar pedido como link (não ocupa disco duas vezes); cópia se não der."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    try:
        os.link(guardado, out)
    except OSError:
        shutil.copyfile(guardado, out)
    # o uso conta pra poda no .json do cache: o .mov é o mesmo inode do link na pasta do vídeo,
    # e mexer no instante dele faria a fábrica achar que a peça mudou
    guardado.with_suffix(".json").touch()


def encolhe(mov: Path, acima: float = 100e6) -> None:
    """Peça com vídeo ou foto dentro o RLE não comprime: 4 s davam 870 MB. Nela o ProRes 4444 do
    hardware do Mac sai 2,5 a 4× menor, com o alfa idêntico e 50 dB na cor (medido em 07/11/2026).
    Na peça chapada ele sai 3× maior, por isso só acima de `acima` bytes e só se ficar menor. Sem o
    codificador (Windows, Linux, Mac Intel) o ffmpeg falha e fica o Animation."""
    if mov.stat().st_size <= acima:
        return
    pr = mov.with_name(f"{mov.stem}.pr{mov.suffix}")
    r = ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(mov), "-c:v", "prores_videotoolbox",
                "-profile:v", "4444", "-pix_fmt", "bgra", str(pr)], quiet=True, check=False)
    if r.returncode == 0 and pr.exists() and pr.stat().st_size < mov.stat().st_size:
        pr.replace(mov)
    pr.unlink(missing_ok=True)


def _poda_cache() -> None:
    """Passou do teto: sai o que foi usado há mais tempo. O link na pasta do vídeo sobrevive."""
    uso = lambda a: a.with_suffix(".json").stat().st_mtime if a.with_suffix(".json").exists() else 0
    arqs = sorted((a for a in CACHE.glob("*") if a.suffix in (".mov", ".mp4") and ".parcial." not in a.name), key=uso)   # o parcial de outro render em andamento não é cache: podar ele derrubava o `replace` do dono
    total = sum(a.stat().st_size for a in arqs)
    while arqs and total > CACHE_GB * 1e9:
        a = arqs.pop(0)
        total -= a.stat().st_size
        a.unlink(missing_ok=True)
        a.with_suffix(".json").unlink(missing_ok=True)


# ───────────────────────── rede local ─────────────────────────
# GSAP e as fontes do Google vinham da internet a cada página aberta. Agora a primeira
# vez baixa e guarda em rede/; dali em diante o render roda sem internet.
REDE = AQUI / "rede"
DE_FORA = ("https://cdnjs.cloudflare.com/", "https://fonts.googleapis.com/", "https://fonts.gstatic.com/")


def _local(url: str) -> Path:
    import hashlib
    ext = {"googleapis": ".css", "gstatic": ".woff2"}.get(next((k for k in ("googleapis", "gstatic") if k in url), ""), ".js")
    return REDE / (hashlib.blake2b(url.encode(), digest_size=10).hexdigest() + ext)


TIPOS = {".css": "text/css", ".js": "application/javascript", ".woff2": "font/woff2"}


def _guarda(arq: Path, corpo: bytes) -> None:
    """Escreve e renomeia: outro render lendo ao mesmo tempo nunca vê o arquivo pela metade."""
    REDE.mkdir(exist_ok=True)
    tmp = arq.with_name(f"{arq.name}.{os.getpid()}.tmp")
    tmp.write_bytes(corpo)
    tmp.replace(arq)


SEM_REDE = "sem internet e sem cópia em tools/v2/rede: {}"


async def _serve_local(route) -> None:
    arq = _local(route.request.url)
    if not arq.is_file():
        try:
            r = await route.fetch()
        except Exception:
            print("  " + SEM_REDE.format(route.request.url))
            return await route.abort()
        if not r.ok:
            return await route.fulfill(response=r)
        _guarda(arq, await r.body())
    await route.fulfill(body=arq.read_bytes(), content_type=TIPOS[arq.suffix],
                        headers={"access-control-allow-origin": "*"})


def _serve_local_sync(route) -> None:
    arq = _local(route.request.url)
    if not arq.is_file():
        try:
            r = route.fetch()
        except Exception:
            print("  " + SEM_REDE.format(route.request.url))
            return route.abort()
        if not r.ok:
            return route.fulfill(response=r)
        _guarda(arq, r.body())
    route.fulfill(body=arq.read_bytes(), content_type=TIPOS[arq.suffix],
                  headers={"access-control-allow-origin": "*"})


def rede_local(alvo, sync: bool = True) -> None:
    """Liga o espelho local num contexto ou página do Playwright."""
    for prefixo in DE_FORA:
        alvo.route(prefixo + "**", _serve_local_sync if sync else _serve_local)


# ───────────────────────── página ─────────────────────────
# Todo navegador do repo abre por aqui: o render de peça, a peça parada (a capa) e a página filmada
# quadro a quadro (a receita). A mesma espera de fonte e a mesma rede local pra todos.
# --allow-file-access-from-files: textura WebGL (three.js) a partir de imagem em file:// cai em SecurityError sem ela
NAVEGADOR = ["--force-color-profile=srgb", "--disable-lcd-text", "--allow-file-access-from-files"]

# O JS de esperar a fonte, separado pra quem abre a página pela API assíncrona (o render).
FONTES_PUXA = "() => Promise.all([...document.fonts].map(f => f.load().catch(() => null)))"
FONTES_ESPERA = "() => [...document.fonts].every(f => f.status !== 'loading')"
FONTES_RUINS = ("() => [...document.fonts].filter(f => f.status === 'error')"
                ".map(f => `${f.family} ${f.weight}`)")


def carrega_fontes(page) -> None:
    """Puxa TODA face declarada antes de começar a saltar no tempo.

    O Google só busca a face quando um glifo precisa dela, e no t=0 os elementos estão com
    opacity:0 — ninguém pinta, nada é pedido. Ao saltar pra 4,6s e fotografar na hora, o pedido
    sai e a foto acontece antes da fonte chegar: o Chromium mede a caixa certa e desenha os glifos
    empilhados. O PNG sai com a palavra amassada e o layout parecendo correto, então o defeito só
    aparece olhando o vídeo pronto."""
    page.evaluate(FONTES_PUXA)
    page.wait_for_function(FONTES_ESPERA, timeout=30000)
    ruins = page.evaluate(FONTES_RUINS)
    if ruins:
        sys.exit("fonte falhou: " + ", ".join(ruins))


@contextmanager
def pagina(url: str, W: int, H: int, pronto: str = "window.__tl && window.__ready === true",
           escala: int = 1, args: tuple[str, ...] = ()):
    """Uma página aberta em `url`, pronta (`pronto`) e com as fontes carregadas; fecha na saída."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=[*NAVEGADOR, *args])
        try:
            ctx = nav.new_context(viewport={"width": W, "height": H}, device_scale_factor=escala)
            rede_local(ctx)
            pg = ctx.new_page()
            pg.goto(url)
            pg.wait_for_function(pronto, timeout=30000)
            carrega_fontes(pg)
            yield pg
        finally:
            nav.close()


def filma(pg, n: int, busca: str, pasta: Path, rotulo: str = "") -> None:
    """Fotografa `n` quadros da página em `pasta`/f_00000.png…: antes de cada um, `busca(i)` leva a
    página ao quadro i. O print sai pelo CDP com o PNG rápido, que é sem perda."""
    import base64
    cdp = pg.context.new_cdp_session(pg)
    t0 = time.time()
    for i in range(n):
        pg.evaluate(busca, i)
        r = cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True})
        (pasta / f"f_{i:05d}.png").write_bytes(base64.b64decode(r["data"]))
        if i % 30 == 0:
            print(f"  {rotulo or 'quadro'} {i}/{n}  {time.time() - t0:.1f}s")


def quadro(peca: str, pares: list[str], out: Path, tema: str | None = None, t: float = 0.5,
           tam: tuple[int, int] = (1080, 1920), escala: int = 1, quality: int = 93, alfa: bool = False) -> Path:
    """A peça parada no instante `t`, direto num JPEG (o mp4 do render passaria a cor por 4:2:0 duas
    vezes). `escala` multiplica os pixels sem mudar o desenho (2: a capa 16:9 em 3840×2160)."""
    p, qv = acha(peca)
    w, h = tam
    url = (AQUI / p["arquivo"]).as_uri() + "?" + _query(qv, pares, {"ar": f"{w}x{h}", "tema": tema})
    with pagina(url, w, h, escala=escala) as pg:
        pg.evaluate(f"() => {{ window.__tl.time({t}); }}")   # devolver a timeline trava o playwright
        if alfa:   # PNG com fundo transparente: o storyboard põe a peça por cima do quadro do corte seco
            pg.screenshot(path=str(out), type="png", omit_background=True)
        else:
            pg.screenshot(path=str(out), type="jpeg", quality=quality)
    print(f"wrote {out}")
    return out


# ───────────────────────── captura ─────────────────────────
# `seeked` chega antes do quadro novo ir pra tela: na página que abre um trecho no meio da timeline, o vídeo
# saía preto por 3 a 6 quadros (carrossel 04/11, cartões 07 e 08). O requestVideoFrameCallback espera o quadro.
BUSCA = ("(t)=>{window.__tl.time(t); const vs = (window.D && D._videos) || [];"
         " return Promise.all(vs.map(v => v.seeking ? new Promise(r => {"
         " v.addEventListener('seeked', () => v.requestVideoFrameCallback ? v.requestVideoFrameCallback(() => r()) : r(),"
         " {once: true}); setTimeout(r, 3000); }) : null));}")


async def _navegador(pw):
    return await pw.chromium.launch(args=NAVEGADOR)


async def _captura(nav, p: dict, q: str, W: int, H: int, fps: int, alfa: bool, rastro: bool, destino: Path,
                   rotulo: str) -> dict:
    """Fotografa a timeline da peça no navegador `nav` e grava o vídeo em `destino`. Os quadros são
    divididos em trechos contíguos entre as páginas; o print sai pelo CDP com a compressão rápida do
    PNG, que é sem perda: muda o tamanho do arquivo, não o pixel."""
    import asyncio, base64

    url = (AQUI / p["arquivo"]).as_uri() + "?" + q
    k = SUBQUADROS if rastro else 1
    quadros = Path(tempfile.mkdtemp(prefix="v2_"))

    async def abre():
        ctx = await nav.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        for prefixo in DE_FORA:
            await ctx.route(prefixo + "**", _serve_local)
        pg = await ctx.new_page()
        await pg.goto(url)
        await pg.wait_for_function("window.__tl && window.__ready === true", timeout=30000)
        await pg.wait_for_timeout(300)
        await pg.evaluate(FONTES_PUXA)
        await pg.wait_for_function(FONTES_ESPERA, timeout=30000)
        ruins = await pg.evaluate(FONTES_RUINS)
        if ruins:
            raise RuntimeError("fonte falhou: " + ", ".join(ruins))
        cdp = await ctx.new_cdp_session(pg)
        if alfa:
            await cdp.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
        return ctx, pg, cdp

    async def fotografa(pg, cdp, trecho, t0):
        if trecho.start:   # página que abre no meio: o vídeo ainda não decodificou ali e saía preto (carrossel 07, 04/11)
            await pg.evaluate(BUSCA, trecho.start / (fps * k))
            await asyncio.sleep(0.8)
        for n, i in enumerate(trecho):
            await pg.evaluate(BUSCA, i / (fps * k))
            r = await cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True})
            (quadros / f"f_{i:05d}.png").write_bytes(base64.b64decode(r["data"]))
            if trecho.start == 0 and n % 60 == 0:
                print(f"  {rotulo}  {i}/{trecho.stop}  {time.time() - t0:.1f}s")

    def grava():
        # Animation (qtrle): o pixel do navegador sem perda, com alfa. Peça é cor chapada e fundo
        # vazio, que o RLE comprime bem: contra o ProRes 4444 de antes, 10× mais rápido de gravar
        # e 18× menor (45 MB contra 828 MB em 15 s do g_jogada, medido em 07/10).
        cod = (["-c:v", "qtrle", "-pix_fmt", "argb"] if alfa else
               ["-c:v", ff.CODEC_VIDEO, "-pix_fmt", ff.PIX_FMT, "-crf", "17", "-movflags", "+faststart"])
        mistura = []
        if rastro:
            m = f"tmix=frames={SUBQUADROS // 2},framestep={SUBQUADROS}"
            mistura = ["-vf", f"premultiply=inplace=1,{m},unpremultiply=inplace=1" if alfa else m, "-r", str(fps)]
        parcial = destino.with_name(f"{destino.stem}.{os.getpid()}.parcial{destino.suffix}")
        ff.run(["ffmpeg", "-y", "-framerate", str(fps * k), "-i", str(quadros / "f_%05d.png"), *mistura, *cod,
                str(parcial)], quiet=True)
        if alfa:
            encolhe(parcial)
        parcial.replace(destino)

    paginas = []
    try:
        ctx, pg, cdp = await abre()
        paginas.append(ctx)
        meta = await pg.evaluate("({duracao: window.__duration, cues: window.__cues || [],"
                                 " pessoa: window.__pessoa || null, video: window.__video || []})")
        total = int(meta["duracao"] * fps) * k + 1
        n = max(1, min(PAGINAS, total // QUADROS_POR_PAGINA))
        cortes = [total * j // n for j in range(n + 1)]
        outras = await asyncio.gather(*[abre() for _ in range(n - 1)])
        paginas += [o[0] for o in outras]
        t0 = time.time()
        await asyncio.gather(*[fotografa(pg_, cdp_, range(cortes[j], cortes[j + 1]), t0)
                               for j, (pg_, cdp_) in enumerate([(pg, cdp), *[(o[1], o[2]) for o in outras]])])
        for c in paginas:
            await c.close()
        paginas = []
        # o encode corre fora do laço: a outra peça do lote segue fotografando
        await asyncio.to_thread(grava)
    finally:
        for c in paginas:
            await c.close()
        shutil.rmtree(quadros, ignore_errors=True)
    return meta


def _do_render(a) -> dict:
    """Os argumentos do `render` como pedido de `render_lote`."""
    return dict(peca=a.peca, pares=(da_mesa(a.mesa, a.peca) if a.mesa else []) + a.pares,
                out=Path(a.out or (a.peca + ".mov")), ar=a.ar, tema=a.tema, camada=a.camada, fps=a.fps,
                alfa=not a.opaco, rastro=a.rastro)


def cmd_render(a):
    render_lote([_do_render(a)])


def cmd_lote(a):
    """Um JSON com a lista de pedidos, cada um os argumentos do `render` ([peca, k=v…, --out x]):
    é o que a fábrica manda pra renderizar as peças de um vídeo num navegador só."""
    ap = _parser()
    render_lote([_do_render(ap.parse_args(["render", *args]))
                 for args in json.loads(Path(a.pedidos).read_text(encoding="utf-8"))])


# ───────────────────────── mesa ─────────────────────────
# O Studio web do HyperFrames (Apache 2.0, roteiros/hyperframes-studio/ESTUDO.md) ajusta a peça
# vendo: os parâmetros dela viram as "variáveis" dele, e o núcleo lê as duas fontes. A mesa é uma
# pasta à parte porque o Studio carimba data-hf-id em tudo que abre; o render final volta pra cá,
# pelo `render --mesa`, com a peça da biblioteca e os valores que o Studio gravou.
HYPERFRAMES = "0.8.137"   # fixa, nunca @latest: a HeyGen solta versão quase todo dia


def cmd_mesa(a):
    import html, re
    p, qv = acha(a.peca)
    W, H = (int(x) for x in p["formato"].split("x"))
    vals = dict(parse_qsl(_query(p["exemplo"].lstrip("?"), [], {}) + "&" + _query(qv, a.pares, {}), keep_blank_values=True))
    decl = [{"id": k, "type": "string", "label": k, "default": v} for k, v in vals.items()]
    # o Studio serve a pasta como raiz e não sobe com ../: ../nucleo/ vira nucleo/, que é um link
    s = re.sub(r"""(["'`(])\.\./""", r"\1", (AQUI / p["arquivo"]).read_text(encoding="utf-8"))
    i = s.index("<html", s.find("-->") + 1)   # depois do cabeçalho, que pode citar <html>
    s = s[:i] + f'<html data-composition-variables="{html.escape(json.dumps(decl, ensure_ascii=False))}"' + s[i + 5:]
    s = s.replace('id="stage"', f'id="stage" data-composition-id="{a.peca}" data-width="{W}" data-height="{H}"', 1)
    reg = ("<script>window.__timelines = window.__timelines || {};"
           f" (function r() {{ if (window.__ready) window.__timelines[{json.dumps(a.peca)}] = window.__tl;"
           " else setTimeout(r, 10); })();</script>\n")
    i = s.rfind("</body>")
    s = s[:i] + reg + s[i:] if i >= 0 else s + reg
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "index.html").write_text(s, encoding="utf-8")
    for d in ("nucleo", "midia", "vivo"):
        if not (pasta / d).exists():
            (pasta / d).symlink_to(AQUI / d)
    print(f"wrote {pasta / 'index.html'}  ({len(decl)} variáveis: {', '.join(vals) or '—'})")
    print(f"  abra:   HYPERFRAMES_NO_TELEMETRY=1 npx --yes hyperframes@{HYPERFRAMES} preview {pasta} --port 3790")
    print(f"  render: v2.py render {a.peca} --mesa {pasta} --out {a.peca}.mov")


def da_mesa(pasta: str, peca: str) -> list[str]:
    """Os valores que o Studio gravou na mesa, como pares k=v (os da linha de comando ganham)."""
    import html, re
    s = (Path(pasta) / "index.html").read_text(encoding="utf-8")
    dono = re.search(r'data-composition-id="([^"]+)"', s)
    if not dono or dono.group(1) != peca:
        sys.exit(f"a mesa {pasta} é de {dono.group(1) if dono else '?'}, não de {peca}")
    m = re.search(r"""data-composition-variables=(?:"([^"]*)"|'([^']*)')""", s)
    decl = json.loads(html.unescape(m.group(1) if m.group(1) is not None else m.group(2))) if m else []
    return [f"{v['id']}={v['default']}" for v in decl if "default" in v]


def cmd_camadas(a):
    """As duas camadas de uma peça de ensaio + um JSON só, que o `compor` lê."""
    p, _ = acha(a.peca)
    if not p["camadas"]:
        sys.exit(f"{a.peca} não é em camadas — use `render`")
    base = Path(a.out)
    meta = None
    for c in ("tras", "frente"):
        meta = render(a.peca, a.pares, base.with_suffix(f".{c}.mov"), a.ar, a.tema, c, a.fps)
        base.with_suffix(f".{c}.json").unlink(missing_ok=True)
    meta["camadas"] = {c: str(base.with_suffix(f".{c}.mov")) for c in ("tras", "frente")}
    base.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {base.with_suffix('.json')}")


# ───────────────────────── sobre ─────────────────────────
# Peça por cima do vídeo, num encode só. Todo chamador que põe peça sobre vídeo (o explicador
# da aula, a legenda da fábrica) passa por aqui: a peça renderizada entra como mais uma entrada
# do ffmpeg e o overlay nativo a põe no lugar e no instante. A entrada, a saída e a sombra
# moram na peça; aqui não se desenha nada.
def grafo_sobre(pecas: list[dict], base: str, primeira: int) -> tuple[list[str], list[str], str]:
    """(entradas do ffmpeg, filtros, rótulo da saída) das peças sobre o rótulo `base`.

    Cada peça: `arquivo` (o render), `em` (segundo do vídeo em que ela está no quadro 0 dela),
    `ate` (some depois disto; sem ele, até o fim do arquivo), `x`/`y` (canto de cima), `largura`
    (escala, a altura segue; com `altura`, as duas), `altura_max` (corta no meio da altura) e `inicio` (pula o começo
    do arquivo), `pip` (`{x,y,w,h,recorte:[cx,cy,cw,ch]}` em fração do quadro e da fonte: o recorte do vídeo vira um cartão
    por cima da peça, que desenha a moldura; pede `largura` e `altura`). A peça mais curta que a janela segura o último quadro (`segura: false`: some)."""
    entradas, fs, ult = [], [], base
    for k, pc in enumerate(pecas):
        i, em = primeira + k, float(pc["em"])
        if pc.get("inicio"):
            entradas += ["-ss", f"{float(pc['inicio']):.3f}"]
        entradas += ["-i", str(pc["arquivo"])]
        cad = []
        if pc.get("largura"):
            alto = int(pc["altura"]) if pc.get("altura") else -2
            cad.append(f"scale={int(pc['largura'])}:{alto}:flags=lanczos")
        if pc.get("altura_max"):
            h = int(pc["altura_max"])
            cad.append(f"crop=iw:'min(ih,{h})':0:'(ih-min(ih,{h}))/2'")
        # meio milissegundo antes: `em` no quadro (2/30 = 0,0666…) arredondado pra cima deixava o
        # quadro da peça um depois do vídeo; assim o quadro i da peça cai no quadro em+i, sem folga
        em -= .0005
        cad += ["format=yuva444p", f"setpts=PTS-STARTPTS+{em:.6f}/TB"]
        fs.append(f"[{i}:v]{','.join(cad)}[p{k}]")
        ate = pc.get("ate")
        janela = f"between(t,{em:.6f},{float(ate) - .0005:.6f})" if ate is not None else f"gte(t,{em:.6f})"
        fim = "repeat" if ate is not None and pc.get("segura", True) else "pass"
        pip = pc.get("pip")
        if pip:   # ele na tela: o recorte do próprio vídeo entra no cartão que a peça desenhou
            W, H = int(pc["largura"]), int(pc["altura"])
            cx, cy, cw, ch = pip["recorte"]
            px, py, pw, ph = (round(pip[c] * m) // 2 * 2 for c, m in (("x", W), ("y", H), ("w", W), ("h", H)))
            fs.append(f"[{ult}]split[ua{k}][ub{k}]")
            fs.append(f"[ub{k}]crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy},scale={pw}:{ph}:flags=lanczos[pv{k}]")
            fs.append(f"[ua{k}][p{k}]overlay={int(pc.get('x', 0))}:{int(pc.get('y', 0))}:"
                      f"enable='{janela}':eof_action={fim}:format=auto[q{k}]")
            fs.append(f"[q{k}][pv{k}]overlay={px}:{py}:enable='{janela}'[s{k}]")
        else:
            fs.append(f"[{ult}][p{k}]overlay={int(pc.get('x', 0))}:{int(pc.get('y', 0))}:"
                      f"enable='{janela}':eof_action={fim}:format=auto[s{k}]")
        ult = f"s{k}"
    return entradas, fs, ult


def sobre(video: Path, pecas: list[dict], out: Path, qualidade: str = "reel") -> Path:
    """O vídeo com as peças por cima. Só o grupo de quadros em volta de cada peça é recodificado (num
    encode só, as peças da janela juntas); o resto é copiado da entrada, como a emenda faz com o
    glitch. Peça sem `ate` vale até o fim do arquivo dela."""
    import emenda
    if not pecas:
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-c", "copy", str(out)], quiet=True)
        return out
    video, out = Path(video), Path(out)
    fim = lambda pc: float(pc["ate"]) if pc.get("ate") is not None else (
        float(pc["em"]) + ff.dur(pc["arquivo"]) - float(pc.get("inicio") or 0))
    # as janelas que se tocam viram uma: a emenda recusa trecho sobreposto
    janelas: list[list[float]] = []
    for a, b in sorted((float(pc["em"]), fim(pc)) for pc in pecas):
        if janelas and a <= janelas[-1][1]:
            janelas[-1][1] = max(janelas[-1][1], b)
        else:
            janelas.append([a, b])
    dur = ff.dur(video)
    trechos = [emenda.Trecho(max(0.0, a), min(b, dur), f"p{i}") for i, (a, b) in enumerate(janelas) if a < dur]
    plano = emenda.planeja(video, trechos, out)
    trab = out.parent / f"_sobre_{out.stem}"
    trab.mkdir(parents=True, exist_ok=True)
    prontos = {}
    for pd in (p for p in plano.pedacos if not p.copia):
        dentro = [{**pc, "em": float(pc["em"]) - pd.inicio,
                   **({"ate": float(pc["ate"]) - pd.inicio} if pc.get("ate") is not None else {})}
                  for pc in pecas if float(pc["em"]) < pd.fim and fim(pc) > pd.inicio]
        entradas, fs, ult = grafo_sobre(dentro, "0:v", 1)
        prontos[pd.nome] = trab / f"{pd.nome}.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", *emenda.recorte(pd), "-i", str(video),
                *entradas, "-filter_complex", ";".join(fs + [f"[{ult}]format={ff.PIX_FMT}[vout]"]),
                "-map", "[vout]", "-an", *ff.args_video(qualidade, fps=None),   # o som sai da fonte, na emenda
                # a peça que segura o último quadro esticava a janela em um quadro
                "-frames:v", str(plano.quadros(pd)), str(prontos[pd.nome])], quiet=True)
    emenda.executa(plano, prontos)
    shutil.rmtree(trab, ignore_errors=True)
    shutil.rmtree(out.parent / f"_emenda_{out.stem}", ignore_errors=True)
    return out


# ───────────────────────── compor ─────────────────────────
# Pilha, tudo no mesmo t:  take (reenquadrado + efeitos) → tras → pessoa → frente.
# `pessoa` é o recorte ALFA do próprio take (HeyGen sem fundo, rembg…): recebe a
# mesma geometria e os mesmos efeitos de cor do take, menos o desfoque — é o
# que faz "desfocar só o fundo" funcionar.
CENTRO_X = 610          # x da pessoa centralizada, no quadro da peça (ensaio.js)
SOBE = .5               # quanto o `empurra` leva pra chegar (s)
IO = "(if(lt({k},.5),4*pow({k},3),1-pow(-2*{k}+2,3)/2))"   # ease-in-out cúbico


def _k_janela(a: float, b: float, dur: float = .6, t: str = "it") -> str:
    """0→1 em `dur` a partir de a, 1→0 em `dur` antes de b."""
    ki = f"clip(({t}-{a:.3f})/{dur},0,1)"
    ko = f"clip(({b:.3f}-{t})/{dur},0,1)"
    return f"min({IO.format(k=ki)},{IO.format(k=ko)})"


def _cartao(meta: dict) -> dict | None:
    """O enquadramento do cartão (e_editorial), se a peça pediu. Um só por peça."""
    cs = [e for e in meta.get("video", []) if e["efeito"] == "cartao"]
    if not cs:
        return None
    geo = lambda e: tuple(e[k] for k in ("x", "y", "w", "h", "raio", "escala", "topo"))
    if any(geo(e) != geo(cs[0]) for e in cs):
        sys.exit("cartões com enquadramento diferente na mesma peça: o compor só sabe um")
    return {**cs[0], "trechos": [(e["t0"], e["t1"]) for e in cs]}


def mascara_cartao(c: dict, destino: Path) -> Path:
    """Branco no cartão, preto fora. Só os cantos de cima arredondam: o de baixo
    sangra pra fora do quadro (o e_editorial). Com `cantos: "todos"`, o cartão solto no
    meio da tela (ve_tese layout=cartao) arredonda os quatro. Desenhado 4× e reduzido,
    pra borda não serrilhar."""
    from PIL import Image, ImageDraw
    k, w, h, r = 4, int(c["w"]), int(c["h"]), int(c["raio"])
    im = Image.new("L", (w * k, h * k), 0)
    pe = h * k - 1 if c.get("cantos") == "todos" else (h + r) * k
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, pe), radius=r * k, fill=255)
    im.resize((w, h), Image.LANCZOS).save(destino)
    return destino


def grafo(meta: dict, em: float, W: int, H: int, folga: float, com_pessoa: bool,
          i_mascara: int | None = None, fontes: tuple[int, int] | None = None) -> tuple[str, str]:
    """`fontes`: os qps do take e da pessoa, que a ff.taxa leva aos da peça."""
    dur = meta["duracao"]
    fps = meta.get("fps", 30)
    fontes = fontes or (fps, fps)
    ef = [{**e, "t0": e["t0"] + em, "t1": e["t1"] + em} for e in meta.get("video", [])]
    um = lambda n: next((e for e in ef if e["efeito"] == n), None)

    # Geometria num filtro só, com saída de tamanho FIXO (perspective + scale W×H):
    # mudar o tamanho do quadro no meio do vídeo é o que fazia a escada do crop no
    # captions_viral. O take aberto é ampliado `folga` vezes e a janela desliza
    # até a pessoa cair onde a peça quer. A folga cresce sozinha se o deslize
    # pedir mais margem do que ela dá.
    pes = meta.get("pessoa") or {}
    dx = (pes.get("x", CENTRO_X) - CENTRO_X) if pes.get("lado") not in (None, "centro") else 0
    folga = max(folga, 1 + 2 * abs(dx) / W) if dx else folga
    # zoom: um trecho ou vários (o rosto cheio do e_editorial pede um por cena, em
    # corte seco: entra 0). Fora de todos, 1.
    # O tempo é o quadro de entrada (`in`): o perspective não tem `t`, e antes dele o take já
    # está na taxa da peça (cadeia).
    t = f"(in/{fps})"
    z = "1"
    for zm in reversed([e for e in ef if e["efeito"] == "zoom"]):
        k = f"clip(({t}-{zm['t0']:.3f})/{max(zm.get('entra', .5), .001)},0,1)"
        # `reta` é a deriva entre dois cortes: o corte esconde a partida e a parada
        anda = k if zm.get("curva") == "reta" else f"(1-pow(1-{k},3))"
        z = (f"if(between({t},{zm['t0']:.3f},{zm['t1']:.3f}),"
             f"{zm['de']}+({zm['para']}-{zm['de']})*{anda},{z})")
    # empurra: a câmera chega junto com a peça que entra por cima — sobe `valor` em SOBE s
    # (ease-out cúbico) e volta até t1 (cosseno). Multiplica o zoom: vale dentro de qualquer cena.
    emp = "".join(
        f"+{e['valor']}*(1-pow(1-clip(({t}-{e['t0']:.3f})/{SOBE},0,1),3))"
        f"*(1+cos(PI*clip(({t}-{e['t0'] + SOBE:.3f})/{max(e['t1'] - e['t0'] - SOBE, .001):.3f},0,1)))/2"
        for e in ef if e["efeito"] == "empurra")
    Z = f"({folga}*{z}*(1{emp}))"
    # perspective, não zoompan: o zoompan arredonda a janela pro pixel, e mesmo com o scale 2× de
    # antes o passo do zoom lento oscilava 0,48 px; o perspective amostra em ponto flutuante
    # (0,06 px, medido em 03/10) e sai um pouco mais barato que o scale 2× + zoompan.
    hw, hh = f"(W/2/{Z})", f"(H/2/{Z})"
    centro = f"clip(W/2-({dx})*{_k_janela(em, em + dur, t=t)}*W/({Z}*{W}),{hw},W-{hw})"
    geo = (f"perspective=x0='{centro}-{hw}':y0='H/2-{hh}':x1='{centro}+{hw}':y1='H/2-{hh}':"
           f"x2='{centro}-{hw}':y2='H/2+{hh}':x3='{centro}+{hw}':y3='H/2+{hh}':interpolation=cubic:eval=frame,"
           f"scale={W}:{H}:flags=lanczos")

    cor = []
    pb, ds = um("pb"), um("dessatura")
    if pb:
        cor.append(f"hue=s=0:enable='between(t,{pb['t0']:.3f},{pb['t1']:.3f})'")
    if ds:
        k = f"clip((t-{ds['t0']:.3f})/{ds.get('entra', .5)},0,1)"
        cor.append(f"hue=s='if(between(t,{ds['t0']:.3f},{ds['t1']:.3f}),1-{ds['valor']}*{k},1)'")
    cg = um("congela")
    cong = (f"[{{i}}a][{{i}}b]freezeframes=first={int(cg['t0'] * fps)}:last={int(cg['t1'] * fps)}:replace={int(cg['t0'] * fps)}"
            if cg else None)

    def cadeia(entrada: str, nome: str, alfa: bool) -> list[str]:
        # Congela ANTES da geometria: congelar depois prende o deslize no meio —
        # a pessoa parava a 1/4 do caminho (medido: 612px de 1033). A taxa vem
        # primeiro porque o freezeframes conta quadro, e o take pode vir a 25.
        fonte = fontes[1] if alfa else fontes[0]
        pre = f"[{entrada}]{'format=yuva444p,' if alfa else ''}{ff.taxa(fonte, fps, alfa=nome if alfa else '')}"
        if cong:
            f = [f"{pre},split[{nome}a][{nome}b]", cong.format(i=nome) + f"[{nome}c]"]
        else:
            f = [f"{pre}[{nome}c]"]
        return f + [f"[{nome}c]{geo}{(',' + ','.join(cor)) if cor else ''}[{nome}]"]

    fs = cadeia("0:v", "base", False)
    df = um("desfoca")
    if df:
        k = (f"min(clip((T-{df['t0']:.3f})/{df.get('entra', .5)},0,1),"
             f"clip(({df['t1']:.3f}-T)/{df.get('sai', .5) or .001},0,1))")
        fs += [f"[base]split[bs][bb]", f"[bb]gblur=sigma={df['px'] / 2:.2f}[bz]",
               f"[bs][bz]blend=all_expr='A+(B-A)*{k}'[base]"]
    atraso = f"setpts=PTS-STARTPTS+{em:.3f}/TB"
    janela = f"enable='between(t,{em:.3f},{em + dur:.3f})'"
    fs += [f"[1:v]{atraso}[tras]", f"[base][tras]overlay=0:0:{janela}:eof_action=pass[v1]"]
    ult = "v1"
    c = _cartao(meta)
    if c:
        # Tela dividida: o take reduzido cai no cartão de cantos redondos, por cima
        # do painel (tras). A pessoa, se veio, só entra ACIMA do cartão: é a cabeça
        # que passa da borda. Dentro dele o recorte seria o mesmo pixel do take.
        # [a, b): no quadro do corte o cartão já saiu (between() fecha nos dois lados).
        # O 1 ms é o t do quadro, que chega como 13.79999 e deixava o cartão um quadro a mais.
        on = "+".join(f"gte(t,{a + em - .001:.3f})*lt(t,{b + em - .001:.3f})" for a, b in c["trechos"])
        s, cx = c["escala"], f"(iw-{W})/2+{int(c['x'])}"
        red = f"scale=trunc(iw*{s}/2)*2:trunc(ih*{s}/2)*2:flags=lanczos"
        fs += [f"[0:v]{ff.taxa(fontes[0], fps)},{red},crop={int(c['w'])}:{int(c['h'])}:{cx}:{int(c['y'] - c['topo'])},format=yuva444p[ct0]",
               f"[{i_mascara}:v]format=gray[cm]", "[ct0][cm]alphamerge[ct]",
               f"[v1][ct]overlay={int(c['x'])}:{int(c['y'])}:enable='{on}'[v2]"]
        ult = "v2"
        if com_pessoa:
            alto = int(c["y"] - max(c["topo"], 0)) + 6
            fs += [f"[3:v]format=yuva444p,{ff.taxa(fontes[1], fps, alfa='pp')},{red},crop={int(c['w'])}:{alto}:{cx}:{int(max(-c['topo'], 0))}[pp]",
                   f"[v2][pp]overlay={int(c['x'])}:{int(max(c['topo'], 0))}:enable='{on}'[v3]"]
            ult = "v3"
    elif com_pessoa:
        fs += cadeia("3:v", "pes", True)
        fs += [f"[v1][pes]overlay=0:0:format=auto[v2]"]
        ult = "v2"
    fs += [f"[2:v]{atraso}[fr]", f"[{ult}][fr]overlay=0:0:{janela}:eof_action=pass,format={ff.PIX_FMT}[vout]"]
    return ";".join(fs), "vout"


def cmd_compor(a):
    meta = json.loads(Path(a.peca).read_text(encoding="utf-8"))
    cam = meta.get("camadas") or sys.exit("o JSON não tem camadas — gere com `v2.py camadas`")
    W, H = (int(x) for x in meta["formato"].split("x"))
    cmd = ["ffmpeg", "-y", "-i", a.take, "-i", cam["tras"], "-i", cam["frente"]]
    if a.pessoa:
        cmd += ["-i", a.pessoa]
    c, i_masc = _cartao(meta), None
    if c:
        i_masc = 4 if a.pessoa else 3
        masc = mascara_cartao(c, Path(tempfile.mkdtemp(prefix="v2_cartao_")) / "cartao.png")
        # a máscara em laço não acaba sozinha: sem o -t, o overlay seguia depois do take
        cmd += ["-loop", "1", "-framerate", str(meta.get("fps", 30)), "-t", f"{ff.dur(a.take):.3f}", "-i", str(masc)]
    fontes = (ff.probe(a.take).fps, ff.probe(a.pessoa).fps if a.pessoa else 0)
    g, saida = grafo(meta, a.em, W, H, a.folga, bool(a.pessoa), i_masc, fontes)
    # crf 17: o composto é fonte de outro passo (legenda, junta), não o final
    cmd += ["-filter_complex", g, "-map", f"[{saida}]", "-map", "0:a?", "-c:a", "copy",
            "-c:v", ff.CODEC_VIDEO, "-crf", "17", "-pix_fmt", ff.PIX_FMT, a.out]
    if a.seco:
        with ff.seco() as cmds:
            ff.run(cmd)
        print(" \\\n  ".join(cmds[0]))
        return
    ff.run(cmd)
    cues = [{**c, "t": round(c["t"] + a.em, 3)} for c in meta.get("cues", [])]
    Path(a.out).with_suffix(".cues.json").write_text(json.dumps({"cues": cues}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {a.out}")


def _parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lista"); s.add_argument("--familia"); s.add_argument("--formato"); s.add_argument("--camadas", action="store_true"); s.add_argument("--curta", action="store_true"); s.set_defaults(f=cmd_lista)
    s = sub.add_parser("cardapio"); s.set_defaults(f=cmd_cardapio)
    s = sub.add_parser("info"); s.add_argument("peca"); s.set_defaults(f=cmd_info)
    s = sub.add_parser("catalogo"); s.set_defaults(f=cmd_catalogo)
    s = sub.add_parser("biblioteca"); s.add_argument("--saida"); s.add_argument("--abrir", action="store_true"); s.set_defaults(f=cmd_biblioteca)
    s = sub.add_parser("qa"); s.add_argument("pecas", nargs="*"); s.add_argument("--familia"); s.add_argument("--json")
    s.add_argument("--notas", action="store_true", help="mostra também as notas (não contam como problema)")
    s.add_argument("--ar", help="confere em outro formato (ex.: 1920x1080, a peça g_ deitada no longo)"); s.set_defaults(f=cmd_qa)
    s = sub.add_parser("mede"); s.add_argument("peca"); s.add_argument("--q", default="{}", help="JSON dos parâmetros da peça, como o plano os dá")
    s.add_argument("--ar"); s.add_argument("--t", type=float, help="instante em s (padrão: metade da duração)"); s.set_defaults(f=cmd_mede)
    for nome, fn in (("render", cmd_render), ("camadas", cmd_camadas)):
        s = sub.add_parser(nome); s.add_argument("peca"); s.add_argument("pares", nargs="*")
        s.add_argument("--out", required=nome == "camadas"); s.add_argument("--ar"); s.add_argument("--tema", choices=["claro", "tinta", "tinteiro", "marca", "neon"])
        s.add_argument("--fps", type=int, default=30)
        if nome == "render":
            s.add_argument("--camada", choices=["tras", "frente"]); s.add_argument("--opaco", action="store_true")
            s.add_argument("--rastro", action="store_true", help="motion blur nas entradas rápidas (~5× o tempo)")
            s.add_argument("--mesa", help="a pasta do `v2.py mesa`: os valores que o Studio gravou")
        s.set_defaults(f=fn)
    s = sub.add_parser("mesa"); s.add_argument("peca"); s.add_argument("pares", nargs="*")
    s.add_argument("--pasta", required=True, help="fora do repo: o Studio carimba o HTML que abre"); s.set_defaults(f=cmd_mesa)
    s = sub.add_parser("compor"); s.add_argument("--take", required=True); s.add_argument("--peca", required=True)
    s.add_argument("--em", type=float, required=True); s.add_argument("--out", required=True); s.add_argument("--pessoa")
    s.add_argument("--folga", type=float, default=1.25, help="quanto o take aberto é ampliado pra ter onde deslizar")
    s.add_argument("--seco", action="store_true", help="só imprime o comando do ffmpeg"); s.set_defaults(f=cmd_compor)
    s = sub.add_parser("lote"); s.add_argument("pedidos", help="JSON: lista dos argumentos de cada `render`")
    s.set_defaults(f=cmd_lote)
    return ap


def main():
    a = _parser().parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
