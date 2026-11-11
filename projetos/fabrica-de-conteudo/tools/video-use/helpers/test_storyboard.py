"""O storyboard do vídeo do celular: a lista numerada do que o render final vai desenhar, e a correção pelo número.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_storyboard.py

Sem rede e sem transcrição: o vídeo é sintético, e as decisões (o `cards.json` que o `cards_da_fala` escreveria)
são escritas à mão no formato dele.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import fabrica as fb
import ff
import storyboard as sb
from PIL import Image, ImageChops


def _video(tmp: Path, dur: int = 8) -> Path:
    saida = tmp / "celular.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=360x640:rate=25:duration={dur}",
            "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", saida], quiet=True)
    return saida


def _cards() -> list[dict]:
    falas = ["oi esse", "é o meu primeiro", "vídeo", "eu gravei no celular"]
    out, t = [], 0.5
    for f in falas:
        ws = f.split()
        out.append({"t0": round(t, 2), "t1": round(t + 0.5 * len(ws), 2), "fonte": "creato",
                    "words": [{"tx": w.upper(), "t0": round(t + 0.5 * i, 2), "t1": round(t + 0.5 * (i + 1), 2)}
                              for i, w in enumerate(ws)]})
        t += 0.5 * len(ws) + 0.1
    return out


def _montado(tmp: Path) -> tuple[dict, Path, Path]:
    """Um plano mínimo, o rascunho com legenda (aqui o próprio vídeo) e a pasta onde a fábrica decidiu."""
    video = _video(tmp)
    plano = {"fonte": str(video), "estilo": "reel-camera", "slug": "celular", "_dir": str(tmp)}
    cadeia = tmp / "rascunho"
    cadeia.mkdir()
    (cadeia / "cards.json").write_text(json.dumps({"cards": _cards()}), encoding="utf-8")
    return plano, video, cadeia


TRECHOS = [{"source": "celular", "start": 0.0, "end": 8.0}]


def test_plano_minimo_gera_linhas_com_numero_tempo_e_peca(tmp: Path):
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    pasta = sb.pasta(plano)
    bruto = (pasta / "storyboard.md").read_text(encoding="utf-8").splitlines()
    assert any("chamada-final" in l for l in bruto), "o vídeo de 8 s sem chamada leva o aviso"
    md = [l for l in bruto if l.startswith("|")]
    assert len(md) == 2 + 4, md
    assert md[2].startswith("| 1 | 0:00.5–0:01.5 | vídeo | legenda | OI ESSE |"), md[2]
    assert "EU GRAVEI NO CELULAR" in md[5]
    assert sorted(p.name for p in (pasta / "q").iterdir()) == ["001.jpg", "002.jpg", "003.jpg", "004.jpg"]
    assert not (pasta / "storyboard.html").exists(), "a página é uma só: o revisao.html"
    html = (pasta / "revisao.html").read_text(encoding="utf-8")
    assert "4 itens" in html and "q/004.jpg" in html
    # a legenda corre por baixo de tudo: os cards vizinhos não são "peça sobre peça"
    assert "junto com" not in "".join(md)


def test_tirar_e_trocar_texto_chegam_no_que_o_render_desenha(tmp: Path):
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    arq = sb.pasta(plano) / "decisoes.json"
    sb.tira(arq, 2)
    sb.troca_texto(arq, 4, "eu gravei no meu iPhone")
    # o render final lê as decisões no lugar de decidir de novo
    seco = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "cards da fala" not in nomes, nomes
    legenda = next(p for p in seco.passos if p.nome == "legenda")
    assert str(arq) in legenda.cmd, legenda.cmd
    cards = json.loads(arq.read_text(encoding="utf-8"))["cards"]
    assert [c["n"] for c in cards] == [1, 3, 4], "o número não muda quando um sai"
    assert " ".join(w["tx"] for w in cards[-1]["words"]) == "EU GRAVEI NO MEU IPHONE"
    a, b = cards[-1]["words"][0]["t0"], cards[-1]["words"][-1]["t1"]
    assert (a, b) == (4.3, 6.3), "as palavras novas ficam dentro do tempo do card"
    # e o storyboard seguinte mostra o corrigido, com os números de antes
    sb.do_celular(plano, cadeia, video, TRECHOS)
    md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
    assert "| 2 |" not in md and "IPHONE" in md and "| 4 |" in md


def test_numero_que_nao_existe_diz_quais_existem(tmp: Path):
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    try:
        sb.tira(sb.pasta(plano) / "decisoes.json", 9)
    except KeyError as e:
        assert "1, 2, 3, 4" in str(e), e
    else:
        raise AssertionError("tirar o nº 9 devia recusar")


def test_corte_que_mudou_recusa_o_render_e_o_storyboard_recomeca(tmp: Path):
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    outro = json.dumps({"ranges": [{"source": "celular", "start": 1.0, "end": 8.0}]})
    try:
        sb.decisoes(plano, outro)
    except ValueError as e:
        assert "outro corte" in str(e) and "--storyboard" in str(e), e
    else:
        raise AssertionError("o render final não pode usar decisão de outro corte")
    assert sb.decisoes(plano, outro, refaz=True) is None
    assert sb.decisoes(plano, json.dumps({"ranges": TRECHOS})) == sb.pasta(plano) / "decisoes.json"


def test_peca_que_nao_fotografa_vira_aviso_no_quadro(tmp: Path):
    from PIL import Image
    quadro = tmp / "q.jpg"
    Image.new("RGB", (360, 640), (40, 40, 40)).save(quadro)
    r = {"peca": "peca-que-nao-existe", "_q": {"txt": "x"}, "t0": 1.0, "t1": 3.0, "ar": "360x640"}
    sb._sobrepoe(r, quadro)         # não levanta
    assert quadro.exists() and not quadro.with_suffix(".peca.png").exists()
    # o aviso é desenhado em vermelho no canto: o quadro não é mais cinza liso
    img = Image.open(quadro).convert("RGB")
    assert any(img.getpixel((x, y))[0] > 150 for x in range(12, 200) for y in range(10, 26))


def test_sobreposicao_de_peca_e_sinalizada_mas_legenda_nao(tmp: Path):
    (tmp / "q").mkdir()
    ls = [{"n": 1, "t0": 1.0, "t1": 4.0, "bloco": "b", "peca": "painel", "conteudo": "A", "fala": "", "q": "q/1.jpg"},
          {"n": 2, "t0": 2.0, "t1": 5.0, "bloco": "b", "peca": "chip", "conteudo": "B", "fala": "", "q": "q/2.jpg"},
          {"n": 3, "t0": 1.5, "t1": 4.5, "bloco": "b", "peca": "legenda", "conteudo": "C", "fala": "", "q": "q/3.jpg",
           "legenda": True}]
    sb._escreve(ls, tmp)
    md = (tmp / "storyboard.md").read_text(encoding="utf-8").splitlines()
    assert "junto com nº 2" in md[2] and "junto com nº 1" in md[3], md
    assert "junto com" not in md[4], md[4]


def test_peca_cortada_abaixo_do_tempo_de_ler_leva_o_aviso(tmp: Path):
    ls = [{"n": 1, "t0": 1.0, "t1": 5.6, "bloco": "b", "peca": "painel", "conteudo": "A", "fala": "", "q": "q/1.jpg", "pede": 6.5},
          {"n": 2, "t0": 6.0, "t1": 9.0, "bloco": "b", "peca": "chip", "conteudo": "B", "fala": "", "q": "q/2.jpg"}]
    sb._escreve(ls, tmp)
    md = (tmp / "storyboard.md").read_text(encoding="utf-8").splitlines()
    assert "⚠ 4,6 s; pede 6,5 s" in md[2] and "pede" not in md[3], md


def test_storyboard_do_celular_recusa_plano_em_blocos(tmp: Path):
    plano = {"estilo": "reel-camera", "slug": "x", "_dir": str(tmp), "blocos": [{"nome": "a", "janelas": [[0, 1]]}],
             "fonte": str(_video(tmp))}
    try:
        fb.fabrica(plano, storyboard=True)
    except (ValueError, KeyError, FileNotFoundError) as e:
        assert "storyboard" in str(e).lower() or "bloco" in str(e).lower(), e
    else:
        raise AssertionError("--storyboard vale só pro vídeo do celular")

def test_storyboard_nao_queima_a_legenda_e_o_final_queima(tmp: Path):
    """O storyboard só precisa dos quadros: a cadeia dele não tem o passo de queimar a legenda (103–166 s a rodada) e o
    quadro de cada linha leva a legenda desenhada só nele. O render final continua queimando."""
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    cheio = {**plano, "saida": str(tmp / "s")}
    rasc = fb.fabrica(cheio, seco=True, storyboard=True)
    nomes = [p.nome for p in rasc.passos]
    assert "legenda" not in nomes and "render" in nomes, nomes
    assert "legenda" in [p.nome for p in fb.fabrica(cheio, seco=True).passos]
    # o vídeo passado ao do_celular é o sem legenda e o quadro sai com ela: não é o quadro liso
    q = Image.open(sb.pasta(plano) / "q" / "001.jpg").convert("RGB")
    liso = tmp / "liso.jpg"
    ff.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.8", "-i", video, "-frames:v", "1", "-vf", f"scale={q.width}:-2", liso], quiet=True)
    assert ImageChops.difference(q, Image.open(liso).convert("RGB")).getbbox(), "o quadro saiu sem a legenda"


PECAS = [{"peca": "g_contador", "q": {"de": "0", "para": "30", "rot": "videos prontos"}, "em": 2.0, "dur": 2.0},
         {"peca": "g_sticker", "q": {"txt": "ok"}, "em": "primeiro", "dur": 1.5}]


def _com_pecas(tmp: Path) -> tuple[dict, Path, Path]:
    plano, video, cadeia = _montado(tmp)
    # a fala no tempo do corte: a âncora "primeiro" cai em 1,6 s
    (cadeia / "fala_cortada.json").write_text(json.dumps({"words": [
        {"text": "é", "start": 1.1, "end": 1.5}, {"text": "primeiro", "start": 1.6, "end": 2.0}]}), encoding="utf-8")
    return {**plano, "pecas": PECAS}, video, cadeia


def test_peca_do_plano_vira_linha_numerada_no_tempo_da_fala(tmp: Path):
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    md = [l for l in (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8").splitlines()[2:] if l.startswith("|")]
    assert len(md) == 4 + 2, md
    achada = [l for l in md if "| g_sticker |" in l]
    assert achada and "0:01.6–0:03.1" in achada[0], f"a âncora não caiu na palavra: {md}"
    assert any("| g_contador |" in l and "videos prontos" in l for l in md), md
    assert len(list((sb.pasta(plano) / "q").iterdir())) == 6, "falta o quadro de alguma linha"
    # tirar pelo número tira a peça, e o número dos outros não muda
    arq = sb.pasta(plano) / "decisoes.json"
    n = next(x["n"] for x in json.loads(arq.read_text(encoding="utf-8"))["pecas"] if x["peca"] == "g_sticker")
    sb.tira(arq, n)
    doc = json.loads(arq.read_text(encoding="utf-8"))
    assert [x["peca"] for x in doc["pecas"]] == ["g_contador"] and len(doc["cards"]) == 4
    # a rodada seguinte não traz a peça de volta
    sb.do_celular(plano, cadeia, video, TRECHOS)
    assert "g_sticker" not in (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")


def test_plano_sem_peca_avisa_pra_propor_de_2_a_4(tmp: Path):
    import contextlib
    import io
    plano, video, cadeia = _montado(tmp)
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        sb.do_celular(plano, cadeia, video, TRECHOS)
    assert "nenhuma peça: proponha 2 a 4" in saida.getvalue() and "fabrica-movimento" in saida.getvalue()
    # peças que chegam depois entram na rodada seguinte, sem refazer as correções da legenda
    sb.do_celular({**plano, "pecas": PECAS[:1]}, cadeia, video, TRECHOS)
    assert "| g_contador |" in (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")


def test_troca_de_texto_vale_pra_peca(tmp: Path):
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    arq = sb.pasta(plano) / "decisoes.json"
    n = next(x["n"] for x in json.loads(arq.read_text(encoding="utf-8"))["pecas"] if x["peca"] == "g_sticker")
    sb.troca_texto(arq, n, "show")
    assert next(x for x in json.loads(arq.read_text(encoding="utf-8"))["pecas"] if x["n"] == n)["q"]["txt"] == "show"


def test_render_final_desenha_as_pecas_do_storyboard_e_o_rascunho_nao(tmp: Path):
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    arq = sb.pasta(plano) / "decisoes.json"
    sb.tira(arq, next(x["n"] for x in json.loads(arq.read_text(encoding="utf-8"))["pecas"] if x["peca"] == "g_sticker"))
    seco = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "peça g_contador" in nomes and "peça g_sticker" not in nomes, nomes
    legenda = next(p for p in seco.passos if p.nome == "legenda")
    brolls = json.loads(legenda.arquivo[1])["brolls"]
    assert len(brolls) == 1 and brolls[0]["arquivo"].endswith(".mov") and "peca" not in brolls[0], brolls
    assert (brolls[0]["t0"], brolls[0]["t1"]) == (2.0, 4.0) and brolls[0]["larg"] == 1.0, brolls
    assert len(json.loads(legenda.arquivo[1])["cards"]) == 4, "a legenda saiu do plano das peças"
    # o rascunho do storyboard não renderiza peça (o quadro dela é o mockup do v2.quadro)
    seco = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True, storyboard=True)
    assert not [p.nome for p in seco.passos if p.nome.startswith("peça")], "o rascunho renderizou peça"


# ---- câmera, sons, palavra atrás da cabeça e fundo pelo plano; densidade; mudo/atras da peça ----------------

MOV = {"camera": [{"em": 0.5, "ate": 1.5, "zoom": [1.0, 1.2], "ease": "sine"},
                  {"em": 4.47, "dur": 0.4, "zoom": [1.0, 1.32], "ease": "crava", "borrao": 4}],
       "sons": [{"t": "primeiro", "tipo": "hit"}, {"t": 6.0, "tipo": "boom"}],
       "palavras_atras": [{"em": 2.5, "texto": "gravei", "dur": 0.8}],
       "fundo": {"de": 2.0, "ate": 4.0}}


def _com_movimento(tmp: Path) -> tuple[dict, Path, Path]:
    plano, video, cadeia = _com_pecas(tmp)
    return {**plano, **MOV}, video, cadeia


def _doc(plano: dict) -> dict:
    return json.loads((sb.pasta(plano) / "decisoes.json").read_text(encoding="utf-8"))


def test_peca_leva_mudo_e_atras_do_plano_ate_o_render(tmp: Path):
    plano, video, cadeia = _montado(tmp)
    (cadeia / "fala_cortada.json").write_text(json.dumps({"words": []}), encoding="utf-8")
    plano = {**plano, "pecas": [{"peca": "g_contador", "q": {"de": "0", "para": "30"}, "em": 2.0, "dur": 2.0,
                                 "mudo": True, "atras": True, "peso": 3}]}
    sb.do_celular(plano, cadeia, video, TRECHOS)
    p = _doc(plano)["pecas"][0]
    assert p["mudo"] is True and p["atras"] is True and p["peso"] == 3, p
    seco = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True)
    brolls = json.loads(next(x for x in seco.passos if x.nome == "legenda").arquivo[1])["brolls"]
    assert brolls[0].get("mudo") is True and brolls[0].get("atras") is True, brolls
    som = json.loads(next(x for x in seco.passos if x.nome == "som").arquivo[1])
    assert som["brolls"][0].get("mudo") is True, "o som.py precisa do mudo pra não tocar a peça"


def test_plano_com_camera_sons_palavra_atras_e_fundo_chega_no_render_sem_mexer_no_json(tmp: Path):
    plano, video, cadeia = _com_movimento(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    doc = _doc(plano)
    assert [(c["t0"], c["t1"], c.get("ease")) for c in doc["camera"]] == [(0.5, 1.5, "sine"), (4.47, 4.87, "crava")], doc["camera"]
    assert doc["camera"][1]["borrao"] == 4
    assert [(s["t"], s["tipo"]) for s in doc["sons"]] == [(1.6, "hit"), (6.0, "boom")], doc["sons"]
    herois = [c for c in doc["cards"] if c.get("atras")]
    assert len(herois) == 1 and herois[0]["words"][0]["tx"] == "GRAVEI" and herois[0]["tela"]["fundo"] is True, herois
    assert herois[0]["tela"]["inicio"] == 0.5, "o fundo toca desde o começo da janela dele"
    assert not [c for c in doc["cards"] if not c.get("atras") and 2.5 <= (c["t0"] + c["t1"]) / 2 <= 3.3], "a legenda de baixo ficou"
    # o número vale pra tudo: card, peça, zoom e som
    ns = [x["n"] for k in ("cards", "pecas", "camera", "sons") for x in doc[k]]
    assert len(ns) == len(set(ns)) == 4 + 2 + 2 + 2, ns
    # o storyboard tem uma linha por zoom e por som, com número
    md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
    assert md.count("| câmera |") == 2 and md.count("| som |") == 2 and "| palavra atrás | gravei" in md.lower().replace("GRAVEI", "gravei"), md
    assert "crava 1,00→1,32" in md and "hit" in md and "boom" in md, md
    # o render final desenha isso: o fundo vira a peça e_fundo (mp4 opaco), e o rascunho não renderiza nem o fundo
    seco = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True)
    assert any(p.nome == "peça e_fundo" for p in seco.passos), [p.nome for p in seco.passos]
    leg = json.loads(next(p for p in seco.passos if p.nome == "legenda").arquivo[1])
    assert len(leg["camera"]) == 2 and leg["camera"][1]["ease"] == "crava", leg["camera"]
    tela = next(c["tela"] for c in leg["cards"] if c.get("atras"))
    assert tela["arquivo"].endswith(".mp4") and tela["fundo"] is True, tela
    som = json.loads(next(p for p in seco.passos if p.nome == "som").arquivo[1])
    assert [(x["t"], x["tipo"]) for x in som["sons"]] == [(1.6, "hit"), (6.0, "boom")], som["sons"]
    ras = fb.fabrica({**plano, "saida": str(tmp / "s")}, seco=True, storyboard=True)
    assert not [p.nome for p in ras.passos if p.nome.startswith("peça")], "o rascunho renderizou peça"
    assert "legenda" not in [p.nome for p in ras.passos], "o storyboard não queima a legenda no vídeo"
    quadros = json.loads((cadeia / "quadros.json").read_text(encoding="utf-8"))     # o plano da legenda dos quadros
    assert quadros["cards"] and all("tela" not in c for c in quadros["cards"]), "o rascunho não tem o fundo trocado"


def test_tirar_zoom_e_som_pelo_numero_e_a_palavra_atras_aceita_troca_de_texto(tmp: Path):
    plano, video, cadeia = _com_movimento(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    arq = sb.pasta(plano) / "decisoes.json"
    doc = _doc(plano)
    zoom, som, heroi = doc["camera"][1]["n"], doc["sons"][1]["n"], next(c["n"] for c in doc["cards"] if c.get("atras"))
    sb.tira(arq, zoom)
    sb.tira(arq, som)
    sb.troca_texto(arq, heroi, "filmei")
    doc = _doc(plano)
    assert len(doc["camera"]) == 1 and [s["tipo"] for s in doc["sons"]] == ["hit"], doc
    assert next(c for c in doc["cards"] if c.get("atras"))["words"][0]["tx"] == "FILMEI"
    try:
        sb.troca_texto(arq, doc["camera"][0]["n"], "x")
    except ValueError as e:
        assert "zoom e o som saem com --tira" in str(e), e
    else:
        raise AssertionError("zoom não tem texto pra trocar")
    # a rodada seguinte não traz de volta o que saiu, nem duplica a palavra atrás
    sb.do_celular(plano, cadeia, video, TRECHOS)
    doc = _doc(plano)
    assert len(doc["camera"]) == 1 and len(doc["sons"]) == 1 and len([c for c in doc["cards"] if c.get("atras")]) == 1
    md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
    assert f"| {zoom} |" not in md and f"| {som} |" not in md, md
    # tirar todos os zooms deixa a câmera parada, e o plano não os repõe
    sb.tira(arq, doc["camera"][0]["n"])
    sb.do_celular(plano, cadeia, video, TRECHOS)
    assert _doc(plano)["camera"] == []


def _mov(tmp: Path, **kw) -> Path:
    import movimento
    arq = tmp / "escolhas.json"
    movimento.grava(arquivo=arq, **kw)
    return arq


FALA = ("Eu parei de editar vídeo na mão. Agora faço trinta vídeos por semana usando um agente de edição. "
        "Foi isso que mudou o meu trabalho completamente, e hoje tudo fica pronto sozinho.")


def _fala(tmp: Path | None = None):
    ws, t = [], 0.1
    for w in FALA.split():
        ws.append({"text": w, "start": round(t, 2), "end": round(t + 0.3, 2), "type": "word"})
        t += 0.34
    return ws, round(t, 1)


def _checa(proposta: dict, dur: float, mov: dict):
    """A proposta, do jeito que o `decisoes.json` a guardaria, medida pelos mesmos avisos do storyboard."""
    doc = {"cards": [{"t0": c["em"], "t1": c["em"] + c["dur"], "atras": True, "tela": {"fundo": True}}
                     for c in proposta.get("palavras_atras", [])],
           "pecas": [{"peca": p["peca"], "t0": p["em"], "t1": p["em"] + p["dur"], "peso": p["peso"]} for p in proposta.get("pecas", [])],
           "camera": [{"t0": c["em"], "t1": c["em"] + c["dur"], "zoom": c["zoom"]} for c in proposta.get("camera", [])],
           "sons": [{"t": x["t"]} for x in proposta.get("sons", [])]}
    import checks
    import movimento
    return {r.id: r for r in checks.ritmo(sb.eventos(doc), dur, {**movimento.PRIMEIRO_VIDEO, **mov})}, doc


def test_proposta_automatica_cumpre_a_densidade_e_so_usa_o_cardapio():
    import checks
    import propoe
    ws, dur = _fala()
    ids = checks._cardapio()
    assert ids, "sem cardápio o teste não prova nada"
    for dens in ("intensa", "media"):
        plano, resumo = propoe.propoe(ws, dur, {"densidade": dens}, ids)
        assert plano == propoe.propoe(ws, dur, {"densidade": dens}, ids)[0], "a proposta tem que ser determinística"
        pecas = plano["pecas"]
        gancho = next(p for p in pecas if p["peca"] == "g_gancho")
        assert gancho["em"] <= 0.5 and gancho["em"] + gancho["dur"] <= 3.0 and gancho["q"]["l"].replace("*", "").replace("_", "").replace("|", " ").startswith("Eu parei de"), gancho
        assert any(p["peca"] == "g_comenta" and p["em"] + p["dur"] >= dur - 0.5 for p in pecas), "falta a chamada no fim"
        assert any(p["peca"] == "k_palavra_gigante" and p["q"]["l"] == "TRINTA" for p in pecas), "o número dito virou peça"
        assert {p["peca"] for p in pecas} <= set(ids), [p["peca"] for p in pecas]
        assert not {p["peca"] for p in pecas} & set(checks.CASCA)
        rs, _ = _checa(plano, dur, {"densidade": dens})
        assert rs["ritmo-vao"].ok, rs["ritmo-vao"].mediu
        assert rs["pouca-variacao"].ok, rs["pouca-variacao"].mediu
        assert rs["peso-3"].ok and rs["veto"].ok and rs["casca-de-pagina"].ok and rs["camera-atras"].ok, rs
        assert 1 <= len(plano["sons"]) <= 3 and len(plano["sons"]) == len(plano["palavras_atras"]), plano["sons"]
        assert plano["fundo"]["de"] <= plano["palavras_atras"][0]["em"] and plano["fundo"]["ate"] >= plano["palavras_atras"][-1]["em"]
    # intensa pede mais troca de layout do que o mínimo dela (uma a cada 12 s), e mais movimento que a média
    assert len(propoe.propoe(ws, dur, {"densidade": "intensa"}, ids)[0]["palavras_atras"]) >= 2
    n = lambda d: sum(len(v) for k, v in propoe.propoe(ws, dur, {"densidade": d}, ids)[0].items() if k in ("pecas", "camera", "palavras_atras"))
    assert n("intensa") > n("media") > n("calma") - 1, (n("intensa"), n("media"), n("calma"))
    assert "palavras_atras" not in propoe.propoe(ws, dur, {"densidade": "calma"}, ids)[0], "calma não exige troca de layout"


def test_proposta_respeita_veto_e_efeitos():
    import checks
    import propoe
    ws, dur = _fala()
    ids = checks._cardapio()
    p, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "vetos": ["zoom", "g_comenta"]}, ids)
    assert "camera" not in p and not any(x["peca"] == "g_comenta" for x in p["pecas"]), p
    p, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "vetos": ["palavra_atras"]}, ids)
    assert not {"palavras_atras", "fundo", "sons"} & set(p), "sem palavra atrás não há troca de layout nem batida de peso 3"
    p, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "efeitos": ["zoom"]}, ids)
    assert set(p) == {"camera"}, p
    p, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "vetos": ["layout"]}, ids)
    assert "palavras_atras" not in p, "veto de layout tira a troca"


def test_pouca_variacao_avisa_quando_falta_troca_de_layout():
    import checks
    ev = lambda *x: [{"t0": a, "t1": b, "tipo": t} for a, b, t in x]
    intensa = {"densidade": "intensa", "efeitos": ["zoom", "palavra_atras", "layout", "pecas", "sons"]}
    seis = [(i, i + 0.4, "zoom") for i in range(0, 26, 2)]
    r = next(x for x in checks.ritmo(ev(*seis), 26, intensa) if x.id == "pouca-variacao")
    assert r.ok is False and "faltam 3" in r.mediu, r.mediu              # 26 s de intensa pedem 3 trocas
    r = next(x for x in checks.ritmo(ev(*seis, (5, 5.8, "layout"), (13, 13.8, "layout"), (20, 20.8, "layout")), 26, intensa) if x.id == "pouca-variacao")
    assert r.ok is True, r.mediu
    media = {**intensa, "densidade": "media"}
    assert next(x for x in checks.ritmo(ev((1, 2, "zoom")), 22, media) if x.id == "pouca-variacao").ok is False   # 22 s: 2 trocas
    assert next(x for x in checks.ritmo(ev((1, 2, "zoom")), 18, media) if x.id == "pouca-variacao").ok is False   # 18 s: 1 troca
    assert next(x for x in checks.ritmo(ev((1, 2, "layout")), 18, media) if x.id == "pouca-variacao").ok is True
    # calma não exige; sem o fundo trocado (aluno vetou) o aviso não cobra o que ele não quer
    assert next(x for x in checks.ritmo(ev((1, 2, "zoom")), 30, {**intensa, "densidade": "calma"}) if x.id == "pouca-variacao").ok is None
    assert next(x for x in checks.ritmo(ev((1, 2, "zoom")), 30, {**intensa, "vetos": ["palavra_atras"]}) if x.id == "pouca-variacao").ok is None
    # o efeito `layout` na lista do aluno basta: não exige palavra_atras gravada ao lado (e a troca não conta como efeito vetado)
    so_layout = {"densidade": "intensa", "efeitos": ["layout", "zoom"]}
    rs = {x.id: x for x in checks.ritmo(ev((1, 2, "layout")), 8, so_layout)}
    assert rs["pouca-variacao"].ok is True and rs["veto"].ok is True


def test_storyboard_sem_plano_propoe_o_movimento_e_o_aluno_so_ajusta(tmp: Path):
    import contextlib
    import io
    import os
    plano, video, cadeia = _montado(tmp)
    ws, _ = _fala()
    (cadeia / "fala_cortada.json").write_text(json.dumps({"words": ws}), encoding="utf-8")
    trechos = [{"source": "celular", "start": 0.0, "end": 8.0}]
    arq = _mov(tmp, densidade="intensa", efeitos=["zoom", "palavra_atras", "layout", "pecas", "sons"])
    antes = os.environ.get("FABRICA_ESCOLHAS")
    os.environ["FABRICA_ESCOLHAS"] = str(arq)
    try:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            sb.do_celular(plano, cadeia, video, trechos)
        doc = _doc(plano)
        assert doc["pecas"] and doc["camera"] and doc["sons"] and any(c.get("atras") and c["tela"]["fundo"] for c in doc["cards"]), doc.keys()
        assert "proposta automática (intensa)" in saida.getvalue() and "nenhuma peça" not in saida.getvalue(), saida.getvalue()
        assert doc["fundo"]["peca"] == "e_fundo" and doc["proposta"] is True
        md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
        assert "| g_gancho |" in md and "| palavra atrás |" in md, md
        # o que o aluno tirou pelo número não volta na rodada seguinte
        n = doc["pecas"][0]["n"]
        sb.tira(sb.pasta(plano) / "decisoes.json", n)
        sb.do_celular(plano, cadeia, video, trechos)
        assert n not in [p["n"] for p in _doc(plano)["pecas"]], "a proposta voltou depois do tira"
        # plano com movimento à mão: a Fábrica não propõe por cima
        outro = tmp / "mao"
        outro.mkdir()
        plano2, video2, cadeia2 = _montado(outro)
        (cadeia2 / "fala_cortada.json").write_text(json.dumps({"words": ws}), encoding="utf-8")
        sb.do_celular({**plano2, "pecas": PECAS[:1]}, cadeia2, video2, trechos)
        assert len(_doc(plano2)["pecas"]) == 1 and "camera" not in _doc(plano2) and "proposta" not in _doc(plano2)
    finally:
        if antes is None:
            os.environ.pop("FABRICA_ESCOLHAS", None)
        else:
            os.environ["FABRICA_ESCOLHAS"] = antes


def test_sem_flash_do_corte_aparece_no_storyboard_e_nao_no_render(tmp: Path):
    import contextlib
    import io
    plano, video, cadeia = _montado(tmp)
    claro = tmp / "flash.mp4"        # preto, um quadro branco, preto: salto de brilho que volta em 1 quadro
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=360x640:r=25:d=2", "-f", "lavfi",
            "-i", "color=c=white:s=360x640:r=25:d=0.04", "-f", "lavfi", "-i", "color=c=gray:s=360x640:r=25:d=2",
            "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", claro], quiet=True)
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        sb.do_celular(plano, cadeia, claro, TRECHOS)
    assert "AVISO sem-flash" in saida.getvalue(), saida.getvalue()
    assert "sem-flash" in (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")


def test_help_imprime_o_uso():
    import subprocess
    p = subprocess.run([sys.executable, str(Path(__file__).with_name("storyboard.py")), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and "storyboard.py <plano.json>" in p.stdout and "Traceback" not in p.stderr, p.stderr[-300:]


def test_ritmo_mede_vao_peso_3_veto_casca_e_camera_sobre_palavra_atras():
    import checks
    ev = lambda *x: [{"t0": a, "t1": b, "tipo": t, **({"peca": p} if p else {}), **({"peso": w} if w else {})}
                     for a, b, t, p, w in x]
    ok = lambda rs, i: next(r for r in rs if r.id == i).ok
    intensa = {"densidade": "intensa", "efeitos": ["zoom", "transicao", "palavra_atras", "pecas", "sons"]}
    # vão: de 3 a 8 são 5 s, mais que os 2 s da intensa; som não conta como mudança de imagem
    rs = checks.ritmo(ev((1, 2, "zoom", None, None), (3, 5, "pecas", "e_raio", None), (6.5, 6.5, "sons", None, None)), 8, intensa)
    assert ok(rs, "ritmo-vao") is False and "maior vão 5.0 s a partir de 3.0 s" in next(r for r in rs if r.id == "ritmo-vao").mediu
    assert ok(checks.ritmo(ev((1, 2, "zoom", None, None), (2.5, 3, "zoom", None, None), (4, 5, "pecas", "e_raio", None),
                             (5.5, 6, "zoom", None, None), (7, 7.5, "zoom", None, None)), 8, intensa), "ritmo-vao")
    assert ok(checks.ritmo(ev((1, 2, "zoom", None, None)), 8, {**intensa, "densidade": "calma"}), "ritmo-vao") is False   # 6 s
    assert ok(checks.ritmo([], 5, {"densidade": "calma"}), "ritmo-vao")
    # sem densidade escolhida o vão não se mede: quem pergunta é o agente
    assert ok(checks.ritmo([], 8, {}), "ritmo-vao") is None
    # peso 3 passa de 25 % do vídeo
    assert ok(checks.ritmo(ev((0, 3, "pecas", "e_x", 3)), 8, intensa), "peso-3") is False
    assert ok(checks.ritmo(ev((0, 2, "pecas", "e_x", 3)), 8, intensa), "peso-3")
    # veto: por tipo, por nome de peça, e efeito fora dos que ele quer
    assert ok(checks.ritmo(ev((1, 2, "zoom", None, None)), 8, {**intensa, "vetos": ["zoom"]}), "veto") is False
    assert ok(checks.ritmo(ev((1, 2, "pecas", "e_raio", None)), 8, {**intensa, "vetos": ["e_raio"]}), "veto") is False
    assert ok(checks.ritmo(ev((1, 2, "transicao", "x_corte", None)), 8, {**intensa, "efeitos": ["zoom"]}), "veto") is False
    assert ok(checks.ritmo(ev((1, 2, "zoom", None, None)), 8, intensa), "veto")
    # casca de página
    for casca in ("g_contador", "g_distintivo_versao", "h_progresso", "k_contador_x"):
        assert ok(checks.ritmo(ev((1, 2, "pecas", casca, None)), 8, intensa), "casca-de-pagina") is False, casca
    assert ok(checks.ritmo(ev((1, 2, "pecas", "e_raio", None)), 8, intensa), "casca-de-pagina")
    # o aviso já diz a saída: peças do cardápio que ainda não estão no plano
    r = next(x for x in checks.ritmo(ev((1, 2, "pecas", "g_contador", None), (3, 4, "pecas", "g_gancho", None)), 8, intensa)
             if x.id == "casca-de-pagina")
    assert "g_contador" in r.mediu and "cardápio: t_headline" in r.mediu and "g_gancho" not in r.mediu.split("cardápio:")[1], r.mediu
    # câmera mexendo por cima da palavra atrás da cabeça
    mexe = [{"t0": 1, "t1": 2, "tipo": "zoom", "zoom": [1.0, 1.3]}, {"t0": 1.5, "t1": 2.5, "tipo": "palavra_atras", "peso": 3}]
    assert ok(checks.ritmo(mexe, 8, intensa), "camera-atras") is False
    parada = [{**mexe[0], "zoom": [1.0, 1.0]}, mexe[1]]
    assert ok(checks.ritmo(parada, 8, intensa), "camera-atras")


def test_aviso_de_densidade_aparece_no_storyboard_e_no_seco(tmp: Path):
    import contextlib
    import io
    import os
    plano, video, cadeia = _com_movimento(tmp)
    # peça de casca no plano: g_contador
    arq = _mov(tmp, densidade="intensa", efeitos=["zoom", "sons", "palavra_atras", "pecas"], veta=["zoom"])
    antes = os.environ.get("FABRICA_ESCOLHAS")
    os.environ["FABRICA_ESCOLHAS"] = str(arq)
    try:
        # antes do primeiro storyboard o --seco já avisa, pelo próprio plano (âncora em segundo, nada medido)
        so_segundos = {**plano, "sons": [s for s in MOV["sons"] if isinstance(s["t"], (int, float))],
                       "pecas": PECAS[:1]}
        seco = fb.fabrica({**so_segundos, "saida": str(tmp / "s0")}, seco=True)
        ids = {r.id: r for r in seco.checks}
        assert ids["ritmo-vao"].ok is False and ids["veto"].ok is False and ids["casca-de-pagina"].ok is False, ids
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            sb.do_celular(plano, cadeia, video, TRECHOS)
        md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
        assert "⚠ ritmo-vao" in md and "⚠ veto" in md and "⚠ casca-de-pagina" in md, md
        assert "AVISO ritmo-vao" in saida.getvalue() and "zoom no plano" in saida.getvalue(), saida.getvalue()
        pagina = (sb.pasta(plano) / "revisao.html").read_text(encoding="utf-8")
        assert "⚠ ritmo-vao" in pagina and "⚠ veto" in pagina, "os avisos de ritmo sobem pro topo da revisão"
        assert pagina.index("ritmo-vao") < pagina.index("<article"), "no topo, antes dos cartões"

        # perdoado o veto e dada a densidade calma, os avisos de veto e de vão somem
        _mov(tmp, densidade="calma", perdoa=["zoom"])
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            sb.do_celular(plano, cadeia, video, TRECHOS)
        md = (sb.pasta(plano) / "storyboard.md").read_text(encoding="utf-8")
        assert "⚠ veto" not in md and "⚠ ritmo-vao" not in md and "⚠ casca-de-pagina" in md, md
    finally:
        if antes is None:
            os.environ.pop("FABRICA_ESCOLHAS", None)
        else:
            os.environ["FABRICA_ESCOLHAS"] = antes


def test_revisao_tem_um_cartao_por_item_e_um_clipe_leve_de_cada(tmp: Path):
    """A página de revisão (dono, 29/10): um cartão por item numerado, com o clipe do trecho cortado da prévia
    (360 px, H.264, com a voz), os três botões e a nota. Abre sem servidor: o que ela toca está ao lado dela."""
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    pasta = sb.pasta(plano)
    pagina = (pasta / "revisao.html").read_text(encoding="utf-8")
    assert pagina.count("<article") == 4, "um cartão por item numerado"
    for n, fala in enumerate(["OI ESSE", "É O MEU PRIMEIRO", "VÍDEO", "EU GRAVEI NO CELULAR"], 1):
        clipe = pasta / "clipes" / f"{n:03d}.mp4"
        assert clipe.exists() and f'src="clipes/{n:03d}.mp4"' in pagina, clipe
        assert f'data-n="{n}"' in pagina and fala in pagina and f"{sb.fmt(0.5)}" in pagina
    for botao in ("manter", "talvez", "tirar"):
        assert pagina.count(f'data-v="{botao}"') == 4, botao
    assert pagina.count("<textarea") == 4 + 1, "a nota de cada item e o texto pra copiar"
    sonda = ff.probe(pasta / "clipes" / "001.mp4")
    assert (sonda.largura, sonda.codec, sonda.tem_audio) == (360, "h264", True), sonda


def test_copiar_revisao_entrega_o_texto_pra_colar_no_claude(tmp: Path):
    """A página roda num Chromium de verdade: marca, escreve nota, clica em Copiar revisão e lê o que foi pro clipboard.
    Sem Playwright ou sem Chromium o teste se cala em vez de reprovar (o computador do aluno pode não ter)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return print("pulou: sem playwright")
    plano, video, cadeia = _montado(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    pasta = sb.pasta(plano)
    pagina = (pasta / "revisao.html").as_uri()                    # file://, como o aluno abre: sem servidor
    clipboard_ok = ("window.__t = null; Object.defineProperty(navigator, 'clipboard', {configurable: true, "
                    "value: {writeText: (t) => { window.__t = t; return Promise.resolve(); }}});")
    clipboard_recusa = ("window.__x = null; Object.defineProperty(navigator, 'clipboard', {configurable: true, "
                        "value: {writeText: () => Promise.reject(new Error('file://'))}});"
                        "document.execCommand = (c) => { window.__x = [c, document.activeElement.value]; return true; };")
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            return print(f"pulou: sem Chromium ({str(e)[:60]})")
        try:
            pag = nav.new_page(viewport={"width": 390, "height": 844})
            pag.add_init_script(clipboard_ok)
            pag.goto(pagina)
            pag.click("#copia")
            assert "Marque pelo menos um item" in pag.inner_text("#status"), "revisão vazia não copia nada"
            pag.click("#i1 [data-v=manter]")
            pag.click("#i4 [data-v=tirar]")
            pag.fill("#i3 textarea", "entra mais cedo")           # nota sem marca: o item vira talvez
            assert pag.inner_text("#feitos") == "3"
            pag.click("#copia")
            pag.wait_for_function("window.__t !== null")
            linhas = pag.evaluate("window.__t").splitlines()
            assert linhas[:4] == ['Revisão do storyboard "celular":', "1 manter", "3 talvez: entra mais cedo", "4 tirar"], linhas
            assert len(linhas) == 5, linhas
            fim = linhas[4]                                         # a linha que diz o que fazer
            assert f"--aplica {pasta.name}" in fim and "só o que precisa de você" in fim and "Não renderize antes" in fim, fim
            pag.reload()                                            # a marcação sobrevive a um F5
            assert pag.get_attribute("#i4 [data-v=tirar]", "aria-pressed") == "true"
            pag.click("#faltam")
            assert pag.locator(".c:visible").count() == 1           # só o 2, que ninguém marcou
            seg = nav.new_page(viewport={"width": 390, "height": 844})
            seg.add_init_script(clipboard_recusa)                   # o file:// recusa: cai no textarea + execCommand
            seg.goto(pagina)
            seg.click("#i4 [data-v=tirar]")
            seg.click("#copia")
            seg.wait_for_function("window.__x !== null")
            comando, valor = seg.evaluate("window.__x")
            assert comando == "copy" and valor.splitlines()[1] == "4 tirar", (comando, valor)
        finally:
            nav.close()


def test_texto_colado_aplica_o_certo_e_lista_so_o_que_o_agente_decide(tmp: Path):
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    arq = sb.pasta(plano) / "decisoes.json"
    doc = json.loads(arq.read_text(encoding="utf-8"))
    n_sticker = next(x["n"] for x in doc["pecas"] if x["peca"] == "g_sticker")
    n_cont = next(x["n"] for x in doc["pecas"] if x["peca"] == "g_contador")
    c1, c2, c3 = (c["n"] for c in doc["cards"][:3])
    colado = "\n".join([
        'Revisão do storyboard "celular":', f"{c1} manter", f"{c2} manter: deixa mais curto", f"{n_cont} tirar",
        f"{n_sticker} texto: certo", f"{c3} talvez: entra mais cedo", f"{c3} talvez: texto: vídeo novo", "99 tirar",
        "isto não é item", "Aplique de uma vez: storyboard.py --aplica x"])
    feito, pendente = sb.aplica(arq, colado)
    novo = json.loads(arq.read_text(encoding="utf-8"))
    assert [x["peca"] for x in novo["pecas"]] == ["g_sticker"] and novo["pecas"][0]["q"]["txt"] == "certo", novo["pecas"]
    assert " ".join(w["tx"].lower() for w in next(c for c in novo["cards"] if c["n"] == c3)["words"]) == "vídeo novo"
    assert len(feito) == 3, feito       # tirar, texto da peça, texto dentro de talvez
    assert pendente[:2] == [f"nº {c2} manter: deixa mais curto", f"nº {c3} talvez: entra mais cedo"], pendente
    assert "não existe o nº 99" in pendente[2] and pendente[3] == "linha que não entendi: 'isto não é item'", pendente
    assert len(pendente) == 4 and f"{c1} manter" not in "".join(pendente)
    # pela linha de comando: o texto vem de arquivo, e a saída é curta
    import contextlib
    import io
    (tmp / "r.txt").write_text(f"{n_sticker} tirar\n{c1} talvez: mais rápido\n", encoding="utf-8")
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        sb._aplica([str(arq.parent), str(tmp / "r.txt")])
    assert "aplicado: 1" in saida.getvalue() and "precisa de você (1)" in saida.getvalue() and f"{c1} talvez: mais rápido" in saida.getvalue()
    assert json.loads(arq.read_text(encoding="utf-8"))["pecas"] == []


def test_so_o_item_mudado_refaz_quadro_e_clipe_e_o_orfao_some(tmp: Path):
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    pasta = sb.pasta(plano)
    arqs = [*(pasta / "q").iterdir(), *(pasta / "clipes").iterdir()]
    antes = {a.relative_to(pasta).as_posix(): a.stat().st_mtime_ns for a in arqs}
    assert len(antes) == 12, sorted(antes)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    assert {a.relative_to(pasta).as_posix(): a.stat().st_mtime_ns for a in [*(pasta / "q").iterdir(), *(pasta / "clipes").iterdir()]} == antes, \
        "nada mudou: nada é refeito"
    # troca o texto da peça 'g_sticker': só o quadro e o clipe dela são refeitos
    arq = pasta / "decisoes.json"
    n = next(x["n"] for x in json.loads(arq.read_text(encoding="utf-8"))["pecas"] if x["peca"] == "g_sticker")
    sb.troca_texto(arq, n, "novo")
    sb.do_celular(plano, cadeia, video, TRECHOS)
    depois = {a.relative_to(pasta).as_posix(): a.stat().st_mtime_ns for a in [*(pasta / "q").iterdir(), *(pasta / "clipes").iterdir()]}
    mudou = sorted(k for k in antes if depois[k] != antes[k])
    assert mudou == [f"clipes/{n:03d}.mp4", f"q/{n:03d}.jpg"], mudou
    # tirar um item apaga os arquivos dele (o órfão), sem refazer os outros
    sb.tira(arq, n)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    assert not (pasta / "q" / f"{n:03d}.jpg").exists() and not (pasta / "clipes" / f"{n:03d}.mp4").exists()
    assert len(list((pasta / "q").iterdir())) == 5 and len(list((pasta / "clipes").iterdir())) == 5
    assert all(depois[k] == a.stat().st_mtime_ns for k, a in ((f"q/{i:03d}.jpg", pasta / "q" / f"{i:03d}.jpg")
                                                              for i in range(1, 7) if i != n)), "os outros ficaram"


def test_cartao_da_peca_aponta_pra_peca_certa_com_os_parametros_dela(tmp: Path):
    import urllib.parse
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    pasta = sb.pasta(plano)
    pagina = (pasta / "revisao.html").read_text(encoding="utf-8")
    import html as h
    srcs = [h.unescape(m) for m in re.findall(r'class="pl" data-src="([^"]+)"', pagina)]
    assert len(srcs) == 2, "uma peça tocando em cada cartão de peça, nenhuma na legenda"
    por_peca = {}
    for s_ in srcs:
        rel, _, qs = s_.partition("?")
        por_peca[Path(urllib.parse.unquote(rel)).name] = (rel, urllib.parse.parse_qs(qs))
    rel, q = por_peca["g_contador.html"]
    if rel.startswith("file:"):      # outro disco (Windows): o endereço inteiro
        import urllib.request
        assert Path(urllib.request.url2pathname(urllib.parse.urlparse(rel).path)).exists(), rel
    else:
        assert (pasta / urllib.parse.unquote(rel)).resolve().exists(), "achada por caminho relativo à pasta da revisão (file://)"
        assert not rel.startswith("/"), rel
    assert q["rot"] == ["videos prontos"] and q["para"] == ["30"] and q["alfa"] == ["1"] and q["vivo"] == ["1"] and q["ar"] == ["1080x1920"], q
    assert por_peca["g_sticker.html"][1]["txt"] == ["ok"]
    # o clipe começa 0,3 s antes da peça (a respiração): é nesse instante que ela entra
    assert 'data-off="0.30"' in pagina and 'data-w="1080" data-h="1920"' in pagina
    # peça que não existe na biblioteca: o cartão fica com o quadro parado, sem iframe
    ls = sb.linhas_decisoes(json.loads((pasta / "decisoes.json").read_text(encoding="utf-8")))
    r = next(x for x in ls if x["peca"] == "g_sticker")
    assert sb._peca_viva({**r, "peca": "nao_existe"}, pasta) is None
    # Windows com a pasta num disco e a biblioteca em outro: sem caminho relativo, vale o endereço file:// inteiro
    real = sb.os.path.relpath
    sb.os.path.relpath = lambda *_a, **_k: (_ for _ in ()).throw(ValueError("path is on mount 'C:'"))
    try:
        assert sb._peca_viva(r, pasta).startswith("file:///"), "outro disco"
    finally:
        sb.os.path.relpath = real


def test_peca_toca_por_cima_do_clipe_no_navegador_por_file(tmp: Path):
    """No Chromium, abrindo por file://: ao dar play a peça entra como iframe na escala do clipe; ao pausar, sai."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return print("pulou: sem playwright")
    plano, video, cadeia = _com_pecas(tmp)
    sb.do_celular(plano, cadeia, video, TRECHOS)
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        except Exception as e:  # noqa: BLE001
            return print(f"pulou: sem Chromium ({str(e)[:60]})")
        try:
            pag = nav.new_page(viewport={"width": 1100, "height": 900})
            pag.goto((sb.pasta(plano) / "revisao.html").as_uri())
            assert pag.locator(".pl iframe").count() == 0, "antes do play não há peça"
            pag.evaluate("() => { const v = document.querySelector('.pl[data-src] video'); v.muted = true; v.play(); }")
            pag.wait_for_selector(".pl iframe", timeout=5000)
            src = pag.get_attribute(".pl iframe", "src")
            assert "/pecas/" in src and "vivo=1" in src and "alfa=1" in src, src
            assert "scale(" in pag.get_attribute(".pl iframe", "style")
            pag.evaluate("() => document.querySelector('.pl[data-src] video').pause()")
            pag.wait_for_function("document.querySelectorAll('.pl iframe').length === 0")
        finally:
            nav.close()


def test_folha_animada_tempo_redondo_e_chamada_fora_do_navegador():
    """06/11: 59,97 s não vira "0:60.0"; a `l_chamada` (que com ?vivo=1 espera o OBS e fica vazia) não toca por cima: vai queimada no clipe."""
    assert sb.fmt(59.97) == "1:00.0" and sb.fmt(61.3) == "1:01.3" and sb.fmt(0.5) == "0:00.5"
    assert "l_chamada" in sb.SEM_VIVO
    assert sb._peca_viva({"peca": "l_chamada", "_q": {"tx": "Link"}}, Path(tempfile.gettempdir())) is None


def test_folha_animada_grande_peca_segue_o_video_e_tela_cheia_e_do_conteiner(tmp: Path):
    """07/11 (dono): em tela cheia do <video> a peça sumia, e o vídeo da folha era pequeno pra um notebook. Na folha animada
    (`grande`): clipe de 1280 px, vídeo na linha inteira (até 1200 px) com o texto embaixo, a peça no tamanho do vídeo
    (janela, layout ou tela cheia), o botão do <video> some e a tela cheia é do contêiner. Sem `grande` nada disso muda."""
    video = tmp / "seco.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=6",
            "-f", "lavfi", "-i", "sine=frequency=300:duration=6", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", video], quiet=True)
    pastas = {}
    for modo in (True, False):
        pastas[modo] = tmp / f"folha-{modo}"
        (pastas[modo] / "q").mkdir(parents=True)
        Image.new("RGB", (1280, 720), "gray").save(pastas[modo] / "q" / "001.jpg")
        ls = [{"n": 1, "t0": 1.0, "t1": 5.0, "bloco": "b", "peca": "g_sticker", "conteudo": "ok", "_q": {"txt": "ok"},
               "ar": None, "fala": "oi", "q": "q/001.jpg", "_k": "a"}]
        sb._revisao(ls, pastas[modo], video, "t", viva=True, grande=modo)
    grande, comum = (pastas[m] / "revisao.html" for m in (True, False))
    assert ff.probe(pastas[True] / "clipes" / "001.mp4").largura == 1280, "o clipe nasce do tamanho em que aparece"
    assert ff.probe(pastas[False] / "clipes" / "001.mp4").largura == 640, "sem `grande` o clipe segue leve"
    pg = grande.read_text(encoding="utf-8")
    assert 'class="w g"' in pg and 'class="w "' in comum.read_text(encoding="utf-8")
    assert pg.count("controlslist=nofullscreen") == 1 and pg.count('class="fs"') == 1, "a tela cheia é do contêiner"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return print("pulou: sem playwright")
    # a peça tem que cobrir o vídeo: mesma largura e, em tela cheia (vídeo contido), centrada na vertical
    casa = ("() => { const p = document.querySelector('.pl'), f = p.querySelector('iframe'); if (!f) return false;"
            " const r = f.getBoundingClientRect(), b = p.getBoundingClientRect();"
            " return Math.abs(r.width - p.clientWidth) < 2 && Math.abs((r.top - b.top - p.clientTop) - (p.clientHeight - r.height) / 2) < 2; }")
    with sync_playwright() as pw:
        try:
            nav = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        except Exception as e:  # noqa: BLE001
            return print(f"pulou: sem Chromium ({str(e)[:60]})")
        try:
            pag = nav.new_page(viewport={"width": 1440, "height": 900})
            pag.goto(grande.as_uri())
            larg = pag.evaluate("document.querySelector('.pl').getBoundingClientRect().width")
            assert 1100 <= larg <= 1200, f"o vídeo tem {larg:.0f} px numa tela de notebook"
            # a 0,1x o clipe não acaba (e a peça não sai) enquanto o teste mede
            pag.evaluate("() => { const v = document.querySelector('.pl video'); v.muted = true; v.playbackRate = 0.1; v.play(); }")
            pag.wait_for_selector(".pl iframe", timeout=5000)
            assert pag.evaluate(casa), "a peça não cobre o vídeo"
            pag.set_viewport_size({"width": 1000, "height": 800})
            pag.wait_for_function(casa, timeout=3000)
            assert pag.evaluate("document.querySelector('.pl').clientWidth") < larg - 100, "o vídeo não acompanhou a janela"
            pag.click(".fs")
            try:
                pag.wait_for_function("document.fullscreenElement && document.fullscreenElement.classList.contains('pl')", timeout=3000)
            except Exception:  # noqa: BLE001  (navegador sem janela que não entra em tela cheia)
                return print("pulou a tela cheia: o navegador não entrou")
            pag.wait_for_function(casa, timeout=3000)
            assert pag.locator(".pl iframe").count() == 1, "a peça tem que ir junto na tela cheia"
        finally:
            nav.close()


def _fala_de_teste() -> tuple[list[dict], float]:
    """Uma fala de 44 s com os gatilhos de cada peça: comando, enumeração, métrica, venda, duração, sigla e a chamada final."""
    frases = ("Eu criei esse CRM só usando o Claude Code sem escrever código nenhum. Esse trabalho levaria meses no passado e precisaria "
              "de uma equipe completa. Eles iam ter que modelar os dados, fazer a integração com o Meta, fazer a integração com o "
              "pagamento, iam precisar testar, iam precisar fazer o deploy. Mas eu só precisei editar um comando e o Claude me entrevistou "
              "para entender toda a minha operação e gerar um CRM que me atendesse. Agora eu sei o meu faturamento, eu sei o ticket médio, "
              "eu recebo notificação quando sai venda, igual essa plataforma que você está pensando. Tem relatório de criativo e todas as "
              "métricas que eu preciso pra saber se eu vou escalar o meu negócio. E levou menos de uma hora pra fazer isso. "
              "Comenta Claude aqui embaixo que eu te mando o treinamento completo pra você aplicar da mesma forma").split()
    t, ws = 0.1, []
    for w in frases:
        ws.append({"text": w, "start": round(t, 2), "end": round(t + 0.26, 2)})
        t += 0.3
    return ws, round(t, 2)


def test_pecas_da_fala_cobrem_a_densidade_sem_casca_e_sem_tapar_o_gancho():
    import checks
    import movimento
    import propoe
    ws, dur = _fala_de_teste()
    cobre = lambda ps: sum(p["dur"] for p in ps) / dur
    ps = propoe.pecas_da_fala(ws, dur, "media")
    assert len(ps) >= 2.0 * dur / 10, f"a densidade média pede 2 a 3 peças por 10 s, veio {len(ps)} em {dur:.0f} s"
    assert cobre(ps) >= 0.6, f"cobertura {cobre(ps):.0%}, a média pede ~80%"
    assert {p["peca"] for p in ps} >= {"i_terminal", "d_linha", "t_lista_cel", "r_notif", "g_comenta"}, "a fala tem o gatilho de cada uma"
    assert all(p["em"] >= propoe.ABERTURA for p in ps), "os 3 primeiros segundos são do gancho escrito"
    assert not [p for p in ps if p["peca"] in checks.CASCA or p["peca"].startswith("k_contador_")], "casca de página"
    ev = sorted((p["em"], p["em"] + p["dur"]) for p in ps)
    assert all(b <= c for (_, b), (c, _) in zip(ev, ev[1:])), "peça sobre peça"
    assert all(p["em"] + p["dur"] <= dur + 1e-6 for p in ps)
    assert len(propoe.pecas_da_fala(ws, dur, "calma")) < len(ps) < len(propoe.pecas_da_fala(ws, dur, "intensa")) + 1
    # o aluno que tirou as peças, ou vetou uma, é obedecido
    assert propoe.pecas_da_fala(ws, dur, "media", {"efeitos": ["zoom"]}) == []
    assert "d_linha" not in {p["peca"] for p in propoe.pecas_da_fala(ws, dur, "media", {"vetos": ["d_linha"]})}
    # cada peça muda é coberta por um golpe, e a densidade do reel de câmera está no estilo
    assert all(p.get("som") for p in ps if p["peca"] == "k_palavra_gigante")
    import estilo as es
    assert es.estilo("reel-camera").eixos["desenho"]["densidade"] in movimento.ALVOS
    assert es.estilo("reel-camera").tem("pecas") and not es.estilo("reel-camera", recursos={"-": ["pecas"]}).tem("pecas")


def test_batida_longa_do_visual_ganha_movimento_dentro_dela():
    """O avatar da rodada 2 teve 6,6 s de dividida sem mudança: a batida mais longa que o vão parte-se em vãos de até 2 s (intensa)."""
    import checks
    import propoe
    ws, dur = _fala()
    cob = [(0.0, 2.6), (2.6, 9.2)]          # a 2ª batida tem 6,6 s
    plano, _ = propoe.propoe(ws, dur, {"densidade": "intensa"}, checks._cardapio(), cob)
    dentro = [p for p in plano["pecas"] if 2.6 < p["em"] < 9.2]
    assert len(dentro) >= 3 and all(p["peca"] == "k_palavra_gigante" for p in dentro), plano["pecas"]
    assert not any(2.6 < c["em"] < 9.2 for c in plano.get("camera", [])), "zoom dentro da dividida desalinha a pessoa"
    ev = [{"t0": p["em"], "t1": p["em"] + p["dur"]} for p in plano["pecas"]]
    marcas = sorted({2.6, 9.2, *(e["t0"] for e in ev if 2.6 <= e["t0"] <= 9.2)})
    assert max(y - x for x, y in zip(marcas, marcas[1:])) <= 2.0 + 1e-6, marcas
    # batida curta (<= vão) não ganha nada por dentro
    curto, _ = propoe.propoe(ws, dur, {"densidade": "intensa"}, checks._cardapio(), [(3.0, 4.8)])
    assert not [p for p in curto.get("pecas", []) if 3.0 < p["em"] < 4.8]


def test_carimbo_com_negacao_e_avisado_e_a_proposta_nao_a_usa():
    import checks
    import propoe
    r = checks.carimbo_sem_negacao({"pecas": [{"peca": "e_carimbo", "q": {"txt": "SEM EDITAR"}}]})
    assert r.ok is False and "SEM EDITAR" in r.mediu, r
    assert checks.carimbo_sem_negacao({"pecas": [{"peca": "k_palavra_gigante", "q": {"l": "não"}}]}).ok is False
    assert checks.carimbo_sem_negacao({"pecas": [{"peca": "e_carimbo", "q": {"txt": "SOZINHA"}}, {"peca": "g_gancho", "q": {"l": "sem editar"}}]}).ok
    assert any(x.id == "carimbo-sem-negacao" for x in checks.antes({"pecas": []}))
    texto = "Eu faço vídeo sem editar nada agora porque nunca mais perco tempo com isso, não preciso mais de editor nenhum, tudo roda sozinho"
    ws = [{"text": w, "start": round(0.1 + 0.4 * i, 2), "end": round(0.4 + 0.4 * i, 2)} for i, w in enumerate(texto.split())]
    for dens in ("intensa", "media"):
        plano, _ = propoe.propoe(ws, ws[-1]["end"], {"densidade": dens}, checks._cardapio())
        for p in plano.get("pecas", []):
            if p["peca"] in ("t_headline", "k_palavra_gigante"):
                assert not checks.NEGACAO & set(__import__("re").findall(r"\w+", p["q"]["l"].lower())), p


def test_video_de_8_s_ou_mais_sem_chamada_no_fim_e_avisado():
    import checks
    import movimento
    mov = {**movimento.PRIMEIRO_VIDEO, "densidade": "calma"}
    sem = [{"t0": 0.2, "t1": 2.8, "tipo": "pecas", "peca": "g_gancho"}, {"t0": 5.0, "t1": 6.0, "tipo": "pecas", "peca": "e_carimbo"}]
    r = {x.id: x for x in checks.ritmo(sem, 9.0, mov)}
    assert r["chamada-final"].ok is False and "pergunte ao aluno" in r["chamada-final"].mediu, r["chamada-final"]
    com = sem + [{"t0": 6.2, "t1": 8.8, "tipo": "pecas", "peca": "g_comenta"}]
    assert {x.id: x for x in checks.ritmo(com, 9.0, mov)}["chamada-final"].ok
    assert "chamada-final" not in {x.id for x in checks.ritmo(sem, 6.0, mov)}, "vídeo curto não exige"


def main() -> None:
    casos = [
        ("peça toca por cima do clipe (file://)", test_peca_toca_por_cima_do_clipe_no_navegador_por_file),
        ("texto colado: aplica o certo, lista o resto", test_texto_colado_aplica_o_certo_e_lista_so_o_que_o_agente_decide),
        ("só o item mudado refaz quadro e clipe", test_so_o_item_mudado_refaz_quadro_e_clipe_e_o_orfao_some),
        ("cartão da peça aponta pra peça certa", test_cartao_da_peca_aponta_pra_peca_certa_com_os_parametros_dela),
        ("revisão: um cartão e um clipe por item", test_revisao_tem_um_cartao_por_item_e_um_clipe_leve_de_cada),
        ("copiar revisão: texto pra colar no Claude", test_copiar_revisao_entrega_o_texto_pra_colar_no_claude),
        ("plano mínimo: nº, tempo e peça", test_plano_minimo_gera_linhas_com_numero_tempo_e_peca),
        ("tirar e trocar texto chegam no render", test_tirar_e_trocar_texto_chegam_no_que_o_render_desenha),
        ("nº inexistente diz os que existem", test_numero_que_nao_existe_diz_quais_existem),
        ("corte que mudou recusa", test_corte_que_mudou_recusa_o_render_e_o_storyboard_recomeca),
        ("peça que não fotografa vira aviso", test_peca_que_nao_fotografa_vira_aviso_no_quadro),
        ("sobreposição sinalizada", test_sobreposicao_de_peca_e_sinalizada_mas_legenda_nao),
        ("peça do plano vira linha numerada", test_peca_do_plano_vira_linha_numerada_no_tempo_da_fala),
        ("sem peça: aviso", test_plano_sem_peca_avisa_pra_propor_de_2_a_4),
        ("troca de texto vale pra peça", test_troca_de_texto_vale_pra_peca),
        ("render final desenha as peças", test_render_final_desenha_as_pecas_do_storyboard_e_o_rascunho_nao),
        ("blocos recusam --storyboard", test_storyboard_do_celular_recusa_plano_em_blocos),
        ("storyboard não queima a legenda", test_storyboard_nao_queima_a_legenda_e_o_final_queima),
        ("peça leva mudo e atras até o render", test_peca_leva_mudo_e_atras_do_plano_ate_o_render),
        ("câmera, sons, palavra atrás e fundo pelo plano", test_plano_com_camera_sons_palavra_atras_e_fundo_chega_no_render_sem_mexer_no_json),
        ("tirar zoom e som pelo número", test_tirar_zoom_e_som_pelo_numero_e_a_palavra_atras_aceita_troca_de_texto),
        ("ritmo: vão, peso 3, veto, casca, câmera", test_ritmo_mede_vao_peso_3_veto_casca_e_camera_sobre_palavra_atras),
        ("proposta automática cumpre a densidade", test_proposta_automatica_cumpre_a_densidade_e_so_usa_o_cardapio),
        ("proposta respeita veto e efeitos", test_proposta_respeita_veto_e_efeitos),
        ("pouca-variacao", test_pouca_variacao_avisa_quando_falta_troca_de_layout),
        ("storyboard sem plano propõe", test_storyboard_sem_plano_propoe_o_movimento_e_o_aluno_so_ajusta),
        ("sem-flash no storyboard", test_sem_flash_do_corte_aparece_no_storyboard_e_nao_no_render),
        ("peças da fala: densidade, sem casca, sem tapar o gancho", test_pecas_da_fala_cobrem_a_densidade_sem_casca_e_sem_tapar_o_gancho),
        ("--help imprime o uso e não quebra", test_help_imprime_o_uso),
        ("aviso de densidade no storyboard e no seco", test_aviso_de_densidade_aparece_no_storyboard_e_no_seco),        ("folha animada: tempo redondo e chamada queimada", test_folha_animada_tempo_redondo_e_chamada_fora_do_navegador),
        ("folha animada grande: peça segue o vídeo, tela cheia do contêiner", test_folha_animada_grande_peca_segue_o_video_e_tela_cheia_e_do_conteiner),
        ("aviso de densidade no storyboard e no seco", test_aviso_de_densidade_aparece_no_storyboard_e_no_seco),
        ("batida longa do visual ganha movimento", test_batida_longa_do_visual_ganha_movimento_dentro_dela),
        ("carimbo com negação", test_carimbo_com_negacao_e_avisado_e_a_proposta_nao_a_usa),
        ("chamada final obrigatória", test_video_de_8_s_ou_mais_sem_chamada_no_fim_e_avisado),
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
