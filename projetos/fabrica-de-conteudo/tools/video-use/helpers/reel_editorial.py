#!/usr/bin/env python3
"""O reel editorial: o molde do Nick Saraev (a peça e_editorial do tools/v2) montado de um plano.

    V=tools/video-use/.venv/bin/python
    $V tools/video-use/helpers/fabrica.py videos/topo/<slug>/reel.json --seco   # confere, não renderiza
    $V tools/video-use/helpers/fabrica.py videos/topo/<slug>/reel.json          # monta e entrega
    $V tools/video-use/helpers/reel_editorial.py voz <trabalho>        # a narração (cobra na ElevenLabs)
    $V tools/video-use/helpers/reel_editorial.py yt_voz <trabalho>     # a frase do YouTube (cobra)
    $V tools/video-use/helpers/reel_editorial.py converte videos/topo/<slug>/plano.json

Quem chama os passos é a fábrica, pelo estilo `reel-editorial`: ela confere o plano, põe nele o
que é do estilo e grava o resultado em <trabalho>/reel.json, que é o que cada passo daqui lê.
Nada aqui gasta dinheiro sozinho: a voz e a frase do YouTube só saem quando alguém pede à mão
(teto de gerações do estilo), e o avatar é gerado na HeyGen com o avatar/geracao.wav que o
passo `heygen` deixa pronto.

As regras do dono que o molde segura (tools/v2/LEIA-ME.md, a voz editorial):
  - cartão arredondado só com o rosto falando (a cabeça passa da borda); cena embaixo divide a
    tela reta, 40/60, costurada num degradê;
  - atrás do rosto, a placa do look (`imagem.fundo`) como é, nítida, na geometria do avatar (sem desfoque);
  - tela cheia sem rosto se enche: a captura vai quase na largura toda, e o `junta` MEDE no
    render a maior faixa vazia acima da legenda do IG (a trava `vazios`); o --seco avisa o que
    as caixas do plano já deixam prever;
  - o título do gancho está parado no quadro 0 (é a capa que o Instagram mostra);
  - letra nenhuma desce até a faixa da legenda do Instagram;
  - sem selo de IA na tela (o aviso vai na legenda do post e no rótulo da rede);
  - a chamada ("comenta / “PALAVRA”") só no fim;
  - cabeça e rosto do cartão saem do mesmo quadro: o webm entra na chave do cache do take.

O plano (reel.json, na pasta do vídeo; tempos em segundos do reel = tempos da voz):
  estilo      "reel-editorial"
  slug        o nome do final (videos/topo/<slug>.mp4)
  fonte       a voz nivelada ("voz.wav"): o relógio do reel. O transcript dela é
              transcripts/<nome>.json, que a fábrica faz quando falta
  narracao    o texto da voz, como se fala: sem sigla, sem marca de emoção. A marca de
              sotaque vem da marca (VOZ_SOTAQUE), o modelo do estilo (voz.sintese). Só faz falta enquanto a voz não existe
  palavra     a palavra da chamada ("VOZ"): a única caixa-alta que a narração pode ter
  trabalho    "_trabalho"
  dur         a duração do reel
  imagem      {fundo: a placa do seu look na HeyGen, da raiz da pasta}: o que vai atrás do rosto.
              O estilo não tem padrão, e o confere cobra
  avatar      {arquivo: o webm com alfa da HeyGen, mapa: avatar/geracao.json,
               cartao: {s, x, y}, cheio: {s, x, y}} — a escala e o lugar do avatar.
              alinha: true — o webm chegou pronto, sem o mapa do passo heygen: a fábrica acha cada
              pedaço da `fonte` no áudio dele (passo `alinha`), e o rosto segue a voz mesmo que ela
              tenha sido aparada depois. O `avatar` do trecho só marca que ali tem rosto
  base        o take, trecho a trecho, de 0 a dur, sem buraco:
                {de, ate, quadro: "cartao"|"cheio", avatar}  o rosto, sobre o `imagem.fundo`
                  + fundo: "xadrez"|"painel:claro"|"painel:tinta"|"@<imagem ou vídeo>"  o rosto recortado
                  sobre outra coisa (o "ele sai sem fundo" literal, o cenário gerado): a exceção ao `imagem.fundo`
                  + congela: o rosto para no quadro do `de` (a capa)
                {de, ate, painel: "claro"|"tinta"}            o painel parado (tela cheia)
                {de, ate, cena: <vídeo>, desde}               b-roll na tela toda
                {de, ate, divide: <vídeo>, painel, desde, foco}  painel 40 em cima, cena 60 embaixo
  junta       [["Eleven", "Labs", "ElevenLabs"], …]: palavras da fala que viram uma
  css         folha de estilo a mais, só deste vídeo (a do molde já vem)
  r           o `r` da e_editorial (cenas, vozes, nomes…), sem a fala: ela sai do transcript
  imagens     [{nome, arquivo, w, x, y, de, ate, sombra}] paradas por cima (o logo)
  pecas       [{nome, peca, em, de, ate, segura, caixa [x0,y0,x1,y1], max, move, onda, q}];
              `@caminho` é da pasta do vídeo, `@foco:nome` é a região medida na captura
  capturas    {logo: <url da página com o logo no cabeçalho>,
               prints: {nome: [url, âncora, altura, frase, [x0, x1]?]}} — páginas públicas,
              sem login; saem em _trabalho/cap/ quando faltam
  sons        [{tipo, t, dur?}] os efeitos à mão (som.py)
  trilha      {faixa, pedacos: [{de, ate, em, entra?, sai?}]} — sobrescreve o eixo do estilo.
              faixa "nenhuma": a música entra pelo app da rede, e o reel sai só com voz e efeitos
  capa        {foto, titulo, destaque, topo, logo, lados, cena, larg, ry, iy} (g_capa_nick): `foto` é
              a foto da pessoa, da pasta do vídeo; o resto no capa.py
  youtube     {fala, chamada: [l1, l2], tema}: a versão sem automação de DM. A frase nova
              mora em vozes/fim-yt.wav
  apara       true: a narração passa pelo apara_pausas (a receita da narração do dono) antes de
              virar a `fonte`; a voz como saiu da ElevenLabs fica em vozes/voz-cru.wav
  abre        segundos de silêncio antes da voz: o gancho que é só tela (o pedido se escrevendo)
  degraus     {ordem: [skills], trocas: [t ou "palavra"], ate, hud: [nomes], zoom}: o mesmo take
              renderizado com 0, 1… N skills ligadas (ritmo, legendas, composicao, movimento, estilo,
              na `ordem`), e o reel troca de degrau em cada `troca` (o número, ou o fim da palavra dita
              depois da troca anterior). Os degraus soltos, [0, ate], ficam em _trabalho/degraus/sN.mp4.
              As peças do `hud` (o placar, o balão) não entram nos degraus: vão por cima da montagem
  fechos      {nome: [de, ate, fica?]}: fechos ditos em sequência no mesmo áudio, depois do corpo. Cada
              um vira um final (final-<nome>.mp4): o corpo até o primeiro fecho e, emendado, só aquele,
              com o último quadro parado `fica` s (0,5). `[]` é o corpo sozinho (o vídeo em laço). O
              primeiro também é o final.mp4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

import ff
import transcript as tr
from capa import capa_nick
from mixa import lufs, resolver as faixa_de
from pre_voo import PAUSA_MAX

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
PY = sys.executable
V2DIR = AQUI.parents[1] / "v2"
V2 = V2DIR / "v2.py"
# a marca do aluno (estilo.py, desenho.tema = marca): mudar a folha dela refaz as peças
MARCA_CSS = RAIZ / "marca" / "tema.css"
FPS, W, H = ff.FPS, 1080, 1920
SR = int(ff.AUDIO_RATE)
CARTAO = (18, 1240, W - 18, H)   # o retângulo do cartão da e_editorial (--ed-cartao-y do editorial.css)
TINTA = "0x0B0D12"               # --ink do núcleo
# `trilha.faixa` que diz "sem música": quem posta põe a dela pelo app do Instagram, o caminho mais
# seguro no orgânico (decisão do dono, 03/10). O reel sai só com a voz e os efeitos, no nível
SEM_TRILHA = "nenhuma"

def css_fala(teto: int = 1450, zona: list | None = None, botoes: list | None = None) -> str:
    """A letra fora da faixa da legenda do Instagram (y > teto, o `legenda_ig` do estilo): a fala sobre o
    rosto sobe de 1560 pra teto-50 e a chamada pra teto-160; na tela cheia a fala desce de 1150 pra
    teto-50, embaixo da captura. Com zona segura (o anúncio), o bloco de duas linhas sobe também, que
    no 1450 ele passava do teto, e a letra centrada encolhe até caber entre a zona e a coluna de botões
    (o --ed-max da e_editorial: 840 px no anuncio-editorial, onde a de 960 entrava nos botões)."""
    css = (f".ed-v.sobre-rosto{{top:{teto - 50}px!important}}.ed-v.sobre-rosto:has(.ed-c1){{top:{teto - 160}px!important}}"
           f'.ed-v[style*="top: 1150px"]{{top:{teto - 50}px!important}}')
    if not zona:
        return css
    meia = min(W // 2 - zona[0], min(zona[2], (botoes or zona[2:])[0]) - W // 2)
    return css + f".ed-v.sobre-rosto:has(.ed-b2){{top:{teto - 110}px!important}}:root{{--ed-max:{2 * meia}px}}"


CSS = css_fala()


class Reel:
    """O plano resolvido que a fábrica deixa na pasta de trabalho."""

    def __init__(self, trabalho: Path):
        self.trab = Path(trabalho)
        self.p = json.loads((self.trab / "reel.json").read_text(encoding="utf-8"))
        self.p.setdefault("avatar", {})          # o Reel todo tela não tem rosto
        self.dir = Path(self.p["_dir"])
        self.est = self.p["_estilo"]
        self.cap = self.dir / "_trabalho" / "cap"

    def rel(self, c: str) -> Path:
        p = Path(c)
        return p if p.is_absolute() else self.dir / p

    @property
    def voz(self) -> Path:
        return self.rel(self.p["fonte"])

    def transcript(self, voz: Path) -> Path:
        return self.dir / "transcripts" / f"{voz.stem}.json"

    @property
    def fim_yt(self) -> Path:
        return self.dir / "vozes" / "fim-yt.wav"


def quadros(t: float) -> int:
    # a regra da e_editorial (a cena entra em t >= de): com round, o take trocava de trecho um quadro
    # antes das peças, e o v4 saiu com o cartão vazio em 15,967 e 22,233 s (01/10)
    return math.ceil(t * FPS - 1e-3)


def _json(x) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


# ───────────────────────── a conferência ─────────────────────────
def cobre(placa: tuple[int, int], g: dict, quadro: str) -> bool:
    """A placa do escritório, na escala e no lugar do avatar, cobre o que o quadro mostra?"""
    w = int(placa[0] * g["s"] / 2) * 2                  # a conta do scale do avatar
    h = round(placa[1] * w / placa[0] / 2) * 2
    x0, y0, x1, y1 = (0, 0, W, H) if quadro == "cheio" else CARTAO
    return g["x"] <= x0 and g["y"] <= y0 and g["x"] + w >= x1 and g["y"] + h >= y1


def confere(doc: dict) -> list[str]:
    """As regras do molde, conferidas no plano antes do primeiro comando. Devolve o que reprovou."""
    est, dur, erros = doc["_estilo"], float(doc.get("dur") or 0), []
    rel = lambda c: Path(c) if Path(c).is_absolute() else Path(doc["_dir"]) / c
    base = doc.get("base") or []
    if not dur or not base:
        return ["o plano não tem `dur` e `base`: sem eles não há reel"]

    t = 0.0
    for s in base:
        if abs(s["de"] - t) > 1e-3:
            erros.append(f"base: buraco ou sobreposição em {t:.2f}s (o trecho seguinte começa em {s['de']:.2f})")
        t = s["ate"]
        tipos = [k for k in ("avatar", "painel", "cena", "divide") if k in s]
        if s.get("quadro") == "cartao" and "avatar" not in s:
            erros.append(f"base {s['de']:.2f}: cartão arredondado é só pra rosto falando; "
                         f"cena embaixo divide a tela reta (`divide`)")
        elif not tipos:
            erros.append(f"base {s['de']:.2f}: o trecho não diz o que mostra (avatar, painel, cena ou divide)")
        for k in ("cena", "divide"):
            if k in s and not rel(s[k]).exists():
                erros.append(f"base {s['de']:.2f}: não existe {rel(s[k])}")
        f = s.get("fundo")
        if f and "avatar" not in s:
            erros.append(f"base {s['de']:.2f}: `fundo` por trecho é o que vai atrás do rosto, e o trecho não tem rosto")
        elif f and f not in ("xadrez", "painel:claro", "painel:tinta") \
                and not (rel(f.lstrip("@")).exists() or _a_cadeia_faz(doc, rel(f.lstrip("@")))):
            erros.append(f"base {s['de']:.2f}: o fundo `{f}` não é xadrez, painel:claro|tinta nem imagem que existe")
    if abs(t - dur) > 1e-3:
        erros.append(f"base: acaba em {t:.2f}s e o reel dura {dur:.2f}s")

    # o fim do rosto também é pausa no avatar/geracao.wav: a cauda muda passa do teto do pre_voo
    voz = rel(doc.get("fonte") or "voz.wav")
    if "avatar" in base[-1] and voz.exists():
        fim = _fala(voz)[1]
        if dur - fim > PAUSA_MAX + 1e-3:
            erros.append(f"a cauda do reel ({dur - fim:.2f}s do fim da voz, em {fim:.2f}s, ao `dur`) passa do teto "
                         f"de pausa do pre_voo ({PAUSA_MAX}s): o último trecho é rosto, e ela vira a maior pausa "
                         f"do avatar/geracao.wav. Encurte o `dur`")

    av = doc.get("avatar") or {}
    fundo = Path(est["fundo"] or "")
    # o Reel todo tela (sem trecho de rosto) não tem o que ir atrás do rosto
    rosto = any("avatar" in s for s in base)
    if rosto and not est["fundo"]:
        erros.append("o plano não diz o que vai atrás do rosto: aponte `imagem.fundo` no plano, a partir da raiz "
                     "da pasta. O fundo é a placa do seu look na HeyGen")
    elif rosto and not fundo.exists():
        erros.append(f"o fundo atrás do rosto não existe: {fundo}")
    elif rosto and av:
        from PIL import Image
        tam = Image.open(fundo).size
        for q in {s["quadro"] for s in base if "avatar" in s and not s.get("fundo")}:
            if q not in av:
                erros.append(f"avatar: falta a geometria do quadro `{q}`")
            elif not cobre(tam, av[q], q):
                erros.append(f"o escritório no {q} ({av[q]}) não cobre o quadro: ajuste x/y/s do avatar")

    # o cartão da peça só onde o take tem o rosto no cartão
    cartoes = [(s["de"], s["ate"]) for s in base if s.get("quadro") == "cartao"]
    for c in (doc.get("r") or {}).get("cenas", []):
        if c[2] == "split" and not any(a - 1e-3 <= c[0] and c[1] <= b + 1e-3 for a, b in cartoes):
            erros.append(f"r.cenas {c[0]:.2f}–{c[1]:.2f}: o cartão arredondado só vai sobre o rosto no cartão")

    pecas, imagens = doc.get("pecas") or [], doc.get("imagens") or []
    janela = lambda p: (p.get("de", p.get("em", 0)), p.get("ate", dur))
    zona, botoes = est.get("zona"), est.get("botoes")
    largura = zona[2] - zona[0] if zona else W     # com zona segura, a largura toda é a dela
    for s in base:
        if "painel" in s and "divide" not in s:
            cheias = [p for p in pecas if "caixa" in p and p["caixa"][2] - p["caixa"][0] >= 0.9 * largura
                      and janela(p)[0] < s["ate"] - 1e-3 and janela(p)[1] > s["de"] + 1e-3]
            if not cheias:
                erros.append(f"tela cheia {s['de']:.2f}–{s['ate']:.2f}: nenhuma peça na largura toda; "
                             f"sem o rosto, a captura enche a tela (ou vira tela dividida)")

    if not any(janela(p)[0] <= 1e-3 for p in pecas + imagens):
        erros.append("nada no quadro 0: o título do gancho entra parado no quadro 0 (é a capa do Instagram)")

    teto = est.get("legenda_ig")
    if teto:
        for p in pecas:
            y1 = p["caixa"][3] if "caixa" in p else (p.get("q") or {}).get("y")
            if isinstance(y1, (int, float)) and y1 > teto:
                erros.append(f"peça {p['nome']}: desce até y {y1}, e abaixo de {teto} é a legenda do Instagram")
        for p in imagens:
            if p.get("y", 0) > teto:
                erros.append(f"imagem {p['nome']}: y {p['y']} cai na legenda do Instagram (> {teto})")
    # a zona segura do anúncio: a caixa é onde a peça desenha, então é ela que tem que caber. Peça sem
    # caixa (carimbo, seta, placar) quem confere é a folha, que risca a zona por cima
    for p in pecas if zona else []:
        x0, y0, x1, y1 = p.get("caixa") or (zona[0], zona[1], zona[2], 0)
        if x0 < zona[0] or y0 < zona[1] or x1 > zona[2]:
            erros.append(f"peça {p['nome']}: a caixa {p['caixa']} sai da zona segura {zona}: a interface da rede cobre")
        elif botoes and x1 > botoes[0] and y1 > botoes[1]:
            erros.append(f"peça {p['nome']}: a caixa {p['caixa']} entra na coluna de botões (x > {botoes[0]}, y > {botoes[1]})")

    faixa = (doc.get("trilha") or {}).get("faixa")
    if not faixa:
        erros.append(f"o reel não tem trilha: `trilha.faixa` (ou \"{SEM_TRILHA}\", quando a música entra pelo app da rede)")
    elif faixa != SEM_TRILHA:
        try:
            faixa_de(faixa)
        except SystemExit as ex:              # o mixa sai com a mensagem de onde procurou
            erros.append(str(ex))

    banco = json.loads((V2DIR / "sfx" / "sfx.json").read_text(encoding="utf-8"))["sons"]
    for s in doc.get("sons") or []:
        if s["tipo"] not in banco:
            erros.append(f"som `{s['tipo']}` em {s['t']:.2f}s: o banco (tools/v2/sfx) não tem, e o som.py larga calado")

    if "selo" in doc or re.search(r"feito com ia", json.dumps(doc, ensure_ascii=False), re.I):
        erros.append("selo de IA na tela: o aviso vai na legenda do post e no rótulo da rede, não no vídeo")

    # com fechos, o fim de cada final é o fecho dele: a chamada mora dentro de um
    fe = {k: v for k, v in (doc.get("fechos") or {}).items() if v}    # `[]` é o final só com o corpo
    fins = [tuple(x[:2]) for x in fe.values()] or [(base[-1]["de"], dur)]
    for v in (doc.get("r") or {}).get("vozes", []):
        if "chamada" in v and not any(a - 1e-3 <= v["t"] and v["ate"] <= b + 1e-3 for a, b in fins):
            erros.append(f"a chamada em {v['t']:.2f}s: ela entra só no fim ({' ou '.join(f'{a:.2f}–{b:.2f}s' for a, b in fins)}); "
                         f"o começo é gancho visual")
    for nome, (a, b, *_) in fe.items():
        if not 0 < a < b <= dur + 1e-3:
            erros.append(f"fecho {nome}: [{a}, {b}] fora do reel (0–{dur:.2f}s)")
    trava = sorted(x[:2] for x in fe.values())
    for (a0, b0), (a1, _) in zip(trava, trava[1:]):
        if a1 < b0 - 1e-3:
            erros.append(f"fechos: {a0}–{b0} e o seguinte, de {a1}, se sobrepõem")

    dg = doc.get("degraus")
    if dg:
        ordem, trocas = dg.get("ordem") or [], dg.get("trocas") or []
        fora = [s for s in ordem if s not in SKILLS]
        if fora or len(set(ordem)) != len(ordem) or not ordem:
            erros.append(f"degraus.ordem {ordem}: as skills são {', '.join(SKILLS)}, cada uma uma vez")
        if len(trocas) != len(ordem):
            erros.append(f"degraus: {len(ordem)} skills e {len(trocas)} trocas; uma troca por skill")
        nomes = {p["nome"] for p in pecas}
        for h in dg.get("hud", []):
            if h not in nomes:
                erros.append(f"degraus.hud: a peça `{h}` não está nas `pecas`")
        # sem composição o rosto fica inteiro no trecho todo: ele tem que ter sido gerado ali
        ate = dg.get("ate")
        if isinstance(ate, (int, float)):
            sem = [s for s in base if s["de"] < ate - 1e-3 and "avatar" not in s]
            if sem:
                erros.append(f"degraus: até {ate}s o take é o rosto em todo degrau, e {sem[0]['de']:.2f}–"
                             f"{sem[0]['ate']:.2f}s não tem rosto (a HeyGen só gera onde a `base` tem avatar)")

    for p in pecas:
        for v in (p.get("q") or {}).values():
            if isinstance(v, str) and v.startswith("@") and not v.startswith("@foco:"):
                arq = rel(v[1:])
                if not arq.exists() and not _a_cadeia_faz(doc, arq):
                    erros.append(f"peça {p['nome']}: não existe {arq}")
    for p in imagens:
        if not rel(p["arquivo"]).exists() and not _a_cadeia_faz(doc, rel(p["arquivo"])):
            erros.append(f"imagem {p['nome']}: não existe {rel(p['arquivo'])}")
    # o título gigante mora na camada tras: sem o recorte ele cobre a pessoa, e o estilo tem de pôr coisa atrás
    if any(v.get("gigante") for v in (doc.get("r") or {}).get("vozes", [])):
        if not est.get("atras"):
            erros.append(f"voz gigante: o estilo '{est.get('nome')}' não põe nada atrás da pessoa (desenho.atras)")
        if not doc.get("recorte"):
            erros.append("voz gigante sem `recorte`: sem a pessoa recortada, o título fica por cima dela")
    for a in preve_vazios(doc):
        print(f"aviso: {a}")
    return erros


VAZIO_MAX = 300    # px: a maior faixa sem nada que uma tela cheia pode ter, acima da legenda do IG
VAZIO_TOL = 0.5    # s: quanto tempo ela pode passar disso (a entrada das peças)


def _maior_vao(cheia, k: int = 1) -> tuple[int, int]:
    """A maior sequência de linhas sem nada: (altura, y onde começa), em px de k em k."""
    melhor, ini, i0 = 0, 0, None
    for i, c in enumerate([*cheia, True]):
        if not c and i0 is None:
            i0 = i
        elif c and i0 is not None:
            if i - i0 > melhor:
                melhor, ini = i - i0, i0
            i0 = None
    return melhor * k, ini * k


def _paineis(base: list) -> list:
    """Os trechos de tela cheia sem rosto: painel sem cena embaixo."""
    return [s for s in base if "painel" in s and "divide" not in s]


def preve_vazios(doc: dict) -> list[str]:
    """O que o plano já deixa prever da trava do render: mesmo com cada peça enchendo a caixa
    inteira (o máximo que ela ocupa), sobra faixa vazia acima do teto? É aviso, não erro: peça
    sem caixa (sticker, mira) pode cair no vão, e quem decide é a medida no render."""
    teto = doc["_estilo"].get("legenda_ig") or H
    dur = float(doc["dur"])
    pecas = [p for p in doc.get("pecas") or [] if "caixa" in p]
    avisos = []
    for s in _paineis(doc.get("base") or []):
        ruins = []
        for t in np.arange(s["de"], s["ate"], 0.1):
            linhas = np.zeros(teto, bool)
            for p in pecas:
                if p.get("de", p.get("em", 0)) <= t < p.get("ate", dur):
                    linhas[max(0, p["caixa"][1]):max(0, min(teto, p["caixa"][3]))] = True
            vao, y = _maior_vao(linhas)
            if vao > VAZIO_MAX:
                ruins.append((round(float(t), 2), vao, y))
        if len(ruins) * 0.1 > VAZIO_TOL:
            t, vao, y = max(ruins, key=lambda x: x[1])
            avisos.append(f"tela cheia {s['de']:.2f}–{s['ate']:.2f}: mesmo com as caixas cheias, sobra faixa vazia "
                          f"de {vao}px (y {y}–{y + vao}, em {t:.2f}s); o render reprova acima de {VAZIO_MAX}px")
    return avisos


def capturas(doc: dict) -> list[Path]:
    """Os arquivos que o passo de captura faz, na _trabalho/cap da pasta do vídeo."""
    c = doc.get("capturas") or {}
    cap = Path(doc["_dir"]) / "_trabalho" / "cap"
    return ([cap / "logo_branco.png", cap / "logo_preto.png"] if c.get("logo") else []) + \
        [cap / f"{n}.png" for n in c.get("prints", {})]


def _a_cadeia_faz(doc: dict, arq: Path) -> bool:
    """O arquivo nasce num passo antes das peças: a captura, ou a capa (o r_capa a mostra no vídeo).
    Sem a capa aqui, o --seco numa pasta nova reprovava o plano que cita `@_trabalho/capa-nick.jpg`."""
    capa = Path(doc["_dir"]) / (doc.get("trabalho") or "_trabalho") / "capa-nick.jpg"
    return arq in capturas(doc) or (bool(doc.get("capa")) and arq == capa)


# ───────────────────────── captura ─────────────────────────
_JS_FRASE = """([ancora, frase]) => {
  const acha = t => { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) if (n.textContent.includes(t) && n.parentElement.offsetParent !== null) return n; return null; };
  const a = acha(ancora), f = acha(frase);
  if (!a || !f) return null;
  const r = document.createRange(), i = f.textContent.indexOf(frase);
  r.setStart(f, i); r.setEnd(f, i + frase.length);
  const rs = [...r.getClientRects()], ra = a.parentElement.getBoundingClientRect();
  return {topo: ra.top + scrollY, x0: Math.min(...rs.map(q => q.left)), x1: Math.max(...rs.map(q => q.right)),
          y0: Math.min(...rs.map(q => q.top)) + scrollY, y1: Math.max(...rs.map(q => q.bottom)) + scrollY};
}"""

_JS_LIMPA = """() => { for (const s of ['#CybotCookiebotDialog', '[class*=VoiceChat]', '[class*=voice-chat]', '[aria-label*="Voice chat"]'])
  document.querySelectorAll(s).forEach(e => e.remove());
  [...document.querySelectorAll('button, a, div')].filter(e => e.innerText && e.innerText.trim() === 'Voice chat')
    .forEach(e => (e.closest('[class*=fixed]') || e).remove()); }"""

# a borda de baixo do que fica grudado no topo da tela (o cabeçalho do site), subindo do elemento em (500, 40)
_JS_CABECALHO = """() => { let e = document.elementFromPoint(500, 40), b = 0;
  for (; e && e !== document.body; e = e.parentElement)
    if (/fixed|sticky/.test(getComputedStyle(e).position)) b = Math.max(b, e.getBoundingClientRect().bottom);
  return b; }"""


# o link pra casa do site (mesmo host, caminho "/") com o logo dentro: SVG, ou a imagem dele (a
# heygen.com põe um PNG pelo next/image, e aí vale o arquivo original do `url=`)
_JS_LOGO = """() => { const casa = h => h.replace(/^www\\./, '');
  const a = [...document.querySelectorAll('a[href]')].find(a => { const u = new URL(a.href, location.href);
    return casa(u.host) === casa(location.host) && u.pathname === '/' && a.querySelector('svg, img'); });
  if (!a) return null;
  const s = a.querySelector('svg'); if (s) return {svg: s.outerHTML};
  const u = new URL(a.querySelector('img').currentSrc || a.querySelector('img').src, location.href);
  return {img: u.pathname.startsWith('/_next/image') && u.searchParams.get('url')
    ? new URL(u.searchParams.get('url'), location.href).href : u.href}; }"""


def _rola(pg, y: float) -> float:
    """Rola até y e espera a página parar. Rolagem animada (o `scroll-behavior: smooth` da
    heygen.com, ou script que anima o scrollTo) ainda andava quando o print saía, 600 ms depois."""
    pg.evaluate(f"window.scrollTo(0, {y})")
    ult, iguais = None, 0
    for _ in range(80):
        pg.wait_for_timeout(100)
        agora = pg.evaluate("() => scrollY")
        iguais, ult = (iguais + 1 if agora == ult else 0), agora
        if iguais >= 3:
            break
    return ult


def _pagina(pg, url: str) -> None:
    """Abre e passa pela página inteira. O `networkidle` nunca chega em página com vídeo e
    analytics (a heygen.com estourava os 60 s): vale o `load`, e a rolagem até o fim carrega o
    que é preguiçoso antes de medir."""
    pg.goto(url, wait_until="load", timeout=60000)
    pg.evaluate("() => document.head.insertAdjacentHTML('beforeend', '<style>html,body{scroll-behavior:auto!important}</style>')")
    y = 0
    while y < pg.evaluate("() => document.documentElement.scrollHeight"):
        pg.evaluate(f"window.scrollTo(0, {y})")
        pg.wait_for_timeout(120)
        y += 900
    _rola(pg, 0)
    pg.wait_for_timeout(1000)
    pg.evaluate(_JS_LIMPA)


def _print(pg, cap: Path, nome: str, ancora: str, alt: int, frase: str, faixa: list | None = None) -> list:
    """O print de um recurso na página aberta, e a região da frase em fração do recorte. Com
    `faixa`, é print de tela cheia: sem as margens da página e sem o cabeçalho do site (ele
    some e volta com a rolagem e cobria a primeira linha)."""
    m = pg.evaluate(_JS_FRASE, [ancora, frase])
    assert m, f"{nome}: não achei “{frase}” em {pg.url}"
    cab = 0 if faixa else pg.evaluate(_JS_CABECALHO)
    alvo = lambda m: max(0, m["topo"] - cab - (80 if faixa else 40))
    for _ in range(3):              # rolar carrega imagem acima da âncora e ela desce: mede de novo
        y0 = _rola(pg, alvo(m))
        m = pg.evaluate(_JS_FRASE, [ancora, frase])
        if abs(y0 - alvo(m)) <= 2:
            break
    pg.evaluate(_JS_LIMPA)
    if faixa:
        # marca e esconde com !important: o site reescreve o estilo do cabeçalho a cada rolagem
        pg.evaluate("() => { document.querySelectorAll('*').forEach(e => { if (/fixed|sticky/.test(getComputedStyle(e).position)) e.dataset.fora = 1; });"
                    " document.head.insertAdjacentHTML('beforeend', '<style>[data-fora]{visibility:hidden!important}</style>'); }")
        pg.wait_for_timeout(300)
    faixa = faixa or (0, 1000)
    y0 = pg.evaluate("() => scrollY")
    x0, larg = faixa[0], faixa[1] - faixa[0]
    pg.screenshot(path=str(cap / f"{nome}.png"), clip={"x": x0, "y": 0, "width": larg, "height": alt + cab})
    alt += cab
    foco = [round(max(0, m["x0"] - x0 - 8) / larg, 4), round((m["y0"] - y0 - 6) / alt, 4),
            round((m["x1"] - m["x0"] + 16) / larg, 4), round((m["y1"] - m["y0"] + 12) / alt, 4)]
    print(f"{nome}: {frase!r} → foco {foco}")
    return foco


def _logo(nav, pg, cap: Path) -> None:
    """O logo do link pra casa do site, na página aberta, em preto e em branco com fundo
    transparente (logo_preto.png, logo_branco.png)."""
    achado = pg.evaluate(_JS_LOGO)
    assert achado, f"não achei o logo no link pra casa de {pg.url}"
    if "img" in achado:
        # a imagem vira só o desenho: o alfa dela (ou o escuro, se ela não tem alfa) pintado de uma cor
        import io
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(pg.request.get(achado["img"]).body())).convert("RGBA")
        a = im.getchannel("A")
        if a.getextrema()[0] == 255:
            a = ImageOps.invert(im.convert("L"))
        a = a.crop(a.getbbox())
        a = a.resize((1200, round(a.height * 1200 / a.width)), Image.LANCZOS)
        for cor, nome in (((0, 0, 0), "logo_preto"), ((255, 255, 255), "logo_branco")):
            out = Image.new("RGBA", a.size, cor + (0,))
            out.putalpha(a)
            out.save(cap / f"{nome}.png")
        return
    svg = achado["svg"]
    (cap / "logo.svg").write_text(svg, encoding="utf-8")
    for cor, nome in (("#000", "logo_preto"), ("#fff", "logo_branco")):
        p2 = nav.new_page(viewport={"width": 1400, "height": 300}, device_scale_factor=1)
        p2.set_content(f"<html><body style='margin:0;background:transparent;color:{cor}'>"
                       f"<div id=l style='display:inline-block;width:1200px;line-height:0'>{svg}</div></body></html>")
        # o SVG do site mede a altura pelo CSS: aqui ela sai do viewBox
        p2.evaluate(f"() => {{ const s = document.querySelector('svg'), v = s.viewBox.baseVal; s.removeAttribute('style');"
                    f" s.setAttribute('width', '1200'); s.setAttribute('height', String(Math.round(1200 * v.height / v.width)));"
                    f" s.querySelectorAll('*').forEach(e => {{ if (e.getAttribute('fill') !== 'none') e.setAttribute('fill', '{cor}'); }}); }}")
        p2.locator("#l").screenshot(path=str(cap / f"{nome}.png"), omit_background=True)
        p2.close()


def captura(r: Reel) -> None:
    """Páginas públicas, num Chromium limpo (sem conta, sem cookie do dono). Só o que falta:
    a captura que já existe fica (pra refazer, apague o arquivo). A região de cada frase vai
    pra _trabalho/cap/focos.json, somada à que já estava lá."""
    from playwright.sync_api import sync_playwright
    c = r.p["capturas"]
    r.cap.mkdir(parents=True, exist_ok=True)
    arq = r.cap / "focos.json"
    focos = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        pg = nav.new_page(viewport={"width": 1000, "height": 1100}, device_scale_factor=2)
        if c.get("logo") and not all(p.exists() for p in capturas(r.p)[:2]):
            _pagina(pg, c["logo"])
            _logo(nav, pg, r.cap)
        for nome, (url, *resto) in c.get("prints", {}).items():
            if (r.cap / f"{nome}.png").exists():
                continue
            if pg.url != url:
                _pagina(pg, url)
            focos[nome] = _print(pg, r.cap, nome, *resto)
        nav.close()
    arq.write_text(json.dumps(focos, indent=1), encoding="utf-8")


# ───────────────────────── a voz ─────────────────────────
def _amostras(p: Path, sr: int = SR) -> np.ndarray:
    res = ff.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                 capture=True, binario=True, quiet=True)
    return np.frombuffer(res.stdout, np.float32)


def _envelope(x: np.ndarray, passo: float = 0.01) -> np.ndarray:
    h = int(SR * passo)
    n = len(x) // h
    return 20 * np.log10(np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)


def _fala(p: Path, limiar: float = -45) -> tuple[float, float]:
    """Onde a fala começa e acaba no arquivo, pelo envelope de 10 ms."""
    on = np.flatnonzero(_envelope(_amostras(p)) > limiar)
    return on[0] / 100, (on[-1] + 1) / 100


def _nivela(src: Path, out: Path, alvo: float) -> Path:
    """Mono 48 kHz, cortado na fala (0,05 s antes, 0,2 s depois), em `alvo` LUFS."""
    a, b = _fala(src)
    de, ate = max(0.0, a - 0.05), b + 0.2
    tmp = out.with_suffix(".tmp.wav")
    ff.run(["ffmpeg", "-y", "-i", str(src), "-af", f"atrim={de:.3f}:{ate:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.02,afade=t=out:st={ate - de - 0.03:.3f}:d=0.03", "-ac", "1", "-ar", str(SR), str(tmp)], quiet=True)
    ff.run(["ffmpeg", "-y", "-i", str(tmp), "-af", f"volume={alvo - lufs(tmp):.2f}dB", "-c:a", "pcm_s16le", str(out)], quiet=True)
    tmp.unlink()
    return out


def sotaque_de(s: dict, env: dict) -> str:
    """A marca de sotaque: a do plano/estilo, senão a da marca de quem grava. Sem nenhuma, vazia."""
    return s["sotaque"] or env.get("VOZ_SOTAQUE", "").strip()


def _gera(r: Reel, texto: str, log: Path, mp3: str) -> Path:
    """Uma geração na ElevenLabs, com a marca de sotaque do estilo na frente e o teto de tentativas."""
    try:
        from narra import voz as tts   # a chamada da ElevenLabs, que vem no módulo Clone de IA
    except ImportError:
        sys.exit("a narração pela voz clonada vem no módulo Clone de IA (narra.py), que esta pasta não tem")
    s = r.est["sintese"]
    feitas = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    if len(feitas) >= s["tentativas"]:
        sys.exit(f"já foram {len(feitas)} gerações em {log.name}: o teto do estilo é {s['tentativas']}")
    env = dict(l.strip().split("=", 1) for l in open(RAIZ / ".env.local", encoding="utf-8") if "=" in l and not l.startswith("#"))
    texto = f"{sotaque_de(s, env)} {texto}".strip()
    ajuste = {"stability": s["stability"], "similarity_boost": s["similarity_boost"]}
    out = log.parent / f"{mp3}-{len(feitas) + 1}.mp3"
    # cada _gera é uma tentativa nova: o take entra na chave do pago, senão a 2ª devolvia a 1ª do cache
    tts(texto, env["VOZ_ID"], ajuste, out, modelo=s["modelo"], take=len(feitas) + 1)
    log.write_text(json.dumps(feitas + [{"arquivo": out.name, "texto": texto, "modelo": s["modelo"], "ajuste": ajuste}],
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _ouve(r: Reel, voz: Path) -> str:
    """Transcreve no large-v3 e devolve o que a voz disse."""
    subprocess.run([PY, str(AQUI / "transcribe.py"), str(voz), "--model", "large-v3", "--language", "pt",
                    "--edit-dir", str(r.dir)], check=True)
    return " ".join(w["text"] for w in _palavras(r.transcript(voz)))


def _difere(ouvido: str, texto: str) -> list[str]:
    """Onde o que a voz disse sai do texto, palavra a palavra ("texto → ouvido"). A repetição
    ("o link, o link tá na descrição") passava: o ouvido.py deu 0 pontos pra ela."""
    import difflib
    a, b = re.findall(r"\w+", texto.lower()), re.findall(r"\w+", ouvido.lower())
    return [f"{' '.join(a[i:j]) or '∅'} → {' '.join(b[k:l]) or '∅'}"
            for op, i, j, k, l in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != "equal"]


def voz(r: Reel) -> None:
    """A narração (cobra na ElevenLabs): gera, nivela na `fonte`, transcreve e o ouvido.py confere."""
    texto = r.p["narracao"]
    if re.search(r"\[[^\]]*\]", texto):
        sys.exit("marca entre colchetes na narração: a de sotaque vem da marca (VOZ_SOTAQUE), e marca de emoção não entra")
    if re.search(r"\b[A-Z]{2,}\b", texto.replace(r.p.get("palavra", "\0"), "")):
        sys.exit("sigla na narração: escreva como se fala")
    (r.dir / "vozes").mkdir(exist_ok=True)
    mp3 = _gera(r, texto, r.dir / "vozes" / "tentativas.json", "narracao")
    _nivela(mp3, r.voz, r.est["alvo"])
    if r.p.get("apara"):
        # o "tira as pausas" acontece de verdade: a mesma receita da narração do dono (o clean_edl tight)
        cru = r.dir / "vozes" / "voz-cru.wav"
        r.voz.replace(cru)
        _ouve(r, cru)
        subprocess.run([PY, str(AQUI / "apara_pausas.py"), str(cru), "--transcript", str(r.transcript(cru)),
                        "-o", str(r.voz)], check=True)
    if r.p.get("abre"):
        # o gancho que é só tela: a voz entra depois de `abre` s de silêncio, e o relógio do reel é ela
        cala = r.voz.with_suffix(".abre.wav")
        ff.run(["ffmpeg", "-y", "-i", str(r.voz), "-af", f"adelay={round(r.p['abre'] * 1000)}:all=1",
                "-c:a", "pcm_s16le", str(cala)], quiet=True)
        cala.replace(r.voz)
    ouvido = _ouve(r, r.voz)
    print(f"{r.voz.name}: {ff.dur(r.voz):.2f}s  {lufs(r.voz):.1f} LUFS  ouvido: {ouvido!r}")
    # na narração longa o Whisper escreve número e marca do jeito dele: aqui é aviso, pra ouvir
    difs = _difere(ouvido, texto)
    if difs:
        print("  aviso: a voz saiu do texto em  " + "  ·  ".join(difs))
    subprocess.run([PY, str(AQUI / "ouvido.py"), "confere", str(r.voz), "--json", str(r.dir / "ouvido.json")])


def yt_voz(r: Reel) -> None:
    """A última frase da versão do YouTube (cobra), no nível da frase que ela substitui. A que
    não diz a `fala` (leu a marca, repetiu palavra) sai do caminho: com o fim-yt.wav no lugar a
    fábrica montaria com ela."""
    fala_ = r.p["youtube"]["fala"]
    mp3 = _gera(r, fala_, r.dir / "vozes" / "tentativas-yt.json", "fim-yt")
    _nivela(mp3, r.fim_yt, lufs(r.voz, f"gte(t,{_ultima_frase(r)[0] - 0.05:.3f})"))
    ouvido = _ouve(r, r.fim_yt)
    print(f"{r.fim_yt.name}: {ff.dur(r.fim_yt):.2f}s  ouvido: {ouvido!r}")
    # a marca é instrução, não fala: lida, a frase sai com inglês e o dobro do tamanho
    difs = _difere(ouvido, fala_)
    erro = ("a voz leu a marca de sotaque" if re.search(r"accent|brazil|janeiro|carioca|portugu", ouvido, re.I)
            else "a voz não disse a fala: " + "  ·  ".join(difs) if difs else "")
    if erro:
        fora = r.fim_yt.with_name(f"{Path(mp3).stem}-recusada.wav")
        r.fim_yt.replace(fora)
        sys.exit(f"{erro}. Ficou em vozes/{fora.name}: ouça, e se ela estiver certa, volte o nome pra {r.fim_yt.name}")
    subprocess.run([PY, str(AQUI / "ouvido.py"), "confere", str(r.fim_yt)])


# ───────────────────────── a fala na tela ─────────────────────────
def _palavras(p: Path) -> list[dict]:
    return tr.palavras(p)


def _segmentos(p: Path, limiar: float = -42, vao: float = 0.15) -> list[list[float]]:
    """Os trechos com voz, separados por silêncio de pelo menos `vao`."""
    on = _envelope(_amostras(p)) > limiar
    k, n, segs, i = int(vao * 100), len(on), [], 0
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and (on[j] or on[j:j + k].any()):
            j += 1
        segs.append([i / 100, j / 100])
        i = j
    return segs


def fala(r: Reel) -> list:
    """A palavra a palavra, no tempo do envelope e não no do Whisper: cada frase (até . ou ?)
    vai pro trecho de voz dela, com a proporção interna do Whisper."""
    ws = _palavras(r.transcript(r.voz))
    frases, cur = [], []
    for w in ws:
        cur.append(w)
        if re.search(r"[.?!]$", w["text"].strip()):
            frases.append(cur)
            cur = []
    frases += [cur] if cur else []
    segs = _segmentos(r.voz)
    saida = []
    for f in frases:
        # os trechos de voz que a frase toca, pelo tempo e não pela ordem: casar a n-ésima frase com o
        # n-ésimo trecho quebrava quando o Whisper pontua com vírgula (o bruto-editado, 01/10: uma
        # frase de 11 s espremida no primeiro trecho de 1,4 s). A borda só vai pra borda do trecho
        # que começa (ou acaba) perto dela; trecho dividido com a frase vizinha fica no tempo do Whisper
        a, b = f[0]["start"], f[-1]["end"]
        partes = [s for s in segs if min(s[1], b) - max(s[0], a) > 0.15]   # o rabo do trecho vizinho não conta
        A = partes[0][0] if partes and partes[0][0] > a - 0.6 else a
        B = partes[-1][1] if partes and partes[-1][1] < b + 0.6 else b
        m = lambda t: A + (t - a) * (B - A) / max(b - a, 1e-3)
        for w in f:
            t0, t1 = m(w["start"]), m(w["end"])
            for p, q in zip(partes, partes[1:]):  # caiu no silêncio de dentro da frase: vai pra borda da voz
                if p[1] <= t0 < q[0]:
                    t0 = q[0]
                if p[1] < t1 <= q[0]:
                    t1 = p[1]
            tx = w["text"].lower() if re.fullmatch(r"[A-ZÉÈ][.,?]?", w["text"]) else w["text"]   # "A", "É": a peça só baixa palavra de 2+ letras
            saida.append([tx, round(t0, 2), round(max(t1, t0 + 0.05), 2)])
    for par in r.p.get("junta", []):             # ["Eleven", "Labs", "ElevenLabs"]: n palavras viram uma
        *velhas, nova = par
        k, i = len(velhas), 0
        while i <= len(saida) - k:
            if [s[0] for s in saida[i:i + k]] == velhas:
                saida[i:i + k] = [[nova, saida[i][1], saida[i + k - 1][2]]]
            i += 1
    return saida


# ───────────────────────── take ─────────────────────────
def _codifica(entradas: list, filtro: str, n: int, out: Path) -> Path:
    # todo trecho sai com as mesmas propriedades de quadro (faixa, SAR, cor): o concat por cópia junta
    # trecho de rosto e de cena, e propriedade diferente faz o compor reconfigurar o grafo no meio.
    # Com a faixa, o setenta-cenas perdeu 136 quadros; com SAR e cor, a legenda do site-vira-video
    # ficou 1,5 s adiantada (o setpts=PTS-STARTPTS da letra recomeça na reconfiguração)
    filtro += (f";[v]scale=out_range=tv,setsar=1,setparams=range=tv:color_primaries=bt709:color_trc=bt709:"
               f"colorspace=bt709,format={ff.PIX_FMT}[vo]")
    ff.run(["ffmpeg", "-y", *entradas, "-filter_complex", filtro, "-map", "[vo]", "-frames:v", str(n), "-an",
            *ff.args_video("final"), str(out)], quiet=True)
    return out


def _laco(desde: float, fim: float, n: int, geo: str, congela: bool = False, vai_volta: bool = False,
          taxa: str = f"fps={FPS}") -> str:
    """Toca [desde, fim] e dá a volta até completar n quadros; congelada, repete o 1º;
    em vai-e-volta, toca de trás pra frente em vez de saltar pro começo. `taxa` é a ff.taxa da cena."""
    k = 1 if congela else max(1, quadros(fim - desde))
    ida = f"{taxa},{geo},trim=end_frame={k}"
    if vai_volta:
        ida, k = f"{ida},split[ida][v0];[v0]reverse[volta];[ida][volta]concat=n=2:v=1:a=0", 2 * k
    return f"{ida},loop=loop=-1:size={k},trim=end_frame={n},setpts=N/{FPS}/TB"


def _tema(r: Reel) -> list[str]:
    """O `--tema` das peças, quando o estilo pede um que não é o claro (a marca do aluno)."""
    # quem monta o Reel por fora (videos/fabrica/monta.py) não passa `est`: aí é o claro
    est = getattr(r, "est", None) or {}
    return ["--tema", est["tema"]] if est.get("tema", "claro") != "claro" else []


def painel(r: Reel, tema: str) -> Path:
    """O chão do painel da e_editorial, parado: nos trechos de tela o take é ele."""
    out = r.trab / f"painel_{tema}.png"
    if not out.exists():
        mov = r.trab / "painel.mov"
        subprocess.run([PY, str(V2), "render", "e_editorial", 'r={"dur":2,"cenas":[[0,1,"tela","claro"],[1,2,"tela","tinta"]]}',
                        "--camada", "tras", *_tema(r), "--out", str(mov)], check=True)
        for t, nome in ((0.5, "claro"), (1.5, "tinta")):
            ff.run(["ffmpeg", "-y", "-ss", f"{t}", "-i", str(mov), "-frames:v", "1", str(r.trab / f"painel_{nome}.png")], quiet=True)
    return out


def degrade(r: Reel, w: int, h: int) -> Path:
    """O alfa da cena na costura: sobe de 0 a 1 no degradê do estilo (smoothstep), cheio no resto."""
    d = r.est["costura"][1]
    out = r.trab / f"degrade_{w}x{h}_{d}.png"
    if not out.exists():
        from PIL import Image
        t = np.clip(np.arange(h) / d, 0, 1)
        Image.fromarray(np.repeat((255 * t * t * (3 - 2 * t)).astype(np.uint8)[:, None], w, 1), "L").save(out)
    return out


def fundo(r: Reel, quadro: str) -> Path:
    """O escritório dele atrás do avatar, nítido, com a MESMA escala e o MESMO deslocamento do avatar
    daquele quadro. A placa, o webm e o vídeo da HeyGen com fundo saem do mesmo enquadramento
    (conferido em 30/09: erro de 1 nível de cinza em 0,0), então o microfone e a cadeira caem no
    lugar. Regra do dono em 30/09: o escritório como é, com o Zelda, sem desfoque."""
    from PIL import Image
    g = r.p["avatar"][quadro]
    src = Path(r.est["fundo"])
    chave = hashlib.md5(json.dumps([str(src), src.stat().st_mtime, src.stat().st_size, g]).encode()).hexdigest()[:10]
    out = r.trab / f"fundo_{quadro}_{chave}.png"
    if out.exists():
        return out
    im = Image.open(src).convert("RGB")
    if not cobre(im.size, g, quadro):
        raise ValueError(f"a placa do {quadro} ({g}) não cobre o quadro: ajuste x/y/s do avatar")
    w = int(im.width * g["s"] / 2) * 2
    im = im.resize((w, round(im.height * w / im.width / 2) * 2), Image.LANCZOS)
    tela = Image.new("RGB", (W, H))
    tela.paste(im, (g["x"], g["y"]))
    tela.save(out)
    return out


VIDEOS = (".mp4", ".mov", ".webm")


def chao(r: Reel, s: dict) -> Path:
    """O que vai atrás do avatar no trecho: o escritório, ou o `fundo` do trecho — o xadrez de
    transparência (o "sai sem fundo" literal), o painel, uma imagem esticada até cobrir a tela, ou um
    vídeo (o cenário gerado atrás do rosto), que vai em laço e cobre a tela do mesmo jeito."""
    f = s.get("fundo")
    if not f:
        return fundo(r, s["quadro"])
    if f.startswith("painel:"):
        return painel(r, f[7:])
    from PIL import Image, ImageOps
    if f == "xadrez":
        out = r.trab / "fundo_xadrez.png"
        if not out.exists():
            y, x = np.mgrid[0:H, 0:W] // 60
            Image.fromarray(np.where((x + y) % 2, 204, 255).astype(np.uint8), "L").convert("RGB").save(out)
        return out
    src = r.rel(f.lstrip("@"))
    if src.suffix.lower() in VIDEOS:                # o cenário gerado: o vídeo mesmo, que o trecho põe em laço
        return src
    out = r.trab / f"fundo_{src.stem}_{hashlib.md5(json.dumps(_estado(src)).encode()).hexdigest()[:10]}.png"
    if not out.exists():
        ImageOps.fit(Image.open(src).convert("RGB"), (W, H), Image.LANCZOS).save(out)
    return out


def _no_webm(r: Reel, s: dict) -> float:
    """O segundo do webm no 1º quadro do trecho: com `mapa` (o avatar/geracao.json do passo heygen),
    sai dele; sem mapa, é o `avatar` do trecho. O quadro começa em quadros(de)/FPS, depois do `de`
    quando ele cai fora da grade: buscar no `de` atrasava o rosto 1 quadro (o v4 em 24,08 s, 01/10)."""
    av = r.p["avatar"]
    atraso = quadros(s["de"]) / FPS - s["de"]
    if "mapa" not in av:
        return s["avatar"] + atraso
    trechos = json.loads(r.rel(av["mapa"]).read_text(encoding="utf-8"))["trechos"]
    for m in trechos:
        if m["fonte"][0] - 1e-3 <= s["de"] < m["fonte"][1]:
            return m["gerado"][0] + s["de"] - m["fonte"][0] + atraso
    # no buraco entre dois trechos (a voz que a HeyGen não recebeu, que o `congela` cobria e o degrau sem
    # capa descobre), o webm segue de onde o anterior parou. Depois do último, não tem rosto: recusa
    antes = [m for m in trechos if m["fonte"][1] <= s["de"] + 1e-3]
    if antes and any(m["fonte"][0] > s["de"] for m in trechos):
        m = max(antes, key=lambda m: m["fonte"][1])
        return m["gerado"][1] + s["de"] - m["fonte"][1] + atraso
    raise ValueError(f"o trecho {s} não está no mapa: refaça o passo heygen e gere o avatar de novo")


def _avatar(r: Reel, s: dict, k: int = 0) -> tuple[list, str, dict]:
    """A entrada do webm (o decodificador VP9 é o que lê o alfa), a cadeia que põe o quadro
    dele na escala do `quadro`, e a geometria. `k` faz os rótulos da cadeia únicos no grafo."""
    av = r.p["avatar"]
    g = av[s["quadro"]]
    entrada = ["-c:v", "libvpx-vp9", "-ss", f"{_no_webm(r, s):.3f}", "-i", str(r.rel(av["arquivo"]))]
    # start_time=0: o -ss fora da grade de 25 fps do webm dá o 1º quadro em pts 0,02, o fps o joga pro
    # quadro 1 e o quadro 0 do trecho sai só com a placa (o v4 em 3,3 e 6,067 s, 01/10).
    # A HeyGen entrega a 25 (travado por ela): aí a taxa mistura em vez de copiar (ff.taxa), e o
    # setpts faz o papel do start_time
    fonte = ff.probe(r.rel(av["arquivo"])).fps
    taxa = (f"fps={FPS}:start_time=0" if fonte == FPS
            else "setpts=PTS-STARTPTS," + ff.taxa(fonte, FPS, alfa=f"av{k}"))
    return entrada, f"{taxa},format=rgba,scale=trunc(iw*{g['s']}/2)*2:-2", g


def _estado(p: Path) -> list:
    return [str(p), p.stat().st_mtime, p.stat().st_size]


def trecho(r: Reel, s: dict, i: int) -> Path:
    n = quadros(s["ate"]) - quadros(s["de"])
    out = r.trab / "take" / f"{i:02d}.mp4"
    if "avatar" in s:
        img = chao(r, s)
        entrada, cadeia, g = _avatar(r, s)
        # o webm, a entrada (o -ss) e a cadeia dele entram na chave: em 30/09 o rosto.webm foi trocado
        # depois do take, e o rosto no cartão ficou do webm velho enquanto a cabeça (a pessoa) vinha do
        # novo; em 01/10 o conserto do _no_webm e do start_time não refazia o trecho que já existia
        fonte = [*_estado(r.rel(r.p["avatar"]["arquivo"])), entrada, cadeia,
                 *(_estado(img) if img.suffix.lower() in VIDEOS else [])]
    else:
        img = painel(r, s.get("painel", "tinta"))
        fonte = _estado(r.rel(s.get("cena") or s["divide"])) if ("cena" in s or "divide" in s) else None
    # o n também: com a mesma chave, a grade de quadros mudada devolvia o trecho 1 quadro mais curto.
    # "mistura": a cena a 24 passou a mudar de taxa por mistura (03/10) sem o pedido mudar
    chave = json.dumps([s, n, r.p["avatar"].get(s.get("quadro")), str(img), fonte, r.est["costura"], "mistura"],
                       sort_keys=True)
    marca = out.with_suffix(".json")
    if out.exists() and marca.exists() and marca.read_text(encoding="utf-8") == chave:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    base = ["-loop", "1", "-framerate", str(FPS), "-i", str(img)]
    if "avatar" in s:
        chao_ = f"[0:v]format={ff.PIX_FMT}[p]"
        if img.suffix.lower() in VIDEOS:            # o cenário em laço, cobrindo a tela
            base = ["-stream_loop", "-1", "-ss", f"{s.get('desde', 0)}", "-i", str(img)]
            chao_ = (f"[0:v]{ff.taxa(ff.probe(img).fps)},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                     f"format={ff.PIX_FMT}[p]")
        if s.get("congela"):                        # a capa: o quadro inteiro para no `de` (rosto e cenário)
            para = f",trim=end_frame=1,loop=loop=-1:size=1,setpts=N/{FPS}/TB"
            cadeia += para
            chao_ = chao_.replace("[p]", f"{para}[p]")
        _codifica([*base, *entrada], f"{chao_};[1:v]{cadeia}[a];[p][a]overlay={g['x']}:{g['y']}[v]", n, out)
    elif "cena" in s or "divide" in s:
        arq = r.rel(s.get("cena") or s["divide"])
        entradas = ["-ss", f"{s.get('desde', 0)}", "-i", str(arq)]
        taxa = ff.taxa(ff.probe(arq).fps)          # a cena gerada vem a 24: mistura, não copia
        laco = lambda geo: _laco(s.get("desde", 0), ff.dur(arq) - 1 / FPS, n, geo, s.get("congela", False),
                                 s.get("vai_volta", False), taxa)
        if "cena" in s:
            filtro = f"[0:v]{laco(f'scale={W}:{H},setsar=1')}[v]"
        else:
            # tela dividida reta: o painel em cima, e a cena (os px em volta do `foco`, no quadro 1080×1920)
            # sobe meia costura por cima dele num degradê — o corte reto seco o dono reprovou (30/09)
            costura, d = r.est["costura"]
            topo = costura - d // 2
            y = min(max(s.get("foco", 960) - (H - costura) // 2 - d // 2, 0), topo)
            entradas += [*base, "-loop", "1", "-framerate", str(FPS), "-i", str(degrade(r, W, H - topo))]
            filtro = (f"[0:v]{laco(f'scale={W}:{H},setsar=1,crop={W}:{H - topo}:0:{y}')},format=rgba[c0];"
                      f"[2:v]format=gray[m];[c0][m]alphamerge[c];[1:v]format={ff.PIX_FMT}[p];[p][c]overlay=0:{topo}[v]")
        _codifica(entradas, filtro, n, out)
    else:
        _codifica(base, f"[0:v]format={ff.PIX_FMT}[v]", n, out)
    marca.write_text(chave, encoding="utf-8")
    return out


def _desvio(trechos: list, t: float) -> float | None:
    """Quanto o webm está adiantado em relação à voz no instante `t`, pelo mapa; None onde o webm não tem rosto."""
    for m in trechos:
        if m["fonte"][0] - 1e-3 <= t < m["fonte"][1]:
            return round(m["gerado"][0] - m["fonte"][0], 3)
    return None


def _partes(r: Reel) -> list:
    """A `base` como o take a toca: com `mapa`, o trecho de rosto se parte onde o webm salta em relação à
    voz (a pausa que saiu dela, a frase que a HeyGen não recebeu). O webm toca contínuo dentro do trecho,
    e o trecho que passasse pelo salto sairia com a boca fora da voz. O cenário em vídeo segue de onde
    estava, sem voltar ao começo no corte."""
    av = r.p["avatar"]
    if "mapa" not in av:
        return r.p["base"]
    trechos = json.loads(r.rel(av["mapa"]).read_text(encoding="utf-8"))["trechos"]
    bordas = sorted({t for m in trechos for t in m["fonte"]})
    saida = []
    for s in r.p["base"]:
        if "avatar" not in s or s.get("congela"):
            saida.append(s)
            continue
        cortes = [t for t in bordas if s["de"] + 1e-3 < t < s["ate"] - 1e-3
                  and _desvio(trechos, t) != _desvio(trechos, t - 2e-3)]
        for a, b in zip([s["de"], *cortes], [*cortes, s["ate"]]):
            p = {**s, "de": a, "ate": b}
            f = str(s.get("fundo", ""))
            if a > s["de"] and f.startswith("@") and r.rel(f[1:]).suffix.lower() in VIDEOS:
                p["desde"] = round((s.get("desde", 0) + a - s["de"]) % ff.dur(r.rel(f[1:])), 3)
            saida.append(p)
    return saida


def take(r: Reel) -> Path:
    partes = [trecho(r, s, i) for i, s in enumerate(_partes(r))]
    lista = r.trab / "take.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    out = r.trab / "take.mp4"
    ff.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(out)], quiet=True)
    print(f"take: {out}  {ff.dur(out):.2f}s")
    return out


RECORTE = AQUI / "recorte.swift"


def recorta(take_: Path, out: Path, n_quadros: int | None = None) -> Path:
    """A pessoa recortada de um vídeo: uma máscara por quadro do Vision da Apple (VNGeneratePersonSegmentationRequest,
    accurate, ~0,1 s/quadro, de graça), o vídeo com ela de alfa (ProRes 4444). Só macOS (swiftc). É o que deixa a
    camada tras da e_editorial (a voz `gigante`) passar atrás do corpo, e a cabeça passar da borda do cartão. Quem chama:
    o `recorte` do plano (abaixo) e o `referencia.py dividida` (o take de câmera no cartão).
    ponytail: a máscara inteira do Vision; o que ela junta à pessoa (o quadro pendurado atrás da cabeça, no
    bruto) só aparece se houver tras naquele trecho. Limpar por caixa, se pedir, como o fundo.py do hero."""
    import tempfile
    marca = out.with_suffix(".recorte.json")
    chave = json.dumps([_estado(take_), hashlib.md5(RECORTE.read_bytes()).hexdigest(), n_quadros])
    if out.exists() and marca.exists() and marca.read_text(encoding="utf-8") == chave:
        return out
    exe = Path(tempfile.gettempdir()) / f"recorte-{hashlib.md5(RECORTE.read_bytes()).hexdigest()[:8]}"
    if not exe.exists():
        subprocess.run(["swiftc", "-O", str(RECORTE), "-o", str(exe)], check=True)
    with tempfile.TemporaryDirectory() as d:
        q, m = Path(d) / "q", Path(d) / "m"
        q.mkdir()
        ff.run(["ffmpeg", "-y", "-i", str(take_), "-q:v", "2", str(q / "%05d.jpg")], quiet=True)
        subprocess.run([str(exe), str(q), str(m)], check=True, stdout=subprocess.DEVNULL)
        # a borda come 1 px e amacia (o MinFilter + desfoque do fundo.py do hero): sem isso o halo do fundo
        # velho contorna o cabelo por cima do título
        limite = ["-frames:v", str(n_quadros)] if n_quadros else []
        ff.run(["ffmpeg", "-y", "-i", str(take_), "-framerate", str(FPS), "-i", str(m / "%05d.png"), "-filter_complex",
                f"[1:v]format=gray,scale={W}:{H},erosion,gblur=sigma=1.4[m];[0:v]format=yuva444p[v];[v][m]alphamerge",
                *limite, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(out)], quiet=True)
    marca.write_text(chave, encoding="utf-8")
    print(f"pessoa (recorte): {out}")
    return out


def recorte(r: Reel) -> Path:
    """A pessoa recortada do próprio take (`recorte` no plano): ver `recorta`."""
    return recorta(r.trab / "take.mp4", r.trab / "pessoa.mov", quadros(r.p["dur"]))


def pessoa(r: Reel) -> Path:
    """O avatar sozinho, com o alfa do webm, no mesmo lugar do take, nos trechos do cartão;
    no resto, transparente. O compor só usa o que fica acima do cartão: a cabeça. Com `recorte`,
    a pessoa do take inteiro (`recorte`)."""
    if r.p.get("recorte"):
        return recorte(r)
    out = r.trab / "pessoa.mov"
    cartoes = [s for s in _partes(r) if s.get("quadro") == "cartao"]
    entradas = ["-f", "lavfi", "-i", f"color=c=black@0:s={W}x{H}:r={FPS},format=yuva444p"]
    fs, ult = [], "0:v"
    for k, s in enumerate(cartoes, 1):
        entrada, cadeia, g = _avatar(r, s, k)
        entradas += [*entrada[:-2], "-t", f"{s['ate'] - s['de']:.3f}", *entrada[-2:]]
        fs += [f"[{k}:v]{cadeia},format=yuva444p,setpts=PTS-STARTPTS+{s['de']:.3f}/TB[a{k}]",
               f"[{ult}][a{k}]overlay={g['x']}:{g['y']}:eof_action=pass:format=yuv444[b{k}]"]
        ult = f"b{k}"
    mapa = ["-filter_complex", ";".join(fs), "-map", f"[{ult}]"] if fs else []
    ff.run(["ffmpeg", "-y", *entradas, *mapa, "-frames:v", str(quadros(r.p["dur"])), "-c:v", "prores_ks",
            "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(out)], quiet=True)
    print(f"pessoa: {out}")
    return out


# ───────────────────────── camadas e peças ─────────────────────────
def r_editorial(r: Reel) -> dict:
    ed = json.loads(json.dumps(r.p["r"]))
    ed["fala"] = [] if r.p.get("_sem_fala") else fala(r)     # o degrau sem a skill de legendas
    if not r.p.get("_parada"):      # a câmera anda e empurra quando uma peça entra (o degrau sem movimento para)
        empurra = []
        for t in sorted(p.get("de", p["em"]) for p in r.p.get("pecas", [])):
            if 0.3 < t < ed["dur"] - 0.5 and (not empurra or t - empurra[-1] >= 1.0):
                empurra.append(t)
        ed.setdefault("camera", {"empurra": empurra})
    # ponytail: a folha de estilo entra por um terminal que nasce depois do fim (o render
    # para no `dur`): a <style> vale pra peça inteira e o terminal nunca aparece. Sem mexer no núcleo.
    ed["graficos"] = ed.get("graficos", []) + [{"t": ed["dur"] + 1, "ate": ed["dur"] + 2, "g": "term",
                                                "linhas": ["<style>" + css_fala(r.est.get("legenda_ig") or 1450, r.est.get("zona"), r.est.get("botoes"))
                                                           + r.p.get("css", "") + "</style>"]}]
    return ed


def camadas(r: Reel) -> Path:
    base = r.trab / "ed"
    subprocess.run([PY, str(V2), "camadas", "e_editorial", f"r={_json(r_editorial(r))}", *_tema(r), "--out", str(base)],
                   check=True)
    return base.with_suffix(".json")


def _valor(r: Reel, v):
    """`@_trabalho/cap/x.png` vira caminho absoluto; `@foco:dez` vira a região medida na captura."""
    if not isinstance(v, str) or not v.startswith("@"):
        return v
    if v.startswith("@foco:"):
        return ",".join(str(x) for x in json.loads((r.cap / "focos.json").read_text(encoding="utf-8"))[v[6:]])
    return str(r.rel(v[1:]))


def picos(r: Reel, de: float, ate: float, n: int = 56) -> str:
    """A forma da onda daquele trecho da voz: o pico de cada uma das n fatias, sobre o maior."""
    x = _amostras(r.voz)[int(de * SR):int(ate * SR)]
    v = np.array([np.sqrt((c ** 2).mean()) for c in np.array_split(x, n)])
    return ",".join(f"{a:.2f}" for a in np.clip(v / v.max(), 0.08, 1))


def pecas(r: Reel) -> Path:
    """Cada peça do plano, renderizada uma vez: só refaz se o pedido, o desenho dela ou o núcleo mudou."""
    pasta = r.trab / "pecas"
    pasta.mkdir(parents=True, exist_ok=True)
    nucleo = [_estado(p) for p in [*sorted((V2DIR / "nucleo").glob("*.*")), *([MARCA_CSS] if _tema(r) else [])]]
    feitas = {}
    for p in r.p["pecas"]:
        q = dict(p["q"])
        if _tema(r):
            q.setdefault("tema", r.est["tema"])
        if "onda" in p:
            q["picos"] = picos(r, *p["onda"])
        pares = [f"{k}={_valor(r, v)}" for k, v in q.items()]
        html = V2DIR / "pecas" / f"{p['peca']}.html"
        # a captura refeita no mesmo caminho muda o arquivo, não o pedido: o estado dela entra na chave
        citados = [_estado(r.rel(v[1:])) for v in q.values()
                   if isinstance(v, str) and v.startswith("@") and not v.startswith("@foco:")]
        out = pasta / f"{p['nome']}.mov"
        marca = out.with_suffix(".q")
        rastro = ["--rastro"] if p.get("rastro") else []    # motion blur, ~5× o render da peça
        chave = hashlib.md5(json.dumps([p["peca"], pares, _estado(html) if html.exists() else None, nucleo,
                                        citados, *rastro]).encode()).hexdigest()
        if not (out.exists() and marca.exists() and marca.read_text(encoding="utf-8") == chave):
            subprocess.run([PY, str(V2), "render", p["peca"], *pares, *rastro, "--out", str(out)], check=True)
            marca.write_text(chave, encoding="utf-8")
        feitas[p["nome"]] = chave
    lista = r.trab / "pecas.json"
    lista.write_text(json.dumps(feitas, indent=1), encoding="utf-8")
    return lista


# ───────────────────────── compor e junta ─────────────────────────
def compor(r: Reel) -> Path:
    out = r.trab / "composto.mp4"
    subprocess.run([PY, str(V2), "compor", "--take", str(r.trab / "take.mp4"), "--pessoa", str(r.trab / "pessoa.mov"),
                    "--peca", str(r.trab / "ed.json"), "--em", "0", "--folga", "1", "--out", str(out)], check=True)
    # os sons são os do plano, à mão: os cues que a e_editorial publica ficam de fora
    out.with_suffix(".cues.json").unlink(missing_ok=True)
    return out


def imagem(r: Reel, p: dict) -> Path:
    """Uma imagem parada do plano (o logo), na largura `w`, com uma sombra difusa escura atrás
    (legível sobre qualquer painel) quando `sombra`."""
    from PIL import Image, ImageFilter
    out = r.trab / f"img_{p['nome']}.png"
    im = Image.open(r.rel(p["arquivo"])).convert("RGBA")
    im = im.resize((p["w"], round(im.height * p["w"] / im.width)), Image.LANCZOS)
    if p.get("sombra"):
        m = 40
        s = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m))
        a = Image.new("RGBA", im.size, (0, 0, 0, 0))
        a.putalpha(im.getchannel("A").point(lambda v: int(v * p["sombra"])))
        s.paste(a, (m, m + 6))
        s = s.filter(ImageFilter.GaussianBlur(14))
        s.alpha_composite(im, (m, m))
        im = s
    im.save(out)
    return out


def desenhado(r: Reel, p: dict, mov: Path) -> list[int]:
    """[x0, y0, x1, y1] do que a peça desenha: a união dos quadros parados (a 10 por segundo, o
    que não andou do anterior pra ele). O último quadro sozinho errava duas vezes: a peça que muda
    de largura (o o_estados com o último estado mais estreito) vazava pela borda, e a que sai
    (`sai`) não tinha caixa nenhuma. O voo da entrada fica de fora: ele anda."""
    arq = r.trab / "pecas" / f"{p['nome']}.desenho.json"
    if arq.exists() and json.loads(arq.read_text(encoding="utf-8"))["mov"] == _estado(mov):
        return json.loads(arq.read_text(encoding="utf-8"))["caixa"]
    w, h = W // 2, H // 2
    raw = ff.run(["ffmpeg", "-v", "error", "-i", str(mov), "-vf", f"fps=10,alphaextract,scale={w}:{h}",
                  "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture=True, binario=True, quiet=True).stdout
    caixas = []
    for q in np.frombuffer(raw, np.uint8).reshape(-1, h, w) > 16:
        ys, xs = np.flatnonzero(q.any(1)), np.flatnonzero(q.any(0))
        caixas.append((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1) if len(ys) else None)
    paradas = [c for a, c in zip([None, *caixas], caixas) if a and c and max(abs(u - v) for u, v in zip(a, c)) <= 2]
    paradas = paradas or [c for c in caixas if c][-1:]        # a peça que nunca para: o último quadro com desenho
    if not paradas:
        raise ValueError(f"peça {p['nome']}: nenhum quadro de {mov.name} desenha nada")
    caixa = [2 * int(f(c[i] for c in paradas)) for i, f in enumerate((min, min, max, max))]
    arq.write_text(json.dumps({"mov": _estado(mov), "caixa": caixa}), encoding="utf-8")
    return caixa


def encaixe(r: Reel, p: dict, mov: Path) -> tuple[float, int, int]:
    """`caixa` [x0, y0, x1, y1] do reel: a escala e a posição que põem o que a peça desenha
    (`desenhado`) dentro dela, centrado. Sem caixa, o `escala`, `x` e `y` do plano."""
    if "caixa" not in p:
        return p.get("escala", 1.0), p.get("x", 0), p.get("y", 0)
    x0, y0, x1, y1 = desenhado(r, p, mov)
    X0, Y0, X1, Y1 = p["caixa"]
    e = min((X1 - X0) / (x1 - x0), (Y1 - Y0) / (y1 - y0), p.get("max", 2.0))
    return e, round((X0 + X1) / 2 - (x0 + x1) / 2 * e), round((Y0 + Y1) / 2 - (y0 + y1) / 2 * e)


def _por_cima(r: Reel, lista: list, k: int, ult: str) -> tuple[list, list, str, int]:
    """As peças `lista` por cima de [ult]: as entradas (a partir da k), os filtros, o rótulo do
    resultado e a próxima entrada livre."""
    entradas, fs, dur = [], [], r.p["dur"]
    for p in lista:
        mov = r.trab / "pecas" / f"{p['nome']}.mov"
        a, b = p.get("de", p["em"]), min(p.get("ate", p["em"] + ff.dur(mov)), dur)
        entradas += ["-i", str(mov)]
        e, x, y = encaixe(r, p, mov)
        esc = f",scale=trunc(iw*{e:.4f}/2)*2:-2" if abs(e - 1) > 1e-3 else ""
        if "move" in p:                          # desliza até move.y em move.d segundos, com a curva suave nas pontas
            m = p["move"]
            u = f"clip((t-{m['t']})/{m['d']},0,1)"
            y = f"'{y}+({m['y']}-({y}))*{u}*{u}*(3-2*{u})'"
        fs.append(f"[{k}:v]format=yuva444p{esc},setpts=PTS-STARTPTS+{p['em']:.3f}/TB[p{k}]")
        fs.append(f"[{ult}][p{k}]overlay={x}:{y}:enable='between(t,{a:.3f},{b - .001:.3f})'"
                  f":eof_action={'repeat' if p.get('segura') else 'pass'}[o{k}]")
        ult, k = f"o{k}", k + 1
    return entradas, fs, ult, k


def junta(r: Reel) -> Path:
    """As imagens e as peças por cima do composto, e a voz. `em` é o 0 da peça no reel; ela aparece de
    `de` (padrão: `em`) até `ate`; `segura` congela o último quadro até o `ate`; `move` desliza."""
    dur = r.p["dur"]
    entradas = ["-i", str(r.trab / "composto.mp4")]
    # o quadro 0 do composto sai sem painel e sem cartão: o gsap não aplica o `set` em t=0 quando
    # a render busca o tempo 0. O 1º quadro vira cópia do 2º, e o resto não anda
    fs, ult, k = ["[0:v]trim=start_frame=1,setpts=PTS-STARTPTS,tpad=start=1:start_mode=clone[c0]"], "c0", 1
    for p in r.p.get("imagens", []):
        entradas += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(imagem(r, p))]
        fs.append(f"[{ult}][{k}:v]overlay={p['x']}:{p['y']}:enable='between(t,{p['de']:.3f},{p['ate'] - .001:.3f})'[i{k}]")
        ult, k = f"i{k}", k + 1
    # com degraus, o placar e o balão (o `hud`) vão por cima da montagem, não do degrau
    hud = set((r.p.get("degraus") or {}).get("hud", []))
    e2, f2, ult, k = _por_cima(r, [p for p in r.p["pecas"] if p["nome"] not in hud], k, ult)
    entradas, fs = entradas + e2, fs + f2
    fs.append(f"[{ult}]format={ff.PIX_FMT}[v]")
    entradas += ["-i", str(r.voz)]
    out = r.trab / "imagem_voz.mp4"
    ff.run(["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(fs), "-map", "[v]", "-map", f"{k}:a",
            "-t", f"{dur:.3f}", *ff.args_video("final"), *ff.args_audio(), str(out)], quiet=True)
    print(f"junta: {out}  {ff.dur(out):.2f}s")
    erros = vazios(r, out)
    if erros:
        # fora do caminho: o `--desde som` montaria o final em cima do render reprovado
        fora = out.with_name("imagem_voz.reprovado.mp4")
        out.replace(fora)
        sys.exit("a trava da tela cheia reprovou o render:\n  " + "\n  ".join(erros) + f"\n  (ficou em {fora.name}, pra olhar)")
    return out


def vazios(r: Reel, video: Path) -> list[str]:
    """A trava da tela cheia, medida no render: em cada trecho de painel (sem rosto), a maior faixa
    de linhas sem nada acima da legenda do Instagram, a 4 quadros por segundo. Nada é o pixel igual
    ao do painel parado daquele trecho; a linha com 2% de pixels diferentes já tem alguma coisa.
    Faixa acima de VAZIO_MAX por mais de VAZIO_TOL reprova. Calibrado no heygen-rosto em 30/09:
    captura na largura toda deixa 110–200 px; contador sozinho 340–440, os chips 410–1360 e a
    ficha 310–760 (as telas que o dono reprovou)."""
    from PIL import Image
    teto, k, fps = r.est.get("legenda_ig") or H, 4, 4
    w, h = W // k, H // k
    raw = ff.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h}:flags=area",
                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture=True, binario=True, quiet=True).stdout
    q = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    erros = []
    for s in _paineis(r.p["base"]):
        chao_ = np.asarray(Image.open(painel(r, s["painel"])).convert("RGB").resize((w, h), Image.BOX), np.int16)
        ruins = []
        for i in range(math.ceil(s["de"] * fps), min(len(q), math.ceil(s["ate"] * fps))):
            cheia = (np.abs(q[i].astype(np.int16) - chao_).max(2) > 24)[:teto // k].mean(1) >= 0.02
            vao, y = _maior_vao(cheia, k)
            if vao > VAZIO_MAX:
                ruins.append((i / fps, vao, y))
        if len(ruins) / fps > VAZIO_TOL:
            t, vao, y = max(ruins, key=lambda x: x[1])
            erros.append(f"tela cheia {s['de']:.2f}–{s['ate']:.2f}: {len(ruins) / fps:.2f}s com faixa vazia acima de "
                         f"{VAZIO_MAX}px (a pior, {vao}px em y {y}–{y + vao}, aos {t:.2f}s). Sem o rosto, a captura "
                         f"enche a tela, ganha camadas, ou vira tela dividida com o rosto no cartão")
    return erros


# ───────────────────────── os degraus ─────────────────────────
# As camadas que um degrau liga, uma por pedido. Um degrau é o mesmo take com as primeiras N da `ordem`
# do plano ligadas; desligar uma é tirar do plano o que ela faz. Camada fora da `ordem` fica sempre ligada.
SKILLS = ("ritmo", "legendas", "composicao", "cenarios", "movimento", "estilo", "capa")


def _limpa(w: str) -> str:
    return w.lower().strip(".,;:!?…“”\"'")


def ancora(alvo, falas: list, desde: float = 0.0) -> float:
    """Um tempo do plano: o número, ou o fim da palavra `alvo` dita a partir de `desde`. Casar pela fala
    é o que deixa o plano valer depois de a voz mudar."""
    if isinstance(alvo, (int, float)):
        return float(alvo)
    for w, _, b in falas:
        if b > desde + 1e-3 and _limpa(w) == _limpa(alvo):
            return float(b)
    raise ValueError(f"degraus: a palavra `{alvo}` não aparece na fala depois de {desde:.2f}s")


def frases(falas: list) -> list[float]:
    """Onde começa cada frase da fala (a primeira palavra depois de . ? !)."""
    inicio, novas = [], True
    for w, a, _ in falas:
        if novas:
            inicio.append(float(a))
        novas = bool(re.search(r"[.?!]$", w))
    return inicio


def degrau(p: dict, desliga: set, ate: float, inicios: list[float], zoom: float = 1.12) -> dict:
    """O plano do mesmo take em [0, ate] com as camadas `desliga` tiradas. Sem composição o rosto fica
    inteiro sobre o escritório (o bruto da HeyGen); sem ritmo não há o corte com zoom a cada frase; sem
    legendas a fala cala; sem cenários o rosto volta pro escritório; sem movimento as peças saem; sem
    estilo o painel fica num tema só; sem capa o quadro não congela e as peças da capa saem."""
    q = json.loads(json.dumps(p))
    hud = set(q.pop("degraus").get("hud", []))
    for k in ("fechos", "youtube", "capa", "sons"):
        q.pop(k, None)
    r = q["r"]
    q["dur"] = r["dur"] = ate
    dentro = lambda de: de < ate - 1e-3
    q["base"] = [{**s, "ate": min(s["ate"], ate)} for s in q["base"] if dentro(s["de"])]
    r["cenas"] = [[c[0], min(c[1], ate), *c[2:]] for c in r.get("cenas", []) if dentro(c[0])]
    for k in ("graficos", "vozes"):
        r[k] = [{**g, "ate": min(g["ate"], ate)} for g in r.get(k, []) if dentro(g["t"])]
    q["imagens"] = [{**g, "ate": min(g["ate"], ate)} for g in q.get("imagens", []) if dentro(g["de"])]
    q["pecas"] = [x for x in q.get("pecas", []) if x["nome"] not in hud and dentro(x.get("de", x["em"]))]
    if "composicao" in desliga:
        q["base"] = [{"de": 0.0, "ate": ate, "avatar": q["base"][0].get("avatar", 0.0), "quadro": "cheio"}]
        r["graficos"] = []
        if "ritmo" not in desliga:   # o corte seco a cada frase: o zoom alterna, e o take não para
            cortes = [0.0, *[t for t in inicios if 0.3 < t < ate - 0.3], ate]
            r["cenas"] = [[a, b, "rosto", "claro", zoom] if i % 2 else [a, b, "rosto"]
                          for i, (a, b) in enumerate(zip(cortes, cortes[1:]))]
        else:
            r["cenas"] = [[0.0, ate, "rosto"]]
    else:
        if "ritmo" in desliga:
            r["cenas"] = [c[:4] for c in r["cenas"]]
        if "estilo" in desliga:
            r["cenas"] = [c if c[2] == "rosto" else [*c[:3], "claro", *c[4:]] for c in r["cenas"]]
    if "cenarios" in desliga:        # o cenário gerado atrás do rosto é o `fundo` que é arquivo (@…)
        q["base"] = [{k: v for k, v in s.items() if not (k == "fundo" and str(v).startswith("@"))} for s in q["base"]]
    if "capa" in desliga:
        q["base"] = [{k: v for k, v in s.items() if k != "congela"} for s in q["base"]]
        q["pecas"] = [x for x in q["pecas"] if x.get("camada") != "capa"]
    if "legendas" in desliga:
        q["_sem_fala"], r["vozes"] = True, []
    if "movimento" in desliga:
        q["pecas"], q["imagens"], q["_parada"] = [], [], True
        r.pop("camera", None)
    # trechos vizinhos que ficaram iguais viram um: o rosto não pula no lugar onde o cenário saiu
    junta = []
    for s in q["base"]:
        u = junta[-1] if junta else None
        if u and "avatar" in s and {k: v for k, v in u.items() if k not in ("de", "ate", "avatar")} == \
                {k: v for k, v in s.items() if k not in ("de", "ate", "avatar")} and abs(u["ate"] - s["de"]) < 1e-3:
            u["ate"] = s["ate"]
        else:
            junta.append(s)
    q["base"] = junta
    return q


def degraus(r: Reel) -> Path:
    """O mesmo take com 0, 1… N skills, e o reel que troca de degrau na palavra de cada pedido.

    Cada degrau é um plano derivado (`degrau`) montado pelos mesmos passos do reel numa pasta própria,
    com as peças já renderizadas emprestadas; o último degrau é o próprio reel. A montagem corta cada
    um no trecho dele, põe o `hud` por cima e a voz. Os degraus soltos, [0, ate], ficam em
    degraus/sN.mp4, com a voz: outros vídeos usam o mesmo trecho ganhando camada."""
    d, falas = r.p["degraus"], fala(r)
    trocas, t = [], 0.0
    for x in d["trocas"]:
        t = ancora(x, falas, t)
        trocas.append(t)
    ate = ancora(d.get("ate", round(trocas[-1] + 2.0, 2)), falas, trocas[-1])
    pasta = r.trab / "degraus"
    pasta.mkdir(parents=True, exist_ok=True)
    estados = []
    for k in range(len(d["ordem"])):
        sub = pasta / f"s{k}"
        sub.mkdir(exist_ok=True)
        q = degrau(r.p, set(d["ordem"][k:]), ate, frases(falas), d.get("zoom", 1.12))
        (sub / "reel.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
        if not (sub / "pecas").exists():
            (sub / "pecas").symlink_to(r.trab / "pecas")
        rr = Reel(sub)
        for passo in (take, pessoa, camadas, compor, junta):
            passo(rr)
        shutil.copyfile(sub / "imagem_voz.mp4", pasta / f"s{k}.mp4")
        estados.append(sub / "imagem_voz.mp4")
    estados.append(r.trab / "imagem_voz.mp4")
    n = len(estados) - 1
    ff.run(["ffmpeg", "-y", "-i", str(estados[-1]), "-frames:v", str(quadros(ate)), "-t", f"{ate:.3f}",
            *ff.args_video("final"), *ff.args_audio(), str(pasta / f"s{n}.mp4")], quiet=True)

    cortes = [0.0, *trocas, r.p["dur"]]
    entradas, fs = [], []
    for k, src in enumerate(estados):
        entradas += ["-i", str(src)]
        fs.append(f"[{k}:v]trim=start_frame={quadros(cortes[k])}:end_frame={quadros(cortes[k + 1])},"
                  f"setpts=PTS-STARTPTS,format={ff.PIX_FMT}[d{k}]")
    fs.append("".join(f"[d{k}]" for k in range(len(estados))) + f"concat=n={len(estados)}:v=1:a=0[m]")
    hud = [p for p in r.p["pecas"] if p["nome"] in set(d.get("hud", []))]
    e2, f2, ult, k = _por_cima(r, hud, len(estados), "m")
    fs += [*f2, f"[{ult}]format={ff.PIX_FMT}[v]"]
    out = r.trab / "imagem_degraus.mp4"
    ff.run(["ffmpeg", "-y", *entradas, *e2, "-i", str(r.voz), "-filter_complex", ";".join(fs), "-map", "[v]",
            "-map", f"{k}:a", "-t", f"{r.p['dur']:.3f}", *ff.args_video("final"), *ff.args_audio(), str(out)], quiet=True)
    print(f"degraus: {out}  trocas em {', '.join(f'{x:.2f}' for x in trocas)}s · soltos em {pasta}/s0–s{n}.mp4 ([0, {ate:.2f}]s)")
    return out


# ───────────────────────── som ─────────────────────────
def trilha(r: Reel) -> Path:
    """A trilha em pedaços da mesma faixa: [de, ate] da faixa entra em `em` do reel, com fade nas
    pontas. Sem pedaços, a faixa inteira do começo."""
    t = r.p["trilha"]
    src = faixa_de(t["faixa"])
    out = r.trab / "trilha.m4a"
    ps = t.get("pedacos") or [{"de": 0.0, "ate": ff.dur(src), "em": 0.0}]
    fs = [f"[0:a]atrim={p['de']}:{p['ate']},asetpts=PTS-STARTPTS,afade=t=in:d={p.get('entra', 0.05)},"
          f"afade=t=out:st={p['ate'] - p['de'] - p.get('sai', 0.3):.3f}:d={p.get('sai', 0.3)},"
          f"adelay={round(p['em'] * 1000)}:all=1[t{i}]" for i, p in enumerate(ps)]
    fs.append("".join(f"[t{i}]" for i in range(len(ps))) + f"amix=inputs={len(ps)}:normalize=0,"
              f"apad=whole_dur={r.p['dur'] + 1:.2f}[m]")
    ff.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", ";".join(fs), "-map", "[m]", *ff.args_audio(), str(out)], quiet=True)
    return out


def _mixa(r: Reel, video: Path, sons: list, voz_: Path, pasta: Path, out: Path) -> Path:
    """Os efeitos e a trilha com ducking na fala da `voz_`, numa mistura só (som.mistura, pelo mixa.py
    com a cama do estilo). Antes os efeitos passavam pelo som.py, que gravava um AAC pro mixa ler."""
    plan = pasta / "sons.json"
    plan.write_text(json.dumps({"sons": [{**x, "arquivo": str(r.rel(x["arquivo"]))} if "arquivo" in x else x
                                         for x in sons]}, ensure_ascii=False, indent=1), encoding="utf-8")
    fala_ = ",".join(f"{a}:{b}" for a, b in _segmentos(voz_))
    musica = [] if r.p["trilha"]["faixa"] == SEM_TRILHA else ["--trilha", str(trilha(r))]   # sem ela, o mixa só nivela
    subprocess.run([PY, str(AQUI / "mixa.py"), str(video), *musica, "--fala", fala_,
                    "--sons", str(plan), "--mestre", str(r.est["sfx_db"]), *r.est["mixa"], "-o", str(out)], check=True)
    return out


def som(r: Reel) -> Path:
    video = r.trab / ("imagem_degraus.mp4" if r.p.get("degraus") else "imagem_voz.mp4")
    if r.p.get("fechos"):
        return fechos(r, video)
    return _mixa(r, video, r.p.get("sons", []), r.voz, r.trab, r.trab / "final.mp4")


def _na_frase(inicios: list[float], a: float, b: float) -> float:
    """O começo do fecho vai pro começo de frase mais perto (até meio segundo antes de `a`, e antes de
    `b`). A legenda fica na tela até a palavra seguinte, e o tempo do Whisper vem adiantado: o fecho
    que começava no silêncio, ou no rabo da frase anterior, abria com ela ("saiba mais" no começo do
    final do "comenta", 03/10)."""
    perto = [t for t in inicios if a - 0.5 <= t < b]
    return min(perto, key=lambda t: abs(t - a)) if perto else a


def fechos(r: Reel, video: Path) -> Path:
    """Um final por fecho: o corpo até o primeiro fecho e, emendado, só o fecho daquele final. Os fechos
    foram ditos em sequência no mesmo áudio, então o corpo é o mesmo quadro a quadro nos três. O som
    (os efeitos e a trilha) é misturado em cada final no tempo dele: a música não pula na emenda."""
    fe = r.p["fechos"]
    inicios = frases(fala(r))
    comeco = {nome: _na_frase(inicios, x[0], x[1]) for nome, x in fe.items() if x}
    corpo = quadros(min(comeco.values())) / FPS
    sons = r.p.get("sons", [])
    saidas = []
    for nome, x in fe.items():
        pasta = r.trab / "fechos" / nome
        pasta.mkdir(parents=True, exist_ok=True)
        if not x:                                    # o corpo sozinho (o vídeo em laço da página)
            img, voz_ = pasta / "imagem_voz.mp4", pasta / "voz.wav"
            ff.run(["ffmpeg", "-y", "-i", str(video), "-frames:v", str(quadros(corpo)), "-t", f"{corpo:.4f}",
                    *ff.args_video("final"), *ff.args_audio(), str(img)], quiet=True)
            ff.run(["ffmpeg", "-y", "-i", str(img), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(voz_)], quiet=True)
            saidas.append(_mixa(r, img, [s for s in sons if s["t"] < corpo], voz_, pasta, r.trab / f"final-{nome}.mp4"))
            print(f"fecho {nome} (só o corpo): {saidas[-1]}  {ff.dur(saidas[-1]):.2f}s")
            continue
        _, b, *fica = x
        a = comeco[nome]
        a, b = quadros(a) / FPS, quadros(b) / FPS
        # o fim do fecho parado um instante (o padrão é meio segundo): os fechos foram ditos colados,
        # e o silêncio depois da última palavra de um é o começo do próximo
        fica = quadros(fica[0] if fica else 0.5) / FPS
        img, voz_ = pasta / "imagem_voz.mp4", pasta / "voz.wav"
        fs = (f"[0:v]trim=end_frame={quadros(corpo)},setpts=PTS-STARTPTS[v0];"
              f"[0:v]trim=start_frame={quadros(a)}:end_frame={quadros(b)},setpts=PTS-STARTPTS[v1];"
              f"[0:a]atrim=0:{corpo:.4f},asetpts=PTS-STARTPTS[a0];[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS[a1];"
              f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v1x][a1x];"
              f"[v1x]tpad=stop_mode=clone:stop_duration={fica:.4f}[v];[a1x]apad=pad_dur={fica:.4f}[a]")
        ff.run(["ffmpeg", "-y", "-i", str(video), "-filter_complex", fs, "-map", "[v]", "-map", "[a]",
                *ff.args_video("final"), *ff.args_audio(), str(img)], quiet=True)
        ff.run(["ffmpeg", "-y", "-i", str(img), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(voz_)], quiet=True)
        meus = [s for s in sons if s["t"] < corpo] + [{**s, "t": round(s["t"] - a + corpo, 3)} for s in sons if a <= s["t"] < b]
        saidas.append(_mixa(r, img, meus, voz_, pasta, r.trab / f"final-{nome}.mp4"))
        print(f"fecho {nome}: {saidas[-1]}  {ff.dur(saidas[-1]):.2f}s")
    shutil.copyfile(saidas[0], r.trab / "final.mp4")
    return r.trab / "final.mp4"


# ───────────────────────── folha e capa ─────────────────────────
def folha(r: Reel, final: Path | None = None, png: Path | None = None, ultimos: float = 0) -> None:
    """A folha a 1 quadro por segundo (com `ultimos`, só os últimos segundos, a 4 por segundo) e a medida do final."""
    final, png = final or r.trab / "final.mp4", png or r.trab / "folha-1fps.png"
    n = ff.dur(final)
    if ultimos:
        ss, vf = ["-ss", f"{n - ultimos:.3f}"], f"fps=4,scale=270:480,tile=8x{math.ceil(ultimos / 2)}:padding=4:color=white"
    else:
        ss, vf = [], f"fps=1,scale=270:480,tile=10x{(int(n) + 9) // 10}:padding=4:color=white"
    # com zona segura, a folha risca ela (vermelho) e a coluna de botões (magenta): é aqui que se confere
    # a peça sem caixa
    z, b = r.est.get("zona"), r.est.get("botoes")
    if z:
        vf = (f"drawbox=x={z[0]}:y={z[1]}:w={z[2] - z[0]}:h={z[3] - z[1]}:color=red@0.8:t=6,"
              + (f"drawbox=x={b[0]}:y={b[1]}:w={W - b[0]}:h={H - b[1]}:color=magenta@0.6:t=5," if b else "") + vf)
    ff.run(["ffmpeg", "-y", *ss, "-i", str(final), "-vf", vf, "-frames:v", "1", str(png)], quiet=True)
    res = ff.run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"],
                 capture=True, quiet=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", res)[-1]
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", res)[-1]
    p = ff.probe(final)
    print(f"folha: {png}\nfinal: {final}  {p.largura}x{p.altura} {p.fps} fps  {p.duracao:.2f}s  {i} LUFS  pico {tp} dBTP")


def capa(r: Reel) -> Path:
    """No molde do Nick (g_capa_nick), pelo capa.py: a foto recortada, o logo da ferramenta no topo, o título
    com o destaque. Tudo que é do vídeo vem do `capa` do plano; o recorte fica na pasta de trabalho."""
    if "expr" in r.p["capa"] and "foto" not in r.p["capa"]:
        sys.exit("a `capa` tem `expr`, uma das doze expressões do dono, que o tronco não conhece: diga a `foto` "
                 "pelo caminho do PNG recortado, da pasta do vídeo")
    return capa_nick(r.p["capa"], r.dir, r.trab / "capa-nick.jpg", tema=r.est.get("tema"))


# ───────────────────────── o que vai pra HeyGen ─────────────────────────
def heygen(r: Reel) -> None:
    """avatar/geracao.wav: só os trechos de rosto da voz (os `base` com avatar, os vizinhos
    juntos), com `sobra` de cada lado pra boca assentar, emendados com `vao` de silêncio.
    Onde a sobra cai numa pausa, ela leva no máximo `cala` de silêncio depois (ou antes) da voz:
    vão + 2 × cala fica abaixo do teto de pausa do pre_voo (0,6 s). A borda de cada trecho
    ganha 5 ms de fade (corte no meio da palavra estala).
    avatar/geracao.json é o mapa reel → arquivo gerado (o `mapa` do avatar)."""
    sobra, vao, cala, dur = 0.25, 0.1, 0.2, r.p["dur"]
    grupos = []
    # o trecho que congela (a capa) só precisa do quadro do `de`, que a sobra do trecho anterior já traz
    for s in (b for b in r.p["base"] if "avatar" in b and not b.get("congela")):
        if grupos and abs(grupos[-1][1] - s["de"]) < 1e-3:
            grupos[-1][1] = s["ate"]
        else:
            grupos.append([s["de"], s["ate"]])
    x = _amostras(r.voz)
    x = np.concatenate([x, np.zeros(max(0, int(dur * SR) - len(x)), np.float32)])   # o reel passa do fim da voz
    on = np.flatnonzero(_envelope(x) > -45)      # os quadros de 10 ms com voz
    rampa = np.linspace(0, 1, int(0.005 * SR), dtype=np.float32)
    partes, trechos, t = [], [], 0.0
    for a, b in grupos:
        f0, f1 = max(0.0, a - sobra), min(dur, b + sobra)
        antes, depois = on[on < f1 * 100], on[on >= f0 * 100]
        if len(antes) and f1 - (antes[-1] + 1) / 100 > cala:
            f1 = max(b + 0.05, (antes[-1] + 1) / 100 + cala)
        if len(depois) and depois[0] / 100 - f0 > cala:
            f0 = min(a - 0.05, depois[0] / 100 - cala)
        f0, f1 = float(max(0.0, f0)), float(min(dur, f1))
        y = x[int(f0 * SR):int(f1 * SR)].copy()
        y[:len(rampa)] *= rampa
        y[-len(rampa):] *= rampa[::-1]
        trechos.append({"reel": [a, b], "fonte": [round(f0, 3), round(f1, 3)], "gerado": [round(t, 3), round(t + len(y) / SR, 3)]})
        partes += [y, np.zeros(int(vao * SR), np.float32)]
        t += len(y) / SR + vao
    pasta = r.dir / "avatar"
    pasta.mkdir(exist_ok=True)
    bruto = r.trab / "geracao.f32"
    bruto.write_bytes(np.concatenate(partes[:-1]).astype(np.float32).tobytes())
    ff.run(["ffmpeg", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(bruto), "-c:a", "pcm_s16le",
            str(pasta / "geracao.wav")], quiet=True)
    bruto.unlink()
    (pasta / "geracao.json").write_text(json.dumps({"voz": r.voz.name, "sobra": sobra, "vao": vao, "trechos": trechos}, indent=1), encoding="utf-8")
    print(f"heygen: {pasta / 'geracao.wav'}  {t - vao:.2f}s de rosto")


# ───────────────────────── o webm que chegou pronto ─────────────────────────
ACHA_SR = 8000      # o alinhamento ouve em 8 kHz: acha a amostra igual, e a FFT de um minuto sai em décimos
ACHOU = 0.9         # a correlação de um pedaço da voz com o áudio do webm. A mesma amostra dá 1,00 (o
                    # do-zero-ao-pronto, 03/10); a frase que a HeyGen não recebeu ficou abaixo de 0,4
PEDACO_MIN = 0.3    # s: pedaço que não acha só se parte em dois se cada metade tiver pelo menos isto


def alinha(r: Reel) -> None:
    """O `mapa` do webm que não saiu do passo `heygen` desta pasta (gerado da voz inteira, de um corte
    dela, ou de antes de ela ser aparada): cada pedaço da `fonte` achado no áudio do webm, que é a voz
    que a HeyGen recebeu. Pedaço que não acha se parte no ponto mais quieto e procura de novo (a pausa
    que saiu da voz); o que não acha de jeito nenhum fica sem rosto. Recusa a `base` que põe rosto ali."""
    av = r.p["avatar"]
    a, b = _amostras(r.voz, ACHA_SR), _amostras(r.rel(av["arquivo"]), ACHA_SR)
    sem = ("se o webm não saiu desta voz, tire o `alinha` e diga em cada trecho onde ele começa no webm "
           "(o `avatar` do trecho)")
    if not len(b):
        sys.exit(f"o webm não tem áudio, e o alinhamento ouve a voz que a HeyGen recebeu: {sem}")
    n, h = 1 << max(len(a), len(b)).bit_length(), ACHA_SR // 100
    B = np.fft.rfft(b, n)
    e = np.concatenate([[0.0], np.cumsum(b.astype(np.float64) ** 2)])

    def acha(i: int, j: int) -> list:
        x = a[i:j]
        m = len(x)
        if m <= len(b):
            c = np.fft.irfft(B * np.conj(np.fft.rfft(x, n)), n)[:len(b) - m + 1]
            cor = c / (np.sqrt(np.maximum(e[m:] - e[:-m], 1e-12)) * np.linalg.norm(x) + 1e-9)
            k = int(np.argmax(cor))
            if cor[k] >= ACHOU:
                return [[i, j, k - i]]
        if m < 2 * PEDACO_MIN * ACHA_SR:
            return [[i, j, None]]
        env = (x[:m // h * h].reshape(-1, h) ** 2).mean(1)
        lo, hi = len(env) // 10, len(env) - len(env) // 10
        corte = i + (lo + int(np.argmin(env[lo:hi]))) * h
        return acha(i, corte) + acha(corte, j)

    grupos = []
    for s0, s1 in _segmentos(r.voz):
        for i, j, d in acha(round(s0 * ACHA_SR), round(s1 * ACHA_SR)):
            if d is not None and grupos and grupos[-1][2] is not None and abs(grupos[-1][2] - d) <= h:
                grupos[-1][1] = j                  # o mesmo desvio do vizinho: o webm toca contínuo
            elif d is not None and len(grupos) > 1 and grupos[-1][2] is None and grupos[-2][2] is not None \
                    and abs(grupos[-2][2] - d) <= h:
                grupos[-2:] = [[grupos[-2][0], j, d]]   # o respiro que não achou, entre dois que concordam
            else:
                grupos.append([i, j, d])
    trechos, fim_a, fim_b = [], max(len(a) / ACHA_SR, float(r.p["dur"])), len(b) / ACHA_SR
    for k, (i, j, d) in enumerate(grupos):
        if d is None:
            continue
        f0 = 0.0 if k == 0 else (grupos[k - 1][1] + i) / 2 / ACHA_SR
        f1 = fim_a if k == len(grupos) - 1 else (j + grupos[k + 1][0]) / 2 / ACHA_SR
        d /= ACHA_SR
        f0, f1 = max(f0, -d), min(f1, fim_b - d)     # o rosto que o webm tem, nem antes nem depois dele
        trechos.append({"fonte": [round(f0, 3), round(f1, 3)], "gerado": [round(f0 + d, 3), round(f1 + d, 3)]})
    mapa = r.rel(av["mapa"])
    mapa.write_text(json.dumps({"voz": r.voz.name, "webm": av["arquivo"], "trechos": trechos}, indent=1), encoding="utf-8")
    tem = " · ".join(f"{m['fonte'][0]:.2f}–{m['fonte'][1]:.2f}" for m in trechos) or "lugar nenhum"
    falta = [f"{s['de']:.2f}–{s['ate']:.2f}" for s in _partes(r) if "avatar" in s and _desvio(trechos, s["de"]) is None]
    if falta:
        sys.exit(f"a base põe rosto onde o webm não tem, em {', '.join(falta)}s: a HeyGen não recebeu essa parte da "
                 f"voz. Buraco curto no meio da fala: um trecho `congela` que começa ainda no rosto (o quadro "
                 f"para ali); o fim sem rosto: `cena` do banco ou `painel`. O webm tem rosto em {tem}s ({mapa}); {sem}")
    print(f"alinha: o webm tem rosto em {tem}s")


# ───────────────────────── a versão do YouTube ─────────────────────────
def _ultima_frase(r: Reel) -> tuple[float, float, float]:
    """Na voz: onde começa a última frase (a chamada), onde acaba a voz antes dela e onde acaba a voz."""
    ws = fala(r)
    pontos = [i for i, w in enumerate(ws) if re.search(r"[.?!]$", w[0])]
    if len(pontos) >= 2:
        k = pontos[-2] + 1
    else:
        # o Whisper às vezes pontua a voz toda com vírgula (o large-v3 no heygen-rosto): o tamanho
        # da última frase sai da narração, que é escrita com ponto
        frases = re.split(r"(?<=[.?!])\s+", r.p.get("narracao", "").strip())
        n = len(frases[-1].split()) if len(frases) >= 2 else 0
        if not 0 < n < len(ws):
            sys.exit("a transcrição da voz não tem ponto antes da última frase, e sem a `narracao` não sei onde ela "
                     "começa: marque o fim da penúltima com um `junta` (ex.: [\"minha,\", \"minha.\"])")
        k = len(ws) - n
    ini = ws[k][1]
    segs = _segmentos(r.voz)
    return ini, max(b for _, b in segs if b <= ini), segs[-1][1]


def _css_yt() -> str:
    """O cartão: a chamada maior, no meio da tela, e embaixo dela a seta em cromo. A seta mora
    dentro da 2ª linha, então chega com ela e leva a mesma sombra."""
    from urllib.parse import quote
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 260"><defs><linearGradient id="c" x2="0" y2="1">'
           '<stop offset=".3" stop-color="#FFFFFF"/><stop offset=".62" stop-color="#D6D8DE"/><stop offset="1" stop-color="#8E939D"/>'
           '</linearGradient></defs><polygon fill="url(#c)" points="58,4 122,4 122,146 174,146 90,254 6,146 58,146"/></svg>')
    return (".ed-v .ed-c1{font-size:150px}.ed-v .ed-c2{font-size:200px}.ed-v:has(.ed-c1){top:860px!important}"
            '.ed-c2::after{content:"";display:block;width:170px;height:245px;margin:48px auto 0;'
            f'background:url("data:image/svg+xml,{quote(svg)}") center/contain no-repeat}}')


def yt(r: Reel) -> Path:
    """No YouTube não há automação de DM: pedir a palavra-chave não tem resposta. O reel até o meio
    do silêncio antes da última frase, e dali o cartão com a chamada do `youtube` sobre o painel,
    com a frase nova (vozes/fim-yt.wav) no lugar da velha e no mesmo tempo dela."""
    y, pasta = r.p["youtube"], r.trab / "yt"
    pasta.mkdir(parents=True, exist_ok=True)
    ini, antes, fim = _ultima_frase(r)
    em = ini - 0.05                                          # a frase nova entra 0,05 s antes da fala dela (o _nivela cortou assim)
    a, b = _fala(r.fim_yt)
    t2 = em + _palavras(r.transcript(r.fim_yt))[-1]["start"]   # a 2ª linha chega com a última palavra
    corte = quadros((antes + ini) / 2) / FPS                  # o rosto sai no meio do silêncio
    dur = quadros(em + b + r.p["dur"] - fim) / FPS            # o mesmo respiro depois da voz que o reel tem
    voz_yt = pasta / "voz.wav"
    ff.run(["ffmpeg", "-y", "-i", str(r.voz), "-i", str(r.fim_yt), "-filter_complex",
            f"[0:a]atrim=0:{em:.3f},afade=t=out:st={em - 0.01:.3f}:d=0.01[a];[a][1:a]concat=n=2:v=0:a=1",
            "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(voz_yt)], quiet=True)
    d = round(dur - corte, 3)
    ed = {"dur": d, "cenas": [[0, d, "tela", y.get("tema", "tinta")]], "fala": [],
          "vozes": [{"t": round(em + a - corte, 3), "t2": round(t2 - corte, 3), "ate": d, "chamada": y["chamada"]}],
          # a folha de estilo entra pelo terminal depois do fim, como no r_editorial
          "graficos": [{"t": d + 1, "ate": d + 2, "g": "term", "linhas": ["<style>" + _css_yt() + "</style>"]}]}
    cartao = pasta / "cartao.mov"
    subprocess.run([PY, str(V2), "render", "e_editorial", f"r={_json(ed)}", *_tema(r), "--out", str(cartao)], check=True)
    img = pasta / "imagem_voz.mp4"
    fs = (f"[0:v]trim=end_frame={quadros(corte)},setpts=PTS-STARTPTS,format={ff.PIX_FMT}[a];[2:v]format={ff.PIX_FMT}[p];"
          # o quadro 0 da render sai sem o `set` do gsap (ver o junta): vira cópia do 1
          f"[1:v]trim=start_frame=1,setpts=PTS-STARTPTS,tpad=start=1:start_mode=clone[c];"
          f"[p][c]overlay=eof_action=pass[k];[a][k]concat=n=2:v=1:a=0,format={ff.PIX_FMT}[v]")
    ff.run(["ffmpeg", "-y", "-i", str(r.trab / "imagem_voz.mp4"), "-i", str(cartao),
            "-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(painel(r, y.get("tema", "tinta"))),
            "-i", str(voz_yt), "-filter_complex", fs, "-map", "[v]", "-map", "3:a", "-t", f"{dur:.3f}",
            *ff.args_video("final"), *ff.args_audio(), str(img)], quiet=True)
    # os efeitos do reel até o corte; o cartão ganha os da chamada velha: whoosh no corte, ding na 2ª linha
    sons = [s for s in r.p.get("sons", []) if s["t"] < corte - 0.05] + [{"tipo": "whoosh", "t": round(corte - 0.02, 2)},
                                                                       {"tipo": "ding", "t": round(t2, 2)}]
    out = _mixa(r, img, sons, voz_yt, pasta, r.trab / "final-yt.mp4")
    folha(r, out, r.trab / "folha-yt.png", 6)
    return out


# ───────────────────────── o plano velho ─────────────────────────
def converte(plano: Path) -> Path:
    """O plano.json dos monta.py (e o roteiro.json ao lado) no formato da fábrica: reel.json na mesma
    pasta. O que é do estilo sai do plano; o que o molde não faz mais é avisado, não levado."""
    import estilo as es
    velho = json.loads(plano.read_text(encoding="utf-8"))
    rot = plano.with_name("roteiro.json")
    rot = json.loads(rot.read_text(encoding="utf-8")) if rot.exists() else {}
    e = es.estilo("reel-editorial")
    novo = {"estilo": "reel-editorial", "slug": plano.parent.name, "fonte": "voz.wav", "trabalho": "_trabalho"}
    if rot.get("narracao"):
        novo["narracao"] = rot["narracao"]
    if rot.get("palavra_dm"):
        novo["palavra"] = rot["palavra_dm"]
    for k in ("dur", "avatar", "base", "junta", "r", "imagens", "pecas", "sons", "capa", "youtube"):
        if k in velho:
            novo[k] = velho[k]
    # no plano velho o webm do avatar às vezes vinha da raiz do repositório; aqui tudo é da pasta do
    # vídeo, e isso vale também pro webm que a HeyGen ainda não gerou (o caminho aponta pra onde ele vai)
    arq = (novo.get("avatar") or {}).get("arquivo")
    if arq and not Path(arq).is_absolute() and not (plano.parent / Path(arq).parts[0]).exists() \
            and ((RAIZ / arq).exists() or (RAIZ / Path(arq).parts[0]).is_dir()):
        try:
            novo["avatar"]["arquivo"] = os.path.relpath(RAIZ / arq, plano.parent)
        except ValueError:      # Windows, plano noutro disco: não existe caminho relativo
            novo["avatar"]["arquivo"] = str(RAIZ / arq)
    avisos = []
    # capturas no formato dos monta.py ({nome: {url, ancora, frase}}) viram os prints do estilo
    cap = {k: v for k, v in (velho.get("capturas") or {}).items() if not k.startswith("_")}
    if "prints" in cap or "logo" in cap:
        novo["capturas"] = cap
    elif cap:
        prints = {n: [c["url"], c["ancora"], c.get("altura", 900), c["frase"], *([c["faixa"]] if "faixa" in c else [])]
                  for n, c in cap.items() if isinstance(c, dict) and {"url", "ancora", "frase"} <= set(c)}
        if prints:
            novo["capturas"] = {"prints": prints}
        for n in set(cap) - set(prints):
            avisos.append(f"`capturas.{n}` não é página pública: o passo captura não faz, e o arquivo pronto "
                          f"vai em _trabalho/cap/{n}.png")
    corrige = {k: v for k, v in (velho.get("corrige") or {}).items() if not k.startswith("_")}
    if corrige:
        novo["junta"] = novo.get("junta", []) + [[k, v] for k, v in corrige.items()]
        avisos.append("o `corrige` virou `junta`, que troca toda ocorrência da palavra: confira a que era só uma")
    css = velho.get("estilo", "")
    for regra in re.findall(r"[^{}]+\{[^}]*\}", CSS):
        css = css.replace(regra, "")
    if css:
        novo["css"] = css
    if velho.get("fundo", {}).get("arquivo"):     # o estilo não tem fundo: o plano diz o dele
        novo["imagem"] = {"fundo": velho["fundo"]["arquivo"]}
    trilha_ = {k: velho["trilha"][k] for k in ("faixa", "pedacos") if k in velho.get("trilha", {})}
    m = velho.get("mixa") or []
    for flag, botao in (("--cama", "cama"), ("--duck-ratio", "duck"), ("--fade-fim", "fade_fim")):
        if flag in m and float(m[m.index(flag) + 1]) != e.eixos["trilha"][botao]:
            trilha_[botao] = float(m[m.index(flag) + 1])
    novo["trilha"] = trilha_
    conhecidos = {"dur", "avatar", "base", "junta", "r", "imagens", "pecas", "sons", "capa", "youtube", "capturas",
                  "corrige", "estilo", "fundo", "trilha", "mixa", "selo", "gancho", "mosaico", "grade", "correcoes",
                  "take", "rosto"}
    for k in sorted(set(velho) - conhecidos):
        if not k.startswith("_"):
            avisos.append(f"`{k}` do plano velho ficou de fora: o estilo não sabe o que é")
    if "selo" in velho:
        avisos.append("o `selo` saiu: sem selo de IA na tela")
    for k in ("gancho", "mosaico", "grade", "correcoes", "take", "rosto"):
        if k in velho or any(k in s for s in velho.get("base", [])):
            avisos.append(f"`{k}` é do molde antigo e o estilo não faz: fica no monta.py daquele vídeo")
    if "capa" in novo and "foto" not in novo["capa"]:
        avisos.append("a `capa` precisa de `foto` (o caminho da foto da pessoa, da pasta do vídeo), e `larg`, `ry`, `iy`")
    if "narracao" not in novo:
        avisos.append("sem `narracao` (o roteiro.json não tem): só faz falta se a voz não existir ainda")
    if "trilha" in velho and "pedacos" not in velho["trilha"] and "faixa" in velho["trilha"]:
        avisos.append("a trilha do plano velho não tem `pedacos`: confira o `trilha` do reel.json")
    out = plano.with_name("reel.json")
    if out.exists():
        sys.exit(f"{out} já existe: não escrevo por cima")
    out.write_text(json.dumps(novo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{out}")
    for a in avisos:
        print(f"  aviso: {a}")
    return out


PASSOS = {"captura": captura, "voz": voz, "yt_voz": yt_voz, "heygen": heygen, "alinha": alinha, "take": take, "pessoa": pessoa,
          "camadas": camadas, "pecas": pecas, "compor": compor, "junta": junta, "degraus": degraus, "som": som, "yt": yt,
          "capa": capa, "folha": folha}


def main() -> None:
    ap = argparse.ArgumentParser(description="O reel editorial, passo a passo (quem chama é a fábrica)")
    ap.add_argument("passo", choices=[*PASSOS, "converte"])
    ap.add_argument("alvo", type=Path, help="a pasta de trabalho (onde a fábrica deixou o reel.json); "
                                            "no `converte`, o plano.json velho")
    a = ap.parse_args()
    if a.passo == "converte":
        converte(a.alvo)
        return
    PASSOS[a.passo](Reel(a.alvo))


if __name__ == "__main__":
    main()
