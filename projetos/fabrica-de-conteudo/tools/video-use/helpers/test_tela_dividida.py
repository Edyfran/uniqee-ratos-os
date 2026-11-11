"""A tela dividida do vídeo de celular (fase (a) do plano visual).

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_tela_dividida.py

Mede por pixel, como o LEIA-ME do tv-sem-anuncio: cabelo y 1064, queixo y 1686, borda do cartão y 1340,
legenda da `dividida` terminando em y 1040. O bruto é o vídeo de teste do kit
(~/fabrica-kit/.github/fixtures/primeiro-video/meu-primeiro-video.mp4, 720x1280: o recorte tem que subir pra 1080x1920);
sem o clone do kit o teste pula. A imagem do cartão é tools/v2/midia/exemplo-print.png. Sem rede.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ff  # noqa: E402
import recorte  # noqa: E402
import tela_dividida as td  # noqa: E402

BRUTO = Path.home() / "fabrica-kit" / ".github" / "fixtures" / "primeiro-video" / "meu-primeiro-video.mp4"
IMG = AQUI.parents[1] / "v2" / "midia" / "exemplo-print.png"
CARTAO_TOPO, LEGENDA_FIM = 1340, 1040


def quadro(video: Path, t: float, png: Path, filtro: str = "null") -> np.ndarray:
    ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1", "-vf", filtro, png], quiet=True)
    return np.array(Image.open(png))


def _alfa_png(video: Path, t: float, pasta: Path) -> Path:
    ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1", "-vf", "alphaextract",
            pasta / "a.png"], quiet=True)
    return pasta / "a.png"


def linhas(a: np.ndarray, minimo: float = 0.06) -> tuple[int, int]:
    """Primeira e última linha com pessoa de verdade (>= `minimo` da largura com alfa > 128)."""
    cheias = np.nonzero((a > 128).mean(axis=1) >= minimo)[0]
    return int(cheias[0]), int(cheias[-1])


def test_trechos_e_grafo():
    assert td.trechos("", 5) == [(0.0, 5.0, "dividida")]
    assert td.trechos("0,2,dividida;2,5,rosto", 5)[1] == (2.0, 5.0, "rosto")
    try:
        td.trechos("0,2,metade", 2)
    except ValueError as e:
        assert "metade" in str(e)
    else:
        raise AssertionError("layout desconhecido devia estourar")
    meta = {"largura": 1080, "altura": 1920, "fps": 25}
    enq = {"escala": 1.0, "x": 0, "y": 200}
    g = td.grafo(td.trechos("0,2,dividida;2,5,cheia", 5), enq, meta)
    assert "between(t,0.000,1.999)" in g and "2.000" not in g.split("enable=")[1].split("'")[1]   # a pessoa só nas dividida
    assert "alphamerge" in g and "framerate=fps=25" in g


def test_peca_nos_tres_layouts():
    v2 = td._v2()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for lay in td.LAYOUTS:
            pares = ["dur=2", f"lay={lay}", f"img={IMG.resolve().as_uri()}", "leg=Prova na tela"]
            cam = {}
            for c in ("tras", "frente"):
                cam[c] = d / f"{lay}.{c}.mov"
                v2.render("e_dividida", pares, cam[c], camada=c)
                cam[c].with_suffix(".json").unlink(missing_ok=True)
            tras = quadro(cam["tras"], 1.0, d / "t.png", "format=rgba")
            frente = quadro(cam["frente"], 1.0, d / "f.png", "format=rgba")
            if lay == "cartao":     # tem o teste dele (`test_peca_cartao_tem_o_vao_aberto`)
                continue
            if lay == "rosto":      # só o take: a camada de trás vazia
                assert tras[..., 3].max() == 0, "rosto: a camada tras devia ser transparente"
                assert frente[..., 3].max() == 0, "rosto: sem legenda de exemplo"
            elif lay == "cheia":    # o visual na tela toda
                assert (tras[..., 3] > 250).mean() > 0.99, "cheia: o visual devia cobrir o quadro"
                y0, y1 = linhas(frente[..., 3], 0.02)
                assert 1250 <= y0 and y1 <= 1500, f"cheia: legenda fora de 1250..1500: {y0}..{y1}"
            else:                   # painel em cima, cartão embaixo, legenda até 1040, nada no meio do rosto
                a = tras[..., 3] > 250
                assert a[400, 540] and a[1500, 540], "dividida: painel e cartão opacos"
                tinta = np.nonzero(tras[1000:, 540, :3].sum(axis=1) < 90)[0]   # a borda de tinta do cartão (x 540, de y 1000 pra baixo)
                assert abs(int(tinta[0]) + 1000 - CARTAO_TOPO) <= 8, f"borda do cartão em y 1340, achei {tinta[0] + 1000}"
                y0, y1 = linhas(frente[..., 3], 0.02)
                assert y1 <= LEGENDA_FIM, f"dividida: a legenda passou de 1040: {y1}"


def _pessoa(h=960, w=540, espinho=0, furo=False, largura=1.0):
    """Uma máscara sintética de pessoa: cabeça (elipse), pescoço e ombros. `espinho`: uma haste de fundo colada no topo do cabelo
    (a cadeira, o objeto da parede), em fração da largura da cabeça."""
    y, x = np.mgrid[0:h, 0:w]
    cab = ((x - w / 2) / (60 * largura)) ** 2 + ((y - 330) / 80) ** 2 <= 1
    om = (y > 540) & (abs(x - w / 2) < 200 * largura) & (y < h)
    m = cab | om | ((y > 380) & (abs(x - w / 2) < 30))
    if espinho:
        m |= (abs(x - w / 2) < 12) & (y > 330 - 80 - int(espinho * 120)) & (y < 330)
    if furo:
        m &= ~((abs(x - w / 2) < 60) & (abs(y - 650) < 60))
    return (m * 255).astype(np.uint8)


def test_qualidade_sintetica():
    """A trava mede a máscara sem referência: pessoa limpa passa; fundo colado no cabelo, furo, máscara que pisca, cabeça
    cortada e trecho sem pessoa não passam, cada um com o seu motivo."""
    boa = [_pessoa() for _ in range(10)]
    assert recorte.confere({"qualidade": recorte.mede_qualidade(boa)}) == (True, "")
    ruins = {"sobra fundo": [_pessoa(espinho=0.9) for _ in range(10)],
             "furos": [_pessoa(furo=True) for _ in range(10)],
             "pisca": [_pessoa(largura=1.0 if i % 2 else 0.6) for i in range(10)],
             "cortada": [np.roll(_pessoa(), -330, axis=0) for _ in range(10)],
             "não achou": [np.zeros((960, 540), np.uint8) for _ in range(10)]}
    for nome, ms in ruins.items():
        ok, motivo = recorte.confere({"qualidade": recorte.mede_qualidade(ms)})
        assert not ok and motivo, f"{nome}: devia reprovar"
        print(f"   {nome}: {motivo}")
    assert recorte.confere({})[0], "meta sem medida (cache velho) não reprova"


def test_peca_cartao_tem_o_vao_aberto():
    """O layout `cartao` da e_dividida: o painel em cima, o vão do cartão (x 80..1000, de y 1060 até o fim) transparente pra o
    vídeo da pessoa aparecer, e a borda de tinta no topo dele."""
    v2 = td._v2()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cam = d / "c.tras.mov"
        v2.render("e_dividida", ["dur=2", "lay=cartao", f"img={IMG.resolve().as_uri()}", "leg=Prova na tela"], cam, camada="tras")
        cam.with_suffix(".json").unlink(missing_ok=True)
        t = quadro(cam, 1.0, d / "t.png", "format=rgba")
        assert t[400, 540, 3] > 250, "o painel é opaco"
        assert t[1500, 540, 3] == 0 and t[1900, 200, 3] == 0, "o vão do cartão é transparente"
        assert t[1500, 20, 3] > 250 and t[1500, 1060, 3] > 250, "fora do cartão é o chão"
        tinta = np.nonzero((t[1000:1200, 540, :3].sum(axis=1) < 90) & (t[1000:1200, 540, 3] > 250))[0]
        assert len(tinta) and abs(int(tinta[0]) + 1000 - td.CARTAO_Y) <= 10, f"borda do cartão em y {td.CARTAO_Y}: {tinta[:3] + 1000}"
        # canto arredondado: o canto de cima à esquerda do vão é chão
        assert t[td.CARTAO_Y + 2, td.CARTAO_X + 2, 3] > 250, "o canto do vão é arredondado (ali ainda é chão)"


def test_numero_termina_meio_segundo_antes_do_fim():
    """O número do painel para de subir ao menos 0,5 s antes do fim da batida (a regra da pauta: o espectador vê o fim)."""
    v2 = td._v2()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cam = d / "n.tras.mov"
        v2.render("e_dividida", ["dur=4", "lay=dividida", "num=250", "suf=mil", "rot=seguidores"], cam, camada="tras")
        cam.with_suffix(".json").unlink(missing_ok=True)
        a = quadro(cam, 3.52, d / "a.png", "format=rgb24")[250:900, 100:980].astype(int)
        b = quadro(cam, 3.95, d / "b.png", "format=rgb24")[250:900, 100:980].astype(int)
        assert np.abs(a - b).mean() < 0.05, "o número ainda sobe depois de 3,5 s numa batida de 4 s"
        c = quadro(cam, 2.0, d / "c.png", "format=rgb24")[250:900, 100:980].astype(int)
        assert np.abs(a - c).mean() > 0.2, "o número devia estar subindo aos 2 s"


def _matte_falso(espinho=0):
    """O matte (os dois modelos) trocado por uma pessoa sintética: o teste da trava e do cache não paga o modelo."""
    def f(quadros):
        w, h = Image.open(quadros[0]).size          # o recorte roda em `recorte.LADO` (1080); a pessoa sintética é medida em 540x960
        m = np.array(Image.fromarray(_pessoa(espinho=espinho)).resize((w, h), Image.BILINEAR))
        return [m for _ in quadros]
    return f


def test_trava_mascara_ruim_cai_no_cartao_e_boa_recorta():
    if not BRUTO.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        real, cache = recorte._matte_do_trecho, recorte.cena.CACHE
        try:
            for nome, esp in (("boa", 0), ("ruim", 0.9)):
                recorte.cena.CACHE = d / f"cache_{nome}"       # o cache do recorte é pelo conteúdo do bruto: a máscara boa não pode servir à ruim
                recorte._matte_do_trecho = _matte_falso(esp)
                saida = io.StringIO()
                with contextlib.redirect_stdout(saida):
                    r = td.monta(BRUTO, 0, 1, IMG, d / f"{nome}.mp4", seg="0,1,dividida", leg="Prova", trab=d / nome)
                if nome == "boa":
                    assert r["layouts"] == ["dividida"] and not r["aviso"] and r["enquadra"], r["aviso"]
                    assert "recorte: fundo" not in saida.getvalue() and not r["pergunta"], "recorte bom não pergunta nada"
                else:
                    linhas_ = [l for l in saida.getvalue().splitlines() if l.startswith("recorte:")]
                    assert len(linhas_) == 1, linhas_
                    linha = linhas_[0]
                    assert linha.startswith("recorte: fundo poluído (tem algo colado na sua cabeça") and "0:00" in linha, linha
                    assert "pergunte ao aluno: 1) seguir com a pessoa no cartão" in linha and "2) regravar com fundo liso" in linha, linha
                    assert "Sem resposta: cartão" in linha and r["pergunta"] == linha, "sem resposta o layout já é o cartão"
                    assert r["layouts"] == ["cartao"] and r["aviso"].startswith(td.AVISO_CARTAO) and r["enquadra"] is None, r["layouts"]
                    f = quadro(d / "ruim.mp4", 0.5, d / "q.png", "format=rgb24")
                    # no vão do cartão está o vídeo (cheio de detalhe), e o painel de cima é o papel com o visual
                    assert f[1100:1900, 120:960].std() > 25, "o vídeo da pessoa está no cartão"
        finally:
            recorte._matte_do_trecho, recorte.cena.CACHE = real, cache


def test_cache_por_trecho_refaz_so_o_que_mudou():
    """Mudar uma batida refaz só o trecho dela: as outras partes (batidas e cortes) saem do `trechos/`, e a chave velha some."""
    if not BRUTO.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    def batida(i, t0, t1, txt, lay="dividida"):
        return {"id": i, "status": "ok", "layout": lay, "painel": {"txt": txt}, "t0": t0, "t1": t1}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        real, cache = recorte._matte_do_trecho, recorte.cena.CACHE
        recorte._matte_do_trecho, recorte.cena.CACHE = _matte_falso(), d / "cache"
        try:
            ach = [batida(1, 1.0, 3.0, "Primeira"), batida(2, 5.0, 7.0, "Segunda")]
            r1 = td.monta_visual(BRUTO, ach, d / "s.mp4", d / "t", "claro")
            assert r1["refeitas"] == r1["partes"] == 5, r1           # corte, batida, corte, batida, corte
            r2 = td.monta_visual(BRUTO, ach, d / "s.mp4", d / "t", "claro")
            assert r2["refeitas"] == 0, f"nada mudou, nada se refaz: {r2}"
            antes = {f.name for f in (d / "t" / "trechos").iterdir()}
            ach[1] = batida(2, 5.0, 7.0, "Segunda mudou")
            r3 = td.monta_visual(BRUTO, ach, d / "s.mp4", d / "t", "claro")
            assert r3["refeitas"] == 1, f"mudou 1 batida, refaz 1 trecho: {r3}"
            depois = {f.name for f in (d / "t" / "trechos").iterdir()}
            assert len(depois) == 5 and len(antes - depois) == 1 and len(depois - antes) == 1, "a chave velha da batida sai, a nova entra"
            assert abs(ff.dur(d / "s.mp4") - ff.dur(BRUTO)) < 0.3
            # a trava no vídeo todo: recorte ruim em uma batida = UMA linha `recorte:` pro agente e todas as batidas no cartão
            recorte._matte_do_trecho, recorte.cena.CACHE = _matte_falso(0.9), d / "cache4"      # o cache não vê o matte: cache novo
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                r4 = td.monta_visual(BRUTO, ach[:1], d / "s4.mp4", d / "t4", "claro")
            linhas_ = [l for l in saida.getvalue().splitlines() if l.startswith("recorte:")]
            assert len(linhas_) == 1 and linhas_[0] == r4["pergunta"] and "pergunte ao aluno" in linhas_[0], linhas_
            assert r4["avisos"] and "Sem resposta: cartão" in r4["pergunta"], "sem resposta, cartão"
        finally:
            recorte._matte_do_trecho, recorte.cena.CACHE = real, cache


def test_limpeza_do_recorte_sintetica():
    """O alfa macio do grande sai limpo: o que o fino não vê como gente cai (microfone ao lado), o furo pequeno fecha e o vão entre
    os dedos fica, o miolo é 1, a borda é macia, e a borda não treme entre quadros (o movimento de verdade não é apagado)."""
    from scipy import ndimage
    h, w = 480, 270
    y, x = np.mgrid[0:h, 0:w]
    pessoa = ((x - 135) ** 2 / 70 ** 2 + (y - 200) ** 2 / 130 ** 2 < 1)
    fino = ndimage.gaussian_filter(pessoa.astype(np.float32), 2)
    grande = fino.copy()
    mic = (abs(x - 235) < 14) & (abs(y - 250) < 50)            # objeto longe da pessoa que o grande confunde
    grande[mic] = 1.0
    grande[(abs(x - 120) < 5) & (abs(y - 180) < 5)] = 0.0      # furo pequeno dentro da pessoa
    grande[(abs(x - 160) < 25) & (abs(y - 260) < 25)] = 0.0    # vão grande (entre os dedos): fica aberto
    a = recorte._limpa(grande, fino)
    assert a[mic].max() == 0, "o microfone cai"
    assert a[(abs(x - 120) < 5) & (abs(y - 180) < 5)].min() == 1.0, "o furo pequeno fecha"
    assert a[(abs(x - 160) < 20) & (abs(y - 260) < 20)].max() < 0.5, "o vão entre os dedos fica aberto"
    assert (a[ndimage.binary_erosion(pessoa, iterations=6) & ~((abs(x - 160) < 28) & (abs(y - 260) < 28))] == 1.0).all(), "miolo sólido"
    assert 0 < ((a > 0.05) & (a < 0.95)).sum() < 0.1 * pessoa.sum(), "só a borda é macia"
    # a borda que balança 1 px de ruído fica quieta; o braço que se move 30 px de um quadro pro outro não é puxado de volta
    ruido = [np.clip(a + 0.3 * np.random.RandomState(i).randn(h, w) * ((a > 0) & (a < 1)), 0, 1).astype(np.float32) for i in range(5)]
    suave = recorte._suaviza(ruido)
    var = lambda m: np.mean([np.abs(m[i] - m[i - 1]).sum() for i in range(1, 5)])
    assert var(suave) < 0.8 * var(ruido), (var(suave), var(ruido))
    mov = [np.roll(a, 30 * (i % 2), axis=1) for i in range(5)]
    assert np.allclose(recorte._suaviza(mov)[2], mov[2], atol=0.26)


def test_quadro_do_meio_mistura_e_o_fantasma_da_mao_cai():
    """Entre dois quadros-chave o alfa é a mistura dos vizinhos mais o MODNet do próprio quadro onde ele tem certeza (a mão que se
    mexeu fica sólida); o fantasma da mão (metade do alfa onde ela já não está) cai na limpeza: só vale a até `PERTO` px do
    que o MODNet vê como gente."""
    h, w = 200, 200
    z = np.zeros((h, w), np.float32)
    ka, kb, f = z.copy(), z.copy(), z.copy()
    ka[60:140, 20:70] = 1
    kb[60:140, 60:110] = 1
    f[60:140, 40:90] = 1                                        # onde a mão está de fato
    m = recorte._entre(ka, kb, 0.5, f)
    assert abs(m[100, 25] - 0.5) < 1e-6 and abs(m[100, 105] - 0.5) < 1e-6 and m[100, 65] == 1.0, "a mistura dos vizinhos"
    assert m[100, 45] == 1.0 and m[100, 85] == 1.0, "onde o MODNet tem certeza e a mistura toca, a mão é sólida"
    assert recorte._entre(ka, kb, 0.5, np.ones((h, w), np.float32))[5, 5] == 0, "fora da mistura o MODNet não entra"
    a = recorte._limpa(m, f)
    assert a[100, 25] == 0 and a[100, 105] == 0, "o fantasma longe do fino cai"
    assert a[100, 50] == 1.0 and a[100, 80] == 1.0, "a mão onde está é sólida"


def test_prompt_do_sam_vem_do_rosto():
    """O prompt do SAM sai do rosto sem clique: a caixa da pessoa, 4 pontos de dentro e 3 de fora ACIMA da cabeça; cabeça perto do topo
    não põe ponto de fora no quadro (cairia em cima do cabelo)."""
    caixa, pts, lab = recorte._prompt((440.0, 700.0, 200.0, 240.0), 1080, 1920)
    assert lab == [1, 1, 1, 1, 0, 0, 0] and len(pts) == 7
    assert caixa[0] < 440 and caixa[2] > 640 and caixa[3] == 1920 and caixa[1] < 700, "a caixa pega a pessoa inteira"
    assert all(p[1] < 700 for p, l in zip(pts, lab) if l == 0), "os pontos de fora ficam acima do rosto"
    assert all(700 < p[1] for p, l in zip(pts, lab) if l == 1), "os de dentro ficam do rosto pra baixo"
    _, pts2, lab2 = recorte._prompt((440.0, 120.0, 200.0, 240.0), 1080, 1920)
    assert all(p[1] >= 2 for p in pts2) and lab2.count(0) < 3, "cabeça perto do topo: ponto de fora que sairia do quadro não entra"


def test_modelos_tem_hash_e_o_aviso_de_tamanho():
    """Todo modelo que o recorte baixa tem url fixa (revisão, não `main`) e hash; o SAM e o detector de rosto são os que o aviso da 1ª
    vez conta (181 MB), e nenhum peso pesado entra sem ficar na lista."""
    for nome, (url, sha) in recorte.MODELOS.items():
        assert url.startswith("https://") and len(sha) == 64 and int(sha, 16) >= 0, nome
        assert "/resolve/main/" not in url or nome == "modnet.onnx", f"{nome}: a url fixa a revisão"
    assert {"yunet.onnx", "sam2.1-tiny/vision_encoder.onnx", "sam2.1-tiny/memory_attention.onnx", "sam2.1-tiny/constants.json"} <= set(recorte.SAM_ARQUIVOS)
    assert all(n in recorte.MODELOS for n in recorte.SAM_ARQUIVOS)


def test_limite_do_sam_entre_quadros_e_rosto_que_falta():
    """O SAM roda nos quadros-chave (e no último); o quadro do meio fica com a união dos limites vizinhos (a mão que se mexeu entre
    dois cabe); o rosto que o detector não achou vem do quadro mais perto onde achou; sem rosto em nenhum quadro, sem limite."""
    h, w = 120, 60
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        qs = []
        for i in range(6):
            Image.new("RGB", (w, h)).save(d / f"{i}.png")
            qs.append(d / f"{i}.png")
        real = (recorte._rosto, recorte._FINO.get("s"), recorte.CHAVE, recorte.SAM_CADA, recorte.LIMITE)
        chamadas = []
        achou = {0: (10.0, 20.0, 10.0, 12.0), 2: None, 5: (30.0, 20.0, 10.0, 12.0)}
        seq = iter([0, 2, 5])

        def rosto(img):
            return achou[next(seq)]

        def sam(img, r, total=0, extra=None):
            chamadas.append(r)
            m = np.zeros((h, w), bool)
            m[40:100, int(r[0]):int(r[0]) + 10] = True
            return m
        recorte._rosto, recorte._FINO["s"], recorte.SAM_CADA, recorte.LIMITE = rosto, sam, 4, 0
        try:
            lims, rostos = recorte._limites(qs, [0, 4, 5])
            assert sorted(lims) == list(range(6)) and len(chamadas) == 3, "o SAM roda em 0, 4 e 5 só"
        finally:
            recorte._rosto, recorte._FINO["s"], recorte.SAM_CADA, recorte.LIMITE = real[0], real[1], real[3], real[4]
            if real[1] is None:
                recorte._FINO.pop("s", None)
    assert rostos[4] == achou[5], "o rosto que falta vem do quadro mais perto (o 5), não do 0"


def test_trilha_do_sam_monta_a_memoria_no_tamanho_do_modelo():
    """A trilha do SAM em vídeo alimenta a atenção com 7 blocos de 4096 quadros de memória + 16 ponteiros do objeto em 4 pedaços
    (28736 entradas), com o rosto só no 1º quadro, e pede o rosto de novo quando a pontuação do objeto cai a 0 ou menos. Sessões falsas."""
    class Sess:
        def __init__(self, f):
            self.f = f

        def run(self, _, feed):
            return self.f(feed)
    visto = {"att": [], "dec": [], "ptr": []}
    escore = [5.0]

    def enc(feed):
        return [np.zeros((1, 32, 256, 256), np.float32), np.zeros((1, 64, 128, 128), np.float32), np.zeros((1, 256, 64, 64), np.float32),
                np.zeros((1, 256, 64, 64), np.float32), np.zeros((1, 256, 64, 64), np.float32)]

    def dec(feed):
        visto["dec"].append(feed["input_points"].shape[2])
        low = np.full((1, 1, 256, 256), -5.0, np.float32)
        low[..., 60:200, 60:200] = 5.0
        return [low, np.zeros((1, 1, 1024, 1024), np.float32), np.zeros((1, 1), np.float32), np.full((1, 1, 1), escore[0], np.float32), np.zeros((1, 1, 256), np.float32)]

    def menc(feed):
        return [np.zeros((4096, 1, 64), np.float32), np.zeros((4096, 1, 64), np.float32)]

    def att(feed):
        visto["att"].append((feed["memory"].shape, feed["memory_pos"].shape))
        return [np.zeros((1, 256, 64, 64), np.float32)]

    def ptr(feed):
        visto["ptr"].append(feed["normalized_diffs"].shape)
        return [np.zeros((len(feed["normalized_diffs"]), 64), np.float32)]
    const = {"image_mean": [0.485, 0.456, 0.406], "image_std": [0.229, 0.224, 0.225], "memory_temporal_positional_encoding": np.zeros((7, 64)).tolist()}
    tr = recorte._Trilha({"enc": Sess(enc), "dec": Sess(dec), "menc": Sess(menc), "att": Sess(att), "ptr": Sess(ptr)}, const)
    img, rosto = np.zeros((192, 108, 3), np.uint8), (30.0, 40.0, 40.0, 50.0)
    for _ in range(3):
        m = tr(img, rosto, 3)
        assert m.shape == (192, 108) and m.dtype == bool and m[100, 50] and not m[5, 5]
    assert visto["dec"][0] > 4 and visto["dec"][1:] == [1, 1], "o prompt do rosto só no 1º quadro; depois o ponto de enchimento"
    assert all(a == ((28736, 1, 64), (28736, 1, 64)) for a in visto["att"]) and len(visto["att"]) == 2 and visto["ptr"] == [(16,)] * 2
    escore[0] = -3.0                                    # o SAM perdeu a pessoa: o rosto o prende de novo (prompt completo, memória nova)
    tr(img, rosto, 3)
    assert visto["dec"][-1] > 4 and tr.cond[3] == tr.i and not tr.recentes


def test_pontos_do_corpo_pegam_a_mao_ao_lado_do_rosto_e_nada_acima_da_testa():
    """Os pontos de dentro tirados do MODNet incluem o braço e a mão ao lado do rosto, longe um do outro, e nenhum acima da testa
    (onde o objeto da parede se confunde com o cabelo)."""
    h, w = 800, 600
    fino = np.zeros((h, w), np.uint8)
    fino[100:300, 200:360] = 255                # a cabeça
    fino[300:800, 100:500] = 255                # o corpo
    fino[350:520, 480:600] = 255                # a mão ao lado do rosto
    fino[20:90, 250:330] = 255                  # objeto colado acima do cabelo
    pts = recorte._pontos_do_corpo(fino, (230.0, 150.0, 100.0, 120.0), 4)
    assert len(pts) >= 2 and all(p[1] >= 150 + 0.6 * 120 for p in pts), pts
    assert any(p[0] > 480 for p in pts), "um ponto cai na mão"
    assert recorte._so_a_pessoa(np.pad(np.ones((100, 100), bool), 40), [[90, 90], [900, 900]]).sum() > 0


def test_excesso_fora_do_sam_na_zona_da_cabeca():
    """O objeto da cor do cabelo colado na cabeça (o recorte sem o SAM o leva) conta como excesso; o cabelo dentro do limite, não."""
    h, w = 400, 300
    rosto = (120.0, 150.0, 60.0, 70.0)
    fino = np.zeros((h, w), np.float32)
    fino[140:400, 100:200] = 1
    lim = np.zeros((h, w), bool)
    lim[140:400, 90:210] = True                 # o SAM: a pessoa do cabelo (140) pra baixo
    g = fino.copy()
    assert recorte._excesso(g, fino, lim, rosto) == 0.0, "pessoa limpa, sem excesso"
    g[110:140, 120:180] = 1                     # a mancha acima do cabelo, que o fino também vê (colada na cabeça)
    fino2 = fino.copy()
    fino2[110:140, 120:180] = 1
    assert recorte._excesso(g, fino2, lim, rosto) > recorte.EXCESSO_ZONA, "o objeto fora do limite passa da zona"


def test_trava_excesso_pergunta_com_o_segundo():
    """O excesso em muitos quadros-chave reprova com o motivo da cabeça e o segundo do pior quadro; poucos quadros ou pouco excesso passam."""
    base = {"quadros": 30, "sem_pessoa": 0.0, "ponta": 0.08, "buracos": 0.2, "salto": 0.02, "cortada": 0.0, "ini": 8.0, "taxa": 10, "onde": {}}
    ruim = {**base, "excesso": {"quadros": list(range(0, 28, 4)), "pct": [0.0, 5.0, 6.5, 0.0, 4.0, 0.0, 0.0]}}
    ok, motivo = recorte.confere({"qualidade": ruim})
    assert not ok and "colado na sua cabeça" in motivo and "(aos 0:08)" in motivo, motivo       # pior quadro: 8, aos 8,8 s
    assert recorte.confere({"qualidade": {**base, "excesso": {"quadros": [0, 4, 8, 12], "pct": [0.0, 0.5, 1.0, 2.9]}}})[0]
    assert recorte.confere({"qualidade": {**base, "excesso": {"quadros": [0, 4], "pct": [9.0, 9.0]}}})[0], "2 quadros-chave não bastam pra medir"
    assert recorte.confere({"qualidade": base})[0], "sem a medida do excesso (sem SAM) a trava não inventa defeito"


def test_recorte_tem_a_pessoa_e_o_detector_acha_o_queixo():
    if not BRUTO.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        meta = recorte.recorta_pessoa(BRUTO, 0, 1, d / "mascara.mov", usa_cache=False)
        assert recorte.FINO == "modnet" and recorte.GRANDE == "birefnet-general-lite" and recorte.TAXA == 10, "os modelos e a taxa medidos em 06/11 (docstring do recorte.py)"
        assert recorte.LIMITADOR == "sam2.1-hiera-tiny" and recorte.LADO == 1080, "o SAM dá o limite e a máscara tem a largura do quadro final"
        assert meta["quadros"] == 10 and meta["taxa_matte"] == 10 and meta["largura"] == 1080 and meta["altura"] == 1920
        # o bruto é 540x960 e o meta vem em pixels de 1080x1920. shortcut: a máscara do Majora na cabeça conta como cabelo
        # (a maior mancha a engole), então o cabelo mede ~615 e não ~720; o queixo real fica ~1430
        assert 560 <= meta["topo"] <= 760 and 1100 <= recorte.queixo(meta) <= 1500, (meta["topo"], recorte.queixo(meta))
        # o alfa já interpolado até o fps do take, em quadro da metade do trecho
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", BRUTO, "-i", meta["mascara"], "-filter_complex",
                recorte.grafo_alfa(0, 1, meta) + ";[p]alphaextract[x]", "-map", "[x]", "-frames:v", "13", d / "a%02d.png"], quiet=True)
        a = np.array(Image.open(d / "a13.png").convert("L"))
        topo, _ = linhas(a)
        assert abs(topo - meta["topo"]) <= 12, f"cabelo no alfa {topo}, no meta {meta['topo']:.0f}"
        assert a[1200, 500] > 250, "o rosto está dentro da máscara"
        assert a[500:1000, 900:1050].max() < 10, "o escudo na parede fica fora da máscara"
        assert a[800:1100, :100].max() < 10, "o quadro à esquerda fica fora"


def test_monta_dividida_e_cheia_no_pixel():
    if not BRUTO.exists():
        print("pulou: sem o vídeo de teste do kit"); return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        saida = d / "saida.mp4"
        seg = "0,0.6,dividida;0.6,1,cheia"
        # o Majora está colado no cabelo deste bruto: a trava (acertadamente) o manda pro cartão. Aqui o que se mede é a geometria da
        # dividida, então a trava fica de fora; ela tem o teste dela (`test_trava_mascara_ruim...`)
        confere, recorte.confere = recorte.confere, lambda meta: (True, "")
        try:
            r = td.monta(BRUTO, 0, 1, IMG, saida, seg=seg, leg="Prova na tela", trab=d / "trab")
        finally:
            recorte.confere = confere
        assert abs(ff.dur(saida) - 1.0) < 0.1
        enq, meta = r["enquadra"], r["meta"]
        topo = enq["y"] + meta["topo"] * enq["escala"]
        queixo = enq["y"] + recorte.queixo(meta) * enq["escala"]
        assert abs(topo - recorte.ALVO_TOPO) <= 8 and abs(queixo - recorte.ALVO_QUEIXO) <= 8, (topo, queixo)
        assert topo < CARTAO_TOPO - 200 < queixo, "a cabeça passa da borda de cima do cartão"
        # na saída, no pixel: cabelo escuro acima do cartão, papel claro acima do cabelo
        f = quadro(saida, 0.3, d / "q.png", "format=rgb24")
        lum = f.mean(axis=2)
        cx = int(enq["x"] + meta["cx"] * enq["escala"])
        assert lum[int(topo) - 10:int(topo) - 4, cx - 40:cx + 40].mean() > 150, "acima do cabelo é papel"
        assert lum[int(topo) + 30:int(topo) + 70, cx - 100:cx + 100].mean() < 140, "cabelo na frente, acima do cartão"
        assert np.abs(lum[1100:1330, cx - 150:cx + 150] - 232).mean() > 40, "a cabeça ocupa o espaço entre painel e cartão"
        # a legenda não cruza o rosto: termina antes do cabelo
        _, fim_leg = linhas(np.array(Image.open(_frame_alfa(r["camadas"]["frente"], 0.3, d))), 0.02)
        assert fim_leg < topo, f"legenda ({fim_leg}) cruza o cabelo ({topo:.0f})"
        # trecho `cheia`: o visual cobre tudo e a pessoa some
        g = quadro(saida, 0.8, d / "g.png", "format=rgb24")
        assert np.abs(g[1100:1700, 300:800].astype(int) - f[1100:1700, 300:800].astype(int)).mean() > 20, "na cheia a cabeça sai"


def _frame_alfa(video: str, t: float, pasta: Path) -> Path:
    return _alfa_png(Path(video), t, pasta)


def test_fundo_da_legenda_mede_o_branco_e_o_preto():
    """A luminância do vão da legenda numa parte `cheia`: papel branco ~1, fundo preto ~0 (a legenda escolhe a cor por ela)."""
    with tempfile.TemporaryDirectory() as td_:
        for cor, ok in (("white", lambda v: v > 0.95), ("black", lambda v: v < 0.03)):
            v = Path(td_) / f"{cor}.mp4"
            ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={cor}:s=1080x1920:r=10:d=1", "-pix_fmt", "yuv420p", v], quiet=True)
            m = td.fundo_da_legenda(v, (700.0, 1200.0))
            assert m is not None and ok(m), (cor, m)
        assert td.fundo_da_legenda(v, (300.0, 1600.0)) is not None      # sem vão pra legenda: mede onde o estilo a põe


def main():
    for nome, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)):
        fn()
        print("ok", nome)


if __name__ == "__main__":
    main()
