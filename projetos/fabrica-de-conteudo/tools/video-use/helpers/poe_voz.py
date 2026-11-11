#!/usr/bin/env python3
"""Põe uma voz gravada à parte num trecho de vídeo mudo: a imagem fica, o áudio
vira a voz.

    python poe_voz.py trecho.mp4 voz.wav -o trecho_com_voz.mp4

É o bloco de abertura e de encerramento do curto de Lorcana: ele grava só a
fala, e a imagem sai do bruto. A voz mais curta que o vídeo ganha silêncio no
fim; a fábrica corta a imagem com a duração da fala, então a voz nunca sobra.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import ff


def poe(video: Path, voz: Path, saida: Path) -> Path:
    saida.parent.mkdir(parents=True, exist_ok=True)
    ff.run(["ffmpeg", "-y", "-i", str(video), "-i", str(voz),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-shortest", str(saida)], quiet=True)
    return saida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("voz", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    print(poe(a.video, a.voz, a.out))


if __name__ == "__main__":
    main()
