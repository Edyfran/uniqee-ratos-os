"""Smoke test do porteiro: o mapa acha a função, o olhar faz resumo e no máximo duas folhas, o hook nega com a versão barata.

Roda no Mac, no Windows e no Linux (no pacote da Fábrica, o `testa` roda nos dois últimos). O Vision é só do Mac:
os casos dele pulam onde não há. O caso "sem Vision" roda em todo sistema, e é o único que o Windows e o Linux vivem:
no Mac ele simula os dois com OLHAR_SEM_VISION=1.

    python tools/economia/test_economia.py        (ou pytest, que roda cada test_*)
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

AQUI = Path(__file__).parent
PY = sys.executable
sys.path.insert(0, str(AQUI))

_REG = tempfile.TemporaryDirectory()  # o registro do teste: nunca o da máquina de quem roda
os.environ["ECONOMIA_REGISTRO"] = str(Path(_REG.name) / "economia.jsonl")
import hook  # noqa: E402
from leitura import avalia, frases  # noqa: E402
from olhar import tem_vision  # noqa: E402

SEM_VISION = {**os.environ, "OLHAR_SEM_VISION": "1"}  # o que o Windows e o Linux vivem: sem swiftc


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", *map(str, args)], check=True)


def olhar(*args, env=None):
    return subprocess.run([PY, AQUI / "olhar.py", *map(str, args)], check=True, capture_output=True, text=True,
                          encoding="utf-8", env=env)


def _hook(entrada, env=None):
    r = subprocess.run([PY, AQUI / "hook.py"], input=json.dumps(entrada), capture_output=True, text=True,
                       encoding="utf-8", check=True, env=env, timeout=150)
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if r.stdout.strip() else None


def test_mapa_acha_funcao_com_faixa_de_linhas():
    m = subprocess.run([PY, AQUI / "mapa.py", AQUI / "olhar.py"], capture_output=True, text=True, encoding="utf-8",
                       check=True).stdout
    assert "def folha" in m and "-" in m.split("def folha")[0].split("\n")[-1], m


def test_olhar_com_vision_no_mac():
    if not tem_vision():
        print("  (pulado: sem Vision nesta máquina)")
        return
    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "t.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10:duration=4", "-pix_fmt", "yuv420p", v)
        out = Path(d) / "o"
        olhar(v, "-n", "30", "-o", out, "--parecido", "-1")
        assert (out / "RESUMO.md").exists()
        assert len(sorted(out.glob("folha*.jpg"))) == 2  # 30 pedidos, teto de 24, duas folhas
        assert (out / "RESUMO.md").read_text(encoding="utf-8").count("\n| ") == 25  # cabeçalho + 24 quadros

        parado = Path(d) / "parado.mp4"  # tela parada: a impressão do Vision junta tudo num quadro
        ffmpeg("-f", "lavfi", "-i", "color=c=gray:size=1280x720:duration=6", "-pix_fmt", "yuv420p", parado)
        out2 = Path(d) / "o2"
        olhar(parado, "-o", out2)
        r = (out2 / "RESUMO.md").read_text(encoding="utf-8")
        assert "11 repetidos fora" in r and r.count("\n| ") == 2, r


def test_olhar_sem_vision_vale_no_windows_e_no_linux():
    """Sem swiftc a folha sai igual, sem texto nem rosto, e o resumo diz que isso é só do Mac."""
    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "t.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10:duration=4", "-pix_fmt", "yuv420p", v)
        out = Path(d) / "o"
        olhar(v, "-n", "30", "-o", out, env=SEM_VISION)
        r = (out / "RESUMO.md").read_text(encoding="utf-8")
        assert len(sorted(out.glob("folha*.jpg"))) == 2, r
        assert r.count("\n| ") == 25 and "só são lidos no Mac" in r and "rostos" not in r, r  # cabeçalho + 24 quadros

        parado = Path(d) / "parado.mp4"  # sem o Vision não há como juntar quadros iguais: ficam os 12
        ffmpeg("-f", "lavfi", "-i", "color=c=gray:size=1280x720:duration=6", "-pix_fmt", "yuv420p", parado)
        olhar(parado, "-o", Path(d) / "o2", env=SEM_VISION)
        r = (Path(d) / "o2" / "RESUMO.md").read_text(encoding="utf-8")
        assert r.count("\n| ") == 13 and "repetidos" not in r, r

        imgs = Path(d) / "imgs"  # pasta de imagens: a medida vem do ffprobe, não do sips do Mac
        imgs.mkdir()
        for k in range(3):
            ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360", "-frames:v", "1", imgs / f"q{k}.png")
        olhar(imgs, "-o", Path(d) / "o3", env=SEM_VISION)
        r = (Path(d) / "o3" / "RESUMO.md").read_text(encoding="utf-8")
        assert "3 imagens, 640×360" in r and r.count("\n| ") == 4, r


def test_registro_no_lugar_de_log_de_cada_sistema():
    h = Path("/casa")
    assert hook.pasta_de_log("darwin", {}, h) == h / "Library" / "Logs"
    assert hook.pasta_de_log("linux", {}, h) == h / ".local" / "state" / "economia"
    assert hook.pasta_de_log("linux", {"XDG_STATE_HOME": "/estado"}, h) == Path("/estado/economia")
    assert hook.pasta_de_log("win32", {"LOCALAPPDATA": "/local"}, h) == Path("/local/economia")
    assert hook.pasta_de_log("win32", {}, h) == h / "AppData" / "Local" / "economia"
    assert hook.pasta_de_log().is_absolute()


def test_hook_nega_arquivo_grande_com_o_mapa():
    grande = AQUI.parent / "video-use" / "helpers" / "fabrica.py"
    assert "Mapa abaixo" in _hook({"tool_name": "Read", "tool_input": {"file_path": str(grande)}})
    assert _hook({"tool_name": "Read", "tool_input": {"file_path": str(grande), "limit": 50}}) is None
    assert _hook({"tool_name": "Read", "tool_input": {"file_path": str(AQUI / "mapa.py")}}) is None  # pequeno
    assert "Mapa abaixo" in _hook({"tool_name": "Bash", "tool_input": {"command": f"cat {grande}"}})
    assert _hook({"tool_name": "Bash", "tool_input": {"command": f"cat {grande} | head"}}) is None
    assert "Mapa abaixo" in _hook({"tool_name": "Bash", "cwd": str(AQUI.anchor),
                                   "tool_input": {"command": f"cd {grande.parent} && cat {grande.name}"}})
    linhas = [json.loads(l) for l in Path(os.environ["ECONOMIA_REGISTRO"]).read_text(encoding="utf-8").splitlines()]
    assert linhas and all(l["tipo"] == "codigo" and l["devolvido"] < l["bruto"] for l in linhas), linhas  # o porteiro anota


def _fluxo_de_imagens(env=None, sem_vision=False):
    with tempfile.TemporaryDirectory() as d:
        for k in range(4):
            ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360", "-frames:v", "1", f"{d}/q{k}.png")
        sess = f"teste-{os.getpid()}"
        ler = lambda k: _hook({"tool_name": "Read", "session_id": sess, "tool_input": {"file_path": f"{d}/q{k}.png"}}, env)
        try:
            assert ler(0) is None and ler(1) is None
            r = ler(2)
            assert "Rodei o olhar.py" in r and (not sem_vision or "só são lidos no Mac" in r), r
            assert all(ler(k % 4) is None for k in range(4))  # 4 soltos depois do resumo
            assert "A pasta não mudou" in ler(0)  # o 5º volta pro resumo, sem rodar de novo
            time.sleep(1.1)
            ffmpeg("-f", "lavfi", "-i", "testsrc=size=640x360", "-frames:v", "1", "-y", f"{d}/q1.png")  # render novo por cima
            assert "A pasta mudou" in ler(1)
            assert _hook({"tool_name": "Read", "session_id": sess,
                          "tool_input": {"file_path": "/tmp/x/crivo/tela9.png"}}, env) is None
        finally:
            (hook.ESTADO / f"{sess}.json").unlink(missing_ok=True)


def test_hook_troca_quadros_soltos_pela_folha_sem_vision():
    _fluxo_de_imagens(SEM_VISION, sem_vision=True)


def test_hook_troca_quadros_soltos_pela_folha_com_vision():
    if tem_vision():
        _fluxo_de_imagens()


def test_hook_doc_longo_e_regra():
    # doc longo fora das regras: nega com mapa (frases podem ser "(sem resumo)" sem o modelo; a negação não muda)
    doc = AQUI.parents[1] / "roteiros/fabrica-de-conteudo/PACOTE.md"
    if doc.exists():
        assert "Mapa por título" in _hook({"tool_name": "Read", "tool_input": {"file_path": str(doc)}})
    regra = AQUI.parents[1] / "CLAUDE.md"
    r = _hook({"tool_name": "Read", "tool_input": {"file_path": str(regra)}})
    assert r is None or "É regra" in r  # regra nunca leva frase do modelo


def test_skill_do_kit_passa_inteira():
    """O agente do aluno lê o SKILL.md das skills fabrica-* inteiro, no .claude e no .agents; a regra longa de qualquer
    outra skill segue negada."""
    with tempfile.TemporaryDirectory() as d:
        for base in (".claude", ".agents"):
            for skill, nega in (("fabrica-de-conteudo", False), ("outra-skill", True)):
                p = Path(d) / base / "skills" / skill / "SKILL.md"
                p.parent.mkdir(parents=True)
                p.write_text("# Título\n\n" + "texto da regra longa. " * 800, encoding="utf-8")  # ~17 mil bytes, acima de DOC
                dec = avalia("Read", {"file_path": str(p)}, barato=False)
                assert (dec is not None) == nega and (dec is None or dec.tipo == "regra"), (p, dec)


def test_transcript_vira_frases_com_tempo():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "transcripts"
        t.mkdir()
        palavras = [{"type": "word", "text": f"p{k}", "start": k * 0.3, "end": k * 0.3 + 0.2} for k in range(2000)]
        palavras[1000]["start"] += 2  # silêncio quebra a frase
        (t / "voz.json").write_text(json.dumps({"words": palavras}), encoding="utf-8")
        dec = avalia("Read", {"file_path": str(t / "voz.json")}, barato=False)
        assert dec and dec.tipo == "transcript" and not dec.motivo  # placar não roda nada pesado
        assert len(frases(t / "voz.json")) == 2 and len(frases(t / "voz.json", 0, 10)) == 1


def test_custo_por_episodio():
    if (AQUI / "custo.py").exists():  # medida do dono: o pacote do aluno não leva
        subprocess.run([PY, AQUI / "custo.py", "--teste"], check=True)  # jsonl de mentira, sem medidor


def main():
    casos = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    ok = 0
    for nome, fn in casos:
        try:
            fn()
            ok += 1
            print(f"ok     {nome[5:].replace('_', ' ')}")
        except Exception as e:
            print(f"FALHOU {nome[5:].replace('_', ' ')}: {e!r}")
    print(f"{ok}/{len(casos)} passaram")
    raise SystemExit(0 if ok == len(casos) else 1)


if __name__ == "__main__":
    main()
