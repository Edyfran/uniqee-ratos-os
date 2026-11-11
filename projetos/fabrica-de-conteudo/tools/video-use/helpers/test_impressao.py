"""Auto-teste da impressão. Um comando, nada renderiza.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_impressao.py

A impressão é o que deixa a fábrica saber se o trabalho de um passo já existe.
Errar para um lado refaz o que estava pronto; errar para o outro entrega vídeo
velho — e o segundo é pior, porque passa calado.
"""
from __future__ import annotations

import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import impressao as imp


def arquivo(d: Path, nome: str, conteudo: str = "x" * 5000) -> Path:
    p = d / nome
    p.write_text(conteudo, encoding="utf-8")
    return p


# ---- o que muda a impressão -------------------------------------------------


def test_mesma_entrada_mesma_impressao(tmp: Path):
    a = arquivo(tmp, "fonte.mp4")
    cmd = ["ffmpeg", "-i", str(a), "saida.mp4"]
    assert imp.de(cmd, [a]) == imp.de(cmd, [a])


def test_comando_diferente_muda_a_impressao(tmp: Path):
    a = arquivo(tmp, "fonte.mp4")
    assert imp.de(["ffmpeg", "-crf", "20"], [a]) != imp.de(["ffmpeg", "-crf", "18"], [a])


def test_entrada_diferente_muda_a_impressao(tmp: Path):
    a, b = arquivo(tmp, "a.mp4"), arquivo(tmp, "b.mp4", "y" * 9000)
    cmd = ["ffmpeg", "-i", "qualquer"]
    assert imp.de(cmd, [a]) != imp.de(cmd, [b])


def test_entrada_reescrita_muda_a_impressao(tmp: Path):
    """O mesmo caminho com conteúdo novo é entrada nova."""
    a = arquivo(tmp, "fonte.mp4")
    antes = imp.de(["x"], [a])
    time.sleep(0.01)
    a.write_text("conteúdo diferente e de outro tamanho" * 50, encoding="utf-8")
    assert imp.de(["x"], [a]) != antes


def test_helper_alterado_invalida_o_que_ele_produziu(tmp: Path):
    """Corrigir uma heurística tem que refazer o que ela produziu — sem ninguém
    lembrar de subir um número de versão."""
    h = arquivo(tmp, "helper.py", "def corta(): return 1")
    antes = imp.de(["x"], [], helpers=[h])
    h.write_text("def corta(): return 2", encoding="utf-8")
    assert imp.de(["x"], [], helpers=[h]) != antes


def test_entrada_que_nao_existe_ainda_nao_estoura(tmp: Path):
    """Numa cadeia, a entrada de um passo é a saída do anterior, que ainda não
    foi produzida. A impressão tem que sair assim mesmo."""
    imp.de(["x"], [tmp / "ainda_nao_existe.mp4"])


# ---- pronto ou não ----------------------------------------------------------


def test_saida_com_impressao_batendo_esta_pronta(tmp: Path):
    saida = arquivo(tmp, "saida.mp4")
    imp.marca(saida, "abc123")
    assert imp.pronto(saida, "abc123")


def test_impressao_diferente_nao_esta_pronta(tmp: Path):
    saida = arquivo(tmp, "saida.mp4")
    imp.marca(saida, "abc123")
    assert not imp.pronto(saida, "outra")


def test_sem_marca_nao_esta_pronta(tmp: Path):
    assert not imp.pronto(arquivo(tmp, "saida.mp4"), "abc123")


def test_saida_que_sumiu_nao_esta_pronta(tmp: Path):
    saida = arquivo(tmp, "saida.mp4")
    imp.marca(saida, "abc")
    saida.unlink()
    assert not imp.pronto(saida, "abc")


def test_saida_truncada_nao_conta_como_pronta(tmp: Path):
    """Interrupção no meio de um render deixa arquivo pela metade. Aceitar
    truncado envenena a corrida seguinte, e o defeito aparece só ao assistir."""
    saida = tmp / "pela_metade.mp4"
    saida.write_bytes(b"\x00" * 10)
    imp.marca(saida, "abc")
    assert not imp.pronto(saida, "abc"), "arquivo de 10 bytes passou como pronto"


def test_arquivo_vazio_nao_conta_como_pronto(tmp: Path):
    saida = tmp / "vazio.mp4"
    saida.touch()
    imp.marca(saida, "abc")
    assert not imp.pronto(saida, "abc")


# ---- a marca --------------------------------------------------------------


def test_a_marca_mora_ao_lado_da_saida(tmp: Path):
    saida = arquivo(tmp, "saida.mp4")
    imp.marca(saida, "abc")
    assert list(tmp.glob("*.impressao")), "a marca não foi escrita ao lado"


def test_apagar_a_pasta_apaga_o_cache(tmp: Path):
    """O cache mora na área de trabalho do vídeo. Não existe pasta global."""
    sub = tmp / "trabalho"
    sub.mkdir()
    saida = arquivo(sub, "saida.mp4")
    imp.marca(saida, "abc")
    for p in sub.iterdir():
        p.unlink()
    assert not imp.pronto(saida, "abc")


def main() -> int:
    casos = [
        ("mesma entrada, mesma impressão", test_mesma_entrada_mesma_impressao),
        ("comando diferente muda",         test_comando_diferente_muda_a_impressao),
        ("entrada diferente muda",         test_entrada_diferente_muda_a_impressao),
        ("entrada reescrita muda",         test_entrada_reescrita_muda_a_impressao),
        ("helper alterado invalida",       test_helper_alterado_invalida_o_que_ele_produziu),
        ("entrada futura não estoura",     test_entrada_que_nao_existe_ainda_nao_estoura),
        ("impressão batendo = pronto",     test_saida_com_impressao_batendo_esta_pronta),
        ("impressão diferente",            test_impressao_diferente_nao_esta_pronta),
        ("sem marca",                      test_sem_marca_nao_esta_pronta),
        ("saída que sumiu",                test_saida_que_sumiu_nao_esta_pronta),
        ("truncado não é pronto",          test_saida_truncada_nao_conta_como_pronta),
        ("vazio não é pronto",             test_arquivo_vazio_nao_conta_como_pronto),
        ("a marca fica ao lado",           test_a_marca_mora_ao_lado_da_saida),
        ("apagar a pasta apaga o cache",   test_apagar_a_pasta_apaga_o_cache),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        for nome, caso in casos:
            sub = Path(td) / re.sub(r"[^\w-]+", "_", nome)
            sub.mkdir(parents=True, exist_ok=True)
            try:
                caso(sub)
                print(f"  ok   {nome}")
            except Exception as e:
                falhas.append((nome, e))
                print(f"  FALHA {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    if falhas:
        print("falhou: " + ", ".join(n for n, _ in falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
