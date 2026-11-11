#!/usr/bin/env python3
"""Atalho antigo do render de peça; a espera de fonte mora no v2.

    python html_para_video.py "t_frase.html?l1=Oi&l2=tudo" saida.mov 1080x1920 [--alpha]
    = python tools/v2/v2.py render t_frase l1=Oi l2=tudo --ar 1080x1920 --out saida.mov

Quem importa `carrega_fontes` daqui (scripts de vídeo, o teste das receitas) recebe a do
`v2`: todo navegador do repo abre por lá (`v2.pagina`, `v2.quadro`, `v2.render`).
"""
import sys
from pathlib import Path
from urllib.parse import parse_qsl

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v2"))
import v2  # noqa: E402
from v2 import carrega_fontes, FONTES_PUXA, FONTES_ESPERA, FONTES_RUINS  # noqa: E402,F401


def main(argv: list[str]) -> None:
    alfa = "--alpha" in argv
    args = [a for a in argv if a != "--alpha"]
    if not args:
        sys.exit(__doc__)
    src, _, query = args[0].partition("?")
    peca = Path(src).stem                 # a peça é o nome do arquivo no catálogo
    out = Path(args[1]) if len(args) > 1 else Path(peca + ".mov")
    ar = args[2] if len(args) > 2 else None
    pares = [f"{k}={v}" for k, v in parse_qsl(query, keep_blank_values=True)]
    v2.render(peca, pares, out, ar=ar, alfa=alfa)


if __name__ == "__main__":
    main(sys.argv[1:])
