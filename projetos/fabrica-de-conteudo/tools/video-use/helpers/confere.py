"""A conferência da Fábrica: um comando só, igual para o agente do aluno, a CI e o ensaio.

    uv run python tools/video-use/helpers/confere.py [--pasta RAIZ_DO_KIT] [--tudo]

Por padrão roda só os testes que provam a máquina (RAPIDOS, ~15 s); `--tudo` roda a suíte inteira
(~10 min, a do `git push` e a da CI). Passa: grava `.fabrica-ok` e sai 0. Falha: grava `conferencia.txt`, diz o conserto em
português (se conhecer a falha) e sai 1. Só stdlib; roda o pytest pelo mesmo Python.
Não chama ferramenta paga e não lê chave.
"""
import argparse
import datetime
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]      # raiz/tools/video-use/helpers/confere.py
HELPERS = Path(__file__).resolve().parent
ECONOMIA = RAIZ / "tools" / "economia" / "test_economia.py"   # o porteiro de leitura; a Fábrica leva

INSTALA_FFMPEG = ("Instale o ffmpeg e reabra o agente:\n"
                  "  Mac:     o bloco do Mac na skill fabrica-de-conteudo (sem senha, sem Homebrew)\n"
                  "  Windows: winget install -e --id Gyan.FFmpeg\n"
                  "  Linux:   sudo apt install ffmpeg")

DEFEITO = ("Defeito do pacote: não edite teste nem helper. Leia o teste que falhou: se a causa é da "
           "máquina (programa que falta, permissão), conserte e rode de novo. Se é do pacote, peça o "
           "conferencia.txt num Chamado da Academy e siga com o que o usuário pediu.")

# O que prova a máquina em segundos, medido num Mac M2 Max em 23/10/2026 (a suíte inteira: ~10 min,
# 295 s só o test_fabrica). Cada um com o defeito de instalação que ele pega. Fica de fora o lento
# (test_fabrica, corte_suave, captions_viral, emenda, storyboard, capa) e o que testa lógica, não a máquina.
RAPIDOS = [
    "test_costura.py",     # ninguém chama ffmpeg por fora do ff.py
    "test_ff.py",          # ffmpeg e ffprobe de verdade: monta um clipe, codifica e mede
    "test_mixa.py",        # os filtros de áudio (loudnorm, amix) existem neste ffmpeg
    "test_fonte.py",       # a fonte livre viaja e desenha os acentos
    "test_trata_voz.py",   # o modelo do rnnoise está onde o helper procura
    "test_estilo.py",      # os estilos resolvem
    "test_transcript.py",  # o leitor da fala importa
    "test_transcribe.py",  # o transcribe.py importa e escolhe o adaptador desta máquina
]

# (todos estes padrões no texto) -> conserto. A primeira linha que casar ganha; a ordem importa.
DIAGNOSTICOS = [
    ([r"Permission denied", r"(?i)chromium|playwright|1100"],
     "No Codex, troque as permissões para Acesso total (no terminal: "
     "`codex --sandbox danger-full-access`) e rode a conferência de novo."),
    # ModuleNotFoundError não está aqui: só é `uv sync` se o módulo for dependência declarada
    # (`_modulo_declarado`). Helper local faltando é defeito do pacote.
    ([r"UnicodeDecodeError|cp1252"],
     "Falta o PYTHONUTF8=1. No Windows: `setx PYTHONUTF8 1`, reabra o agente e rode de novo."),
    ([r"Executable doesn't exist"],
     "Falta o Chromium: `uv run playwright install chromium` "
     "(no Linux: `uv run playwright install --with-deps chromium`)."),
    ([r"(?i)command not found|FileNotFoundError.*\b(ffmpeg|ffprobe)\b|nao e reconhecido|não é reconhecido"],
     "Programa instalado e não achado: o PATH desta sessão é velho. Reabra o agente e rode de novo."),
]


# nome que se importa -> nome no pyproject, quando diferem
_ALIAS = {"pil": "pillow", "cv2": "opencv-python", "yaml": "pyyaml", "sklearn": "scikit-learn"}


def _modulo_declarado(saida: str, raiz: Path = RAIZ) -> bool:
    """O módulo que faltou é dependência declarada no pyproject.toml do kit?"""
    m = re.search(r"No module named '([\w.]+)'", saida)
    # no kit o pyproject fica na raiz; no repositório, em tools/video-use/
    pyproject = next((c for c in (raiz / "pyproject.toml", HELPERS.parent / "pyproject.toml")
                      if c.exists()), None)
    if not m or not pyproject:
        return False
    topo = m.group(1).split(".")[0].lower().replace("_", "-")
    topo = _ALIAS.get(topo, topo)
    texto = pyproject.read_text(encoding="utf-8").split("[project.optional-dependencies]")[0]
    bloco = re.search(r"dependencies\s*=\s*\[(.*?)\n\]", texto, re.S)
    nomes = {re.match(r"[A-Za-z0-9_.-]+", d).group(0).lower().replace("_", "-")
             for d in re.findall(r'^\s*"([^"]+)"', bloco.group(1) if bloco else "", re.M)}
    return topo in nomes


def diagnostico(saida: str, raiz: Path = RAIZ) -> str:
    """O conserto conhecido para a saída do pytest, ou o aviso de defeito do pacote."""
    if "ModuleNotFoundError" in saida and _modulo_declarado(saida, raiz):
        return "Falta dependência: rode `uv sync` e a conferência de novo."
    for padroes, conselho in DIAGNOSTICOS:
        if all(re.search(p, saida) for p in padroes):
            return conselho
    return DEFEITO


def _versao(raiz: Path) -> str:
    f = raiz / "VERSAO"
    return f.read_text(encoding="utf-8").strip() if f.exists() else "sem versão"


def _agente() -> str:
    if any(k.startswith("CODEX_") for k in os.environ):
        return "Codex"
    if os.environ.get("CLAUDECODE"):
        return "Claude Code"
    return "não detectado"


def _linha_ffmpeg() -> str:
    ff = shutil.which("ffmpeg")
    if not ff:
        return "ffmpeg não encontrado"
    r = subprocess.run([ff, "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout.splitlines() or ["?"])[0]


def _alvos(testes: Path | None, tudo: bool) -> list[Path]:
    """O que o pytest roda: a pasta pedida; senão a dos helpers inteira e o teste do porteiro (`--tudo`); senão os RAPIDOS."""
    if testes:
        return [Path(testes)]
    if not tudo:
        return [HELPERS / n for n in RAPIDOS]
    return [HELPERS, *([ECONOMIA] if ECONOMIA.is_file() else [])]


def confere(raiz: Path, testes: Path | None = None, exige_ffmpeg: bool = True, tudo: bool = False) -> bool:
    raiz = Path(raiz)
    alvos = _alvos(testes, tudo)
    ok, nota = raiz / ".fabrica-ok", raiz / "conferencia.txt"
    ok.unlink(missing_ok=True)
    nota.unlink(missing_ok=True)

    cabecalho = [f"Fábrica de Conteúdo com IA, versão {_versao(raiz)}",
                 f"Sistema: {platform.platform()}",
                 f"Python: {platform.python_version()}",
                 f"ffmpeg: {_linha_ffmpeg()}"]
    print("\n".join(cabecalho))
    if not testes and not tudo:
        print("Conferência rápida; `--tudo` roda a suíte inteira.")

    if exige_ffmpeg and not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        saida, conselho = "ffmpeg ou ffprobe fora do PATH", INSTALA_FFMPEG
    else:
        # FABRICA_CONFERENCIA: teste que mede a máquina (régua de cor do ffmpeg) pula aqui
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "FABRICA_CONFERENCIA": "1"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *map(str, alvos)],
                           capture_output=True, env=env, cwd=raiz)
        saida = (r.stdout + r.stderr).decode("utf-8", errors="replace")
        if r.returncode == 0:
            ok.write_text(f"{datetime.date.today():%Y-%m-%d} {platform.system()} {platform.machine()}\n",
                          encoding="utf-8")
            print(saida.strip().splitlines()[-1] if saida.strip() else "")
            print("Pronto: a máquina está conferida. Pode pedir o primeiro vídeo.")
            return True
        conselho = diagnostico(saida, raiz)

    nota.write_text("\n".join([*cabecalho, f"Agente: {_agente()}", "", saida]) + "\n", encoding="utf-8")
    print("\n".join(saida.splitlines()[-30:]))
    print(f"\nA conferência falhou. {conselho}")
    print("Mande o arquivo conferencia.txt num Chamado da Academy.")
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pasta", type=Path, default=RAIZ, help="raiz do kit (onde fica o .fabrica-ok)")
    ap.add_argument("--testes", type=Path, default=None, help="pasta dos testes (padrão: a dos helpers)")
    ap.add_argument("--tudo", action="store_true", help="a suíte inteira, não só a conferência rápida")
    a = ap.parse_args()
    sys.exit(0 if confere(a.pasta, a.testes, tudo=a.tudo) else 1)


if __name__ == "__main__":
    main()
