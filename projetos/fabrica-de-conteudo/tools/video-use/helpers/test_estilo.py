"""Auto-teste do estilo. Sem framework — assert direto, um comando.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_estilo.py

Nada aqui abre vídeo nem renderiza: o estilo é dado, e resolver dado é a coisa
mais barata de cobrar que este projeto tem.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import estilo as es


# ---- resolver por nome ------------------------------------------------------


def test_os_quatro_estilos_existem():
    """Extraídos do que já era feito, não inventados."""
    for nome in ("aula-ccnp", "reel-mono", "reel-camera", "quadro"):
        assert nome in es.ESTILOS, f"faltou o estilo {nome}"


def test_resolve_os_oito_eixos():
    e = es.estilo("aula-ccnp")
    for eixo in es.EIXOS:
        assert eixo in e.eixos, f"o estilo resolveu sem o eixo {eixo}"


def test_nome_que_nao_existe_lista_os_validos():
    erro = None
    try:
        es.estilo("aula-que-nao-existe")
    except Exception as ex:
        erro = ex
    assert erro is not None, "estilo inexistente passou calado"
    assert "aula-ccnp" in str(erro), f"o erro não lista os válidos: {erro}"


def test_estilo_declara_de_que_bruto_parte():
    assert es.estilo("aula-ccnp").bruto == "live"
    assert es.estilo("reel-camera").bruto == "camera"


def test_orientacao_e_campo_do_estilo():
    """O eixo do projeto: formato é valor, não nome de módulo."""
    assert es.estilo("aula-ccnp").orientacao == "16:9"
    assert es.estilo("reel-mono").orientacao == "9:16"


def test_quadro_serve_os_dois_formatos():
    """O que derrubou as duas fábricas: um estilo que atende as duas orientações."""
    assert es.estilo("quadro").orientacao == "16:9"
    vertical = es.estilo("quadro", imagem={"orientacao": "9:16"})
    assert vertical.orientacao == "9:16" and vertical.vertical
    # e o resto do estilo — corte, trilha, desenho — segue sendo o mesmo
    assert vertical.eixos["corte"] == es.estilo("quadro").eixos["corte"]


# ---- herança ----------------------------------------------------------------


def test_herda_o_que_nao_sobrescreveu():
    filho = es.estilo("reel-mono-claro")
    pai = es.estilo("reel-mono")
    assert filho.eixos["corte"] == pai.eixos["corte"], "não herdou o corte do pai"
    assert filho.eixos["desenho"]["tema"] != pai.eixos["desenho"]["tema"], \
        "herdou até o que devia sobrescrever"


def test_herdar_de_pai_que_nao_existe_estoura_na_leitura():
    erro = None
    try:
        es.resolver({"herda": "fantasma"}, nome="orfao")
    except Exception as ex:
        erro = ex
    assert erro is not None, "estilo órfão passou calado"
    assert "fantasma" in str(erro)


def test_ciclo_de_heranca_nomeia_os_envolvidos():
    catalogo = {"a": {"herda": "b"}, "b": {"herda": "a"}}
    erro = None
    try:
        es.resolver(catalogo["a"], nome="a", catalogo=catalogo)
    except Exception as ex:
        erro = ex
    assert erro is not None, "o ciclo não estourou"
    assert "a" in str(erro) and "b" in str(erro), f"o erro não nomeia o ciclo: {erro}"


# ---- sobrescritas -----------------------------------------------------------


def test_sobrescrita_ganha_do_estilo():
    e = es.estilo("aula-ccnp", imagem={"altura": 1080})
    assert e.eixos["imagem"]["altura"] == 1080


def test_sobrescrita_num_eixo_nao_vaza_para_os_outros():
    base = es.estilo("aula-ccnp")
    e = es.estilo("aula-ccnp", imagem={"altura": 1080})
    for eixo in es.EIXOS:
        if eixo != "imagem":
            assert e.eixos[eixo] == base.eixos[eixo], f"a sobrescrita vazou para {eixo}"


def test_sobrescrita_parcial_mantem_o_resto_do_eixo():
    base = es.estilo("aula-ccnp")
    e = es.estilo("aula-ccnp", imagem={"altura": 1080})
    assert e.eixos["imagem"]["fps"] == base.eixos["imagem"]["fps"], \
        "mexer na altura zerou o resto do eixo de imagem"


def test_sobrescrita_nao_mexe_no_estilo_nomeado():
    es.estilo("aula-ccnp", imagem={"altura": 1080})
    assert es.estilo("aula-ccnp").eixos["imagem"]["altura"] != 1080, \
        "a sobrescrita contaminou o estilo guardado"


def test_eixo_que_nao_existe_estoura():
    erro = None
    try:
        es.estilo("aula-ccnp", velocidade={"x": 2})
    except Exception as ex:
        erro = ex
    assert erro is not None, "eixo inexistente passou calado"
    assert "velocidade" in str(erro)


def test_botao_que_nao_existe_dentro_do_eixo_estoura():
    erro = None
    try:
        es.estilo("aula-ccnp", imagem={"profundidade": 10})
    except Exception as ex:
        erro = ex
    assert erro is not None, "botão inexistente passou calado"
    assert "profundidade" in str(erro), f"o erro não nomeia o botão: {erro}"


# ---- recursos ---------------------------------------------------------------


def test_recursos_tem_posicao_declarada():
    """Ligar um recurso o põe no lugar dele, não no fim da fila."""
    e = es.estilo("aula-ccnp")
    pos = [es.RECURSOS[r]["posicao"] for r in e.recursos]
    assert pos == sorted(pos), f"os recursos saíram fora de ordem: {e.recursos}"


def test_desligar_recurso():
    e = es.estilo("aula-ccnp", recursos={"-": ["abertura"]})
    assert "abertura" not in e.recursos
    assert "explicador" in e.recursos, "desligar um recurso derrubou os outros"


def test_ligar_recurso_entra_na_posicao():
    e = es.estilo("reel-mono", recursos={"+": ["abertura"]})
    pos = [es.RECURSOS[r]["posicao"] for r in e.recursos]
    assert pos == sorted(pos), "o recurso ligado foi para o fim em vez da posição dele"


def test_recurso_que_nao_existe_estoura():
    erro = None
    try:
        es.estilo("aula-ccnp", recursos={"+": ["fumaca"]})
    except Exception as ex:
        erro = ex
    assert erro is not None, "recurso inexistente passou calado"
    assert "fumaca" in str(erro)


def test_desligar_recurso_que_ja_estava_desligado_nao_estoura():
    e = es.estilo("reel-mono", recursos={"-": ["abertura"]})
    assert "abertura" not in e.recursos


# ---- o corte vem do estilo --------------------------------------------------


def test_o_estilo_entrega_a_afinacao_de_corte():
    """O elo com a costura A: o estilo diz qual afinação, e ela sai pronta."""
    import clean_edl
    assert es.estilo("aula-ccnp").afinacao() == clean_edl.AULA
    assert es.estilo("reel-mono").afinacao() == clean_edl.TIGHT


def test_ajuste_de_corte_no_estilo_chega_na_afinacao():
    e = es.estilo("aula-ccnp", corte={"ajuste": {"pause_keep": 0.4}})
    assert e.afinacao().pause_keep == 0.4
    assert es.estilo("aula-ccnp").afinacao().pause_keep != 0.4, \
        "o ajuste contaminou o estilo guardado"


# ---- catálogo ---------------------------------------------------------------


def test_catalogo_lista_todos_com_formato_e_bruto():
    linhas = es.catalogo()
    assert len(linhas) == len(es.ESTILOS)
    for l in linhas:
        assert l["orientacao"] and l["bruto"], f"linha incompleta: {l}"


def test_catalogo_e_ordenado():
    nomes = [l["nome"] for l in es.catalogo()]
    assert nomes == sorted(nomes), "o catálogo saiu fora de ordem"


def test_legenda_do_estilo_e_um_preset():
    """Nome de preset errado no estilo só estouraria no render da legenda."""
    from captions_viral import PRESETS
    for nome in es.ESTILOS:
        leg = es.estilo(nome).eixos["desenho"]["legenda"]
        assert leg is None or leg in PRESETS, f"{nome}: legenda '{leg}' não é preset"


def test_todo_estilo_do_catalogo_resolve():
    """Nenhum estilo guardado pode estar quebrado — o catálogo é a prova."""
    for nome in es.ESTILOS:
        e = es.estilo(nome)
        assert e.nome == nome
        assert e.recursos == sorted(e.recursos, key=lambda r: es.RECURSOS[r]["posicao"])


def test_reel_avatar_herda_da_vsl_e_liga_o_broll():
    """Formato novo é estilo herdando: o reel de avatar é a VSL com b-roll, voz
    sintética e a pasta dos reels — o resto vem do pai."""
    e, vsl = es.estilo("reel-avatar"), es.estilo("vsl")
    assert e.bruto == "avatar" and e.vertical
    assert e.recursos == ["legenda", "broll", "trilha"], e.recursos
    assert e.eixos["voz"]["tratamento"] == "cru"
    assert e.eixos["corte"] == vsl.eixos["corte"] and e.adaptadores == vsl.adaptadores


def test_reel_editorial_guarda_as_regras_do_dono():
    """O molde do Nick virou estilo herdando do reel de avatar, com o que o dono decidiu
    em 30/09 como padrão: o que se repetia em três monta.py mora aqui uma vez."""
    e = es.estilo("reel-editorial")
    assert e.bruto == "avatar" and e.vertical and e.eixos["imagem"]["composicao"] == "editorial"
    assert e.eixos["imagem"]["fundo"] is None, (
        "o fundo é a placa do look de quem grava: vem do plano, e o confere cobra quando falta")
    assert e.eixos["imagem"]["costura"] == [768, 120], "tela dividida 40/60 com degradê"
    assert e.eixos["desenho"]["legenda_ig"] == 1450
    s = e.eixos["voz"]["sintese"]
    assert (s["modelo"], s["stability"], s["similarity_boost"]) == ("eleven_v4", 0.25, 0.85), s
    assert s["sotaque"] == "", "o sotaque é de quem grava (VOZ_SOTAQUE), nunca do estilo: aluno de SP não sai carioca"
    import reel_editorial as re_
    assert re_.sotaque_de(s, {}) == "", "sem config não vai marca"
    marca = "[in a Brazilian Portuguese accent from São Paulo]"
    assert re_.sotaque_de(s, {"VOZ_SOTAQUE": marca}) == marca, "com config vai a do aluno"
    assert re_.sotaque_de({"sotaque": "[x]"}, {"VOZ_SOTAQUE": marca}) == "[x]", "o plano manda sobre a marca"
    t = e.eixos["trilha"]
    assert (t["cama"], t["duck"], t["fade_fim"]) == (-21.0, 3.0, 0.6), t
    assert es.estilo("reel-avatar").eixos["trilha"]["duck"] is None, "o botão novo vazou pro pai"


def test_criativo_herda_da_vsl_e_parte_do_banco():
    """O criativo dos ninjas virou estilo: da VSL vem a legenda viral no ritmo dela e a cama;
    o bruto é o banco de cenas, e o que é dele mora aqui, não num monta_criativo.py."""
    e, vsl = es.estilo("criativo"), es.estilo("vsl")
    assert e.bruto == "banco" and e.vertical and e.eixos["imagem"]["composicao"] == "cenas"
    assert e.recursos == ["legenda", "trilha"] and e.adaptadores == vsl.adaptadores, (e.recursos, e.adaptadores)
    assert e.eixos["desenho"]["ritmo"] == [0.167, 0.033]
    assert (e.eixos["desenho"]["destaque"], e.eixos["desenho"]["legenda_layout"]) == ("mk", "faixa_criativo")
    s = e.eixos["voz"]["sintese"]
    assert (e.eixos["voz"]["tratamento"], s["modelo"], s["tentativas"]) == ("cru", "eleven_multilingual_v2", 3), s
    t = e.eixos["trilha"]
    assert (t["cama"], t["duck"], t["fade_fim"]) == (-20.0, 1.5, 0.3), t
    assert e.eixos["entrega"]["pasta"] == "videos/criativos"
    assert vsl.eixos["desenho"]["destaque"] == "ac", "o amarelo do criativo vazou pra VSL"
    r = es.estilo("criativo-reel")
    assert (r.eixos["desenho"]["legenda_layout"], r.eixos["trilha"]["fade_fim"]) == ("faixa", 1.2)
    assert r.eixos["trilha"]["cama"] == -20.0 and r.bruto == "banco", "o resto vem do criativo"


def test_marca_do_aluno_entra_no_catalogo():
    """A pasta marca/ do aluno acrescenta estilo sem editar código: herda de um do kit, ganha o
    tema e a letra dela, e o erro dela sai com o arquivo no começo, antes de qualquer render."""
    import json, tempfile
    with tempfile.TemporaryDirectory() as d:
        pasta = Path(d)
        assert es.da_marca(pasta) == {}, "sem estilos.json a marca não acrescenta nada"
        arq = pasta / "estilos.json"
        arq.write_text(json.dumps({"_leia": "nota", "acme-reel": {
            "_nota": "nota também", "herda": "reel-editorial",
            "desenho": {"tema": "marca", "fonte": "marca/fontes/Acme.ttf#Black"},
            "imagem": {"fundo": "marca/placa.png"}}}), encoding="utf-8")
        novos = es.da_marca(pasta)
        assert list(novos) == ["acme-reel"], novos
        e = es.resolver(novos["acme-reel"], "acme-reel", {**es.ESTILOS, **novos})
        assert e.eixos["desenho"]["tema"] == "marca" and e.eixos["imagem"]["fundo"] == "marca/placa.png"
        assert e.eixos["voz"]["sintese"]["modelo"] == "eleven_v4", "o resto vem do reel-editorial"
        velho = dict(es.ESTILOS)
        try:
            es.ESTILOS.update(novos)        # o que a importação faz com a marca da raiz
            assert list(es.da_marca(pasta)) == ["acme-reel"], "ler a mesma marca de novo acusou ela mesma"
        finally:
            es.ESTILOS.clear()
            es.ESTILOS.update(velho)
        for ruim, diz in (({"reel-editorial": {"herda": "vsl"}}, "já existe no kit"),
                          ({"acme": {"herda": "nao-existe"}}, "nao-existe"),
                          ({"acme": {"herda": "vsl", "desenho": {"cor": "x"}}}, "cor")):
            arq.write_text(json.dumps(ruim), encoding="utf-8")
            try:
                es.da_marca(pasta)
            except ValueError as err:
                assert str(err).startswith(str(arq)) and diz in str(err), err
            else:
                raise AssertionError(f"{ruim} passou")
        arq.write_text("{", encoding="utf-8")
        try:
            es.da_marca(pasta)
        except ValueError as err:
            assert "JSON quebrado" in str(err), err
        else:
            raise AssertionError("JSON quebrado passou")


def test_aula_fabrica_herda_o_corte_e_troca_o_que_e_do_ccnp():
    """A aula que ele grava na cara da Fábrica: o modo 2 com o corte do CCnP, sem o CRT e o
    glitch, a tela na chapa, e a marca abrindo e fechando por peça. A variante live é a mesma
    aula com a câmera dentro do OBS: muda o bruto e a bolinha, o resto vem dela."""
    e, ccnp = es.estilo("aula-fabrica"), es.estilo("aula-ccnp")
    assert (e.bruto, e.orientacao) == ("obs+celular", "16:9") and e.eixos["corte"] == ccnp.eixos["corte"]
    assert e.recursos == ["chapa", "explicador", "abertura"], "o glitch é do CCnP"
    img, ef = e.eixos["imagem"], e.eixos["efeito"]
    assert img["canvas"] is None and img["recorte"] is None, "o modo 2 põe o celular inteiro no cartão"
    assert ef["abertura"]["peca"] == ef["fecho"]["peca"] == "t_marca" and ef["fecho"]["q"]["sai"] == 0
    assert e.eixos["desenho"]["tema"] == "claro", "o tema claro é a paleta e a letra da página"
    assert (ccnp.eixos["efeito"]["abertura"], ccnp.eixos["efeito"]["fecho"]) == ("crt", None), "vazou pro pai"
    assert es.estilo("aula-fabrica", efeito={"fecho": None}).eixos["efeito"]["abertura"]["peca"] == "t_marca"
    live = es.estilo("aula-fabrica-live")
    assert live.bruto == "live" and live.eixos["imagem"]["recorte"].startswith("crop=")
    assert live.recursos == e.recursos and live.eixos["efeito"] == ef


# ---- pedidos de personalização ----------------------------------------------


def _marca_de_teste(raiz: Path) -> Path:
    """Uma marca de aluno: cores no tema.css, uma música, e um estilo que a usa."""
    import json
    marca = raiz / "marca"
    marca.mkdir()
    (marca / "tema.css").write_text("html.marca{--pp:#FFF8E7; --ink:#1A1A1A; --ac:#0A7E5A; --mk:#F4B400;}",
                                    encoding="utf-8")
    (marca / "musica.mp3").write_bytes(b"x")
    (marca / "estilos.json").write_text(json.dumps({
        "acme-celular": {"herda": "reel-camera", "desenho": {"tema": "marca"}},
        "acme-musica": {"herda": "reel-camera", "trilha": {"faixa": "marca/musica.mp3"}}}), encoding="utf-8")
    return marca


def _confere_pedidos(nome: str, ps: list[dict]):
    """Três pedidos, todos distintos, em português curto; o plano de cada um passa na validação
    do próprio estilo.py e muda o estilo de fato."""
    import copy, json
    assert len(ps) == 3, (nome, ps)
    assert len({json.dumps(p["plano"], sort_keys=True) for p in ps}) == 3, (nome, "pedido repetido")
    base = es.estilo(nome)
    for p in ps:
        assert 0 < len(p["pedido"]) <= 120 and p["pedido"].startswith("Quero"), (nome, p["pedido"])
        assert "cereja" not in json.dumps(p["plano"]), "a LUT do pack não vai em pedido de aluno"
        assert es.estilo(nome, **copy.deepcopy(p["plano"])) != base, (nome, p["plano"], "não muda nada")


def test_reel_camera_tem_tres_pedidos_que_valem():
    ps = es.pedidos("reel-camera")
    _confere_pedidos("reel-camera", ps)
    eixos = {eixo for p in ps for eixo in p["plano"]}
    assert "desenho" in eixos, "a legenda é o que o aluno vê primeiro"


def test_reel_camera_sai_pronto_sem_personalizar_nada():
    """O primeiro vídeo do aluno: corte sem a gaguejada e uma graduação leve, sem LUT licenciada.
    O que herda do reel-camera e já tinha outro corte ou cor segue com o que tinha."""
    import grade
    e = es.estilo("reel-camera")
    assert e.eixos["corte"]["afinacao"] == "silencio-gagueira" and e.afinacao().disfluencia
    preset = e.eixos["graduacao"]["preset"]
    assert preset == "neutral_punch" and preset in grade.PRESETS, preset
    assert not preset.startswith(("cereja", "camera_escura")), "LUT licenciada ou que o kit não leva"
    for nome in ("lorcana-curto", "lorcana-longo"):
        d = es.estilo(nome)
        assert d.eixos["corte"]["afinacao"] == "silencio" and not d.afinacao().disfluencia, \
            (nome, "o corte do Tinteiro mudou")
        assert d.eixos["graduacao"]["preset"] == "none", (nome, "a cor do Tinteiro mudou")
    assert es.estilo("video-longo").afinacao().usa_texto, "o longo corta lendo o texto"
    assert es.estilo("aula-fabrica-camera").eixos["graduacao"]["preset"] == "camera_escura"


def test_padrao_da_marca_so_vale_se_o_estilo_existe():
    """`_padrao` é o estilo que o onboarding grava; nome que o catálogo não conhece não pode virar
    erro no meio do render. E `da_marca` segue devolvendo só estilos, sem a chave de nota."""
    import json, tempfile
    with tempfile.TemporaryDirectory() as d:
        pasta = Path(d)
        assert es.padrao_da_marca(pasta) is None, "sem estilos.json não há padrão"
        arq = pasta / "estilos.json"
        arq.write_text(json.dumps({"_padrao": "acme-celular", "acme-celular": {"herda": "reel-camera"}}),
                       encoding="utf-8")
        assert es.padrao_da_marca(pasta) is None, "estilo que ninguém carregou ainda não é padrão"
        assert list(es.da_marca(pasta)) == ["acme-celular"], "a nota virou estilo"
        velho = dict(es.ESTILOS)
        try:
            es.ESTILOS.update(es.da_marca(pasta))
            assert es.padrao_da_marca(pasta) == "acme-celular"
            arq.write_text(json.dumps({"_padrao": "nao-existe"}), encoding="utf-8")
            assert es.padrao_da_marca(pasta) is None
            arq.write_text(json.dumps({"_padrao": 7}), encoding="utf-8")
            assert es.padrao_da_marca(pasta) is None
            arq.write_text("{quebrado", encoding="utf-8")
            assert es.padrao_da_marca(pasta) is None, "JSON quebrado quem acusa é o da_marca, na importação"
        finally:
            es.ESTILOS.clear()
            es.ESTILOS.update(velho)


def test_todo_estilo_tem_tres_pedidos_que_valem():
    for nome in sorted(es.ESTILOS):
        _confere_pedidos(nome, es.pedidos(nome))


def test_pedido_usa_a_cor_e_a_musica_da_marca():
    import tempfile
    antes = dict(es.ESTILOS)
    with tempfile.TemporaryDirectory() as d:
        marca = _marca_de_teste(Path(d))
        ps = es.pedidos("reel-camera", marca)
        _confere_pedidos("reel-camera", ps)
        cor = next(p for p in ps if "#F4B400" in p["pedido"])
        assert cor["plano"] == {"desenho": {"tema": "marca", "destaque": "mk"}}, cor
        musica = next(p for p in ps if "trilha" in p["plano"])
        assert musica["plano"] == {"recursos": {"+": ["trilha"]}, "trilha": {"faixa": "marca/musica.mp3"}}, musica
        assert not any(p["plano"].get("desenho", {}).get("legenda") for p in ps), \
            "o preset traz paleta própria e apagaria a cor da marca"
        # o estilo da própria marca: já está no tema dela, então o pedido é a outra cor
        es.ESTILOS.update(es.da_marca(marca))   # o que a importação faz com a marca da raiz
        try:
            ps = es.pedidos("acme-celular", marca)
            _confere_pedidos("acme-celular", ps)
            assert ps[0]["plano"] == {"desenho": {"destaque": "mk"}} and "#F4B400" in ps[0]["pedido"], ps[0]
        finally:
            es.ESTILOS.clear()
            es.ESTILOS.update(antes)
        (marca / "musica.mp3").unlink()
        assert not any("trilha" in p["plano"] for p in es.pedidos("reel-camera", marca)), "música que não existe"
    assert es.ESTILOS == antes, "o estilo da marca vazou pro catálogo"


def test_pedidos_na_linha_de_comando():
    import contextlib, io, json
    saida = io.StringIO()
    velho = sys.argv
    sys.argv = ["estilo.py", "pedidos", "reel-camera"]
    try:
        with contextlib.redirect_stdout(saida):
            es.main()
    finally:
        sys.argv = velho
    linhas = saida.getvalue().splitlines()
    assert [l[:3] for l in linhas if l[:1].isdigit()] == ["1. ", "2. ", "3. "], linhas
    planos = [json.loads(l) for l in linhas if l.strip().startswith("{")]
    assert planos == [p["plano"] for p in es.pedidos("reel-camera")], planos
    try:
        es.pedidos("nao-existe")
    except KeyError as err:
        assert "reel-camera" in str(err), "o erro lista os estilos que existem"
    else:
        raise AssertionError("estilo que não existe passou")


# ---- corrida ----------------------------------------------------------------


def test_zonas_seguras_num_lugar_so():
    """`ZONAS` (28/10) é a tabela dos números da zona segura: orgânico até y 1500, anúncio até 1250, o mesmo lado e a mesma coluna de botões. O estilo do
    anúncio a lê, e a legenda do Short (captions_viral) assenta dentro da zona orgânica."""
    assert set(es.ZONAS) == {"organico", "anuncio", "longo"}
    for destino, z in es.ZONAS.items():
        W, H = z["quadro"]
        x0, y0, x1, y1 = z["zona"]
        assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H, (destino, z)
    assert es.zona("organico")["zona"][3] == 1500 and es.zona("anuncio")["zona"][3] == 1250 and es.zona("organico")["botoes"] == [960, 1000]
    d = es.estilo("anuncio-editorial").eixos["desenho"]
    assert d["zona"] == es.ZONAS["anuncio"]["zona"] and d["botoes"] == es.ZONAS["anuncio"]["botoes"] and d["legenda_ig"] == 1250
    import captions_viral as cv
    pe = cv.LAYOUTS["faixa"]["zona"][1] * es.ZONAS["organico"]["quadro"][1]
    assert pe <= es.ZONAS["organico"]["zona"][3], f"a legenda do Short ('faixa') assenta até y {pe:.0f}, e a zona orgânica acaba em {es.ZONAS['organico']['zona'][3]}"


def test_lorcana_longo_traz_o_som_aprovado_e_o_aluno_nao():
    """O som do longo do Tinteiro é do estilo (27 e 28/10): voz por bloco, nivelador de -22 dBFS e a cama a 24 dB da voz, que o episódio não repete.
    Os números iguais aos de `som_tinteiro.py` são conferidos no `test_serie_tinteiro` (o kit não leva esse módulo). O `video-longo` do aluno não herda."""
    e = es.estilo("lorcana-longo").eixos
    assert e["voz"]["por_bloco"] is True and e["voz"]["nivela_fala"] == {"alvo": -22.0}, e["voz"]
    assert (e["trilha"]["cama"], e["trilha"]["duck"], e["trilha"]["duck_limiar"], e["trilha"]["duck_solta"]) == (-43, 20, 0.006, 150), e["trilha"]
    assert es.estilo("lorcana-curto").eixos["voz"]["nivela_fala"] is None and es.estilo("lorcana-curto").eixos["trilha"]["cama"] == -27.0, "o Short não muda"
    v = es.estilo("video-longo").eixos
    assert v["voz"]["nivela_fala"] is None and (v["trilha"]["cama"], v["trilha"]["duck_solta"]) == (-27.0, 250), "o aluno segue com o som de antes"
    assert es.estilo("lorcana-longo", voz={"por_bloco": False}).eixos["voz"]["por_bloco"] is False, "o plano pode sobrescrever: quem cobra o motivo é a nota"


def main() -> int:
    casos = [
        ("os quatro estilos existem",        test_os_quatro_estilos_existem),
        ("resolve os oito eixos",            test_resolve_os_oito_eixos),
        ("nome errado lista os válidos",     test_nome_que_nao_existe_lista_os_validos),
        ("estilo declara o bruto",           test_estilo_declara_de_que_bruto_parte),
        ("orientação é campo do estilo",     test_orientacao_e_campo_do_estilo),
        ("quadro serve os dois formatos",    test_quadro_serve_os_dois_formatos),
        ("herda o que não sobrescreveu",     test_herda_o_que_nao_sobrescreveu),
        ("pai que não existe estoura",       test_herdar_de_pai_que_nao_existe_estoura_na_leitura),
        ("ciclo nomeia os envolvidos",       test_ciclo_de_heranca_nomeia_os_envolvidos),
        ("sobrescrita ganha do estilo",      test_sobrescrita_ganha_do_estilo),
        ("sobrescrita não vaza",             test_sobrescrita_num_eixo_nao_vaza_para_os_outros),
        ("sobrescrita parcial",              test_sobrescrita_parcial_mantem_o_resto_do_eixo),
        ("sobrescrita não contamina",        test_sobrescrita_nao_mexe_no_estilo_nomeado),
        ("eixo que não existe estoura",      test_eixo_que_nao_existe_estoura),
        ("botão que não existe estoura",     test_botao_que_nao_existe_dentro_do_eixo_estoura),
        ("recursos têm posição",             test_recursos_tem_posicao_declarada),
        ("desligar recurso",                 test_desligar_recurso),
        ("ligar recurso entra na posição",   test_ligar_recurso_entra_na_posicao),
        ("recurso que não existe estoura",   test_recurso_que_nao_existe_estoura),
        ("desligar o que já estava off",     test_desligar_recurso_que_ja_estava_desligado_nao_estoura),
        ("estilo entrega a afinação",        test_o_estilo_entrega_a_afinacao_de_corte),
        ("ajuste de corte chega",            test_ajuste_de_corte_no_estilo_chega_na_afinacao),
        ("catálogo lista tudo",              test_catalogo_lista_todos_com_formato_e_bruto),
        ("catálogo é ordenado",              test_catalogo_e_ordenado),
        ("todo estilo resolve",              test_todo_estilo_do_catalogo_resolve),
        ("legenda do estilo é preset",       test_legenda_do_estilo_e_um_preset),
        ("reel-avatar herda da vsl",         test_reel_avatar_herda_da_vsl_e_liga_o_broll),
        ("reel-editorial: regras do dono",   test_reel_editorial_guarda_as_regras_do_dono),
        ("criativo herda da vsl",            test_criativo_herda_da_vsl_e_parte_do_banco),
        ("a marca do aluno entra",           test_marca_do_aluno_entra_no_catalogo),
        ("aula-fabrica herda do ccnp",       test_aula_fabrica_herda_o_corte_e_troca_o_que_e_do_ccnp),
        ("reel-camera: 3 pedidos",           test_reel_camera_tem_tres_pedidos_que_valem),
        ("reel-camera sai pronto",           test_reel_camera_sai_pronto_sem_personalizar_nada),
        ("_padrao da marca",                 test_padrao_da_marca_so_vale_se_o_estilo_existe),
        ("todo estilo: 3 pedidos",           test_todo_estilo_tem_tres_pedidos_que_valem),
        ("pedido usa a marca",               test_pedido_usa_a_cor_e_a_musica_da_marca),
        ("pedidos na linha de comando",      test_pedidos_na_linha_de_comando),
        ("zonas seguras num lugar só",       test_zonas_seguras_num_lugar_so),
        ("lorcana-longo: som aprovado",      test_lorcana_longo_traz_o_som_aprovado_e_o_aluno_nao),
    ]
    falhas = []
    for nome, caso in casos:
        try:
            caso()
            print(f"  ok   {nome}")
        except Exception as e:
            falhas.append((nome, e))
            print(f"  FALHA {nome}: {e}")

    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    if falhas:
        print("falhou: " + ", ".join(n for n, _ in falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
