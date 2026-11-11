"""Legenda viral dirigida — o plano manda, o script desenha.

Este ffmpeg não tem libass nem freetype (sem `ass`, sem `drawtext`): o texto sai
do PIL e entra por overlay.

    python captions_viral.py video.mp4 --plan plano.json -o out.mp4
    python captions_viral.py video.mp4 --words t.json --style destaque -o out.mp4

O que o renderer garante sozinho, sem o plano pedir:

  - Nada de interpolação linear. Entrada é mola amortecida.
  - Entrada mexe em três propriedades juntas: escala, opacidade e y.
  - Palavra entra escalonada dentro do card, não o card inteiro de uma vez.
  - Saída existe e é mais rápida que a entrada — quando há respiro depois do card.
  - Amplitude da entrada é proporcional ao VOLUME da fala naquela palavra.
  - Palavra `punch` respira (micro-oscilação) enquanto está na tela.
  - O y do card foge do movimento da cena: o texto não senta em cima da boca.

A linha é diagramada com o tamanho FINAL de cada palavra e cada uma anima em
torno do próprio centro. A escala nunca reflui a linha.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import ff
import transcript as tr
from camera import _ANDAMENTO, camera_cenas, curva_da_janela, curva_tela, na_camera, zoom_em
from cena import MATTE_PADRAO, _alfa_cache, linha_do_ombro, mapa_movimento, mapa_sujeito, melhor_y

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W_REF = 1080
ENTRADA = 0.267         # 8 frames a 30fps
STAGGER = 0.067         # 2 frames entre palavras do mesmo card
SAIDA = 0.133           # 4 frames — metade da entrada, como manda a regra


PE_ABAIXO = 1470        # o começo da interface do rodape do Reels/Shorts (a mesma medida da `faixa`)


def layout_do_vao(y0: float, y1: float, h: int = 108, folga: int = 24) -> str | None:
    """O layout da legenda de uma tela cheia com peça na caixa `y0..y1` (px de 1080x1920): abaixo da caixa se o pé ainda
    cabe antes da interface do rodape; senão acima, se couber abaixo da faixa do topo (250). Registra o layout em `LAYOUTS`
    e devolve o nome; sem vão, `None` (a legenda fica onde o estilo põe)."""
    if y1 + folga + h <= PE_ABAIXO:
        pe = y1 + folga + h
    elif y0 - folga - h >= 250:
        pe = y0 - folga
    else:
        return None
    nome = f"vao_{round(pe)}"
    LAYOUTS[nome] = {"zona": ((pe - h) / 1920, pe / 1920), "h": h, "corpo": 52, "base": True}
    return nome


CONTRASTE_MIN = 4.5     # letra contra o fundo (WCAG AA): o mínimo da legenda em tela cheia


def luminancia(cor) -> float:
    """Luminância relativa (0 preto, 1 branco) de uma cor `(r, g, b)` 0-255."""
    r, g, b = ((v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in cor[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(l1: float, l2: float) -> float:
    a, b = max(l1, l2), min(l1, l2)
    return (a + 0.05) / (b + 0.05)


def faixa_da_legenda(layout: str | None = None) -> tuple[float, float]:
    """Onde a legenda de um layout senta na tela 1080x1920 (y de cima, y de baixo, px): o pé da zona se ela é de base, senão o meio."""
    lay = LAYOUTS.get(layout or "faixa", LAYOUTS["faixa"])
    h, k = lay["h"] * 1080 / W_REF, 1080 / W_REF
    if lay.get("base"):
        return lay["zona"][1] * 1920 - h, lay["zona"][1] * 1920
    meio = (lay["zona"][0] + lay["zona"][1]) / 2 * 1920
    return meio - h / 2, meio + h / 2


def luminancia_do_vao(quadro, y0: float, y1: float) -> float:
    """Luminância média das linhas `y0..y1` de um quadro RGB (array HxWx3 de uma tela 1080x1920): o que há atrás da legenda."""
    q = np.asarray(quadro)
    if q.shape[0] != 1920:
        y0, y1 = y0 * q.shape[0] / 1920, y1 * q.shape[0] / 1920
    faixa = q[max(0, int(y0)):max(int(y0) + 1, int(y1))].reshape(-1, q.shape[2])[:, :3].astype(np.float64) / 255
    lin = np.where(faixa <= 0.03928, faixa / 12.92, ((faixa + 0.055) / 1.055) ** 2.4)
    return float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean())


def legivel(cor, fundo: float) -> tuple[int, int, int]:
    """A `cor` se ela tem contraste >= 4,5 com o fundo (luminância); senão a mesma cor puxada ao preto ou ao branco (o que
    contrasta mais) até passar: a matiz do estilo fica enquanto der. Sempre passa: preto ou branco chegam a 4,58 no pior fundo."""
    cor = tuple(int(v) for v in cor[:3])
    if contraste(luminancia(cor), fundo) >= CONTRASTE_MIN:
        return cor
    alvo = (0, 0, 0) if contraste(0.0, fundo) >= contraste(1.0, fundo) else (255, 255, 255)
    for k in range(1, 21):
        c = tuple(round(v + (t - v) * k / 20) for v, t in zip(cor, alvo))
        if contraste(luminancia(c), fundo) >= CONTRASTE_MIN:
            return c
    return alvo


def aplicar_plano(plano: dict) -> None:
    """Ajustes que são do VÍDEO, não do renderer: `ritmo` e `acento`.

    `"acento": "#0640fb"` troca a cor com que a palavra falada acende. O amarelo
    padrão é do reel; numa VSL que tem identidade própria ele briga com a marca.

    `"ritmo": {"entrada": 0.167, "stagger": 0.033}`.

    A entrada é a mesma há oito frames porque a fala de referência tinha 150
    palavras por minuto. A 197 — que é o que ele fala de verdade — o card dura
    0,6s e a entrada come 0,47 deles: a frase aparece e sai sem nunca ter estado
    inteira na tela. Alargar o card pra caber a entrada dá card de oito
    palavras; encurtar a entrada resolve sem tocar no texto.

    Global, e não parâmetro: são seis funções no caminho do desenho, e o script
    roda um plano por vez.
    """
    global ENTRADA, STAGGER, SAIDA, HOT
    if plano.get("acento"):
        c = str(plano["acento"]).lstrip("#")
        HOT = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        ENFASE["chave"]["cor"] = HOT      # ENFASE prendeu o valor antigo na definição
    # TELA DIVIDIDA MANDA NO LAYOUT, e isso mora aqui pra não depender de quem
    # escreve o plano lembrar. Card dentro de uma cena com `janela` vai pro
    # layout `entre` — encostado por baixo do painel. Na `faixa` ele cairia na
    # boca; no `rodape`, largado no pé da tela, longe do gráfico que narra.
    # Layout escrito à mão no card continua valendo: o explícito ganha.
    janelas = [(float(c["t0"]), float(c["t1"]))
               for c in (plano.get("camera") or []) if c.get("janela")]
    # Painel que nasce ou morre junto com a janela não faz fade NENHUM: quem
    # transiciona ali é o corte de câmera. Durante o fade o painel ainda é
    # translúcido e a tarja preta da tela dividida aparece por baixo — um quadro
    # escuro na entrada e outro na saída, em toda peça de painel do vídeo.
    #
    # As duas pontas, e não só a saída: o defeito é simétrico e só a metade
    # dele tinha sido vista.
    inicios = {round(a, 3) for a, _ in janelas}
    fins = {round(b, 3) for _, b in janelas}
    cenas_j = [c for c in (plano.get("camera") or []) if c.get("janela")]
    curvas_ini = {round(float(c["t0"]), 3): curva_da_janela(c) for c in cenas_j}
    curvas_fim = {round(float(c["t1"]), 3): curva_da_janela(c) for c in cenas_j}
    for b in plano.get("brolls") or []:
        if b.get("alfa"):
            continue                       # chip flutua: o fade dele é a entrada
        # Painel que nasce ou morre na borda da janela, e TAMBÉM a peça de tela
        # cheia que assume quando a janela acaba. No fade dela o rosto reaparece
        # por um sexto de segundo entre o painel e o card — não é tarja preta,
        # é um piscar de rosto, e lê como falha de montagem do mesmo jeito.
        if "fade" not in b and round(float(b["t0"]), 3) in (inicios | fins):
            b["fade"] = 0.0
        if "fade_saida" not in b and round(float(b["t1"]), 3) in (inicios | fins):
            b["fade_saida"] = 0.0
        # PAINEL AMARRADO À JANELA anda na mesma curva da câmera: desce na
        # entrada e sobe na saída, sem fade. As durações são as da cena de
        # câmera, pra painel e câmera nunca descolarem. Com a câmera sempre
        # atrás da borda do painel, o recuo de dois quadros que cobria a tarja
        # na entrada deixou de ter o que cobrir.
        if b.get("encaixe") == "topo":
            ini = curvas_ini.get(round(float(b["t0"]), 3))
            fim = curvas_fim.get(round(float(b["t1"]), 3))
            if ini:
                b["_entra"], b["fade"] = ini[0], 0.0
            if fim:
                b["_sai"], b["fade_saida"] = fim[1], 0.0

    # `dividida` (lista de [t0, t1] das batidas em tela dividida) vence até o layout do estilo; fora dela o estilo segue
    # Entrada de 4 números `[t0, t1, y0, y1]` é a tela cheia com uma peça: a caixa dela (px da tela 1080x1920) é onde a legenda não senta.
    div = [(float(e[0]), float(e[1])) for e in plano.get("dividida") or [] if len(e) == 2]
    # O 5º número, se vier, é a luminância do que está atrás da legenda (`luminancia_do_vao`): a cor da letra passa a ter contraste com ela.
    cheia = [tuple(float(v) for v in e) for e in plano.get("dividida") or [] if len(e) in (4, 5)]
    for c in plano.get("cards") or []:
        meio_c = (float(c["t0"]) + float(c["t1"])) / 2
        if cheia and c.get("camada", "legenda") == "legenda" and not c.get("layout"):
            ach = next((e for e in cheia if e[0] <= meio_c < e[1]), None)
            vao = layout_do_vao(ach[2], ach[3]) if ach else None
            if ach and len(ach) == 5:
                c["_fundo"] = ach[4]
            if vao:
                c["layout"] = vao
                continue
        if div and c.get("camada", "legenda") == "legenda" and any(a <= (float(c["t0"]) + float(c["t1"])) / 2 < b for a, b in div):
            c["layout"] = "dividida"
            continue
        if c.get("layout") or c.get("camada", "legenda") != "legenda":
            continue
        meio = (float(c["t0"]) + float(c["t1"])) / 2
        if any(a <= meio < b for a, b in janelas):
            c["layout"] = "entre"

    r = plano.get("ritmo") or {}
    ENTRADA = float(r.get("entrada", ENTRADA))
    STAGGER = float(r.get("stagger", STAGGER))
    # a saída continua mais rápida que a entrada, como manda a regra
    SAIDA = float(r.get("saida", min(SAIDA, ENTRADA * 0.6)))
    # depois do ritmo: o corte dos cartões confere o tempo de leitura com a
    # entrada que vale neste plano
    _aplicar_presets(plano)


def _aplicar_presets(plano: dict) -> None:
    """Veste cada card de legenda com o preset dele. Sem `legenda` no plano nem
    nos cards, não toca em nada — o plano de antes sai byte a byte igual."""
    geral = plano.get("legenda")
    cards = plano.get("cards") or []
    if not geral and not any(c.get("legenda") for c in cards):
        return
    saida, n = [], 0
    for c in cards:
        nome = c.get("legenda", geral)
        if c.get("camada", "legenda") != "legenda" or not nome:
            saida.append(c)
            continue
        if nome not in PRESETS:
            raise SystemExit(f"legenda '{nome}' não existe. Presets: {', '.join(PRESETS)}")
        p = PRESETS[nome]
        if nome == "padrao":
            saida.append(c)
            continue
        c = {**c, "words": [dict(w) for w in c["words"]], "_preset": nome}
        c.setdefault("quebra", p.get("quebra", "nunca"))
        for k in _DO_CARD:
            if k in p:
                c.setdefault(k, json.loads(json.dumps(p[k])))
        # o cards_da_fala grava a fonte padrão em todo card: essa não é escolha
        # de ninguém. A letra da marca (desenho.fonte) é, e continua valendo.
        if c.get("fonte", FONTE_PADRAO) == FONTE_PADRAO:
            c["fonte"] = p.get("fonte", FONTE_PADRAO)
        lay = LAYOUTS.get(c.get("layout", "faixa"), LAYOUTS["faixa"])
        c.setdefault("corpo", round(lay["corpo"] * p.get("escala", 1.0)))
        if p.get("destaca") == "longa" and not any(
                w.get("enf") in ("chave", "punch") for w in c["words"]):
            # ponytail: a mais comprida é a palavra de conteúdo; quem quiser
            # outra marca `enf` no plano. Abaixo de 7 letras não destaca nada,
            # senão todo cartão ganha cor e nenhuma marca.
            cheias = [w for w in c["words"] if w.get("enf", "normal") == "normal"]
            longa = max(cheias, key=lambda w: len(w["tx"]), default=None)
            if longa and len(longa["tx"].strip(".,!?;:")) >= p.get("min_letras", 7):
                longa["enf"] = "chave"
        for w in c["words"]:
            if p.get("liso"):            # sem ênfase: todas as palavras no mesmo corpo e cor
                w["enf"] = "normal"
            if w.get("enf") == "chave" and p.get("fonte_chave"):
                w.setdefault("fonte", p["fonte_chave"])
            # SISTEMA: cada papel da palavra com a letra dele — a átona fina e
            # espaçada, a chave noutra família, o número condensado. É o que põe
            # duas ou três fontes no mesmo cartão (o dono reprovou em 05/10 a
            # legenda de uma fonte só: "monótona")
            papel = "numero" if any(ch.isdigit() for ch in w["tx"]) else w.get("enf", "normal")
            _veste(w, (p.get("papeis") or {}).get(papel, {}), c["corpo"])
        # o cartão do herói dirigido não se corta: o momento empilha a frase
        # em linhas (apoio em cima, herói embaixo), que é o desenho dele
        dirigido_aqui = p.get("momento") and any(w.get("heroi") for w in c["words"])
        for parte in ([c] if dirigido_aqui else _reparte(c, int(p.get("palavras", 99)))):
            if p.get("ciclo"):
                parte.setdefault("acento", p["ciclo"][n % len(p["ciclo"])])
            n += 1
            saida.append(parte)
    # o MOMENTO-CHAVE: um cartão a cada `cada` segundos, o que tem número ou
    # chave e tempo pra ser lido, troca de composição (e de layout, se pedir).
    # Plano DIRIGIDO marca a palavra com `"heroi": true` (quem leu a fala inteira
    # escolhe pelo sentido e pelo volume) e aí só ela vira momento.
    dirigido = any(w.get("heroi") for c in saida for w in c["words"])
    ultimo: dict[str, float] = {}
    for i, c in enumerate(saida):
        m = PRESETS.get(c.get("_preset"), {}).get("momento")
        if not m:
            continue
        if dirigido:
            heroi = next((w for w in c["words"] if w.get("heroi")), None)
        else:
            heroi = next((w for w in c["words"] if w.get("enf") in ("punch", "chave")
                          or any(ch.isdigit() for ch in w["tx"])), None)
        if (heroi is None or c["t1"] - c["t0"] < m.get("min_dur", 0.6)
                or (not dirigido and c["t0"] - ultimo.get(c["_preset"], -99.0) < m.get("cada", 3.0))):
            continue
        ultimo[c["_preset"]] = c["t0"]
        saida[i] = _momento(c, heroi, m)
    momentos = [c for c in saida if c.get("assinatura")]
    for j, c in enumerate(momentos):
        if c["t1"] - c["_pouso"] < SEGURA:
            # herói dito no fim do cartão ficava 0,4 s na tela: ele SEGURA no alto,
            # na camada dele, e a fala segue na legenda de baixo, como no trailer
            prox = momentos[j + 1]["t0"] - 0.05 if j + 1 < len(momentos) else 1e9
            fim = min(c["_pouso"] + SEGURA, prox, max(x["t1"] for x in saida))
            if fim > c["t1"]:
                c["t1"], c["camada"] = round(fim, 3), "heroi"
        if c.get("crava"):
            _crava(plano, c)
    plano["cards"] = saida


SEGURA = 1.4        # quanto o herói fica depois de cravar, no mínimo


CRAVA = 0.167       # 5 quadros: o crash zoom do Melies crava em menos de um segundo e fica


def _crava(plano: dict, c: dict) -> None:
    """A câmera crava no herói: aproxima em 5 quadros, com borrão de movimento,
    e segura andando devagar até o fim do cartão (O-QUE-USAR do Melies, item 3).
    Só onde o plano não move a câmera por conta própria."""
    a, fim = c["_t_in"], c["t1"]
    cenas = plano.setdefault("camera", [])
    if fim - a < CRAVA + 0.1 or any(float(x["t0"]) < fim and float(x["t1"]) > a
                                    for x in cenas if not x.get("_crava")):
        return
    z0, z1 = c["crava"]
    b = round(a + CRAVA, 3)
    c["_cam"] = [{"t0": a, "t1": b, "zoom": [1.0, z0], "ease": "crava", "borrao": 4, "_crava": True},
                 {"t0": b, "t1": fim, "zoom": [z0, z1], "ease": "sine", "_crava": True}]
    cenas += c["_cam"]


def _veste(w: dict, campos: dict, corpo: int) -> None:
    """Campos de palavra do preset (`fonte`, `track`, `cor`, `caixa`, `entrada`);
    `escala` vira o corpo final da palavra, já descontada a escala da ênfase."""
    for k, v in campos.items():
        if k == "escala":
            e = ENFASE.get(w.get("enf", "normal"), ENFASE["normal"])["escala"]
            w.setdefault("corpo", round(corpo * v / e))
        else:
            w.setdefault(k, v)


def _momento(c: dict, heroi: dict, m: dict) -> dict:
    """O cartão do momento-chave vira bloco, como título de filme: o que vem antes
    do herói numa linha de apoio pequena e espaçada, o herói enorme sozinho na
    dele, o resto embaixo. Cada linha é um papel, então a quebra é a composição,
    não a frase quebrada no meio."""
    i = c["words"].index(heroi)

    def apoio(ws: list[dict]) -> list[dict]:
        if not ws:
            return []
        w = {"tx": " ".join(corrigir(x["tx"]) for x in ws), "t0": ws[0]["t0"],
             "t1": ws[-1]["t1"], "enf": "filler"}
        _veste(w, m.get("apoio", {}), c["corpo"])
        return [w]

    h = {k: v for k, v in heroi.items() if k in ("tx", "t0", "t1", "emoji")}
    h["enf"] = "chave" if heroi.get("enf") != "punch" else "punch"
    _veste(h, m.get("heroi", {}), c["corpo"])
    novo = {**c, "words": apoio(c["words"][:i]) + [h] + apoio(c["words"][i + 1:]),
            "quebra": "palavra", "_momento": True}
    for k in ("layout", "atras", "alinhar", "entrelinha", "anim", "entrada",
              "assinatura", "crava", "luz", "sons", "contorno"):
        if k in m:
            novo[k] = m[k]
    if m.get("no_alto"):
        novo["_no_alto"] = True
    if m.get("assinatura"):
        # quem desenha o herói é a assinatura; o resto do cartão segue o normal
        h["_heroi"] = True
        novo["_t_in"] = round(max(c["t0"], h["t0"]), 3)
        novo["_pouso"] = round(novo["_t_in"] + CRAVA, 3)
        if m["assinatura"] == "colagem":
            # o flash é quando a palavra fica inteira, não quando a câmera chega
            n = sum(1 for ch in h["tx"] if ch.strip())
            novo["_pouso"] = round(novo["_t_in"] + (n - 1) * PASSO_COLAGEM + 0.12, 3)
        novo["_respiro"] = m.get("cada", 2.6)
    return novo


def _reparte(c: dict, teto: int) -> list[dict]:
    """Corta o card em cartões de até `teto` palavras cheias que cabem numa linha.

    O preset não quebra linha, ele corta no tempo: cada pedaço começa quando a
    primeira palavra dele é dita. Pedaço que fica curto demais pra ler (a régua
    é a do lint, `_tempo`) junta de novo com o vizinho.
    """
    ec = c.get("estreita", 1.0)
    esp = fonte(c["fonte"], c["corpo"]).getlength(" ") * ec

    def cabe(ws: list[dict]) -> bool:
        tot = esp * (len(ws) - 1)
        for w in ws:
            e = ENFASE.get(w.get("enf", "normal"), ENFASE["normal"])["escala"]
            tx = corrigir(w["tx"])
            tx = tx.upper() if w.get("caixa", c.get("caixa", "alta")) == "alta" else tx
            f = fonte(w.get("fonte", c["fonte"]), max(8, int((w.get("corpo") or c["corpo"]) * e)))
            tot += f.getlength(tx) * ec + w.get("track", 0.0) * f.size * max(0, len(tx) - 1)
        # 0.86 e não os 0.90 do `diagramar`: o contorno, a caixa e a sombra
        # saem da largura do texto
        return tot <= W_REF * c.get("largura", 0.86) * c.get("linhas", 1) * (0.94 if c.get("linhas", 1) > 1 else 1)

    grupos: list[list[dict]] = []
    cur: list[dict] = []
    for w in c["words"]:
        cheias = sum(x.get("enf") != "filler" for x in cur)
        if cur and ((w.get("enf") != "filler" and cheias >= teto) or not cabe(cur + [w])):
            grupos.append(cur)
            cur = []
        cur.append(w)
    if cur:
        grupos.append(cur)

    def montar(gs: list[list[dict]]) -> list[dict]:
        return [{**c, "words": g,
                 "t0": c["t0"] if i == 0 else g[0]["t0"],
                 "t1": gs[i + 1][0]["t0"] if i + 1 < len(gs) else c["t1"]}
                for i, g in enumerate(gs)]

    while len(grupos) > 1:
        curto = next((i for i, x in enumerate(montar(grupos)) if _tempo(x)), None)
        if curto is None:
            break
        # junta com o vizinho que ainda cabe na linha, o seguinte primeiro; se
        # nenhum cabe, o seguinte (o último, com o anterior) e o card encolhe
        lados = [j for j in (curto, curto - 1) if 0 <= j < len(grupos) - 1]
        j = next((j for j in lados if cabe(grupos[j] + grupos[j + 1])), lados[0])
        grupos[j:j + 2] = [grupos[j] + grupos[j + 1]]
    return montar(grupos)


RESPIRO_MIN = 0.12      # buraco pro card seguinte que justifica animar a saída
BASE = (255, 255, 255)
HOT = (245, 217, 10)
STROKE = (0, 0, 0)

_SYS = "/System/Library/Fonts"
_USR = str(Path.home() / "Library/Fonts")
_V2F = str(Path(__file__).resolve().parents[3] / "tools/v2/nucleo/fontes")
# As fontes que VIAJAM (OFL, assets/fontes/LICENCAS.md): mesmo caminho relativo no
# tronco e no kit. Todo preset tira a letra daqui; o resto do registro é da
# máquina do dono, pra plano escrito à mão.
_AF = str(Path(__file__).resolve().parents[1] / "assets/fontes")

# (arquivo, índice na .ttc, instância da fonte variável)
# Escolhidas medindo densidade de tinta e OLHANDO o render, não pelo nome.
# Trocar de fonte só marca a virada se os dois desenhos não se parecerem.
#
# As `capviral-*` vêm do pack pago do Matheus e vivem em ~/Library/Fonts, fora
# do repo — não versione arquivo de fonte aqui.
FONTES = {
    # peso pesado — trilho e herói
    "gotham": (f"{_USR}/capviral-gotham-cd.otf", 0, None),      # Cond Ultra, a mais densa
    "gotham-nr": (f"{_USR}/capviral-gotham-nr.otf", 0, None),   # Narrow Ultra, menos apertada
    "basement": (f"{_USR}/capviral-basement.otf", 0, None),     # Black, larga e moderna
    "creato": (f"{_AF}/CreatoDisplay-Black.otf", 0, None),     # Black geométrica (OFL, o mesmo arquivo do pack)
    "pilat": (f"{_USR}/capviral-pilat.ttf", 0, None),           # Extended Black — só palavra curta
    # o traço do quadro — estilo 7a, prancha rabiscada
    #
    # Mesma fonte que o board desenha, então a legenda deixa de ser uma camada
    # colada por cima e passa a ser a mesma mão. O repo guarda `.woff2` (é o que
    # o browser lê) e o PIL não abre woff2: o `.ttf` sai do subconjunto mais
    # completo (`a88b72a2`, 212 glifos, os 26 acentos do pt-BR conferidos) com
    # `fontTools` + `brotli`, e mora em ~/Library/Fonts como as outras.
    "excali": (f"{_AF}/Excalifont-Regular.ttf", 0, None),
    # contraste / seção
    "cooper": (f"{_USR}/capviral-cooper.ttf", 0, None),         # serifa 70s, beat retrô
    "slab": (f"{_SYS}/Supplemental/SuperClarendon.ttc", 7, None),
    "serifa": (f"{_AF}/PlayfairDisplay-Variable.ttf", 0, "Black"),
    # condensadas leves — lista, spec, número
    "akzidenz": (f"{_USR}/capviral-akzidenz.ttf", 0, None),
    "bebas": (f"{_AF}/BebasNeue-Regular.otf", 0, None),        # OFL, livre
    "altgothic": (f"{_USR}/capviral-altgothic.ttf", 0, None),
    # neutras
    "haas": (f"{_USR}/capviral-haas.otf", 0, None),             # Neue Haas 75 Bold
    "klavika": (f"{_USR}/capviral-klavika.otf", 0, None),       # técnica
    "helvetica": (f"{_SYS}/HelveticaNeue.ttc", 9, None),
    "futura": (f"{_SYS}/Supplemental/Futura.ttc", 4, None),
    "avenir": (f"{_SYS}/Avenir Next Condensed.ttc", 8, None),
    "redonda": (f"{_AF}/Nunito-Variable.ttf", 0, "Black"),
    "dm": (f"{_AF}/DMSans-Variable.ttf", 0, "Black"),
    "tiktok": (f"{_AF}/TikTokSans-Variable.ttf", 0, "Black"),
    "tiktok-filme": (f"{_AF}/TikTokSans-Variable.ttf", 0, "SemiBold"),   # a legenda do longo (27/10)
    # as livres no lugar das comerciais que os presets usavam (LICENCAS.md):
    # Futura Condensed ExtraBold, Cooper Black e Arial Black
    "jost": (f"{_AF}/Jost-Variable.ttf", 0, "ExtraBold"),
    "fraunces": (f"{_AF}/Fraunces-Variable.ttf", 0, (72, 900, 100, 0)),   # opsz, peso, suave, torto
    # a serifa da placa verde (`placa-serifa`): a Fraunces fina de contraste alto, com os
    # números alinhados. A medida do anúncio de referência pede mais estreita (`estreita`)
    "fraunces-fina": (f"{_AF}/Fraunces-Variable.ttf", 0, (72, 400, 0, 0)),
    "archivo": (f"{_AF}/ArchivoBlack-Regular.ttf", 0, None),
    # os de sempre
    "impact": (f"{_SYS}/Supplemental/Impact.ttf", 0, None),
    "black": (f"{_SYS}/Supplemental/Arial Black.ttf", 0, None),
    "pixel": (f"{_USR}/PixelifySans-Bold.ttf", 0, None),
    # cursivas do pack — acento conferido. Servem de ACENTO numa linha do bloco,
    # nunca no trilho: script em legenda rolando não se lê.
    "script": (f"{_USR}/capviral-script.ttf", 0, None),          # Vegan Style
    "script-fina": (f"{_USR}/capviral-script-fina.otf", 0, None),  # The Brightside
    # as duas letras do editorial (Nick): moram no núcleo do tools/v2, OFL com a
    # licença ao lado. Fora do repo (no kit) caem na Montserrat, como as outras.
    "inter": (f"{_AF}/Inter-opsz-wght.ttf", 0, "SemiBold"),
    "instrument": (f"{_AF}/InstrumentSerif-Italic.ttf", 0, None),
    "inter-regular": (f"{_AF}/Inter-opsz-wght.ttf", 0, "Regular"),
    "serifa-italica": (f"{_AF}/PlayfairDisplay-Italic-Variable.ttf", 0, "Black Italic"),   # OFL
}
# Padrão escolhido OLHANDO a legenda no tamanho real, não pela medição.
# Densidade de tinta premia condensada, e condensada pesada lê como barata:
# `gotham` (Cond Ultra) ganhou a métrica e perdeu feio na tela. Legenda quer
# letra larga e arejada, não a que enfia mais tinta no mesmo espaço.
FONTE_PADRAO = "creato"

# Fora do registro por não desenharem acento: `cubano` não tem Ç (vira buraco em
# "INTEGRAÇÃO") e `arcade` não tem nenhum. O cmap das duas MAPEIA os códigos —
# só o glifo é oco, então checagem por cmap passa e o vídeo sai errado.
ACENTOS = "ÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç"

# Pasta de origem no pack. A regra é UMA por grupo por reel: as famílias de uma
# mesma pasta se parecem, então duas delas no mesmo vídeo gastam uma troca de
# fonte sem marcar virada nenhuma.
GRUPO_FONTE = {
    "creato": "LEGENDAS", "gotham": "LEGENDAS", "gotham-nr": "LEGENDAS",
    "haas": "LEGENDAS",
    "basement": "YOUTUBE", "pilat": "YOUTUBE", "akzidenz": "YOUTUBE",
    "altgothic": "YOUTUBE", "bebas": "YOUTUBE",
    "cooper": "ANIMADO",
    "klavika": "GAMERS",
}

# zona vertical onde o card pode assentar, em fração da altura; o y exato é
# escolhido dentro dela pelo mapa de movimento
LAYOUTS = {
    "topo": {"zona": (0.05, 0.40), "h": 440, "corpo": 60},
    "centro": {"zona": (0.26, 0.70), "h": 520, "corpo": 78},
    # A faixa desceu 200px (0.55 -> 0.654): medido no short de webhook, a legenda
    # acabava em 1270 e a zona segura do rodape so comeca em 1470 -- 200px de
    # tela util que ninguem usava, com o quadro espremido logo acima.
    # o pe da caixa (zona[1]) e onde a legenda encosta -- 1470 e o comeco da
    # interface no rodape do Shorts/Reels, medido em set/2026
    "faixa": {"zona": (0.505, 0.765), "h": 500, "corpo": 64, "base": True},
    # O pé de 0.765 existe por causa da interface do Reels/Shorts. VSL toca numa
    # landing, sem interface nenhuma por cima — e na tela dividida o rosto vai
    # até o rodapé, então a zona da `faixa` cai na boca. Aqui o texto desce pro
    # peito, que é o único lugar livre.
    #
    # Anúncio reserva MAIS rodapé que Reels orgânico: "patrocinado", conta, a
    # prévia do texto principal e o botão do CTA, empilhados — não só legenda
    # e música. O pé de 0.765 da `faixa` desaparece atrás disso. Pé em 0.68 pro
    # criativo pago, mesma caixa, só mais alto.
    "faixa_criativo": {"zona": (0.42, 0.68), "h": 500, "corpo": 64, "base": True},
    "rodape": {"zona": (0.76, 0.93), "h": 420, "corpo": 62, "base": True},
    # Tela dividida: o texto senta EM CIMA DO DEGRADÊ, não abaixo dele. O painel
    # de 40% é sólido até 0.40 e dissolve até 0.535; a cabeça dele começa entre
    # 0.48 e 0.55 conforme se mexe. Nessa faixa a legenda fica grudada no
    # gráfico e ainda por cima do que já está dissolvendo — mais baixo ela
    # desgruda do painel, mais alto ela bate no conteúdo dele.
    "entre": {"zona": (0.385, 0.515), "h": 230, "corpo": 58},
    # Tela dividida do vídeo de celular (`tela_dividida.py`): a pessoa sobe até o cabelo em y ~1064 (1080x1920), então a
    # legenda termina em 1040 (regra do dono) e nunca cai no rosto ou no peito. A mesma zona da legenda de `e_dividida`.
    "dividida": {"zona": (932 / 1920, 1040 / 1920), "h": 108, "corpo": 52, "base": True},
    # A palavra-herói que passa ATRÁS de quem fala, no alto: o topo da cabeça
    # morde o pé das letras. No meio da tela a cabeça engole a palavra inteira (o
    # avatar enche o quadro; medido em 05/10, 4 de 4 heróis caíam pra frente,
    # em cima dos olhos). Começa abaixo da faixa de interface do alto do Reels.
    "alto": {"zona": (0.12, 0.46), "h": 560, "corpo": 64},
}

ENFASE = {
    "filler": {"escala": 0.92, "cor": (222, 222, 222), "s0": 0.88},
    "normal": {"escala": 1.00, "cor": BASE, "s0": 0.80},
    "chave": {"escala": 1.20, "cor": HOT, "s0": 0.70},
    "punch": {"escala": 1.50, "cor": (255, 64, 48), "s0": 0.58},
}

# PRESETS — o visual inteiro de um tipo de legenda, escolhido por nome:
# `"legenda": "fita"` na raiz do plano (ou num card só) e `desenho.legenda` no
# estilo da fábrica. Sem nome, nada muda: sai a legenda de sempre.
#
# A referência de cada um, medida em vídeo público, está em
# assets/legendas/REFERENCIA.md. Antes eram todos a mesma legenda na mesma cor,
# então cada preset traz a PRÓPRIA paleta, e ela vence o `acento` do estilo:
# com o azul da VSL por cima, os onze voltariam a ser um só.
#
# Campos de card (`fonte` `caixa` `modo` `anim` `contorno` `efeito` `placa`),
# mais: `escala` (corpo do layout × escala), `cor` (palavra normal), `acento`
# (a que acende e a chave) ou `ciclo` (acento que troca a cada cartão), `punch`,
# `palavras` (teto de palavras cheias por cartão), `destaca: "longa"` (a palavra
# longa do cartão vira chave), `fonte_chave` e `uso` (quando escolher).
#
# Minúscula lê menor que maiúscula no mesmo corpo: os presets em caixa da fala
# andam ~1,5× o corpo dos em caixa alta (o crivo de personas de 05/10 não leu a
# `minimal` a 70 px no celular).
#
# Preset nunca quebra linha: o cartão que não cabe numa linha é cortado no
# tempo (`_reparte`). Quebra no meio da frase é o que o dono mais reclama.
PRESETS: dict[str, dict] = {
    "padrao": {"uso": "a de sempre: Creato branca, a palavra falada acende na cor do estilo"},
    "filme": {
        "uso": "legenda de longo (27/10): TikTok Sans branca, caixa normal, até 2 linhas de ~42 letras embaixo, contorno preto grosso (6 px a 1080p) e sombra, sem cor e sem animação",
        "fonte": "tiktok-filme", "caixa": "original", "escala": 0.52, "horizontal": True, "cor": "#FFFFFF", "acento": "#FFFFFF",
        # 27/10, 2ª rodada: o contorno de 5 px e a sombra rala sumiam na camiseta branca. 6 px a 1080p (3,4 × k), arredondado
        # (o traço do PIL é redondo), e a sombra leva o contorno junto (`borda`), larga e escura. Largura 0,62: ~42 letras por linha
        "modo": "pop", "anim": "nenhuma", "liso": True, "linhas": 2, "quebra": "linhas", "largura": 0.62,
        "contorno": {"largura": 3.4, "cor": "#000000"},
        "efeito": {"sombra": {"dx": 0, "dy": 3, "blur": 8, "alpha": 0.9, "borda": True}}, "palavras": 24},
    "contorno": {
        "uso": "Hormozi: caixa alta com contorno grosso, a falada em vermelho; fala rápida, fundo agitado",
        "fonte": "montserrat", "escala": 1.15, "cor": "#FFFFFF", "acento": "#FF3B3B",
        "punch": "#F6FF14", "modo": "destaque",
        "contorno": {"largura": 10, "cor": "#000000"},
        "efeito": {"offset": {"dx": 0, "dy": 8, "cor": "#000000"}}, "palavras": 3},
    "caixa-branca": {
        "uso": "a do anúncio nº 1 em impressões: pílula clara, letra preta, duas palavras, corte seco",
        "fonte": "dm", "caixa": "original", "escala": 1.25, "cor": "#111111",
        "modo": "pop", "anim": "nenhuma", "contorno": 0,
        "placa": {"cor": "#F6EFF2", "opacidade": 1.0, "raio": 14}, "palavras": 2},
    "sombra-chave": {
        "uso": "a que domina nos anúncios escalados: branca em minúscula, sombra mole, palavra longa em laranja",
        "fonte": "redonda", "caixa": "original", "escala": 1.0, "cor": "#FFFCF8",
        "acento": "#F0882E", "modo": "pop", "contorno": 0,
        "efeito": {"sombra": {"dx": 0, "dy": 6, "blur": 14, "alpha": 0.85}},
        "palavras": 3, "destaca": "longa"},
    "caixa-cor": {
        "uso": "caixa magenta que anda atrás da palavra falada; tutorial, passo a passo",
        "fonte": "tiktok", "escala": 1.05, "cor": "#FFFFFF", "modo": "pop", "contorno": 0,
        "efeito": {"sombra": {"dx": 0, "dy": 5, "blur": 10, "alpha": 0.6},
                   "marca": {"fala": True, "cor": "#E6007E", "raio": 14}},
        "palavras": 3},
    "karaoke-ciclo": {
        "uso": "karaokê: a frase acende palavra a palavra e a cor troca a cada cartão; lista, energia",
        "fonte": "archivo", "escala": 1.0, "cor": "#FFFFFF",
        "ciclo": ["#22E0FF", "#FF4FA3", "#B8F23A"], "modo": "karaoke",
        "contorno": {"largura": 7, "cor": "#000000"}, "palavras": 4},
    "condensada": {
        "uso": "caixa alta condensada com sombra dura e a palavra longa em verde-neon; frase inteira, fala calma",
        "fonte": "bebas", "escala": 1.6, "cor": "#FFFFFF", "acento": "#29F725",
        "modo": "pop", "anim": "nenhuma", "contorno": {"largura": 3, "cor": "#000000"},
        "efeito": {"offset": {"dx": 7, "dy": 7, "cor": "#000000"}},
        "palavras": 4, "destaca": "longa"},
    "editorial": {
        "uso": "duas letras do Nick: sans em minúscula e a palavra longa em serifa itálica dourada; tom de autoridade",
        "fonte": "inter", "caixa": "original", "escala": 1.5, "cor": "#FFFFFF",
        "acento": "#EEBE22", "modo": "pop", "anim": "revela", "contorno": 0,
        "efeito": {"sombra": {"dx": 0, "dy": 5, "blur": 14, "alpha": 0.8},
                   "gradiente": {"de": "#FAF9B6", "para": "#EEBE22", "enf": "chave"}},
        "palavras": 3, "destaca": "longa", "fonte_chave": "instrument"},
    "manuscrita": {
        "uso": "letra de mão com a palavra falada sublinhada em coral; bastidor, conversa, tom pessoal",
        "fonte": "excali", "caixa": "original", "escala": 1.7, "cor": "#FFFFFF",
        "modo": "pop", "anim": "revela",
        # a Excalifont só tem um peso, fino: o contorno branco engrossa a letra
        # (o crivo de 05/10 não leu a fina no celular, 5 de 6)
        "contorno": {"largura": 3, "cor": "#FFFFFF"},
        "efeito": {"sombra": {"dx": 0, "dy": 6, "blur": 12, "alpha": 1.0},
                   "marca": {"fala": True, "forma": "sublinha", "cor": "#FF7A59"}},
        "palavras": 3},
    "fita": {
        "uso": "fita amarela atrás da linha, letra tinta e a falada em azul: a paleta da VSL",
        "fonte": "jost", "escala": 1.05, "cor": "#0B0D12", "acento": "#0640FB",
        "modo": "destaque", "contorno": 0,
        "efeito": {"marca": {"cor": "#F2C744", "raio": 0}}, "palavras": 3},
    "minimal": {
        "uso": "branca sem caixa nem contorno, a palavra falada sublinhada; explicação, fala longa",
        "fonte": "inter", "caixa": "original", "escala": 1.45, "cor": "#FFFFFF",
        "modo": "pop", "anim": "nenhuma", "contorno": 0,
        "efeito": {"sombra": {"dx": 0, "dy": 4, "blur": 10, "alpha": 0.9},
                   "marca": {"fala": True, "forma": "sublinha", "cor": "#FFFFFF"}},
        "palavras": 4},
    "gigante": {
        "uso": "uma palavra por vez, enorme, branco e amarelo alternando; gancho, emoji por cima quando o plano trouxer",
        "fonte": "fraunces", "escala": 1.9, "ciclo": ["#FFFFFF", "#FFD400"], "modo": "karaoke",
        "contorno": {"largura": 10, "cor": "#000000"},
        "efeito": {"offset": {"dx": 0, "dy": 10, "cor": "#000000"}}, "palavras": 1},

    # SISTEMAS DE CINEMA (05/10, depois do "monótonas" do dono). Os de cima trocam
    # a cor de uma fonte só; estes compõem: duas ou três famílias no mesmo cartão
    # por papel da palavra (`papeis`), salto de tamanho de 5x entre o herói e o
    # apoio, espaçamento de título, entrada com máscara, desfoque ou giro, e um
    # MOMENTO-CHAVE que muda a composição (e o layout) a cada ~3 s. As medidas
    # vêm dos templates de texto do Jitter (pesquisa/referencias-texto/).
    # TERCEIRA VOLTA (05/10, "me impressiona"): os três mais fortes ganham uma
    # ASSINATURA no momento-chave, que ninguém confunde: a palavra de ouro em 3D
    # atrás de você (trailer), a colagem de letras recortadas (revista), a máquina
    # de escrever e o carimbo (thriller). A câmera crava junto (`crava`), a luz
    # estoura (`luz`) e cada golpe tem som no pico (`sons`, publicados em
    # <saída>.cues.json pro som.py). `borrao` é o borrão de movimento de verdade:
    # o quadro em movimento é a média de N instantes do obturador.
    "trailer": {
        "uso": "trailer de cinema: condensada creme que voa com borrão de movimento; a cada 3-4 s a palavra em ouro 3D crava atrás de você, com a câmera, o clarão e o grave",
        "fonte": "bebas", "escala": 1.5, "cor": "#F4F1EA", "acento": "#E9C46A", "modo": "pop",
        "anim": "revela", "entrada": "voa", "contorno": 0, "borrao": 6, "pe": 0.745, "largura": 0.70,
        "efeito": {"sombra": {"dx": 0, "dy": 6, "blur": 6, "alpha": 1.0},
                   "gradiente": {"de": "#FFF6DA", "para": "#C9932B", "enf": "chave"}},
        "papeis": {"filler": {"fonte": "montserrat-media", "escala": 0.55, "track": 0.18, "caixa": "alta"},
                   "chave": {"escala": 1.25}},
        "palavras": 3, "destaca": "longa", "min_letras": 6,
        "momento": {"layout": "alto", "atras": True, "cada": 2.6, "entrelinha": 1.12,
                    "assinatura": "heroi3d", "crava": [1.16, 1.22], "luz": "ouro",
                    "contorno": {"largura": 2, "cor": "#000000"},
                    "sons": {"crava": "zoom-in", "golpe": "impact", "primeiro": "boom"},
                    "heroi": {"escala": 3.2, "track": 0.04},
                    "apoio": {"fonte": "montserrat-semi", "escala": 0.6, "track": 0.34, "caixa": "alta"}}},
    "documentario": {
        "uso": "documentário: alinhada à esquerda, sans leve com a palavra de peso em serifa itálica, tudo subindo de uma máscara",
        "fonte": "inter", "caixa": "original", "escala": 1.35, "cor": "#F3EEE4", "acento": "#F3EEE4",
        "modo": "pop", "anim": "revela", "entrada": "mascara", "alinhar": "esquerda",
        # a Instrument só tem um peso, fino: o contorno da mesma cor engrossa a
        # letra (o crivo de 05/10 não leu a serifa fina no celular, 3 de 6)
        "contorno": {"largura": 2, "cor": "#F3EEE4"},
        "efeito": {"sombra": {"dx": 0, "dy": 4, "blur": 10, "alpha": 1.0}},
        "papeis": {"filler": {"fonte": "inter-regular"}, "chave": {"fonte": "instrument", "escala": 1.85}},
        "palavras": 3, "destaca": "longa", "min_letras": 6,
        "momento": {"alinhar": "esquerda", "entrelinha": 0.92,
                    "heroi": {"fonte": "instrument", "escala": 3.1},
                    "apoio": {"fonte": "inter", "escala": 0.55, "track": 0.25, "caixa": "alta"}}},
    "thriller": {
        "uso": "suspense: máquina de escrever fria que aparece seca; a cada 3-4 s a frase se datilografa com cursor e a palavra-chave leva um carimbo vermelho, com a câmera e o tranco",
        "fonte": "mono", "caixa": "alta", "escala": 1.1, "cor": "#E6E6E6", "acento": "#E5322D",
        "modo": "pop", "anim": "revela", "entrada": "corte", "contorno": {"largura": 3, "cor": "#000000"},
        "borrao": 6, "pe": 0.745, "largura": 0.70,
        "efeito": {"sombra": {"dx": 0, "dy": 3, "blur": 6, "alpha": 0.9}},
        "papeis": {"filler": {"track": 0.12}, "normal": {"track": 0.08},
                   "chave": {"fonte": "bebas", "escala": 1.6, "entrada": "giro"},
                   "numero": {"fonte": "bebas", "escala": 1.6, "entrada": "giro"}},
        "palavras": 3, "destaca": "longa", "min_letras": 6,
        "momento": {"layout": "alto", "entrelinha": 1.15, "cada": 2.6, "no_alto": True,
                    "assinatura": "carimbo", "crava": [1.12, 1.15], "luz": "sombra",
                    "sons": {"maquina": "type", "golpe": "stamp", "primeiro": "hit"},
                    "heroi": {"fonte": "bebas", "escala": 3.0},
                    "apoio": {"fonte": "mono", "escala": 0.75, "track": 0.12, "entrada": "maquina"}}},
    "revista": {
        "uso": "capa de revista: sans limpa com a palavra-chave em serifa itálica coral; a cada 3-4 s a palavra se monta com letras recortadas de revista, coladas por cima da imagem, com o flash",
        "fonte": "dm", "caixa": "original", "escala": 1.2, "cor": "#FFFFFF", "acento": "#FF5A36",
        "modo": "pop", "contorno": 0, "entrada": "voa", "borrao": 6, "pe": 0.745, "largura": 0.70,
        "efeito": {"sombra": {"dx": 0, "dy": 5, "blur": 10, "alpha": 1.0}},
        "papeis": {"filler": {"escala": 0.8},
                   "chave": {"fonte": "serifa-italica", "escala": 1.7, "entrada": "mascara"}},
        "palavras": 3, "destaca": "longa", "min_letras": 6,
        # a colagem vai POR CIMA, colada na imagem: atrás da cabeça as letras
        # mordidas liam como "erro de render" (crivo de 05/10, 3 de 6 não leram)
        "momento": {"layout": "alto", "no_alto": True, "cada": 2.6, "entrelinha": 1.12,
                    "assinatura": "colagem", "crava": [1.10, 1.14], "luz": "flash",
                    "contorno": {"largura": 2, "cor": "#000000"},
                    "sons": {"crava": "papel", "golpe": "obturador", "fim": "thud"},
                    "heroi": {"fonte": "serifa-italica", "escala": 2.6},
                    "apoio": {"fonte": "dm", "escala": 0.62, "track": 0.3, "caixa": "alta",
                              "entrada": "mascara"}}},
    "comedia": {
        "uso": "comédia de pôster: geométrica espaçada em amarelo-pastel, a palavra-chave em serifa gorda rosa que estica e crava torta, o aparte escrito à mão",
        "fonte": "jost", "escala": 1.25, "cor": "#FFE9A8", "acento": "#FF8FA3", "modo": "pop",
        "entrada": "elastico", "contorno": 0,
        "efeito": {"sombra": {"dx": 0, "dy": 5, "blur": 10, "alpha": 1.0}},
        "papeis": {"normal": {"track": 0.08},
                   "filler": {"fonte": "excali", "escala": 0.85, "caixa": "original", "entrada": "giro"},
                   "chave": {"fonte": "fraunces", "escala": 1.35, "entrada": "elastico+giro"}},
        "palavras": 3, "destaca": "longa", "min_letras": 6,
        "momento": {"entrelinha": 0.95,
                    "heroi": {"fonte": "fraunces", "escala": 3.1, "entrada": "elastico+giro"},
                    "apoio": {"fonte": "excali", "escala": 0.75, "caixa": "original", "entrada": "giro"}}},
    # A legenda dos dois anúncios de editor de vídeo clonados (medida quadro a quadro em
    # 1080x1920, fichas 00 de videos/fabrica/clone-*): placa verde-escura de altura fixa
    # (84 px) que abraça a linha, serifa creme em minúscula, corte seco na entrada, na
    # troca e na saída. A frase inteira está na placa desde o primeiro quadro: a palavra
    # ainda não dita fica a 40 % e acende quando é dita (nada de ênfase, tamanho ou cor
    # extra). A letra é a Fraunces fina espremida a 0,77 — a referência é mais estreita e
    # tem x mais alto que qualquer serifa que viaja (a Instrument Serif Regular seria a
    # mesma, e não está no repo). A linha de base fica em 71,8 % da altura (y 1379 em 1920),
    # a placa 22 px abaixo dela, com a sombra só pra baixo.
    "placa-serifa": {
        "uso": "placa verde-escura com serifa creme em minúscula, corte seco, palavra dita acende; anúncio de editor de vídeo, depoimento, fala calma",
        "fonte": "fraunces-fina", "caixa": "original", "corpo": 66, "estreita": 0.77,
        "cor": "#6C8474", "acento": "#F4EFD8", "modo": "karaoke", "anim": "nenhuma", "seco": True,
        "contorno": 0, "liso": True, "linha_base": 0.7182, "largura": 0.42, "palavras": 4,
        "placa": {"cor": "#153327", "opacidade": 0.95, "raio": 6, "alto": 84, "sob": 22, "lado": 20,
                  "sombra": {"dy": 18, "blur": 14, "alpha": 0.55}}},
}
# o que o preset copia pro card; o resto é instrução pro `_aplicar_presets`
_DO_CARD = ("linhas", "caixa", "modo", "anim", "contorno", "efeito", "placa", "cor", "acento", "punch",
            "entrada", "alinhar", "entrelinha", "borrao", "pe", "largura",
            "corpo", "estreita", "linha_base", "seco")

MAX_WORDS = 4        # a quebra de linha é por largura medida, não por caractere
LEAD, TAIL = 0.10, 0.50

CORRECOES = tr.GLOSSARIO      # o glossário de marca mora no transcript.py

_cache_fonte: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

# A fonte livre que viaja junto (OFL). Quem não tem o pack nem a fonte do sistema
# cai nela: antes, a primeira legenda do aluno dava OSError, porque o padrão
# (`creato`) só existe no ~/Library/Fonts do Matheus. Mesmo caminho relativo no
# tronco (tools/video-use/assets) e no kit (skill/assets).
LIVRE = (str(Path(__file__).resolve().parents[1] / "assets/fontes/Montserrat[wght].ttf"), 0, "Black")
FONTES["montserrat"] = LIVRE
# pesos finos das mesmas variáveis: a linha de apoio espaçada dos sistemas de
# cinema pede contraste de PESO, não só de tamanho
FONTES["montserrat-media"] = (LIVRE[0], 0, "Medium")
FONTES["montserrat-semi"] = (LIVRE[0], 0, "SemiBold")     # o apoio que lê sobre fundo claro
FONTES["mono"] = (str(Path(LIVRE[0]).with_name("IBMPlexMono-Regular.ttf")), 0, None)   # OFL, no repo
_avisadas: set[str] = set()


def _por_caminho(nome: str) -> tuple[str, int, str | None] | None:
    """`marca/fontes/x.ttf#Black` → (caminho, 0, "Black"). Relativo parte da raiz da fábrica: a fonte
    da marca do aluno não mora no ~/Library/Fonts de ninguém, e no Windows nem existe esse lugar."""
    arq, _, inst = nome.partition("#")
    if Path(arq).suffix.lower() not in (".ttf", ".otf", ".ttc"):
        return None
    p = Path(arq)
    return (str(p if p.is_absolute() else Path(__file__).resolve().parents[3] / p), 0, inst or None)


def fonte(nome: str, corpo: int) -> ImageFont.FreeTypeFont:
    chave = (nome, corpo)
    if chave not in _cache_fonte:
        caminho, idx, inst = FONTES.get(nome) or _por_caminho(nome) or FONTES[FONTE_PADRAO]
        if not Path(caminho).exists():
            if nome not in _avisadas:
                print(f"  fonte '{nome}' não está nesta máquina; usando a Montserrat", file=sys.stderr)
                _avisadas.add(nome)
            caminho, idx, inst = LIVRE
        f = ImageFont.truetype(caminho, corpo, index=idx)
        if isinstance(inst, tuple):    # eixos à mão, quando a instância com nome não basta
            f.set_variation_by_axes(list(inst))
        elif inst:                     # fonte variável cai na instância fina sem isto
            f.set_variation_by_name(inst)
        _cache_fonte[chave] = f
    return _cache_fonte[chave]


def acentos_faltando(nome: str, corpo: int = 64) -> str:
    """Acentos que a fonte NÃO desenha. Renderiza e mede tinta — glifo oco
    passa em qualquer checagem de cmap."""
    f = fonte(nome, corpo)

    def tinta_de(ch: str) -> int:
        im = Image.new("L", (corpo * 3, corpo * 3), 0)
        ImageDraw.Draw(im).text((corpo * 1.5, corpo * 1.5), ch, font=f,
                                fill=255, anchor="mm")
        return int((np.array(im) > 128).sum())

    piso = tinta_de("H") * 0.12
    return "".join(c for c in ACENTOS if tinta_de(c) < piso)


def _larg(d: ImageDraw.ImageDraw, tx: str, f: ImageFont.FreeTypeFont, track: float = 0.0) -> float:
    """Largura do texto com o espaçamento entre letras (`track`, em fração do corpo)."""
    return d.textlength(tx, font=f) + track * f.size * max(0, len(tx) - 1)


def _escreve(d: ImageDraw.ImageDraw, xy: tuple[float, float], tx: str,
             f: ImageFont.FreeTypeFont, track: float = 0.0, **kw) -> None:
    """`d.text` centrado em xy, com espaçamento entre letras. O PIL não tem
    letter-spacing: com `track` a palavra sai letra a letra (e perde o kerning,
    que no espaçamento largo de título não aparece)."""
    if not track:
        d.text(xy, tx, font=f, anchor="mm", **kw)
        return
    x = xy[0] - _larg(d, tx, f, track) / 2
    for ch in tx:
        d.text((x, xy[1]), ch, font=f, anchor="lm", **kw)
        x += d.textlength(ch, font=f) + track * f.size


corrigir = tr.corrigir_termo


# ------------------------------------------------------------ curvas

def suave(p: float) -> float:
    """ease-out cúbico, saturado."""
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def mola(p: float, amp: float) -> float:
    """0->1 com overshoot `amp`, amortecida. f(0)=0, assenta em 1."""
    if p >= 1.0:
        return 1.0
    if p <= 0.0:
        return 0.0
    e = math.exp(-5.5 * p)
    return 1 - e * math.cos(3.6 * p) + amp * e * math.sin(3.6 * p)


# ------------------------------------------------------------ mapas da cena

def preparar_overlays(cards: list[dict], fps: int, dur: float, largura: int,
                      altura: int, tmp: Path) -> dict[int, tuple[Path, dict]]:
    """Extrai os frames dos mattes usados pelos cards.

    O pack do CapCut veio com os RGB truncados e os `.alpha.mp4` INTEIROS. Pra
    gráfico monocromático isso basta: o matte é o desenho. Colorir o estêncil
    reconstrói a placa, a moldura, a barra — e ainda deixa escolher a cor, que o
    mp4 pronto não deixaria.
    """
    mapa: dict[int, tuple[Path, dict]] = {}
    for j, c in enumerate(cards):
        ov = c.get("overlay")
        if not ov:
            continue
        src = Path(ov["arquivo"]).expanduser()
        if not src.exists():
            print(f'  overlay não achado: {src}')
            continue
        sub = tmp / f"ov{j}"
        sub.mkdir(parents=True, exist_ok=True)
        # Asset com alpha próprio (ProRes 4444 recuperado) sai em RGBA e entra
        # com a COR ORIGINAL. Matte cru sai em cinza e vira estêncil colorível.
        # Distinguir importa: extrair o ProRes como gray jogaria a cor fora.
        ov["_rgba"] = not src.name.endswith(".alpha.mp4")
        ff.run(
            ["ffmpeg", "-v", "error", "-ss", f'{ov.get("inicio", 0):.3f}',
             "-t", f'{c["t1"] - c["t0"]:.3f}', "-i", str(src),
             "-vf", f"fps={fps}",
             "-pix_fmt", "rgba" if ov["_rgba"] else "gray",
             f"{sub}/%05d.png"], quiet=True)
        base = int(round(c["t0"] * fps))
        for f in sorted(sub.glob("*.png")):
            idx = base + int(f.stem) - 1
            if 0 <= idx < int(dur * fps):
                mapa[idx] = (f, ov)
    return mapa


def preparar_brolls(brolls: list[dict], fps: int, dur: float, largura: int,
                    tmp: Path, base_dir: Path,
                    video_fonte: Path | None = None, altura: int = 0
                    ) -> dict[int, list[tuple[Path, dict, float]]]:
    """Trilha de b-roll, independente dos cards.

    Não cabe como campo de card porque os clipes SE SOBREPÕEM: no reel do kit o
    painel de fundo fica 12s no ar enquanto os gráficos entram e saem por cima.
    Amarrar b-roll a card forçaria um clipe por card e perderia a camada.

    Devolve {frame: [(png, cfg, t_relativo), ...]} na ordem de empilhamento.
    """
    mapa: dict[int, list[tuple[Path, dict, float]]] = {}
    for j, b in enumerate(brolls):
        src = Path(b["arquivo"])
        if not src.is_absolute():
            src = base_dir / src
        if not src.exists():
            print(f"  b-roll não achado: {src}")
            continue
        t0, t1 = float(b["t0"]), float(b["t1"])
        # `alt` manda na ALTURA ocupada, não na largura. Pensar por largura é
        # indireto demais: o que importa é quanto da tela o painel toma, e o
        # degradê come parte dele — com `alt` o alvo é o que se vê.
        if b.get("alt") and altura:
            alvo_h = int(altura * float(b["alt"]))
            larg = None                      # calculado abaixo pelo aspecto
        else:
            alvo_h = None
            larg = int(largura * float(b.get("larg", 0.9)))

        # Cor média do fundo na faixa onde o painel vai dissolver. Rampar só o
        # alpha não mescla: painel branco a 40% sobre parede roxa continua sendo
        # uma mancha clara. Puxar a COR do painel pra cor do ambiente conforme
        # desce é o que faz ele sumir em vez de ficar translúcido.
        if b.get("encaixe") == "topo" and b.get("mescla") and video_fonte:
            amostra = ff.run(
                ["ffmpeg", "-v", "error", "-ss", f"{(t0 + t1) / 2:.3f}",
                 "-i", str(video_fonte), "-frames:v", "1",
                 "-vf", "crop=iw:ih/6:0:ih/3,scale=1:1", "-f", "rawvideo",
                 "-pix_fmt", "rgb24", "-"], capture=True, binario=True, quiet=True).stdout
            if len(amostra) >= 3:
                b["_cor_fundo"] = tuple(amostra[:3])
        sub = tmp / f"br{j}"
        sub.mkdir(parents=True, exist_ok=True)
        ff.run(
            ["ffmpeg", "-v", "error", "-ss", f'{b.get("inicio", 0):.3f}',
             "-t", f"{t1 - t0:.3f}", "-i", str(src),
             # Largura CHEIA sempre; a altura é que se ajusta, cortando na
             # vertical pelo centro. Escalar pela altura deixava sobra roxa nas
             # laterais — painel que não sangra de lado a lado lê como card.
             "-vf", (f"fps={fps},scale={largura}:-2,"
                     f"crop={largura}:'min(ih,{alvo_h})':0:'(ih-min(ih,{alvo_h}))/2'"
                     if alvo_h else f"fps={fps},scale={larg}:-2"),
             # `alfa` = a peça flutua sobre o vídeo com a transparência dela
             # própria (ProRes 4444). Sem forçar rgba aqui o alpha se perde na
             # escrita do PNG e a peça volta a ser um retângulo.
             *(["-pix_fmt", "rgba"] if b.get("alfa") else []),
             f"{sub}/%05d.png"], quiet=True)
        # COR DO RODAPÉ, medida UMA VEZ. O degradê replicava a última linha de
        # CADA quadro: numa gravação de tela a borda é preta e vira uma barra;
        # e quando a câmera dá zoom a linha muda de conteúdo, então o degradê
        # pula de cor no meio do plano. Aqui a cor sai da faixa de baixo do
        # PRIMEIRO quadro, ignorando linha preta de borda, e não muda mais.
        quadros = sorted(sub.glob("*.png"))
        if quadros and b.get("encaixe") == "topo" and b.get("mescla"):
            px = np.array(Image.open(quadros[0]).convert("RGB"))
            faixa = px[max(0, px.shape[0] - max(3, px.shape[0] // 30)):]
            vivas = faixa[faixa.reshape(-1, 3).mean(axis=1).reshape(faixa.shape[0], -1)
                          .mean(axis=1) > 12] if faixa.size else faixa
            if vivas.size:
                b["_rodape"] = tuple(int(v) for v in
                                     np.median(vivas.reshape(-1, 3), axis=0))
        if not quadros:
            continue
        # SEGURA O ÚLTIMO QUADRO quando o clipe é mais curto que a janela. Um
        # clipe de 4.80s numa janela de 4.89s deixa três quadros sem peça — e
        # numa tela dividida esses três mostram a tarja preta. Congelar o fim é
        # invisível; sumir não é.
        base = int(round(t0 * fps))
        precisa = int(round(t1 * fps)) - base
        for i in range(precisa):
            idx = base + i
            if 0 <= idx < int(dur * fps):
                mapa.setdefault(idx, []).append(
                    (quadros[min(i, len(quadros) - 1)], b, i / fps))
    return mapa


def _v2():
    """Import tardio da biblioteca de peças: só quem põe peça por cima precisa dela."""
    v2 = Path(__file__).resolve().parents[2] / "v2"
    if str(v2) not in sys.path:
        sys.path.insert(0, str(v2))
    import v2 as m
    return m


ESCURO_SAT, ESCURO_BRI, ESCURO_RAMPA = 0.45, 0.10, 0.3   # o fundo atrás da carta: perde 55% da cor e 10% de luz, em 0,3 s


def fundo_escuro(brolls: list[dict], dur: float) -> str:
    """O filtro `eq` que escurece e tira a cor do VÍDEO enquanto uma peça com `escurece` está na tela (a carta, a mão
    de cartas): o olho vai pra carta e o fundo vira pano de fundo. Rampa de ESCURO_RAMPA s dos dois lados; vazio se
    nenhuma peça pede."""
    janelas = [(float(b["t0"]), min(float(b["t1"]), dur)) for b in brolls if b.get("escurece") and float(b["t0"]) < dur]
    if not janelas:
        return ""
    r = ESCURO_RAMPA
    p = "+".join(f"min(clip((t-{a:.3f})/{r},0,1),clip(({z:.3f}-t)/{r},0,1))" for a, z in janelas)
    return (f"eq=saturation='1-{1 - ESCURO_SAT}*clip({p},0,1)':brightness='-{ESCURO_BRI}*clip({p},0,1)':eval=frame")


def _sobre_nativo(b: dict) -> bool:
    """A peça da biblioteca (a fábrica marca `_peca`) com alfa vai pelo overlay nativo do v2: a
    entrada, a saída e a sombra são dela. Fica no quadro a quadro o que precisa da pessoa
    recortada (`atras`), o painel que sangra no topo e a entrada deslizando."""
    return bool(b.get("_peca") and b.get("alfa") and not b.get("atras") and not b.get("encaixe")
                and b.get("anim", "static") not in ("esquerda", "direita"))


def separa_nativas(brolls: list[dict]) -> tuple[list[dict], list[dict]]:
    """(quadro a quadro, nativas). A peça nativa vai por baixo da camada de quadros; um b-roll de vídeo
    de quadro inteiro (as mãos) a taparia, então a peça que cruza um vai pro quadro a quadro, por cima dele."""
    tampa = [b for b in brolls if not b.get("_peca") and float(b.get("alt") or 0) >= 1.0 and float(b["t1"]) > float(b["t0"])]
    cruza = lambda b: any(float(b["t0"]) < float(c["t1"]) and float(c["t0"]) < float(b["t1"]) for c in tampa)
    nativas = [b for b in brolls if _sobre_nativo(b) and not cruza(b)]
    resto = [b for b in brolls if b not in nativas]
    return ([b for b in resto if not _sobre_nativo(b)] + [b for b in resto if _sobre_nativo(b)]), nativas


def _peca_nativa(b: dict, fps: int, largura: int, altura: int) -> dict:
    """O b-roll da peça no vocabulário do `v2.grafo_sobre`, com a mesma geometria do
    `pintar_broll`: `alt` manda na altura (largura cheia, corte no meio), senão `larg`."""
    k = largura / W_REF
    alto = int(altura * float(b["alt"])) if b.get("alt") and altura else None
    larg = largura if alto else int(largura * float(b.get("larg", 0.9)))
    return {"arquivo": b["arquivo"], "inicio": float(b.get("inicio", 0)),
            "em": round(float(b["t0"]) * fps) / fps, "ate": round(float(b["t1"]) * fps) / fps,
            "largura": larg, "altura_max": alto,
            "x": int((largura - larg) / 2 + float(b.get("x", 0)) * k), "y": int(float(b.get("y", 120)) * k)}


def pintar_broll(caminho: Path, b: dict, rel: float, largura: int,
                 altura: int) -> Image.Image:
    """Um clipe de b-roll posicionado, com entrada e fade."""
    im = Image.open(caminho).convert("RGBA")
    k = largura / W_REF
    dur = float(b["t1"]) - float(b["t0"])
    encaixe = b.get("encaixe")          # "topo" = sangra no alto, sem cantos
    ph = im.height                      # altura do painel SEM a mescla

    if b.get("alfa"):
        # a máscara do clipe É o recorte: nada de faixa, nada de canto
        # arredondado. Encostar aqui apaga a transparência que a peça trouxe.
        pass
    elif encaixe == "topo":
        # Painel encostado no topo com degradê no rodapé. Card flutuando com
        # sombra lê como adesivo colado por cima; sangrar e dissolver a borda
        # faz o gráfico e a câmera lerem como UMA imagem.
        faixa = int(b.get("mescla", 150) * k)
        if faixa > 0:
            # A mescla ESTENDE o painel pra baixo, não come por dentro. Rampar
            # dentro da altura pedida desperdiça um terço do gráfico: o original
            # fica sólido até o fim e corta seco, e o que se quer é o mesmo
            # conteúdo com a borda dissolvendo depois dele.
            # cor fixa quando `preparar_brolls` mediu; senão, a última linha
            rod = b.get("_rodape")
            rodape = (Image.new("RGB", (im.width, faixa), tuple(rod)).convert("RGBA")
                      if rod else
                      im.crop((0, im.height - 1, im.width, im.height)).resize(
                          (im.width, faixa), Image.NEAREST))
            maior = Image.new("RGBA", (im.width, im.height + faixa))
            maior.paste(im, (0, 0))
            maior.paste(rodape, (0, im.height))
            im = maior
        masc = Image.new("L", im.size, 255)
        if faixa > 0:
            ramp = ImageOps.invert(Image.linear_gradient("L").resize((im.width, faixa)))
            masc.paste(ramp, (0, im.height - faixa))
            cf = b.get("_cor_fundo")
            if cf:
                # a cor do painel caminha pra cor do ambiente na mesma rampa.
                # Só com alpha, branco a 40% sobre parede roxa ainda é mancha
                # clara; com a cor junto, ele se dissolve no fundo.
                alvo = Image.new("RGB", (im.width, faixa), tuple(int(v) for v in cf))
                trecho = im.crop((0, im.height - faixa, im.width, im.height)).convert("RGB")
                im.paste(Image.composite(trecho, alvo, ramp), (0, im.height - faixa))
        im.putalpha(masc)
    elif b.get("raio", 22):
        masc = Image.new("L", im.size, 0)
        ImageDraw.Draw(masc).rounded_rectangle(
            [0, 0, im.width - 1, im.height - 1], radius=int(b.get("raio", 22) * k), fill=255)
        im.putalpha(masc)

    fade = float(b.get("fade", 0.22))
    # `fade_saida` separado da entrada: painel que termina junto com a cena da
    # câmera não pode desaparecer ANTES do corte. Se desaparece, os últimos
    # quadros mostram a tarja preta da tela dividida — que é o que sobra quando
    # o painel sai e a câmera ainda está na janela.
    fade_out = float(b.get("fade_saida", fade))
    a = 1.0
    if fade > 0 or fade_out > 0:
        a = min(suave(rel / fade) if fade > 0 else 1.0,
                suave((dur - rel) / fade_out) if fade_out > 0 else 1.0)
    # entrada deslizando: `anim` diz de que lado o clipe entra
    dx = 0.0
    anim = b.get("anim", "static")
    if anim in ("esquerda", "direita") and rel < fade * 2:
        p = suave(rel / max(0.05, fade * 2))
        dx = (1 - p) * largura * (-0.55 if anim == "esquerda" else 0.55)
    # DESCE E SOBE, contínuo: y = -PH + PH·p, com a mesma `curva_tela` que
    # move a câmera. Amarrado à janela, `aplicar_plano` pôs as durações da cena
    # de câmera em `_entra`/`_sai`; solto, vale o `entra`/`sai` (ou `sobe`) dele.
    p_tela = 1.0
    if encaixe == "topo" and not b.get("alfa"):
        ent = float(b.get("_entra", b.get("entra", 0)) or 0)
        sai = float(b.get("_sai", b.get("sai", b.get("sobe", 0))) or 0)
        p_tela = curva_tela(rel, dur, ent, sai)
        if p_tela <= 0.001:
            return Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    if a <= 0.01:
        return Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    im.putalpha(im.split()[3].point(lambda v: int(v * a)))

    fundo = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    x = int((largura - im.width) / 2 + b.get("x", 0) * k + dx)
    y = int(b.get("y", 120) * k)
    if b.get("alfa"):
        # posiciona por x/y como qualquer objeto e segue pro passo da sombra:
        # peça que flutua sobre a imagem precisa da sombra pra ler em cima de
        # uma parede clara tanto quanto de uma escura
        pass
    elif encaixe == "topo":
        # sangra: no alto, e a sombra some — a borda agora é o degradê
        x, y = int(dx), int(-ph + ph * p_tela)
        fundo.paste(im, (x, y), im)
        if y > 0:
            # a mola passa de 1 e o painel desce uns px além do topo: a linha
            # de cima dele estica pra cobrir o vão, senão o vão é tarja preta
            topo = im.crop((0, 0, im.width, 1)).resize((im.width, y), Image.NEAREST)
            fundo.paste(topo, (x, 0), topo)
        return fundo
    if b.get("sombra", True):
        s = Image.new("RGBA", im.size, (0, 0, 0, 0))
        s.putalpha(im.split()[3])
        s = s.filter(ImageFilter.GaussianBlur(16 * k))
        fundo.paste(s, (x, y + int(12 * k)), s)
    fundo.paste(im, (x, y), im)
    return fundo


def preparar_telas(cards: list[dict], fps: int, dur: float, largura: int,
                   tmp: Path) -> dict[int, tuple[Path, dict]]:
    """Recorte de outra gravação entrando como card de tela.

    É o que faz o reel ser SOBRE o produto em vez de cabeça falante: quando ele
    diz "eu sei meu faturamento", a tela do faturamento aparece. A fonte é
    qualquer vídeo — no reel-crm vem das aulas do curso, que são captura 2560x1440.
    """
    mapa: dict[int, tuple[Path, dict]] = {}
    for j, c in enumerate(cards):
        tl = c.get("tela")
        if not tl:
            continue
        src = Path(tl["arquivo"]).expanduser()
        if not src.exists():
            print(f"  tela não achada: {src}")
            continue
        sub = tmp / f"tl{j}"
        sub.mkdir(parents=True, exist_ok=True)
        larg = int(largura * float(tl.get("larg", 0.92)))
        # `crop` antes do scale: a captura da aula traz a cabeça em PiP no canto,
        # e levar isso pro reel põe dois rostos na tela ao mesmo tempo.
        vf = f"crop={tl['crop']}," if tl.get("crop") else ""
        ff.run(
            ["ffmpeg", "-v", "error", "-ss", f'{tl.get("inicio", 0):.3f}',
             "-t", f'{c["t1"] - c["t0"]:.3f}', "-i", str(src),
             "-vf", f"{vf}fps={fps},scale={larg}:-2", f"{sub}/%05d.png"], quiet=True)
        base = int(round(c["t0"] * fps))
        for f in sorted(sub.glob("*.png")):
            idx = base + int(f.stem) - 1
            if 0 <= idx < int(dur * fps):
                mapa[idx] = (f, tl)
    return mapa


def pintar_tela(caminho: Path, tl: dict, largura: int, altura: int) -> Image.Image:
    """Canto arredondado + sombra. Retângulo cru colado no vídeo lê como erro
    de montagem; o arredondamento é o que diz 'isto é uma janela'."""
    im = Image.open(caminho).convert("RGBA")
    k = largura / W_REF
    raio = int(tl.get("raio", 26) * k)
    masc = Image.new("L", im.size, 0)
    ImageDraw.Draw(masc).rounded_rectangle([0, 0, im.width - 1, im.height - 1],
                                           radius=raio, fill=255)
    im.putalpha(masc)

    fundo = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    x = int((largura - im.width) / 2 + tl.get("x", 0) * k)
    y = int(tl.get("y", 120) * k)
    if tl.get("sombra", True):
        s = Image.new("RGBA", im.size, (0, 0, 0, 0))
        s.putalpha(masc)
        s = s.filter(ImageFilter.GaussianBlur(18 * k))
        fundo.paste(s, (x, y + int(14 * k)), s)
    fundo.paste(im, (x, y), im)
    return fundo


def pintar_overlay(caminho: Path, ov: dict, largura: int, altura: int) -> Image.Image:
    """Gráfico do pack posicionado no quadro.

    Dois caminhos: asset com cor própria entra como está; matte cinza vira
    estêncil e ganha a cor que o plano pedir. `cor:` força o estêncil mesmo
    num asset colorido — útil quando a cor original não serve.
    """
    forca = float(ov.get("forca", 1.0))
    esc = float(ov.get("escala", 1.0))
    if ov.get("_rgba") and not ov.get("cor"):
        g = Image.open(caminho).convert("RGBA")
        if esc != 1.0:
            g = g.resize((max(1, int(g.width * esc)), max(1, int(g.height * esc))),
                         Image.LANCZOS)
        if forca != 1.0:
            g.putalpha(g.split()[3].point(lambda v: min(255, int(v * forca))))
    else:
        im = Image.open(caminho)
        m = im.split()[3] if im.mode == "RGBA" else im.convert("L")
        if esc != 1.0:
            m = m.resize((max(1, int(m.width * esc)), max(1, int(m.height * esc))),
                         Image.LANCZOS)
        if forca != 1.0:
            m = m.point(lambda v: min(255, int(v * forca)))
        g = Image.new("RGBA", m.size, rgb(ov.get("cor", "#FFFFFF")) + (0,))
        g.putalpha(m)
    m = g
    fundo = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    k = largura / W_REF
    # x/y são DESLOCAMENTO a partir da posição nativa, e aceitam negativo: o
    # matte já vem posicionado em 1080x1920 e quase sempre só precisa de ajuste.
    x = int((largura - m.width) / 2 + ov.get("x", 0) * k)
    y = int((altura - m.height) / 2 + ov.get("y", 0) * k)
    fundo.paste(g, (x, y), g)          # paste aceita offset negativo, alpha_composite não
    return fundo


def probe(video: Path) -> tuple[int, int, float]:
    """largura, altura e DURAÇÃO em segundos.

    Devolvia `fps` no lugar da duração, e quem chama nomeia o terceiro valor
    `dur_video`. Como todo fps do pipeline é 30, `dur` virava 30 e a linha
    `cards = [c for c in cards if c["t0"] < dur]` jogava fora toda legenda
    depois do meio minuto. No short de webhook: 283 cards no plano, 74 no vídeo.

    A duração é a da IMAGEM, não a do formato: o AAC fecha em pacote de 1024 amostras e o som do
    bloco passa da imagem em até 1 quadro (o title drop do Treinando #3: 5,000 s de imagem, 5,034 de
    som). Com `-t` do formato, o overlay repetia o último quadro e o vídeo "travava" na emenda.
    """
    p = ff.probe(video)
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                "-of", "csv=p=0", str(video)], capture=True, quiet=True, check=False)
    try:
        imagem = float((r.stdout or "").strip())
    except ValueError:
        imagem = 0.0
    return p.largura, p.altura, (min(imagem, p.duracao) if imagem and p.duracao else p.duracao) or 30.0



def mapa_volume(video: Path, dur: float, taxa: int = 100) -> np.ndarray:
    """RMS da fala em janelas de 10ms, normalizado pelo p90 do clipe."""
    raw = ff.run(
        ["ffmpeg", "-v", "error", "-t", f"{dur}", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture=True, binario=True, quiet=True, check=False).stdout
    if not raw:
        return np.zeros(1, dtype=np.float32)
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    passo = 8000 // taxa
    n = len(a) // passo
    if n < 1:
        return np.zeros(1, dtype=np.float32)
    rms = np.sqrt((a[:n * passo].reshape(n, passo) ** 2).mean(axis=1))
    p90 = float(np.percentile(rms, 90)) or 1.0
    return np.clip(rms / p90, 0.0, 1.0).astype(np.float32)


def fundo_dos_cards(video: Path, cards: list[dict], altura: int, k: float) -> None:
    """A luminância do que há atrás de cada legenda, tirada do próprio vídeo (4 quadros por segundo, 108x192), no
    `_fundo` do card. Sem ela a cor de destaque do estilo caía em azul sobre a camisa preta; com ela, `cor_da_palavra`
    puxa a cor até o contraste de 4,5 (`legivel`). Card que já traz `_fundo` (tela cheia com peça) fica como está."""
    quer = [c for c in cards if c.get("camada", "legenda") == "legenda" and "_fundo" not in c and "_y" in c]
    if not quer:
        return
    w, h = 108, 192
    raw = ff.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=4,scale={w}:{h}", "-f", "rawvideo",
                  "-pix_fmt", "rgb24", "-"], capture=True, binario=True, quiet=True, check=False).stdout
    n = len(raw) // (w * h * 3)
    if not n:
        return
    quadros = np.frombuffer(raw[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    for c in quer:
        lay = LAYOUTS.get(c["layout"], LAYOUTS["faixa"])
        y0 = c["_y"] * 1920 / altura
        y1 = y0 + lay["h"] * k * 1920 / altura
        i0 = min(n - 1, int(c["t0"] * 4))
        i1 = max(i0 + 1, min(n, int(c["t1"] * 4) + 1))
        c["_fundo"] = float(np.mean([luminancia_do_vao(q, y0, y1) for q in quadros[i0:i1]]))


def volume_de(vol: np.ndarray, t0: float, t1: float, taxa: int = 100) -> float:
    i0, i1 = int(t0 * taxa), max(int(t1 * taxa), int(t0 * taxa) + 1)
    trecho = vol[i0:i1]
    return float(trecho.mean()) if trecho.size else 0.5


# ------------------------------------------------------------ plano

def carregar_palavras(caminho: Path, ate: float | None) -> list[dict]:
    return [{"t0": w["start"], "t1": w["end"], "tx": corrigir(w["text"]).upper()}
            for w in tr.palavras(caminho, ate)]


def finalizar(cards: list[dict]) -> list[dict]:
    """Normaliza e resolve a saída de cada card DENTRO DA SUA CAMADA.

    Reel real tem cartela de gancho parada no topo enquanto a legenda rola
    embaixo. São duas sequências independentes: se a saída do gancho for
    calculada contra o card de legenda que vem depois, ele pisca sem motivo.
    """
    cards = sorted(cards, key=lambda c: c["t0"])
    for c in cards:
        c.setdefault("layout", "faixa")
        c.setdefault("anim", "entra")
        c.setdefault("modo", "destaque")
        c.setdefault("camada", "legenda")
        for w in c["words"]:
            w.setdefault("enf", "normal")
            # O `CORRECOES` mora aqui, e não só no caminho `--words`.
            #
            # Ele estava aplicado num lugar só -- a leitura do transcript cru --
            # e todo plano dirigido passava direto. O short de webhook saiu com
            # "NO NTYN VOCÊ PÕE" e "fingindo ser a QWIFI" em letra garrafal,
            # com o termo novo já na tabela. Nome de ferramenta escrito errado
            # na legenda é pior que legenda nenhuma.
            w["tx"] = corrigir(w["tx"])
            # caixa alta é o padrão de legenda, mas script em CAIXA ALTA não se
            # lê: as ligaduras do desenho pressupõem minúscula.
            if w.get("caixa", c.get("caixa", "alta")) == "alta":
                w["tx"] = w["tx"].upper()

    for camada in {c["camada"] for c in cards}:
        fila = [c for c in cards if c["camada"] == camada]
        for i, c in enumerate(fila):
            prox = fila[i + 1]["t0"] if i + 1 < len(fila) else c["t1"] + 9
            c["saida"] = (prox - c["t1"]) >= RESPIRO_MIN
    return cards


def plano_uniforme(palavras: list[dict], dur: float, estilo: str) -> list[dict]:
    grupos, cur = [], []
    for i, w in enumerate(palavras):
        cur.append(w)
        gap = palavras[i + 1]["t0"] - w["t1"] if i + 1 < len(palavras) else 9.0
        if len(cur) >= MAX_WORDS or gap >= 0.4 or w["tx"].endswith((".", "?", "!", ",")):
            grupos.append(cur)
            cur = []
    if cur:
        grupos.append(cur)
    inicios = [max(0.0, g[0]["t0"] - LEAD) for g in grupos]
    cards = []
    for i, g in enumerate(grupos):
        fim = inicios[i + 1] if i + 1 < len(inicios) else min(dur, g[-1]["t1"] + TAIL)
        cards.append({"t0": inicios[i], "t1": fim, "layout": "faixa",
                      "anim": "entra", "modo": estilo,
                      "words": [dict(w, enf="normal") for w in g]})
    return finalizar(cards)


# ------------------------------------------------------------ animação

def anim(card: dict, i: int, w: dict, t: float, vol: float) -> tuple[float, float, float]:
    """(escala, alpha, dy) da palavra i do card, no instante t."""
    if card["anim"] == "revela" and t < w["t0"] - 0.05:
        return 0.0, 0.0, 0.0
    inicio = card["t0"] + (i * STAGGER if card["anim"] != "nenhuma" else 0.0)
    if card["anim"] == "revela":
        inicio = max(inicio, w["t0"] - 0.05)
    idade = t - inicio
    if idade < 0:
        return 0.0, 0.0, 0.0

    s0 = ENFASE.get(w.get("enf", "normal"), ENFASE["normal"])["s0"]
    if card["anim"] == "nenhuma":
        esc, alpha, dy = 1.0, 1.0, 0.0
    elif idade < ENTRADA:
        p = idade / ENTRADA
        amp = 0.12 + 0.30 * vol                    # fala mais alta, entrada mais viva
        esc = s0 + (1 - s0) * mola(p, amp)
        alpha = suave(p / 0.55)
        dy = 26 * (1 - suave(p))
    else:
        esc, alpha, dy = 1.0, 1.0, 0.0

    if card.get("saida") and not card.get("seco"):     # `seco`: o card some num quadro
        resta = card["t1"] - t
        if resta < SAIDA:
            q = suave(1 - resta / SAIDA)
            esc *= 1 - 0.07 * q
            alpha *= 1 - q
            dy -= 14 * q

    if w.get("enf") == "punch" and idade >= ENTRADA:
        esc *= 1 + 0.016 * math.sin(2 * math.pi * 0.7 * (t - card["t0"]))
    return esc, max(0.0, min(1.0, alpha)), dy


def cor_da_palavra(card: dict, w: dict, t: float) -> tuple[int, int, int]:
    """A cor da palavra no instante `t`. Em tela cheia (`_fundo`: luminância atrás da legenda) a cor tem contraste >= 4,5 com o fundo;
    com placa por baixo, o fundo é a placa."""
    cor = _cor_do_estilo(card, w, t)
    fundo = card.get("_fundo")
    if fundo is None:
        return cor
    placa = card.get("placa")
    if isinstance(placa, dict) and float(placa.get("opacidade", 1.0)) >= 0.5:
        fundo = luminancia(rgb(placa.get("cor", "#141414")))
    if card.get("modo") == "chave":
        # A letra tem contorno preto: branca ela se lê em qualquer fundo, e puxá-la ao preto sobre uma mão clara a
        # apagava no contorno. Só o destaque muda: precisa se ler E se distinguir do branco, e clarear o azul do
        # estilo até o contraste dava um lilás que some ao lado dele. Sem contraste, vale o marcador amarelo (VSL).
        if w.get("enf") in ("chave", "punch") and contraste(luminancia(cor), fundo) < CONTRASTE_MIN:
            return (245, 217, 10)
        return cor
    return legivel(cor, fundo)


def _cor_do_estilo(card: dict, w: dict, t: float) -> tuple[int, int, int]:
    enf = w.get("enf", "normal")
    base = ENFASE.get(enf, ENFASE["normal"])["cor"]
    if w.get("cor"):
        c = w["cor"].lstrip("#")
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    # a paleta do preset mora no card: base, acento e punch próprios
    hot = rgb(card["acento"]) if card.get("acento") else HOT
    if card.get("cor") and enf in ("normal", "filler"):
        base = rgb(card["cor"])
    if card["modo"] == "chave":
        # uma palavra de destaque por cartão, parada (a referência acende uma, não a que está sendo dita)
        return hot if enf in ("chave", "punch") else base
    if enf == "chave" and card.get("acento"):
        return hot
    if enf == "punch" and card.get("punch"):
        return rgb(card["punch"])
    if enf in ("chave", "punch"):
        return base                                  # ênfase não é ponteiro da fala
    if card["modo"] == "karaoke":
        return hot if t >= w["t0"] else base
    if card["modo"] == "destaque":
        return hot if w["t0"] <= t < w["t1"] else base
    return base


def _falada(card: dict, t: float) -> dict | None:
    """A palavra que está sendo dita: a última que já começou. Segura até a
    próxima começar — sumir no vão entre duas palavras pisca."""
    ditas = [w for w in card["words"] if w["t0"] <= t]
    return ditas[-1] if ditas else None


def diagramar(card: dict, largura: int, corpo: int, nome_fonte: str,
              d: ImageDraw.ImageDraw, y_caixa: float, alt_caixa: float) -> list[dict]:
    """Posição FINAL de cada palavra. Escala anima em torno destes centros —
    é isto que impede a linha de refluir quando uma palavra cresce."""
    k = largura / W_REF
    ec = card.get("estreita", 1.0)       # letra espremida na horizontal (`placa-serifa`)
    for w in card["words"]:
        esc = ENFASE.get(w.get("enf", "normal"), ENFASE["normal"])["escala"]
        # corpo por PALAVRA: bloco de manchete mistura tamanhos na mesma cartela
        base = w["corpo"] * k if w.get("corpo") else corpo
        w["_corpo"] = max(8, int(base * esc))
        w["_fonte"] = w.get("fonte", nome_fonte)
        w["_larg"] = _larg(d, w["tx"], fonte(w["_fonte"], w["_corpo"]), w.get("track", 0.0)) * ec

    # Quebra por LARGURA MEDIDA, não por contagem de caractere. "MENOS DE UMA
    # HORA" tem 17 caracteres e passa em qualquer teto de texto — mas com a
    # palavra em punch 1.5x numa fonte larga a linha estoura o quadro e as
    # pontas somem. Caractere não sabe o corpo nem o desenho da fonte.
    # `largura` do preset: a legenda corrida fica fora da coluna de botões do Reels
    maxl = largura * (card.get("largura", 0.90) if not card.get("_momento") else 0.90)
    esp = d.textlength(" ", font=fonte(nome_fonte, corpo)) * ec
    if card.get("quebra") == "palavra":
        # cartela de gancho manda na própria quebra: cada `tx` é uma linha.
        # Empacotar por largura transforma um bloco de 3 linhas em 2 e encolhe
        # o gancho — que é justamente o elemento que precisa dominar a tela.
        linhas = [[w] for w in card["words"]]
    elif card.get("quebra") == "nunca":
        # preset: a frase não quebra. Se não cabe, o card inteiro encolhe
        # (abaixo); quem corta no tempo antes, pra quase nunca chegar aqui, é o
        # `_reparte`
        linhas = [card["words"]]
    else:
        linhas, cur, larg = [], [], 0.0
        for w in card["words"]:
            extra = w["_larg"] + (esp if cur else 0.0)
            if cur and larg + extra > maxl:
                linhas.append(cur)
                cur, larg, extra = [], 0.0, w["_larg"]
            cur.append(w)
            larg += extra
        if cur:
            linhas.append(cur)

    if card.get("_momento"):
        # bloco do momento-chave: só a linha que estoura encolhe. Encolher o card
        # inteiro levava o apoio (já 5x menor que o herói) pra baixo do piso.
        # Atrás de quem fala sobra margem pro herói andar até achar a cabeça
        teto = maxl * (0.86 if card.get("atras") else 1.0)
        for ln in linhas:
            larg = sum(w["_larg"] for w in ln) + esp * (len(ln) - 1)
            if larg > teto:
                for w in ln:
                    w["_corpo"] = max(8, int(w["_corpo"] * teto / larg))
                    w["_larg"] = _larg(d, w["tx"], fonte(w["_fonte"], w["_corpo"]), w.get("track", 0.0)) * ec

    # palavra sozinha maior que o quadro: encolhe o card inteiro até caber
    pior = max(sum(w["_larg"] for w in ln) + esp * (len(ln) - 1) for ln in linhas)
    if pior > maxl:
        k = maxl / pior
        for w in card["words"]:
            w["_corpo"] = max(8, int(w["_corpo"] * k))
            w["_larg"] = _larg(d, w["tx"], fonte(w["_fonte"], w["_corpo"]), w.get("track", 0.0)) * ec
        corpo = max(8, int(corpo * k))
        esp = d.textlength(" ", font=fonte(nome_fonte, corpo)) * ec

    # entrelinha: manchete empilha linhas justas, quase encostando. 1.30 é o
    # espaçamento de legenda corrida e afasta demais pra bloco de cartela.
    ent = float(card.get("entrelinha", 1.30))
    # a altura da linha sai da CAIXA REAL do glifo, não do corpo. Script tem
    # ascendente e descendente muito maiores que o corpo nominal — usar corpo
    # faz a linha de cima sumir atrás dela.
    # Quanto a tinta sobe e desce A PARTIR DA ÂNCORA. Medir a caixa da tinta
    # sozinha não serve: o `anchor="mm"` do PIL centra pelas métricas da fonte,
    # e no script os floreios passam muito do ascendente nominal. Os dois números
    # só batem se a medida for relativa à mesma âncora usada no desenho.
    sobe, desce = [], []
    for ln in linhas:
        u = dn = 0
        for w in ln:
            f = fonte(w["_fonte"], w["_corpo"])
            bb = f.getbbox(w["tx"], anchor="mm")
            traco = max(2, w["_corpo"] // 11)
            u = max(u, -bb[1] + traco, w["_corpo"] * 0.45)
            dn = max(dn, bb[3] + traco, w["_corpo"] * 0.45)
        sobe.append(u)
        desce.append(dn)
    avancos = [(desce[i] + sobe[i + 1]) * ent for i in range(len(linhas) - 1)]
    total = sobe[0] + sum(avancos) + desce[-1]
    # `_base`: o bloco encosta no PE da caixa em vez de centrar nela.
    #
    # Centrado, card de uma linha e card de tres linhas ficam em alturas
    # diferentes -- a legenda sobe e desce a cada troca. Encostando no pe, todos
    # dividem a mesma linha de base, que e como legenda de verdade se comporta,
    # e "desce ate tocar a zona segura" passa a valer pra todos.
    if card.get("_base"):
        y = y_caixa + alt_caixa - total + sobe[0]
    else:
        y = y_caixa + alt_caixa / 2 - total / 2 + sobe[0]
    # Alinhamento e deslocamento por LINHA. Bloco de manchete não é texto
    # centrado: as linhas se escalonam umas em relação às outras, e é isso que
    # faz parecer composição em vez de parágrafo.
    al = card.get("alinhar", "centro")
    mg = largura * 0.055
    for i, linha in enumerate(linhas):
        larg = sum(w["_larg"] for w in linha) + esp * (len(linha) - 1)
        if al == "esquerda":
            x = mg
        elif al == "direita":
            x = largura - mg - larg
        else:
            x = (largura - larg) / 2
        x += linha[0].get("dx", 0) * k
        for w in linha:
            w["_cx"], w["_cy"] = x + w["_larg"] / 2, y
            x += w["_larg"] + esp
        if i < len(avancos):
            y += avancos[i]
    return card["words"]


def alpha_placa(p: dict) -> float:
    """Opacidade da placa. Cheia tapa o vídeo; 0.82 deixa o fundo respirar."""
    return float(p.get("opacidade", 0.82))


def tinta(card: dict, largura: int, altura: int) -> tuple[np.ndarray, list[tuple]]:
    """Alpha do texto assentado + a caixa de CADA letra.

    A caixa por letra é o que importa: medir só a tinta total deixa o herói
    perder as duas últimas letras e ainda marcar 72% — foi assim que "NENHUM"
    virou "NENHU" atrás da cabeça.
    """
    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lay = LAYOUTS.get(card["layout"], LAYOUTS["faixa"])
    k = largura / W_REF
    corpo = int(card.get("corpo", lay["corpo"]) * k)
    diagramar(card, largura, corpo, card.get("fonte", FONTE_PADRAO), d,
              card["_y"], lay["h"] * k)
    caixas = []
    for w in card["words"]:
        f = fonte(w["_fonte"], w["_corpo"])
        tr = w.get("track", 0.0)
        _escreve(d, (w["_cx"], w["_cy"]), w["tx"], f, tr,
                 fill=(255, 255, 255, 255),
                 stroke_width=max(2, f.size // 9), stroke_fill=(255, 255, 255, 255))
        x = w["_cx"] - w["_larg"] / 2
        alt = f.size * 0.66
        for ch in w["tx"]:
            av = d.textlength(ch, font=f)
            if ch.strip():
                caixas.append((int(x), int(w["_cy"] - alt),
                               max(int(x) + 1, int(x + av)), int(w["_cy"] + alt)))
            x += av + tr * f.size
    return np.array(img)[..., 3], caixas


def _visibilidade(base: np.ndarray, caixas: list[tuple], livre: np.ndarray,
                  dy: int, dx: int) -> tuple[float, float]:
    """(pior letra, média geral) depois de empurrar por (dy, dx)."""
    H, W = base.shape
    pior, sv, sn = 1.0, 0.0, 0.0
    for x0, y0, x1, y1 in caixas:
        ink = base[max(0, y0):y1, max(0, x0):x1]
        s = float(ink.sum())
        if s < 1:
            continue
        ny0, nx0 = max(0, y0) + dy, max(0, x0) + dx
        ny1, nx1 = ny0 + ink.shape[0], nx0 + ink.shape[1]
        if ny0 < 0 or nx0 < 0 or ny1 > H or nx1 > W:
            return -1.0, -1.0                      # empurrou letra pra fora
        v = float((ink * livre[ny0:ny1, nx0:nx1]).sum())
        pior = min(pior, v / s)
        sv += v
        sn += s
    return pior, (sv / sn if sn else 1.0)


def ajustar_heroi(card: dict, alfas: list[np.ndarray], largura: int, altura: int,
                  piso_letra: float = 0.60,
                  alvo_geral: float = 0.86) -> tuple[float, float, int, int]:
    """Empurra o card herói até TODA LETRA continuar legível sobre a silhueta.

    A profundidade tem que vir da borda mordida, não de letra sumida. Devolve
    (pior letra, geral, dy, dx).
    """
    base, caixas = tinta(card, largura, altura)
    # UNIÃO da silhueta em TODOS os frames do card, não a média de alguns.
    # Com média, letra tapada em metade do card marca 50% e passa — e some na
    # tela justo quando a pessoa vira a cabeça. Aqui a posição escolhida vale
    # pro pior instante, então o que está legível fica legível o card inteiro.
    varrida = np.maximum.reduce([a for a in alfas]) if alfas else None
    livre = (255 - varrida).astype(np.float32) / 255 if varrida is not None \
        else np.ones(base.shape, dtype=np.float32)
    if not caixas:
        return 1.0, 1.0, 0, 0

    ys, xs = np.nonzero(base)
    if not len(xs):
        return 1.0, 1.0, 0, 0
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    mx, my = int(0.035 * largura), int(0.03 * altura)
    dx_lo, dx_hi = mx - x0, largura - mx - x1
    dy_lo, dy_hi = my - y0, altura - my - y1
    # A busca respeita a ZONA do layout. Solta, ela varre o quadro inteiro e
    # sobe o herói pra dentro do painel de b-roll, onde o matte do sujeito não
    # vale nada: microfone e mão viram silhueta preta recortada sobre o gráfico.
    z0, z1 = LAYOUTS.get(card.get("layout", "faixa"), LAYOUTS["faixa"])["zona"]
    zona_lo, zona_hi = int(z0 * altura) - y0, int(z1 * altura) - y1
    if zona_lo <= zona_hi:
        dy_lo, dy_hi = max(dy_lo, zona_lo), min(dy_hi, zona_hi)
        if dy_lo > dy_hi:                      # texto mais alto que a zona
            dy_lo = dy_hi = zona_lo
    if dx_lo > dx_hi or dy_lo > dy_hi:
        # texto maior que o quadro: não há deslocamento válido. Devolver 1.0/1.0
        # aqui mentia — lê como "sem oclusão" quando é "não coube".
        return -1.0, -1.0, 0, 0

    melhor = (-1e9, 0, 0, 1.0, 1.0)
    for dy in range(dy_lo, dy_hi + 1, max(1, altura // 80)):
        for dx in range(dx_lo, dx_hi + 1, max(1, largura // 40)):
            pior, geral = _visibilidade(base, caixas, livre, dy, dx)
            if pior < 0:
                continue
            if pior < piso_letra:
                score = pior - 10                       # nenhuma letra pode sumir
            else:
                # letra salva; entre os que passam, o que morde mais borda
                score = -abs(geral - alvo_geral)
            if score > melhor[0]:
                melhor = (score, dy, dx, pior, geral)
    _, dy, dx, pior, geral = melhor
    return pior, geral, dy, dx


def desenhar(t: float, cards: list[dict], largura: int, altura: int,
             vol: np.ndarray) -> Image.Image:
    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    ativos = [c for c in cards if c["t0"] <= t < c["t1"]]
    if not ativos:
        return img
    # camada != "legenda" desenha primeiro, por baixo: gancho parado no topo
    # não pode cobrir a legenda que está rolando
    for card in sorted(ativos, key=lambda c: c["camada"] == "legenda"):
        m = _movendo(card, t) if card.get("borrao") else 0
        if m:
            img.alpha_composite(_obturador(card, t, largura, altura, vol, card["borrao"] * m))
        else:
            _camada(img, card, t, largura, altura, vol)
    return img


def _obturador(card: dict, t: float, largura: int, altura: int, vol: np.ndarray,
               n: int = 6) -> Image.Image:
    """Borrão de movimento de verdade: o card em N instantes do obturador aberto
    (um quadro inteiro, como o tmix da câmera que crava), somado com o alfa
    pré-multiplicado. O que anda rápido vira rastro; o que está parado fica nítido."""
    n = max(2, int(n))
    camadas = []
    for j in range(n):
        lay = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        _camada(lay, card, t - OBTURADOR * j / (n - 1), largura, altura, vol)
        camadas.append(lay)
    caixas = [b for b in (c.getbbox() for c in camadas) if b]
    out = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    if not caixas:
        return out
    # a conta em ponto flutuante só onde há tinta: o quadro inteiro custava 12x
    x0, y0 = min(b[0] for b in caixas), min(b[1] for b in caixas)
    x1, y1 = max(b[2] for b in caixas), max(b[3] for b in caixas)
    soma = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
    for lay in camadas:
        a = np.asarray(lay.crop((x0, y0, x1, y1)), np.float32)
        soma[..., :3] += a[..., :3] * a[..., 3:4] / 255
        soma[..., 3] += a[..., 3]
    soma /= n
    cor = soma[..., :3] * 255 / np.maximum(soma[..., 3:4], 1e-3)
    out.paste(Image.fromarray(np.dstack([np.clip(cor, 0, 255), soma[..., 3]]).round().astype(np.uint8),
                              "RGBA"), (x0, y0))
    return out


OBTURADOR = 1 / 30


def _camada(img: Image.Image, card: dict, t: float, largura: int, altura: int,
            vol: np.ndarray) -> None:
    ef = card.get("efeito") or {}
    if not ef:
        _desenhar_card(ImageDraw.Draw(img), card, t, largura, altura, vol)
    else:
        _com_efeito(img, card, t, largura, altura, vol, ef)
    if card.get("assinatura"):
        some = _some(card, t)
        if some >= 1.0:
            ASSINATURAS[card["assinatura"]](img, card, t, largura, altura)
        elif some > 0.0:
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ASSINATURAS[card["assinatura"]](lay, card, t, largura, altura)
            lay.putalpha(lay.split()[3].point(lambda v: int(v * some)))
            img.alpha_composite(lay)


def _com_efeito(img: Image.Image, card: dict, t: float, largura: int, altura: int,
                vol: np.ndarray, ef: dict) -> None:
    # com efeito o card vai pra camada própria: glow precisa borrar a mancha
    # do texto isolada, e borrar em cima do frame borraria o vídeo junto
    k = largura / W_REF
    cam = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    _desenhar_card(ImageDraw.Draw(cam), card, t, largura, altura, vol)

    def mancha(cor=(255, 255, 255), desloc=(0.0, 0.0), borda=False, enf=None):
        m = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        _pintar(ImageDraw.Draw(m), card, t, vol, k,
                desloc=desloc, cor_fixa=cor, borda=borda, enf=enf)
        return m

    # ordem importa: tudo que é "atrás" entra antes, do mais longe pro mais
    # perto. Extrusão depois de glow ficaria flutuando sobre o halo.
    if ef.get("glow"):
        g = ef["glow"]
        al = mancha().split()[3].filter(
            ImageFilter.GaussianBlur(g.get("raio", 18) * k))
        forca = float(g.get("forca", 0.85))
        brilho = Image.new("RGBA", (largura, altura), rgb(g.get("cor", "#F5D90A")) + (0,))
        brilho.putalpha(al.point(lambda v: min(255, int(v * forca * 2.2))))
        img.alpha_composite(brilho)

    if ef.get("sombra"):                     # difusa, diferente do offset duro
        s = ef["sombra"]
        m = mancha(rgb(s.get("cor", "#000000")),
                   (s.get("dx", 8) * k, s.get("dy", 10) * k), borda=bool(s.get("borda")))   # `borda`: a sombra leva o contorno junto (legenda de filme)
        al = m.split()[3].filter(ImageFilter.GaussianBlur(s.get("blur", 12) * k))
        m.putalpha(al.point(lambda v: int(v * float(s.get("alpha", 0.75)))))
        img.alpha_composite(m)

    if ef.get("extrusao"):                   # N cópias -> volume de cartaz
        e = ef["extrusao"]
        prof = int(e.get("profundidade", 10))
        ang = math.radians(e.get("angulo", 45))
        ce = rgb(e.get("cor", "#2B2B38"))
        for p in range(prof, 0, -1):
            img.alpha_composite(
                mancha(ce, (math.cos(ang) * p * k, math.sin(ang) * p * k)))

    if ef.get("offset"):                     # deslocamento duro, sem blur
        of = ef["offset"]
        img.alpha_composite(mancha(rgb(of.get("cor", "#000000")),
                                   (of.get("dx", 6) * k, of.get("dy", 6) * k)))

    if ef.get("gradiente"):                  # preenche a letra com degradê
        gr = ef["gradiente"]
        m = mancha(borda=False, enf=gr.get("enf"))
        # `enf`: só a palavra de ênfase, e o degradê corre na altura DELA —
        # na altura da tela, uma palavra só pega uma fatia e sai lisa
        y0, y1 = (m.getbbox() or (0, 0, 0, altura))[1::2] if gr.get("enf") else (0, altura)
        faixa = Image.new("RGB", (1, altura))
        d1, d2 = rgb(gr.get("de", "#FFFFFF")), rgb(gr.get("para", "#F5D90A"))
        px = faixa.load()
        for y in range(altura):
            q = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0 - 1)))
            px[0, y] = tuple(int(d1[j] + (d2[j] - d1[j]) * q) for j in range(3))
        deg = faixa.resize((largura, altura)).convert("RGBA")
        deg.putalpha(m.split()[3])
        if gr.get("enf"):
            cam.alpha_composite(deg)         # por cima da palavra, o resto fica
        else:
            cam = deg                        # troca a pintura do card
            if _borda(card, 60, k)[0]:       # redesenha só o contorno por baixo
                img.alpha_composite(mancha(_borda(card, 60, k)[1], borda=True))

    img.alpha_composite(cam)


def _desenhar_card(d: ImageDraw.ImageDraw, card: dict, t: float,
                   largura: int, altura: int, vol: np.ndarray) -> None:

    lay = LAYOUTS.get(card["layout"], LAYOUTS["faixa"])
    k = largura / W_REF
    corpo = int(card.get("corpo", lay["corpo"]) * k)
    alt_caixa = lay["h"] * k
    diagramar(card, largura, corpo, card.get("fonte", FONTE_PADRAO), d,
              card["_y"] + card.get("_dy", 0), alt_caixa)
    if card.get("_dx"):
        for w in card["words"]:
            w["_cx"] += card["_dx"]
    if card.get("linha_base"):
        # a linha de base cravada numa altura do quadro, igual pra toda frase: o `anchor="mm"`
        # do PIL centra pelas métricas da fonte, então o y de cada card não depende de
        # a frase ter ou não letra com cauda
        for w in card["words"]:
            asc, desc = fonte(w["_fonte"], w["_corpo"]).getmetrics()
            w["_cy"] = card["linha_base"] * altura - (asc - desc) / 2
    if card.get("assinatura") == "carimbo":
        # o tranco do carimbo: o cartão inteiro treme e assenta
        tx_, ty_ = _tranco(card, t, k)
        for w in card["words"]:
            w["_cx"] += tx_
            w["_cy"] += ty_

    # placa atrás do texto: retângulo arredondado dimensionado pela mancha real
    # das palavras. Entra com a MESMA curva da primeira palavra, senão a placa e
    # o texto chegam em tempos diferentes e parece bug.
    if card.get("placa"):
        p = card["placa"]
        e0, a0, d0 = anim(card, 0, card["words"][0], t,
                          volume_de(vol, card["words"][0]["t0"], card["words"][0]["t1"]))
        if a0 > 0.01:
            xs = [w["_cx"] - w["_larg"] / 2 for w in card["words"]]
            xe = [w["_cx"] + w["_larg"] / 2 for w in card["words"]]
            ys = [w["_cy"] for w in card["words"]]
            px, py = corpo * 0.52, corpo * 0.44
            x0, x1 = min(xs) - px, max(xe) + px
            y0, y1 = min(ys) - corpo * 0.62 - py, max(ys) + corpo * 0.62 + py
            if p.get("alto"):
                # placa de altura fixa e folga lateral fixa, a `sob` px abaixo da linha de base
                w0 = card["words"][0]
                asc, desc = fonte(w0["_fonte"], w0["_corpo"]).getmetrics()
                y1 = w0["_cy"] + (asc - desc) / 2 + p.get("sob", 22) * k
                y0 = y1 - p["alto"] * k
                x0, x1 = min(xs) - p.get("lado", 20) * k, max(xe) + p.get("lado", 20) * k
            if p.get("tipo") == "cartao":              # notificação: bolinha + placa
                x0 -= corpo * 1.5
            # a placa é dimensionada pelo texto e não sabe onde o quadro acaba:
            # com fonte larga ela vaza pela lateral. Prende com margem.
            mg = largura * 0.03
            x0, x1 = max(mg, x0), min(largura - mg, x1)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            w2, h2 = (x1 - x0) / 2 * e0, (y1 - y0) / 2 * e0
            if p.get("sombra"):
                _sombra_placa(d, p["sombra"], x0, x1, y0, y1, k, a0)
            d.rounded_rectangle(
                [cx - w2, cy - h2 + d0, cx + w2, cy + h2 + d0],
                radius=int(p.get("raio", 26) * k),
                fill=rgb(p.get("cor", "#141414")) + (int(255 * alpha_placa(p) * a0),))
            if p.get("tipo") == "cartao":
                r = corpo * 0.42 * e0
                d.ellipse([cx - w2 + corpo * 0.55 - r, cy - r + d0,
                           cx - w2 + corpo * 0.55 + r, cy + r + d0],
                          fill=rgb(p.get("bolinha", "#F5D90A")) + (int(255 * a0),))

    # marca-texto: tarja atrás de CADA palavra, não do card inteiro como a placa.
    # Marca só a palavra marcada, que é o ponto — grifo, não fundo.
    mt = (card.get("efeito") or {}).get("marca")
    if mt:
        alvo = mt.get("enf")            # None = todas; "chave" = só as chaves
        quais = mt.get("palavras")      # ou índices: [0] marca só a 1ª linha
        # `fala`: a marca anda atrás da palavra que está sendo dita
        falada = _falada(card, t) if mt.get("fala") else None
        for i, w in enumerate(card["words"]):
            if quais is not None and i not in quais:
                continue
            if alvo and w.get("enf") != alvo:
                continue
            if mt.get("fala") and w is not falada:
                continue
            esc, alpha, dy = anim(card, i, w, t, volume_de(vol, w["t0"], w["t1"]))
            if alpha <= 0.01:
                continue
            if mt.get("forma") == "sublinha":
                # traço sob a palavra, da largura dela: grifo sem caixa
                y = w["_cy"] + dy + w["_corpo"] * esc * 0.42
                d.rectangle([w["_cx"] - w["_larg"] / 2 * esc, y,
                             w["_cx"] + w["_larg"] / 2 * esc, y + max(3, w["_corpo"] * esc * 0.08)],
                            fill=rgb(mt.get("cor", "#F5D90A")) + (int(255 * alpha),))
                continue
            pad = w["_corpo"] * 0.18
            hh = w["_corpo"] * 0.62 * esc
            d.rounded_rectangle(
                [w["_cx"] - w["_larg"] / 2 * esc - pad, w["_cy"] + dy - hh - pad * 0.5,
                 w["_cx"] + w["_larg"] / 2 * esc + pad, w["_cy"] + dy + hh + pad * 0.5],
                radius=int(mt.get("raio", 10) * k),
                fill=rgb(mt.get("cor", "#F5D90A")) + (int(255 * alpha),))

    _pintar(d, card, t, vol, k)


def _sombra_placa(d: ImageDraw.ImageDraw, s: dict, x0: float, x1: float,
                  y0: float, y1: float, k: float, a0: float) -> None:
    """Sombra da placa SÓ pra baixo, como a da referência (`0 18px 28px`, medida: 51 % logo
    abaixo da borda, 10 % a 36 px, nada a 57 px, nada acima nem nos lados). O retângulo
    é recolhido de `blur` em cada lado pra sombra não vazar pela lateral, e o que ficaria
    acima da borda de baixo é cortado (ali a placa já cobre). Camada do tamanho da sombra,
    não do quadro: custa 1 ms."""
    sig, dy = s.get("blur", 14) * k, s.get("dy", 18) * k
    m = int(sig * 3)
    ox, oy = int(x0) - m, int(y1) - m
    w, h = int(x1 - x0) + 2 * m, int(dy + 2 * m + sig)
    cam = Image.new("L", (w, h), 0)
    ImageDraw.Draw(cam).rectangle([m + sig, y0 + dy - oy, w - m - sig, y1 + dy - oy], fill=255)
    cam = cam.filter(ImageFilter.GaussianBlur(sig))
    cam.paste(0, (0, 0, w, int(y1) - oy))                       # nada acima da borda de baixo
    cam = cam.point(lambda v: int(v * float(s.get("alpha", 0.55)) * a0))
    sombra = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sombra.putalpha(cam)
    _compoe(d._image, sombra, ox, oy)


def rgb(s: str, padrao: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    if not s:
        return padrao
    c = s.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _borda(card: dict, tam: int, k: float) -> tuple[int, tuple[int, int, int]]:
    """Contorno da letra. Antes era fixo em corpo//9 e engordava TODA fonte —
    era por isso que serifa, script e display pareciam a mesma coisa. Agora é
    escolha, e o padrão é mais fino."""
    c = card.get("contorno")
    if c is None:
        return max(2, tam // 11), STROKE
    if c is False or c == 0:
        return 0, STROKE
    if isinstance(c, (int, float)):
        return max(0, int(c * k)), STROKE
    return max(0, int(c.get("largura", 7) * k)), rgb(c.get("cor", "#000000"))


def _pintar(d: ImageDraw.ImageDraw, card: dict, t: float, vol: np.ndarray,
            k: float = 1.0,
            desloc: tuple[float, float] = (0.0, 0.0),
            cor_fixa: tuple[int, int, int] | None = None,
            borda: bool = True, enf: str | None = None) -> None:
    """Só as palavras, já diagramadas. Separado do card pra poder ser
    redesenhado — offset, glow, sombra e extrusão são a MESMA pintura em outra
    cor/posição. `enf` pinta só as palavras dessa ênfase."""
    ox, oy = desloc
    for i, w in enumerate(card["words"]):
        if enf and w.get("enf") != enf:
            continue
        if w.get("_heroi"):
            continue                    # quem desenha é a assinatura do cartão
        esc, alpha, dy = anim(card, i, w, t, volume_de(vol, w["t0"], w["t1"]))
        if alpha <= 0.01 or esc <= 0.01:
            continue
        f = fonte(w["_fonte"], max(8, int(w["_corpo"] * esc)))
        a = int(255 * alpha)
        cor = cor_fixa or cor_da_palavra(card, w, t)
        bl, bc = _borda(card, f.size, k) if borda else (0, STROKE)
        tipo = w.get("entrada", card.get("entrada"))
        if tipo == "maquina":
            _datilografa(d, w, f, cor + (a,), bl, bc + (a,), ox, oy, t,
                         cursor=cor_fixa is None)
            continue
        p = _p_entrada(card, i, w, t) if tipo else 1.0
        if tipo == "corte":
            # corte seco: a palavra aparece inteira, sem mola nem fade
            if p <= 0:
                continue
            if p < 1.0:
                f, a, dy = fonte(w["_fonte"], w["_corpo"]), 255, 0.0
            p = 1.0
        if p < 1.0:
            # a máscara revela, não esmaece: entra opaca
            _sprite(d, w, cor + (255 if "mascara" in tipo else a,), bl,
                    bc + (255 if "mascara" in tipo else a,),
                    w["_cx"] + ox, w["_cy"] + oy, tipo, p, i, k)
        elif w.get("track"):
            _escreve(d, (w["_cx"] + ox, w["_cy"] + dy + oy), w["tx"], f, w["track"],
                     fill=cor + (a,), stroke_width=bl, stroke_fill=bc + (a,))
        elif card.get("estreita"):
            _estreita(d, w, f, cor + (a,), bl, bc + (a,), w["_cx"] + ox, w["_cy"] + dy + oy,
                      card["estreita"])
        else:
            d.text((w["_cx"] + ox, w["_cy"] + dy + oy), w["tx"], font=f, anchor="mm",
                   fill=cor + (a,), stroke_width=bl, stroke_fill=bc + (a,))
        if w.get("emoji") and cor_fixa is None and alpha > 0.5:
            _emoji(d, w["emoji"], w["_cx"] + ox,
                   w["_cy"] + dy + oy - f.size * 0.55, f.size * 1.4)


def _p_entrada(card: dict, i: int, w: dict, t: float) -> float:
    """0→1 da entrada da palavra i, no relógio do `anim` (stagger e `revela`)."""
    inicio = card["t0"] + (i * STAGGER if card["anim"] != "nenhuma" else 0.0)
    if card["anim"] == "revela":
        inicio = max(inicio, w["t0"] - 0.05)
    return min(1.0, max(0.0, (t - inicio) / ENTRADA))


def _sprite(d: ImageDraw.ImageDraw, w: dict, cor: tuple, bl: int, bc: tuple,
            cx: float, cy: float, tipo: str, p: float, i: int, k: float) -> None:
    """A palavra numa camada só dela, pra entrar com máscara (`mascara`), desfoque
    (`desfoque`), giro (`giro`), deformação (`elastico`) ou espaçamento que fecha
    (`espaco`) — as mecânicas dos templates de texto do Jitter
    (pesquisa/referencias-texto/O-QUE-USAR.md e COMPOSICAO.md)."""
    f = fonte(w["_fonte"], w["_corpo"])
    tr = w.get("track", 0.0)
    tipos = set(tipo.split("+"))           # combinam: "desfoque+espaco"
    if "espaco" in tipos:
        # entra aberta e fecha no espaçamento final (elastic-text do Jitter)
        tr += 0.6 * (1 - p) ** 3
    pad = bl + f.size // 2
    lw, lh = int(_larg(d, w["tx"], f, tr)) + 2 * pad, f.size * 2 + 2 * pad
    sp = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    _escreve(ImageDraw.Draw(sp), (lw / 2, lh / 2), w["tx"], f, tr,
             fill=cor, stroke_width=bl, stroke_fill=bc)
    if "mascara" in tipos:
        # sobe de dentro da própria linha: o que passa do pé da caixa não aparece
        desce = int((1 - (1 - (1 - p) ** 4)) * f.size * 1.1)
        janela = Image.new("RGBA", sp.size, (0, 0, 0, 0))
        janela.paste(sp.crop((0, 0, lw, lh - desce)), (0, desce))
        janela.paste((0, 0, 0, 0), (0, int(lh / 2 + f.size * 0.62 + bl), lw, lh))
        sp = janela
    if "desfoque" in tipos:
        if (1 - p) * 12 * k > 0.3:
            sp = sp.filter(ImageFilter.GaussianBlur((1 - p) * 12 * k))
        cy += 20 * k * (1 - suave(p))
    if "voa" in tipos:
        # sobe rápido e freia (expo): é a velocidade que o `borrao` do card
        # transforma em rastro, como no motion-blur-text do Jitter
        cy += f.size * 0.7 * (1 - p) ** 3
    if "giro" in tipos:                  # crava girada; o lado alterna a cada palavra
        sp = sp.rotate((7 if i % 2 else -7) * (1 - mola(p, 0.5)),
                       resample=Image.BICUBIC, expand=True)
    if "elastico" in tipos:              # estica na largura, achata, e assenta
        e = math.exp(-5.5 * p) * math.cos(9 * p)
        sp = sp.resize((max(1, int(lw * (1 + 0.25 * e))), max(1, int(lh * (1 - 0.2 * e)))),
                       Image.BICUBIC)
    # ponytail: o ImageDraw guarda a imagem em `_image`; passar a imagem por
    # todo o caminho do desenho era mexer em seis assinaturas
    _compoe(d._image, sp, cx - sp.width / 2, cy - sp.height / 2)


def _estreita(d: ImageDraw.ImageDraw, w: dict, f: ImageFont.FreeTypeFont, cor: tuple, bl: int,
              bc: tuple, cx: float, cy: float, fator: float) -> None:
    """A palavra espremida na horizontal por `fator` (o PIL não tem largura de letra): sai
    numa camada dela na largura cheia e encolhe só em x, com o centro no mesmo ponto.
    Largura da camada = a medida pela qual o `diagramar` já assentou a palavra."""
    pad = bl + f.size // 2
    lw, lh = int(d.textlength(w["tx"], font=f)) + 2 * pad, f.size * 2 + 2 * pad
    sp = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(sp).text((lw / 2, lh / 2), w["tx"], font=f, anchor="mm", fill=cor,
                            stroke_width=bl, stroke_fill=bc)
    sp = sp.resize((max(1, round(lw * fator)), lh), Image.LANCZOS)
    _compoe(d._image, sp, cx - sp.width / 2, cy - sp.height / 2)


def _compoe(img: Image.Image, sp: Image.Image, x: float, y: float) -> None:
    """alpha_composite que aceita a camada saindo pela borda do quadro."""
    x, y = int(round(x)), int(round(y))
    l, t = max(0, -x), max(0, -y)
    r, b = min(sp.width, img.width - x), min(sp.height, img.height - y)
    if r > l and b > t:
        img.alpha_composite(sp.crop((l, t, r, b)), (x + l, y + t))


# ------------------------------------------------------------ assinaturas
#
# O momento-chave de cada sistema de cinema tem um desenho que só ele faz. A
# palavra-herói sai do `_pintar` (`_heroi`) e quem a desenha é a função da
# assinatura, depois do resto do cartão. Tudo aqui anda no relógio do cartão:
# `_t_in` é quando a câmera começa a cravar e `_pouso`, quando ela chega.

# O 3D do núcleo do tools/v2 (D.palco3d, D.espessura, D.luz; perfil `a`, i3d média,
# tools/v2/nucleo/direcao-v2.js): a lente de 1800 px, a luz de cima, da esquerda e
# da frente, e cada face que escurece INTEIRA até 55 % de costas pra ela ou clareia
# até 22 % de frente. Os números são os de lá; mudou lá, muda aqui.
LENTE = 1800.0
LUZ3D = np.array([-0.45, -0.6, 0.66]) / np.linalg.norm([-0.45, -0.6, 0.66])
ESCURO3D, CLARO3D = 0.55, 0.22
TINTA3D = np.array([11, 13, 18], np.float32)
PARALAXE = 0.85      # o herói anda com a câmera, um pouco menos que a cena
PASSO_COLAGEM = 0.05  # uma letra recortada a cada 1,5 quadro
TRANCO = 0.22        # quanto o carimbo sacode depois de bater

_cache_ass: dict = {}


def _movendo(card: dict, t: float) -> int:
    """Quanto o cartão anda neste quadro: 0 parado (o obturador não abre: a
    média de N quadros iguais é o mesmo quadro, pago N vezes), 1 palavra
    entrando, 2 a assinatura cravando (o salto é grande e pede o dobro de
    instantes, senão o rastro sai em degraus)."""
    a = card.get("_t_in")
    if a is not None:
        fim = a + {"colagem": _colagem_dur(card), "carimbo": CRAVA + TRANCO}.get(
            card.get("assinatura"), CRAVA)
        if a - 0.02 <= t < fim + OBTURADOR:
            return 2
    for i, w in enumerate(card["words"]):
        tipo = w.get("entrada", card.get("entrada"))
        if not tipo or tipo in ("corte", "maquina") or w.get("_heroi"):
            continue
        if _p_entrada(card, i, w, t) > 0.0 and _p_entrada(card, i, w, t - OBTURADOR) < 1.0:
            return 1
    return 0


def _heroi(card: dict) -> dict:
    return next(w for w in card["words"] if w.get("_heroi"))


def _some(card: dict, t: float) -> float:
    """A assinatura sai em 0,2 s quando há respiro depois (senão corta seco)."""
    return max(0.0, min(1.0, (card["t1"] - t) / 0.2)) if card.get("saida") else 1.0


def _paralaxe(card: dict, t: float) -> float:
    """Escala do herói no quadro: a câmera que crava e segue andando leva a palavra
    junto, um pouco menos que a cena, e é isso que a põe no espaço e não na tela."""
    cam = card.get("_cam")
    if not cam:
        return 1.0
    return 1 + (zoom_em(t, cam)[0] / cam[0]["zoom"][1] - 1) * PARALAXE


def _passo_maquina(w: dict) -> float:
    """Uma tecla por letra, no tempo em que a frase é dita (entre 30 e 75 ms)."""
    return min(0.075, max(0.03, (w["t1"] - w["t0"]) / max(1, len(w["tx"]))))


def _datilografa(d: ImageDraw.ImageDraw, w: dict, f: ImageFont.FreeTypeFont, cor: tuple,
                 bl: int, bc: tuple, ox: float, oy: float, t: float, cursor: bool = True) -> None:
    """Máquina de escrever: a frase sai letra a letra, com o cursor em bloco no fim,
    firme enquanto digita e piscando depois. A palavra cresce pra direita a partir
    de onde vai assentar, então nada reflui."""
    f = fonte(w["_fonte"], w["_corpo"])
    cor, bc = cor[:3] + (255,), bc[:3] + (255,)
    tx, tr = w["tx"], w.get("track", 0.0)
    n = max(0, min(len(tx), int((t - w["t0"]) / _passo_maquina(w)) + 1))
    x0, cy = w["_cx"] - w["_larg"] / 2 + ox, w["_cy"] + oy
    lp = _larg(d, tx[:n], f, tr) if n else 0.0
    if n:
        _escreve(d, (x0 + lp / 2, cy), tx[:n], f, tr, fill=cor, stroke_width=bl, stroke_fill=bc)
    if cursor and (n < len(tx) or int((t - w["t0"]) * 2.6) % 2 == 0):
        xc = x0 + lp + (f.size * 0.1 if n else 0.0)
        d.rectangle([xc, cy - f.size * 0.4, xc + f.size * 0.48, cy + f.size * 0.4], fill=cor)


def _tranco(card: dict, t: float, k: float) -> tuple[float, float]:
    dt = t - card.get("_pouso", 1e9)
    if not 0.0 <= dt < TRANCO:
        return 0.0, 0.0
    amp = 18 * k * math.exp(-dt / 0.06)
    return amp * math.sin(dt * 95), amp * 0.7 * math.cos(dt * 120)


def _molde(w: dict) -> tuple:
    """A palavra herói como máscara, com a normal 2D da borda (pra luz dos lados)
    e o aro de dentro da face (o chanfro que pega a luz). Uma vez por palavra."""
    chave = ("molde", w["tx"], w["_fonte"], w["_corpo"], w.get("track", 0.0))
    if chave not in _cache_ass:
        f = fonte(w["_fonte"], w["_corpo"])
        tr = w.get("track", 0.0)
        lw = int(_larg(ImageDraw.Draw(Image.new("L", (1, 1))), w["tx"], f, tr))
        pad = int(f.size * 0.3)
        m = Image.new("L", (lw + 2 * pad, int(f.size * 1.5) + 2 * pad), 0)
        _escreve(ImageDraw.Draw(m), (m.width / 2, m.height / 2), w["tx"], f, tr, fill=255)
        a = np.asarray(m, np.float32) / 255
        g = np.asarray(m.filter(ImageFilter.GaussianBlur(max(1.5, f.size / 80))), np.float32)
        gy, gx = np.gradient(g)
        nn = np.hypot(gx, gy) + 1e-6
        r = max(2, f.size // 55)
        miolo = np.asarray(m.filter(ImageFilter.MinFilter(2 * r + 1)), np.float32) / 255
        ys = np.nonzero(a.max(axis=1) > 0.5)[0]
        _cache_ass[chave] = (a, -gx / nn, -gy / nn, np.clip(a - miolo, 0, 1),
                             (int(ys.min()), int(ys.max())) if len(ys) else (0, m.height))
    return _cache_ass[chave]


def _gira(rx: float, ry: float) -> np.ndarray:
    """Ry·Rx, no sistema da luz do núcleo: x à direita, y pra baixo, z pra quem assiste."""
    cx, sx, cy, sy = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry)
    return (np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


def _acende(cor: np.ndarray, dd: np.ndarray) -> np.ndarray:
    """O D._acende do núcleo, por pixel: clareia pro branco de frente pra luz,
    escurece pra tinta de costas, chapado."""
    claro = np.clip(dd * CLARO3D * 2, 0, CLARO3D)[..., None]
    escuro = np.clip(-dd * ESCURO3D * 1.4, 0, ESCURO3D)[..., None]
    return cor * (1 - claro - escuro) + 255 * claro + TINTA3D * escuro


def _coefs(saida: list[tuple[float, float]], entrada: list[tuple[float, float]]) -> list[float]:
    """Os 8 coeficientes do Image.PERSPECTIVE que levam o quadro de saída ao sprite."""
    A, b = [], []
    for (x, y), (X, Y) in zip(saida, entrada):
        A += [[x, y, 1, 0, 0, 0, -X * x, -X * y], [0, 0, 0, x, y, 1, -Y * x, -Y * y]]
        b += [X, Y]
    return list(np.linalg.solve(np.array(A, float), np.array(b, float)))


def _heroi3d(img: Image.Image, card: dict, t: float, largura: int, altura: int) -> None:
    """A palavra em ouro maciço, com espessura e luz do núcleo do v2, atrás de quem
    fala: entra de perto da lente e crava junto com a câmera, depois segue a câmera
    com paralaxe e gira devagar, e a sombra dela cai na parede."""
    w = _heroi(card)
    a0 = card["_t_in"]
    if t < a0:
        return
    k = largura / W_REF
    pe = min(1.0, (t - a0) / CRAVA)
    e = _ANDAMENTO["crava"](pe)
    hold = max(0.3, card["t1"] - card["_pouso"])
    deriva = _ANDAMENTO["sine"](min(1.0, max(0.0, (t - card["_pouso"]) / hold)))
    R = _gira(math.radians(10 + 6 * (1 - e) - 3 * deriva), math.radians(-22 * (1 - e) - 9 + 16 * deriva))
    zw = -0.42 * LENTE * (1 - e)                 # vem de perto da lente
    s = _paralaxe(card, t)
    a, nx, ny, aro, (yt, yb) = _molde(w)
    sh, sw = a.shape
    V = np.array([largura / 2, altura / 2])
    C = (np.array([w["_cx"], w["_cy"]]) - V) * s
    esp = 0.30 * w["_corpo"]

    def projeta(u: float, v: float, z: float) -> tuple[float, float]:
        p = R @ np.array([u * s, v * s, z * s])
        q = V + (C + p[:2]) * LENTE / (LENTE + zw - p[2])
        return float(q[0]), float(q[1])

    cantos = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
    # presa no quadro com 64 px de margem: o crava empurrava o "O" pra borda
    tinta_x = [projeta(x - sw / 2, y - sh / 2, 0.0)[0] for x, y in cantos]
    mg = 64 * largura / W_REF
    sobra_e, sobra_d = mg - min(tinta_x), max(tinta_x) - (largura - mg)
    if sobra_e > 0 and sobra_d <= 0:
        C[0] += sobra_e * (LENTE + zw) / LENTE
    elif sobra_d > 0 and sobra_e <= 0:
        C[0] -= sobra_d * (LENTE + zw) / LENTE
    n_cam = max(10, int(esp * s / 2.5))
    camadas = [-esp * j / n_cam for j in range(n_cam, -1, -1)]      # de trás pra frente
    todos = [projeta(x - sw / 2, y - sh / 2, z) for z in (camadas[0], 0.0) for x, y in cantos]
    sx_, sy_ = 0.08 * w["_corpo"] * s, 0.11 * w["_corpo"] * s        # onde a sombra cai
    x0 = max(0, int(min(p[0] for p in todos)) - 4)
    y0 = max(0, int(min(p[1] for p in todos)) - 4)
    x1 = min(largura, int(max(p[0] for p in todos) + sx_) + 6)
    y1 = min(altura, int(max(p[1] for p in todos) + sy_) + 6)
    if x1 <= x0 or y1 <= y0:
        return

    # os lados: a cor de cada pixel da borda vem da normal dele girada contra a luz
    n3 = (np.stack([nx, ny, np.zeros_like(nx)], -1) @ R.T)
    lado = _acende(np.broadcast_to(np.array([150, 98, 28], np.float32), a.shape + (3,)),
                   n3 @ LUZ3D - LUZ3D[2])
    # a face: degradê de ouro na altura da letra, a luz da face inteira e o chanfro
    q = np.clip((np.arange(sh, dtype=np.float32) - yt) / max(1, yb - yt), 0, 1)[:, None, None]
    de, para = np.array([255, 246, 218], np.float32), np.array([201, 147, 43], np.float32)
    face = np.broadcast_to(de + (para - de) * q, a.shape + (3,)).copy()
    face = _acende(face, np.full(a.shape, float(R[:, 2] @ LUZ3D - LUZ3D[2])))
    olha = (nx * LUZ3D[0] + ny * LUZ3D[1]) / np.hypot(LUZ3D[0], LUZ3D[1])
    face += (aro * np.clip(olha, 0, 1) * 0.75)[..., None] * (255 - face)
    face -= (aro * np.clip(-olha, 0, 1) * 0.35)[..., None] * face
    al = (a * 255).astype(np.uint8)
    sp_lado = Image.fromarray(np.dstack([np.clip(lado, 0, 255).astype(np.uint8), al]), "RGBA")
    sp_face = Image.fromarray(np.dstack([np.clip(face, 0, 255).astype(np.uint8), al]), "RGBA")

    reg = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for z in camadas:
        sp = sp_face if z == 0.0 else sp_lado
        alvo = [(px - x0, py - y0) for px, py in (projeta(x - sw / 2, y - sh / 2, z) for x, y in cantos)]
        reg.alpha_composite(sp.transform(reg.size, Image.PERSPECTIVE, _coefs(alvo, cantos),
                                         Image.BICUBIC if z == 0.0 else Image.BILINEAR))
    op = min(1.0, pe * 4)
    if op < 1.0:
        reg.putalpha(reg.split()[3].point(lambda v: int(v * op)))
    # a sombra cai na cena: a silhueta inteira (face e lados), deslocada pela luz,
    # escura e quase dura. Atrás de quem fala ela também fica atrás dele.
    sombra = Image.new("RGBA", reg.size, (0, 0, 0, 0))
    sombra.putalpha(reg.split()[3].point(lambda v: int(v * 0.42)).filter(
        ImageFilter.GaussianBlur(max(1.0, 0.012 * w["_corpo"]))))
    _compoe(img, sombra, x0 + sx_ * e, y0 + sy_ * e)
    _compoe(img, reg, x0, y0)


# Quatro famílias e duas cores de papel, mais UM recorte coral por palavra. Com
# oito famílias, cinco papéis e minúscula solta, as 6 personas de 05/10 leram a
# colagem como "TikTok faça você mesmo" (6 de 6) e 3 não conseguiram ler tudo
_LETRAS_COLAGEM = ["serifa", "bebas", "serifa-italica", "dm"]
_PAPEIS = [((244, 239, 230), (17, 17, 17)), ((17, 17, 17), (244, 239, 230))]
_PAPEL_DESTAQUE = ((255, 90, 54), (255, 255, 255))


def _recortes(w: dict) -> list:
    """Cada letra num recorte de revista: família, papel, giro e altura sorteados
    pela própria palavra, então o mesmo herói sai igual em todo render. Só letra
    OFL, tudo em caixa alta e na mesma altura de recorte: o que varia é a família
    e o papel, não o tamanho (letra miúda no meio some no celular)."""
    chave = ("colagem", w["tx"], w["_corpo"])
    if chave in _cache_ass:
        return _cache_ass[chave]
    rnd = random.Random("colagem:" + w["tx"])
    letras = _LETRAS_COLAGEM[:]
    rnd.shuffle(letras)
    s, out = w["_corpo"] * 1.25, []        # o recorte é maior que a letra corrida
    letras_ = [i for i, ch in enumerate(w["tx"]) if ch.strip()]
    destaque = letras_[rnd.randrange(len(letras_))] if letras_ else -1
    for i, ch in enumerate(w["tx"]):
        if not ch.strip():
            out.append(None)
            continue
        nome = letras[i % len(letras)]
        g = ch.upper()
        f = fonte(nome, int(s * {"bebas": 1.22}.get(nome, 1.0) * rnd.uniform(0.96, 1.04)))
        bb = f.getbbox(g, anchor="mm")
        alto = f.getbbox("H", anchor="mm")
        papel, tinta_ = _PAPEL_DESTAQUE if i == destaque else _PAPEIS[(i + rnd.randrange(2)) % 2]
        px, py = s * 0.07, s * 0.06
        cw = bb[2] - bb[0] + 2 * px
        chh = max(bb[3], alto[3]) - min(bb[1], alto[1]) + 2 * py
        chip = Image.new("RGBA", (int(cw) + 4, int(chh) + 4), (0, 0, 0, 0))
        j = s * 0.035
        poly = [(2 + rnd.uniform(0, j), 2 + rnd.uniform(0, j)), (cw + 2 - rnd.uniform(0, j), 2 + rnd.uniform(0, j)),
                (cw + 2 - rnd.uniform(0, j), chh + 2 - rnd.uniform(0, j)), (2 + rnd.uniform(0, j), chh + 2 - rnd.uniform(0, j))]
        d = ImageDraw.Draw(chip)
        d.polygon(poly, fill=papel + (255,))
        d.text((chip.width / 2 - (bb[0] + bb[2]) / 2,
                chip.height / 2 - (min(bb[1], alto[1]) + max(bb[3], alto[3])) / 2),
               g, font=f, fill=tinta_ + (255,), anchor="mm")
        # grão de papel impresso, fraco: o recorte não é cor chapada de tela
        px_ = np.asarray(chip, np.float32)
        px_[..., :3] += np.random.default_rng(i + len(out)).normal(0, 5, px_.shape[:2])[..., None]
        chip = Image.fromarray(np.clip(px_, 0, 255).astype(np.uint8), "RGBA")
        out.append((chip, rnd.uniform(-5, 5), rnd.uniform(-0.04, 0.04) * s, nome))
    _cache_ass[chave] = out
    return out


def _colagem_dur(card: dict) -> float:
    n = sum(1 for ch in _heroi(card)["tx"] if ch.strip())
    return (n - 1) * PASSO_COLAGEM + 0.12


def _colagem(img: Image.Image, card: dict, t: float, largura: int, altura: int) -> None:
    """A palavra se monta com letras recortadas de revista, uma a uma, cada uma
    batendo girada com sombra dura na parede, e a colagem segue a câmera."""
    w = _heroi(card)
    a0 = card["_t_in"]
    if t < a0:
        return
    rec = _recortes(w)
    s = _paralaxe(card, t)
    # uma linha só: em duas, a segunda descia pra trás da cabeça e sumia (05/10)
    sobra = -w["_corpo"] * 0.1
    larg = sum(r[0].width + sobra if r else w["_corpo"] * 0.25 for r in rec) - sobra
    sc = min(1.0, largura * 0.92 / max(1.0, larg)) * s
    F = np.array([largura / 2, altura / 2])
    cx, cy = F + (np.array([w["_cx"], w["_cy"]]) - F) * s
    antes = card["words"][:card["words"].index(w)]
    if antes:
        # folga de 24 px entre o pé da frase de apoio e o topo do recorte mais
        # alto, já com o giro e a escala de quando ele bate
        pe_apoio = max(x["_cy"] + x["_corpo"] * 0.5 for x in antes)
        meia = max(r[0].height for r in rec if r) * sc * 0.62
        cy = max(cy, pe_apoio + 24 * largura / W_REF + meia)
    # o recorte é mais largo que a letra que o herói mediu: segura dentro do quadro
    mg = largura * 0.035
    cx = min(max(cx, mg + larg * sc / 2), largura - mg - larg * sc / 2)
    x = cx - larg * sc / 2
    n = 0
    for r in rec:
        if r is None:
            x += w["_corpo"] * 0.25 * sc
            continue
        _recorte_bate(img, r, w, t - a0 - n * PASSO_COLAGEM, x, cy, sc, n + 1)
        n += 1
        x += (r[0].width + sobra) * sc


def _recorte_bate(img: Image.Image, r: tuple, w: dict, idade: float, x: float, cy: float,
                  sc: float, n: int) -> None:
    """Uma letra recortada batendo na parede: chega grande e girada, assenta, e a
    sombra dura encosta conforme ela pousa."""
    chip, ang, dy, _ = r
    pe = min(1.0, idade / 0.12)
    meio = x + chip.width * sc / 2
    if pe > 0:
        e = 1 - (1 - pe) ** 3
        esc = sc * (1 + 0.7 * (1 - e))
        c2 = chip.rotate(ang + (1 - e) * (26 if n % 2 else -26), resample=Image.BICUBIC, expand=True)
        c2 = c2.resize((max(1, int(c2.width * esc)), max(1, int(c2.height * esc))), Image.BICUBIC)
        sombra = Image.new("RGBA", c2.size, (0, 0, 0, 0))
        sombra.putalpha(c2.split()[3].point(lambda v: int(v * 0.55)))
        lev = 1 + 1.8 * (1 - e)                          # no ar, a sombra cai mais longe
        px, py = meio - c2.width / 2, cy + dy * sc - c2.height / 2
        _compoe(img, sombra, px + 0.05 * w["_corpo"] * sc * lev, py + 0.07 * w["_corpo"] * sc * lev)
        _compoe(img, c2, px, py)


def _carimbo(img: Image.Image, card: dict, t: float, largura: int, altura: int) -> None:
    """A palavra-chave leva um carimbo vermelho: desce acelerando de cima da lente,
    bate (o cartão sacode no `_tranco`) e fica, com a tinta falhada de carimbo."""
    w = _heroi(card)
    a0 = card["_t_in"]
    if t < a0:
        return
    chave = ("carimbo", w["tx"], w["_fonte"], w["_corpo"])
    if chave not in _cache_ass:
        f = fonte(w["_fonte"], w["_corpo"])
        d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
        tw = _larg(d0, w["tx"], f, w.get("track", 0.0))
        bb = f.getbbox(w["tx"], anchor="mm")
        pad, bo = f.size * 0.16, max(4, int(f.size * 0.065))
        W_, H_ = int(tw + 2 * pad + 2 * bo), int(bb[3] - bb[1] + 2 * pad + 2 * bo)
        m = Image.new("L", (W_ + 8, H_ + 8), 0)
        d = ImageDraw.Draw(m)
        d.rounded_rectangle([4, 4, W_ + 4, H_ + 4], radius=int(f.size * 0.08), outline=255, width=bo)
        ins = bo * 1.9
        d.rounded_rectangle([4 + ins, 4 + ins, W_ + 4 - ins, H_ + 4 - ins], radius=int(f.size * 0.05),
                            outline=255, width=max(2, bo // 3))
        _escreve(d, (m.width / 2, m.height / 2 - (bb[1] + bb[3]) / 2), w["tx"], f,
                 w.get("track", 0.0), fill=255)
        # a tinta que falha: manchas grandes e poros miúdos tirados do alfa
        rng = np.random.default_rng(len(w["tx"]) * 7919 + w["_corpo"])
        grossa = Image.fromarray((rng.random((m.height // 9 + 1, m.width // 9 + 1)) * 255).astype(np.uint8))
        grossa = np.asarray(grossa.resize(m.size, Image.BICUBIC), np.float32) / 255
        fina = rng.random(m.size[::-1])
        falha = ((grossa > 0.80) & (fina > 0.35)) | (fina > 0.94)
        # falha forte só na beirada do traço; dentro, a tinta fica (o cabelo
        # preto atravessava o vermelho)
        beira = np.asarray(m, np.float32) - np.asarray(m.filter(ImageFilter.MinFilter(7)), np.float32)
        al = np.asarray(m, np.float32) * np.where(falha, np.where(beira > 0, 0.12, 0.55), 1.0)
        verm = np.array([229, 50, 45], np.float32)
        cor = np.broadcast_to(verm, al.shape + (3,)) * (0.92 + 0.08 * grossa[..., None])
        _cache_ass[chave] = Image.fromarray(np.dstack([cor, al]).astype(np.uint8), "RGBA")
    sp = _cache_ass[chave]
    pe = min(1.0, (t - a0) / CRAVA)
    dt = t - card["_pouso"]
    esc = 1 + 1.3 * (1 - pe) ** 2                  # desce acelerando, como a mão
    if 0 <= dt < 0.07:
        esc *= 0.95 + 0.05 * dt / 0.07             # amassa ao bater e volta
    rnd = random.Random(f"carimbo:{card['t0']:.2f}")
    ang = rnd.choice((-1, 1)) * rnd.uniform(4, 11)     # cada batida torta de um jeito
    s2 = sp.rotate(ang, resample=Image.BICUBIC, expand=True)
    s2 = s2.resize((max(1, int(s2.width * esc)), max(1, int(s2.height * esc))), Image.BICUBIC)
    sombra = Image.new("RGBA", s2.size, (0, 0, 0, 0))
    sombra.putalpha(s2.split()[3].point(lambda v: int(v * 0.4)))
    lev = 1 + 3 * (1 - pe)
    # a moldura do carimbo passa da letra: desce o bastante pra não tapar a
    # frase datilografada em cima
    px, py = w["_cx"] - s2.width / 2, w["_cy"] - s2.height / 2 + w["_corpo"] * 0.1
    _compoe(img, sombra, px + 0.03 * w["_corpo"] * lev, py + 0.045 * w["_corpo"] * lev)
    if dt >= 0:
        # a segunda batida, fantasma: o carimbo que tremeu na mão
        fant = s2.copy()
        fant.putalpha(s2.split()[3].point(lambda v: int(v * 0.25)))
        _compoe(img, fant, px + 6 * largura / W_REF, py - 4 * largura / W_REF)
    _compoe(img, s2, px, py)


ASSINATURAS = {"heroi3d": _heroi3d, "colagem": _colagem, "carimbo": _carimbo}


def luz(t: float, cards: list[dict], largura: int, altura: int) -> Image.Image | None:
    """A sombra do thriller, por CIMA de tudo (até de quem fala: é a lente que
    escurece, não a parede): bordas fechadas no momento e o quadro que apaga e
    pisca vermelho na batida. A luz que SOMA (clarão, flash) é o `brilho`."""
    for c in cards:
        if not (c.get("luz") == "sombra" and c.get("_pouso") is not None and c["t0"] <= t < c["t1"]):
            continue
        dt = t - c["_pouso"]
        vin = _vinheta(largura, altura)
        lay = vin.copy()
        if 0 <= dt < 1 / 30:
            lay.alpha_composite(Image.new("RGBA", lay.size, (0, 0, 0, 115)))
        elif 0 <= dt < 0.3:
            # o alarme acende nas bordas (a vinheta), não no quadro inteiro, que
            # ficava marrom
            k = 110 / 150 * math.exp(-dt / 0.08)
            verm = Image.new("RGBA", lay.size, (229, 50, 45, 0))
            verm.putalpha(vin.split()[3].point(lambda v: int(min(255, v * k * 1.7))))
            lay.alpha_composite(verm)
        return lay
    return None


def brilho(t: float, cards: list[dict], largura: int, altura: int) -> np.ndarray | None:
    """A luz que SOMA à imagem, em RGB sobre preto, pra entrar em modo tela
    (screen) por cima do quadro pronto: luz de verdade clareia sem lavar.
    `ouro`: o clarão quente que nasce na palavra quando ela crava e o vazamento
    laranja que atravessa o quadro (Light Flash e Light Leak do Melies);
    `flash`: o flash de foto da revista, um quadro estourado que cai em quatro."""
    for c in cards:
        if not (c.get("luz") in ("ouro", "flash") and c.get("_pouso") is not None
                and c["t0"] <= t < c["t1"]):
            continue
        dt = t - c["_pouso"]
        if c["luz"] == "flash":
            if dt < 0:
                return None
            a = 0.8 if dt < 1 / 30 else 0.8 * math.exp(-(dt - 1 / 30) / 0.035)
            return None if a < 0.01 else np.full((altura, largura, 3), 255 * a, np.float32)
        out = np.zeros((altura, largura, 3), np.float32)
        u = (t - c["_t_in"]) / 0.5
        if 0 <= u < 1:
            vaz = _vazamento(largura, altura)
            env = math.sin(math.pi * u) ** 0.7 * 0.5
            dx, dy = int((-0.55 + 0.75 * u) * largura), int((-0.10 + 0.06 * u) * altura)
            src = vaz[max(0, -dy):altura - max(0, dy), max(0, -dx):largura - max(0, dx)]
            out[max(0, dy):max(0, dy) + src.shape[0], max(0, dx):max(0, dx) + src.shape[1]] += src * env
        if dt >= 0:
            h = next((w for w in c["words"] if w.get("_heroi")), None)
            cx, cy = (h.get("_cx", largura / 2), h.get("_cy", altura / 2)) if h else (largura / 2, altura / 2)
            yy, xx = np.ogrid[0:altura, 0:largura]
            r = np.hypot((xx - cx) / largura, (yy - cy) / largura)
            k = math.exp(-dt / 0.06)
            out += (np.clip(1 - r / 0.95, 0, 1) ** 1.3 * 255 * 0.9 * k)[..., None] * np.array([1.0, 0.93, 0.8])
        return np.clip(out, 0, 255) if out.max() > 2 else None
    return None


def _vazamento(largura: int, altura: int) -> np.ndarray:
    """Duas manchas de luz quente, laranja e ouro, em RGB pré-multiplicado."""
    chave = ("vaz", largura, altura)
    if chave not in _cache_ass:
        h, w_ = 240, 135
        yy, xx = np.mgrid[0:h, 0:w_].astype(np.float32)

        def mancha(cx, cy, r):
            return np.clip(1 - np.hypot((xx - cx * w_) / (r * w_), (yy - cy * h) / (r * w_ * 1.6)), 0, 1) ** 1.8
        # no alto, na altura da palavra: na do rosto a pele ficava verde-amarela
        m1, m2 = mancha(0.5, 0.18, 0.8), mancha(0.35, 0.25, 0.45)
        rgb = (np.array([255, 105, 20], np.float32) * m1[..., None] * 0.9
               + np.array([255, 200, 90], np.float32) * m2[..., None])
        im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").resize((largura, altura), Image.BICUBIC)
        _cache_ass[chave] = np.asarray(im, np.float32)
    return _cache_ass[chave]


def _vinheta(largura: int, altura: int) -> Image.Image:
    chave = ("vinheta", largura, altura)
    if chave not in _cache_ass:
        yy, xx = np.mgrid[0:96, 0:54].astype(np.float32)
        r = np.hypot((xx - 27) / 27, (yy - 48) / 48)
        al = (np.clip((r - 0.55) / 0.6, 0, 1) ** 1.5 * 150).astype(np.uint8)
        _cache_ass[chave] = Image.fromarray(np.dstack([np.zeros((96, 54, 3), np.uint8), al]), "RGBA").resize(
            (largura, altura), Image.BICUBIC)
    return _cache_ass[chave]


def cues(cards: list[dict]) -> list[dict]:
    """Os golpes das assinaturas como cues do sfx.json: o som.py põe o PICO medido
    de cada um no instante do golpe. O de cinema (`primeiro`) só no primeiro
    momento do sistema: o teto é três por vídeo."""
    out, ja = [], set()
    for c in sorted(cards, key=lambda c: c["t0"]):
        s = c.get("sons")
        if not s or c.get("_t_in") is None:
            continue
        if s.get("crava"):
            out.append({"tipo": s["crava"], "t": c["_t_in"]})
        for w in c["words"]:
            if s.get("maquina") and w.get("entrada") == "maquina":
                out.append({"tipo": s["maquina"], "t": round(w["t0"], 3),
                            "dur": round(min(len(w["tx"]) * _passo_maquina(w), w["t1"] - w["t0"] + 0.1), 3)})
        if s.get("golpe"):
            out.append({"tipo": s["golpe"], "t": c["_pouso"]})
        if s.get("fim") and c.get("assinatura") == "colagem":
            out.append({"tipo": s["fim"], "t": round(c["_t_in"] + _colagem_dur(c), 3)})
        if s.get("primeiro") and c.get("_preset") not in ja:
            ja.add(c.get("_preset"))
            out.append({"tipo": s["primeiro"], "t": c["_pouso"]})
    return sorted(out, key=lambda x: x["t"])


_EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"


def _emoji(d: ImageDraw.ImageDraw, txt: str, cx: float, pe: float, alvo: float) -> None:
    """Emoji colorido em cima da palavra (`"emoji": "💰"` na palavra do plano).

    A fonte da Apple só abre nos tamanhos que ela traz desenhados, então vale o
    maior que cabe no alvo. Fora do Mac não há fonte de emoji: ele não sai, e a
    palavra sai igual."""
    tam = max([s for s in (20, 32, 40, 48, 64, 96, 160) if s <= alvo] or [20])
    chave = ("_emoji", tam)
    if chave not in _cache_fonte:
        try:
            _cache_fonte[chave] = ImageFont.truetype(_EMOJI, tam)
        except OSError:
            return
    d.text((cx, pe), txt, font=_cache_fonte[chave], anchor="md", embedded_color=True)


def estado(t: float, cards: list[dict], fps: int) -> tuple:
    """Chave do frame. Frame animado é sempre único; card assentado repete.

    A chave cobre TODOS os cards ativos — com duas camadas, o gancho parado
    reaproveitaria o frame errado se só a legenda entrasse na conta.
    """
    chave = []
    for i, c in enumerate(cards):
        if not (c["t0"] <= t < c["t1"]):
            continue
        f = int((t - c["t0"]) * fps)
        movendo = (
            (t - c["t0"]) <= ENTRADA + STAGGER * len(c["words"])
            or (c.get("saida") and c["t1"] - t < SAIDA)
            or c["anim"] == "revela"
            or any(w.get("enf") == "punch" for w in c["words"])
            or c.get("assinatura")
        )
        if movendo:
            chave.append((i, f))
        else:
            chave.append((i, -1,
                          tuple(1 if w["t0"] <= t < w["t1"] else 0 for w in c["words"]),
                          tuple(1 if t >= w["t0"] else 0 for w in c["words"])))
    return tuple(chave) if chave else (-1,)


# ------------------------------------------------------------ main

_CTX: dict | None = None   # o que o desenho de um quadro lê e não muda de um quadro pro outro; cada processo recebe uma vez
# o que `aplicar_plano` troca no módulo: o processo novo (spawn) importa o padrão, então o estado viaja com ele
_ESTADO = ("ENTRADA", "STAGGER", "SAIDA", "HOT", "ENFASE", "LAYOUTS")


def pintar_quadro(i: int, d: dict, c: dict) -> None:
    """Desenha o quadro `i` e grava `c["tmp"]/NNNNNN.png`. `c` é o que vale pro vídeo todo (cards, volume, tamanho,
    pastas); `d`, o que é só deste quadro (b-roll, tela, gráfico e recortes), de modo que o processo que desenha
    receba o recorte de 2 MB do quadro e não o de todos."""
    cards, largura, altura, vol, tmp = c["cards"], c["largura"], c["altura"], c["vol"], c["tmp"]
    t, alvo = i / c["fps"], tmp / f"{i:06d}.png"
    sis = c["sis"]
    if sis:
        luzes = c["luzes"]
        br = brilho(t, cards, largura, altura)
        if br is None:
            os.link(luzes / "preto.png", luzes / f"{i:06d}.png")
        else:
            Image.fromarray(br.astype(np.uint8), "RGB").save(luzes / f"{i:06d}.png", compress_level=1)
    if i in c["reaproveita"]:
        return
    alfa_frame, alfa_broll = d.get("alfa_frame"), d.get("alfa_broll")
    frente = None
    if sis and alfa_frame is not None:
        # só o herói passa atrás de quem fala: a legenda que segue rolando
        # embaixo enquanto ele segura no alto fica na frente, inteira
        img = desenhar(t, [x for x in cards if x.get("atras")], largura, altura, vol)
        frente = desenhar(t, [x for x in cards if not x.get("atras")], largura, altura, vol)
    else:
        img = desenhar(t, cards, largura, altura, vol)
    if d.get("brl") is not None:
        fundo = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        atras = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        for cam, cfg, rel in d["brl"]:
            pb = pintar_broll(cam, cfg, rel, largura, altura)
            (atras if cfg.get("atras") else fundo).alpha_composite(pb)
        if alfa_broll is not None:
            # fura a camada de trás com a silhueta: a pessoa fica NA
            # FRENTE do painel, e o vídeo de baixo já tem a pessoa
            px = np.array(atras)
            px[..., 3] = (px[..., 3].astype(np.uint16)
                          * (255 - alfa_broll) // 255).astype(np.uint8)
            atras = Image.fromarray(px)
        atras.alpha_composite(fundo)
        atras.alpha_composite(img)
        img = atras
    if d.get("tela") is not None:
        # a tela vai por baixo de tudo: ela é o assunto, a legenda narra
        g = pintar_tela(*d["tela"], largura, altura)
        g.alpha_composite(img)
        img = g
    if d.get("overlay") is not None:
        # gráfico entra POR BAIXO do texto: a legenda é que tem que ler
        g = pintar_overlay(*d["overlay"], largura, altura)
        g.alpha_composite(img)
        img = g
    if alfa_frame is not None:
        # fura o texto com a silhueta: a pessoa passa a estar NA FRENTE.
        # O vídeo de baixo já tem a pessoa — o buraco basta, sem recompor.
        px = np.array(img)
        px[..., 3] = (px[..., 3].astype(np.uint16)
                      * (255 - alfa_frame) // 255).astype(np.uint8)
        img = Image.fromarray(px)
    if frente is not None:
        img.alpha_composite(frente)
    if sis:
        lz = luz(t, cards, largura, altura)      # depois do recorte: a luz é da lente
        if lz is not None:
            img.alpha_composite(lz)
    img.save(alvo, compress_level=1)


def _inicia(c: dict, estado: dict) -> None:
    """Primeira coisa de cada processo que desenha: guarda o contexto e põe o estado do módulo como o pai deixou."""
    global _CTX
    globals().update(estado)
    _CTX = c


def _filho(par: tuple[int, dict]) -> None:
    pintar_quadro(par[0], par[1], _CTX)


def processos() -> int:
    """Quantos processos desenham quadros: um núcleo fica pro ffmpeg e pro resto da máquina, e quatro bastam
    (cada quadro é PIL e numpy; acima disso o disco de PNG é que segura)."""
    return max(1, min(4, (os.cpu_count() or 1) - 1))


def pintar_quadros(quadros: list[int], dados, c: dict, procs: int) -> int:
    """Desenha cada quadro de `quadros` (ver `pintar_quadro`; `dados(i)` dá o `d` dele). Cada quadro grava o próprio
    arquivo e não depende de outro, então a ordem não muda o resultado: com `procs` > 1 os quadros se repartem
    entre processos do contexto padrão da plataforma (spawn no Mac e no Windows), cada um com o contexto uma vez
    só. Com poucos quadros, desenha em série (o processo novo custa mais que o ganho).
    Devolve quantos processos desenharam."""
    if procs <= 1 or len(quadros) < 4 * procs:
        for i in quadros:
            pintar_quadro(i, dados(i), c)
        return 1
    estado = {k: globals()[k] for k in _ESTADO}
    with ProcessPoolExecutor(procs, initializer=_inicia, initargs=(c, estado)) as ex:
        # blocos de quadros vizinhos: o cache de sprite e de fonte de cada processo serve ao quadro seguinte
        for _ in ex.map(_filho, ((i, dados(i)) for i in quadros), chunksize=max(1, min(16, len(quadros) // (procs * 4)))):
            pass
    return procs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--dividida", type=Path, help="o `dividida.json` do `tela_dividida.py`: a legenda desses trechos termina acima do cabelo")
    ap.add_argument("--words", type=Path)
    ap.add_argument("--style", choices=["destaque", "pop", "karaoke"], default="destaque")
    ap.add_argument("--dur", type=float, default=None)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--y-fixo", action="store_true",
                    help="usa o y nominal do layout em vez de fugir do sujeito")
    ap.add_argument("--matte", default=MATTE_PADRAO,
                    choices=["u2net_human_seg", "birefnet-portrait"],
                    help="recorte dos cards herói: u2net p/ iterar (0.4s/frame), "
                         "birefnet p/ o corte final (9.6s/frame, com cache)")
    ap.add_argument("--fonte-alpha", type=Path, default=None,
                    help="vídeo com alpha (webm do HeyGen, ProRes 4444) de onde "
                         "tirar o matte. Recorte exato e sem custo de modelo")
    ap.add_argument("--matte-fps", type=int, default=10,
                    help="taxa do matte de b-roll. A silhueta de quem fala muda "
                         "devagar: 10fps custa um terço de 30 e a borda não denuncia")
    ap.add_argument("--procs", type=int, default=None,
                    help="processos que desenham os quadros (1 = em série; padrão: até 4, deixando um núcleo livre)")
    ap.add_argument("--quadros", default=None,
                    help="t1,t2,...: desenha só estes instantes (a legenda do storyboard) e grava <out>/<t:.3f>.jpg, sem o vídeo "
                         "todo, câmera nem peça. -o é a pasta")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    if not a.plan and not a.words:
        sys.exit("passe --plan (dirigido) ou --words (uniforme)")

    largura, altura, dur_video = probe(a.video)
    dur = min(a.dur, dur_video) if a.dur else dur_video

    brolls: list[dict] = []
    nativas: list[dict] = []
    cenas: list[dict] = []
    if a.plan:
        _plano = json.loads(a.plan.read_text(encoding="utf-8"))
        if isinstance(_plano, list):      # a saída crua do cards_da_fala: só cards
            _plano = {"cards": _plano}
        if a.dividida and a.dividida.exists():
            _plano["dividida"] = json.loads(a.dividida.read_text(encoding="utf-8"))
        aplicar_plano(_plano)
        brolls = [b for b in (_plano.get("brolls") or []) if float(b["t0"]) < dur]
        brolls, nativas = separa_nativas(brolls)
        cenas = [c for c in (_plano.get("camera") or []) if float(c["t0"]) < dur]
        cards = [c for c in finalizar(_plano["cards"]) if c["t0"] < dur]
        if any(c.get("tela") or c.get("overlay") for c in cards):
            # a tela e o gráfico do card vão por baixo da camada de PNG; a peça ia por cima deles.
            # Com eles no bloco, a peça fica no quadro a quadro pra empilhar como antes
            brolls, nativas = brolls + nativas, []
    else:
        palavras = carregar_palavras(a.words, dur)
        if not palavras:
            sys.exit("nenhuma palavra no intervalo")
        cards = plano_uniforme(palavras, dur, a.style)

    if a.quadros:       # só o instante: nada que mexe no vídeo todo (câmera, peça) entra
        brolls, nativas, cenas = [], [], []
    vol = mapa_volume(a.video, dur)
    k = largura / W_REF
    avisos = []
    # sistema de cinema com assinatura: a luz por cima, a câmera que crava e os
    # cues. Sem assinatura nenhum desses caminhos roda (o padrão sai igual)
    sis = any(c.get("assinatura") for c in cards)
    cam_sis = sis and bool(cenas)
    # o layout diz se o bloco encosta no pe da caixa (ver `diagramar`)
    for c in cards:
        c["_base"] = LAYOUTS.get(c["layout"], LAYOUTS["faixa"]).get("base", False)
    if a.y_fixo:
        for c in cards:
            lay = LAYOUTS.get(c["layout"], LAYOUTS["faixa"])
            c["_y"] = int((lay["zona"][0] + lay["zona"][1]) / 2 * altura - lay["h"] * k / 2)
    elif cards:
        # o movimento e o sujeito só servem pra assentar card: bloco só com peça não paga a análise
        mov, t_mov = mapa_movimento(a.video, dur, largura, altura)
        suj, t_suj = mapa_sujeito(a.video, dur, largura, altura)
        for c in cards:
            lay = LAYOUTS.get(c["layout"], LAYOUTS["faixa"])
            if c.get("atras"):
                # card herói NÃO desvia: ele senta no meio da zona e o sujeito
                # passa por cima. A colisão é o efeito.
                c["_y"] = int((lay["zona"][0] + lay["zona"][1]) / 2 * altura
                              - lay["h"] * k / 2)
                continue
            if c.get("pe") and c.get("pe_fixo"):
                # o pé cravado, sem seguir o ombro: na mesa filmada de cima as mãos sobem
                # e descem, e a legenda pulava do rodapé pro meio da tela (longo do semanal, 07/10)
                c["_y"] = int(c["pe"] * altura - lay["h"] * k)
                continue
            # Video sem sujeito (o quadro) nao tem linha de ombro: a busca
            # devolve um numero qualquer e a legenda para onde calhar. Medido no
            # short de webhook, ela acabava em 1270 com 200px de tela livre
            # embaixo. Sem mascara de gente, manda a zona.
            if c["layout"] == "faixa" and not c.get("sobre_rosto") and suj.max() > 0.02:
                # Colocação DIRETA abaixo do ombro, não busca por zona: a caixa
                # de 500px não cabe entre o ombro (~69%) e o teto da UI do
                # Instagram (~88%), então procurar "o mais quieto" ali devolve
                # posição inválida e cai no fallback — que é o rosto de novo.
                ombro = linha_do_ombro(suj, t_suj, c["t0"], c["t1"], altura)
                centro = min(altura * 0.83, ombro + altura * 0.06)
                c["_y"] = int(centro - lay["h"] * k / 2)
                if c.get("pe"):
                    # o pé da legenda (letra, sombra e rastro) acima da interface
                    # do Reels: o ombro do avatar que enche o quadro a jogava em 1595
                    c["_y"] = min(c["_y"], int(c["pe"] * altura - lay["h"] * k))
                continue
            if c.get("_no_alto"):
                c["_y"] = int(lay["zona"][0] * altura)     # encostado no teto da zona
                continue
            c["_y"], ocup = melhor_y(suj, t_suj, mov, t_mov, c["t0"], c["t1"],
                                     lay["zona"], int(lay["h"] * k), altura)
            # `faixa` é sobre o corpo por definição — texto no peito é o normal
            # e não merece aviso. Só centro/topo indicam intenção de achar ar.
            if c["layout"] != "faixa" and ocup > 0.55:
                avisos.append(f'  {c["t0"]:5.2f}s {c["layout"]}: {ocup:.0%} em cima do '
                              f'sujeito — use "atras": true ou mande pra faixa')

    fundo_dos_cards(a.video, cards, altura, k)

    # frames dos cards herói precisam do recorte do sujeito em resolução cheia
    alfa_frame: dict[int, np.ndarray] = {}
    alfa_broll: dict[int, np.ndarray] = {}
    cam_alfa: dict = {}

    # b-roll com `atras`: o painel desce POR TRÁS da pessoa e a cabeça quebra a
    # borda dele. Sem isso o painel corta o quadro numa linha reta e lê como
    # adesivo — o degradê sozinho suaviza a borda mas não cria profundidade.
    br_atras = [b for b in brolls if b.get("atras")]
    if br_atras:
        cache_b = a.video.parent / f".{a.video.stem}_matte_{a.matte}_{a.matte_fps}"
        with tempfile.TemporaryDirectory() as td:
            for j, b in enumerate(br_atras):
                t0, t1 = float(b["t0"]), min(float(b["t1"]), dur)
                sub = Path(td) / f"b{j}"
                sub.mkdir()
                # Matte AMOSTRADO, não quadro a quadro. A silhueta de quem fala
                # muda devagar; a 30fps eu pagava três vezes pelo mesmo recorte.
                # O que o olho pega é a borda, e ela quase não anda em 1/10s.
                ff.run(
                    ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}",
                     "-t", f"{t1 - t0:.3f}", "-i", str(a.fonte_alpha or a.video),
                     "-vf", f"fps={a.matte_fps}",
                     "-pix_fmt", "rgba" if a.fonte_alpha else "rgb24",
                     f"{sub}/%05d.png"], quiet=True)
                amostras = sorted(sub.glob("*.png"))
                if not amostras:
                    continue
                alfas = [_alfa_cache(f, cache_b / f"br{t0:.2f}", a.matte)
                         for f in amostras]
                ini, fim = int(round(t0 * a.fps)), int(round(t1 * a.fps))
                for idx in range(max(0, ini), min(fim, int(dur * a.fps))):
                    s = int((idx - ini) / a.fps * a.matte_fps)
                    alfa_broll[idx] = alfas[min(s, len(alfas) - 1)]
                    if cenas:
                        # o recorte sai do quadro parado; a câmera depois move a pessoa,
                        # então o recorte vai pra onde ela foi (como no herói, abaixo)
                        z, foco = zoom_em(idx / a.fps, cenas, a.fps)
                        k = (j, min(s, len(alfas) - 1), round(z, 4), tuple(round(v, 4) for v in foco))
                        if k not in cam_alfa:
                            cam_alfa[k] = na_camera(alfa_broll[idx], z, foco)
                        alfa_broll[idx] = cam_alfa[k]
        print(f"  matte do b-roll: {len(alfa_broll)} frames cobertos por "
              f"{sum(1 for _ in set(id(v) for v in alfa_broll.values()))} recortes "
              f"a {a.matte_fps}fps")
    pedidos = [float(x) for x in a.quadros.split(",")] if a.quadros else []
    quer = {max(0, min(int(dur * a.fps) - 1, round(t * a.fps))) for t in pedidos} if a.quadros else None
    heróis = [c for c in cards if c.get("atras")]
    if heróis:
        with tempfile.TemporaryDirectory() as td:
            for j, c in enumerate(heróis):
                sub = Path(td) / str(j)
                sub.mkdir()
                ff.run(
                    ["ffmpeg", "-v", "error", "-ss", f'{c["t0"]:.3f}',
                     "-t", f'{c["t1"] - c["t0"]:.3f}',
                     "-i", str(a.fonte_alpha or a.video),
                     "-vf", f"fps={a.fps}",
                     "-pix_fmt", "rgba" if a.fonte_alpha else "rgb24",
                     f"{sub}/%05d.png"], quiet=True)
                base = int(round(c["t0"] * a.fps))
                cache = a.video.parent / f".{a.video.stem}_matte_{a.matte}"
                do_card = []
                for f in sorted(sub.glob("*.png")):
                    idx = base + int(f.stem) - 1
                    if quer is not None and idx not in quer:
                        continue        # o matte custa segundos por quadro: só o do instante pedido
                    if 0 <= idx < int(dur * a.fps):
                        alvo = cache / f"{c['t0']:.2f}"
                        if sis:
                            # cache pelo quadro do vídeo, não pelo cartão: os
                            # sistemas cortam cartões diferentes na mesma fala e
                            # o birefnet (9,6 s/quadro) se paga uma vez só
                            f = f.rename(f.with_name(f"q{idx:06d}.png"))
                            alvo = cache / "quadros"
                        alfa_frame[idx] = _alfa_cache(f, alvo, a.matte)
                        if cam_sis:
                            # o recorte sai do quadro parado (com cache) e vai
                            # pra onde a câmera que crava levou a pessoa
                            alfa_frame[idx] = na_camera(alfa_frame[idx],
                                                        *zoom_em(idx / a.fps, cenas, a.fps))
                        do_card.append(alfa_frame[idx])
                if not do_card:
                    continue
                pior, geral, dy, dx = ajustar_heroi(c, do_card, largura, altura)
                if c.get("assinatura"):
                    # a assinatura pede a letra quase inteira: a cabeça morde até
                    # ~25 % dela; se não houver lugar assim, fica a régua de sempre
                    melhor = ajustar_heroi(c, do_card, largura, altura,
                                           piso_letra=0.75, alvo_geral=0.93)
                    if melhor[0] >= 0.75:
                        pior, geral, dy, dx = melhor
                c["_dy"], c["_dx"] = dy, dx
                if pior < 0:
                    c["atras"] = False
                    for i in range(base, base + len(do_card)):
                        alfa_frame.pop(i, None)
                    avisos.append(f'  {c["t0"]:5.2f}s herói: texto largo demais pro '
                                  f'quadro, sem deslocamento possível — FRENTE')
                elif pior < 0.60:
                    c["atras"] = False                    # letra sumindo: vai pra frente
                    for i in range(base, base + len(do_card)):
                        alfa_frame.pop(i, None)
                    avisos.append(f'  {c["t0"]:5.2f}s herói: a pior letra ficava só '
                                  f'{pior:.0%} visível — desenhei na FRENTE')
                else:
                    avisos.append(f'  {c["t0"]:5.2f}s herói: pior letra {pior:.0%}, '
                                  f'geral {geral:.0%} (dy={dy} dx={dx})')
        print(f"  matte: {len(alfa_frame)} frames de {len(heróis)} card(s) herói")

    n = int(dur * a.fps)
    fonte_audio = a.video          # o áudio NUNCA sai daqui, nem passa pela câmera
    if not ff.probe(fonte_audio).tem_audio:
        # o `-map 2:a?` lá embaixo é opcional: sem esta linha, uma fonte muda vira vídeo mudo sem aviso
        print(f"  AVISO: {Path(fonte_audio).name} não tem faixa de áudio — o vídeo sai mudo")
    tmp = Path(tempfile.mkdtemp(prefix="capviral_"))
    if cenas:
        # move a câmera primeiro: o matte do sujeito precisa ser tirado do
        # quadro JÁ deslocado, senão a silhueta não bate com o que se vê
        fonte_audio = a.video
        a.video = camera_cenas(a.video, cenas, dur, a.fps, largura, altura, tmp)
        print(f"  câmera: {len(cenas)} cena(s) movida(s)")
    reaproveitados = 0
    try:
        overlays = preparar_overlays(cards, a.fps, dur, largura, altura, tmp)
        if overlays:
            print(f"  overlay: {len(overlays)} frames de matte")
        telas = preparar_telas(cards, a.fps, dur, largura, tmp)
        if telas:
            print(f"  tela: {len(telas)} frames de captura")
        brl = preparar_brolls(brolls, a.fps, dur, largura, tmp,
                              a.plan.parent if a.plan else Path("."), a.video, altura)
        if brl:
            # nome próprio: `n` é o total de frames do vídeo. Reusar aqui
            # encurtava o loop pro número de CAMADAS, e o que passasse disso
            # saía congelado no último quadro composto.
            camadas = sum(len(v) for v in brl.values())
            print(f"  b-roll: {len(brolls)} clipes, {len(brl)} frames, "
                  f"{camadas} camadas")
        anterior, arq_anterior = None, None
        # nada pra desenhar quadro a quadro (o bloco só com peça, que vai pelo overlay nativo):
        # sem a camada de PNGs transparentes, que custava escrever, ler e compor à toa
        vazio = not (cards or overlays or telas or brl or sis)
        if vazio:
            n = 0
        if sis:
            # a luz que soma (clarão, flash) vai numa trilha própria, em modo tela
            luzes = tmp / "luz"
            luzes.mkdir()
            Image.new("RGB", (largura, altura)).save(luzes / "preto.png")
        # o plano do quadro a quadro, em série e barato: quais quadros se desenham e quais herdam o anterior
        reaproveita: dict[int, Path] = {}
        desenha: list[int] = []
        for i in (quer if quer is not None else range(n)):
            chave = estado(i / a.fps, cards, a.fps)
            com_camada = i in brl or i in overlays or i in telas or i in alfa_frame or i in alfa_broll
            if chave == anterior and arq_anterior is not None and not com_camada:
                reaproveita[i] = arq_anterior
                continue
            desenha.append(i)
            # quadro com camada (b-roll, tela, matte) não serve de molde: o seguinte sem camada herdava o fantasma
            anterior, arq_anterior = (None, None) if com_camada else (chave, tmp / f"{i:06d}.png")

        t_quadros = time.perf_counter()
        ctx = dict(cards=cards, vol=vol, largura=largura, altura=altura, fps=a.fps, sis=sis, tmp=tmp,
                   luzes=luzes if sis else None, reaproveita=frozenset(reaproveita))
        dados = lambda i: {"brl": brl.get(i), "overlay": overlays.get(i), "tela": telas.get(i),
                           "alfa_frame": alfa_frame.get(i), "alfa_broll": alfa_broll.get(i)}
        usou = pintar_quadros(list(range(n)) if sis and quer is None else desenha, dados, ctx, a.procs or processos())   # a luz (sis) sai de TODO quadro
        for i, molde in reaproveita.items():
            os.link(molde, tmp / f"{i:06d}.png")
        reaproveitados = len(reaproveita)
        if n:
            print(f"  quadros: {len(desenha)} desenhados e {reaproveitados} reaproveitados em "
                  f"{time.perf_counter() - t_quadros:.1f}s, {usou} processo(s)")

        if quer is not None:
            # a prévia do storyboard: o quadro do vídeo com a legenda por cima, um JPEG por instante pedido
            a.out.mkdir(parents=True, exist_ok=True)

            def tira(i: int) -> None:       # uma busca por quadro; em fila eram 0,2 s cada (15 s em 60 quadros)
                ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{i / a.fps:.3f}", "-i", str(a.video), "-frames:v", "1",
                        str(tmp / f"b{i:06d}.png")], quiet=True)

            with ThreadPoolExecutor(a.procs or processos()) as ex:
                list(ex.map(tira, sorted(quer)))
            for t in pedidos:
                i = max(0, min(int(dur * a.fps) - 1, round(t * a.fps)))
                bruto = tmp / f"b{i:06d}.png"
                img = Image.open(bruto).convert("RGBA")
                img.alpha_composite(Image.open(tmp / f"{i:06d}.png").convert("RGBA"))
                img.convert("RGB").save(a.out / f"{t:.3f}.jpg", quality=90)
            print(f"{a.out}  ({len(quer)} quadros com a legenda)")
            return

        # as peças da biblioteca entram por baixo da legenda, pelo overlay nativo do v2
        entra_pecas, sob, base = [], [], "0:v"
        escuro = fundo_escuro(_plano.get("brolls") or [], dur) if a.plan else ""
        if escuro:
            sob, base = [f"[0:v]{escuro}[esc]"], "esc"
        if nativas:
            entra_pecas, nativo, base = _v2().grafo_sobre(
                [_peca_nativa(b, a.fps, largura, altura) for b in nativas], base, 4 if sis else 3)
            sob += nativo
            print(f"  peças: {len(nativas)} por cima do vídeo, sem passar quadro a quadro")
        if sis:
            entra_luz = ["-framerate", str(a.fps), "-i", str(luzes / "%06d.png")]
            grafo = (f"[{base}][1:v]overlay=0:0:format=auto,format=gbrp[b];[3:v]format=gbrp[l];"
                     f"[b][l]blend=all_mode=screen,format={ff.PIX_FMT}[v]")
        elif vazio:
            entra_luz, grafo = [], f"[{base}]null[v]"
        else:
            entra_luz, grafo = [], f"[{base}][1:v]overlay=0:0:format=auto[v]"
        ff.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{dur}", "-i", str(a.video),
             # vazio: a fonte de novo no lugar da camada, pros índices das entradas não mudarem
             *(["-i", str(a.video)] if vazio else ["-framerate", str(a.fps), "-i", str(tmp / "%06d.png")]),
             "-t", f"{dur}", "-i", str(fonte_audio), *entra_luz, *entra_pecas,
             "-filter_complex", ";".join([*sob, grafo]),
             "-map", "[v]", "-map", "2:a?", "-t", f"{dur}",
             *ff.args_video("reel", fps=None),
             "-c:a", ff.CODEC_AUDIO, "-b:a", "160k", str(a.out)], quiet=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"{a.out}  ({len(cards)} cards, {n} frames desenhados, {reaproveitados} reaproveitados)")
    if sis and cues(cards):
        # os golpes ao lado do vídeo, no formato que o som.py lê (`cues_de`)
        a.out.with_suffix(".cues.json").write_text(json.dumps(
            {"duracao": round(dur, 3), "cues": cues(cards)}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"  {len(cues(cards))} cue(s) de som em {a.out.with_suffix('.cues.json').name}")
    for av in avisos:
        print(av)
    print("  CONFIRA OS FRAMES: a máscara é do SUJEITO, não dos objetos. "
          "Microfone, luminária e texto na tela são invisíveis pra ela.")


def _tempo(c: dict) -> list[str]:
    """O que impede o card de ser lido, pelo tempo. O lint reprova com isto e o
    preset junta cartão até isto calar."""
    dur, n = c["t1"] - c["t0"], len(c["words"])
    erros = []
    # O PISO DEPENDE DE QUANTAS PALAVRAS O CARD TEM.
    #
    # 0,35s e a regua de card com frase: abaixo disso o olho nao termina de
    # varrer e a leitura pisca. Card de UMA palavra e outra coisa -- e
    # karaoke, o olho ja esta no lugar e so troca o que esta escrito, e a
    # velocidade e a da fala. O estilo 7a e todo assim, e com o piso unico
    # ele reprovava 200 cards que estao certos.
    piso = 0.35 if n > 1 else 0.14
    if dur < piso:
        erros.append(f"card de {dur:.2f}s com {n} palavra(s) — ninguém lê abaixo de {piso}")
    # ENTRAR NÃO É ESTAR LEGÍVEL. A última palavra do card só assenta em
    # t0 + ENTRADA + STAGGER*(n-1); o que sobra até t1 é o tempo em que a
    # frase inteira está na tela. Medir o intervalo cru aprova card de meio
    # segundo com quatro palavras — 0,47s entrando e 0,03s legível.
    # `anim: nenhuma` (corte seco): o card nasce inteiro em t0, não há entrada a esperar
    entrando = 0.0 if c.get("anim") == "nenhuma" else ENTRADA + STAGGER * (n - 1)
    legivel = dur - entrando
    if n > 1:
        if legivel <= 0:
            erros.append(f"acaba antes de terminar de entrar "
                         f"({dur:.2f}s de card, {entrando:.2f}s de entrada)")
        elif legivel < 0.12:
            erros.append(f"só {legivel:.2f}s com a frase inteira na tela"
                         f" — entra em {entrando:.2f}s e já sai")
    return erros


def _linhas(card: dict) -> int:
    """Em quantas linhas o card sai, diagramado de verdade a 1080."""
    c = finalizar([json.loads(json.dumps(card))])[0]
    lay = LAYOUTS.get(c["layout"], LAYOUTS["faixa"])
    ws = diagramar(c, W_REF, int(c.get("corpo", lay["corpo"])), c.get("fonte", FONTE_PADRAO),
                   ImageDraw.Draw(Image.new("RGBA", (1, 1))), 0, lay["h"])
    return len({round(w["_cy"]) for w in ws})


def _lint(caminho: Path) -> int:
    """Confere o plano contra as regras da skill. Rode ANTES de renderizar —
    o render leva minutos por causa do matte; isto leva um segundo.

    O teto de palavras conta só palavra CHEIA: filler é encolhido e apagado, não
    custa leitura como as outras.
    """
    plano = json.loads(caminho.read_text(encoding="utf-8"))
    if isinstance(plano, list):
        plano = {"cards": plano}
    aplicar_plano(plano)
    cards = sorted(plano["cards"], key=lambda c: c["t0"])
    erros, avisos = [], []
    punch, herois = [], []

    # Onde o TRATAMENTO do texto muda: a câmera troca de cena (o corpo dele pula
    # de lugar) ou um painel de tela cheia entra e sai (ele deixa de estar
    # exposto). Uma legenda que atravessa esse instante nasce num regime e morre
    # noutro — pisca por cima do gráfico ou fica sem lugar quando a câmera anda.
    # (a câmera que crava no herói não conta: ela anda DENTRO do cartão dele)
    cortes = sorted({round(float(v), 3)
                     for c in (plano.get("camera") or []) if not c.get("_crava")
                     for v in (c["t0"], c["t1"])}
                    | {round(float(v), 3)
                       for b in (plano.get("brolls") or [])
                       # peça com alpha não tapa ninguém: ela flutua sobre a
                       # imagem e o apresentador continua exposto, então não há
                       # troca de tratamento pra legenda atravessar
                       if float(b.get("alt", 0)) >= 0.9 and not b.get("alfa")
                       for v in (b["t0"], b["t1"])})

    # sobreposição só é erro DENTRO da mesma camada: gancho e legenda convivem
    for cam in {c.get("camada", "legenda") for c in cards}:
        fila = [c for c in cards if c.get("camada", "legenda") == cam]
        for a, b in zip(fila, fila[1:]):
            if a["t1"] > b["t0"] + 1e-6:
                erros.append(f'{a["t0"]:6.2f}s  invade o card seguinte (camada {cam})')

    for c in cards:
        t0, t1 = c["t0"], c["t1"]
        erros += [f"{t0:6.2f}s  {m}" for m in _tempo(c)]
        # O CHECK_LINES DA LEGENDA: quebra de linha no meio da frase, medida
        # com a diagramação de verdade. O preset corta o cartão no tempo pra
        # caber numa linha; se ainda assim quebrar, reprova.
        # o bloco do momento-chave tem uma linha por papel, de propósito
        if c.get("_preset") and _linhas(c) > (len(c["words"]) if c.get("quebra") == "palavra" else 1):
            erros.append(f"{t0:6.2f}s  quebra em {_linhas(c)} linhas no meio da frase "
                         f"(preset {c['_preset']})")
        # a folga é de UM frame: com mais que isso, um card que começa dois
        # frames antes do painel e roda dois segundos embaixo dele passa batido
        cruza = [x for x in cortes if t0 + 1 / 30 < x < t1 - 1 / 30]
        if cruza and c.get("camada", "legenda") == "legenda":
            avisos.append(f"{t0:6.2f}s  atravessa a virada de {cruza[0]:.2f}s — "
                          f"nasce num tratamento e morre noutro")
        cheias = [w for w in c["words"] if w.get("enf") != "filler"]
        if len(cheias) > 4:
            erros.append(f"{t0:6.2f}s  {len(cheias)} palavras cheias (teto 4)")
        if sum(len(w["tx"]) + 1 for w in c["words"]) > 40:
            avisos.append(f"{t0:6.2f}s  card comprido, vai quebrar em 3 linhas")
        for w in c["words"]:
            if w["t0"] < t0 - 0.4 or w["t1"] > t1 + 0.4:
                erros.append(f"{t0:6.2f}s  '{w['tx']}' fora da janela do card")
            if w.get("enf") == "punch":
                punch.append((t0, w["tx"]))
            if w.get("fonte", c.get("fonte")) and w["tx"] != w["tx"].upper():
                pass
        if c.get("atras"):
            herois.append((c.get("_t_in", t0), c.get("_respiro", 5.0)))
            if c.get("layout") not in ("centro", "alto"):
                avisos.append(f"{t0:6.2f}s  herói fora do centro — a oclusão pede o meio")

    if len(punch) > 3:
        erros.append(f"        {len(punch)} punches (teto 3): "
                     f"{', '.join(t for _, t in punch)} — quatro punches é zero punch")
    # 5 s entre heróis atrás de você; a assinatura de um sistema de cinema é
    # pedida a cada 3-4 s (o `cada` dela), e o respiro dela é esse
    for (a, _), (b, resp) in zip(herois, herois[1:]):
        if b - a < resp:
            erros.append(f"{b:6.2f}s  herói a {b - a:.1f}s do anterior — falta respiro")

    fontes = {}
    for c in cards:
        fontes[c.get("fonte", FONTE_PADRAO)] = fontes.get(c.get("fonte", FONTE_PADRAO), 0) + 1
    if len(fontes) > 6:
        avisos.append(f"        {len(fontes)} fontes — se tudo muda, nada marca virada")

    # uma fonte por grupo do pack: duas da mesma pasta se parecem demais
    porgrupo: dict[str, set[str]] = {}
    for n in fontes:
        g = GRUPO_FONTE.get(n)
        if g:
            porgrupo.setdefault(g, set()).add(n)
    for g, ns in sorted(porgrupo.items()):
        if len(ns) > 1:
            erros.append(f"        {len(ns)} fontes do grupo {g} ({', '.join(sorted(ns))}) "
                         f"— máximo 1 por grupo; as da mesma pasta se parecem")

    # Buraco curto entre duas peças pisca. A de trás sai com fade, a da frente
    # entra com fade, e no vão as duas estão transparentes: aparece o vídeo cru
    # por três frames e lê como falha de edição. Ou as peças se encostam, ou o
    # vão é longo o bastante pra ser respiro.
    peças = sorted((b for b in (plano.get("brolls") or [])
                    if float(b.get("alt", 0)) >= 0.35),
                   key=lambda b: float(b["t0"]))
    for a, b in zip(peças, peças[1:]):
        vao = float(b["t0"]) - float(a["t1"])
        if 0 < vao < 0.5:
            erros.append(f'{a["t1"]:6.2f}s  buraco de {vao:.2f}s até a peça '
                         f'seguinte — encoste as duas ou abra pra 0.5s, senão '
                         f'a imagem pisca no vão')

    cobre = sum(c["t1"] - c["t0"] for c in cards)
    print(f"{len(cards)} cards | {cobre:.1f}s de legenda | {len(punch)} punch | "
          f"{len(herois)} herói | fontes: {', '.join(f'{k}×{v}' for k, v in fontes.items())}")
    for a in avisos:
        print(f"  aviso  {a}")
    for e in erros:
        print(f"  ERRO   {e}")
    if not erros and not avisos:
        print("  plano limpo")
    return 1 if erros else 0


def _auditar(pasta: Path) -> None:
    """Varre um pack de fontes: densidade de tinta, proporção e buraco de glifo.

    Rode isto ANTES de adicionar fonte ao registro. Densidade alta = pesada =
    boa pra legenda queimada; proporção alta = larga = come linha.
    """
    linhas = []
    for f in sorted(pasta.rglob("*")):
        if f.suffix.lower() not in (".otf", ".ttf") or "__MACOSX" in str(f):
            continue
        try:
            ft = ImageFont.truetype(str(f), 64)
            fam, est = ft.getname()
        except Exception:
            print(f"  ABRIU NÃO  {f.name}")
            continue
        FONTES[f"_aud_{f.stem}"] = (str(f), 0, None)
        falta = acentos_faltando(f"_aud_{f.stem}")
        im = Image.new("L", (900, 220), 0)
        ImageDraw.Draw(im).text((450, 110), "NENHUM", font=ft, fill=255, anchor="mm")
        a = np.array(im) > 128
        ys, xs = np.nonzero(a)
        if not len(xs):
            continue
        lg, al = int(xs.max() - xs.min()), int(ys.max() - ys.min())
        linhas.append((round(float(a.sum()) / max(1, lg * al), 3),
                       round(lg / max(1, al), 2), fam, est, falta, str(f)))
    linhas.sort(key=lambda r: -r[0])
    ruins = [r for r in linhas if r[4]]
    print(f"{len(linhas)} fontes | {len(ruins)} com acento faltando\n")
    print(f"{'dens':>5} {'l/a':>5}  {'família':32} {'estilo':18} falta")
    for d, ra, fam, est, falta, _ in linhas:
        print(f"{d:5.2f} {ra:5.2f}  {fam[:32]:32} {est[:18]:18} {falta[:14]}")


if __name__ == "__main__":
    if "--lint" in sys.argv:
        sys.exit(_lint(Path(sys.argv[sys.argv.index("--lint") + 1])))
    elif "--auditar" in sys.argv:
        _auditar(Path(sys.argv[sys.argv.index("--auditar") + 1]))
    elif "--presets" in sys.argv:
        for nome, p in PRESETS.items():
            print(f"{nome:14} {p['uso']}")
    else:
        main()
