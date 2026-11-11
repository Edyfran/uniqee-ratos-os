"""A atualização da Fábrica troca o que é do kit, guarda o que sai e não encosta no que é do aluno.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_atualiza.py
"""
import contextlib
import io
import json
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import atualiza

PASTA = "fabrica-de-conteudo"


def _zip(onde: Path, nome: str, arquivos: dict, versao: str, pasta: str = PASTA) -> Path:
    """O ZIP como o zipa.py monta: com a pasta raiz (Fábrica) ou sem ela (módulo), e o VERSAO."""
    zp = onde / nome
    with zipfile.ZipFile(zp, "w") as z:
        for caminho, texto in {**arquivos, "VERSAO": f"{versao}\n"}.items():
            z.writestr(f"{pasta}/{caminho}" if pasta else caminho, texto)
    return zp


def _fabrica(onde: Path, versao: str, arquivos: dict) -> Path:
    """Uma Fábrica instalada, com o que é do aluno espalhado nela."""
    raiz = onde / "instalada"
    for caminho, texto in {**arquivos, "VERSAO": f"{versao} abc1234\n",
                           ".env.local": "ELEVENLABS_API_KEY=segredo\n", ".fabrica-ok": "ok\n",
                           "marca/MARCA.md": "# minha marca\n", "onboarding/escolhas.json": '{"estilo": "x"}\n',
                           "videos/reel-do-aluno/final.mp4": "video dele\n",
                           "videos/LEIA-ME.md": "leia-me velho\n"}.items():
        (raiz / caminho).parent.mkdir(parents=True, exist_ok=True)
        (raiz / caminho).write_text(texto, encoding="utf-8")
    return raiz


def _foto(raiz: Path) -> dict:
    return {a.relative_to(raiz).as_posix(): a.read_bytes() for a in sorted(raiz.rglob("*")) if a.is_file()}


def _roda(raiz: Path, zips: list, seco: bool = False) -> str:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        atualiza.atualiza(raiz, zips, seco)
    return saida.getvalue()


def _recusa(raiz: Path, zips: list) -> str:
    try:
        _roda(raiz, zips)
    except SystemExit as e:
        return str(e.code)
    raise AssertionError("era para recusar")


def _ler(arq: Path) -> str:
    return arq.read_text(encoding="utf-8")


def test_versao_em_tupla():
    assert atualiza.versao_em_tupla("2026.10.22") == (2026, 10, 22, 0)
    assert atualiza.versao_em_tupla("2026.10.22.2 a0fafaf") == (2026, 10, 22, 2)
    assert atualiza.versao_em_tupla("2026.10.22") < atualiza.versao_em_tupla("2026.10.22.2")
    assert atualiza.versao_em_tupla("2026.10.22.10") > atualiza.versao_em_tupla("2026.10.22.9")
    assert atualiza.versao_em_tupla("") == () and atualiza.versao_em_tupla("sem versão") == ()


def test_troca_guarda_a_copia_e_traz_o_novo(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho", "tools/b.py": "igual", "pyproject.toml": "dep=1"})
    zp = _zip(tmp, "novo.zip", {"tools/a.py": "novo", "tools/b.py": "igual", "tools/c.py": "c novo",
                                "pyproject.toml": "dep=2"}, "2026.10.22.2 def5678")
    saida = _roda(raiz, [zp])
    assert _ler(raiz / "tools/a.py") == "novo" and _ler(raiz / "tools/c.py") == "c novo"
    assert _ler(raiz / ".fabrica/copia/2026.10.22/tools/a.py") == "velho"
    assert not (raiz / ".fabrica/copia/2026.10.22/tools/b.py").exists(), "o que não mudou não vai pra cópia"
    assert _ler(raiz / "VERSAO").strip() == "2026.10.22.2 def5678"
    lista = _ler(raiz / ".fabrica/arquivos.txt").splitlines()
    assert lista[0] == "# 2026.10.22.2 def5678" and set(lista[1:]) == {"tools/a.py", "tools/b.py", "tools/c.py",
                                                                      "pyproject.toml"}
    assert "2026.10.22 -> 2026.10.22.2" in saida and "uv sync" in saida and "confere.py" in saida
    assert "VERSAO" not in lista, "o VERSAO não é arquivo do kit na lista"


def test_nao_pede_uv_sync_sem_mudar_dependencia(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho", "pyproject.toml": "dep=1"})
    saida = _roda(raiz, [_zip(tmp, "n.zip", {"tools/a.py": "novo", "pyproject.toml": "dep=1"}, "2026.10.23")])
    assert "uv sync" not in saida and "confere.py" in saida


def test_o_que_e_do_aluno_fica_intacto(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho"})
    antes = _foto(raiz)
    zp = _zip(tmp, "novo.zip", {
        "tools/a.py": "novo",
        ".env.local": "CHAVE=do-zip\n", ".fabrica-ok": "do zip", "conferencia.txt": "do zip",
        "marca/MARCA.md": "do zip", "onboarding/escolhas.json": "do zip", "biblioteca.html": "do zip",
        "videos/reel-do-aluno/final.mp4": "do zip", "videos/outro/novo.mp4": "do zip",
        "videos/LEIA-ME.md": "leia-me novo\n",
    }, "2026.10.22.2")
    saida = _roda(raiz, [zp])
    depois = _foto(raiz)
    for caminho in (".env.local", ".fabrica-ok", "marca/MARCA.md", "onboarding/escolhas.json",
                    "videos/reel-do-aluno/final.mp4"):
        assert depois[caminho] == antes[caminho], caminho
    assert not {"conferencia.txt", "biblioteca.html", "videos/outro/novo.mp4"} & set(depois)
    assert not [c for c in depois if c.startswith(".fabrica/copia/") and not c.endswith(("tools/a.py", "LEIA-ME.md"))]
    # a única coisa do kit que mora em videos/ é o LEIA-ME: troca, com cópia
    assert _ler(raiz / "videos/LEIA-ME.md") == "leia-me novo\n"
    assert _ler(raiz / ".fabrica/copia/2026.10.22/videos/LEIA-ME.md") == "leia-me velho\n"
    assert "não toquei" in saida
    assert "videos/reel-do-aluno/final.mp4" not in _ler(raiz / ".fabrica/arquivos.txt")


def test_o_que_saiu_do_kit_vai_para_a_copia_pela_lista(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/video-use/helpers/a.py": "a", "tools/video-use/helpers/x.py": "x"})
    _roda(raiz, [_zip(tmp, "v2.zip", {"tools/video-use/helpers/a.py": "a", "tools/video-use/helpers/x.py": "x"},
                      "2026.10.22.1")])
    # o módulo do aluno mora na mesma pasta e não é do ZIP da Fábrica
    (raiz / "tools/video-use/helpers/narra.py").write_text("do modulo", encoding="utf-8")
    saida = _roda(raiz, [_zip(tmp, "v3.zip", {"tools/video-use/helpers/a.py": "a"}, "2026.10.22.2")])
    assert not (raiz / "tools/video-use/helpers/x.py").exists()
    assert _ler(raiz / ".fabrica/copia/2026.10.22.1/tools/video-use/helpers/x.py") == "x"
    assert _ler(raiz / "tools/video-use/helpers/narra.py") == "do modulo"
    assert "movidos para a cópia: 1" in saida


def test_sem_lista_so_move_das_pastas_so_do_kit(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {
        "tools/v2/nucleo/velho.js": "velho", "tools/v2/nucleo/fica.js": "fica",
        "tools/video-use/helpers/narra.py": "do modulo", "tools/video-use/helpers/test_ouvido.py": "do modulo",
        "tools/v2/pecas/minha.html": "peca do aluno", "docs/anotacao.md": "dele"})
    (raiz / "tools/v2/nucleo/__pycache__").mkdir()
    (raiz / "tools/v2/nucleo/__pycache__/x.pyc").write_bytes(b"cache")
    assert not (raiz / ".fabrica/arquivos.txt").exists()
    _roda(raiz, [_zip(tmp, "n.zip", {"tools/v2/nucleo/fica.js": "fica"}, "2026.10.22.2")])
    assert not (raiz / "tools/v2/nucleo/velho.js").exists()
    assert _ler(raiz / ".fabrica/copia/2026.10.22/tools/v2/nucleo/velho.js") == "velho"
    for fica in ("tools/video-use/helpers/narra.py", "tools/video-use/helpers/test_ouvido.py",
                 "tools/v2/pecas/minha.html", "docs/anotacao.md", "tools/v2/nucleo/__pycache__/x.pyc"):
        assert (raiz / fica).exists(), fica


def test_zip_slip_recusa_o_zip_inteiro_sem_escrever(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho"})
    for ruim in ("../fora.txt", "tools/../../fora.txt", "/abs/fora.txt", "C:/Windows/fora.txt",
                 "tools\\..\\fora.txt"):
        zp = _zip(tmp, "ruim.zip", {"tools/a.py": "novo", ruim: "x"}, "2026.10.22.2")
        antes = _foto(tmp)
        assert "recusado" in _recusa(raiz, [zp]), ruim
        assert _foto(tmp) == antes, f"escreveu algo com {ruim}"
        assert not (tmp / "fora.txt").exists()
    # o mesmo vale com a pasta raiz já tirada, e no ZIP de módulo
    zp = _zip(tmp, "mod.zip", {"../fora.txt": "x"}, "2026.10.22.2", pasta="")
    assert "recusado" in _recusa(raiz, [zp])


def test_zip_quebrado_ou_sem_versao_recusa(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho"})
    (tmp / "lixo.zip").write_bytes(b"isto nao e um zip")
    assert "ZIP" in _recusa(raiz, [tmp / "lixo.zip"])
    sem = tmp / "sem.zip"
    with zipfile.ZipFile(sem, "w") as z:
        z.writestr(f"{PASTA}/tools/a.py", "novo")
    assert "VERSAO" in _recusa(raiz, [sem])
    assert _ler(raiz / "tools/a.py") == "velho"


def test_versao_igual_ou_mais_velha_nao_mexe(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22.2", {"tools/a.py": "meu"})
    antes = _foto(raiz)
    for versao in ("2026.10.22.2", "2026.10.22.1", "2026.10.22", "2026.10.20"):
        saida = _roda(raiz, [_zip(tmp, "z.zip", {"tools/a.py": "do zip"}, versao)])
        assert "já está na versão 2026.10.22.2" in saida
        assert _foto(raiz) == antes, versao


def test_seco_mostra_e_nao_escreve(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {"tools/a.py": "velho", "tools/x.py": "sai"})
    _roda(raiz, [_zip(tmp, "v2.zip", {"tools/a.py": "velho", "tools/x.py": "sai"}, "2026.10.22.1")])
    antes = _foto(raiz)
    zp = _zip(tmp, "v3.zip", {"tools/a.py": "novo", "tools/b.py": "b"}, "2026.10.22.2")
    saida = _roda(raiz, [zp], seco=True)
    assert _foto(raiz) == antes
    assert "seco" in saida and "trocados: 1" in saida and "novos: 1" in saida and "movidos para a cópia: 1" in saida


def test_modulo_sem_pasta_raiz_tem_versao_propria(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22.2", {"tools/video-use/helpers/agenda.py": "modulo velho"})
    zp = _zip(tmp, "fabrica-posta.zip", {"tools/video-use/helpers/agenda.py": "modulo novo",
                                         ".agents/skills/fabrica-posta/SKILL.md": "skill"}, "2026.10.22.2", pasta="")
    # módulo sem lista nunca foi atualizado por aqui: entra mesmo na versão da Fábrica
    saida = _roda(raiz, [zp])
    assert "fabrica-posta:" in saida
    assert _ler(raiz / "tools/video-use/helpers/agenda.py") == "modulo novo"
    assert _ler(raiz / ".agents/skills/fabrica-posta/SKILL.md") == "skill"
    assert _ler(raiz / "VERSAO").strip() == "2026.10.22.2 abc1234", "o ZIP de módulo não mexe no VERSAO da Fábrica"
    assert _ler(raiz / ".fabrica/arquivos-fabrica-posta.txt").splitlines()[0] == "# 2026.10.22.2"
    # agora a lista dele diz a versão: repetir não mexe
    assert "já está na versão 2026.10.22.2" in _roda(raiz, [zp])
    # a Fábrica e o módulo juntos, na mesma versão nova: os dois entram
    fabrica = _zip(tmp, "f.zip", {"tools/a.py": "novo"}, "2026.10.23")
    novo_mod = _zip(tmp, "fabrica-posta (1).zip", {"tools/video-use/helpers/agenda.py": "modulo 3"}, "2026.10.23",
                    pasta="")
    _roda(raiz, [novo_mod, fabrica])
    assert _ler(raiz / "tools/a.py") == "novo" and _ler(raiz / "tools/video-use/helpers/agenda.py") == "modulo 3"


def test_procura_escolhe_pela_versao_de_dentro(tmp: Path):
    raiz = _fabrica(tmp, "2026.10.22", {".agents/skills/fabrica-posta/SKILL.md": "skill"})
    baixados = tmp / "Downloads"
    baixados.mkdir()
    velho = _zip(baixados, "fabrica-de-conteudo-com-ia.zip", {"tools/a.py": "1"}, "2026.10.22.1")
    novo = _zip(baixados, "fabrica-de-conteudo-com-ia (1).zip", {"tools/a.py": "2"}, "2026.10.22.3")
    velho.touch()       # o mais recente no disco é o mais velho por dentro
    posta = _zip(baixados, "fabrica-posta.zip", {"x": "y"}, "2026.10.22.3", pasta="")
    _zip(baixados, "fabrica-clone.zip", {"x": "y"}, "2026.10.22.3", pasta="")     # módulo que não está instalado
    _zip(baixados, "pack-todos.zip", {"x": "y"}, "2026.10.22.3", pasta="")
    achados = atualiza.procura([baixados, tmp / "nao-existe"], raiz)
    assert sorted(a.name for a in achados) == sorted([novo.name, posta.name])
    assert atualiza.procura([tmp / "vazia"], raiz) == []


def test_pasta_sem_versao_nao_e_fabrica_de_zip(tmp: Path):
    """O tronco do dono não tem VERSAO: a ferramenta recusa em vez de despejar o ZIP em cima dele."""
    raiz = tmp / "tronco"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "tools/a.py").write_text("meu", encoding="utf-8")
    antes = _foto(raiz)
    assert "VERSAO" in _recusa(raiz, [_zip(tmp, "z.zip", {"tools/a.py": "do zip"}, "2026.10.22.2")])
    assert _foto(raiz) == antes


def test_o_settings_do_aluno_junta_o_porteiro_e_guarda_o_resto(tmp: Path):
    """O .claude/settings.json é do kit (o hook do porteiro) e do aluno (permissões, outros hooks): junta, não troca."""
    porteiro = lambda v: {"matcher": "Read|Bash", "hooks": [{"type": "command", "command": f"py tools/economia/hook.py {v}"}]}
    meu = {"permissions": {"allow": ["Bash(ls:*)"]},
           "hooks": {"PreToolUse": [porteiro("v1"), {"matcher": "Write", "hooks": [{"type": "command", "command": "meu-hook.sh"}]}],
                     "Stop": [{"hooks": [{"type": "command", "command": "avisa.sh"}]}]}}
    kit = {"hooks": {"PreToolUse": [porteiro("v2")]}}
    raiz = _fabrica(tmp, "2026.10.22", {".claude/settings.json": json.dumps(meu)})
    saida = _roda(raiz, [_zip(tmp, "novo.zip", {".claude/settings.json": json.dumps(kit)}, "2026.10.22.2")])
    depois = json.loads(_ler(raiz / ".claude/settings.json"))
    assert depois["permissions"] == meu["permissions"] and depois["hooks"]["Stop"] == meu["hooks"]["Stop"], depois
    assert [h["command"] for g in depois["hooks"]["PreToolUse"] for h in g["hooks"]] == \
        ["meu-hook.sh", "py tools/economia/hook.py v2"], depois      # a entrada velha do porteiro saiu, a do aluno ficou
    assert json.loads(_ler(raiz / ".fabrica/copia/2026.10.22/.claude/settings.json")) == meu, "a cópia é a dele"
    assert ".claude/settings.json" in saida
    # sem settings na pasta: entra o do ZIP como veio
    (tmp / "b").mkdir()
    raiz2 = _fabrica(tmp / "b", "2026.10.22", {})
    _roda(raiz2, [_zip(tmp / "b", "novo.zip", {".claude/settings.json": json.dumps(kit)}, "2026.10.22.2")])
    assert json.loads(_ler(raiz2 / ".claude/settings.json")) == kit
    # JSON do aluno que não lê, ou já em dia: fica como está
    assert atualiza.junta_settings(b"{nao e json", json.dumps(kit).encode()) == b"{nao e json"
    em_dia = json.dumps(depois).encode()
    assert atualiza.junta_settings(em_dia, json.dumps(kit).encode()) == em_dia


def test_aviso_de_versao(tmp: Path):
    raiz = tmp / "f"
    raiz.mkdir()
    assert atualiza.aviso_de_versao(raiz, date(2026, 10, 30)) is None, "sem VERSAO (o tronco): sem aviso"
    (raiz / "VERSAO").write_text("2026.10.22.2 a0fafaf\n", encoding="utf-8")
    assert atualiza.aviso_de_versao(raiz, date(2026, 10, 28)) is None, "6 dias: sem aviso"
    aviso = atualiza.aviso_de_versao(raiz, date(2026, 10, 29))
    assert aviso and "22/10" in aviso and "/atualizar" in aviso and "atualiza a fábrica" in aviso, "7 dias: avisa"
    (raiz / "VERSAO").write_text("lixo\n", encoding="utf-8")
    assert atualiza.aviso_de_versao(raiz, date(2026, 12, 1)) is None


def main() -> None:
    casos = [(n[5:].replace("_", " "), f) for n, f in sorted(globals().items(), key=lambda kv: kv[0])
             if n.startswith("test_") and callable(f)]
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
