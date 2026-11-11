"""O visual.json, a busca e o encaixe na cadeia (fase (b) do plano visual).

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_visual.py
    FABRICA_TESTE_REDE=1 tools/video-use/.venv/bin/python tools/video-use/helpers/test_visual.py   # + os 3 casos reais

Sem rede por padrão: a rede é trocada por dublês (print, logo e API do GitHub). O teste real (repositório do GitHub citado,
logo de marca, número de estrelas) só roda com FABRICA_TESTE_REDE=1 e pula sozinho se a rede falhar. O encaixe usa o
vídeo de teste do kit (pula sem o clone do kit).
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import urllib.parse
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import acha  # noqa: E402
import fabrica as fb  # noqa: E402
import ff  # noqa: E402
import propoe  # noqa: E402
import storyboard as sb  # noqa: E402
import tela_dividida as td  # noqa: E402
import visual  # noqa: E402

KIT = Path.home() / "fabrica-kit" / ".github" / "fixtures" / "primeiro-video" / "meu-primeiro-video.mp4"
ALT = lambda lay="dividida", t="Frase da alternativa": {"tipo": "texto", "layout": lay, "texto": t}


def _doc(*bs: dict, dens: str = "media") -> dict:
    return {"versao": 1, "densidade": dens, "batidas": list(bs)}


def _b(i: int, t0: float, t1: float, lay: str = "dividida", **k) -> dict:
    b = {"id": i, "t0": t0, "t1": t1, "prova": f"prova {i}", "tipo": "print", "layout": lay,
         "fonte": {"origem": "url", "url": "https://exemplo.com", "frase": "x"}, "alternativa": ALT(lay)}
    return {**b, **k}


def _tem(erros: list[str], trecho: str) -> bool:
    return any(trecho in e for e in erros)


# ───────────── a validação ─────────────
def _fim(i: int, t0: float, t1: float) -> dict:
    """A última batida de um vídeo de 8 s ou mais: o rosto da chamada final."""
    return _b(i, t0, t1, "rosto", tipo="texto", fonte=None, alternativa=None, texto="Comenta *TV*", porque="chamada final")


def test_visual_valido_passa():
    d = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia"), _fim(3, 6, 9))
    assert visual.valida(d, 9) == []


def test_validacao_recusa_cada_regra_da_spec():
    base = [_b(1, 0, 3), _b(2, 3, 6, "cheia"), _b(3, 6, 9)]
    d = _doc(*copy.deepcopy(base))
    d["batidas"][1].pop("alternativa")
    assert _tem(visual.valida(d), "a alternativa é obrigatória")
    d = _doc(*[_b(i, 3 * i - 3, 3 * i, "cheia") for i in (1, 2, 3)])
    assert _tem(visual.valida(d), "3 `cheia` seguidas")
    d = _doc(*[_b(i, 3 * i - 3, 3 * i, "dividida") for i in (1, 2, 3)])
    assert _tem(visual.valida(d), "3 `dividida` seguidas")
    d = _doc(_b(1, 0, 4, "cheia"), _b(2, 4, 8, "cheia"), dens="calma")
    assert _tem(visual.valida(d), "dois `cheia` seguidos somam")
    d = _doc(_b(1, 0, 3, tipo="numero", fonte={"origem": "numero", "valor": "50"}))
    assert _tem(visual.valida(d), "número sem fonte")
    d["batidas"][0]["fonte"]["de"] = "fala"
    assert visual.valida(d) == []
    d = _doc(_b(1, 0, 3, tipo="video"))
    assert _tem(visual.valida(d), "tipo “video” não existe")
    d = _doc(_b(1, 0, 3, layout="metade"))
    assert _tem(visual.valida(d), "layout “metade” não existe")
    d = _doc(_b(1, 0, 3, prova=" "))
    assert _tem(visual.valida(d), "`prova` em branco")
    d = _doc(_b(1, 0, 3, tipo="texto", fonte=None))
    assert _tem(visual.valida(d), "só entra com `porque`")
    d = _doc(_b(1, 0, 5))
    assert _tem(visual.valida(d), "passa do vão"), "5 s na média pede `muda`"
    d["batidas"][0]["muda"] = "a lista rola"
    assert visual.valida(d) == []
    d = _doc(_b(1, 0, 3), _b(2, 2, 5, "cheia"))
    assert _tem(visual.valida(d), "antes de a 1 acabar")
    d = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia"))
    assert _tem(visual.valida(d, 20), "cobertura"), "6 s de prova em 20 s"
    d = _doc(_b(1, 0, 3, fonte={"origem": "url"}))
    assert _tem(visual.valida(d), "precisa de `url`")
    assert visual.valida({"versao": 2}) == ["versao: tem que ser 1"]


def test_ancora_na_palavra_dita():
    ws = [{"text": "Tem", "start": 0.0}, {"text": "gente.", "start": 0.4}, {"text": "gente", "start": 2.0}]
    d = _doc(_b(1, {"palavra": "Tem"}, {"palavra": "gente", "n": 2}))
    r = visual.ancora(d, ws)
    assert (r["batidas"][0]["t0"], r["batidas"][0]["t1"]) == (0.0, 2.0)
    assert isinstance(d["batidas"][0]["t0"], dict), "não mexe na entrada"
    try:
        visual.ancora(_doc(_b(1, {"palavra": "xis"}, 3)), ws)
    except ValueError as e:
        assert "xis" in str(e)
    else:
        raise AssertionError("palavra que não existe devia estourar")


# ───────────── a busca, com a rede trocada por dublês ─────────────
def _png(p: Path, w: int = 2000, h: int = 2200) -> Path:
    im = Image.new("RGB", (w, h), (240, 240, 240))
    im.paste(Image.new("RGB", (400, 60), (30, 30, 30)), (200, 600))      # a "frase"
    im.save(p)
    return p


class dubla:
    """Troca atributos do `acha` por dublês e devolve no fim (sem pytest)."""
    def __init__(self, **k): self.k, self.old = k, {}
    def __enter__(self):
        for n, v in self.k.items():
            self.old[n] = getattr(acha, n); setattr(acha, n, v)
    def __exit__(self, *a):
        for n, v in self.old.items(): setattr(acha, n, v)


def _falha(*a, **k):
    raise ConnectionError("sem rede")


def test_formata_milhar_arredonda_pra_baixo():
    assert acha.formata_milhar(50284) == ("50", "mil")
    assert acha.formata_milhar(51999) == ("51", "mil")
    assert acha.formata_milhar(1450) == ("1,4", "mil")
    assert acha.formata_milhar(420) == ("420", "")


def test_numero_vem_da_api_e_sem_ela_fica_o_dito():
    f = {"origem": "numero", "valor": "50", "sufixo": "mil", "rotulo": "estrelas", "github_repo": "a/b"}
    with dubla(estrelas_do_github=lambda r: 50284):
        n = acha.numero_de(f)
    assert (n["num"], n["suf"], n["rot"]) == ("50", "mil", "estrelas") and "a/b" in n["de"]
    with dubla(estrelas_do_github=_falha):
        n = acha.numero_de(f)
    assert (n["num"], n["suf"], n["de"]) == ("50", "mil", "fala")
    assert acha.numero_de({"valor": "400", "sufixo": "+"}) == {"num": "400", "suf": "+", "rot": "", "de": "fala"}


def test_print_logo_e_numero_resolvem(tmp: Path | None = None):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cru, logo = _png(d / "cru.png"), d / "logo.png"
        Image.new("RGBA", (1200, 1200), (11, 13, 18, 255)).save(logo)
        with dubla(print_de=lambda url, frase="", ancora="": (cru, [0.1, 0.27, 0.2, 0.03]), logo_de=lambda n, s="": logo,
                   estrelas_do_github=lambda r: 50284):
            p = acha.resolve(_b(1, 0, 3, fonte={"origem": "url", "url": "https://github.com/a/b", "frase": "x"}), d)
            assert p["status"] == "ok" and p["foco"] and Image.open(p["painel"]["img"]).size == (1840, 1460)
            amarelo = np.array(Image.open(p["painel"]["img"]).convert("RGB")).reshape(-1, 3)
            assert (np.abs(amarelo - np.array(acha.AMARELO)).sum(axis=1) < 40).sum() > 500, "a frase sai grifada"
            c = acha.resolve(_b(2, 3, 6, "cheia", fonte={"origem": "url", "url": "https://github.com/a/b", "frase": "x"}), d)
            assert c["painel"]["peca"] == "r_print" and c["painel"]["img"] == str(cru), "print em cheia é a peça, não a imagem crua"
            m = acha.resolve(_b(3, 6, 9, tipo="marca", fonte={"origem": "marca", "nome": "GitHub"}), d)
            assert m["status"] == "ok" and "Simple Icons (CC0)" in m["de"] and Image.open(m["painel"]["img"]).size == (1840, 1460)
            n = acha.resolve(_b(4, 9, 12, tipo="numero", fonte={"origem": "numero", "valor": "50", "sufixo": "mil", "github_repo": "a/b", "de": "API"}), d)
            assert n["status"] == "ok" and n["painel"] == {"num": "50", "suf": "mil"} and "img" not in n["painel"]


def test_o_que_falha_cai_na_alternativa_sem_travar():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        with dubla(print_de=_falha, logo_de=_falha, foto_livre=_falha):
            for b in (_b(1, 0, 3), _b(2, 3, 6, tipo="marca", fonte={"origem": "marca", "nome": "Xis"}),
                      _b(3, 6, 9, fonte={"origem": "busca_imagem", "consulta": "tv"})):
                r = acha.resolve(b, d)
                assert r["status"] == "alternativa" and r["painel"] == {"txt": "Frase da alternativa"} and "ConnectionError" in r["motivo"]
        # o tweet sem login: a frase entra como citação, com o @ da URL
        tw = _b(4, 9, 12, fonte={"origem": "url", "url": "https://x.com/gattin/status/1"})
        with dubla(print_de=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("embed fora"))):
            r = acha.resolve(tw, d)
        assert r["status"] == "alternativa" and r["painel"]["tag"] == "CITAÇÃO · @gattin"
        # login (Instagram): nem tenta a rede
        with dubla(_rede=_falha):
            r = acha.resolve(_b(5, 12, 15, fonte={"origem": "url", "url": "https://www.instagram.com/p/x/"}), d)
        assert r["status"] == "alternativa" and "login" in r["motivo"]
        # o que só o aluno tem: alternativa e a pergunta no motivo
        r = acha.resolve(_b(6, 15, 18, tipo="demo", fonte={"origem": "aluno", "pedido": "o terminal"}), d)
        assert r["status"] == "alternativa" and "o terminal" in r["motivo"]
        # o arquivo que o aluno mandou entra no painel
        arq = _png(d / "aluno.png", 1080, 1920)
        r = acha.resolve(_b(7, 18, 21, tipo="tela_aluno", fonte={"origem": "arquivo", "caminho": str(arq)}), d)
        assert r["status"] == "ok" and r["de"] == "arquivo do aluno"
        # rosto não busca nada
        assert acha.resolve(_b(8, 21, 24, "rosto", fonte=None), d)["status"] == "rosto"
        # o seco só lista, sem abrir nada
        with dubla(_rede=_falha, print_de=_falha):
            linhas = acha.seco(_doc(_b(1, 0, 3), _b(2, 3, 6, tipo="marca", fonte={"origem": "marca", "nome": "GitHub"})))
        assert len(linhas) == 2 and "Simple Icons" in linhas[1]


def test_licenca_da_foto_livre_recusa_sa_nc_nd():
    resp = {"query": {"pages": {str(i): {"index": i, "imageinfo": [{"mime": "image/jpeg", "thumburl": f"https://x/{i}.jpg",
            "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "<b>Ana</b>"}}}]}
            for i, lic in enumerate(["CC BY-SA 4.0", "CC BY-NC 2.0", "cc-by-sa-3.0", "CC BY 4.0"], 1)}}}
    with tempfile.TemporaryDirectory() as d:
        with dubla(_rede=lambda url, timeout=20: json.dumps(resp).encode() if "api.php" in url else b"jpg", CACHE=Path(d)):
            arq, credito = acha.foto_livre("tv")
    assert credito == "Ana / Wikimedia Commons (CC BY 4.0)", credito


def test_busca_real_nos_tres_casos_do_exemplo_ouro():
    """Lento e opcional: rede de verdade. O repositório citado (print com a frase grifada), um logo e as estrelas."""
    if not os.environ.get("FABRICA_TESTE_REDE"):
        print("pulou: FABRICA_TESTE_REDE=1 liga os 3 casos reais"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        repo = _b(1, 0, 3, fonte={"origem": "url", "url": "https://github.com/Gathin23/cleanyourtv", "frase": "Start here", "ancora": "Start here"})
        marca = _b(2, 3, 6, tipo="marca", fonte={"origem": "marca", "nome": "GitHub"})
        num = _b(3, 6, 9, tipo="numero", fonte={"origem": "numero", "valor": "50", "sufixo": "mil", "github_repo": "Gathin23/cleanyourtv"})
        r1, r2, r3 = (acha.resolve(b, d) for b in (repo, marca, num))
        if r1["status"] != "ok":
            print("pulou: sem rede pro GitHub:", r1["motivo"]); return
        assert r1["foco"] and 0 <= r1["foco"][0] <= 1 and 0 <= r1["foco"][1] <= 1, "região da frase dentro da imagem"
        assert r2["status"] == "ok" and r3["status"] == "ok" and int(r3["painel"]["num"]) >= 40 and "API" in r3["de"]


# ───────────── o encaixe ─────────────
def _plano(d: Path, doc: dict) -> dict:
    (d / "visual.json").write_text(json.dumps(doc), encoding="utf-8")
    return {"fonte": str(KIT), "slug": "t", "_dir": str(d), "trabalho": str(d / "_t"), "saida": str(d / "out")}


def test_a_cadeia_ganha_os_dois_passos_so_com_visual():
    if not KIT.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        sem = fb.fabrica({"fonte": str(KIT), "slug": "t", "trabalho": str(d / "_t"), "saida": str(d / "out")}, seco=True)
        assert not [p for p in sem.passos if p.nome in ("acha o visual", "tela dividida")]
        doc = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia", tipo="numero", fonte={"origem": "numero", "valor": "4", "de": "fala"}, alternativa=None))
        com = fb.fabrica(_plano(d, doc), seco=True)
        nomes = [p.nome for p in com.passos]
        assert nomes.index("acha o visual") + 1 == nomes.index("tela dividida") < nomes.index("legenda"), nomes
        # o visual.json que reprova recusa antes do primeiro comando
        doc["batidas"][0]["alternativa"] = None
        try:
            fb.fabrica(_plano(d, doc), seco=True)
        except ValueError as e:
            assert "a alternativa é obrigatória" in str(e)
        else:
            raise AssertionError("visual.json sem alternativa devia recusar")


def _frame(video: Path, t: float, png: Path) -> np.ndarray:
    ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1", "-vf", "scale=1080:1920,format=rgb24", png], quiet=True)
    return np.array(Image.open(png)).astype(int)


def test_o_video_final_tem_dividida_cheia_e_o_resto_como_estava():
    if not KIT.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        base = d / "base.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-t", "5", "-i", KIT, "-vf", "scale=1080:1920,fps=30", *ff.args_video("final"),
                *ff.args_audio(), base], quiet=True)
        with dubla():
            achados = [acha.resolve(b, d) | {"t0": b["t0"], "t1": b["t1"]} for b in (
                _b(1, 0.5, 2.0, tipo="numero", fonte={"origem": "numero", "valor": "50", "sufixo": "mil", "rotulo": "estrelas", "de": "fala"}),
                _b(2, 2.0, 3.5, "cheia", tipo="texto", texto="É só colar *um prompt*", porque="x", fonte=None))]
        saida = d / "saida.mp4"
        r = td.monta_visual(base, achados, saida, d / "t")
        assert r["partes"] == 4, r
        assert abs(ff.dur(saida) - ff.dur(base)) < 0.12, (ff.dur(saida), ff.dur(base))
        a, b = _frame(base, 1.0, d / "a.png"), _frame(saida, 1.0, d / "b.png")
        assert np.abs(a[250:900] - b[250:900]).mean() > 30, "dividida: o painel com o número está no lugar do take"
        assert b[600, 540].min() > 200 or b[300:900, 100:980].mean() > 180, "o painel é claro"
        assert np.abs(a[1500:1700] - b[1500:1700]).mean() > 5, "dividida: a pessoa foi recortada pra frente do cartão"
        g = _frame(saida, 2.8, d / "g.png")
        assert g[100:1700].mean() > 200, "cheia: o visual cobre a tela toda (papel claro com a frase)"
        z0, z1 = _frame(base, 4.4, d / "z0.png"), _frame(saida, 4.4, d / "z1.png")
        assert np.abs(z0 - z1).mean() < 6, "o trecho sem visual segue como estava"


def test_decisoes_tiram_a_batida_pelo_numero():
    """O que o dono tirou no storyboard não entra no render: o `--decisoes` filtra os achados."""
    doc = {"visual": [{"n": 1, "id": 1, "t0": 0.0, "t1": 2.0, "layout": "dividida", "tipo": "print", "prova": "p", "status": "ok", "de": "https://x", "motivo": ""},
                      {"n": 2, "id": 2, "t0": 2.0, "t1": 4.0, "layout": "cheia", "tipo": "marca", "prova": "q", "status": "alternativa", "de": "", "motivo": "ConnectionError"}]}
    ls = sb.linhas_decisoes(doc)
    assert [r["peca"] for r in ls] == ["visual · dividida", "visual · cheia"]
    assert "[ALTERNATIVA]" in ls[1]["conteudo"] and "[ALTERNATIVA]" not in ls[0]["conteudo"]
    assert [e["tipo"] for e in sb.eventos(doc)] == ["layout", "layout"]
    with tempfile.TemporaryDirectory() as d:
        arq = Path(d) / "decisoes.json"
        arq.write_text(json.dumps(doc), encoding="utf-8")
        sb.tira(arq, 2)
        assert [v["id"] for v in json.loads(arq.read_text(encoding="utf-8"))["visual"]] == [1]
        arq.write_text(json.dumps(doc), encoding="utf-8")
        try:
            sb.troca_texto(arq, 1, "novo")
        except ValueError as e:
            assert "não troca de texto" in str(e)
        else:
            raise AssertionError("o visual não troca de texto pelo número")


def test_propoe_nao_poe_nada_por_cima_do_visual():
    ws = [{"text": t, "start": 0.4 * i, "end": 0.4 * i + 0.35} for i, t in enumerate(
        "Esse vídeo mostra como automatizar processos pesados usando agentes poderosos sempre rápido durante trinta segundos inteiros hoje cedo".split())]
    dur = ws[-1]["end"]
    cob = [(0.0, 2.8), (3.0, 4.4)]
    plano, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "efeitos": ["zoom", "palavra_atras", "pecas", "sons"]}, (), cob)
    # a única peça que entra dentro da batida é a palavra gigante que parte uma batida mais longa que o vão (propoe.py); a batida 2 é curta
    itens = [(p["em"], p["em"] + p["dur"]) for k in ("pecas", "camera", "palavras_atras") for p in plano.get(k, [])
             if not (k == "pecas" and p["peca"] == "k_palavra_gigante" and p["em"] < 2.8)]
    assert all(b <= a2 + 1e-6 or a >= b2 - 1e-6 for a, b in itens for a2, b2 in cob), (itens, cob)
    assert not any(p["peca"] == "g_gancho" for p in plano.get("pecas", [])), "o gancho cairia dentro da batida 1"
    sem, _ = propoe.propoe(ws, dur, {"densidade": "intensa", "efeitos": ["zoom", "palavra_atras", "pecas", "sons"]})
    assert any(p["peca"] == "g_gancho" for p in sem.get("pecas", [])), "sem visual o gancho continua"


# ───────────── fase (c): a pauta pelo agente, o antes e depois, o print largo, a legenda acima do cabelo ─────────────
def _skill_do_kit() -> Path | None:
    for base in (AQUI.parents[2], AQUI.parents[2] / "kit-fabrica"):
        d = base / ".agents" / "skills" / "fabrica-de-conteudo"
        if (d / "SKILL.md").exists() and (d / "pauta-visual.md").exists():
            return d
    return None


def test_o_skill_manda_fazer_a_pauta_em_um_passo():
    d = _skill_do_kit()
    if not d:
        print("pulou: sem a skill do kit"); return
    skill, pauta = (d / "SKILL.md").read_text(encoding="utf-8"), (d / "pauta-visual.md").read_text(encoding="utf-8")
    for trecho in ("visual.json", "acha.py", "pauta-visual.md", "alternativa", "uma só", "transcript.py frases"):
        assert trecho in (skill + pauta), trecho
    # o exemplo-ouro da skill passa na validação (tempos trocados por segundos, 2 s cada)
    doc = json.loads(pauta.split("```json")[1].split("```")[0])
    for i, b in enumerate(doc["batidas"]):
        b["t0"], b["t1"] = 2.0 * i, 2.0 * i + (3.0 if i == len(doc["batidas"]) - 1 else 2.0)      # a última é a chamada: rosto de 2,8 s ou mais
    assert visual.valida(doc, 15.0) == [], visual.valida(doc, 15.0)


def test_par_e_terminal_desenhado_na_validacao():
    par = {"origem": "par", "antes": {"origem": "aluno", "pedido": "a"}, "depois": {"origem": "arquivo", "caminho": "x.png"}}
    ok = _doc(_b(1, 0, 2, tipo="antes_depois", fonte=par, layout="cheia"))
    assert visual.valida(ok, 2) == []
    par["depois"] = {"origem": "numero"}
    assert _tem(visual.valida(ok, 2), "o par precisa de `depois`")
    term = _doc(_b(1, 0, 2, tipo="demo", fonte={"origem": "peca", "peca": "terminal"}))
    assert _tem(visual.valida(term, 2), "não é de demonstração do kit")     # peça fora do kit não entra
    tela = _doc(_b(1, 0, 2, tipo="tela_aluno", fonte={"origem": "peca", "peca": "i_terminal", "q": {"cmd": "x"}}))
    assert _tem(visual.valida(tela, 2), "vem da tela do aluno")               # a tela do aluno é do aluno; a demonstração é `demo`/`animacao`


def _demo(i, t0, t1, lay="dividida", peca="i_tv", **q):
    return _b(i, t0, t1, lay, tipo="animacao", fonte={"origem": "peca", "peca": peca, "q": q or {"modo": "limpa"}}, alternativa=None, casa="mostra a ação dita")


def test_texto_demais_reprova_e_a_demonstracao_passa():
    """Mostrar, não dizer: mais de 1 painel de texto puro num vídeo de até 45 s reprova; a demonstração da biblioteca passa."""
    txt = lambda i, t0, t1, lay="dividida": _b(i, t0, t1, lay, tipo="texto", fonte=None, alternativa=None, texto="Frase", porque="não há prova")
    dois = _doc(txt(1, 0, 3), _demo(2, 3, 6, "cheia"), txt(3, 6, 9, "cheia"))
    assert _tem(visual.valida(dois, 9), "2 painéis de texto puro"), visual.valida(dois, 9)
    um = _doc(txt(1, 0, 3), _demo(2, 3, 6, "cheia"), _b(3, 6, 9), _b(4, 9, 12, "cheia"), _fim(5, 12, 15))
    assert visual.valida(um, 15) == [], visual.valida(um, 15)
    rosto = _doc(txt(1, 0, 3, "rosto"), txt(2, 3, 6, "rosto"), _demo(3, 6, 9))
    assert not _tem(visual.valida(rosto, 9), "painéis de texto"), "texto no rosto é gancho ou chamada, não painel"
    longo = _doc(*[txt(i, 3.0 * i, 3.0 * i + 3, "dividida" if i % 2 else "cheia") for i in range(2)], *[_demo(i, 3.0 * i, 3.0 * i + 3, "dividida" if i % 2 else "cheia") for i in range(2, 31)])
    assert not _tem(visual.valida(longo, 93), "painéis de texto"), "93 s: o teto sobe a 2"


def test_alternativa_pode_ser_demonstracao_e_a_peca_vira_painel():
    b = _b(1, 0, 3, fonte={"origem": "url", "url": "https://exemplo.com", "frase": "x"},
           alternativa={"tipo": "animacao", "layout": "dividida", "fonte": {"origem": "peca", "peca": "i_tv", "q": {"modo": "limpa"}}})
    assert visual.valida(_doc(b), 3) == []
    ruim = copy.deepcopy(b); ruim["alternativa"]["fonte"]["peca"] = "r_clone_do_dono"
    assert _tem(visual.valida(_doc(ruim), 3), "alternativa:")
    with tempfile.TemporaryDirectory() as d:
        r = acha.resolve(b, Path(d), rede=False)       # sem rede: cai na demonstração, não no texto
        assert r["status"] == "alternativa" and r["painel"]["peca"] == "i_tv" and "txt" not in r["painel"], r
        d2 = acha.resolve(_demo(2, 0, 3, peca="i_terminal", cmd='claude "x"', n=25), Path(d), rede=False)
        assert d2["status"] == "ok" and d2["painel"]["peca"] == "i_terminal"
        assert dict(__import__("urllib.parse").parse.parse_qsl(d2["painel"]["pq"])) == {"cmd": 'claude "x"', "n": "25"}


def _gh_falso(total=2350, criado="2026-10-17T08:00:00Z"):
    """O dublê da API do GitHub: o repositório e as páginas de stargazers (a n-ésima estrela do repositório é de `criado` + n*3 min)."""
    from datetime import datetime, timedelta
    chamadas = []

    def gh(url, accept="application/vnd.github+json"):
        chamadas.append((url, accept))
        if "/stargazers" in url:
            assert accept == "application/vnd.github.star+json", "o starred_at só vem com este Accept"
            pg = int(url.split("&page=")[1])
            ini = datetime.fromisoformat(criado.replace("Z", "+00:00")) + timedelta(minutes=3 * ((pg - 1) * 100))
            return [{"starred_at": (ini + timedelta(minutes=3 * k)).strftime("%Y-%m-%dT%H:%M:%SZ")} for k in range(100)], {}
        return {"stargazers_count": total, "created_at": criado}, {}
    return gh, chamadas


def test_historico_de_estrelas_com_a_api_dublada():
    """O gráfico de estrelas é histórico de verdade (amostra de páginas de stargazers), com poucas requisições e rótulo honesto."""
    gh, chamadas = _gh_falso()
    velho, acha._gh = acha._gh, gh
    old_sh, acha.historico_star_history = acha.historico_star_history, _falha      # o gráfico público fora: fica a lista de stargazers
    old_cache, acha.CACHE = acha.CACHE, Path(tempfile.mkdtemp())
    try:
        h = acha.historico_estrelas("a/b")
        assert h["requisicoes"] <= 17 and h["requisicoes"] == len(chamadas) and h["requisicoes"] < 60, h["requisicoes"]
        assert len(h["pts"]) == acha.PONTOS_DO_GRAFICO and h["pts"][-1] == 2350 and h["pts"][0] == 1
        assert h["pts"] == sorted(h["pts"]), "estrela só sobe"
        n = len(chamadas)
        acha.historico_estrelas("a/b")
        assert len(chamadas) - n == 1 + 1, "refazer só pergunta o total e a última página: o resto está no cache"
        p = acha.painel_estrelas("a/b")
        assert p["peca"] == "d_linha" and "estrelas+no+GitHub" in p["pq"] and "2.350" in urllib_unquote(p["pq"])
        r = acha.resolve({"id": 7, "t0": 0, "t1": 3, "tipo": "numero", "layout": "cheia", "prova": "x",
                          "fonte": {"origem": "numero", "valor": "2", "sufixo": "mil", "github_repo": "a/b", "de": "API"}}, Path(tempfile.mkdtemp()))
        assert r["status"] == "ok" and r["painel"]["peca"] == "d_linha" and "histórico" not in r["motivo"], r
    finally:
        acha._gh, acha.CACHE, acha.historico_star_history = velho, old_cache, old_sh


def urllib_unquote(s):
    import urllib.parse
    return urllib.parse.unquote_plus(s)


def test_sem_historico_o_numero_vira_contador():
    """A API de stargazers pede login (401): sem token o painel cai no contador subindo até o número, e diz isso no relatório."""
    def gh(url, accept="application/vnd.github+json"):
        if "/stargazers" in url:
            raise OSError("HTTP Error 401: Unauthorized")
        return {"stargazers_count": 51899, "created_at": "2026-10-17T00:00:00Z"}, {}
    velho, acha._gh = acha._gh, gh
    velho_rede, acha._rede = acha._rede, lambda u, timeout=20: json.dumps({"stargazers_count": 51899}).encode()
    old_sh, acha.historico_star_history = acha.historico_star_history, _falha
    try:
        r = acha.resolve({"id": 7, "t0": 0, "t1": 3, "tipo": "numero", "layout": "cheia", "prova": "x",
                          "fonte": {"origem": "numero", "valor": "50", "sufixo": "mil", "rotulo": "estrelas no GitHub", "github_repo": "a/b", "de": "API"}},
                         Path(tempfile.mkdtemp()))
        assert r["status"] == "ok" and r["painel"]["num"] == "51" and r["painel"]["suf"] == "mil" and "contador" in r["motivo"], r
        src = (AQUI.parents[1] / "v2" / "pecas" / "e_dividida.html").read_text(encoding="utf-8")
        assert "nmv" in src and "onUpdate" in src, "a e_dividida conta de 0 até o número"
    finally:
        acha._gh, acha._rede, acha.historico_star_history = velho, velho_rede, old_sh


def test_antes_depois_gera_as_duas_imagens():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        Image.new("RGB", (800, 600), (200, 20, 20)).save(d / "antes.png")
        Image.new("RGB", (800, 600), (20, 20, 200)).save(d / "depois.png")
        for lay, (W, H) in acha.PAINEL.items():
            r = acha.par_de(d / "antes.png", d / "depois.png", lay, d / f"{lay}.png")
            im = np.array(Image.open(r).convert("RGB")).astype(int)
            assert im.shape[:2] == (H, W)
            verm = (np.abs(im - [200, 20, 20]).sum(axis=2) < 30)
            azul = (np.abs(im - [20, 20, 200]).sum(axis=2) < 30)
            assert verm.sum() > 20000 and azul.sum() > 20000, lay
            yv, xv = np.nonzero(verm); ya, xa = np.nonzero(azul)
            # `dividida`: o antes à esquerda, o depois à direita; `cheia`: o antes em cima, o depois embaixo
            assert (xv.mean() < xa.mean()) if lay == "dividida" else (yv.mean() < ya.mean()), lay
        b = _b(1, 0, 3, tipo="antes_depois", fonte={"origem": "par", "antes": {"origem": "arquivo", "caminho": str(d / "antes.png")},
                                                      "depois": {"origem": "arquivo", "caminho": str(d / "depois.png")}})
        p = acha.resolve(b, d)
        assert p["status"] == "ok" and Image.open(p["painel"]["img"]).size == (1840, 1460), p


def test_foto_larga_empilha_o_antes_e_o_depois_na_dividida():
    """A TV em 16:9 lado a lado sobra papel em cima e embaixo; empilhada enche o painel: a disposição é a de maior imagem."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        Image.new("RGB", (1600, 900), (200, 20, 20)).save(d / "a.png")
        Image.new("RGB", (1600, 900), (20, 20, 200)).save(d / "b.png")
        im = np.array(Image.open(acha.par_de(d / "a.png", d / "b.png", "dividida", d / "p.png")).convert("RGB")).astype(int)
        yv, xv = np.nonzero(np.abs(im - [200, 20, 20]).sum(axis=2) < 30)
        ya, xa = np.nonzero(np.abs(im - [20, 20, 200]).sum(axis=2) < 30)
        assert yv.mean() < ya.mean() and abs(xv.mean() - xa.mean()) < 50, "o antes em cima, o depois embaixo"
        meio = (yv.max() + ya.min()) // 2      # entre as duas imagens: a seta é um desenho (a fonte da Pillow não tem ↓)
        W = im.shape[1]
        assert (im[meio - 30:meio + 30, W // 2 - 30:W // 2 + 30].sum(axis=2) < 120).sum() > 300, "a seta entre o antes e o depois"


def test_trocar_a_imagem_do_painel_com_o_mesmo_nome_refaz_o_render():
    """A imagem do painel vai pra peça como URI `file://`: ela entra na chave do cache pelo conteúdo (antes, o render velho voltava)."""
    sys.path.insert(0, str(AQUI.parents[1] / "v2"))
    import v2
    with tempfile.TemporaryDirectory() as d:
        img = Path(d) / "1 a.png"
        img.write_bytes(b"um")
        peca, _ = v2.acha("e_dividida")
        q = "dur=3&img=" + img.as_uri()
        k1 = v2.chave_render(peca, q, 30, True, False)
        img.write_bytes(b"dois")
        assert v2.chave_render(peca, q, 30, True, False) != k1


def test_nenhum_print_vai_cru_em_tela_cheia():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cru = _png(d / "cru.png")
        Image.new("RGB", (900, 1200), (250, 250, 250)).save(d / "aluno.png")
        with dubla(print_de=lambda url, frase="", ancora="": (cru, None)):
            for url in ("https://x.com/a/status/1", "https://github.com/a/b"):       # tweet (sem região) e página
                p = acha.resolve(_b(1, 0, 3, "cheia", fonte={"origem": "url", "url": url, "frase": ""}), d)
                assert p["status"] == "ok" and p["painel"]["peca"] == "r_print" and "foco" in p["painel"], p
            a = acha.resolve(_b(2, 0, 3, "cheia", tipo="demo", fonte={"origem": "arquivo", "caminho": str(d / "aluno.png")}), d)
            assert a["painel"]["peca"] == "r_print", "o print do aluno em cheia também vai pela peça"
        if not KIT.exists():
            print("pulou o render: sem o vídeo de teste do kit"); return
        base = d / "base.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-t", "4", "-i", KIT, "-vf", "scale=1080:1920,fps=30", *ff.args_video("final"),
                *ff.args_audio(), base], quiet=True)
        ach = [{"id": 1, "status": "ok", "layout": "cheia", "t0": 0.5, "t1": 3.5, "tipo": "print", "prova": "x",
                "painel": acha._painel_print(cru, None, "A página", "github.com")}]
        saida = d / "saida.mp4"
        td.monta_visual(base, ach, saida, d / "t")
        f = _frame(saida, 2.5, d / "f.png")
        barra = (np.abs(f.astype(int) - np.array(acha.AMARELO)).sum(axis=2) < 40).sum()
        assert barra > 20000, f"a moldura da peça (barra amarela da janela) está no quadro: {barra} px"


def test_imagem_larga_na_cheia_nao_corta_o_texto():
    """Foto e logo em cheia (o que não é print) cabem na largura, com margem."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        W, H = acha.PAINEL["cheia"]
        # um tweet: 1100x1488, com texto (barras pretas) encostando nas duas bordas
        im = Image.new("RGB", (1100, 1488), (255, 255, 255))
        for y in (100, 400, 900):
            im.paste(Image.new("RGB", (1100, 40), (0, 0, 0)), (0, y))
        im.save(d / "tw.png")
        a = np.array(Image.open(acha.compoe(d / "tw.png", "cheia", d / "o.png")).convert("L"))
        assert a.shape == (H, W)
        escuro = np.nonzero((a < 60).any(axis=0))[0]
        assert escuro.min() == 48 and escuro.max() == W - 49, (escuro.min(), escuro.max())      # a largura inteira, com margem
        # página alta (4000 px) com a frase no meio: rola só em altura, a largura segue inteira
        alta = Image.new("RGB", (1000, 4000), (255, 255, 255)); alta.paste(Image.new("RGB", (1000, 30), (0, 0, 0)), (0, 2000)); alta.save(d / "alta.png")
        b = np.array(Image.open(acha.compoe(d / "alta.png", "cheia", d / "p.png", [0.0, 0.5, 0.95, 0.01])).convert("L"))
        esc = np.nonzero((b < 60).any(axis=0))[0]
        assert b.shape == (H, W) and esc.min() == 48 and esc.max() == W - 49, (esc.min(), esc.max())
        assert (b < 60).any(), "a frase grifada/escura segue no recorte"


def test_a_pergunta_ao_aluno_e_uma_so_com_no_maximo_cinco():
    bs = [_b(i, 3 * i, 3 * i + 2 + i * 0.1, tipo="demo", layout="cheia" if i % 2 else "dividida",
             fonte={"origem": "aluno", "pedido": f"o terminal {i}"}) for i in range(7)]
    doc = _doc(*bs)
    ach = [{"id": b["id"], "status": "alternativa", "t0": b["t0"], "t1": b["t1"]} for b in bs]
    p = acha.pedidos_ao_aluno(doc, ach)
    assert len(p) == acha.MAX_PEDIDOS == 5 and "o terminal 6" in p[0] and all("Sem isso: texto" in x for x in p), p
    ach[0]["status"] = "ok"
    assert acha.pedidos_ao_aluno(doc, [a for a in ach if a["id"] == 0]) == []


def test_a_legenda_da_dividida_termina_acima_do_cabelo():
    import captions_viral as cv
    assert cv.LAYOUTS["dividida"]["zona"][1] * 1920 <= 1040 + 1e-6      # a regra do dono: y ~1040 em 1080x1920
    plano = {"dividida": [[2.0, 5.0]], "cards": [{"t0": 0.0, "t1": 1.0, "layout": "rodape"}, {"t0": 2.5, "t1": 3.5, "layout": "rodape"},
                                                {"t0": 6.0, "t1": 7.0, "layout": "rodape"}]}
    cv.aplicar_plano(plano)
    assert [c["layout"] for c in plano["cards"]] == ["rodape", "dividida", "rodape"], "só dentro da dividida; `cheia` e `rosto` seguem o estilo"
    if not KIT.exists():
        print("pulou a cadeia: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        doc = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia", tipo="numero", fonte={"origem": "numero", "valor": "4", "de": "fala"}, alternativa=None))
        leg = [p for p in fb.fabrica(_plano(d, doc), seco=True).passos if p.nome == "legenda"][0]
        assert "--dividida" in leg.cmd and leg.cmd[leg.cmd.index("--dividida") + 1].endswith("dividida.json"), leg.cmd


# ───────────── fase (e): a mídia real da fonte antes do desenho ─────────────
def _jpg_bytes(w=400, h=200, cor=(200, 30, 30)) -> bytes:
    import io
    b = io.BytesIO()
    Image.new("RGB", (w, h), cor).save(b, "JPEG")
    return b.getvalue()


def _rede_falsa(chamadas: list):
    """Dublê da rede: post do X com 1 foto, README com banner + selo + captura, site com og:image."""
    tweet = json.dumps({"photos": [{"url": "https://pbs.twimg.com/media/ABC.jpg"}]}).encode()
    readme = (b'<a><img src="https://img.shields.io/github/stars/a/b" alt="x"></a>\n<img src="docs/banner.png" width="800">\n'
              b'![captura](https://exemplo.com/captura.png)\n![](docs/x.svg)')
    html = b'<html><head><meta property="og:image" content="/capa.jpg?a=1&amp;b=2"></head></html>'

    def rede(url, timeout=20):
        chamadas.append(url)
        if "syndication.twimg.com" in url:
            return tweet if "id=111" in url else json.dumps({"photos": []}).encode()
        if url.endswith("README.md"):
            return readme
        if url.endswith((".jpg", ".png")) or "pbs.twimg.com" in url or ".jpg?" in url:
            return _jpg_bytes()
        return html
    return rede


def test_a_escada_pega_a_midia_da_fonte_antes_do_desenho():
    """(a) a mídia da fonte citada (foto do post, README, capa) vem antes da peça desenhada (d), que fica de alternativa."""
    chamadas: list = []
    old_cache, acha.CACHE = acha.CACHE, Path(tempfile.mkdtemp())
    try:
        with dubla(_rede=_rede_falsa(chamadas)):
            tw = "https://x.com/fulano/status/111"
            anim = {"tipo": "animacao", "layout": "dividida", "fonte": {"origem": "peca", "peca": "i_tv", "q": {"modo": "limpa"}}}
            # X: as fotos do post (o JSON público de sindicação), a maior resolução
            arq, de = acha.midia_de(tw)
            assert Image.open(arq).size == (400, 200) and "foto do post" in de
            assert any("tweet-result?id=111&token=a" in c for c in chamadas) and any(c.endswith("ABC.jpg?name=large") for c in chamadas)
            # README: pula selo e SVG, resolve o caminho relativo
            assert acha.imagens_do_readme("https://github.com/a/b") == ["https://raw.githubusercontent.com/a/b/HEAD/docs/banner.png", "https://exemplo.com/captura.png"]
            # capa: og:image, com o endereço relativo resolvido e o &amp; desfeito
            assert acha.imagem_de_capa("https://site.com/p") == ["https://site.com/capa.jpg?a=1&b=2"]
            # a batida com a mídia vira painel; antes e depois saem da MESMA foto, recortada
            par = {"id": 1, "t0": 0, "t1": 3, "tipo": "antes_depois", "layout": "dividida", "prova": "x", "alternativa": anim,
                   "fonte": {"origem": "par", "antes": {"origem": "midia", "url": tw, "recorte": [0, 0, .5, 1]},
                             "depois": {"origem": "midia", "url": tw, "recorte": [.5, 0, 1, 1]}}}
            r = acha.resolve(par, Path(tempfile.mkdtemp()))
            assert r["status"] == "ok" and r["painel"].get("img") and "foto do post" in r["de"], r
            r = acha.resolve({"id": 2, "t0": 0, "t1": 3, "tipo": "print", "layout": "dividida", "prova": "x", "alternativa": anim,
                              "fonte": {"origem": "midia", "url": "https://site.com/p"}}, Path(tempfile.mkdtemp()))
            assert r["status"] == "ok" and "capa" in r["de"] and r["painel"].get("img"), r
            # em tela cheia a imagem real nunca vai crua: é a peça r_print
            r = acha.resolve({"id": 3, "t0": 0, "t1": 3, "tipo": "print", "layout": "cheia", "prova": "x", "alternativa": {**anim, "layout": "cheia"},
                              "fonte": {"origem": "midia", "url": "https://github.com/a/b", "n": 1}}, Path(tempfile.mkdtemp()))
            assert r["status"] == "ok" and r["painel"]["peca"] == "r_print" and "README" in r["de"], r
            # sem a mídia (post sem foto) cai na demonstração desenhada, não em texto
            r = acha.resolve({**par, "fonte": {"origem": "midia", "url": "https://x.com/fulano/status/999"}}, Path(tempfile.mkdtemp()))
            assert r["status"] == "alternativa" and r["painel"]["peca"] == "i_tv", r
    finally:
        acha.CACHE = old_cache


def test_validacao_aceita_a_midia_e_pede_a_alternativa():
    anim = {"tipo": "animacao", "layout": "dividida", "fonte": {"origem": "peca", "peca": "i_tv", "q": {}}}
    ok = _b(1, 0, 3, tipo="print", fonte={"origem": "midia", "url": "https://x.com/a/status/1"}, alternativa=anim)
    assert visual.valida(_doc(ok), 3) == []
    sem = {k: v for k, v in ok.items() if k != "alternativa"}
    assert _tem(visual.valida(_doc(sem), 3), "alternativa é obrigatória")
    assert _tem(visual.valida(_doc({**ok, "fonte": {"origem": "midia"}}), 3), "precisa de `url`")


def test_foto_do_post_ja_citado_vence_o_desenho_da_mesma_coisa():
    """A escada vale entre batidas: com o post do X já citado, a TV mudando é a foto dele; o `i_tv` só na alternativa."""
    tw = "https://x.com/a/status/1"
    foto = _b(1, 0, 3, tipo="antes_depois", fonte={"origem": "par", "antes": {"origem": "midia", "url": tw}, "depois": {"origem": "midia", "url": tw}})
    tv = {"origem": "peca", "peca": "i_tv", "q": {"modo": "instala"}}
    desenho = _b(2, 3, 6, tipo="animacao", fonte=tv, alternativa=None)
    erros = visual.valida(_doc(foto, desenho), 6)
    assert _tem(erros, "batida 2: o vídeo já cita o post") and _tem(erros, "alternativa"), erros
    # a foto do mesmo post, com o desenho de alternativa: passa
    ok = _b(2, 3, 6, tipo="print", fonte={"origem": "midia", "url": tw, "recorte": [.5, 0, 1, 1]},
            alternativa={"tipo": "animacao", "layout": "dividida", "fonte": tv})
    assert visual.valida(_doc(foto, ok), 6) == []
    # sem post citado, o desenho segue sendo a prova; e o selo de compatibilidade nunca teve foto
    assert visual.valida(_doc(_b(1, 0, 3, tipo="animacao", fonte=tv, alternativa=None)), 3) == []
    compat = _b(2, 3, 6, tipo="animacao", fonte={"origem": "peca", "peca": "i_tv", "q": {"modo": "compat"}}, alternativa=None)
    assert visual.valida(_doc(foto, compat), 6) == []


def _svg_estrelas(y_ticks=((400, ""), (300, "10K"), (200, "20K")), x_ticks=((0, "Oct 25"), (600, "Sat 31"), (700, "November")),
                  caminho="M0 400L350 300L700 100") -> str:
    ys = "".join(f'<g class="tick"><path d="M0 {y}h-1"/><text x="-7" transform="translate(0 {y})">{t or " "}</text></g>' for y, t in y_ticks)
    xs = "".join(f'<text class="tick" y="6" transform="translate({x} 423.333)">{t}</text>' for x, t in x_ticks)
    return (f'<svg><g class="xaxis">{xs}</g><g class="yaxis">{ys}</g><text transform="translate(650 463.333)">star-history.com</text>'
            f'<path fill="none" stroke="#dd4528" d="{caminho}" class="xkcd-chart-xyline"/></svg>')


def test_parser_do_svg_do_star_history():
    from datetime import date
    r = acha.le_svg_estrelas(_svg_estrelas(), pontos=5, hoje=date(2026, 11, 4))
    # a curva sobe de 0 a 30 mil (y 400 -> 100, 100 px por 10 mil), com a data de cada ponto lida do eixo (7 dias em 700 px)
    assert r["pts"] == [0, 5000, 10000, 20000, 30000], r      # a reta quebra em x 350 (y 300 = 10 mil)
    assert r["datas"][0] == "2026-10-25" and r["datas"][-1] == "2026-11-01", r["datas"]
    # Bézier relativo (c e s) e o ano que vira (Dez -> Jan)
    curvo = "M0 400c100 0 200 -100 350 -100s250 -100 350 -200"
    r = acha.le_svg_estrelas(_svg_estrelas(x_ticks=((0, "Dec 30"), (350, "January"), (700, "Fri 03")), caminho=curvo),
                             pontos=4, hoje=date(2027, 1, 10))
    assert r["datas"][0] == "2026-12-30" and r["datas"][-1] == "2027-01-03" and r["pts"][-1] == 30000, r
    # SVG que não é o esperado estoura (o caller cai no contador)
    for ruim in ("<svg></svg>", _svg_estrelas(y_ticks=((400, ""),))):
        try:
            acha.le_svg_estrelas(ruim, hoje=date(2026, 11, 4))
        except ValueError:
            continue
        raise AssertionError("devia estourar")


def test_estrelas_pelo_star_history_viram_a_linha_que_sobe_a_batida_inteira():
    old_cache, acha.CACHE = acha.CACHE, Path(tempfile.mkdtemp())
    chamadas: list = []
    svg = _svg_estrelas().encode()
    try:
        with dubla(_rede=lambda u, timeout=20: (chamadas.append(u), svg)[1], estrelas_do_github=lambda repo: 30410):
            # as datas do mock são de 2026: o dia de hoje do teste não pode atrapalhar a leitura do ano
            import datetime as dt
            real = acha.le_svg_estrelas
            acha.le_svg_estrelas = lambda s, pontos=18, hoje=None: real(s, pontos, dt.date(2026, 11, 4))
            try:
                h = acha.historico_star_history("a/b", pontos=6)
                assert h["total"] == 30410 and h["pts"][-1] == 30410 and h["origem"] == "star-history" and h["requisicoes"] == 1
                p = acha.painel_estrelas("a/b")
                q = urllib_unquote(p["pq"])
                assert p["peca"] == "d_linha" and "estrelas no GitHub" in q and "dl=" not in q, q      # sem `dl`: a peça cresce a batida inteira
                assert "star-history.com" in p["de"]
                n = len(chamadas)
                acha.historico_star_history("a/b")
                assert len(chamadas) == n, "o SVG do dia fica em cache"
            finally:
                acha.le_svg_estrelas = real
        assert "star-history.com/svg?repos={repo}&type=Date" in acha.STAR_HISTORY
    finally:
        acha.CACHE = old_cache


def test_estrelas_reais_do_star_history_opcional():
    """Só com FABRICA_TESTE_REDE=1: o endpoint público devolve uma curva que sobe, com as datas lidas do eixo."""
    if not os.environ.get("FABRICA_TESTE_REDE"):
        print("pulou: sem FABRICA_TESTE_REDE=1"); return
    try:
        h = acha.historico_star_history("Gathin23/cleanyourtv")
    except OSError as e:
        print("pulou: sem rede", e); return
    assert h["pts"] == sorted(h["pts"]) and h["total"] > 10000 and h["datas"][0] < h["datas"][-1], h


def _mede_num(peca: str, q: dict, t: float, ar: str, cls: str) -> float | None:
    sys.path.insert(0, str(AQUI.parents[1] / "v2"))
    import re
    import v2
    r = v2.mede([(peca, q, ar)], t)[0]
    if "erro" in r:
        raise RuntimeError(r["erro"])
    for x in r["textos"]:
        if x.get("cls", "") == cls and re.search(r"\d", x["tx"]):
            return float(re.sub(r"[^\d]", "", x["tx"]))
    return None


def test_contador_dura_a_batida_inteira_nao_um_segundo():
    """Na metade de uma batida de 8 s o número ainda está subindo (nem no começo, nem já no valor), nas três peças com contador."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("pulou: sem playwright"); return
    casos = [("d_linha", {"pts": "100,400,900,2000,5000", "x": "a,b,c,d,e", "pre": "", "suf": "", "rot": "estrelas no GitHub", "dur": "8"}, "920x730", "vl"),
             ("d_grade", {"n": "400", "suf": "+", "rot": "modelos", "cel": "60", "dur": "8"}, "920x730", ""),
             ("e_dividida", {"peca": "", "num": "50", "suf": "mil", "rot": "x", "dur": "8", "seg": "0,8,dividida"}, "1080x1920", "nm")]
    for peca, q, ar, quer in casos:
        fim = {"d_linha": 5000, "d_grade": 400, "e_dividida": 50}[peca]
        meio = _mede_num(peca, q, 4.0, ar, quer)
        cedo = _mede_num(peca, q, 1.2, ar, quer)
        assert meio is not None and cedo is not None, (peca, meio, cedo)
        assert cedo < meio < fim, f"{peca}: o contador devia estar subindo na metade da batida (1,2 s: {cedo}, 4 s: {meio}, fim: {fim})"
    # a batida curta (3 s, a do número nas estrelas): na metade a linha ainda não chegou, e a peça acaba com o valor inteiro
    q = {"pts": "100,400,900,2000,5000", "x": "a,b,c,d,e", "pre": "", "suf": "", "rot": "estrelas no GitHub", "dur": "3"}
    meio, fim = _mede_num("d_linha", q, 1.65, "920x730", "vl"), _mede_num("d_linha", q, 2.95, "920x730", "vl")
    assert 1000 < meio < 4500 and fim == 5000, f"batida de 3 s: na metade {meio}, no fim {fim}"


def test_o_ponto_da_ponta_da_linha_nao_aparece_antes_da_hora():
    """A soma das retas passa de 1 por um fio e o sqrt da curva dava NaN: o último ponto estourava no 0 s (visto nos estilos Pop e Luxo)."""
    src = (AQUI.parents[1] / "v2" / "pecas" / "d_linha.html").read_text(encoding="utf-8")
    assert "inv(Math.min(1, Ls[i] / L))" in src


def test_a_legenda_da_cheia_fica_fora_da_caixa_da_peca():
    import captions_viral as cv

    def topo_e_pe(nome):
        lay = cv.LAYOUTS[nome]
        pe = lay["zona"][1] * 1920
        return pe - lay["h"], pe

    cards = lambda: [{"t0": 0.0, "t1": 1.0, "layout": None}, {"t0": 2.5, "t1": 3.5}, {"t0": 6.0, "t1": 7.0}]
    # a linha (caixa 430-1450): não cabe abaixo (o rodapé do Reels começa em 1470): legenda acima, sob a faixa do topo
    plano = {"dividida": [[2.0, 5.0, 430, 1450]], "cards": cards()}
    cv.aplicar_plano(plano)
    nome = plano["cards"][1]["layout"]
    assert nome.startswith("vao_") and not plano["cards"][0].get("layout") and not plano["cards"][2].get("layout"), "só dentro do trecho"
    topo, pe = topo_e_pe(nome)
    assert pe <= 430 and topo >= 250, (topo, pe)
    # a grade (caixa 300-1180): cabe abaixo
    plano = {"dividida": [[2.0, 5.0, 300, 1180]], "cards": cards()}
    cv.aplicar_plano(plano)
    topo, pe = topo_e_pe(plano["cards"][1]["layout"])
    assert topo >= 1180 and pe <= cv.PE_ABAIXO, (topo, pe)
    # a peça que ocupa a tela toda não deixa vão: a legenda fica onde o estilo põe
    plano = {"dividida": [[2.0, 5.0, 100, 1800]], "cards": cards()}
    cv.aplicar_plano(plano)
    assert plano["cards"][1].get("layout") is None
    # a dividida (2 números) segue como era, ao lado da cheia
    plano = {"dividida": [[0.0, 2.0], [2.0, 5.0, 430, 1450]], "cards": [{"t0": 0.5, "t1": 1.5}, {"t0": 2.5, "t1": 3.5}]}
    cv.aplicar_plano(plano)
    assert plano["cards"][0]["layout"] == "dividida" and plano["cards"][1]["layout"].startswith("vao_")
    assert "LAYOUTS" in cv._ESTADO, "o processo que desenha precisa do layout novo"


def test_a_caixa_da_peca_vem_do_navegador_e_o_erro_nao_derruba():
    class V2Falso:
        def __init__(self, r): self.r, self.visto = r, None
        def mede(self, pecas, t=None):
            self.visto = pecas
            if isinstance(self.r, Exception): raise self.r
            return self.r
    velho = td._v2
    try:
        v = V2Falso([{"caixa": {"x": 60, "y": 430, "w": 960, "h": 1020}}])
        td._v2 = lambda: v
        assert td.caixa_da_peca({"peca": "d_linha", "pq": "pts=1,2&rot=x"}) == (430.0, 1450.0)
        assert v.visto == [("d_linha", {"pts": "1,2", "rot": "x"}, "1080x1920")]
        td._v2 = lambda: V2Falso(RuntimeError("sem navegador"))
        assert td.caixa_da_peca({"peca": "d_linha", "pq": ""}) is None
        td._v2 = lambda: V2Falso([{"erro": "x"}])
        assert td.caixa_da_peca({"peca": "d_linha", "pq": ""}) is None
    finally:
        td._v2 = velho


def test_confianca_por_regra():
    c = lambda **k: (visual.confianca(_b(1, 0, 3, **k)) or ("",))[0]
    assert c(fonte={"origem": "midia", "url": "https://x.com/a/status/1"}) == "forte"
    assert c(fonte={"origem": "aluno", "pedido": "o terminal"}, tipo="tela_aluno") == "forte"
    assert c(tipo="marca", fonte={"origem": "marca", "nome": "Claude"}) == "fraca"          # logo solto não é prova
    assert c(tipo="texto", fonte=None) == "fraca"
    assert c(tipo="animacao", fonte={"origem": "peca", "peca": "i_terminal", "q": {"cmd": "x"}}) == "fraca"   # sem `casa`
    assert c(tipo="animacao", fonte={"origem": "peca", "peca": "i_terminal", "q": {"cmd": "x"}}, casa="o pedido dito") == "média"
    assert visual.confianca(_b(1, 0, 3, "rosto", tipo="texto", fonte=None)) is None


def test_fraca_sem_pergunta_reprova_e_pergunta_tem_ate_5():
    fraca = lambda i, t0, t1, **k: _b(i, t0, t1, "dividida" if i % 2 else "cheia", tipo="marca", fonte={"origem": "marca", "nome": "Claude"},
                                      alternativa={"tipo": "texto", "layout": "dividida", "texto": "No *Claude*"}, **k)
    forte = lambda i, t0, t1: _b(i, t0, t1, "dividida" if i % 2 else "cheia")
    dois = _doc(fraca(1, 0, 3), forte(2, 3, 6), fraca(3, 6, 9))
    assert _tem(visual.valida(dois, 9), "confiança fraca sem pergunta"), visual.valida(dois, 9)
    p = {"x": "o seu terminal", "demo": "o terminal com o pedido"}
    ok = _doc(fraca(1, 0, 3, pergunta=p), forte(2, 3, 6), fraca(3, 6, 9), _fim(4, 9, 12))
    assert visual.valida(ok, 12) == [], visual.valida(ok, 12)
    ruim = _doc(fraca(1, 0, 3, pergunta={"x": "só isto"}), forte(2, 3, 6))
    assert _tem(visual.valida(ruim, 6), "`pergunta` é")
    sete = [fraca(i, 3 * (i - 1), 3 * i, pergunta=p) for i in range(1, 8)]
    perg, sem = visual.fracas(sete)
    assert len(perg) == 5 and len(sem) == 2             # a pergunta única cabe 5; o resto conta como sem pergunta
    txt = visual.pergunta_da({**fraca(1, 12, 15, pergunta=p), "fala": "o agente edita"})
    assert "(0:12)" in txt and "1) um print/vídeo seu de o seu terminal" in txt and "4) deixa comigo" in txt
    t = _b(1, 0, 3, tipo="texto", fonte=None, alternativa=None, texto="x", porque="y", pergunta=p)
    assert _tem(visual.valida(_doc(t), 3), "não cai em texto")


def test_pergunta_unica_junta_as_fracas_com_ate_5_itens():
    p = {"x": "o seu terminal", "demo": "o terminal com o pedido"}
    bs = [_b(i, 3 * (i - 1), 3 * i, "dividida" if i % 2 else "cheia", tipo="marca", fonte={"origem": "marca", "nome": "Claude"},
             alternativa={"tipo": "texto", "layout": "dividida", "texto": "No *Claude*"}, pergunta=p, fala=f"frase {i}") for i in range(1, 8)]
    doc = _doc(*bs)
    ach = [{"id": b["id"], "status": "ok", "t0": b["t0"], "t1": b["t1"]} for b in bs]
    itens = acha.pedidos_ao_aluno(doc, ach)
    assert len(itens) == 5 and itens[0].startswith("No trecho “frase")


def test_animacao_termina_meio_segundo_antes_do_fim_da_batida():
    """Em toda batida de uma pauta de exemplo: fim da animação <= fim da batida - 0,5 s."""
    casos = [
        ("i_terminal", {"cmd": 'claude "desative os pacotes inúteis"@0.3', "n": "25", "nrot": "pacotes"}),
        ("i_terminal", {"cmd": 'claude "ache a minha TV no Wi-Fi"@0.3;claude "desative os pacotes inúteis"@1.8', "n": "25"}),
        ("d_grade", {"n": "400", "suf": "+"}), ("d_grade", {"n": "400", "dc": "2.2"}),
        ("d_linha", {"pts": "1,2,3"}), ("d_linha", {"pts": "1,2,3", "dl": "2.4"}),
        ("r_print", {}), ("i_tv", {"modo": "limpa"}),
    ]
    for dur in (3.0, 4.0, 6.5, 8.0):
        for peca, q in casos:
            if peca == "i_terminal" and dur < 6.5:
                continue        # o pedido digitado + 25 pacotes pedem ~6 s: abaixo disso o aviso é o certo (testado abaixo)
            novo, aviso = acha.encaixa_animacao({"peca": peca, "pq": urllib.parse.urlencode(q)}, dur)
            fim = acha.fim_da_animacao(novo, dur)
            assert aviso == "" and fim <= dur - 0.5 + 1e-6, (peca, q, dur, fim, aviso)
    # não cabe nem no limite: o storyboard recebe o aviso
    _, aviso = acha.encaixa_animacao({"peca": "d_linha", "pq": "pts=1,2"}, 1.5)
    assert "animação não termina" in aviso
    # o número da e_dividida sobe até 0,5 s antes do fim (conta de 0,6 no acha): uma batida comum não dispara o aviso
    novo, aviso = acha.encaixa_animacao({"num": "50", "suf": "mil", "rot": "x"}, 4.0)
    assert aviso == "" and acha.fim_da_animacao(novo, 4.0) <= 4.0 - 0.5 + 1e-6, aviso
    assert acha.fim_da_animacao({"img": "a.png"}, 4.0) is None       # imagem e texto não animam


def _term(i, t0, t1, lay="dividida", fala="", casa="o pedido que a fala conta", pergunta=None, **q):
    return _b(i, t0, t1, lay, tipo="animacao", fala=fala, casa=casa, muda="digita", **({"pergunta": pergunta} if pergunta else {}),
              fonte={"origem": "peca", "peca": "i_terminal", "q": q or {"cmd": 'claude "edita o vídeo"@0.3'}})


def test_variedade_mesmo_tipo_no_maximo_2_seguidas_e_40_por_cento():
    P = {"x": "o seu terminal", "demo": "o terminal"}
    cinco = _doc(*[_term(i, 3 * (i - 1), 3 * i, "dividida" if i % 2 else "cheia", pergunta=P) for i in range(1, 6)], dens="media")
    erros = visual.valida(cinco, 15)
    assert _tem(erros, "3 batidas seguidas de `i_terminal`"), erros
    assert _tem(erros, "`i_terminal` é 5 de 5"), erros
    # 2 seguidas e em 2 de 5 (40%) passa; um `rosto` entre elas quebra a sequência
    mix = [_term(1, 0, 3, pergunta=P), _term(2, 3, 6, "cheia", pergunta=P), _b(3, 6, 9),
           _b(4, 9, 12, "cheia", fonte={"origem": "midia", "url": "https://x.com/a/status/1"}),
           _b(5, 12, 15, tipo="tela_aluno", fonte={"origem": "aluno", "pedido": "a tela"})]
    assert not _tem(visual.valida(_doc(*mix), 15), "seguidas de"), visual.valida(_doc(*mix), 15)
    assert not _tem(visual.valida(_doc(*mix), 15), "o máximo por tipo")


def test_prova_baixa_obriga_a_pergunta_e_oferece_o_antes_depois_do_aluno():
    fracas = [_term(i, 3 * (i - 1), 3 * i, "dividida" if i % 2 else "cheia", casa="", cmd=f"claude {i}") for i in range(1, 4)]
    fracas[1]["fonte"]["peca"], fracas[2]["fonte"]["peca"] = "d_grade", "d_linha"        # variedade ok: o que falta é a pergunta
    for b in fracas:
        b["fonte"]["q"] = {"n": "5"}
    d = _doc(*copy.deepcopy(fracas))
    assert visual.baixa_prova(d["batidas"])
    assert _tem(visual.valida(d, 9), "a pergunta ao aluno é obrigatória"), visual.valida(d, 9)
    P = {"x": "um print seu", "demo": "a grade enchendo"}
    com = _doc(*[{**b, "pergunta": P, "fala": f"frase {i}"} for i, b in enumerate(copy.deepcopy(fracas), 1)])
    assert not _tem(visual.valida(com, 9), "obrigatória"), visual.valida(com, 9)
    itens = acha.pedidos_ao_aluno(com, [{"id": b["id"], "status": "ok", "t0": b["t0"], "t1": b["t1"]} for b in com["batidas"]])
    assert len(itens) == 3 and all("o antes×depois do seu próprio vídeo" in t for t in itens), itens
    # com prova forte em 30% ou mais, a pergunta volta a ser opcional
    forte = _doc(_b(1, 0, 3), fracas[1] | {"id": 2, "t0": 3, "t1": 6}, fracas[2] | {"id": 3, "t0": 6, "t1": 9})
    assert not visual.baixa_prova(forte["batidas"]) and not _tem(visual.valida(forte, 9), "obrigatória")


def test_casa_falsa_vira_fraca():
    # a fala é sobre o produto, a peça mostra outra coisa: a `casa` não vale
    falsa = _term(1, 0, 3, fala="a tua produção ainda tá parada esperando editor", cmd='claude "gera meu reel"@0.3')
    assert visual.confianca(falsa)[0] == "fraca" and "casa falsa" in visual.confianca(falsa)[1]
    falsa2 = _term(1, 0, 3, fala="vai pro ChatGPT que você já assina", rot="Claude Code", cmd='claude "corta e legenda"@0.2')
    assert visual.confianca(falsa2)[0] == "fraca"
    # a peça mostra a ação que a fala diz (o comando tem a palavra) e o número dito: média
    certa = _term(1, 0, 3, fala="desativou 25 pacotes inúteis da TV", cmd='claude "desative os pacotes inúteis"@0.3', n="25")
    assert visual.confianca(certa)[0] == "média"
    assert visual.confianca(_term(1, 0, 3))[0] == "média"      # sem `fala` não há com o que comparar


def test_video_de_8_s_ou_mais_termina_em_rosto_pra_chamada():
    sem = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia"), _b(3, 6, 9))
    assert _tem(visual.valida(sem, 9), "terminar em `rosto`"), visual.valida(sem, 9)
    com = _doc(_b(1, 0, 3), _b(2, 3, 6, "cheia"), _b(3, 6, 9, "rosto", tipo="texto", fonte=None, alternativa=None, texto="Comenta *TV*", porque="chamada"))
    assert not _tem(visual.valida(com, 9), "terminar em `rosto`"), visual.valida(com, 9)
    assert not _tem(visual.valida(sem, 6), "terminar em `rosto`"), "vídeo curto não exige"


def main():
    for nome, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)):
        fn()
        print("ok", nome)


if __name__ == "__main__":
    main()
