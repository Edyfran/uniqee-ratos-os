"""Queima legenda sem libass.

O `brew install ffmpeg` do homebrew-core vem sem libass, e sem libass o filtro
`subtitles` do ffmpeg não existe. Como isso é o que a maioria tem instalado, a
legenda aqui não depende dele: os cues viram uma sequência de PNGs desenhada com
Pillow — que o kit já usa — e entram por `overlay`. Nada pra instalar.

A sequência entra a 10 quadros por segundo, e não na taxa do vídeo: legenda troca
a cada segundo e meio, então 100 ms de granularidade não aparece, e o número de
PNGs cai por um fator de 3.

Uso:
    python helpers/legendar.py <video.mp4> <legenda.srt> -o <saida.mp4>
    python helpers/legendar.py --selftest
"""
import argparse, os, re, shutil, sys, tempfile
from pathlib import Path

import ff
import transcript as tr

from PIL import Image, ImageDraw, ImageFont

FPS = 10
Y_FRAC = 0.70          # mesma altura do MarginV=90 do estilo antigo: fora da UI do app
FONTES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   # macOS
    "/System/Library/Fonts/Helvetica.ttc",                 # macOS, fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    "C:/Windows/Fonts/arialbd.ttf",                        # Windows
]
# A livre que viaja junto (OFL), como no captions_viral: sem fonte do sistema,
# a legenda sai nela antes de cair na embutida do Pillow.
LIVRE = Path(__file__).resolve().parents[1] / "assets" / "fontes" / "Montserrat[wght].ttf"


def achar_fonte(tamanho):
    for f in FONTES:
        try:
            return ImageFont.truetype(f, tamanho)
        except OSError:
            continue
    try:
        f = ImageFont.truetype(str(LIVRE), tamanho)
        f.set_variation_by_name("Bold")
        print(f"aviso: nenhuma fonte do sistema encontrada, usando a {LIVRE.stem}")
        return f
    except OSError:
        pass
    # load_default ignora o tamanho e sai minúsculo, mas é melhor que estourar:
    # o vídeo sai com legenda feia em vez de não sair.
    print("aviso: nenhuma fonte do sistema encontrada, usando a embutida do Pillow")
    return ImageFont.load_default()


def ler_srt(p: Path):
    """(inicio, fim, texto) por cue. Cue sem tempo válido é ignorado, não quebra."""
    cues = []
    for bloco in p.read_text(encoding="utf-8").strip().split("\n\n"):
        linhas = [l for l in bloco.strip().split("\n") if l.strip()]
        if len(linhas) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", linhas[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        ini = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        fim = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        if fim > ini:
            texto = " ".join(linhas[2:]).strip()
            cues.append((ini, fim, " ".join(tr.corrigir_termo(w) for w in texto.split())))
    return cues


def quebrar(texto, fonte, largura_max, desenho):
    """Quebra em linhas que cabem. Palavra sozinha maior que a largura fica e vaza —
    cortar no meio da palavra atrapalha mais a leitura do que passar da margem."""
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if desenho.textlength(teste, font=fonte) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def desenhar(texto, W, fonte, altura_faixa, desenho_ref):
    im = Image.new("RGBA", (W, altura_faixa), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    linhas = quebrar(texto, fonte, W * 0.88, desenho_ref)
    alt = fonte.size + 12
    y = (altura_faixa - alt * len(linhas)) // 2
    for l in linhas:
        x = (W - dr.textlength(l, font=fonte)) / 2
        dr.text((x, y), l, font=fonte, fill=(255, 255, 255, 255),
                stroke_width=max(2, fonte.size // 11), stroke_fill=(0, 0, 0, 255))
        y += alt
    return im


def dims_dur(video):
    p = ff.probe(video)
    return p.largura, p.altura, p.duracao


def queimar(video: Path, srt: Path, saida: Path, y_frac: float = Y_FRAC) -> bool:
    cues = ler_srt(srt)
    if not cues:
        print("aviso: nenhum cue no .srt, saindo sem queimar")
        return False

    W, H, dur = dims_dur(video)
    fonte = achar_fonte(max(20, W // 16))
    faixa = int(fonte.size * 3.2)
    ref = ImageDraw.Draw(Image.new("RGBA", (W, faixa)))

    tmp = Path(tempfile.mkdtemp(prefix="legenda_"))
    try:
        vazio = tmp / "_vazio.png"
        Image.new("RGBA", (W, faixa), (0, 0, 0, 0)).save(vazio)
        feitos, n = {}, int(dur * FPS) + 1
        for i in range(n):
            t = i / FPS
            txt = next((c[2] for c in cues if c[0] <= t < c[1]), None)
            destino = tmp / f"f{i:06d}.png"
            origem = vazio
            if txt:
                if txt not in feitos:
                    p = tmp / f"_t{len(feitos):04d}.png"
                    desenhar(txt, W, fonte, faixa, ref).save(p)
                    feitos[txt] = p
                origem = feitos[txt]
            # link em vez de cópia: numa aula de 10 min são 6000 quadros, e quase
            # todos repetem o mesmo desenho.
            try:
                os.link(origem, destino)
            except OSError:
                shutil.copy(origem, destino)

        y = int(H * y_frac)
        r = ff.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(video),
                            "-framerate", str(FPS), "-start_number", "0", "-i", str(tmp / "f%06d.png"),
                            "-filter_complex", f"[0:v][1:v]overlay=0:{y}:shortest=1[v]",
                            "-map", "[v]", "-map", "0:a?",
                            *ff.args_video("reel", fps=None), "-c:a", "copy",
                            "-movflags", "+faststart", str(saida)])
        if r.returncode != 0:
            return False
        print(f"legenda queimada: {len(cues)} cues, {len(feitos)} desenhos")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _selftest():
    f = achar_fonte(60)
    ref = ImageDraw.Draw(Image.new("RGBA", (1080, 200)))

    # SRT com vírgula e com ponto nos milissegundos; bloco quebrado é ignorado
    srt = Path(tempfile.mktemp(suffix=".srt"))
    srt.write_text("1\n00:00:01,000 --> 00:00:02,500\nOLA MUNDO\n\n"
                   "2\n00:00:03.000 --> 00:00:04,000\nSEGUNDO\n\n"
                   "3\nsem tempo\nlixo\n", encoding="utf-8")
    c = ler_srt(srt)
    assert len(c) == 2, c
    assert c[0] == (1.0, 2.5, "OLA MUNDO"), c[0]
    assert c[1][0] == 3.0, c[1]
    srt.unlink()

    # cue de duração negativa ou zero não entra
    srt2 = Path(tempfile.mktemp(suffix=".srt"))
    srt2.write_text("1\n00:00:05,000 --> 00:00:05,000\nZERO\n", encoding="utf-8")
    assert ler_srt(srt2) == []
    srt2.unlink()

    # quebra: texto curto fica numa linha, texto longo em várias
    assert len(quebrar("DUAS PALAVRAS", f, 1080 * 0.88, ref)) == 1
    longo = quebrar("PALAVRA " * 20, f, 1080 * 0.88, ref)
    assert len(longo) > 1, longo
    # palavra única gigante não entra em loop infinito nem some
    uma = quebrar("X" * 200, f, 1080 * 0.88, ref)
    assert len(uma) == 1 and uma[0].startswith("XXX")

    # o desenho sai do tamanho pedido e com pixel opaco (o texto está lá)
    im = desenhar("TESTE", 1080, f, 200, ref)
    assert im.size == (1080, 200)
    assert im.getbbox() is not None, "desenho saiu vazio"
    print("legendar selftest ok")


def main():
    ap = argparse.ArgumentParser(description="Queima legenda de um .srt sem libass")
    ap.add_argument("video", type=Path)
    ap.add_argument("srt", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--y-frac", type=float, default=Y_FRAC,
                    help=f"altura da legenda, 0 a 1 (padrão {Y_FRAC})")
    a = ap.parse_args()
    if not queimar(a.video, a.srt, a.output, a.y_frac):
        sys.exit("não consegui queimar a legenda")
    print(f"pronto -> {a.output}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
