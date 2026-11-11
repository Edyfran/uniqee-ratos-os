"""A busca do visual, de graça (fase (b) do plano visual, `docs/kit/plano-visual.md`, seção 2).

    python acha.py visual.json --trab _trabalho [--video cortado.mp4] [--fala fala_cortada.json] [--seco]

Resolve cada batida do `visual.json` em algo que a peça `e_dividida` mostra no painel: uma imagem (print recortado no
que importa, logo), um número, ou um texto. Código, sem agente e sem chave paga: Chromium sem janela (o do render do v2),
Simple Icons (CC0) pelo jsDelivr, API aberta do GitHub, Wikimedia Commons. O que falhar cai na `alternativa` da batida
e fica no relatório; nunca trava. Os brutos da rede ficam em cache (`cena.CACHE/visual`); o painel de cada batida, em
`<trab>/visual/<id>.png`; o resultado, em `<trab>/visual/achados.json`.

Sem login: X/Twitter pelo embed público (oembed), Instagram, LinkedIn e Facebook direto na alternativa. O Chromium é
limpo, sem cookie de ninguém.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import cena
import ff
import visual

CACHE = cena.CACHE / "visual"
VERSAO = 1                          # muda quando o que a busca devolve muda: o cache velho não vale
UA = "Mozilla/5.0 (fabrica-de-conteudo; +https://ninjadasautomacoes.com.br)"
HOSTS_X = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
HOSTS_LOGIN = {"instagram.com", "www.instagram.com", "linkedin.com", "www.linkedin.com", "facebook.com", "www.facebook.com",
               "fb.com", "tiktok.com", "www.tiktok.com"}
PAINEL = {"dividida": (1840, 1460), "cheia": (1080, 1920)}      # o painel da peça, no dobro (920x730), e a tela toda
LICENCAS_OK = ("cc0", "public domain", "pd", "cc by 4.0", "cc by 3.0", "cc by 2.5", "cc by 2.0", "cc-by")   # sem SA, sem NC, sem ND
AMARELO = (242, 199, 68)


def _chave(*partes) -> str:
    return hashlib.blake2b(json.dumps([VERSAO, *partes], default=str).encode(), digest_size=10).hexdigest()


def _rede(url: str, timeout: float = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ───────────────────────── print de página ─────────────────────────
def _navegador():
    from playwright.sync_api import sync_playwright
    return sync_playwright()


def _print_pagina(url: str, frase: str, ancora: str, saida: Path) -> list | None:
    """Print da página pública, do topo da âncora, e a região da frase (fração da imagem). A `_pagina`, a `_print` e as
    rotinas de limpeza são as do `reel_editorial.py` (uma só, sem cópia). A frase que não está na página não derruba:
    o print do topo vale, sem região (None)."""
    import reel_editorial as re_
    with _navegador() as pw:
        nav = pw.chromium.launch()
        try:
            pg = nav.new_page(viewport={"width": 1000, "height": 1100}, device_scale_factor=2)
            re_._pagina(pg, url)
            if urlparse(pg.url).hostname in HOSTS_LOGIN or "/login" in urlparse(pg.url).path:
                raise PermissionError(f"a página pede login ({pg.url})")
            try:
                if not frase:
                    raise AssertionError("sem frase")
                return re_._print(pg, saida.parent, saida.stem, ancora or frase, 900, frase)
            except AssertionError:
                pg.screenshot(path=str(saida), clip={"x": 0, "y": 0, "width": 1000, "height": 1100})
                return None
        finally:
            nav.close()


def _print_tweet(url: str, saida: Path) -> None:
    """O tweet pelo embed público do X (`publish.twitter.com/oembed`, sem chave), no Chromium sem janela. Sem o embed
    renderizado em 20 s (apagado, privado, o X mudou o embed), estoura e a batida cai na alternativa."""
    j = json.loads(_rede("https://publish.twitter.com/oembed?omit_script=1&theme=light&dnt=true&url=" + urllib.parse.quote(url, safe="")))
    with _navegador() as pw:
        nav = pw.chromium.launch()
        try:
            pg = nav.new_page(viewport={"width": 640, "height": 900}, device_scale_factor=2)
            pg.set_content("<html><body style='margin:0;padding:24px;background:#fff'>" + j["html"]
                           + "<script async src='https://platform.twitter.com/widgets.js'></script></body></html>")
            pg.wait_for_selector("iframe[src*='platform.twitter.com'], .twitter-tweet-rendered", timeout=20000)
            pg.wait_for_timeout(2500)
            caixa = pg.locator(".twitter-tweet-rendered, iframe").first
            caixa.screenshot(path=str(saida))
        finally:
            nav.close()


def print_de(url: str, frase: str = "", ancora: str = "") -> tuple[Path, list | None]:
    """(o png cru, a região da frase). Em cache pela URL + frase."""
    host = urlparse(url).hostname or ""
    if host in HOSTS_LOGIN:
        raise PermissionError(f"{host} pede login pra abrir a página")
    CACHE.mkdir(parents=True, exist_ok=True)
    k = _chave("print", url, frase, ancora)
    png, js = CACHE / f"{k}.png", CACHE / f"{k}.json"
    if not (png.exists() and js.exists()):
        tmp = CACHE / f"{k}.tmp.png"
        foco = None
        if host in HOSTS_X:
            _print_tweet(url, tmp)
        else:
            foco = _print_pagina(url, frase, ancora, tmp)
        tmp.replace(png)
        js.write_text(json.dumps({"foco": foco}), encoding="utf-8")
    return png, json.loads(js.read_text(encoding="utf-8"))["foco"]


# ───────────────────────── logo ─────────────────────────
def logo_de(nome: str, slug: str = "") -> Path:
    """O logo da marca em PNG transparente, preto, 1200 px de largura. Pacote Simple Icons (licença CC0 nos arquivos; as
    marcas seguem sendo dos donos: vale como referência editorial), baixado na hora pelo jsDelivr e guardado em cache,
    sem instalar nada. Marca que não está no pacote estoura (vai pra alternativa)."""
    slug = slug or re.sub(r"[^a-z0-9]", "", nome.lower())
    CACHE.mkdir(parents=True, exist_ok=True)
    k = _chave("logo", slug)
    png = CACHE / f"{k}.png"
    if not png.exists():
        svg = _rede(f"https://cdn.jsdelivr.net/npm/simple-icons/icons/{slug}.svg").decode()
        if "<svg" not in svg:
            raise ValueError(f"o pacote não devolveu um SVG pra “{slug}”")
        with _navegador() as pw:
            nav = pw.chromium.launch()
            try:
                pg = nav.new_page(viewport={"width": 1200, "height": 1200}, device_scale_factor=1)
                pg.set_content("<html><body style='margin:0;background:transparent'><div id=l style='width:1200px;line-height:0'>"
                               + svg.replace("<svg", "<svg width='1200' height='1200' fill='#0B0D12'", 1) + "</div></body></html>")
                tmp = CACHE / f"{k}.tmp.png"
                pg.locator("#l").screenshot(path=str(tmp), omit_background=True)
                tmp.replace(png)
            finally:
                nav.close()
    return png


# ───────────────────────── mídia da própria fonte ─────────────────────────
# A escada da prova (fase (e)): (a) a mídia da fonte que a fala cita, (b) o que o aluno manda, (c) foto livre, (d) a demonstração
# animada da biblioteca, (e) texto. Esta seção é o degrau (a): foto de um post público do X, imagem do README do repositório,
# imagem de capa (`og:image`) do site. Nada com login; o que falhar estoura e a batida cai na `alternativa`.
SINDICACAO_X = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token=a"
IMG_FORA = re.compile(r"shields\.io|badge|\.svg(\?|$)|visitor|trendshift|buymeacoffee", re.I)


def _guarda_imagem(url: str) -> Path:
    """Baixa a imagem (cache por URL) e guarda em JPG sobre branco: o que a Pillow abre, e sem alfa preto por baixo."""
    from PIL import Image
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / f"{_chave('midia', url)}.jpg"
    if not arq.exists():
        import io
        im = Image.open(io.BytesIO(_rede(url)))
        im = im.convert("RGBA")
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        fundo.paste(im, mask=im.split()[3])
        fundo.save(arq, quality=92)
    return arq


def fotos_do_tweet(url: str) -> list[str]:
    """As fotos do post público (JSON de sindicação do X, sem login), na maior resolução servida."""
    m = re.search(r"/status/(\d+)", url)
    if not m:
        raise LookupError(f"sem id de post em {url}")
    d = json.loads(_rede(SINDICACAO_X.format(id=m.group(1))))
    fotos = [p["url"] + ("?name=large" if "pbs.twimg.com" in p["url"] else "") for p in d.get("photos") or []]
    if not fotos:
        raise LookupError("o post não tem foto")
    return fotos


def imagens_do_readme(url: str) -> list[str]:
    """As imagens do README do repositório (banner, capturas), sem selo/badge/SVG, com o endereço resolvido."""
    partes = [p for p in urlparse(url).path.split("/") if p]
    if len(partes) < 2:
        raise LookupError(f"não é um repositório: {url}")
    base = f"https://raw.githubusercontent.com/{partes[0]}/{partes[1]}/HEAD/"
    md = _rede(base + "README.md").decode("utf-8", "replace")
    srcs = re.findall(r"""<img[^>]+src=["']([^"']+)["']|!\[[^\]]*\]\(([^)\s]+)""", md)
    out = []
    for a, b in srcs:
        src = a or b
        if IMG_FORA.search(src):
            continue
        out.append(src if src.startswith("http") else urllib.parse.urljoin(base, src))
    if not out:
        raise LookupError("o README não tem imagem")
    return out


def imagem_de_capa(url: str) -> list[str]:
    """A imagem de capa do site (`og:image`, ou `twitter:image`): o que o próprio dono da página escolheu pra representá-la."""
    html = _rede(url).decode("utf-8", "replace")
    achados = re.findall(r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)(?::url)?["'][^>]*content=["']([^"']+)""", html, re.I) \
        or re.findall(r"""<meta[^>]+content=["']([^"']+)["'][^>]*(?:property|name)=["'](?:og:image|twitter:image)""", html, re.I)
    if not achados:
        raise LookupError(f"{url} não declara imagem de capa")
    return [urllib.parse.urljoin(url, a.replace("&amp;", "&")) for a in achados]


def midia_de(url: str, n: int = 0) -> tuple[Path, str]:
    """(o arquivo, de onde veio) da `n`-ésima imagem da fonte citada: foto do post (X), imagem do README (repositório do GitHub)
    ou imagem de capa (qualquer outro site). Estoura se a fonte não tem essa imagem."""
    host = urlparse(url).hostname or ""
    if host in HOSTS_X:
        lista, de = fotos_do_tweet(url), "foto do post"
    elif host in ("github.com", "www.github.com") and len([p for p in urlparse(url).path.split("/") if p]) == 2:
        lista, de = imagens_do_readme(url), "imagem do README"
    else:
        lista, de = imagem_de_capa(url), "imagem de capa (og:image)"
    if n >= len(lista):
        raise LookupError(f"{de} nº {n + 1} não existe em {url} (tem {len(lista)})")
    return _guarda_imagem(lista[n]), f"{de}: {url}"


def recorta(arq: Path, caixa: list[float]) -> Path:
    """O recorte `[x0, y0, x1, y1]` (fração da imagem): quando a foto da fonte traz o antes e o depois lado a lado."""
    from PIL import Image
    im = Image.open(arq)
    x0, y0, x1, y1 = caixa
    sai = CACHE / f"{_chave('recorte', str(arq), caixa)}.jpg"
    if not sai.exists():
        im.crop((round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height))).convert("RGB").save(sai, quality=92)
    return sai


# ───────────────────────── número ─────────────────────────
def estrelas_do_github(repo: str) -> int:
    """`stargazers_count` da API aberta do GitHub (60 consultas por hora sem chave). Só repositório público."""
    return int(json.loads(_rede(f"https://api.github.com/repos/{repo}"))["stargazers_count"])


def _gh(url: str, accept: str = "application/vnd.github+json"):
    """(corpo JSON, cabeçalhos) da API do GitHub. `GITHUB_TOKEN`/`GH_TOKEN` entram se existirem (sobem o limite de 60 por hora), mas
    nada exige: sem eles a lista de estrelas pode vir `401` (o GitHub passou a pedir login nela) e o caller cai no contador."""
    import os
    h = {"User-Agent": UA, "Accept": accept}
    if (tok := os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
        h["Authorization"] = f"Bearer {tok}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
        return json.loads(r.read()), dict(r.headers)


PAGINAS_DE_ESTRELAS = 16        # requisições de stargazers por histórico: 1 do repositório + 16 = 17, longe das 60 por hora
PONTOS_DO_GRAFICO = 12


def historico_estrelas(repo: str, paginas: int = PAGINAS_DE_ESTRELAS, pontos: int = PONTOS_DO_GRAFICO) -> dict:
    """O histórico de estrelas de um repositório público, pela API de stargazers (`application/vnd.github.star+json` traz o
    `starred_at`): amostra `paginas` páginas de 100 espalhadas até a última (a primeira e a última sempre), pega a data da primeira
    estrela de cada uma (a contagem até ali é `(página-1)*100 + 1`) e interpola linear, entre amostras reais, em `pontos` pontos a
    intervalos iguais de tempo. Cada página fica em cache (as antigas não mudam), então refazer não gasta o limite.
    Devolve `{"pts": [contagens], "datas": [ISO], "total", "criado", "requisicoes", "amostras"}`; estoura se a API não responder."""
    from datetime import datetime, timezone
    base = f"https://api.github.com/repos/{repo}"
    info, _ = _gh(base)
    total, criado, req = int(info["stargazers_count"]), info["created_at"], 1
    ult = max(1, math.ceil(total / 100))
    quais = sorted({1 + round(i * (ult - 1) / max(1, paginas - 1)) for i in range(min(paginas, ult))} | {ult})
    pasta = CACHE / "estrelas"
    pasta.mkdir(parents=True, exist_ok=True)
    amostras = []                                   # (instante, contagem)
    for pg in quais:
        arq = pasta / f"{repo.replace('/', '_')}-{pg}.json"
        if arq.exists():
            ini = json.loads(arq.read_text(encoding="utf-8"))
        else:
            lista, _ = _gh(f"{base}/stargazers?per_page=100&page={pg}", "application/vnd.github.star+json")
            req += 1
            if not lista:
                continue
            ini = {"quando": lista[0]["starred_at"], "n": (pg - 1) * 100 + 1}
            if pg < ult:                            # página cheia: não muda mais, vai pro cache
                arq.write_text(json.dumps(ini), encoding="utf-8")
        amostras.append((datetime.fromisoformat(ini["quando"].replace("Z", "+00:00")), ini["n"]))
    if len(amostras) < 3:
        raise LookupError(f"poucas amostras do histórico de {repo} ({len(amostras)})")
    agora = datetime.now(timezone.utc)
    amostras.append((agora, total))
    amostras.sort()
    t0, t1 = amostras[0][0].timestamp(), amostras[-1][0].timestamp()
    pts, datas = [], []
    for k in range(pontos):
        t = t0 + (t1 - t0) * k / (pontos - 1)
        for (a, na), (b, nb) in zip(amostras, amostras[1:]):
            if a.timestamp() <= t <= b.timestamp():
                f = (t - a.timestamp()) / max(1, b.timestamp() - a.timestamp())
                pts.append(round(na + (nb - na) * f))
                break
        datas.append(datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"))
    pts[0], pts[-1] = amostras[0][1], total
    return {"pts": pts, "datas": datas, "total": total, "criado": criado, "requisicoes": req, "amostras": len(amostras) - 1,
            "dias": max(1, round((amostras[-1][0] - amostras[0][0]).total_seconds() / 86400))}


STAR_HISTORY = "https://api.star-history.com/svg?repos={repo}&type=Date"
_NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")
_MES_EN = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def _curva_svg(d: str) -> list[tuple[float, float]]:
    """Os pontos de um `d` de caminho SVG (M, c, s, C, a, L, h, v), com as curvas de Bézier amostradas em 4 pontos cada."""
    pts, x, y, cmd, ult = [], 0.0, 0.0, "", None
    for m in re.finditer(r"([MmLlHhVvCcSsAaZz])([^MmLlHhVvCcSsAaZz]*)", d):
        cmd, n = m.group(1), [float(v) for v in _NUM.findall(m.group(2))]
        rel = cmd.islower()
        c = cmd.lower()
        tam = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "a": 7, "z": 0}[c]
        for i in range(0, len(n), tam) if tam else []:
            a = n[i:i + tam]
            ox, oy = (x, y) if rel else (0.0, 0.0)
            if c in ("m", "l"):
                x, y = ox + a[0], oy + a[1]
                pts.append((x, y))
                ult = None
            elif c == "h":
                x = ox + a[0]
                pts.append((x, y))
            elif c == "v":
                y = oy + a[0]
                pts.append((x, y))
            elif c == "a":
                x, y = ox + a[5], oy + a[6]
                pts.append((x, y))
                ult = None
            else:
                if c == "c":
                    p1, p2, p3 = (ox + a[0], oy + a[1]), (ox + a[2], oy + a[3]), (ox + a[4], oy + a[5])
                else:                                       # s: a 1ª alça é o espelho da 2ª do segmento anterior
                    p1 = (2 * x - ult[0], 2 * y - ult[1]) if ult else (x, y)
                    p2, p3 = (ox + a[0], oy + a[1]), (ox + a[2], oy + a[3])
                p0 = (x, y)
                for t in (.25, .5, .75, 1):
                    u = 1 - t
                    pts.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
                x, y = p3
                ult = p2
    return pts


def _data_dos_ticks(rot: list[tuple[float, str]], hoje) -> list[tuple[float, "date"]]:
    """(x, data) de cada marca do eixo do tempo. As marcas vêm como `Mon 19`, `Oct 25` ou `November` (o 1º do mês); o mês e o
    ano saem da sequência (o dia que volta pra baixo vira o mês seguinte) e o ano é o mais recente que não passa de hoje."""
    from datetime import date, timedelta
    itens = []                                               # (x, mes|None, dia)
    for x, t in rot:
        t = t.strip()
        if (m := re.fullmatch(r"(?:[A-Za-z]{3} )?(\d{1,2})", t)):
            itens.append((x, None, int(m.group(1))))
        elif (m := re.fullmatch(r"([A-Za-z]{3,9}) (\d{1,2})", t)) and m.group(1)[:3].lower() in _MES_EN:
            itens.append((x, _MES_EN[m.group(1)[:3].lower()], int(m.group(2))))
        elif re.fullmatch(r"[A-Za-z]{3,9}", t) and t[:3].lower() in _MES_EN:
            itens.append((x, _MES_EN[t[:3].lower()], 1))
        else:
            raise ValueError(f"marca de tempo que não sei ler: “{t}”")
    k = next((i for i, it in enumerate(itens) if it[1]), None)
    if k is None:
        raise ValueError("nenhuma marca com o mês")
    meses = [0] * len(itens)                                 # mês (contado em sequência, com folga de ano) de cada marca
    meses[k] = itens[k][1]
    for i in range(k + 1, len(itens)):
        meses[i] = itens[i][1] or (meses[i - 1] + (1 if itens[i][2] < itens[i - 1][2] else 0))
        if itens[i][1]:
            meses[i] = itens[i][1] + 12 * ((meses[i - 1] - 1) // 12) + (12 if itens[i][1] < (meses[i - 1] - 1) % 12 + 1 else 0)
    for i in range(k - 1, -1, -1):
        meses[i] = meses[i + 1] - (1 if itens[i][2] > itens[i + 1][2] else 0)
    def monta(ano):
        return [(it[0], date(ano + (mm - 1) // 12, (mm - 1) % 12 + 1, it[2])) for it, mm in zip(itens, meses)]
    for ano in (hoje.year, hoje.year - 1, hoje.year - 2):
        r = monta(ano)
        if r[-1][1] <= hoje + timedelta(days=3):
            return r
    return monta(hoje.year)


def le_svg_estrelas(svg: str, pontos: int = 18, hoje=None) -> dict:
    """O histórico de estrelas que o `api.star-history.com/svg` desenha: a curva (o caminho `xkcd-chart-xyline`), os rótulos do
    eixo das estrelas (`10K`, `20K`...) e os do tempo. Devolve `{"pts": [estrelas], "datas": [ISO], "total"}` em `pontos` pontos
    a intervalos iguais de tempo. Estoura (`ValueError`) se o SVG não for o esperado: o caller cai no contador.
    shortcut: só o eixo de dias/meses desse gráfico (dezenas de dias); com anos nas marcas estoura, quando precisar, ler anos."""
    from datetime import date
    hoje = hoje or date.today()
    m = re.search(r'<path[^>]*stroke="#[0-9a-f]{6}"[^>]*d="([^"]+)"[^>]*class="xkcd-chart-xyline"|<path[^>]*d="([^"]+)"[^>]*class="xkcd-chart-xyline"', svg)
    d = (m.group(1) or m.group(2)) if m else None
    if not d:
        raise ValueError("o SVG não tem a curva (xkcd-chart-xyline)")
    curva = _curva_svg(d)
    ys = []
    for yy, rot in re.findall(r'translate\(0 ([\d.]+)\)">([^<]*)</text>', svg):
        r = rot.strip().upper().replace(",", ".")
        if not r:
            ys.append((float(yy), 0.0))
        elif (mm := re.fullmatch(r"([\d.]+)([KM]?)", r)):
            ys.append((float(yy), float(mm.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[mm.group(2)]))
    if len(ys) < 2:
        raise ValueError("o SVG não tem rótulos no eixo das estrelas")
    (ya, va), (yb, vb) = ys[0], ys[-1]
    xs = [(float(x), t) for x, t in re.findall(r'class="tick"[^>]*transform="translate\(([\d.]+) [\d.]+\)">([^<]+)</text>', svg)]
    ticks = _data_dos_ticks(xs, hoje)
    if len(ticks) < 2 or ticks[-1][0] == ticks[0][0]:
        raise ValueError("o SVG não tem marcas de tempo")
    (xa, da), (xb, db) = ticks[0], ticks[-1]
    dias_px = (db - da).days / (xb - xa)
    curva.sort()
    x0, x1 = curva[0][0], curva[-1][0]
    pts, datas = [], []
    from datetime import timedelta
    for k in range(pontos):
        x = x0 + (x1 - x0) * k / (pontos - 1)
        for (ax, ay), (bx, by) in zip(curva, curva[1:]):
            if ax <= x <= bx:
                y = ay + (by - ay) * ((x - ax) / (bx - ax) if bx > ax else 0)
                break
        pts.append(max(0, round(va + (y - ya) * (vb - va) / (yb - ya))))
        datas.append((da + timedelta(days=(x - xa) * dias_px)).isoformat())
    pts = list(itertools.accumulate(pts, max))          # estrela não desfaz: o ruído da curva não faz a linha descer
    return {"pts": pts, "datas": datas, "total": pts[-1]}


def historico_star_history(repo: str, pontos: int = 18) -> dict:
    """O histórico real de estrelas pelo `api.star-history.com/svg` (público, sem login e sem token do GitHub). Cache de um dia
    por repositório. A ponta vale o `stargazers_count` da API do GitHub se ela responder (o SVG arredonda o último ponto)."""
    from datetime import date
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / f"{_chave('star-history', repo, date.today().isoformat())}.svg"
    if not arq.exists():
        arq.write_bytes(_rede(STAR_HISTORY.format(repo=repo)))
    h = le_svg_estrelas(arq.read_text(encoding="utf-8"), pontos)
    try:
        h["total"] = h["pts"][-1] = max(h["pts"][-2], estrelas_do_github(repo))
    except Exception:      # sem a API: fica a leitura do gráfico
        pass
    h["dias"] = max(1, (date.fromisoformat(h["datas"][-1]) - date.fromisoformat(h["datas"][0])).days)
    h["requisicoes"], h["amostras"], h["origem"] = 1, pontos, "star-history"
    return h


_MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()


def painel_estrelas(repo: str) -> dict:
    """O painel do gráfico de estrelas: a peça `d_linha` com o histórico real (rótulo honesto, `estrelas no GitHub`) e a conta
    das requisições pro relatório. Estoura se não houver histórico (o caller cai no contador)."""
    try:       # primeiro o gráfico público do star-history (sem token); a lista de stargazers só se ele falhar
        h = historico_star_history(repo)
    except Exception:      # noqa: BLE001
        h = historico_estrelas(repo)
    n = len(h["pts"])
    rot_x = [("" if i % 3 and i != n - 1 else f"{int(h['datas'][i][8:])} {_MESES[int(h['datas'][i][5:7]) - 1]}") for i in range(n)]
    q = {"pts": ",".join(map(str, h["pts"])), "x": ",".join(rot_x), "rot": "estrelas no GitHub", "pre": "", "suf": "",
         "selo": f"{h['total']:,} em {h['dias']} dias".replace(",", ".")}      # sem `dl`: a linha cresce a batida inteira
    return {"peca": "d_linha", "pq": urllib.parse.urlencode(q), "requisicoes": h["requisicoes"],
            "de": (f"star-history.com ({repo}), {n} pontos lidos da curva" if h.get("origem") == "star-history" else
                  f"API do GitHub ({repo}): {h['amostras']} páginas de stargazers em {h['requisicoes']} requisições, interpolado em {n} pontos")}


def formata_milhar(n: int) -> tuple[str, str]:
    """(número, sufixo) pra tela: 50284 vira ("50", "mil"), arredondado pra baixo (nunca pra mais do que o repositório tem)."""
    if n >= 10000:
        return str(n // 1000), "mil"
    if n >= 1000:
        return f"{math.floor(n / 100) / 10:.1f}".replace(".", ","), "mil"
    return str(n), ""


def numero_de(f: dict) -> dict:
    """O painel do número. `valor` é o que a fala disse (ou o que a fonte mostra); com `github_repo`, as estrelas lidas
    da API valem mais que a fala, e a API fora do ar deixa o `valor` da batida. A regra 6 da spec: número da fonte ou da
    fala, nunca do agente."""
    num, suf, de = str(f["valor"]), str(f.get("sufixo", "")), f.get("de") or "fala"
    if f.get("github_repo"):
        try:
            num, suf = formata_milhar(estrelas_do_github(f["github_repo"]))
            de = f"API do GitHub, {f['github_repo']}"
        except Exception:        # sem rede ou limite: fica o que a pessoa disse
            pass
    return {"num": num, "suf": suf, "rot": f.get("rotulo", ""), "de": de}


# ───────────────────────── foto livre (Wikimedia Commons) ─────────────────────────
def foto_livre(consulta: str) -> tuple[Path, str]:
    """(o arquivo, o crédito) da 1ª foto da Wikimedia Commons com licença CC0, domínio público ou CC BY. O crédito é
    gravado no `visual.json` e entra na legenda do post (CC BY pede). Sem resultado bom, estoura."""
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=12&gsrsearch="
           + urllib.parse.quote(consulta + " filetype:bitmap") + "&prop=imageinfo&iiprop=url|extmetadata|mime&iiurlwidth=1600")
    paginas = (json.loads(_rede(api)).get("query") or {}).get("pages", {})
    for p in sorted(paginas.values(), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value") or "").lower()
        if ii.get("mime") in ("image/jpeg", "image/png") and any(lic.startswith(x) for x in LICENCAS_OK) \
                and not re.search(r"(^|[\s-])(sa|nc|nd)([\s-]|$)", lic):
            if (meta.get("Restrictions") or {}).get("value"):      # pessoa identificável, marca: fica de fora
                continue
            CACHE.mkdir(parents=True, exist_ok=True)
            arq = CACHE / f"{_chave('wiki', ii['thumburl'])}.jpg"
            if not arq.exists():
                arq.write_bytes(_rede(ii["thumburl"]))
            autor = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "") or "").strip()
            return arq, f"{autor or 'autor desconhecido'} / Wikimedia Commons ({meta['LicenseShortName']['value']})"
    raise LookupError(f"nenhuma foto livre pra “{consulta}”")


# ───────────────────────── o painel ─────────────────────────
def _cabe_na_largura(im, W: int, H: int, cy: float, saida: Path, margem: int = 48) -> Path:
    """Tela cheia: o print inteiro na largura, com margem, sobre papel; nunca corta texto dos lados. Se for mais alto que a
    tela, rola (recorta) só em altura, centrado em `cy` (o grifo; 0 = o topo)."""
    from PIL import Image
    s = (W - 2 * margem) / im.width
    im = im.resize((W - 2 * margem, max(1, round(im.height * s))), Image.LANCZOS)
    fundo = Image.new("RGB", (W, H), (255, 255, 255))
    caixa = H - 2 * margem
    if im.height <= caixa:
        fundo.paste(im, (margem, (H - im.height) // 2))
    else:
        topo = min(max(round(cy * s - caixa / 2), 0), im.height - caixa) if cy else 0
        fundo.paste(im.crop((0, topo, im.width, topo + caixa)), (margem, margem))
    fundo.save(saida)
    return saida


def compoe(img: Path, layout: str, saida: Path, foco: list | None = None, contido: bool = False) -> Path:
    """Põe a imagem no tamanho do painel do layout. `contido` (logo): sobre papel branco, inteira, no meio. Print: recorte
    no aspecto do painel, centrado na região da frase (`foco`, fração da imagem) e com a frase grifada em amarelo; texto
    do print abaixo de ~28 px na tela vira zoom na região, não print inteiro miúdo (regra 7)."""
    from PIL import Image
    W, H = PAINEL[layout]
    im = Image.open(img)
    if contido:
        im = im.convert("RGBA")
        fundo = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        s = min(0.55 * W / im.width, 0.55 * H / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        fundo.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2))
        fundo.convert("RGB").save(saida)
        return saida
    im = im.convert("RGB")
    w, h = im.size
    if foco:
        x, y, fw, fh = foco
        grifo = Image.new("RGB", im.size, (255, 255, 255))
        ret = (int(x * w), int(y * h), int((x + fw) * w), int((y + fh) * h))
        grifo.paste(Image.new("RGB", (ret[2] - ret[0], ret[3] - ret[1]), AMARELO), ret[:2])
        from PIL import ImageChops
        im = ImageChops.multiply(im, grifo)
        cx, cy = (x + fw / 2) * w, (y + fh / 2) * h
        cw = min(w, max(fw * w * 1.25, 0.5 * w))
        if layout == "cheia" and fw > 0.6:      # a frase ocupa a largura: o print inteiro na largura; frase curta segue em zoom
            return _cabe_na_largura(im, W, H, cy, saida)
    elif layout == "cheia":
        return _cabe_na_largura(im, W, H, 0, saida)
    else:
        cx, cy, cw = w / 2, 0, w
        if cw * H / W > h * 1.05:     # sem região e mais larga que o painel é alta (tweet na cheia): inteira, sobre papel
            fundo = Image.new("RGB", (W, H), (255, 255, 255))
            s = min(W / w, H / h)
            im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
            fundo.paste(im, ((W - im.width) // 2, 0 if im.height >= 0.9 * H else (H - im.height) // 2))
            fundo.save(saida)
            return saida
    ch = cw * H / W
    if ch > h:
        ch, cw = h, h * W / H
    x0 = min(max(cx - cw / 2, 0), w - cw)
    y0 = min(max(cy - ch / 2 if foco else 0, 0), h - ch)
    im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))).resize((W, H), Image.LANCZOS).save(saida)
    return saida


def par_de(antes: Path, depois: Path, layout: str, saida: Path) -> Path:
    """O antes e o depois da mesma coisa numa imagem do tamanho do painel: lado a lado ou um sobre o outro, o que der a imagem maior
    (foto larga empilha; a `cheia`, que é alta, quase sempre empilha). Cada um inteiro (nunca cortado), com a etiqueta ANTES / DEPOIS e uma seta no meio."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = PAINEL[layout]
    m, rot = 30, 64                                     # margem; altura da etiqueta
    from PIL import Image as _I
    (aw, ah), (dw, dh) = _I.open(antes).size, _I.open(depois).size

    def area(lado):      # a área das duas imagens, cada uma inteira, na disposição: a que enche mais o painel vence
        cw, ch = ((W - 3 * m) // 2, H - 2 * m) if lado else (W - 2 * m, (H - 3 * m) // 2)
        return sum((min(cw / w, (ch - rot - m) / h) ** 2) * w * h for w, h in ((aw, ah), (dw, dh)))
    lado = area(True) >= area(False)                    # fotos largas (TV, tela) empilham; retratos ficam lado a lado
    try:
        fonte = ImageFont.load_default(size=int(rot * 0.62))
    except TypeError:                                   # Pillow antigo: sem tamanho (fica miúdo, mas não quebra)
        fonte = ImageFont.load_default()
    fundo = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(fundo)
    cw, ch = ((W - 3 * m) // 2, H - 2 * m) if lado else (W - 2 * m, (H - 3 * m) // 2)
    for i, (arq, nome) in enumerate(((antes, "ANTES"), (depois, "DEPOIS"))):
        x0, y0 = (m + i * (cw + m), m) if lado else (m, m + i * (ch + m))
        im = Image.open(arq).convert("RGB")
        sc = min(cw / im.width, (ch - rot - m) / im.height)
        im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
        d.rectangle((x0, y0, x0 + cw, y0 + rot), fill=AMARELO if i else (20, 20, 20))
        d.text((x0 + cw / 2, y0 + rot / 2), nome, font=fonte, fill=(20, 20, 20) if i else (255, 255, 255), anchor="mm")
        ix, iy = x0 + (cw - im.width) // 2, y0 + rot + m + (ch - rot - m - im.height) // 2
        d.rectangle((ix - 3, iy - 3, ix + im.width + 2, iy + im.height + 2), outline=(20, 20, 20), width=3)
        fundo.paste(im, (ix, iy))
    cx, cy = (W // 2, H // 2) if lado else (W // 2, m + ch + m // 2)
    r = 22      # a seta é desenhada (a fonte embutida da Pillow não tem → e ↓)
    d.polygon([(cx - r, cy - r), (cx + r, cy - r), (cx, cy + r)] if not lado else [(cx - r, cy - r), (cx - r, cy + r), (cx + r, cy)], fill=(20, 20, 20))
    fundo.save(saida)
    return saida


def _painel_print(png: Path, foco: list | None, tag: str, rot: str) -> dict:
    """O painel de um print em tela cheia: a peça `r_print` da biblioteca (janela neobrutal, a câmera aproxima a região da frase
    e a marca: grifo na frase achada, contorno na imagem toda quando não há região). `peca` diz ao `tela_dividida` que o
    painel é a peça por inteiro, não uma imagem pro `e_dividida`."""
    return {"peca": "r_print", "img": str(png), "rot": rot, "tag": tag, "marca": "grifo" if foco else "contorno",
            "foco": ",".join(f"{v:.4f}" for v in (foco or [0.03, 0.03, 0.94, 0.94]))}


def _usuario_x(url: str) -> str:
    partes = [p for p in urlparse(url).path.split("/") if p]
    return f"@{partes[0]}" if partes else ""


def _alternativa(b: dict, motivo: str, layout: str) -> dict:
    a = b["alternativa"]
    if a.get("tipo") == "animacao":      # a escada: sem a prova real, a demonstração da biblioteca (não precisa de rede nem do aluno)
        f = a["fonte"]
        return {"id": b["id"], "status": "alternativa", "motivo": motivo, "layout": a.get("layout") or layout,
                "painel": {"peca": f["peca"], "pq": urllib.parse.urlencode(f.get("q") or {})}, "de": f"alternativa da pauta: animação {f['peca']}"}
    f = b.get("fonte") or {}
    url = f.get("url") or ""
    # a frase de um tweet entra como citação, nunca com cara de captura
    tag = a.get("tag") or (f"CITAÇÃO · {_usuario_x(url)}".strip(" ·") if urlparse(url).hostname in HOSTS_X else "")
    return {"id": b["id"], "status": "alternativa", "motivo": motivo, "layout": a.get("layout") or layout,
            "painel": {"txt": a["texto"], **({"tag": tag} if tag else {})}, "de": "alternativa da pauta"}


def _imagem_de(f: dict, rede: bool) -> tuple[Path, str]:
    """(o arquivo, de onde veio) de uma fonte que vira imagem: o que cada metade do par usa."""
    o = f.get("origem")
    if o == "arquivo":
        return Path(f["caminho"]), "arquivo do aluno"
    if o == "aluno":
        raise LookupError(f"só o aluno tem: {f.get('pedido')}")
    if not rede:
        raise ConnectionError("sem rede (modo --sem-rede)")
    if o in ("url", "busca"):
        if not f.get("url"):
            raise LookupError("`busca`: o agente grava a `url` na pauta antes; sem ela, não há onde abrir")
        return print_de(f["url"], f.get("frase", ""), f.get("ancora", ""))[0], f["url"]
    if o == "busca_imagem":
        return foto_livre(f["consulta"])
    if o == "midia":
        arq, de = midia_de(f["url"], int(f.get("n", 0)))
        return (recorta(arq, f["recorte"]) if f.get("recorte") else arq), de
    if o == "marca":
        return logo_de(f["nome"], f.get("slug", "")), f"Simple Icons (CC0): {f['nome']}"
    raise LookupError(f"origem “{o}” não vira imagem")


def resolve(b: dict, trab: Path, rede: bool = True) -> dict:
    """O painel de uma batida: `{"id", "status": "ok"|"alternativa"|"rosto", "layout", "painel": {"img"|"txt"|"num"...},
    "motivo", "de", "foco"}`. Nunca levanta: o que falha vira alternativa (ou, sem alternativa, texto da própria batida)."""
    layout, tipo, f = b["layout"], b["tipo"], b.get("fonte") or {}
    pasta = Path(trab) / "visual"
    pasta.mkdir(parents=True, exist_ok=True)
    if layout == "rosto":
        return {"id": b["id"], "status": "rosto", "layout": layout, "painel": {}, "motivo": "", "de": ""}
    if layout == "rosto_cartao":      # o rosto no cartão pequeno ainda não existe: fica o rosto cheio
        return {"id": b["id"], "status": "rosto", "layout": "rosto", "painel": {}, "motivo": "rosto_cartao ainda não tem peça (fica o rosto)", "de": ""}
    origem = f.get("origem")
    saida = pasta / f"{b['id']}.png"
    try:
        if tipo == "texto":
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"txt": b["texto"], **({"tag": b["tag"]} if b.get("tag") else {})}, "motivo": "", "de": "texto da pauta"}
        if origem == "numero" and f.get("github_repo") and f.get("grafico", True) and rede:
            try:          # o histórico de verdade vira a linha que sobe; sem ele, o contador abaixo
                pn = painel_estrelas(f["github_repo"])
                return {"id": b["id"], "status": "ok", "layout": layout, "motivo": "", "de": pn["de"],
                        "painel": {"peca": pn["peca"], "pq": pn["pq"]}, "requisicoes": pn["requisicoes"]}
            except Exception as e:      # noqa: BLE001  (401, limite, sem rede: cai no contador)
                nota_gh = f"sem o histórico de estrelas ({type(e).__name__}: {str(e)[:70]}): contador"
        else:
            nota_gh = ""
        if origem == "peca":
            return {"id": b["id"], "status": "ok", "layout": layout, "motivo": "", "de": f"animação da biblioteca: {f['peca']}",
                    "painel": {"peca": f["peca"], "pq": urllib.parse.urlencode({k: v for k, v in (f.get("q") or {}).items()})}}
        if origem == "numero":
            n = numero_de(f)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {k: n[k] for k in ("num", "suf", "rot") if n[k]},
                    "motivo": nota_gh, "de": n["de"]}
        if origem == "par":
            (a, da), (d, dd) = _imagem_de(f["antes"], rede), _imagem_de(f["depois"], rede)
            par_de(a, d, layout, saida)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "motivo": "",
                    "de": f"antes: {da}; depois: {dd}"}
        if origem == "arquivo" and layout == "cheia" and tipo in ("print", "tela_aluno", "demo"):
            return {"id": b["id"], "status": "ok", "layout": layout, "motivo": "", "de": "arquivo do aluno",
                    "painel": _painel_print(Path(f["caminho"]), None, "A tela dele", "tela do aluno")}
        if origem == "arquivo":
            compoe(Path(f["caminho"]), layout, saida)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "motivo": "", "de": "arquivo do aluno"}
        if origem == "aluno":
            raise LookupError(f"só o aluno tem: {f.get('pedido')}")
        if not rede:
            raise ConnectionError("sem rede (modo --sem-rede)")
        if origem in ("url", "busca"):
            if not f.get("url"):
                raise LookupError("`busca`: o agente grava a `url` na pauta antes; sem ela, não há onde abrir")
            png, foco = print_de(f["url"], f.get("frase", ""), f.get("ancora", ""))
            if layout == "cheia":      # print nunca vai cru em tela cheia: a peça `r_print` (janela, zoom e marca na frase)
                host = urlparse(f["url"]).hostname or ""
                return {"id": b["id"], "status": "ok", "layout": layout, "foco": foco, "de": f["url"],
                        "painel": _painel_print(png, foco, "O post" if host in HOSTS_X else "A página", host),
                        "motivo": "" if foco or host in HOSTS_X else "a frase não está na página: print do topo, sem grifo"}
            compoe(png, layout, saida, foco)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "foco": foco,
                    "motivo": "" if foco or urlparse(f["url"]).hostname in HOSTS_X else f"a frase não está na página: print do topo, sem grifo",
                    "de": f["url"]}
        if origem == "midia":
            arq, de = _imagem_de(f, True)
            if layout == "cheia":      # imagem real nunca vai crua em tela cheia: a peça `r_print`
                return {"id": b["id"], "status": "ok", "layout": layout, "de": de, "motivo": "",
                        "painel": _painel_print(arq, None, "A fonte", urlparse(f["url"]).hostname or "")}
            compoe(arq, layout, saida)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "motivo": "", "de": de}
        if origem == "marca":
            compoe(logo_de(f["nome"], f.get("slug", "")), layout, saida, contido=True)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "motivo": "",
                    "de": f"Simple Icons (CC0): {f['nome']}"}
        if origem == "busca_imagem":
            arq, credito = foto_livre(f["consulta"])
            compoe(arq, layout, saida)
            return {"id": b["id"], "status": "ok", "layout": layout, "painel": {"img": str(saida)}, "motivo": "", "de": credito,
                    "credito": credito}
        raise LookupError(f"origem “{origem}” sem busca")
    except Exception as e:      # a busca não trava o vídeo: cai na alternativa
        motivo = f"{type(e).__name__}: {str(e)[:160]}"
        if b.get("alternativa"):
            return _alternativa(b, motivo, layout)
        return {"id": b["id"], "status": "alternativa", "motivo": motivo, "layout": layout,
                "painel": {"txt": b.get("texto") or b["prova"]}, "de": "a prova da pauta (sem alternativa escrita)"}


def seco(doc: dict) -> list[str]:
    """O que `--seco` mostra: o que precisa de rede, sem abrir nada."""
    out = []
    for b in doc["batidas"]:
        f, o = b.get("fonte") or {}, (b.get("fonte") or {}).get("origem")
        if b["layout"] in ("rosto", "rosto_cartao") or b["tipo"] == "texto":
            continue
        if o in ("url", "busca"):
            out.append(f"batida {b['id']}: abre {f.get('url') or '(sem url: cai na alternativa)'}")
        elif o == "midia":
            out.append(f"batida {b['id']}: a imagem {f.get('n', 0) + 1} da fonte {f['url']} (post, README ou capa)")
        elif o == "marca":
            out.append(f"batida {b['id']}: logo “{f['nome']}” no Simple Icons")
        elif o == "busca_imagem":
            out.append(f"batida {b['id']}: foto livre “{f['consulta']}” na Wikimedia")
        elif o == "numero" and f.get("github_repo"):
            out.append(f"batida {b['id']}: estrelas de {f['github_repo']} na API do GitHub")
        elif o == "par":
            out.append(f"batida {b['id']}: o antes e o depois ({', '.join(str(f[k].get('url') or f[k].get('consulta') or f[k].get('caminho') or f[k].get('pedido') or f[k].get('nome')) for k in ('antes', 'depois'))})")
        elif o == "aluno":
            out.append(f"batida {b['id']}: do aluno ({f['pedido']})")
        elif o == "peca":
            out.append(f"batida {b['id']}: animação da biblioteca ({f['peca']}), sem rede")
    return out


def resolve_todas(doc: dict, trab: Path, rede: bool = True) -> list[dict]:
    achados = []
    for b in sorted(doc["batidas"], key=lambda b: b["t0"]):
        r = resolve(b, trab, rede)
        r["painel"], aviso = encaixa_animacao(r["painel"], b["t1"] - b["t0"])
        c = visual.confianca(b)
        achados.append({**r, "t0": b["t0"], "t1": b["t1"], "tipo": b["tipo"], "prova": b["prova"],
                        "confianca": c[0] if c else "", **({"aviso": f"animação não termina: batida nº {b['id']} ({aviso.split(': ', 1)[1]})"} if aviso else {})})
        print(f"  batida {b['id']:>2} {b['layout']:<8} {r['status']:<11} {r['de'] or r['motivo']}"
              + (f"   [{r['motivo']}]" if r["status"] != "ok" and r["motivo"] and r["de"] else ""), flush=True)
    (Path(trab) / "visual").mkdir(parents=True, exist_ok=True)
    (Path(trab) / "visual" / "achados.json").write_text(json.dumps(achados, ensure_ascii=False, indent=1), encoding="utf-8")
    return achados


# ── A animação inteira, mais meio segundo parada ────────────────────────────────────────────────────────────────────
FOLGA = 0.5     # a animação termina pelo menos isto antes do fim da batida (o espectador vê o fim, não o corte)
# O fim do número do `e_dividida`: sobe até 0,5 s antes do fim da batida (a peça); a conta usa 0,6 de margem.
E_DIVIDIDA_NUM_FIM = 0.6


def _q(painel: dict) -> dict:
    return dict(urllib.parse.parse_qsl(painel.get("pq", ""), keep_blank_values=True))


def _f(q: dict, k: str, d: float) -> float:
    try:
        return float(q[k])
    except (KeyError, ValueError):
        return d


def fim_da_animacao(painel: dict, dur: float) -> float | None:
    """Em que segundo da batida (de `dur` s) a animação do painel termina de fato, medido no código da peça (não no
    navegador). `None`: o painel não anima (imagem, texto). Uma conta por peça; a peça nova entra aqui."""
    peca, q = painel.get("peca"), _q(painel)
    if peca is None:
        return dur - E_DIVIDIDA_NUM_FIM if "num" in painel and _f({"n": painel["num"]}, "n", 0) > 0 else None
    if peca == "i_terminal":
        t, fim = _f(q, "t0", 0.4), 0.0
        for c in [c for c in q.get("cmd", "").split(";") if c.strip()]:
            tx, _, a = c.rpartition("@")
            tx, a = (tx, float(a)) if tx and a.replace(".", "", 1).isdigit() else (c, t)
            fim = a + len(tx.strip()) * 0.05
            t = fim + 0.55
        n = int(_f(q, "n", 0))
        if n:
            t1 = fim + 0.45
            fim = t1 + max(0.06, min(0.4, (dur - t1 - 0.8) / n)) * n
        return fim
    if peca == "d_grade":
        t0 = _f(q, "t0", 0.3)
        return t0 + (_f(q, "dc", 2.2) if "dc" in q else max(1.2, dur - t0 - 0.7)) + 0.3
    if peca == "d_linha":
        t0 = _f(q, "t0", 0.2)
        return t0 + 0.45 + (_f(q, "dl", 2.4) if "dl" in q else max(1.2, dur - t0 - 1.05)) + 0.55
    if peca == "r_print":
        tz = _f(q, "t_zoom", 1.0)
        return max(tz + 1.0, _f(q, "t_marca", tz + 0.9) + 0.55)
    if peca == "i_tv":
        return _f(q, "t_troca", 1.6) + 1.2
    return None


def encaixa_animacao(painel: dict, dur: float) -> tuple[dict, str]:
    """(painel, aviso). Acelera a animação até caber (`dc`, `dl`, `t_zoom`/`t_marca`, `t_troca`, o ritmo do terminal) para que ela
    termine `FOLGA` s antes do fim da batida. Se nem no limite cabe, devolve o aviso que o storyboard mostra (aviso vazio = coube)."""
    peca, q = painel.get("peca"), _q(painel)
    if peca == "d_grade":
        q["dc"] = f"{max(1.0, min(_f(q, 'dc', 99), dur - _f(q, 't0', 0.3) - 0.3 - FOLGA)):.2f}"
    elif peca == "d_linha":
        q["dl"] = f"{max(0.8, min(_f(q, 'dl', 99), dur - _f(q, 't0', 0.2) - 1.0 - FOLGA)):.2f}"
    elif peca == "r_print":
        tm = max(1.0, min(_f(q, "t_marca", 1.9), dur - 0.55 - FOLGA))
        q["t_marca"], q["t_zoom"] = f"{tm:.2f}", f"{max(0.1, min(_f(q, 't_zoom', 1.0), tm - 0.9)):.2f}"
    elif peca == "i_tv":
        q["t_troca"] = f"{max(0.3, min(_f(q, 't_troca', 1.6), dur - 1.2 - FOLGA)):.2f}"
    elif peca == "i_terminal" and q.get("cmd"):      # digitar mais cedo: os @ viram "logo depois do comando anterior"
        antes = fim_da_animacao({**painel, "pq": urllib.parse.urlencode(q)}, dur)
        if antes is not None and antes > dur - FOLGA:
            t, cs = 0.2, []
            for c in [c for c in q["cmd"].split(";") if c.strip()]:
                tx = c.rpartition("@")[0] if c.rpartition("@")[2].replace(".", "", 1).isdigit() else c
                cs.append(f"{tx.strip()}@{t:.2f}")
                t += len(tx.strip()) * 0.05 + 0.2
            q["cmd"] = ";".join(cs)
    novo = {**painel, "pq": urllib.parse.urlencode(q)} if "pq" in painel else painel
    fim = fim_da_animacao(novo, dur)
    if fim is not None and fim > dur - FOLGA + 1e-6:
        return novo, f"animação não termina: acaba em {fim:.1f} s de uma batida de {dur:.1f} s (precisa de {FOLGA} s parada no fim)"
    return novo, ""


MAX_PEDIDOS = visual.MAX_PERGUNTAS


def pedidos_ao_aluno(doc: dict, achados: list[dict]) -> list[str]:
    """A pergunta única: (a) o que o código não achou e SÓ o aluno tem (a tela dele) ou pode mandar no lugar do que não abriu
    (print de página atrás de login); (b) as batidas de confiança fraca que o agente da pauta perguntou (`pergunta`). No máximo 5,
    os de mais peso (mais tempo na tela) primeiro; o resto fica em silêncio na alternativa. Cada item diz a batida, o instante e
    o que vira se ele não tiver."""
    por_id = {b["id"]: b for b in doc["batidas"]}
    itens, vistos = [], set()
    for a in achados:
        b = por_id[a["id"]]
        f = b.get("fonte") or {}
        if a["status"] != "alternativa" or f.get("origem") not in ("aluno", "url", "busca"):
            continue
        o = (f["pedido"] if f["origem"] == "aluno" else f"o print de {f.get('url') or 'a página'} (não consegui abrir sem login)")
        queda = (b.get("alternativa") or {}).get("texto") or b["prova"]
        vistos.add(b["id"])
        itens.append((a["t1"] - a["t0"], f"{o} (batida {a['id']}, {a['t0']:.0f} a {a['t1']:.0f} s). Sem isso: texto “{queda}”"))
    baixa = visual.baixa_prova(doc["batidas"])
    for b in visual.a_perguntar(doc["batidas"]):
        if b["id"] not in vistos:
            itens.append((b["t1"] - b["t0"], visual.pergunta_da(b, baixa)))
    return [t for _, t in sorted(itens, key=lambda x: -x[0])[:MAX_PEDIDOS]]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("visual", type=Path)
    p.add_argument("--trab", type=Path, required=True)
    p.add_argument("--video", type=Path, help="o vídeo cortado: dá a duração pra conferir a cobertura")
    p.add_argument("--fala", type=Path, help="a fala cortada (`fala_cortada.json`): resolve as palavras-âncora do `visual.json`")
    p.add_argument("--seco", action="store_true", help="confere o JSON e lista o que precisa de rede, sem abrir nada")
    p.add_argument("--sem-rede", action="store_true", help="tudo cai na alternativa")
    a = p.parse_args()
    doc = visual.le(a.visual)
    dur = ff.dur(a.video) if a.video else None
    if a.fala:
        import transcript as tr
        palavras = tr.palavras(a.fala)
        doc = visual.ancora(doc, palavras)
        dur = dur or (palavras[-1]["end"] if palavras else None)
    erros = visual.valida(doc, dur)
    if erros:
        sys.exit("o visual.json reprovou:\n  " + "\n  ".join(erros))
    if a.seco:
        print("\n".join(seco(doc)) or "nada pra buscar na rede")
        return
    ach = resolve_todas(doc, a.trab, not a.sem_rede)
    for x in ach:
        if x.get("aviso"):
            print("AVISO " + x["aviso"])
    queda = [x for x in ach if x["status"] == "alternativa"]
    print(f"achou {len(ach) - len(queda)} de {len(ach)}; {len(queda)} na alternativa" + "".join(f"\n  batida {x['id']}: {x['motivo']}" for x in queda))
    if (pedidos := pedidos_ao_aluno(doc, ach)):
        texto = "Pra ficar com prova na tela, me diga:\n" + "\n".join(f"{i}) {t}" for i, t in enumerate(pedidos, 1)) \
            + "\nPode mandar só os que tiver, ou dizer “não tenho”: o resto eu resolvo."
        (Path(a.trab) / "visual" / "pergunta.txt").write_text(texto, encoding="utf-8")
        print("\nPERGUNTA AO ALUNO (uma só, de uma vez):\n" + texto)


if __name__ == "__main__":
    main()
