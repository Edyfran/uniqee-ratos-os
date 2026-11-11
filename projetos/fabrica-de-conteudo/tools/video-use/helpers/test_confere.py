"""A conferência escreve `.fabrica-ok` ou `conferencia.txt`, e diz o conserto em português.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_confere.py
"""
import sys
import tempfile
from pathlib import Path

import confere


def _kit(tmp: Path, teste: str) -> tuple[Path, Path]:
    """Um kit de mentira: VERSAO e uma pasta de testes com um arquivo só."""
    raiz = tmp / "kit"
    testes = raiz / "testes"
    testes.mkdir(parents=True)
    (raiz / "VERSAO").write_text("9.9.9-teste\n", encoding="utf-8")
    (testes / "test_falso.py").write_text(teste, encoding="utf-8")
    return raiz, testes


def test_passa_e_grava_o_marcador(tmp: Path):
    raiz, testes = _kit(tmp, "def test_ok():\n    assert True\n")
    (raiz / ".fabrica-ok").write_text("velho", encoding="utf-8")
    assert confere.confere(raiz, testes, exige_ffmpeg=False) is True
    assert (raiz / ".fabrica-ok").read_text(encoding="utf-8").split()[0] != "velho"
    assert not (raiz / "conferencia.txt").exists()


def test_falha_grava_a_conferencia_e_apaga_o_marcador(tmp: Path):
    raiz, testes = _kit(tmp, "def test_ruim():\n    assert 1 == 2\n")
    (raiz / ".fabrica-ok").write_text("velho", encoding="utf-8")
    assert confere.confere(raiz, testes, exige_ffmpeg=False) is False
    assert not (raiz / ".fabrica-ok").exists()
    nota = (raiz / "conferencia.txt").read_text(encoding="utf-8")
    assert "9.9.9-teste" in nota and "assert 1 == 2" in nota


def test_avisa_os_testes_que_e_a_conferencia(tmp: Path):
    raiz, testes = _kit(tmp, "import os\ndef test_flag():\n    assert os.environ.get('FABRICA_CONFERENCIA') == '1'\n")
    assert confere.confere(raiz, testes, exige_ffmpeg=False) is True


def test_versao_ausente_diz_sem_versao(tmp: Path):
    assert confere._versao(tmp) == "sem versão"


def test_diagnostico_do_sandbox_do_codex():
    saida = "playwright._impl._errors.Error: BrowserType.launch: Permission denied (1100) chromium"
    assert "Acesso total" in confere.diagnostico(saida)


def test_diagnosticos_conhecidos_e_o_desconhecido():
    assert "uv sync" in confere.diagnostico("ModuleNotFoundError: No module named 'numpy'")
    assert "PYTHONUTF8" in confere.diagnostico("UnicodeDecodeError: 'charmap' codec cp1252")
    assert "playwright install" in confere.diagnostico("Executable doesn't exist at /x")
    assert "PATH" in confere.diagnostico("FileNotFoundError: ffmpeg")
    assert "Defeito do pacote" in confere.diagnostico("AssertionError: 1 == 2")
    # `Permission denied` sozinho (sem Chromium) não é o sandbox do Codex
    assert "Acesso total" not in confere.diagnostico("PermissionError: Permission denied: 'x.txt'")


def test_defeito_do_pacote_nao_para_o_aluno():
    """22/10: no Windows sem git, o agente leu "pare" e o aluno ficou sem onboarding. O defeito
    vai pro Chamado e o trabalho segue; o que não muda é não mexer em teste nem helper."""
    aviso = confere.diagnostico("AssertionError: 1 == 2")
    assert "pare" not in aviso.lower(), aviso
    assert "siga" in aviso and "conferencia.txt" in aviso and "não edite" in aviso, aviso


def test_modulo_e_arquivo_largos_demais_viram_defeito_do_pacote():
    # helper local ou módulo que o pyproject não declara: defeito do pacote, não `uv sync`
    assert "Defeito do pacote" in confere.diagnostico("ModuleNotFoundError: No module named 'corte_suave'")
    assert "Defeito do pacote" in confere.diagnostico("ModuleNotFoundError: No module named 'inventado'")
    # submódulo de dependência declarada (PIL é o pillow; faster_whisper, o faster-whisper)
    assert "uv sync" in confere.diagnostico("ModuleNotFoundError: No module named 'PIL.Image'")
    assert "uv sync" in confere.diagnostico("ModuleNotFoundError: No module named 'faster_whisper'")
    # FileNotFoundError só é PATH velho quando o arquivo é o ffmpeg/ffprobe
    assert "PATH" in confere.diagnostico("FileNotFoundError: [Errno 2] No such file or directory: 'ffprobe'")
    assert "Defeito do pacote" in confere.diagnostico(
        "FileNotFoundError: [Errno 2] No such file or directory: 'assets/falta.json'")


def test_o_padrao_e_o_subconjunto_rapido_e_tudo_e_a_pasta_inteira():
    assert confere._alvos(None, tudo=False) == [confere.HELPERS / n for n in confere.RAPIDOS]
    assert confere._alvos(None, tudo=True) == ([confere.HELPERS, confere.ECONOMIA] if confere.ECONOMIA.is_file()
                                              else [confere.HELPERS]), "a suíte inteira leva o teste do porteiro, onde ele mora"
    assert confere._alvos(Path("/x/testes"), tudo=False) == [Path("/x/testes")]   # pasta pedida ganha


def test_todo_teste_rapido_existe_e_vai_no_pacote():
    for n in confere.RAPIDOS:
        assert (confere.HELPERS / n).exists(), f"{n} está no RAPIDOS e não existe"
    try:
        sys.path.insert(0, str(confere.HELPERS.parent))
        import empacota_kit
    except ImportError:   # no pacote não há empacotador: quem confere o RAPIDOS é o repositório
        return
    fora = [n for n in confere.RAPIDOS if n not in empacota_kit.FABRICA_TESTES]
    assert not fora, f"o pacote não leva {fora}: a conferência rápida falharia na máquina do aluno"


def test_tudo_na_linha_de_comando_chega_na_conferencia():
    vistos, velho, argv = [], confere.confere, sys.argv
    confere.confere = lambda raiz, testes=None, exige_ffmpeg=True, tudo=False: vistos.append(tudo) or True
    try:
        for args in ([], ["--tudo"]):
            sys.argv = ["confere.py", *args]
            try:
                confere.main()
            except SystemExit as e:
                assert e.code == 0
    finally:
        confere.confere, sys.argv = velho, argv
    assert vistos == [False, True], vistos


def main() -> None:
    casos = [
        ("passa e grava o marcador", test_passa_e_grava_o_marcador),
        ("falha grava a conferência", test_falha_grava_a_conferencia_e_apaga_o_marcador),
        ("avisa que é a conferência", test_avisa_os_testes_que_e_a_conferencia),
        ("sem VERSAO", test_versao_ausente_diz_sem_versao),
        ("sandbox do Codex", test_diagnostico_do_sandbox_do_codex),
        ("diagnósticos", test_diagnosticos_conhecidos_e_o_desconhecido),
        ("defeito do pacote não para o aluno", test_defeito_do_pacote_nao_para_o_aluno),
        ("diagnóstico estreito", test_modulo_e_arquivo_largos_demais_viram_defeito_do_pacote),
        ("rápido por padrão, --tudo a pasta inteira", test_o_padrao_e_o_subconjunto_rapido_e_tudo_e_a_pasta_inteira),
        ("o rápido existe e vai no pacote", test_todo_teste_rapido_existe_e_vai_no_pacote),
        ("--tudo chega na conferência", test_tudo_na_linha_de_comando_chega_na_conferencia),
    ]
    ok = 0
    for nome, fn in casos:
        try:
            if fn.__code__.co_varnames[:1] == ("tmp",):
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            ok += 1
            print(f"ok     {nome}")
        except Exception as e:
            print(f"FALHOU {nome}: {e!r}")
    print(f"{ok}/{len(casos)} passaram")
    raise SystemExit(0 if ok == len(casos) else 1)


if __name__ == "__main__":
    main()
