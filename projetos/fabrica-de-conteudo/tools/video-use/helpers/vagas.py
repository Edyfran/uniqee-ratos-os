"""As vagas da máquina: quantos passos pesados rodam ao mesmo tempo, somando todos os processos.

O pool da fábrica limita os passos de UMA corrida. Duas corridas ao mesmo tempo (o render e o
ensaio, dois blocos de um episódio em abas diferentes) somavam os dois pools, e em 28/09 o Mac
reiniciou com quatro builds em paralelo.

    with vagas.ocupa(2):
        ff.run(cmd)

Cada vaga é um arquivo de trava na pasta de cache do usuário. Quem chega tenta cada vaga sem bloquear
e, se não acha nenhuma livre, dorme meio segundo e tenta de novo. A trava é do sistema: quando o
processo morre, ela se solta sozinha, e nenhuma vaga fica presa.

A pasta de cache também guarda o tempo medido de cada passo (`fabrica.tempos_medidos`).
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

# Muda o lugar do cache; é o que os testes usam para não escrever na pasta de quem os roda.
CACHE = "FABRICA_CACHE"

ESPERA = 0.5


def pasta_de_cache() -> Path:
    """O cache do usuário: ~/.cache no Mac e no Linux, %LOCALAPPDATA% no Windows."""
    if os.environ.get(CACHE):
        return Path(os.environ[CACHE])
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path.home() / ".cache"
    return base / "fabrica"


def _tenta(f) -> bool:
    """Trava o arquivo sem esperar. False se outro processo (ou outra thread) já a tem; o erro de um
    disco que não trava (rede, ENOLCK) sobe, para `ocupa` seguir sem vaga em vez de esperar pra sempre."""
    try:
        if os.name == "nt":
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)      # flock, não lockf: esta vale por arquivo aberto, então duas threads também se travam
        return True
    except (BlockingIOError, PermissionError):               # ocupada: EAGAIN no POSIX, EACCES no Windows
        return False


def _solta(f) -> None:
    if os.name == "nt":
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)       # fechar solta, mas o Windows demora; solta antes
    f.close()                                                # no POSIX, fechar já solta a trava


@contextmanager
def ocupa(quantas: int):
    """Segura uma das `quantas` vagas da máquina enquanto o bloco roda; espera se todas estão cheias."""
    f = _pega(pasta_de_cache(), max(1, quantas))
    try:
        yield
    finally:
        if f is not None:
            _solta(f)


def _pega(pasta: Path, quantas: int):
    """O arquivo da vaga travada, ou None quando não há como travar (cache sem escrita, disco que
    não trava): a vaga é proteção, e não pode derrubar o render."""
    while True:
        for i in range(quantas):
            f = None
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                f = open(pasta / f"vaga-{i}.lock", "a+b")
                if _tenta(f):
                    return f
            except OSError:
                if f is not None:
                    f.close()
                return None
            f.close()
        time.sleep(ESPERA)
