"""A legenda (captions_viral) confere consigo mesma: o que era o `--autoteste` dele.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_captions_viral.py

Morava no fim do captions_viral.py, e a impressão do passo de legenda lê o arquivo inteiro: mexer
num assert refazia toda legenda de todo vídeo. Aqui ele mexe só no teste.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402,F401

import ff  # noqa: E402
import camera  # noqa: E402
import captions_viral as cv  # noqa: E402
import cena  # noqa: E402

# Os nomes da legenda, como o autoteste os via de dentro do módulo. Os quatro que um plano muda
# (HOT, ENTRADA, STAGGER, SAIDA) são lidos e escritos pelo `cv.`: lidos daqui, ficariam no valor
# do import.
for _m in (camera, cena, cv):
    globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})


def test_a_legenda_confere_consigo_mesma():
    # mola: sai de 0, passa de 1 (overshoot) e assenta em 1
    assert abs(mola(0.0, 0.3)) < 1e-9 and mola(1.0, 0.3) == 1.0
    assert max(mola(p / 100, 0.5) for p in range(60)) > 1.0, "sem overshoot"
    assert abs(suave(0) ) < 1e-9 and abs(suave(1) - 1) < 1e-9

    c = finalizar([{"t0": 0.0, "t1": 1.0, "anim": "entra",
                    "words": [{"tx": "UM", "t0": 0.0, "t1": 0.4},
                              {"tx": "DOIS", "t0": 0.4, "t1": 0.9, "enf": "punch"}]},
                   {"t0": 1.5, "t1": 2.0, "words": [{"tx": "TRES", "t0": 1.5, "t1": 1.9}]}])
    # o primeiro card tem respiro depois -> saída animada; o último também
    assert c[0]["saida"] and c[1]["saida"]
    # stagger: no t=0 a segunda palavra ainda não entrou
    assert anim(c[0], 1, c[0]["words"][1], 0.0, 0.5)[1] == 0.0
    assert anim(c[0], 1, c[0]["words"][1], 0.30, 0.5)[1] > 0.0
    # entrada mexe nas três propriedades ao mesmo tempo
    e, al, dy = anim(c[0], 0, c[0]["words"][0], 0.05, 0.5)
    assert e < 1.0 and 0.0 < al < 1.0 and dy > 0.0
    # saída é mais rápida que a entrada e chega a alpha 0
    assert cv.SAIDA < cv.ENTRADA
    assert anim(c[0], 0, c[0]["words"][0], 1.0 - 1e-4, 0.5)[1] < 0.02
    # volume alto dá overshoot maior que volume baixo
    pico = lambda v: max(anim(c[0], 0, c[0]["words"][0], x / 200, v)[0] for x in range(60))
    assert pico(1.0) > pico(0.0), "amplitude não segue o volume"
    # punch respira depois de assentar
    r = [anim(c[0], 1, c[0]["words"][1], 0.55 + x / 60, 0.5)[0] for x in range(30)]
    assert max(r) - min(r) > 0.005, "punch não respira"
    # melhor_y foge do sujeito mesmo quando ele está PARADO (o caso do rosto
    # em plano fechado, que o mapa de movimento sozinho não pegava)
    suj = np.zeros((8, 100), dtype=np.float32); suj[:, 20:45] = 1.0
    mov = np.zeros((8, 100), dtype=np.float32); mov[:, 70:90] = 9.0
    y, ocup = melhor_y(suj, 4, mov, 4, 0.0, 2.0, (0.0, 1.0), 192, 1920)
    lin = y / 1920 * 100
    assert not (20 <= lin < 45), f"sentou no sujeito parado (linha {lin:.0f})"
    assert not (70 <= lin < 90), f"sentou no movimento (linha {lin:.0f})"
    assert ocup < 0.2, f"ocupação devolvida errada ({ocup})"
    # alpha da fonte: recorte que já veio pronto não pode ser refeito por modelo
    with tempfile.TemporaryDirectory() as _ta:
        _p = Path(_ta)
        op = Image.new("RGBA", (40, 40), (10, 20, 30, 255))
        op.save(_p / "opaco.png")
        assert alfa_do_arquivo(_p / "opaco.png") is None, \
            "PNG opaco com canal sobrando não é recorte"
        rec = Image.new("RGBA", (40, 40), (10, 20, 30, 0))
        rec.paste(Image.new("RGBA", (18, 18), (255, 0, 0, 255)), (8, 8))
        rec.save(_p / "recorte.png")
        got = alfa_do_arquivo(_p / "recorte.png")
        assert got is not None and got[16, 16] == 255 and got[2, 2] == 0, \
            "recorte de verdade tinha que ser aproveitado"
        Image.new("RGB", (40, 40), (9, 9, 9)).save(_p / "semcanal.png")
        assert alfa_do_arquivo(_p / "semcanal.png") is None, "RGB não tem alpha"

    # câmera: escala constante e zoom montam filtros diferentes, e zoom tem que
    # sair como perspective — scale+pad varia a dimensão por frame e o codec recusa,
    # e o zoompan arredonda a janela pro pixel (o zoom lento parava em degrau).
    # A fonte a 25 vai a 30 por mistura, não por cópia.
    import tempfile as _tc
    with _tc.TemporaryDirectory() as _tcd:
        _x = Path(_tcd) / "x.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=25:d=1",
                "-pix_fmt", ff.PIX_FMT, "-c:v", ff.CODEC_VIDEO, str(_x)], check=True)
        with ff.seco() as _gravado:
            camera_cenas(_x, [{"t0": 0.0, "t1": 1.0, "zoom": [1.0, 1.25]},
                              {"t0": 2.0, "t1": 3.0, "escala": 0.6, "dy": 0.2}],
                         4.0, 30, 1080, 1920, Path(_tcd))
    tudo = " || ".join(" ".join(str(c) for c in cmd) for cmd in _gravado)
    assert "perspective" in tudo and "zoompan" not in tudo, "cena com zoom não virou perspective"
    assert "scale=648:1152" in tudo, "cena com escala não virou scale+pad"
    assert tudo.count("perspective") == 1, "perspective vazou pras cenas sem zoom"
    assert tudo.count("fps=30") == tudo.count("framerate=fps=30") > 0, "a fonte a 25 foi a 30 por cópia"

    # tela dividida: a curva sai de 0, passa de 1 na mola, assenta, e sai
    # monotônica até ~0. A câmera nunca fica à frente da borda do painel.
    assert curva_da_janela({"abre": 0.43}) == (0.6, 0.43)
    assert curva_da_janela({"sobe": 0.3, "entra": 0.5}) == (0.5, 0.3)
    assert curva_tela(0.0, 5.0, 0.6, 0.45) == 0.0
    assert max(curva_tela(k / 300, 5.0, 0.6, 0.45) for k in range(180)) > 1.0
    assert curva_tela(2.0, 5.0, 0.6, 0.45) == 1.0
    saida = [curva_tela(5.0 - 0.45 + k / 100, 5.0, 0.6, 0.45) for k in range(46)]
    assert all(b <= a for a, b in zip(saida, saida[1:])) and saida[-1] < 1e-9
    for k in range(151):
        pk = curva_tela(k / 30, 5.0, 0.6, 0.45) if k < 18 else saida[min(45, k - 105)] if k >= 105 else 1.0
        assert desce_camera(pk, 768, 307, 120) <= 768 * pk + 1e-6, "câmera à frente do painel"

    # e renderiza: 2s com janela têm que COMPOR a câmera. A versão contínua
    # anterior saía com o quadro inteiro preto; quadro preto reprova aqui.
    with tempfile.TemporaryDirectory() as _tl:
        _d = Path(_tl)
        fonte_t = _d / "fonte.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "testsrc2=s=1080x1920:r=25:d=3", "-pix_fmt", ff.PIX_FMT,
                "-c:v", ff.CODEC_VIDEO, "-preset", "ultrafast", str(fonte_t)],
               check=True)
        cam = camera_cenas(fonte_t, [{"t0": 0.0, "t1": 2.0, "janela": [0.24, 0.6]}],
                           2.0, 30, 1080, 1920, _d)
        luma = ff.run(["ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(cam),
                       "-frames:v", "1", "-vf", "crop=iw:ih/2:0:ih/2",
                       "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                      capture=True, binario=True, quiet=True).stdout
        media = float(np.frombuffer(luma, np.uint8).mean()) if luma else 0.0
        assert media > 30, f"tela dividida saiu preta (luminância {media:.1f})"

        # tela dividida do editorial: o papel cobre o pé, menos o cartão de cantos redondos, onde o vídeo aparece
        cam = camera_cenas(fonte_t, [{"t0": 0.0, "t1": 1.0, "zoom": [1.0, 1.0], "ease": "reta", "desce": 0.34,
                                      "cartao": {"cor": "#FFFFFF"}}], 1.0, 30, 1080, 1920, _d)
        q = ff.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(cam), "-frames:v", "1", "-f", "rawvideo",
                    "-pix_fmt", "rgb24", "-"], capture=True, binario=True, quiet=True).stdout
        im = np.frombuffer(q, np.uint8).reshape(1920, 1080, 3)
        assert im[1260, 3].min() > 250, "a margem do cartão não é papel"
        assert im[1250, 20].min() > 250, "o canto redondo do cartão não é papel"
        assert (im[1700, 540].astype(int) != 255).any(), "o cartão não mostra o vídeo"

    # linha do ombro, no perfil REAL: curva do cabelo subindo, platô da cabeça,
    # depois o ombro. A rampa do cabelo é o que quebrava a medição.
    perfil = np.zeros((6, 100), dtype=np.float32)
    for i, y in enumerate(range(26, 32)):       # cabelo: 0.05 -> 0.35
        perfil[:, y] = 0.05 + i * 0.06
    perfil[:, 32:62] = 0.42                     # platô da cabeça
    perfil[:, 62:70] = 0.62                     # ombro entra
    perfil[:, 70:96] = 0.95                     # tronco
    y_omb = linha_do_ombro(perfil, 4, 0.0, 1.0, 1920) / 1920 * 100
    assert 58 <= y_omb <= 70, f"ombro em {y_omb:.0f}%, esperava entre 58 e 70"
    # sem sujeito reconhecível, não inventa: cai no meio
    assert linha_do_ombro(np.zeros((4, 100), np.float32), 4, 0, 1, 1920) == int(1920 * 0.55)

    # e reporta ocupação alta quando a zona inteira é sujeito
    _, ocup2 = melhor_y(suj, 4, mov, 4, 0.0, 2.0, (0.20, 0.45), 192, 1920)
    assert ocup2 > 0.55, f"não acusou zona tomada ({ocup2})"
    # fonte variável não pode cair na instância fina
    assert fonte("tiktok", 40).get_variation_names(), "tiktok sem eixos"

    # guarda de legibilidade do herói: silhueta cobrindo o meio da tela tem que
    # empurrar o texto pro lado em vez de deixar a palavra ser engolida
    # Resolução real e fonte FIXA: o teste é da lógica do guarda, não da escolha
    # de padrão nem de um quadro de brinquedo. Sem pinar a fonte, trocar
    # FONTE_PADRAO muda a largura do texto e quebra o caso por motivo errado.
    L, A = 1080, 1920
    h = dict(finalizar([{"t0": 0.0, "t1": 1.0, "layout": "centro", "atras": True,
                         "fonte": "black", "corpo": 52,
                         "words": [{"tx": "NENHUM", "t0": 0.0, "t1": 0.9,
                                    "enf": "punch"}]}])[0])
    h["_y"] = int(0.30 * A)
    def _cena(x0f, x1f):
        s = np.zeros((A, L), dtype=np.uint8)
        s[:, int(x0f * L):int(x1f * L)] = 255
        return s

    base, caixas = tinta(h, L, A)
    ys, xs = np.nonzero(base)
    assert len(caixas) == len("NENHUM"), f"caixa por letra errada ({len(caixas)})"

    # cabeça no meio com ar na lateral: empurra e NENHUMA letra pode sumir
    magra = _cena(0.46, 0.54)
    pior0, _ = _visibilidade(base, caixas, (255 - magra) / 255, 0, 0)
    pior, geral, dy, dx = ajustar_heroi(h, [magra], L, A)
    assert pior > pior0, f"não melhorou a pior letra ({pior:.2f} vs {pior0:.2f})"
    assert pior >= 0.60, f"letra sumindo ({pior:.0%})"
    assert geral < 1.0, "sem nenhuma oclusão não vende profundidade"
    # e o empurrão não pode jogar letra pra fora do quadro
    assert 0 <= xs.min() + dx and xs.max() + dx < L, f"saiu pela lateral (dx={dx})"
    assert 0 <= ys.min() + dy and ys.max() + dy < A, f"saiu por cima/baixo (dy={dy})"

    # tinta total mente: com a ÚLTIMA LETRA inteira tapada, o geral continua
    # alto e a palavra já virou outra. Tapa pela caixa da letra, não por um
    # número de pixels — número fixo deixa de cobrir quando o corpo muda.
    tapa = np.zeros((A, L), dtype=np.uint8)
    ux0, uy0, ux1, uy1 = caixas[-1]
    tapa[:, ux0:ux1 + 2] = 255
    p2, g2 = _visibilidade(base, caixas, (255 - tapa) / 255, 0, 0)
    assert g2 > 0.60, f"geral devia seguir alto, deu {g2:.2f}"
    assert p2 < 0.15, f"pior letra devia denunciar, deu {p2:.2f}"

    # duas camadas: gancho parado no topo + legenda rolando embaixo. A saída de
    # cada um se resolve na própria fila, e o frame tem que conter os dois.
    duas = finalizar([
        {"t0": 0.0, "t1": 3.0, "layout": "topo", "camada": "gancho",
         "words": [{"tx": "GANCHO", "t0": 0.0, "t1": 2.9}]},
        {"t0": 0.0, "t1": 1.0, "words": [{"tx": "UM", "t0": 0.0, "t1": 0.9}]},
        {"t0": 1.0, "t1": 2.0, "words": [{"tx": "DOIS", "t0": 1.0, "t1": 1.9}]},
    ])
    g = [c for c in duas if c["camada"] == "gancho"][0]
    l0 = [c for c in duas if c["camada"] == "legenda"][0]
    assert g["saida"], "gancho é o último da fila dele, devia animar saída"
    assert not l0["saida"], "legenda colada na seguinte não pode piscar"
    assert len(estado(0.5, duas, 30)) == 2, "chave do frame perdeu uma camada"
    for c in duas:
        c["_y"] = LAYOUTS[c["layout"]]["zona"][0] * 1920
    v0 = np.zeros(200, dtype=np.float32)
    im2 = desenhar(0.5, duas, 1080, 1920, v0)
    linhas = np.nonzero(np.array(im2)[..., 3].sum(axis=1))[0]
    assert linhas.min() < 900 and linhas.max() > 1000, "os dois não saíram no frame"

    # overlay de matte: colorir o estêncil e aceitar deslocamento NEGATIVO — o
    # gráfico do pack vem posicionado no quadro e quase sempre precisa descer
    # ou subir pra encontrar a faixa da legenda
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        mt = Image.new("L", (1080, 1920), 0)
        ImageDraw.Draw(mt).rectangle([300, 200, 780, 400], fill=255)
        pth = Path(_td) / "m.png"
        mt.save(pth)
        for desl, esperado in ((0, (200, 400)), (500, (700, 900)), (-150, (50, 250))):
            got = pintar_overlay(pth, {"cor": "#00FF00", "y": desl}, 1080, 1920)
            ys_o = np.nonzero(np.array(got)[..., 3].sum(axis=1))[0]
            assert abs(int(ys_o.min()) - esperado[0]) <= 2, \
                f"deslocamento y={desl} caiu em {ys_o.min()}, esperava {esperado[0]}"
        cor = np.array(pintar_overlay(pth, {"cor": "#12E06A"}, 1080, 1920))
        px = cor[300, 500]
        assert tuple(px[:3]) == (0x12, 0xE0, 0x6A) and px[3] == 255, f"não coloriu ({px})"

            # b-roll: fade nas pontas, entrada deslizando, empilhamento na ordem
        with _tf.TemporaryDirectory() as _tb:
            quadro = Image.new("RGB", (720, 480), (30, 160, 90))
            pb = Path(_tb) / "b.png"
            quadro.save(pb)
            cfg = {"t0": 0.0, "t1": 2.0, "y": 300, "fade": 0.3, "anim": "esquerda"}
            # no meio do clipe está cheio e no lugar
            meio = np.array(pintar_broll(pb, cfg, 1.0, 1080, 1920))
            assert meio[..., 3].max() == 255, "meio do b-roll devia estar opaco"
            xs_m = np.nonzero(meio[..., 3].sum(axis=0))[0]
            assert abs((xs_m.min() + xs_m.max()) / 2 - 540) < 30, "b-roll fora do centro"
            # no começo ainda entrando pela esquerda e transparente
            ini = np.array(pintar_broll(pb, cfg, 0.02, 1080, 1920))
            assert ini[..., 3].max() < 120, "fade de entrada não aplicou"
            xs_i = np.nonzero(ini[..., 3].sum(axis=0))[0]
            if xs_i.size:
                assert xs_i.mean() < xs_m.mean(), "entrada devia vir da esquerda"
            # e no fim, sumindo
            fim = np.array(pintar_broll(pb, cfg, 1.98, 1080, 1920))
            assert fim[..., 3].max() < 120, "fade de saída não aplicou"

            # encaixe no topo: sangra no alto e dissolve no rodapé
            enc = {"t0": 0.0, "t1": 2.0, "encaixe": "topo", "mescla": 150,
                   "larg": 1.0, "fade": 0}
            e = np.array(pintar_broll(pb, enc, 1.0, 1080, 1920))[..., 3]
            linhas = np.nonzero(e.sum(axis=1))[0]
            assert linhas.min() == 0, f"devia sangrar no topo, começa em {linhas.min()}"
            col = e[:, 540]
            cheio = np.nonzero(col == 255)[0]
            assert cheio.size, "nada opaco no painel encaixado"
            pe = int(linhas.max())
            # rodapé tem que ser rampa, não corte seco
            assert 0 < col[pe - 12] < 255, f"rodapé sem degradê (alpha {col[pe - 12]})"
            assert col[int(cheio.max())] == 255 and col[pe] < 70, "rampa invertida"

            # a mescla ESTENDE, não come: o painel tem que seguir opaco até a
            # altura pedida e só dissolver depois dela
            semm = np.array(pintar_broll(pb, dict(enc, mescla=0), 1.0, 1080, 1920))[..., 3]
            comm = np.array(pintar_broll(pb, enc, 1.0, 1080, 1920))[..., 3]
            fim_sem = int(np.nonzero(semm[:, 540])[0].max())
            opaco_com = int(np.nonzero(comm[:, 540] == 255)[0].max())
            assert opaco_com >= fim_sem - 4, \
                f"degradê comeu o painel (opaco até {opaco_com}, devia ir a {fim_sem})"
            fim_com = int(np.nonzero(comm[:, 540])[0].max())
            assert fim_com > fim_sem + 40, "a mescla não estendeu pra baixo"

            # degradê de COR: o painel caminha pra cor do ambiente na descida.
            # Só rampar alpha deixa branco translúcido, que não mescla.
            branco = Image.new("RGB", (720, 480), (250, 250, 250))
            pw = Path(_td) / "w.png"
            branco.save(pw)
            roxo = (40, 30, 200)   # bem saturado: torna a medida decisiva
            com = np.array(pintar_broll(pw, dict(enc, _cor_fundo=roxo), 1.0, 1080, 1920))
            sem = np.array(pintar_broll(pw, enc, 1.0, 1080, 1920))
            # `paste` com máscara sobre fundo transparente PRÉ-MULTIPLICA o RGB,
            # então nas linhas de alpha baixo a cor já vem escurecida e medir
            # valor absoluto não diz nada. A comparação tem que ser relativa.
            alfa = sem[..., 3][:, 540]
            lin = np.nonzero(alfa)[0]
            meio_rampa = int(np.argmin(np.abs(alfa[lin].astype(int) - 128)) + lin.min())
            r_com, r_sem = int(com[meio_rampa, 540, 0]), int(sem[meio_rampa, 540, 0])
            b_com, b_sem = int(com[meio_rampa, 540, 2]), int(sem[meio_rampa, 540, 2])
            assert r_com < r_sem - 10, f"vermelho não caiu rumo ao roxo ({r_com} vs {r_sem})"
            assert (b_com / max(1, r_com)) > (b_sem / max(1, r_sem)) + 0.15, \
                "não puxou pro azul do ambiente"
            # e o topo do painel fica intacto
            topo_y = int(lin.min()) + 20
            assert abs(int(com[topo_y, 540, 0]) - int(sem[topo_y, 540, 0])) < 4, \
                "topo do painel foi contaminado pela cor do fundo"

            # painel atrás do sujeito: a silhueta fura a camada de trás
            painel = np.array(pintar_broll(pb, dict(enc, atras=True), 1.0, 1080, 1920))
            base_lin = np.nonzero(painel[..., 3].sum(axis=1))[0]
            meio = int(base_lin.min() + (base_lin.max() - base_lin.min()) * 0.4)
            silhueta = np.zeros((1920, 1080), dtype=np.uint8)
            silhueta[:, 380:700] = 255                 # coluna central = a pessoa
            furado = painel.copy()
            furado[..., 3] = (furado[..., 3].astype(np.uint16)
                              * (255 - silhueta) // 255).astype(np.uint8)
            dentro = int(furado[meio, 540, 3])
            fora = int(furado[meio, 120, 3])
            assert dentro == 0, f"silhueta não furou o painel (alpha {dentro})"
            assert fora > 200, f"furou fora da silhueta (linha {meio}, alpha {fora})"

    # card de tela: canto arredondado e posicionado, não colado cru
        capt = Image.new("RGB", (900, 500), (40, 90, 200))
        pt = Path(_td) / "t.png"
        capt.save(pt)
        tl = pintar_tela(pt, {"y": 200, "raio": 40, "sombra": False}, 1080, 1920)
        at = np.array(tl)[..., 3]
        assert at[200 + 250, 540] == 255, "meio da tela devia ser opaco"
        assert at[200 + 2, 2] == 0, "canto devia estar arredondado (transparente)"
        ys_t = np.nonzero(at.sum(axis=1))[0]
        assert abs(int(ys_t.min()) - 200) <= 2, f"y da tela errado ({ys_t.min()})"

        # asset COM cor própria entra como está; com `cor:` vira estêncil
        colorido = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        ImageDraw.Draw(colorido).rectangle([300, 200, 780, 400], fill=(255, 90, 30, 255))
        pc = Path(_td) / "c.png"
        colorido.save(pc)
        orig = np.array(pintar_overlay(pc, {"_rgba": True}, 1080, 1920))[300, 500]
        assert tuple(orig[:3]) == (255, 90, 30), f"perdeu a cor original ({orig})"
        forc = np.array(pintar_overlay(pc, {"_rgba": True, "cor": "#0000FF"},
                                       1080, 1920))[300, 500]
        assert tuple(forc[:3]) == (0, 0, 255), f"`cor` não sobrepôs ({forc})"

    # bloco de manchete: fonte e corpo por linha, script em minúscula, e as
    # linhas não podem se atropelar por causa do ascendente do script
    def _bloco(ent):
        b = finalizar([{"t0": 0.0, "t1": 3.0, "layout": "topo", "quebra": "palavra",
                        "entrelinha": ent, "corpo": 70, "words": [
                            {"tx": "UM CRM INTEIRO", "t0": 0.0, "t1": 2.9, "corpo": 62},
                            {"tx": "sem contratar", "t0": 0.1, "t1": 2.9,
                             "corpo": 128, "fonte": "script", "caixa": "original"},
                            {"tx": "NENHUM DEV", "t0": 0.2, "t1": 2.9, "corpo": 58}]}])[0]
        b["_y"] = 200
        perfil = tinta(b, 1080, 1920)[0].sum(axis=1) > 0
        oc = np.nonzero(perfil)[0]
        return b, int(np.sum(np.diff(oc) > 1) + 1)          # blocos de tinta

    # alinhamento e dx por linha: manchete escalona, não centraliza
    esq = finalizar([{"t0": 0.0, "t1": 3.0, "layout": "topo", "quebra": "palavra",
                      "alinhar": "esquerda", "corpo": 70, "words": [
                          {"tx": "UMA", "t0": 0.0, "t1": 2.9},
                          {"tx": "DUAS", "t0": 0.1, "t1": 2.9, "dx": 120}]}])[0]
    esq["_y"] = 300
    diagramar(esq, 1080, 70, "creato", ImageDraw.Draw(Image.new("RGBA", (1080, 1920))),
              esq["_y"], 440)
    x0, x1 = esq["words"][0]["_cx"], esq["words"][1]["_cx"]
    assert x0 < 1080 / 2, "alinhar=esquerda não encostou na margem"
    assert abs((x1 - esq["words"][1]["_larg"] / 2)
               - (x0 - esq["words"][0]["_larg"] / 2) - 120) < 3, "dx da linha não aplicou"

    b, blocos = _bloco(1.20)
    assert b["words"][1]["tx"] == "sem contratar", "script foi pra caixa alta"
    assert b["words"][0]["tx"] == "UM CRM INTEIRO", "linha normal perdeu a caixa alta"
    # com entrelinha > 1 as três linhas ficam separadas mesmo com o script no meio
    assert blocos == 3, f"esperava 3 linhas separadas, achei {blocos}"
    # e entrelinha < 1 tem que ENCOSTAR de propósito — é como se aperta manchete
    assert _bloco(0.85)[1] < 3, "entrelinha apertada devia juntar as linhas"

    # placa não pode vazar pelo quadro, por mais larga que seja a fonte
    pl = finalizar([{"t0": 0.0, "t1": 1.0, "fonte": "basement", "corpo": 84,
                     "placa": {"tipo": "cartao", "cor": "#111318"},
                     "words": [{"tx": "EU RECEBO NOTIFICAÇÃO", "t0": 0.0, "t1": 0.9}]}])[0]
    pl["_y"] = 1150
    imp = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    _desenhar_card(ImageDraw.Draw(imp), pl, 0.9, 1080, 1920, np.zeros(200, np.float32))
    cols = np.nonzero(np.array(imp)[..., 3].sum(axis=0))[0]
    assert cols.min() >= 1 and cols.max() <= 1078, f"placa vazou ({cols.min()}..{cols.max()})"

    # quebra forçada: cartela de gancho vira N linhas, não o que couber na largura
    hk = finalizar([{"t0": 0.0, "t1": 3.0, "layout": "topo", "quebra": "palavra",
                     "corpo": 82, "words": [{"tx": "UM CRM INTEIRO", "t0": 0.0, "t1": 2.9},
                                            {"tx": "SEM CONTRATAR", "t0": 0.1, "t1": 2.9},
                                            {"tx": "NENHUM DEV", "t0": 0.2, "t1": 2.9}]}])[0]
    hk["_y"] = 200
    bh = tinta(hk, 1080, 1920)[0]
    ys_h = np.nonzero(bh.sum(axis=1))[0]
    livres = np.nonzero(bh.sum(axis=1) == 0)[0]
    quebras = np.sum(np.diff(livres[(livres > ys_h.min()) & (livres < ys_h.max())]) > 1) + 1
    assert quebras == 2, f"esperava 3 linhas (2 vãos), achei {quebras + 1}"

    # quebra por LARGURA MEDIDA: card curto em caractere mas largo em pixel
    # (punch numa fonte larga) tem que quebrar/encolher, não vazar pela lateral
    largo = finalizar([{"t0": 0.0, "t1": 1.0, "layout": "centro", "fonte": "slab",
                        "words": [{"tx": "MENOS DE", "t0": 0.0, "t1": 0.4},
                                  {"tx": "UMA HORA", "t0": 0.4, "t1": 0.9,
                                   "enf": "punch"}]}])[0]
    largo["_y"] = 400
    b3 = tinta(largo, 1080, 1920)[0]
    xs3 = np.nonzero(b3)[1]
    assert xs3.min() >= 0 and xs3.max() < 1080, "texto vazou pela lateral"

    # sujeito tomando o quadro: não dá pra salvar, e o chamador tem que saber
    p3, _, _, _ = ajustar_heroi(h, [_cena(0.05, 0.95)], L, A)
    assert p3 < 0.60, f"devia reprovar e cair pra frente, deu {p3:.0%}"

    # cabeça que ANDA durante o card: a posição tem que aguentar o pior instante.
    # Com média das amostras, a esquerda e a direita se anulam e o herói passa
    # num lugar que fica tapado em metade do card.
    anda = [_cena(0.10, 0.45), _cena(0.30, 0.65), _cena(0.55, 0.90)]
    p4, _, dy4, dx4 = ajustar_heroi(h, anda, L, A)
    if p4 >= 0.60:                       # se aprovou, tem que valer frame a frame
        b2, cx2 = tinta(dict(h, _y=h["_y"]), L, A)
        for i, q in enumerate(anda):
            pf, _ = _visibilidade(b2, cx2, (255 - q) / 255, dy4, dx4)
            assert pf >= 0.55, f"aprovou mas some no frame {i} ({pf:.0%})"

    # toda fonte do registro abre (índice de .ttc, instância variável) E desenha
    # acento — fonte de display costuma vir sem Ç, e o buraco só aparece no vídeo
    for n in FONTES:
        assert fonte(n, 40).getbbox("A"), f"fonte {n} não abriu"
        falta = acentos_faltando(n)
        assert not falta, f"fonte {n} não desenha: {falta}"

    # lint: o card que entra e sai sem nunca ficar inteiro na tela, e o que
    # atravessa a virada de tratamento. Os dois passavam batido antes.
    import io
    import contextlib
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "p.json"
        p.write_text(json.dumps({
            "camera": [{"t0": 0.0, "t1": 2.0, "zoom": [1.0, 1.1]},
                       {"t0": 2.0, "t1": 5.0, "janela": [0.3, 0.6]}],
            "brolls": [],
            "cards": [
                {"t0": 0.0, "t1": 0.30, "words": [{"tx": "UM", "t0": 0.0, "t1": 0.15},
                                                  {"tx": "DOIS", "t0": 0.15, "t1": 0.3}]},
                {"t0": 1.60, "t1": 2.60, "words": [{"tx": "TRÊS", "t0": 1.6, "t1": 2.6}]},
            ]}), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _lint(p)
        saida = buf.getvalue()
        assert "terminar de entrar" in saida, saida
        assert "atravessa a virada de 2.00s" in saida, saida

    # PRESETS. Sem `legenda`, o plano sai intocado: é a legenda de sempre.
    def _plano_fala(passo=0.32):
        tx = ("Agora eu sei o meu faturamento eu recebo notificação quando sai "
              "venda integração com desenvolvedores e o ticket médio").split()
        ws = [{"tx": x, "t0": round(i * passo, 2), "t1": round(i * passo + passo - 0.04, 2),
               **({"enf": "filler"} if x.lower() in ("eu", "o", "meu", "com", "e") else {})}
              for i, x in enumerate(tx)]
        return {"cards": [{"t0": ws[i]["t0"], "t1": ws[min(i + 4, len(ws)) - 1]["t1"] + 0.04,
                           "fonte": FONTE_PADRAO, "words": ws[i:i + 4]}
                          for i in range(0, len(ws), 4)]}
    cru = _plano_fala()
    intocado = json.loads(json.dumps(cru))
    aplicar_plano(intocado)
    assert intocado == cru, "plano sem `legenda` mudou"
    assert all("quebra" not in c for c in finalizar(intocado["cards"])), "padrão ganhou campo de preset"
    _antes = (cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA)
    try:
        aplicar_plano({"legenda": "nao-existe", "cards": _plano_fala()["cards"]})
        raise AssertionError("preset inexistente passou calado")
    except SystemExit as e:
        assert "Presets:" in str(e), e

    # O KIT: toda letra de preset (e a da colagem, e a do padrão) mora em
    # assets/fontes, com a licença ao lado. Nenhuma do ~/Library/Fonts do dono nem
    # do Mac: na máquina do aluno elas não existem e o preset caía na Montserrat
    usadas = {FONTE_PADRAO, *_LETRAS_COLAGEM}
    for p in PRESETS.values():
        usadas |= {p.get("fonte"), p.get("fonte_chave")}
        for b in [*(p.get("papeis") or {}).values(),
                  *(v for v in (p.get("momento") or {}).values() if isinstance(v, dict))]:
            usadas.add(b.get("fonte"))
    usadas.discard(None)
    licencas = (Path(_AF) / "LICENCAS.md").read_text(encoding="utf-8")
    for n in sorted(usadas):
        arq = Path(FONTES[n][0])
        assert arq.parent == Path(_AF) and arq.exists(), f"preset usa '{n}' de fora do kit: {arq}"
        assert f"`{arq.name}`" in licencas, f"{arq.name} sem linha no LICENCAS.md"
        familia = arq.stem.split("[")[0].split("-")[0]
        assert (Path(_AF) / f"{familia}-OFL.txt").exists(), f"{arq.name} sem o texto da OFL ao lado"

    paletas = {}
    for nome, p in PRESETS.items():
        assert p.get("uso"), f"preset {nome} sem `uso`"
        if nome == "padrao":
            continue
        # cada um com cor própria de verdade: base, destaque e o que vai atrás
        ef = p.get("efeito") or {}
        paleta = (p.get("cor"), p.get("acento") or tuple(p.get("ciclo") or ()),
                  (p.get("placa") or {}).get("cor"), (ef.get("marca") or {}).get("cor"),
                  p.get("fonte"))
        assert paleta not in paletas.values(), f"{nome} repete a paleta de outro preset"
        paletas[nome] = paleta
        assert p.get("fonte") in FONTES, f"{nome}: fonte '{p.get('fonte')}' fora do registro"
        # piso do celular: 44 px em tela cheia, até na palavra encolhida (filler)
        menor = min([ENFASE["filler"]["escala"]]
                    + [x["escala"] for x in [*(p.get("papeis") or {}).values(),
                                             *(p.get("momento") or {}).values()]
                       if isinstance(x, dict) and "escala" in x])
        # 16:9 (`horizontal`): o corpo escala pela largura (1920), o piso vale no lado menor (1080)
        k = 1920 / 1080 if p.get("horizontal") else 1
        assert LAYOUTS["faixa"]["corpo"] * p.get("escala", 1) * menor * k >= 44, \
            f"{nome}: letra abaixo do piso de 44 px"
        pl = _plano_fala()
        pl["legenda"] = nome
        aplicar_plano(pl)
        cs = finalizar(pl["cards"])
        assert sum(len(w["tx"].split()) for c in cs for w in c["words"]) == 19, \
            f"{nome}: palavra sumiu no corte"
        teto = p.get("palavras", 99)
        for c in cs:
            # o check_lines da legenda: nenhum cartão quebra linha
            linhas = len(c["words"]) if c.get("quebra") == "palavra" else 1
            assert _linhas(c) == linhas, f"{nome}: '{' '.join(w['tx'] for w in c['words'])}' quebrou"
            assert not _tempo(c), f"{nome}: {_tempo(c)}"
            assert c["fonte"] == p["fonte"], f"{nome}: a fonte do preset não pegou"
        if teto < 4:
            assert len(cs) > 5, f"{nome}: o teto de {teto} palavras não cortou os cartões"
        for c in cs:
            c["_y"], c["_base"] = 1300, True
        im = np.array(desenhar(cs[1]["t0"] + 0.5, cs, 1080, 1920, np.zeros(200, np.float32)))
        assert im[..., 3].max() == 255, f"{nome}: não desenhou nada"
        # no meio da entrada (é aí que máscara, desfoque e giro desenham à parte)
        for c in cs:
            meio = np.array(desenhar(c["t0"] + cv.ENTRADA * 0.4, cs, 1080, 1920, np.zeros(200, np.float32)))
            assert meio[..., 3].max() > 0 or c.get("anim") == "revela", f"{nome}: a entrada sumiu"
        if p.get("papeis"):
            assert any(len({w.get("fonte", c["fonte"]) for w in c["words"]}) >= 2 for c in cs), \
                f"{nome}: sistema com uma fonte só por cartão"
        if p.get("momento"):
            mo = [c for c in cs if c.get("_momento")]
            assert mo, f"{nome}: nenhum momento-chave"
            ws = mo[0]["words"]
            corpos = [w.get("corpo", mo[0]["corpo"]) * ENFASE[w.get("enf", "normal")]["escala"]
                      for w in ws]
            assert max(corpos) >= 4 * min(corpos), f"{nome}: o momento não salta de tamanho ({corpos})"
        cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes

    # a cor do preset vence o acento do estilo, e o ciclo troca a cada cartão
    pl = _plano_fala()
    pl.update(legenda="karaoke-ciclo", acento="#0640fb")
    aplicar_plano(pl)
    assert [c["acento"] for c in pl["cards"][:3]] == PRESETS["karaoke-ciclo"]["ciclo"]
    cv.HOT = _antes[0]
    ENFASE["chave"]["cor"] = cv.HOT
    # card com o próprio `legenda` vence o do plano; a letra escolhida também
    pl = _plano_fala()
    pl["legenda"] = "fita"
    pl["cards"][0].update(legenda="minimal")
    pl["cards"][1]["fonte"] = "slab"
    aplicar_plano(pl)
    assert pl["cards"][0]["_preset"] == "minimal" and pl["cards"][-1]["_preset"] == "fita"
    assert any(c["fonte"] == "slab" for c in pl["cards"]), "a letra da marca foi atropelada"
    # a marca `fala` segura na última palavra que começou, sem piscar no vão
    cf = {"words": [{"tx": "A", "t0": 0.0, "t1": 0.2}, {"tx": "B", "t0": 0.5, "t1": 0.7}]}
    assert _falada(cf, 0.35)["tx"] == "A" and _falada(cf, 0.6)["tx"] == "B"
    assert _falada(cf, -0.1) is None
    # o lint mede a quebra: card de preset longo demais reprova
    longo = finalizar([{"t0": 0.0, "t1": 3.0, "_preset": "x", "quebra": "palavra",
                        "words": [{"tx": "UMA", "t0": 0.0, "t1": 1}, {"tx": "DUAS", "t0": 1, "t1": 2}]}])[0]
    assert _linhas(longo) == 2

    # ASSINATURAS (terceira volta). Plano dirigido: só a palavra marcada vira
    # momento, o cartão dela não se corta, e a câmera crava no instante dela.
    v0 = np.zeros(4000, np.float32)

    def _dirigido(nome: str, i_card: int = 2, i_w: int = 0) -> dict:
        pl = _plano_fala()
        pl["legenda"] = nome
        pl["cards"][i_card]["words"][i_w]["heroi"] = True
        aplicar_plano(pl)
        mo = [c for c in pl["cards"] if c.get("_momento")]
        assert len(mo) == 1, f"{nome}: dirigido devia dar um momento só, deu {len(mo)}"
        for c in pl["cards"]:
            c["_y"], c["_base"] = 700, False
        pl["cards"] = finalizar(pl["cards"])
        return pl

    pl = _dirigido("trailer")
    mo = next(c for c in pl["cards"] if c.get("_momento"))
    h = _heroi(mo)
    assert mo["assinatura"] == "heroi3d" and h["tx"] == "NOTIFICAÇÃO", (mo.get("assinatura"), h["tx"])
    assert mo["_t_in"] == round(max(mo["t0"], h["t0"]), 3) and mo["_pouso"] > mo["_t_in"]
    cam = [c for c in pl["camera"] if c.get("_crava")]
    assert len(cam) == 2 and cam[0]["t0"] == mo["_t_in"] and cam[0]["ease"] == "crava" \
        and cam[0]["borrao"] and cam[1]["t1"] == mo["t1"], cam
    # a câmera em Python anda na mesma curva do ffmpeg: parte de 1, chega no crava
    assert abs(zoom_em(mo["_t_in"], pl["camera"])[0] - 1.0) < 1e-6
    assert abs(zoom_em(cam[1]["t0"], pl["camera"])[0] - cam[0]["zoom"][1]) < 1e-6
    assert zoom_em(mo["t1"] - 0.01, pl["camera"])[0] > cam[0]["zoom"][1], "a câmera não segue andando"
    # o recorte vai junto: o centro fica, a borda abre pra fora
    mt = np.zeros((1920, 1080), np.uint8)
    mt[900:1020, 480:600] = 255
    mt[580:620, 280:320] = 255                 # vai pra 540 + (300 - 540) * 1,2 = 252
    mz = na_camera(mt, 1.2)
    assert mz[960, 540] == 255 and mz[600, 300] == 0 and mz[528, 252] == 255, "recorte não seguiu o zoom"
    # `desce`: a pessoa passa do teto do foco (aqui 0,065 a 1,15) e o recorte desce junto, 0,17 do quadro
    cd = [{"t0": 0.0, "t1": 1.0, "zoom": [1.15, 1.15], "ease": "reta", "foco": [0.0, -0.065], "desce": 0.17}]
    zd, fd = zoom_em(0.5, cd)
    assert len(fd) == 3 and abs(fd[2] - 0.17) < 1e-9 and len(zoom_em(0.5, [{**cd[0], "desce": 0}])[1]) == 2
    linha = lambda m: np.where(m[:, 540] > 128)[0].mean()
    assert abs(linha(na_camera(mt, zd, fd)) - linha(na_camera(mt, zd, fd[:2])) - 0.17 * 1920) < 2, "recorte não desceu"
    # o ffmpeg da cena que crava: o borrão de verdade (N instantes e tmix) só nela
    with _tc.TemporaryDirectory() as _tcd:
        _x = Path(_tcd) / "x.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:r=30:d=1",
                "-pix_fmt", ff.PIX_FMT, "-c:v", ff.CODEC_VIDEO, str(_x)], check=True)
        with ff.seco() as _gravado:
            camera_cenas(_x, cam, 4.0, 30, 1080, 1920, Path(_tcd))
    tudo = " || ".join(" ".join(str(c) for c in cmd) for cmd in _gravado)
    assert tudo.count("tmix=frames=4") == 1 and tudo.count("fps=120") == 1, tudo[:300]
    # o lint não acusa a câmera que crava como virada, e o respiro é o da assinatura
    with tempfile.TemporaryDirectory() as td:
        pj = Path(td) / "p.json"
        cru = _plano_fala()
        cru["legenda"] = "trailer"
        cru["cards"][2]["words"][0]["heroi"] = True
        pj.write_text(json.dumps(cru), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _lint(pj)
        assert "atravessa" not in buf.getvalue() and "ERRO" not in buf.getvalue(), buf.getvalue()
    cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes
    ENFASE["chave"]["cor"] = cv.HOT
    # o 3D: face clara, lado escuro, sombra; e o quadro parado sai nítido
    t_h = mo["_pouso"] + 0.5
    assert mo["t1"] - mo["_pouso"] >= SEGURA - 1e-6 and mo["camada"] == "heroi", "o herói não segurou"
    im = np.array(desenhar(t_h, pl["cards"], 1080, 1920, v0))
    al = im[..., 3] > 200
    lum = im[..., :3].astype(np.float32).mean(axis=2)
    assert (lum[al] > 200).sum() > 500 and (lum[al] < 90).sum() > 200, "o 3D saiu sem face clara ou lado escuro"
    # e entrando: o obturador abre (o dobro de instantes na assinatura) e borra:
    # o mesmo instante com e sem obturador, e o com tem mais meio-tom (rastro)
    t_e = mo["_t_in"] + CRAVA * 0.35
    assert _movendo(mo, t_e) == 2 and _movendo(mo, t_h) == 0
    meio_tom = lambda a: ((a > 25) & (a < 230)).sum() / max(1, (a > 25).sum())
    com = meio_tom(np.array(desenhar(t_e, pl["cards"], 1080, 1920, v0))[..., 3])
    b_ = mo.pop("borrao")
    sem = meio_tom(np.array(desenhar(t_e, pl["cards"], 1080, 1920, v0))[..., 3])
    mo["borrao"] = b_
    assert com > sem * 1.15, f"a entrada não borrou ({com:.2f} com obturador, {sem:.2f} sem)"
    # a luz soma: estoura no pouso, acaba antes do fim; os golpes viram cues
    assert brilho(mo["_pouso"], pl["cards"], 1080, 1920).max() > 150
    assert brilho(mo["t1"] - 0.01, pl["cards"], 1080, 1920) is None
    assert luz(mo["_pouso"], pl["cards"], 1080, 1920) is None, "o trailer não escurece"
    cs_ = {(c["tipo"], c["t"]) for c in cues(pl["cards"])}
    assert {("zoom-in", mo["_t_in"]), ("impact", mo["_pouso"]), ("boom", mo["_pouso"])} <= cs_, cs_
    assert estado(t_h, pl["cards"], 30) != estado(t_h + 1 / 30, pl["cards"], 30), "momento reaproveitou quadro"
    cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes
    ENFASE["chave"]["cor"] = cv.HOT

    # a colagem: letras de famílias diferentes, todas OFL do registro
    pl = _dirigido("revista")
    mo = next(c for c in pl["cards"] if c.get("_momento"))
    desenhar(mo["_pouso"] + 0.5, pl["cards"], 1080, 1920, v0)
    nomes = {r[3] for r in _recortes(_heroi(mo)) if r}
    assert len(nomes) >= 4 and nomes <= set(FONTES), nomes
    assert mo["assinatura"] == "colagem" and brilho(mo["_pouso"], pl["cards"], 1080, 1920).min() > 150, "o flash"
    assert abs(mo["_pouso"] - (mo["_t_in"] + _colagem_dur(mo))) < 0.002, "o flash veio antes da palavra inteira"
    assert all(c.get("pe") and c.get("largura") for c in pl["cards"]), "a corrida sem o pé da zona segura"
    assert any(c["tipo"] == "thud" for c in cues(pl["cards"]))
    cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes
    ENFASE["chave"]["cor"] = cv.HOT

    # o thriller: a frase se datilografa (metade da frase na metade do tempo) e o
    # carimbo bate, com o som de tecla e o de carimbo
    pl = _dirigido("thriller", 1, 1)
    mo = next(c for c in pl["cards"] if c.get("_momento"))
    ap = next(w for w in mo["words"] if w.get("entrada") == "maquina")
    larg = lambda t: np.nonzero(np.array(desenhar(t, pl["cards"], 1080, 1920, v0))[..., 3].sum(axis=0))[0]
    meio_t = larg(ap["t0"] + (ap["t1"] - ap["t0"]) * 0.4)
    cheio = larg(mo["_t_in"] - 0.01)
    assert len(meio_t) and len(cheio) and meio_t.max() < cheio.max() - 20, "a máquina não datilografou"
    assert mo["assinatura"] == "carimbo" and luz(mo["_pouso"], pl["cards"], 1080, 1920) is not None
    tipos = {c["tipo"] for c in cues(pl["cards"])}
    assert {"type", "stamp", "hit"} <= tipos, tipos
    cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes
    ENFASE["chave"]["cor"] = cv.HOT


def test_quadros_em_paralelo_dao_os_mesmos_bytes():
    """A legenda desenha os quadros em vários processos (spawn no Mac e no Windows: o processo novo parte do
    módulo recém-importado) e cada PNG sai byte a byte igual ao do processo único: o desenho do quadro não pode
    depender de quem o desenhou nem da ordem. Com o herói 3D na tela, que é o desenho que mais usa numpy, e com
    cor e ritmo trocados pelo plano, que o processo novo só enxerga se o estado do módulo viajar com ele."""
    import hashlib
    tx = "Agora eu sei o meu faturamento eu recebo notificação quando sai venda integração com desenvolvedores".split()
    ws = [{"tx": x, "t0": round(i * 0.32, 2), "t1": round(i * 0.32 + 0.28, 2)} for i, x in enumerate(tx)]
    pl = {"legenda": "trailer", "acento": "#0640fb", "ritmo": {"entrada": 0.2, "stagger": 0.05},
          "cards": [{"t0": ws[i]["t0"], "t1": ws[min(i + 4, len(ws)) - 1]["t1"] + 0.04,
                     "fonte": FONTE_PADRAO, "words": ws[i:i + 4]} for i in range(0, len(ws), 4)]}
    pl["cards"][2]["words"][0]["heroi"] = True
    _antes = (cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA)
    try:
        aplicar_plano(pl)
        for c in pl["cards"]:
            c["_y"], c["_base"] = 700, False
        cards = finalizar(pl["cards"])
        mo = next(c for c in cards if c.get("_momento"))
        quadros = sorted({round(t * 30) for t in np.linspace(0.0, mo["t1"], 24)})
        vol = np.zeros(4000, np.float32)

        def em(pasta: Path, procs: int):
            pasta.mkdir()
            ctx = dict(cards=cards, vol=vol, largura=1080, altura=1920, fps=30, sis=False, tmp=pasta,
                       luzes=None, reaproveita=frozenset())
            usou = pintar_quadros(quadros, lambda i: {}, ctx, procs)
            return usou, {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in pasta.glob("*.png")}

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            usou_p, par = em(d / "par", 4)      # primeiro o paralelo: os filhos partem de cache frio
            usou_s, serie = em(d / "serie", 1)
    finally:
        cv.HOT, cv.ENTRADA, cv.STAGGER, cv.SAIDA = _antes
        ENFASE["chave"]["cor"] = cv.HOT
    assert (usou_s, usou_p) == (1, 4), (usou_s, usou_p)
    assert len(serie) == len(quadros) and serie == par, \
        f"{sum(serie[k] != par.get(k) for k in serie)} de {len(serie)} quadros mudaram com os processos"
    assert len(set(serie.values())) > 8, "os quadros saíram todos iguais: o teste não olhou o desenho"
    assert 1 <= processos() <= 4


def test_mapa_do_sujeito_guarda_pelo_conteudo():
    """O trecho refeito igual (instante novo, outra pasta) não paga o recorte de novo; o refeito
    diferente, sim. Pelo nome e pelo instante, o r2-mesa do Treinando #2 pagava 25 s a cada rodada."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        velho, cena.CACHE = cena.CACHE, d / "cache"
        recortes = []
        alfa = cena._alfa
        cena._alfa = lambda im, *a, **k: recortes.append(1) or np.zeros((im.height, im.width), np.uint8)
        try:
            a = d / "a.mp4"
            ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x284:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", str(a)], quiet=True)
            cena.mapa_sujeito(a, 2.0, 160, 284)
            n = len(recortes)
            assert n > 0
            (d / "outra").mkdir()
            b = d / "outra" / "b.mp4"
            shutil.copyfile(a, b)
            os.utime(b, (1, 1))
            cena.mapa_sujeito(b, 2.0, 160, 284)
            cena.mapa_movimento(b, 2.0, 160, 284)
            assert len(recortes) == n, "o mesmo trecho em outra pasta, com outro instante, recortou de novo"
            ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x284:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", str(a)], quiet=True)
            cena.mapa_sujeito(a, 2.0, 160, 284)
            assert len(recortes) == 2 * n, "o trecho refeito diferente serviu o mapa velho"
        finally:
            cena.CACHE, cena._alfa = velho, alfa


def test_legenda_em_tela_cheia_tem_contraste_com_o_fundo_nos_12_estilos():
    """Em `cheia`, a letra (normal, chave, punch, filler, e a que acende) tem contraste >= 4,5 com o que está atrás: branco sobre
    branco some. Fundo = chão de cada um dos 12 estilos, mais branco e preto; a cor é a do estilo (letra e destaque dele)."""
    estilos = {"neobrutalista": ("#FFFFFF", "#0B0D12", "#0640FB"), "editorial": ("#F5F2EB", "#1B1B1B", "#7A2E2E"),
               "tech": ("#060A12", "#E7EEF8", "#2F6BFF"), "retro": ("#F4E3C1", "#3B2314", "#C8512B"),
               "pop": ("#9EE3FF", "#1A1446", "#F0287A"), "luxo": ("#0D0C0A", "#F1E9DA", "#8F7342"),
               "cyberpunk": ("#0B0618", "#F3F0FF", "#E21CC0"), "pixel": ("#1A1C3A", "#F7F7F2", "#6C4CF5"),
               "quadrinhos": ("#FFF3D6", "#111111", "#F2620F"), "vaporwave": ("#2A1352", "#FFF0FB", "#E0459B"),
               "lousa": ("#1E3A2F", "#F2EFE6", "#3C6DB4"), "colagem": ("#D6C4A2", "#141414", "#1F45C8")}
    assert len(estilos) == 12
    hot, chave = cv.HOT, dict(cv.ENFASE["chave"])
    try:
        for nome, (chao, letra, destaque) in estilos.items():
            for fundo in (chao, "#FFFFFF", "#000000"):
                L = cv.luminancia(cv.rgb(fundo))
                plano = {"acento": destaque, "dividida": [[0, 3, 600, 1100, L]],
                         "cards": [{"t0": 0.0, "t1": 2.0, "cor": letra, "modo": "karaoke", "words": [
                             {"tx": "a", "t0": 0.0, "t1": 0.5}, {"tx": "b", "t0": 0.5, "t1": 1.0, "enf": "chave"},
                             {"tx": "c", "t0": 1.0, "t1": 1.5, "enf": "punch"}, {"tx": "d", "t0": 1.5, "t1": 2.0, "enf": "filler"}]}]}
                cv.aplicar_plano(plano)
                c = plano["cards"][0]
                assert c.get("_fundo") == L, (nome, "o fundo medido não chegou à legenda")
                for t in (0.1, 1.9):
                    for w in c["words"]:
                        cor = cv.cor_da_palavra(c, w, t)
                        ct = cv.contraste(cv.luminancia(cor), L)
                        assert ct >= 4.5, f"{nome} sobre {fundo}: palavra {w['tx']} ({w.get('enf', 'normal')}) {cor} contraste {ct:.2f}"
    finally:
        cv.HOT = hot
        cv.ENFASE["chave"].update(chave)
    # sem fundo medido, a cor do estilo fica como está; e com placa o fundo é a placa
    c = {"modo": "pop", "words": [{"tx": "x", "t0": 0, "t1": 1}], "cor": "#FFFFFF", "t0": 0, "t1": 1}
    assert cv.cor_da_palavra(c, c["words"][0], 0.5) == (255, 255, 255)
    assert cv.cor_da_palavra({**c, "_fundo": 1.0, "placa": {"cor": "#111111", "opacidade": 1.0}}, c["words"][0], 0.5) == (255, 255, 255)
    assert cv.cor_da_palavra({**c, "_fundo": 1.0}, c["words"][0], 0.5) != (255, 255, 255)
    # a luminância medida no quadro: branco 1, preto 0
    q = np.full((1920, 1080, 3), 255, np.uint8)
    assert abs(cv.luminancia_do_vao(q, 100, 300) - 1.0) < 1e-6 and cv.luminancia_do_vao(q * 0, 100, 300) == 0.0


def test_quadros_desenha_so_os_instantes_pedidos_e_nao_faz_o_video(tmp_path=None):
    """`--quadros` é a prévia do storyboard: um JPEG por instante com a legenda por cima do quadro, em vez do vídeo todo
    queimado (103–166 s por rodada). -o vira pasta e o vídeo de saída não existe."""
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        video = d / "v.mp4"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x303030:size=360x640:rate=25:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", video], quiet=True)
        plano = d / "plano.json"
        plano.write_text(json.dumps({"cards": [{"t0": 0.2, "t1": 2.5, "fonte": FONTE_PADRAO, "words": [
            {"tx": "OI", "t0": 0.2, "t1": 1.0}, {"tx": "MUNDO", "t0": 1.0, "t1": 2.5}]}]}), encoding="utf-8")
        saida = d / "quadros"
        r = subprocess.run([sys.executable, str(Path(cv.__file__)), str(video), "--plan", str(plano),
                            "--quadros", "1.200,1.200,2.800", "-o", str(saida)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[-400:]
        assert sorted(f.name for f in saida.iterdir()) == ["1.200.jpg", "2.800.jpg"], list(saida.iterdir())
        com, sem = np.asarray(Image.open(saida / "1.200.jpg")).astype(int), np.asarray(Image.open(saida / "2.800.jpg")).astype(int)
        assert com.shape == sem.shape == (640, 360, 3)
        assert np.abs(com - 0x30).max() > 60, "a legenda não apareceu no quadro de 1,2 s"
        assert np.abs(sem - 0x30).max() < 30, "o quadro de 2,8 s (sem card) devia ser o vídeo limpo"


def main() -> int:
    casos = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    falhas = 0
    for nome, caso in casos:
        try:
            caso()
            print(f"  ok   {nome}")
        except AssertionError as e:
            falhas += 1
            print(f"  FALHA {nome}: {e}")
    print(f"\n{len(casos) - falhas}/{len(casos)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
