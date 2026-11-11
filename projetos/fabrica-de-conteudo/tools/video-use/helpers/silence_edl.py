"""Corte por energia do áudio, não por palavra.

O whisper borra o tempo das palavras por cima das pausas, então cortar por vão
entre palavras não tira silêncio. Aqui o silêncio é detectado no áudio de verdade,
pelo `silencedetect`, e sobra a fala.

**Só a detecção mora aqui.** O que fazer com os trechos achados — construir
segmento, juntar o que está colado, dar pad nas bordas — é a costura A, afinação
`SILENCIO`. Antes disto eram dois motores de corte com a mesma saída e regras
diferentes: o reel usava um, a aula usava o outro.

Uso:
  python helpers/silence_edl.py --video V -o edl.json --range S E [--range S E ...]
  opções: --noise -30dB  --min-sil 0.12  --pad 0.06  --min-seg 0.18
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

import clean_edl
import ff


def detect(src, ws, we, noise, d):
    out = ff.run(
        ["ffmpeg", "-hide_banner", "-vn", "-ss", str(ws), "-t", str(we - ws), "-i", str(src),
         "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
        quiet=True, check=False).stderr
    sils = []; cs = None
    for line in out.splitlines():
        m = re.search(r"silence_start: ([0-9.]+)", line)
        if m:
            cs = float(m.group(1))
        m = re.search(r"silence_end: ([0-9.]+)", line)
        if m and cs is not None:
            sils.append((ws + cs, ws + float(m.group(1)))); cs = None
    return sils


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("-o", "--output", required=True, type=Path)
    ap.add_argument("--range", nargs=2, type=float, action="append", required=True,
                    metavar=("S", "E"))
    ap.add_argument("--noise", default="-30dB")
    ap.add_argument("--min-sil", type=float, default=0.12, help="min silence to cut (s)")
    ap.add_argument("--pad", type=float, default=0.06, help="keep this much speech edge (s)")
    ap.add_argument("--min-seg", type=float, default=0.18)
    a = ap.parse_args()
    src = a.video.resolve()
    stem = src.stem

    af = clean_edl.afinacao("silencio", pad_in=a.pad, pad_out=a.pad, min_seg=a.min_seg)

    falados = []
    for ws, we in a.range:
        sils = sorted((max(x, ws), min(y, we)) for x, y in detect(src, ws, we, a.noise, a.min_sil) if y > x)
        # fala = janela MENOS os silêncios (o que também tira silêncio de ponta a ponta)
        prev = ws
        for sa, sb in sils:
            if sa > prev:
                falados.append((prev, sa))
            prev = sb
        if we > prev:
            falados.append((prev, we))

    # A costura A cuida do resto: pad nas bordas, juntar o que está colado, piso de
    # tamanho. A detecção acima é a única coisa que este arquivo sabe fazer sozinho.
    out_ranges = clean_edl.cortar(clean_edl.palavras_de_trechos(falados),
                                  janelas=[tuple(r) for r in a.range],
                                  afinacao=af, fonte=stem)
    total = sum(r["end"] - r["start"] for r in out_ranges)
    src_total = sum(e - s for s, e in a.range)
    a.output.write_text(json.dumps({"version": 1, "sources": {stem: str(src)},
        "ranges": out_ranges, "grade": "none", "overlays": [],
        "total_duration_s": round(total, 2)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"segments {len(out_ranges)} | kept {total:.1f}s of {src_total:.1f}s "
          f"(cortou {src_total-total:.1f}s de silêncio)")


if __name__ == "__main__":
    main()
