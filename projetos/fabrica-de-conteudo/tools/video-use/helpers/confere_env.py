#!/usr/bin/env python3
"""Diz quais chaves do .env.local estão preenchidas, sem nunca mostrar o valor.

    uv run python tools/video-use/helpers/confere_env.py            # todas
    uv run python tools/video-use/helpers/confere_env.py VOZ_ID     # só essas

É o único jeito de olhar o .env.local: nada de grep, cat nem Read nele, que
imprimem a chave no log da sessão (foi o que a ELEVENLABS_API_KEY sofreu em 06/10).
A saída é "NOME: preenchida" ou "NOME: vazia". Sai com 1 se alguma pedida está vazia.
"""
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parents[3] / ".env.local"


def estado(env: Path = ENV) -> dict[str, bool]:
    """Nome -> tem valor. O valor nunca sai desta função."""
    achado: dict[str, bool] = {}
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                nome, valor = linha.split("=", 1)
                achado[nome.strip().removeprefix("export ").strip()] = bool(valor.strip().strip("\"'"))
    return achado


def main() -> int:
    achado = estado()
    if not ENV.exists():
        print(".env.local não existe: copie o .env.local.exemplo", file=sys.stderr)
        return 1
    nomes = sys.argv[1:] or list(achado)
    for n in nomes:
        print(f"{n}: {'preenchida' if achado.get(n) else 'vazia'}")
    return 0 if all(achado.get(n) for n in nomes) else 1


if __name__ == "__main__":
    sys.exit(main())
