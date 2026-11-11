"""O quanto o vídeo do aluno se mexe, e o que ele não quer ver: a preferência fica gravada, pra ninguém perguntar de novo.

Mora no mesmo `onboarding/escolhas.json` das outras escolhas dele, na chave `movimento`:

    densidade  calma | media | intensa     (intensa: algo muda a cada 2 s no máximo; media 3,5 s; calma 6 s)
    efeitos    lista entre zoom, transicao, palavra_atras, layout, pecas, linhas, sons
    vetos      tipos de efeito ou nomes de peça que ele mandou tirar ("e_raio", "zoom")

    python movimento.py ler                                   # o que está gravado e o que falta perguntar
    python movimento.py grava --densidade intensa --efeitos zoom,transicao,sons
    python movimento.py grava --padrao                        # "tanto faz": intensa, com tudo (o do primeiro vídeo)
    python movimento.py grava --veta e_raio --veta zoom       # correção de gosto do storyboard
    python movimento.py grava --perdoa zoom                   # ele mudou de ideia

O storyboard (`fabrica.py --storyboard`) lê isso e avisa quando o plano foge. Com `FABRICA_ESCOLHAS` apontando
pra outro arquivo, lê e grava lá (os testes usam).
"""
import argparse
import json
import os
import sys
from pathlib import Path

DENSIDADES = {"intensa": 2.0, "media": 3.5, "calma": 6.0}   # o maior vão, em s, entre uma mudança e a seguinte
# troca de layout (tela cheia, rosto sobre o fundo trocado): no mínimo uma a cada tantos s; calma não exige
LAYOUT_CADA = {"intensa": 12.0, "media": 20.0, "calma": None}
# O que a densidade pede de peça (recurso `pecas` do estilo): quantas por 10 s e que fatia do vídeo elas cobrem.
# A média é a do Reel editado à mão que a régua do teste da Fábrica mede (~2,5 por janela, ~80% do tempo).
ALVOS = {"intensa": (3.0, 0.9), "media": (2.5, 0.8), "calma": (1.0, 0.4)}
EFEITOS = ("zoom", "transicao", "palavra_atras", "layout", "pecas", "linhas", "sons")
# O primeiro vídeo tem que impressionar (dono, 29/10): intensa, no ritmo dos anúncios, com tudo menos as linhas.
RECOMENDADA = "intensa"
PRIMEIRO_VIDEO = {"densidade": RECOMENDADA, "efeitos": [e for e in EFEITOS if e != "linhas"]}
ARQUIVO = Path(__file__).resolve().parents[3] / "onboarding" / "escolhas.json"


def _arq(arquivo: Path | str | None = None) -> Path:
    return Path(arquivo or os.environ.get("FABRICA_ESCOLHAS") or ARQUIVO)


def _todas(arq: Path) -> dict:
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def le(arquivo: Path | str | None = None) -> dict:
    """O que está gravado: `densidade`, `efeitos`, `vetos`. Chave que o aluno não deu não aparece."""
    m = _todas(_arq(arquivo)).get("movimento")
    return dict(m) if isinstance(m, dict) else {}


def falta(m: dict) -> list[str]:
    """O que o agente ainda tem que perguntar antes do primeiro storyboard."""
    return [k for k in ("densidade", "efeitos") if not m.get(k)]


def grava(densidade: str | None = None, efeitos: list[str] | None = None, veta: list[str] = (),
          perdoa: list[str] = (), arquivo: Path | str | None = None, padrao: bool = False) -> dict:
    """Junta ao que já está gravado, sem tocar nas outras chaves do arquivo. Valor fora da lista é erro, não palpite.
    `padrao`: o aluno não soube dizer ("tanto faz"); grava o do primeiro vídeo no que ele ainda não deu."""
    if padrao:
        m = le(arquivo)
        densidade = densidade or m.get("densidade") or PRIMEIRO_VIDEO["densidade"]
        efeitos = efeitos if efeitos is not None else m.get("efeitos") or PRIMEIRO_VIDEO["efeitos"]
    if densidade is not None and densidade not in DENSIDADES:
        raise ValueError(f"densidade é {' | '.join(DENSIDADES)}, não {densidade!r}")
    if efeitos is not None and (ruim := [e for e in efeitos if e not in EFEITOS]):
        raise ValueError(f"efeito é um destes: {', '.join(EFEITOS)} (veio {', '.join(ruim)})")
    arq = _arq(arquivo)
    todas = _todas(arq)
    m = todas.get("movimento") if isinstance(todas.get("movimento"), dict) else {}
    if densidade is not None:
        m["densidade"] = densidade
    if efeitos is not None:
        m["efeitos"] = list(dict.fromkeys(efeitos))
    vetos = [v for v in m.get("vetos", []) if v not in perdoa]
    m["vetos"] = list(dict.fromkeys([*vetos, *veta]))
    todas["movimento"] = m
    arq.parent.mkdir(parents=True, exist_ok=True)
    novo = arq.with_name(f"{arq.name}.{os.getpid()}.tmp")
    novo.write_text(json.dumps(todas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(novo, arq)
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["ler", "grava"])
    ap.add_argument("--densidade", choices=list(DENSIDADES))
    ap.add_argument("--efeitos", help=f"separados por vírgula: {', '.join(EFEITOS)}")
    ap.add_argument("--veta", action="append", default=[], help="tipo de efeito ou nome de peça; pode repetir")
    ap.add_argument("--perdoa", action="append", default=[], help="tira um veto")
    ap.add_argument("--padrao", action="store_true", help="o aluno não soube dizer: grava intensa, com todos os efeitos")
    ap.add_argument("--arquivo")
    a = ap.parse_args(argv)
    try:
        if a.acao == "grava":
            m = grava(a.densidade, a.efeitos.split(",") if a.efeitos is not None else None, a.veta, a.perdoa, a.arquivo, a.padrao)
        else:
            m = le(a.arquivo)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps({**m, "falta": falta(m), **({"recomendada": RECOMENDADA} if "densidade" in falta(m) else {})},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
