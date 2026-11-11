"""Auto-teste da página do onboarding (tools/onboarding). Sem rede, sem vídeo, sem chave de ninguém.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_onboarding.py

A página recebe a chave paga do aluno e grava no .env.local dele: o que se cobra aqui é que a chave
não estraga as outras linhas, que nenhum outro site e nenhum caminho torto chegam ao arquivo, e que
o que a página lista (legendas, estilos) sai do código e do guia, não de uma lista à mão. E o
"gera pra mim": a IA do aluno roda sem cabeça, num subprocesso, e o que ela devolve só chega à tela depois de conferido.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "onboarding"))

import onboarding as ob


def test_a_chave_troca_a_linha_dela_e_mais_nenhuma(tmp: Path):
    env = tmp / ".env.local"
    env.write_text("# comentário do aluno\n#ELEVENLABS_API_KEY=\nVOZ_ID=abc123\nOUTRA=1\n", encoding="utf-8")
    ob.grava_env({"ELEVENLABS_API_KEY": "sk_teste", "HIGGSFIELD_KEY_ID": "hg"}, env)
    linhas = env.read_text(encoding="utf-8").splitlines()
    assert linhas[:4] == ["# comentário do aluno", "ELEVENLABS_API_KEY=sk_teste", "VOZ_ID=abc123", "OUTRA=1"], linhas
    assert linhas[4] == "HIGGSFIELD_KEY_ID=hg", linhas
    assert ob.le_env(env)["VOZ_ID"] == "abc123"


def test_a_chave_da_higgsfield_vem_inteira_e_parte_no_dois_pontos(tmp: Path):
    assert ob.campos_da_chave("higgsfield", {"HIGGSFIELD_KEY": " abc-123:s3gr:edo \n"}) == {
        "HIGGSFIELD_KEY_ID": "abc-123", "HIGGSFIELD_KEY_SECRET": "s3gr:edo"}
    assert ob.campos_da_chave("higgsfield", {"HIGGSFIELD_KEY": "sem-dois-pontos"})["HIGGSFIELD_KEY_SECRET"] == ""
    assert ob.campos_da_chave("elevenlabs", {"ELEVENLABS_API_KEY": " sk_1 "}) == {"ELEVENLABS_API_KEY": "sk_1"}


def test_o_sotaque_e_opcional_e_vira_a_marca_do_v4(tmp: Path):
    assert ob.marca_sotaque("nenhum") == "" and ob.marca_sotaque("") == ""
    assert ob.marca_sotaque("paulista") == "[in a Brazilian Portuguese accent from São Paulo]"
    assert ob.marca_sotaque("klingon") is None
    env = tmp / ".env.local"
    env.write_text("VOZ_ID=abc\n", encoding="utf-8")
    ob.grava_env({"VOZ_SOTAQUE": ob.marca_sotaque("carioca")}, env)
    assert ob.le_env(env)["VOZ_SOTAQUE"].endswith("Rio de Janeiro]") and ob.le_env(env)["VOZ_ID"] == "abc"


def test_a_pagina_lista_do_codigo_e_do_guia(tmp: Path):
    nomes = [u["nome"] for u in ob.legendas()]
    sys.path.insert(0, str(AQUI))
    import captions_viral
    assert nomes == list(captions_viral.PRESETS), "a lista de legendas não é a do captions_viral"
    estilos = ob.estilos()
    assert len(estilos) >= 12 and estilos[0]["slug"] == "neobrutalista", estilos
    assert all(len(e["cores"]) == 4 and e["letra"] and e["combina"] for e in estilos), estilos


def test_toda_letra_dos_temas_vem_no_kit(tmp: Path):
    """O tema aponta url(fontes/X); o agente copia X de tools/video-use/assets/fontes. Letra que não
    está lá cairia na letra do sistema no computador do aluno, sem ninguém ver."""
    import re
    fontes = ob.RAIZ / "tools/video-use/assets/fontes"
    for css in sorted((ob.RAIZ / "docs/guia-de-estilos").glob("*.css")):
        arqs = re.findall(r"url\(fontes/([^)]+)\)", css.read_text(encoding="utf-8"))
        assert arqs, f"{css.name} sem letra"
        for a in arqs:
            assert (fontes / a).is_file(), f"{css.name}: {a} não está em {fontes}"
    assert all(e["letras"]["fd"] and e["letras"]["fm"] for e in ob.estilos())


def _sobe(raiz: Path) -> tuple[ThreadingHTTPServer, str]:
    """O servidor de verdade, numa pasta de mentira."""
    for nome, valor in {"RAIZ": raiz, "PASTA": raiz / "onboarding", "ENV": raiz / ".env.local"}.items():
        setattr(ob, nome, valor)
    ob.ESTADO.update(escolhas={}, previa=None, agente={}, usos=[], legendas={}, fila=[],
                     estilos=[], gera={})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ob.Pagina)
    ob.Pagina.porta, ob.Pagina.token = srv.server_address[1], "tok"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{ob.Pagina.porta}"


def _get(url: str, **h) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def test_so_a_pagina_aberta_pelo_agente_le_e_grava(tmp: Path):
    raiz = (tmp / "fabrica").resolve()      # o servidor compara caminhos resolvidos (/var é /private/var)
    (raiz / "videos" / "exemplo").mkdir(parents=True)
    (raiz / "tools" / "video-use" / "helpers").mkdir(parents=True)
    (raiz / ".env.local").write_text("ELEVENLABS_API_KEY=segredo\n", encoding="utf-8")
    (raiz / "tools" / "video-use" / "helpers" / "x.py").write_text("print()", encoding="utf-8")
    (raiz / "videos" / "exemplo" / "a.mp4").write_bytes(b"0123456789")
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "PASTA", "ENV")}
    srv, url = _sobe(raiz)
    try:
        assert _get(url + "/api/estado")[0] == 403, "a API respondeu sem o token"
        assert _get(url + "/api/estado", **{"X-Fabrica": "errado"})[0] == 403
        st, corpo = _get(url + "/api/estado", **{"X-Fabrica": "tok"})
        assert st == 200 and b"segredo" not in corpo, corpo
        # a Fábrica principal só edita: sem os módulos, nenhuma ferramenta paga tem tela
        assert json.loads(corpo)["ferramentas"] == {}, corpo
        assert json.loads(corpo)["modulos"] == [], corpo
        # outro nome na porta da máquina é rebinding de DNS: nada responde
        assert _get(url + "/api/estado", **{"X-Fabrica": "tok", "Host": "malicioso.com"})[0] == 403
        for torto in ("/.env.local", "/videos/../.env.local", "/videos/%2e%2e/tools/video-use/helpers/x.py",
                      "/tools/video-use/helpers/x.py"):
            assert _get(url + torto)[0] == 404, torto
        st, corpo = _get(url + "/videos/exemplo/a.mp4", Range="bytes=2-5")
        assert st == 206 and corpo == b"2345", (st, corpo)
    finally:
        srv.shutdown()
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_a_marca_entra_na_peca_antes_dela_medir(tmp: Path):
    html = ob._injeta_marca("<html><head><title>x</title></head>", {
        "pp": "#FFF6E9", "ink": "#2B2238", "ac": "#E52E71", "mk": "red;}</style><script>",
        "fd": "Fraunces-Variable.ttf", "pfd": "340", "fm": "../../.env.local", "estilo": "pop"})
    cabeca = html.split("<title>")[0]
    assert "--pp:#FFF6E9;" in cabeca and "--fd:'MarcaFd'" in cabeca and "--ed-sans:'MarcaFd'" in cabeca, cabeca
    assert "font-weight:340;src:url(/tools/video-use/assets/fontes/Fraunces-Variable.ttf)" in cabeca, cabeca
    assert "/docs/guia-de-estilos/pop.css" in cabeca and "googleapis" not in cabeca, cabeca
    assert "<script>document.documentElement.classList.add('marca')</script>" in cabeca
    assert "red;" not in html, "cor fora do #RRGGBB entrou na peça"
    assert "MarcaFm" not in html and ".env" not in html, "letra fora da pasta de fontes entrou na peça"


def test_o_gera_pra_mim_confere_o_que_chega(tmp: Path):
    raiz = (tmp / "fabrica").resolve()
    (raiz / "onboarding" / "gerados").mkdir(parents=True)
    (raiz / "tools" / "video-use" / "assets" / "fontes").mkdir(parents=True)
    (raiz / "tools" / "video-use" / "assets" / "fontes" / "Jost-Variable.ttf").write_bytes(b"0")
    ger = raiz / "onboarding" / "gerados"
    (ger / "bom.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h9v9z"/></svg>', encoding="utf-8")
    (ger / "mau.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', encoding="utf-8")
    (raiz / "fora.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "PASTA", "ENV")}
    srv, url = _sobe(raiz)
    try:
        req = lambda c, corpo: urllib.request.urlopen(urllib.request.Request(url + c, data=json.dumps(corpo).encode(),
                                                      headers={"X-Fabrica": "tok"}), timeout=5).read()
        # sem Claude nem Codex no computador, a IA recusa e a página some com o botão
        achado = ob.shutil.which
        ob.shutil.which = lambda n: None
        try:
            assert json.loads(_get(url + "/api/estado", **{"X-Fabrica": "tok"})[1])["ia"] == ""
            try:
                req("/api/gera", {"o": "paleta", "sobre": "bolo"})
                assert False, "o gera pra mim rodou sem agente"
            except urllib.error.HTTPError as e:
                assert e.code == 400
        finally:
            ob.shutil.which = achado
        assert ob.limpa_opcoes("logo", [{"arquivo": "onboarding/gerados/bom.svg"}, {"arquivo": "onboarding/gerados/mau.svg"},
                                        {"arquivo": "fora.svg"}, {"arquivo": "onboarding/gerados/../../fora.svg"}]) \
            == [{"arquivo": "onboarding/gerados/bom.svg", "nome": ""}]
        assert len(ob.limpa_opcoes("paleta", [{"cores": {"pp": "#FFFFFF", "ink": "#000000", "ac": "#123456", "mk": "#ABCDEF"}},
                                              {"cores": {"pp": "red"}}])) == 1
        assert ob.limpa_opcoes("letras", [{"fd": {"arq": "Jost-Variable.ttf"}, "fm": {"arq": "Jost-Variable.ttf", "peso": "300"}},
                                          {"fd": {"arq": "Nao-Existe.ttf"}, "fm": {"arq": "Jost-Variable.ttf"}}])[0]["fm"]["peso"] == "300"
        try:
            req("/api/logo-gerado", {"arquivo": "onboarding/gerados/mau.svg"})
            assert False, "o logo com código entrou"
        except urllib.error.HTTPError as e:
            assert e.code == 400
        req("/api/logo-gerado", {"arquivo": "onboarding/gerados/bom.svg"})
        assert (raiz / "onboarding" / "logo.svg").read_text(encoding="utf-8").startswith("<svg")
        assert ob.ESTADO["escolhas"]["marca"]["logo"] == "onboarding/logo.svg"
        # a letra do tema, pelo caminho que o tema usa, sai da pasta de fontes do kit
        assert _get(url + "/docs/guia-de-estilos/fontes/Jost-Variable.ttf")[0] == 200
    finally:
        srv.shutdown()
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_o_logo_sai_em_contorno_na_letra_da_marca(tmp: Path):
    try:
        import fontTools  # noqa: F401
    except ImportError:
        return                              # o tronco sem fontTools: o kit traz (pyproject)
    d, largura, altura = ob.letra_svg(ob.RAIZ / "tools/video-use/assets/fontes/Jost-Variable.ttf", "Ab", 700)
    assert d.startswith("M") and "Z" in d and largura > 50 and altura > 90, (d[:40], largura, altura)


def test_o_modulo_traz_a_tela_dele(tmp: Path):
    """Um módulo instalado (o ZIP do bump) descreve a tela no onboarding.json da skill: a página monta o
    passo, a chave entra no .env.local e o teste dela é a leitura que ele declara, sem gastar."""
    raiz = (tmp / "fabrica").resolve()
    pasta = raiz / ".agents" / "skills" / "fabrica-posta"
    pasta.mkdir(parents=True)
    (pasta / "onboarding.json").write_text(json.dumps({
        "nome": "Zernio", "campos": [["ZERNIO_API_KEY", "Chave"]],
        "teste": {"url": "https://exemplo/contas", "cabecalho": {"Authorization": "Bearer {ZERNIO_API_KEY}"},
                  "lista": "accounts", "item": "{platform} @{username}"}}), encoding="utf-8")
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "ENV", "_pede")}
    pedidos = []
    ob.RAIZ, ob.ENV = raiz, raiz / ".env.local"
    ob._pede = lambda u, h, c=None: (pedidos.append((u, h)) or
                                     (200, {"accounts": [{"_id": "a1", "platform": "instagram", "username": "loja"},
                                                         {"_id": "a2", "platform": "tiktok"}]}))
    try:
        assert list(ob.modulos()) == ["fabrica-posta"] and ob.chaves()["fabrica-posta"] == ["ZERNIO_API_KEY"]
        r = ob.testa_chave("fabrica-posta", ob.campos_da_chave("fabrica-posta", {"ZERNIO_API_KEY": " k123 "}))
        assert pedidos == [("https://exemplo/contas", {"Authorization": "Bearer k123"})], pedidos
        assert r["ok"] and [o["nome"] for o in r["opcoes"]] == ["instagram @loja", "tiktok @"], r
        assert ob.conectadas()["fabrica-posta"] is False     # só a página grava, depois do teste
    finally:
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_a_ferramenta_paga_so_aparece_com_o_modulo_dela(tmp: Path):
    """A voz e o rosto vêm no Clone de IA, as cenas no Cenas de Cinema: sem a skill do módulo em
    .agents/skills/, a página não pede a chave e a API recusa."""
    raiz = (tmp / "fabrica").resolve()
    raiz.mkdir()
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "ENV")}
    ob.RAIZ, ob.ENV = raiz, raiz / ".env.local"
    try:
        assert ob.chaves() == {}, ob.chaves()
        (raiz / ".agents" / "skills" / "fabrica-clone").mkdir(parents=True)
        assert list(ob.chaves()) == ["elevenlabs", "heygen"]
        (raiz / ".agents" / "skills" / "fabrica-cinema").mkdir()
        assert list(ob.chaves()) == ["elevenlabs", "heygen", "higgsfield"], ob.chaves()
    finally:
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_a_heygen_entra_pelo_mcp_sem_chave(tmp: Path):
    """A HeyGen não tem chave: o agente fala com ela pelo MCP oficial, com o login do aluno, e gasta os
    créditos do plano. A página não aceita chave dela, pede ao agente a lista dos looks (o `looks` do
    gera pra mim), e escolher o look é o que conecta."""
    import contextlib
    import io
    raiz = (tmp / "fabrica").resolve()
    (raiz / ".agents" / "skills" / "fabrica-clone").mkdir(parents=True)
    (raiz / "onboarding" / "gerados").mkdir(parents=True)
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "PASTA", "ENV")}
    srv, url = _sobe(raiz)
    post = lambda c, corpo: urllib.request.urlopen(urllib.request.Request(url + c, data=json.dumps(corpo).encode(),
                                                   headers={"X-Fabrica": "tok"}), timeout=5).read()
    try:
        assert ob.chaves()["heygen"] == ["HEYGEN_LOOK"] and ob.conectadas()["heygen"] is False
        try:
            post("/api/chave", {"ferramenta": "heygen", "HEYGEN_LOOK": "abcd1234"})
            assert False, "a página aceitou chave da HeyGen"
        except urllib.error.HTTPError as e:
            assert e.code == 400
        try:
            ob.testa_chave("heygen", {})
            assert False, "a página ainda testa chave da HeyGen pela API"
        except KeyError:
            pass
        post("/api/gera", {"o": "looks"})
        with ob.TRAVA:
            t = ob.proxima()
        assert t["faz"] == "gerar" and t["o"] == "looks", t
        assert ob.limpa_opcoes("looks", [{"id": "c68d44b1d4bb", "nome": "Look 17", "tipo": "digital_twin"},
                                         {"id": "x y", "nome": "espaço no id"}, {"nome": "sem id"}]) \
            == [{"id": "c68d44b1d4bb", "nome": "Look 17", "tipo": "digital_twin"}]
        post("/api/id", {"chave": "HEYGEN_LOOK", "valor": "c68d44b1d4bb"})
        assert ob.conectadas()["heygen"] is True and ob.ESTADO["escolhas"]["ferramentas"]["heygen"] is True
        # o agente lê e grava o look sem abrir o .env.local (onboarding.py id)
        argv, out = sys.argv, io.StringIO()
        try:
            sys.argv = ["onboarding.py", "id", "HEYGEN_LOOK"]
            with contextlib.redirect_stdout(out):
                ob.main()
            assert out.getvalue().strip() == "c68d44b1d4bb", out.getvalue()
            sys.argv = ["onboarding.py", "id", "HEYGEN_LOOK", "outro_look_9"]
            with contextlib.redirect_stdout(io.StringIO()):
                ob.main()
            assert ob.le_env()["HEYGEN_LOOK"] == "outro_look_9"
            sys.argv = ["onboarding.py", "id", "ELEVENLABS_API_KEY"]
            try:
                ob.main()
                assert False, "o `id` leu uma chave"
            except SystemExit as e:
                assert "HEYGEN_LOOK" in str(e.code), e.code
        finally:
            sys.argv = argv
    finally:
        srv.shutdown()
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_a_ia_do_aluno_roda_sem_cabeca_e_sem_travar(tmp: Path):
    """O gera pra mim chama o `claude -p` ou o `codex exec` num subprocesso, pede só texto e confere o que volta:
    paleta que não lê bem cai, e o logo é desenhado pelo código, não pela IA."""
    raiz = (tmp / "fabrica").resolve()
    (raiz / "onboarding").mkdir(parents=True)
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "PASTA", "ENV")}
    srv, url = _sobe(raiz)
    chamadas = []
    resposta = {"opcoes": [
        {"nome": "Doce", "porque": "rosa e creme", "cores": {"pp": "#FFF4E6", "ink": "#3D1F2B", "ac": "#D9376E", "mk": "#FFC93C"}},
        {"nome": "Apagada", "porque": "não lê", "cores": {"pp": "#FFFFFF", "ink": "#EEEEEE", "ac": "#FFFFFF", "mk": "#FFFFFF"}}]}

    class R:                                # o resultado do subprocesso, falso
        returncode, stderr = 0, "aviso de hook\n"
        stdout = "claro, aqui vai:\n" + json.dumps(resposta)

    achado, rodou = ob.shutil.which, ob.subprocess.run
    ob.shutil.which = lambda n: f"/falso/{n}" if n == "claude" else None
    ob.subprocess.run = lambda cmd, **kw: (chamadas.append((cmd, kw)) or R())
    try:
        assert json.loads(_get(url + "/api/estado", **{"X-Fabrica": "tok"})[1])["ia"] == "claude"
        urllib.request.urlopen(urllib.request.Request(url + "/api/gera", data=json.dumps({"o": "paleta", "sobre": "bolo"}).encode(),
                               headers={"X-Fabrica": "tok"}), timeout=5).read()
        for _ in range(100):                # a thread responde sozinha; a página só olha o estado
            g = ob.ESTADO["gera"]["paleta"]
            if g["estado"] != "fazendo":
                break
            import time
            time.sleep(.05)
        assert g["estado"] == "pronto" and [o["nome"] for o in g["opcoes"]] == ["Doce"], g
        cmd, kw = chamadas[0]
        assert cmd[:2] == ["/falso/claude", "-p"] and "--tools" in cmd and cmd[cmd.index("--tools") + 1] == "", cmd
        assert "bolo" in kw["input"] and kw["cwd"] != str(raiz), "o pedido não foi pela entrada, ou rodou dentro da fábrica"
        # nada na fila do agente: ninguém precisa estar esperando
        with ob.TRAVA:
            assert ob.proxima() is None
        # o Codex: a resposta vem pelo arquivo do -o
        ob.shutil.which = lambda n: f"/falso/{n}" if n == "codex" else None
        def codex(cmd, **kw):
            Path(cmd[cmd.index("-o") + 1]).write_text(json.dumps(resposta), encoding="utf-8")
            R.stdout = ""
            return R()
        ob.subprocess.run = codex
        assert [o["nome"] for o in ob.opcoes_da_ia("paleta", {}, ob._roda_agente("x"))] == ["Doce"]
        # o logo: a IA só diz forma e texto; o SVG sai da letra, em contorno, sem nada executável
        try:
            import fontTools  # noqa: F401
            R.stdout = json.dumps({"opcoes": [{"nome": "a", "forma": "monograma", "texto": "DL"},
                                              {"nome": "b", "forma": "<script>", "texto": "x"},
                                              {"nome": "c", "forma": "nome", "texto": "Doce Lua"}]})
            ob.subprocess.run = lambda cmd, **kw: R()
            ob.shutil.which = lambda n: "/falso/claude"
            fontes = raiz / "tools/video-use/assets/fontes"
            fontes.mkdir(parents=True)
            (fontes / "Jost-Variable.ttf").write_bytes((AQUI.parents[0] / "assets/fontes/Jost-Variable.ttf").read_bytes())
            ops = ob.opcoes_da_ia("logo", {"cores": {"pp": "#FFF4E6", "ink": "#3D1F2B", "ac": "#D9376E", "mk": "#FFC93C"},
                                           "fontes": {"fd": {"arq": "Jost-Variable.ttf", "peso": "700"}}}, ob._roda_agente("x"))
            assert len(ops) == 2, ops
            svg = (raiz / ops[0]["arquivo"]).read_text(encoding="utf-8")
            assert svg.startswith("<svg") and "<path" in svg and "script" not in svg and "<text" not in svg, svg[:200]
        except ImportError:
            pass
        # falha do subprocesso vira mensagem na tela, não exceção
        R.returncode = 1
        ob.gera_com_ia("paleta", {})
        assert ob.ESTADO["gera"]["paleta"]["estado"] == "erro" and ob.ESTADO["gera"]["paleta"]["msg"]
    finally:
        ob.shutil.which, ob.subprocess.run = achado, rodou
        srv.shutdown()
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_o_onboarding_termina_sem_nenhum_video_e_grava_as_preferencias(tmp: Path):
    """O onboarding só define preferências (decisão de 21/10): ninguém manda vídeo, a fábrica não edita
    nada nele, e tudo fica em escolhas.json sem o agente. As prévias tocam num clipe de domínio público do kit."""
    raiz = (tmp / "fabrica").resolve()
    (raiz / "onboarding").mkdir(parents=True)
    salvos = {k: getattr(ob, k) for k in ("RAIZ", "PASTA", "ENV")}
    srv, url = _sobe(raiz)
    post = lambda c, corpo: urllib.request.urlopen(urllib.request.Request(url + c, data=json.dumps(corpo).encode(),
                                                   headers={"X-Fabrica": "tok"}), timeout=5).read()
    try:
        post("/api/escolhas", {"marca": {"nome": "Doce Lua"}, "legenda": "padrao", "pronto": True})
        gravado = json.loads((raiz / "onboarding" / "escolhas.json").read_text(encoding="utf-8"))
        assert gravado["marca"]["nome"] == "Doce Lua" and gravado["legenda"] == "padrao", gravado
        with ob.TRAVA:
            t = ob.proxima()
        assert t is None, "o agente ganhou tarefa: o onboarding não espera por ele"
        estado = json.loads(_get(url + "/api/estado", **{"X-Fabrica": "tok"})[1])
        assert "video" not in estado, "o estado ainda carrega o vídeo do aluno"
        try:
            post("/api/video?nome=a.mp4", {})
            assert False, "a página ainda recebe vídeo"
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code
        assert ob.base_das_previas() is None, "sem o exemplo no kit, não há base"
        exemplo = raiz / "tools" / "onboarding" / "previa"
        exemplo.mkdir(parents=True)
        (exemplo / "previa.mp4").write_bytes(b"0")
        (exemplo / "fala.json").write_text("{}", encoding="utf-8")
        assert ob.base_das_previas() == {"base": "tools/onboarding/previa/previa.mp4",
                                         "fala": "tools/onboarding/previa/fala.json"}
    finally:
        srv.shutdown()
        for k, v in salvos.items():
            setattr(ob, k, v)


def test_primeiro_video_recomenda_intensa_e_tanto_faz_grava_intensa(tmp: Path):
    import contextlib
    import io
    import movimento as mv
    assert next(iter(mv.DENSIDADES)) == "intensa", "intensa vem primeiro na pergunta"
    arq = tmp / "escolhas.json"
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        mv.main(["ler", "--arquivo", str(arq)])
    assert json.loads(saida.getvalue())["recomendada"] == "intensa", saida.getvalue()
    assert mv.main(["grava", "--padrao", "--arquivo", str(arq)]) == 0                    # "tanto faz"
    m = mv.le(arq)
    assert m["densidade"] == "intensa" and "layout" in m["efeitos"] and "palavra_atras" in m["efeitos"] and not mv.falta(m), m
    mv.grava(densidade="calma", arquivo=arq)
    mv.grava(padrao=True, arquivo=arq)               # o que ele já deu fica
    assert mv.le(arq)["densidade"] == "calma"


def test_o_movimento_fica_gravado_no_mesmo_arquivo_e_a_pagina_nao_apaga(tmp: Path):
    import movimento as mv
    arq = tmp / "escolhas.json"
    arq.write_text(json.dumps({"marca": {"cor": "#fff"}}), encoding="utf-8")
    assert mv.le(arq) == {} and mv.falta(mv.le(arq)) == ["densidade", "efeitos"]
    assert mv.main(["grava", "--densidade", "intensa", "--efeitos", "zoom,transicao", "--veta", "e_raio", "--arquivo", str(arq)]) == 0
    m = mv.le(arq)
    assert m == {"densidade": "intensa", "efeitos": ["zoom", "transicao"], "vetos": ["e_raio"]} and not mv.falta(m), m
    mv.grava(veta=["zoom"], perdoa=["e_raio"], arquivo=arq)               # a correção de gosto soma; o perdão tira
    assert mv.le(arq)["vetos"] == ["zoom"] and mv.le(arq)["densidade"] == "intensa"
    assert json.loads(arq.read_text(encoding="utf-8"))["marca"] == {"cor": "#fff"}   # as outras chaves ficam
    for ruim in ({"densidade": "frenética"}, {"efeitos": ["laser"]}):
        try:
            mv.grava(arquivo=arq, **ruim)
            raise AssertionError("aceitou valor fora da lista")
        except ValueError:
            pass
    # a página regrava o arquivo inteiro a partir da memória dela: o `movimento` que o agente gravou por fora tem que sobreviver
    antes = (ob.PASTA, ob.ESTADO.get("escolhas"))
    try:
        ob.PASTA = tmp
        (tmp / "escolhas.json").write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")
        ob.ESTADO["escolhas"] = {"marca": {"cor": "#000"}}
        ob.salva_escolhas()
        salvo = json.loads((tmp / "escolhas.json").read_text(encoding="utf-8"))
        assert salvo["marca"] == {"cor": "#000"} and salvo["movimento"]["densidade"] == "intensa", salvo
    finally:
        ob.PASTA, ob.ESTADO["escolhas"] = antes


def main() -> int:
    casos = [
        ("a chave troca a linha dela e mais nenhuma", test_a_chave_troca_a_linha_dela_e_mais_nenhuma),
        ("a chave da Higgsfield vem inteira e parte no dois-pontos", test_a_chave_da_higgsfield_vem_inteira_e_parte_no_dois_pontos),
        ("o sotaque é opcional e vira a marca do v4", test_o_sotaque_e_opcional_e_vira_a_marca_do_v4),
        ("a página lista do código e do guia", test_a_pagina_lista_do_codigo_e_do_guia),
        ("só a página aberta pelo agente lê e grava", test_so_a_pagina_aberta_pelo_agente_le_e_grava),
        ("a marca entra na peça antes dela medir", test_a_marca_entra_na_peca_antes_dela_medir),
        ("toda letra dos temas vem no kit", test_toda_letra_dos_temas_vem_no_kit),
        ("o gera pra mim confere o que chega", test_o_gera_pra_mim_confere_o_que_chega),
        ("o logo sai em contorno na letra da marca", test_o_logo_sai_em_contorno_na_letra_da_marca),
        ("o módulo traz a tela dele", test_o_modulo_traz_a_tela_dele),
        ("a ferramenta paga só aparece com o módulo dela", test_a_ferramenta_paga_so_aparece_com_o_modulo_dela),
        ("a IA do aluno roda sem cabeça e sem travar", test_a_ia_do_aluno_roda_sem_cabeca_e_sem_travar),
        ("a HeyGen entra pelo MCP, sem chave", test_a_heygen_entra_pelo_mcp_sem_chave),
        ("o onboarding termina sem nenhum vídeo e grava as preferências", test_o_onboarding_termina_sem_nenhum_video_e_grava_as_preferencias),
        ("primeiro vídeo: intensa recomendada", test_primeiro_video_recomenda_intensa_e_tanto_faz_grava_intensa),
        ("o movimento fica gravado no mesmo arquivo e a página não apaga", test_o_movimento_fica_gravado_no_mesmo_arquivo_e_a_pagina_nao_apaga),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        for nome, caso in casos:
            sub = Path(td) / nome.replace(" ", "_")
            sub.mkdir()
            try:
                caso(sub)
                print(f"  ok   {nome}")
            except Exception as e:
                falhas.append((nome, e))
                print(f"  FALHA {nome}: {e!r}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
