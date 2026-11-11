"""Loudness no alvo das redes, em duas passadas.

Mora sozinho porque roda POR ÚLTIMO. Antes, a normalização acontecia dentro do
render e os passos seguintes mexiam no som depois dela — o CRT mistura o efeito
sonoro, a trilha entra por cima. Medir o áudio e entregar outro é normalizar no
escuro.

    python helpers/normaliza.py <entrada.mp4> -o <saida.mp4>

A imagem é copiada. Só o som passa pelo encoder.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import ff


def normaliza(entrada: Path, saida: Path, previa: bool = False) -> Path:
    medida = None if previa else ff.loudness(entrada)
    if not previa and medida is None:
        print("  a medida falhou — caindo para uma passada só")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(entrada),
           # o loudnorm fecha o pico em -1 dBTP, mas o AAC passa ~1 dB por cima (medido: 0,0 dBTP na saída).
           # O limitador de pico real a 0,86 (-1,3 dBFS; a 0,89 o AAC ainda passava de -1 dBTP: medido -0,91) segura isso, sem o corte de 1,8 dB do 0,72.
           "-af", ff.loudnorm_filter(medida) + "," + ff.limitador(0.86),
           "-c:v", "copy", *ff.args_audio(),
           "-movflags", "+faststart", str(saida)]
    ff.run(cmd, quiet=True)
    return saida


def main() -> None:
    ap = argparse.ArgumentParser(description="Normaliza o loudness, copiando a imagem")
    ap.add_argument("entrada", type=Path)
    ap.add_argument("-o", "--saida", type=Path, required=True)
    ap.add_argument("--previa", action="store_true", help="uma passada só, mais rápido")
    args = ap.parse_args()
    normaliza(args.entrada.resolve(), args.saida.resolve(), args.previa)
    print(f"normalizado -> {args.saida}")


if __name__ == "__main__":
    main()
