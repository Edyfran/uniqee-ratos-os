"""A impressão de um passo: tudo que determina a saída dele.

Rodar o mesmo plano duas vezes custava duas vezes. Nada era guardado sob o que o
produziu, então refazer um vídeo depois de trocar uma palavra da legenda pagava o
corte, o render e os dois efeitos de novo — 19,5 s medidos num clipe de 54 s, que
numa aula de 15 min são cerca de cinco minutos para não mudar nada.

A impressão junta três coisas:

  o comando montado   — que já sai pronto do modo seco, então isto é de graça
  as entradas         — tamanho e instante de cada arquivo que entra
  os helpers          — o CONTEÚDO do código que executa o passo

O terceiro é o que faz uma correção de heurística invalidar o que ela produziu
**sem ninguém lembrar de subir um número de versão**. Número de versão que
alguém precisa lembrar de subir é número que fica para trás.

O que NÃO entra é o conteúdo do vídeo de entrada. Resumir um bruto de cinco
gigabytes custa mais que o passo que se quer pular; tamanho e instante pegam o
que importa e custam uma chamada ao sistema de arquivos.

**O cache mora ao lado da saída**, na área de trabalho do vídeo. Apagar a pasta
apaga o cache; não existe pasta global para encher o disco nem política de
limpeza para manter.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# Abaixo disto, o arquivo é sobra de render interrompido e não saída pronta.
# Um mp4 válido com um quadro já passa de mil bytes; dez bytes é lixo.
PISO_BYTES = 1024

SUFIXO = ".impressao"


def _do_arquivo(p: Path) -> str:
    """Tamanho e instante. Não o conteúdo — resumir um bruto de cinco gigabytes
    custaria mais que refazer o passo que se quer pular."""
    try:
        s = p.stat()
        return f"{p.name}:{s.st_size}:{int(s.st_mtime_ns)}"
    except FileNotFoundError:
        # Na cadeia, a entrada de um passo é a saída do anterior, que ainda não
        # existe quando a impressão é calculada. Isso não é erro.
        return f"{p.name}:ausente"


def de(cmd: list[str], entradas: list[Path] | None = None,
       helpers: list[Path] | None = None) -> str:
    """A impressão de um passo."""
    h = hashlib.blake2b(digest_size=16)
    h.update("\x00".join(str(c) for c in cmd).encode())
    for p in entradas or []:
        h.update(_do_arquivo(Path(p)).encode())
    for p in helpers or []:
        try:
            h.update(Path(p).read_bytes())
        except OSError:
            h.update(b"helper-ausente")
    return h.hexdigest()


def _marca_de(saida: Path) -> Path:
    return saida.with_suffix(saida.suffix + SUFIXO)


def marca(saida: Path, impressao: str) -> None:
    """Grava a impressão ao lado da saída."""
    _marca_de(saida).write_text(impressao, encoding="utf-8")


def esquece(saida: Path) -> None:
    """Apaga a marca do passo: o cache dele deixa de valer, e só o dele (o `--refaz <bloco>` da fábrica)."""
    _marca_de(Path(saida)).unlink(missing_ok=True)


def pronto(saida: Path, impressao: str) -> bool:
    """O trabalho deste passo já existe e continua valendo?

    Exige as duas coisas: a impressão bate E a saída tem tamanho plausível.
    Interrupção no meio de um render deixa arquivo pela metade, e aceitar
    truncado envenena a corrida seguinte — com o defeito aparecendo só ao
    assistir.
    """
    saida = Path(saida)
    if not saida.exists() or saida.stat().st_size < PISO_BYTES:
        return False
    m = _marca_de(saida)
    return m.exists() and m.read_text(encoding="utf-8").strip() == impressao
