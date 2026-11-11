"""Olhar um vídeo ou uma pasta de quadros sem ler quadro por quadro.

Sai um RESUMO.md de uma página e no máximo duas folhas. O agente lê isso no lugar dos quadros soltos.
No Mac, o Vision (Apple) lê o texto de cada quadro e os rostos e acusa alerta de zona segura. No Windows e no
Linux, ou sem o swiftc, sai só a folha de quadros (feita pelo ff.py), sem texto nem rosto, e o resumo diz isso.
OLHAR_SEM_VISION=1 força esse caminho (o teste usa).

    python tools/economia/olhar.py final.mp4            # 12 quadros
    python tools/economia/olhar.py final.mp4 -n 24      # duas folhas
    python tools/economia/olhar.py /tmp/crivo/telas     # pasta de PNG/JPG
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "video-use" / "helpers"))
import ff  # noqa: E402
from leitura import TMP, binario  # noqa: E402

PARECIDO = 0.08  # impressão do Vision: <= isso é o mesmo quadro (calibrado em 12/10 numa aula: 0,10 já era texto novo)
LADO = 1568  # a API reduz a borda longa pra isso; acima disso é token jogado fora
POR_FOLHA = 12
IMG = {".png", ".jpg", ".jpeg", ".webp"}


def tem_vision():
    """O Vision é da Apple: só o Mac com swiftc e os dois fontes ao lado lê texto e rosto."""
    return (sys.platform == "darwin" and not os.environ.get("OLHAR_SEM_VISION") and bool(shutil.which("swiftc"))
            and all((AQUI / f"{n}.swift").exists() for n in ("parecido", "vis")))


def tira_quadros(video, dur, n, pasta):
    quadros = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        q = pasta / f"q{i:02d}_{t:07.2f}s.png"
        ff.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-y", q], quiet=True)
        quadros.append((q, t))
    return quadros


def folha(quadros, w, h, saida):
    """Tile com ffmpeg: grade escolhida pra borda longa da folha caber em LADO."""
    n = len(quadros)
    cols = 6 if h > w else 4  # vertical: 6x2; horizontal: 4x3
    linhas = -(-n // cols)
    tw = LADO // cols
    th = int(tw * h / w) // 2 * 2
    if th * linhas > LADO:
        th = LADO // linhas // 2 * 2
        tw = int(th * w / h) // 2 * 2
    lista = saida.with_suffix(".txt")
    # o concat lê aspas simples; a barra do Windows vira "/"; caminho relativo seria lido a partir da lista
    aspas = lambda q: Path(q).resolve().as_posix().replace("'", "'\\''")
    lista.write_text("".join(f"file '{aspas(q)}'\nduration 1\n" for q, _ in quadros) + f"file '{aspas(quadros[-1][0])}'\n",
                     encoding="utf-8")
    ff.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-vf",
            f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:-1:-1:gray,"
            f"tile={cols}x{linhas}:padding=2", "-frames:v", "1", "-q:v", "3", "-y", saida], quiet=True)
    lista.unlink()
    return saida


def alertas(textos, faces):
    a = []
    for t in textos:
        palavra, caixa, _ = t.rsplit("@", 2)
        x, y, bw, bh = map(float, caixa.split(","))
        if min(x, y, 1 - x - bw, 1 - y - bh) < 0.03:
            a.append(f"borda:{palavra[:18]}")
        if bh < 0.018:
            a.append(f"miúdo:{palavra[:18]}")
    return a[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fonte")
    ap.add_argument("-n", type=int, default=POR_FOLHA, help="quadros (máx. 24, duas folhas)")
    ap.add_argument("-o", "--saida")
    ap.add_argument("--parecido", type=float, default=PARECIDO,
                    help="distância que conta como repetido; -1 = todos (só onde há Vision, no Mac)")
    a = ap.parse_args()
    fonte = Path(a.fonte).expanduser()
    n = min(a.n, 2 * POR_FOLHA)
    saida = Path(a.saida or TMP / "olhar" / fonte.stem)
    shutil.rmtree(saida, ignore_errors=True)
    saida.mkdir(parents=True)

    if fonte.is_dir():
        arqs = sorted(p for p in fonte.iterdir() if p.suffix.lower() in IMG)
        if not arqs:
            sys.exit(f"nenhuma imagem em {fonte}")
        passo = max(1, -(-len(arqs) // n))  # ponytail: amostra uniforme se tiver mais que n
        quadros = [(p, None) for p in arqs[::passo]][:n]
        s = ff.probe(arqs[0])
        w, h = s.largura, s.altura
        cab = f"pasta `{fonte}` — {len(arqs)} imagens, {w}×{h}, {len(quadros)} na folha"
    else:
        s = ff.probe(fonte)
        w, h, dur = s.largura, s.altura, s.duracao
        tmp = saida / "quadros"
        tmp.mkdir()
        quadros = tira_quadros(fonte, dur, n, tmp)
        cab = f"vídeo `{fonte.name}` — {dur:.1f}s, {w}×{h}, {s.fps} fps, {n} quadros a cada {dur / n:.1f}s"

    vision = tem_vision()
    if vision:
        try:
            exe_parecido, exe_vis = binario("parecido"), binario("vis")
        except (OSError, subprocess.SubprocessError):
            vision = False  # o swiftc não compilou: segue só com a folha
    lido, repetidos = {}, 0
    if vision:
        dist = json.loads(subprocess.run([str(exe_parecido), *[str(q) for q, _ in quadros]], capture_output=True,
                                         text=True, encoding="utf-8").stdout or "[]")
        if len(dist) == len(quadros):
            mantidos = [quadros[0]] if quadros else []
            for q, d in zip(quadros[1:], dist[1:]):
                if 0 <= d <= a.parecido:
                    repetidos += 1  # ponytail: compara com o vizinho, não com o último mantido; tela parada longa cai inteira
                else:
                    mantidos.append(q)
            quadros = mantidos
        out = subprocess.run([str(exe_vis), *[str(q) for q, _ in quadros]], capture_output=True, text=True,
                             encoding="utf-8").stdout
        for linha in out.splitlines():
            j = json.loads(linha)
            lido[j["file"]] = j
    if repetidos:
        cab += f" — {repetidos} repetidos fora"

    folhas = [folha(quadros[i:i + POR_FOLHA], w, h, saida / f"folha{i // POR_FOLHA + 1}.jpg")
              for i in range(0, len(quadros), POR_FOLHA)]

    linhas = [f"# Olhar: {fonte.name}", "", cab, "",
              "Folhas: " + ", ".join(f"`{f}`" for f in folhas) + f" — {POR_FOLHA} por folha, da esquerda pra direita, de cima pra baixo (folha 2 começa no #{POR_FOLHA})", ""]
    if not vision:
        linhas += ["Texto e rosto só são lidos no Mac (o Vision é da Apple). Aqui o resumo é a folha: olhe os quadros nela, pelo número.", ""]
    linhas += ["| # | quando | rostos | texto na tela (Vision) | alertas |", "|---|---|---|---|---|"] if vision else \
              ["| # | quando |", "|---|---|"]
    anterior = None
    for i, (q, t) in enumerate(quadros):
        quando = f"{t:.1f}s" if t is not None else q.name
        if not vision:
            linhas.append(f"| {i} | {quando} |")
            continue
        j = lido.get(q.name, {"faces": [], "texts": []})
        texto = " · ".join(x.rsplit("@", 2)[0] for x in j["texts"]) or "—"
        if texto == anterior and texto != "—":
            texto = "(igual ao anterior)"
        else:
            anterior = texto
        linhas.append(f"| {i} | {quando} | {len(j['faces'])} | {texto[:140]} | {', '.join(alertas(j['texts'], j['faces']))} |")
    if vision:
        linhas += ["", "Borda = texto a menos de 3% da beirada (zona segura). Miúdo = letra com menos de 1,8% da altura."]
    linhas += ["", "Precisa de um quadro inteiro? Leia só ele, pelo número."]
    (saida / "RESUMO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(saida / "RESUMO.md")


if __name__ == "__main__":
    main()
