"""Auto-teste das vagas da máquina. Nada renderiza.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_vagas.py

O pool da fábrica limita os passos de UMA corrida. Duas corridas ao mesmo tempo somavam os dois
pools, e em 28/09 o Mac reiniciou com quatro builds em paralelo. A vaga vale para a máquina inteira,
entre processos: aqui quatro processos de verdade disputam duas vagas.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import vagas


def _filho(pasta: str, quantas: int, registro: str, segura: float, morre: bool) -> None:
    """Um processo que pega a vaga, anota quando entrou e quando saiu, e a segura."""
    os.environ[vagas.CACHE] = pasta
    with vagas.ocupa(quantas):
        entrou = time.time()
        if morre:
            os._exit(0)             # sem soltar nada: quem solta é o sistema
        time.sleep(segura)
        saiu = time.time()
    with open(registro, "a", encoding="utf-8") as f:
        f.write(f"{entrou!r} {saiu!r}\n")


def _lanca(pasta: Path, quantas: int, registro: Path, segura: float = 1.0, morre: bool = False):
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--filho", str(pasta),
                             str(quantas), str(registro), str(segura), "1" if morre else ""])


def _no_maximo(intervalos: list[tuple[float, float]]) -> int:
    """O maior número de intervalos abertos ao mesmo tempo."""
    eventos = sorted([(a, 1) for a, _ in intervalos] + [(b, -1) for _, b in intervalos])
    abertos = maximo = 0
    for _, delta in eventos:
        abertos += delta
        maximo = max(maximo, abertos)
    return maximo


def test_quatro_processos_em_duas_vagas_nunca_passam_de_dois(tmp: Path):
    registro = tmp / "registro.txt"
    filhos = [_lanca(tmp / "cache", 2, registro) for _ in range(4)]
    for f in filhos:
        assert f.wait(timeout=60) == 0
    intervalos = [tuple(float(x) for x in linha.split())
                  for linha in registro.read_text(encoding="utf-8").splitlines()]
    assert len(intervalos) == 4, intervalos
    assert _no_maximo(intervalos) <= 2, f"mais de 2 ao mesmo tempo: {sorted(intervalos)}"


def test_a_vaga_solta_quando_o_processo_morre(tmp: Path):
    """Processo que cai (ou é morto) no meio do passo não pode deixar a vaga presa para sempre."""
    registro = tmp / "registro.txt"
    _lanca(tmp / "cache", 1, registro, morre=True).wait(timeout=30)
    inicio = time.monotonic()
    _lanca(tmp / "cache", 1, registro, segura=0.1).wait(timeout=30)
    assert registro.exists() and len(registro.read_text(encoding="utf-8").splitlines()) == 1
    assert time.monotonic() - inicio < 20, "a vaga ficou presa"


def test_o_cache_do_usuario_e_por_sistema_e_a_variavel_manda(tmp: Path):
    velho = os.environ.pop(vagas.CACHE, None)
    try:
        assert vagas.pasta_de_cache().name == "fabrica"
        os.environ[vagas.CACHE] = str(tmp / "meu")
        assert vagas.pasta_de_cache() == tmp / "meu"
    finally:
        os.environ.pop(vagas.CACHE, None)
        if velho is not None:
            os.environ[vagas.CACHE] = velho


def test_cache_sem_escrita_roda_sem_vaga(tmp: Path):
    """A vaga é proteção: cache que não dá para criar não derruba o passo, roda sem trava."""
    velho = os.environ.get(vagas.CACHE)
    (tmp / "arquivo").write_text("x", encoding="utf-8")
    os.environ[vagas.CACHE] = str(tmp / "arquivo" / "cache")   # pai é arquivo: mkdir falha
    try:
        rodou = []
        with vagas.ocupa(2):
            rodou.append(1)
        assert rodou == [1]
    finally:
        os.environ.pop(vagas.CACHE, None)
        if velho is not None:
            os.environ[vagas.CACHE] = velho


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--filho":
        _, _, pasta, quantas, registro, segura, morre = sys.argv
        _filho(pasta, int(quantas), registro, float(segura), bool(morre))
        return 0
    casos = [
        ("4 processos, 2 vagas",         test_quatro_processos_em_duas_vagas_nunca_passam_de_dois),
        ("processo morto solta a vaga",  test_a_vaga_solta_quando_o_processo_morre),
        ("cache do usuário",             test_o_cache_do_usuario_e_por_sistema_e_a_variavel_manda),
        ("cache sem escrita, sem vaga",  test_cache_sem_escrita_roda_sem_vaga),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        for i, (nome, caso) in enumerate(casos):
            sub = Path(td) / str(i)
            sub.mkdir()
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
