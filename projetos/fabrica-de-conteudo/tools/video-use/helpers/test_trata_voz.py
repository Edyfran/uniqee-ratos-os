"""O rnnoise do `trata_voz` tem que ser achado no kit, não só no tronco.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_trata_voz.py

O modelo morava em tools/quadro/public/rnnoise, lido por parents[2]. Na pasta
plana do kit isso caía fora da skill, e o estilo `vsl` morria no sys.exit. Agora
mora em assets/rnnoise, ao lado de helpers/ nos dois layouts. O teste monta o
layout do kit (skill/helpers + skill/assets) e roda a voz de verdade nele.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ff

AQUI = Path(__file__).resolve().parent
MODELOS = AQUI.parent / "assets" / "rnnoise"


def _kit(raiz: Path, com_modelo: bool) -> Path:
    helpers = raiz / "kitsim" / "skill" / "helpers"
    helpers.mkdir(parents=True)
    for nome in ("trata_voz.py", "ff.py"):
        shutil.copy2(AQUI / nome, helpers / nome)
    if com_modelo:
        shutil.copytree(MODELOS, raiz / "kitsim" / "skill" / "assets" / "rnnoise")
    return helpers


def _trata(helpers: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "trata_voz.py", *args], cwd=helpers,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _tom(destino: Path) -> Path:
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=220:duration=1", str(destino)], quiet=True)
    return destino


def test_rnnoise_resolve_no_layout_do_kit():
    with tempfile.TemporaryDirectory() as d:
        helpers = _kit(Path(d), com_modelo=True)
        r = _trata(helpers, "--autoteste")
        assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr
        r = _trata(helpers, str(_tom(Path(d) / "take.wav")), "-o", "voz.wav")
        assert r.returncode == 0, r.stderr
        assert "aviso" not in r.stderr and "rnnoise sh" in r.stdout, r.stdout + r.stderr


def test_sem_modelo_avisa_e_segue():
    with tempfile.TemporaryDirectory() as d:
        helpers = _kit(Path(d), com_modelo=False)
        r = _trata(helpers, str(_tom(Path(d) / "take.wav")), "-o", "voz.wav")
        assert r.returncode == 0, r.stderr
        assert "aviso: modelo do rnnoise" in r.stderr, r.stderr
        assert (helpers / "voz.wav").exists() and "rnnoise ausente" in r.stdout, r.stdout


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print(f"ok  {nome}")
