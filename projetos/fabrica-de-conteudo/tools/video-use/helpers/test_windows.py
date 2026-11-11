"""A fábrica roda no Windows sem tropeçar no primeiro uso.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_windows.py

No Mac e no Linux o texto sai em utf-8 sem ninguém pedir. No Windows sai na
página de código do sistema (cp1252 no Brasil): um JSON com acento estoura no
primeiro `read_text()`, e a saída do ffmpeg com byte alto estoura no meio do
`subprocess`. O conserto é escrever `encoding="utf-8"` — e este teste é o que
impede o próximo helper de esquecer.

A varredura lê o código como texto, igual ao test_costura. O outro risco é o
`C:` do caminho dentro de filtro do ffmpeg: esse o teste prova rodando o ffmpeg.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
V2 = AQUI.parents[1] / "v2"

# Arquivos que o teste ainda não cobra, com o motivo. Lista que encolhe: quem
# ajustar o arquivo tira a linha.
PERDOADOS = {
    "test_v2.py":         "outro worker editando em 30/09; falta o encoding",
}

# Quem abre processo. Com `text=True` e sem `encoding`, a saída é lida na
# página de código do sistema.
PROCESSO = {"run", "Popen", "check_output", "check_call", "call"}
TEMPORARIO = {"NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"}


def _arquivos() -> list[Path]:
    return sorted([*AQUI.glob("*.py"), *V2.rglob("*.py")])


def _kw(no: ast.Call, nome: str) -> ast.expr | None:
    return next((k.value for k in no.keywords if k.arg == nome), None)


def _modo(valor: ast.expr | None, padrao: str) -> str | None:
    """O modo de abertura, quando dá pra saber lendo. `None` se é calculado."""
    if valor is None:
        return padrao
    if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
        return valor.value
    return None


def _e_modo(s: str) -> bool:
    return 0 < len(s) <= 3 and set(s) <= set("rwxabt+")


def _verdadeiro(valor: ast.expr | None) -> bool:
    """`text=True` ou `text=<expressão>`: só `False` literal é binário de certeza."""
    return valor is not None and not (isinstance(valor, ast.Constant) and valor.value is False)


def _falta_encoding(no: ast.Call) -> str | None:
    """O que a chamada faz sem `encoding`, ou `None` se ela está certa."""
    f = no.func
    tem = _kw(no, "encoding") is not None

    if isinstance(f, ast.Name) and f.id == "open":
        modo = _modo(no.args[1] if len(no.args) > 1 else _kw(no, "mode"), "r")
        if modo is not None and "b" in modo:
            return None
        return None if tem or len(no.args) > 3 else "open() de texto"

    if not isinstance(f, ast.Attribute):
        return None

    if f.attr == "read_text":
        return None if tem or no.args else "read_text()"
    if f.attr == "write_text":
        return None if tem or len(no.args) > 1 else "write_text()"

    if f.attr == "open":
        # Path.open("w"). `Image.open(caminho)` e `wave.open(p, "rb")` não são
        # texto: só conta quando o primeiro argumento é um modo de texto.
        primeiro = no.args[0] if no.args else _kw(no, "mode")
        modo = _modo(primeiro, "")
        if not modo or not _e_modo(modo) or "b" in modo:
            return None
        return None if tem else f'.open("{modo}")'

    if f.attr in TEMPORARIO:
        modo = _modo(no.args[0] if no.args else _kw(no, "mode"), "w+b")
        if modo is not None and "b" in modo:
            return None
        return None if tem else f"{f.attr} de texto"

    if (f.attr in PROCESSO and isinstance(f.value, ast.Name) and f.value.id == "subprocess"
            and (_verdadeiro(_kw(no, "text")) or _verdadeiro(_kw(no, "universal_newlines")))):
        return None if tem else f"subprocess.{f.attr}(text=…)"

    return None


def _achados(arquivo: Path) -> list[tuple[int, str]]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    return [(no.lineno, motivo) for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and (motivo := _falta_encoding(no))]


def test_todo_texto_diz_o_encoding():
    culpados = []
    for arq in _arquivos():
        if arq.name in PERDOADOS:
            continue
        for linha, motivo in _achados(arq):
            culpados.append(f"{arq.name}:{linha} {motivo} sem encoding")
    assert not culpados, ("texto sem encoding (quebra no Windows):\n  "
                          + "\n  ".join(culpados))


def test_o_detector_acerta():
    """O detector sozinho, contra os casos que ele tem que pegar e soltar."""
    def acha(codigo: str) -> bool:
        no = ast.parse(codigo).body[0].value
        return _falta_encoding(no) is not None

    assert acha('open(p)') and acha('open(p, "w")') and acha('p.read_text()')
    assert acha('p.write_text(s)') and acha('p.open("w")')
    assert acha('subprocess.run(c, text=True)') and acha('subprocess.run(c, text=not b)')
    assert acha('tempfile.NamedTemporaryFile(mode="w+")')
    assert not acha('open(p, "rb")') and not acha('open(p, encoding="utf-8")')
    assert not acha('p.read_text(encoding="utf-8")') and not acha('p.write_bytes(b)')
    assert not acha('Image.open(p)') and not acha('Image.open("/tmp/a.png")')
    assert not acha('wave.open(p, "rb")') and not acha('p.open("rb")')
    assert not acha('subprocess.run(c, capture_output=True)')
    assert not acha('subprocess.run(c, text=True, encoding="utf-8", errors="replace")')
    assert not acha('tempfile.NamedTemporaryFile(suffix=".wav")')


def test_caminho_no_filtro_chega_ao_ffmpeg():
    """O caminho do Windows dentro do filtro, e o ffmpeg escrevendo nele de verdade.

    O Mac aceita `:` em nome de pasta, então dá pra provar o escape aqui: o
    `metadata=print:file=` grava num lugar com tudo que o filtro trata como
    sintaxe. Se o escape falhar, o arquivo cai noutro nome ou o ffmpeg recusa.
    """
    import tempfile
    from pathlib import PureWindowsPath
    import ff

    # caminho de Mac fora do texto: o teste vai no pacote, e o portão de privacidade o reprova
    assert ff.caminho_no_filtro(PureWindowsPath(r"D:\Aulas\Zé\leg.ass")) == r"D\\:/Aulas/Zé/leg.ass"
    assert ff.caminho_no_filtro("/home/ze/Área de Trabalho/a.ass") == "/home/ze/Área de Trabalho/a.ass"

    with tempfile.TemporaryDirectory() as td:
        alvo = Path(td) / "C:" / "d'Ávila, [x]; y" / "meta.txt"
        alvo.parent.mkdir(parents=True)
        ff.run(["ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i", "color=s=16x16:d=0.1",
                "-vf", f"signalstats,metadata=print:file={ff.caminho_no_filtro(alvo)}",
                "-f", "null", "-"], quiet=True)
        assert "YAVG" in alvo.read_text(encoding="utf-8"), "o ffmpeg não escreveu no caminho escapado"


def main() -> int:
    casos = [
        ("o detector acerta",           test_o_detector_acerta),
        ("todo texto diz o encoding",   test_todo_texto_diz_o_encoding),
        ("caminho no filtro chega",     test_caminho_no_filtro_chega_ao_ffmpeg),
    ]
    falhas = []
    for nome, caso in casos:
        try:
            caso()
            print(f"  ok   {nome}")
        except Exception as e:
            falhas.append((nome, e))
            print(f"  FALHA {nome}: {e}")

    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    print(f"({len(_arquivos())} arquivos conferidos; {len(PERDOADOS)} perdoados)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
