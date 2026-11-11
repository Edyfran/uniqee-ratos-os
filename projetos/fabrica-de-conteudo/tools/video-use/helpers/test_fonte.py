"""A legenda não pode depender de fonte que só existe na máquina do Matheus.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_fonte.py

O padrão (`creato`) vem do pack pago em ~/Library/Fonts. Sem ele, a primeira
legenda do aluno dava OSError. Agora cai na Montserrat, que viaja em assets/fontes.
"""
from pathlib import Path

import captions_viral as cv


def test_fonte_livre_viaja_junto():
    assert Path(cv.LIVRE[0]).exists(), f"a fonte livre não está em {cv.LIVRE[0]}"


def test_fonte_ausente_cai_na_livre():
    cv.FONTES["_fantasma"] = ("/nao/existe/fantasma.otf", 0, None)
    try:
        assert cv.fonte("_fantasma", 48).getname()[0] == "Montserrat"
    finally:
        del cv.FONTES["_fantasma"]


def test_fonte_por_caminho():
    """A letra da marca do aluno vem por caminho (estilo.py, desenho.fonte), não por nome do registro;
    relativo, o caminho parte da raiz da fábrica."""
    f = cv.fonte(cv.LIVRE[0] + "#Black", 50)
    assert f.getname() == ("Montserrat", "Black"), f.getname()
    assert cv._por_caminho("creato") is None, "nome do registro não é caminho"


def test_livre_desenha_os_acentos():
    assert cv.acentos_faltando("montserrat") == ""


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print(f"ok  {nome}")
