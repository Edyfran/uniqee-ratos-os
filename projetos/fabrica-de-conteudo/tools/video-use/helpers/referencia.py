#!/usr/bin/env python3
"""Ler um vídeo de referência e pôr o resultado ao lado dele.

Este helper não decide o que copiar: quem decide é o agente, olhando os quadros. Ele tira o
que se mede (quadros, trocas de imagem, pausas, som) e monta a folha lado a lado.

    referencia.py le <vídeo ou link> -o <pasta> [-n 14]       # quadros, folha e medidas
    referencia.py compara <referência> <final.mp4> -o folha.png [-n 6]
    referencia.py vozes <vídeo> [--pausa 0.2] [--transcript t.json [--alinha t2.json]] [-o janelas.json]
    referencia.py esboco <medidas.json> --cards cards.json -o dividida.json   # o ritmo de layout e de peças da referência, no tamanho do seu vídeo
    referencia.py dividida dividida.json -o final.mp4            # a tela dividida (molde Saraev) sobre o seu vídeo de câmera
    referencia.py presets                                       # as legendas do captions_viral

`le` aceita arquivo ou link que o yt-dlp baixa. Escreve em <pasta>: folha-1.png (e a 2, se
n > 8), plano-longo.png (o maior trecho sem corte, para ver zoom), medidas.json.

`vozes` mede onde há voz no áudio e imprime a lista `janelas` do plano. Com a transcrição, tira a
janela sem palavra; com `--alinha`, grava uma cópia dela com cada palavra dentro de uma janela.

`compara` mostra a referência na fileira de cima e o resultado na de baixo, nos mesmos
instantes relativos (o primeiro é o 0,1 s: o gancho), e imprime as medidas lado a lado, com a
densidade de motion (layout, peças, eventos). Quando o resultado tem menos da metade do motion da
referência, imprime ATENÇÃO: quem entrega diz isso ao usuário, não entrega calado.

O motion também se mede (9:16): `le` classifica cada quadro em rosto cheio, tela dividida (painel em cima, rosto
embaixo) ou tela só de painel, conta as peças (cada conteúdo novo do painel) e os eventos por segundo (cortes, peças
novas e trocas de layout). É o que separa uma referência de rosto com legenda de uma referência com painel e peças.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import ff

LADO = 1568         # a borda longa que o agente lê sem a imagem ser reduzida
PISO_TROCA = 0.04   # o `scene` do ffmpeg abaixo disto é movimento, não troca
PICO = 6            # quantas vezes a mediana dos vizinhos é um pico
JANELA = 0.05       # s por janela de som
PAUSA_MIN = 0.25    # vão menor que isso o ouvido não conta como pausa
POR_FOLHA = 8

# o layout, medido na textura (referencia.py le, `layout`): a faixa de cima (2 a 40% da altura) e a de baixo
# (62 a 98%), cada uma com a fração de pixels de gradiente baixo. Painel (papel, tinta, peça sobre fundo liso) é
# liso; rosto com cenário não é. Medido na referência Saraev: painel em cima 0,74 a 0,98; rosto cheio 0,49 a 0,57
LISO = 1.2          # gradiente (0-255, numa tela de 216×384) abaixo disto é pixel liso
PAINEL = 0.68       # faixa de cima lisa a partir daqui: tem painel em cima
TELA = 0.85         # as duas faixas lisas a partir daqui: a tela é só de painel
LAYOUT_FPS = 15
LAYOUT_MIN = 0.4    # trecho de layout mais curto que isso (s) é ruído de classificação e se junta ao vizinho
PECA_PISO = 0.05    # diferença média (0 a 1) da faixa de cima que conta como peça nova
LAYOUT_MAX_S = 120  # mede só os primeiros 2 minutos


# ---- o vídeo ----------------------------------------------------------------


def baixa(alvo: str, pasta: Path) -> Path:
    """Arquivo que existe vale como está; link o yt-dlp baixa (o `uvx` roda sem instalar nada)."""
    p = Path(alvo).expanduser()
    if p.exists():
        return p
    if not re.match(r"https?://", alvo):
        raise SystemExit(f"não achei o arquivo {alvo}")
    pasta.mkdir(parents=True, exist_ok=True)
    exe = [shutil.which("yt-dlp")] if shutil.which("yt-dlp") else ["uvx", "yt-dlp"]
    try:
        subprocess.run([*exe, "-f", "bv*+ba/b", "--merge-output-format", "mp4", "--no-playlist",
                        "-o", str(pasta / "ref.%(ext)s"), alvo], check=True)
    except FileNotFoundError:
        raise SystemExit("sem o `uvx` nem o `yt-dlp` neste computador: instale o uv, ou mande o vídeo como arquivo")
    except subprocess.CalledProcessError:
        raise SystemExit("o yt-dlp não baixou: post privado, ou que pede login, ou link errado. Mande o vídeo como arquivo")
    achados = sorted(pasta.glob("ref.*"), key=lambda a: a.suffix != ".mp4")
    if not achados:
        raise SystemExit("o yt-dlp não baixou nada: confira o link (post privado ou que pede login não baixa)")
    return achados[0]


def trocas(video: Path) -> list[float]:
    """Os instantes em que a imagem muda de uma vez: corte seco, painel que entra, cena nova.

    Mede a 15 quadros por segundo e conta o pico: a diferença entre dois quadros que passa de
    seis vezes a mediana dos vizinhos (1 s de cada lado). Mão que mexe e peça que desliza dão
    diferença o tempo todo e não são pico; imagem escura marca pouco, por isso o piso baixo."""
    r = ff.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", video, "-an", "-vf",
                "fps=15,scale=320:-2,select='gte(scene,0)',metadata=print:file=-", "-f", "null", "-"],
               capture=True, quiet=True)
    ts = np.array([float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stdout)])
    sc = np.array([float(x) for x in re.findall(r"scene_score=([\d.]+)", r.stdout)])
    achados = []
    for i, s in enumerate(sc):
        viz = np.delete(sc[max(0, i - 15):i + 16], min(i, 15))
        if s >= max(PISO_TROCA, PICO * np.median(viz)) and s >= sc[max(0, i - 2):i + 3].max():
            achados.append(float(ts[i]))
    return achados


def _db(video: Path, janela: float) -> np.ndarray:
    """O nível do áudio (dB) a cada `janela` segundos."""
    r = ff.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                "-f", "s16le", "-"], capture=True, binario=True, quiet=True)
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768
    n = int(16000 * janela)
    k = len(x) // n
    return 20 * np.log10(np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-9)


def _corridas(marca: np.ndarray, janela: float) -> list[list[float]]:
    """[início, fim] em segundos de cada corrida de True."""
    saida, ini = [], None
    for i, m in enumerate(list(marca) + [False]):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            saida.append([ini * janela, i * janela])
            ini = None
    return saida


def som(video: Path) -> dict:
    """Pausas e piso de som, medidos no áudio. `fala` e `piso` são os níveis (dB) que a fala
    e o trecho mais quieto atingem: piso perto da fala é som contínuo sob ela (trilha)."""
    db = _db(video, JANELA)
    if len(db) < 20:
        return {}
    fala, piso = float(np.percentile(db, 90)), float(np.percentile(db, 10))
    vaos = [b - a for a, b in _corridas(db < fala - 22, JANELA) if b - a >= PAUSA_MIN]
    return {"fala_db": round(fala, 1), "piso_db": round(piso, 1),
            "distancia_fala_piso_db": round(fala - piso, 1),
            "som_continuo_sob_a_fala": bool(fala - piso < 22),
            "pausas": len(vaos), "pausas_total_s": round(sum(vaos), 1),
            "maior_pausa_s": round(max(vaos, default=0.0), 1)}


def vozes(video: Path, pausa: float = 0.2, folga: float = 0.06, minimo: float = 0.25,
          transcript: Path | None = None) -> list[list[float]]:
    """Onde há voz, medido no áudio: a lista `janelas` do plano. O Whisper marca o começo da palavra
    dentro do silêncio, e cortar pelo texto guarda esse silêncio na emenda; a janela vem da energia.
    Vão menor que `pausa` não separa duas vozes; cada voz leva `folga` de cada lado. Com a
    transcrição, a janela sem nenhuma palavra por perto (a 0,5 s) é respiração ou ruído e cai."""
    db = _db(video, 0.01)
    corridas = _corridas(db >= np.percentile(db, 90) - 22, 0.01)
    juntas: list[list[float]] = []
    for a, b in corridas:
        if juntas and a - juntas[-1][1] < pausa:
            juntas[-1][1] = b
        else:
            juntas.append([a, b])
    if transcript:
        ws = [w for w in json.loads(transcript.read_text(encoding="utf-8")).get("words", []) if w.get("type") == "word"]
        juntas = [[a, b] for a, b in juntas if any(w["start"] < b + 0.5 and w["end"] > a - 0.5 for w in ws)]
    dur = len(db) * 0.01
    return [[round(max(0.0, a - folga), 2), round(min(dur, b + folga), 2)] for a, b in juntas if b - a >= minimo]


def alinha(transcript: dict, janelas: list[list[float]], alcance: float = 0.6) -> dict:
    """A transcrição com cada palavra dentro de uma janela de voz. O Whisper põe o começo da palavra
    antes da voz, e com `janelas` essa palavra cai fora do corte: some da legenda e a janela some
    com ela. A palavra a até `alcance` s de uma janela encosta nela (com 0,15 s); a que está longe
    de toda voz fica como está, e o corte a tira."""
    saida, cursor = [], 0.0
    for w in transcript["words"]:
        if w.get("type") != "word":
            saida.append(w)
            continue
        a, b = float(w["start"]), float(w["end"])
        meio = (a + b) / 2
        dentro = [j for j in janelas if j[0] <= meio <= j[1]]
        if not dentro:
            perto = min(janelas, key=lambda j: min(abs(meio - j[0]), abs(meio - j[1])), default=None)
            if perto and min(abs(meio - perto[0]), abs(meio - perto[1])) <= alcance:
                curto = min(b - a, 0.15)
                if meio < perto[0]:
                    a = max(perto[0], cursor)
                    b = a + curto
                else:
                    b = perto[1]
                    a = b - curto
        saida.append({**w, "start": round(a, 3), "end": round(b, 3)})
        cursor = max(cursor, b)
    return {**transcript, "words": saida}


def quadro(video: Path, t: float, largura: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "q.png"
        ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", video,
                "-frames:v", "1", "-vf", f"scale={largura}:-2", png], quiet=True)
        return Image.open(png).convert("RGB")


def _cinza(video: Path, fps: int = LAYOUT_FPS, w: int = 216, h: int = 384) -> np.ndarray:
    """Os quadros em cinza, pequenos, a `fps`: o que o layout e as peças medem (só os primeiros LAYOUT_MAX_S s)."""
    r = ff.run(["ffmpeg", "-v", "error", "-t", str(LAYOUT_MAX_S), "-i", video, "-an", "-vf",
                f"fps={fps},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
               capture=True, binario=True, quiet=True)
    x = np.frombuffer(r.stdout, np.uint8)
    n = len(x) // (w * h)
    return x[:n * w * h].reshape(n, h, w).astype(np.float32)


def _liso(f: np.ndarray, a: float, b: float) -> tuple[np.ndarray, np.ndarray]:
    """Por quadro: a fração de pixels lisos (gradiente abaixo de LISO) na faixa de a a b da altura, e o brilho médio dela."""
    s = f[:, int(f.shape[1] * a):int(f.shape[1] * b), :]
    gx = np.abs(np.diff(s, axis=2))[:, :-1, :]
    gy = np.abs(np.diff(s, axis=1))[:, :, :-1]
    return (np.maximum(gx, gy) < LISO).mean((1, 2)), s.mean((1, 2))


def _pico(d: np.ndarray, piso: float) -> list[int]:
    """Os índices em que a série passa de `PICO` vezes a mediana dos vizinhos (e do `piso`): o mesmo critério do `trocas`."""
    achados = []
    for i, s in enumerate(d):
        viz = np.delete(d[max(0, i - 15):i + 16], min(i, 15))
        if s >= max(piso, PICO * np.median(viz)) and s >= d[max(0, i - 2):i + 3].max():
            achados.append(i)
    return achados


def _trechos(cls: np.ndarray, fps: int) -> list[list]:
    """Corridas de classe (índices), sem as menores que LAYOUT_MIN: a curta se junta à vizinha maior."""
    corridas: list[list[int]] = []
    for i, c in enumerate(cls):
        if corridas and corridas[-1][2] == c:
            corridas[-1][1] = i + 1
        else:
            corridas.append([i, i + 1, int(c)])
    while len(corridas) > 1:
        curta = min(range(len(corridas)), key=lambda k: corridas[k][1] - corridas[k][0])
        if corridas[curta][1] - corridas[curta][0] >= LAYOUT_MIN * fps:
            break
        viz = [k for k in (curta - 1, curta + 1) if 0 <= k < len(corridas)]
        k = max(viz, key=lambda k: corridas[k][1] - corridas[k][0])
        corridas[k][0], corridas[k][1] = min(corridas[k][0], corridas[curta][0]), max(corridas[k][1], corridas[curta][1])
        corridas.pop(curta)
        for j in range(len(corridas) - 1, 0, -1):    # as vizinhas da mesma classe viram uma
            if corridas[j][2] == corridas[j - 1][2]:
                corridas[j - 1][1] = corridas[j][1]
                corridas.pop(j)
    return corridas


# a classe de cada quadro: 0 rosto cheio · 1 dividida clara · 2 dividida de tinta · 3 tela clara · 4 tela de tinta
NOMES = ("cheio", "dividida", "dividida", "tela", "tela")
TEMAS = (None, "claro", "tinta", "claro", "tinta")


def layout(video: Path, trocas_: list[float], dur: float) -> dict:
    """O layout e as peças, medidos nos quadros (9:16). Cada quadro é rosto cheio, tela dividida (painel liso em cima
    e rosto embaixo, o molde Saraev) ou tela só de painel; `layout_trechos` guarda [de, até, nome, tema, [instantes de
    peça nova]]. Peça = um conteúdo do painel: uma por trecho de painel, mais uma a cada troca brusca da faixa de cima
    dentro dele (a 0,25 s das bordas do trecho). Evento = corte, peça nova ou troca de layout (juntos a 0,25 s)."""
    f = _cinza(video)
    if len(f) < LAYOUT_FPS:
        return {}
    topo, brilho = _liso(f, 0.02, 0.40)
    base, _ = _liso(f, 0.62, 0.98)
    painel = np.where((topo >= TELA) & (base >= TELA), 3, np.where((topo >= PAINEL) & (base < TELA), 1, 0))
    cls = painel + ((brilho < 100) & (painel > 0)).astype(int)    # o painel escuro (a tinta) ou o claro (o papel): troca de tema é troca de cena
    cls = np.array([np.bincount(cls[max(0, i - 2):i + 3], minlength=5).argmax() for i in range(len(cls))])
    corridas = _trechos(cls, LAYOUT_FPS)
    d = np.abs(np.diff(f[:, int(f.shape[1] * .02):int(f.shape[1] * .40), :], axis=0)).mean((1, 2)) / 255
    picos = [(i + 1) / LAYOUT_FPS for i in _pico(d, PECA_PISO)]
    trechos, pecas, novas = [], 0, []
    for a, b, c in corridas:
        t0, t1 = a / LAYOUT_FPS, b / LAYOUT_FPS
        dentro = [round(t, 2) for t in picos if t0 + 0.25 < t < t1 - 0.25] if c else []
        trechos.append([round(t0, 2), round(t1, 2), NOMES[c], TEMAS[c], dentro])
        pecas += (1 + len(dentro)) if c else 0
        novas += ([t0] if c else []) + dentro
    tempo = len(f) / LAYOUT_FPS
    por = {n: round(sum(t[1] - t[0] for t in trechos if t[2] == n) / tempo, 2) for n in NOMES}
    eventos: list[float] = []
    for t in sorted([*trocas_, *novas, *[tr[0] for tr in trechos[1:]]]):
        if not eventos or t - eventos[-1] > 0.25:
            eventos.append(t)
    dur = dur or tempo
    return {"layout": por, "layout_trechos": trechos, "trocas_de_layout": len(trechos) - 1,
            "pecas": pecas, "pecas_por_s": round(pecas / dur, 2), "cobertura_de_pecas": round(por["dividida"] + por["tela"], 2),
            "eventos": len(eventos), "eventos_por_s": round(len(eventos) / dur, 2)}



def medidas(video: Path) -> dict:
    s = ff.probe(video)
    ts = trocas(video)
    cantos = [0.0, *ts, s.duracao]
    planos = [b - a for a, b in zip(cantos, cantos[1:])]
    i = planos.index(max(planos))
    q = quadro(video, min(0.1, s.duracao / 2), 360)   # o quadro já vem em pé: o celular grava deitado com rotação
    larg, alt = (s.altura, s.largura) if (q.height > q.width) == (s.largura > s.altura) else (s.largura, s.altura)
    m = {"arquivo": video.name, "largura": larg, "altura": alt, "fps": s.fps,
         "formato": "9:16" if q.height > q.width * 1.6 else "16:9" if q.width > q.height * 1.6 else "outro",
         "duracao_s": round(s.duracao, 1), "trocas": len(ts),
         "trocas_por_s": round(len(ts) / s.duracao, 2) if s.duracao else 0,
         "plano_mais_longo": [round(cantos[i], 1), round(cantos[i + 1], 1)],
         "tempos_das_trocas": [round(t, 1) for t in ts]}
    if m["formato"] == "9:16":
        m |= layout(video, ts, s.duracao)
    if s.tem_audio:
        m |= som(video)
        try:
            m["lufs"] = round(ff.lufs(video), 1)
        except Exception:  # medir o loudness é um extra: sem ele a leitura segue
            pass
    return m


# ---- a folha ----------------------------------------------------------------


def _fonte(tam: int):
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:  # Pillow antigo: sem tamanho
        return ImageFont.load_default()


def tempos(dur: float, n: int) -> list[float]:
    """O gancho (0,1 s) e o resto espalhado pelo vídeo."""
    return [min(0.1, dur / 2)] + [dur * (i + 0.5) / (n - 1) * 0.98 for i in range(n - 1)]


def folha(tiles: list[tuple[Image.Image, str]], cols: int, saida: Path) -> Path:
    """Grade de quadros com o rótulo numa tira em cima de cada um."""
    tw = tiles[0][0].width
    alt = 26
    linhas = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    hs = [max(t.height for t, _ in ln) + alt for ln in linhas]
    img = Image.new("RGB", (cols * tw, sum(hs)), (16, 16, 16))
    d, y, fonte = ImageDraw.Draw(img), 0, _fonte(18)
    for ln, h in zip(linhas, hs):
        for j, (t, rotulo) in enumerate(ln):
            d.text((j * tw + 6, y + 3), rotulo, fill=(255, 220, 80), font=fonte)
            img.paste(t, (j * tw, y + alt))
        y += h
    img.save(saida)
    return saida


# ---- os comandos ------------------------------------------------------------


def le(alvo: str, pasta: Path, n: int) -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    video = baixa(alvo, pasta)
    m = {"video": str(video), **medidas(video)}
    dur = m["duracao_s"]
    por_folha = POR_FOLHA if m["formato"] == "9:16" else 12
    cols = 4
    marcas = tempos(dur, n)
    tw = LADO // cols
    tiles = [(quadro(video, t, tw), f"{t:.1f}s") for t in marcas]
    m["folhas"] = [folha(tiles[i:i + por_folha], cols, pasta / f"folha-{i // por_folha + 1}.png").name
                   for i in range(0, len(tiles), por_folha)]
    a, b = m["plano_mais_longo"]
    if b - a >= 1.0:   # o mesmo trecho em seis quadros: zoom lento aparece aqui e não na folha
        seis = [a + 0.1 + (b - a - 0.2) * i / 5 for i in range(6)]
        folha([(quadro(video, t, 260), f"{t:.1f}s") for t in seis], 6, pasta / "plano-longo.png")
        m["plano_longo_png"] = "plano-longo.png"
    (pasta / "medidas.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def compara(ref: Path, final: Path, saida: Path, n: int) -> dict:
    mr, mf = medidas(ref), medidas(final)
    tw = 300
    tiles = [(quadro(v, t, tw), f"{nome} {t:.1f}s")
             for nome, v, m in (("REF", ref, mr), ("SEU", final, mf)) for t in tempos(m["duracao_s"], n)]
    folha(tiles, n, saida)   # n colunas: a referência é a fileira de cima
    return {"ref": mr, "seu": mf}


def _pct(m: dict, k: str = "layout") -> str:
    L = m.get(k)
    return " · ".join(f"{L[n] * 100:.0f}%" for n in ("cheio", "dividida", "tela")) if L else "-"


def tabela(mr: dict, mf: dict) -> str:
    linhas = [("formato", "formato"), ("duração (s)", "duracao_s"), ("fps", "fps"),
              ("trocas de imagem", "trocas"), ("trocas por s", "trocas_por_s"),
              ("plano mais longo", "plano_mais_longo"), ("pausas", "pausas"),
              ("pausas, total (s)", "pausas_total_s"), ("maior pausa (s)", "maior_pausa_s"),
              ("som contínuo sob a fala", "som_continuo_sob_a_fala"),
              ("distância fala-piso (dB)", "distancia_fala_piso_db"), ("loudness (LUFS)", "lufs")]
    out = [f"{'':30}{'REF':>20}{'SEU':>20}"]
    for rotulo, k in linhas:
        out.append(f"{rotulo:30}{str(mr.get(k, '-')):>20}{str(mf.get(k, '-')):>20}")
    # o motion: o layout (rosto cheio · tela dividida · só painel), as peças e os eventos
    out.append(f"{'layout (cheio·dividida·tela)':30}{_pct(mr):>20}{_pct(mf):>20}")
    for rotulo, k in (("peças (painéis)", "pecas"), ("peças por s", "pecas_por_s"), ("trocas de layout", "trocas_de_layout"),
                      ("eventos de motion por s", "eventos_por_s")):
        out.append(f"{rotulo:30}{str(mr.get(k, '-')):>20}{str(mf.get(k, '-')):>20}")
    out.append(f"{'tempo com painel':30}{str(mr.get('cobertura_de_pecas', '-')):>20}{str(mf.get('cobertura_de_pecas', '-')):>20}")
    return "\n".join(out)


def veredito(mr: dict, mf: dict) -> list[str]:
    """O motion do resultado contra o da referência. Vazio quando bate, ou quando a referência não tem painel (nada a copiar);
    com diferença grande, as linhas que dizem qual (a primeira começa por ATENÇÃO). Quem entrega não entrega calado."""
    if "layout" not in mr or "layout" not in mf and mf.get("formato") == "9:16":
        return []
    cr, cf = mr.get("cobertura_de_pecas", 0), mf.get("cobertura_de_pecas", 0)
    pr, pf = mr.get("pecas_por_s", 0), mf.get("pecas_por_s", 0)
    er, ef = mr.get("eventos_por_s", 0), mf.get("eventos_por_s", 0)
    achados = []
    if cr >= 0.25 and cf < cr * 0.5:
        achados.append(f"layout: a referência tem painel em {cr * 100:.0f}% do tempo (tela dividida ou só painel), o resultado em {cf * 100:.0f}%")
    if pr >= 0.2 and pf < pr * 0.5:
        achados.append(f"peças: {pr:.2f} por s na referência, {pf:.2f} no resultado")
    if er >= 0.3 and ef < er * 0.6:
        achados.append(f"eventos de motion: {er:.2f} por s na referência, {ef:.2f} no resultado")
    if achados:
        achados.insert(0, "ATENÇÃO: o resultado tem bem menos motion que a referência. Diga isso ao usuário, ou refaça no layout dela "
                          "(`referencia.py esboco` e `dividida`):")
    return achados


# ---- a tela dividida: o layout e as peças da referência, no seu vídeo -----------

V2 = Path(__file__).resolve().parents[2] / "v2" / "v2.py"
GRAFICOS = ("mascote", "term", "fluxo", "pagina", "lista", "email")      # os `g` da peça e_editorial


def fala_de(arq: Path) -> list[list]:
    """As palavras com tempo, [[palavra, de, até]], de um `cards.json` (a legenda da fábrica, no tempo do vídeo cortado)
    ou de uma transcrição (campo `words`). A e_editorial desenha a fala na tela com elas."""
    j = json.loads(arq.read_text(encoding="utf-8"))
    if "cards" in j:
        return [[w["tx"], round(w["t0"], 3), round(w["t1"], 3)] for c in j["cards"] for w in c["words"]]
    return [[w["text"], round(w["start"], 3), round(w["end"], 3)] for w in j["words"] if w.get("type", "word") == "word"]


def esboco(m: dict, fala: list[list], dur: float) -> dict:
    """O ritmo de layout e de peças da referência (`layout_trechos` do `le`), esticado ao tamanho do seu vídeo, com cada
    borda de cena caindo no fim de uma palavra (a cena troca no fim da frase, não no meio dela). Sai o plano da
    `dividida` com as cenas prontas e as peças como vagas: o agente preenche cada `g` com o que o usuário disse (e só
    com isso: nada do conteúdo da referência vai pro final)."""
    if "layout_trechos" not in m:
        raise SystemExit("a leitura não tem `layout_trechos`: rode `referencia.py le` de novo (e só 9:16 tem layout)")
    k = dur / m["duracao_s"]
    fins = sorted({w[2] for w in fala})

    def prende(t: float, perto: float = 0.45) -> float:
        c = min(fins, key=lambda x: abs(x - t), default=t)
        return round(c if abs(c - t) <= perto else t, 2)

    tr = m["layout_trechos"]
    bordas = [0.0, *[prende(t[1] * k) for t in tr[:-1]], round(dur, 2)]
    for i in range(1, len(bordas)):                      # cada cena com 0,5 s pelo menos, em ordem
        bordas[i] = round(max(bordas[i], bordas[i - 1] + 0.5), 2)
    bordas[-1] = round(max(bordas[-1], bordas[-2] + 0.5), 2)
    cenas, graficos, zoom = [], [], iter([1.08, 1.18, 1.1] * 4)
    for i, (t0, t1, nome, tema, dentro) in enumerate(tr):
        de, ate = bordas[i], bordas[i + 1]
        if nome == "cheio":
            cenas.append([de, ate, "rosto", None, next(zoom)])
            continue
        cenas.append([de, ate, "split" if nome == "dividida" else "tela", tema or "claro"])
        cortes = [de, *[c for c in (prende(p * k) for p in dentro) if de + 0.4 < c < ate - 0.4], ate]
        for a, b in zip(cortes, cortes[1:]):
            dito = " ".join(w[0] for w in fala if a - 0.05 <= w[1] < b)
            graficos.append({"t": a, "ate": b, "g": "?", "_preencher": f"uma peça de {GRAFICOS} com o que ele diz aqui: {dito}"})
    return {"take": "", "fala_de": "", "dur": round(dur, 2), "marca": "robo", "cartao": {"escala": 0.967, "topo": 413},
            "cenas": cenas, "graficos": graficos, "vozes": []}


def confere_plano(p: dict) -> list[str]:
    """O que impede a `dividida`: peça sem preencher, `g` que a e_editorial não conhece, peça fora de uma cena de painel."""
    erros = []
    for g in p.get("graficos", []):
        if "_preencher" in g or g.get("g") not in GRAFICOS:
            erros.append(f"gráfico em {g.get('t')}s sem preencher: {g.get('_preencher') or 'g = ' + repr(g.get('g'))}")
    paineis = [(c[0], c[1]) for c in p.get("cenas", []) if c[2] in ("split", "tela")]
    for g in p.get("graficos", []):
        if not any(a - 0.05 <= g.get("t", 0) < b for a, b in paineis):
            erros.append(f"gráfico em {g.get('t')}s fora de uma cena split ou tela: não aparece")
    cenas = p.get("cenas", [])
    for (a0, a1, *_), (b0, *_) in zip(cenas, cenas[1:]):
        if abs(a1 - b0) > 0.02:
            erros.append(f"cena que acaba em {a1}s e a próxima que começa em {b0}s: buraco ou sobreposição")
    if not cenas:
        erros.append("sem cenas")
    return erros


def r_do_plano(p: dict, base: Path) -> dict:
    """O `r` da e_editorial: o plano sem o que é do helper (take, fala_de), com a fala vinda do arquivo."""
    r = {k: v for k, v in p.items() if k not in ("take", "fala_de", "trabalho")}
    r["fala"] = p.get("fala") or fala_de((base / p["fala_de"]).resolve())
    r.setdefault("dur", round(ff.dur((base / p["take"]).resolve()), 2))
    return r


def dividida(plano: Path, saida: Path, trabalho: Path | None = None) -> Path:
    """O layout Dividida (a e_editorial: painel em cima com as peças, o take num cartão de cantos redondos embaixo, a
    cabeça passando da borda) sobre o seu take de câmera. O take é o vídeo já cortado (a fábrica, sem a legenda): o recorte
    da pessoa sai dele (Vision da Apple, macOS), as camadas saem da peça, e o compor monta tudo."""
    p = json.loads(plano.read_text(encoding="utf-8"))
    base = plano.parent
    erros = confere_plano(p)
    if erros:
        raise SystemExit("o plano da dividida não está pronto:\n  " + "\n  ".join(erros))
    take = (base / p["take"]).resolve()
    trab = trabalho or saida.parent / f"{saida.stem}_trabalho"
    trab.mkdir(parents=True, exist_ok=True)
    r = json.dumps(r_do_plano(p, base), ensure_ascii=False, separators=(",", ":"))
    subprocess.run([sys.executable, str(V2), "camadas", "e_editorial", f"r={r}", "--out", str(trab / "ed")], check=True)
    cmd = [sys.executable, str(V2), "compor", "--take", str(take), "--peca", str(trab / "ed.json"), "--em", "0", "--folga", "1",
           "--out", str(saida)]
    if shutil.which("swiftc"):
        from reel_editorial import recorta     # a cabeça sobre o cartão: o recorte é do Vision, só macOS
        cmd += ["--pessoa", str(recorta(take, trab / "pessoa.mov", round(r_dur(p, take) * ff.FPS)))]
    else:
        print("sem swiftc (só macOS): o take entra no cartão sem a cabeça passando da borda")
    subprocess.run(cmd, check=True)
    saida.with_suffix(".cues.json").unlink(missing_ok=True)
    return saida


def r_dur(p: dict, take: Path) -> float:
    return float(p.get("dur") or ff.dur(take))


def presets() -> str:
    from captions_viral import FONTES, PRESETS
    return "\n".join([f"{nome:15}{p.get('fonte', 'creato'):12}{p.get('caixa', 'alta'):9}"
                      f"{p.get('palavras', '-')!s:>3} pal  {p.get('uso', '')}" for nome, p in PRESETS.items()]
                     + ["", "letras (desenho.fonte): " + ", ".join(n for n, f in FONTES.items() if Path(f[0]).exists())])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("le")
    a.add_argument("alvo")
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("-n", type=int, default=14)
    c = sub.add_parser("compara")
    c.add_argument("ref", type=Path)
    c.add_argument("final", type=Path)
    c.add_argument("-o", "--out", type=Path, required=True)
    c.add_argument("-n", type=int, default=6)
    e = sub.add_parser("esboco")
    e.add_argument("medidas", type=Path, help="o medidas.json do `le`")
    e.add_argument("--cards", type=Path, required=True, help="a legenda do seu vídeo (cards.json) ou a transcrição, no tempo do vídeo cortado")
    e.add_argument("--take", type=Path, required=True, help="o seu vídeo já cortado, sem legenda")
    e.add_argument("-o", "--out", type=Path, required=True)
    d = sub.add_parser("dividida")
    d.add_argument("plano", type=Path)
    d.add_argument("-o", "--out", type=Path, required=True)
    d.add_argument("--trabalho", type=Path)
    v = sub.add_parser("vozes")
    v.add_argument("video", type=Path)
    v.add_argument("--pausa", type=float, default=0.2, help="vão (s) que separa duas vozes")
    v.add_argument("--transcript", type=Path, help="a transcrição do vídeo: tira a janela sem palavra")
    v.add_argument("--alinha", type=Path, help="com a transcrição: grava aqui a cópia com as palavras dentro das janelas")
    v.add_argument("-o", "--out", type=Path)
    sub.add_parser("presets")
    x = ap.parse_args()
    if x.cmd == "presets":
        print(presets())
    elif x.cmd == "esboco":
        plano = esboco(json.loads(x.medidas.read_text(encoding="utf-8")), fala_de(x.cards), ff.dur(x.take))
        plano["take"] = os.path.relpath(x.take, x.out.parent)
        plano["fala_de"] = os.path.relpath(x.cards, x.out.parent)
        x.out.write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"esboço: {x.out}  ({len(plano['cenas'])} cenas, {len(plano['graficos'])} peças a preencher)")
    elif x.cmd == "dividida":
        print(f"dividida: {dividida(x.plano, x.out, x.trabalho)}")
    elif x.cmd == "vozes":
        j = vozes(x.video, x.pausa, transcript=x.transcript)
        print(json.dumps(j))
        if x.out:
            x.out.write_text(json.dumps(j), encoding="utf-8")
        if x.alinha:
            if not x.transcript:
                raise SystemExit("--alinha pede a --transcript")
            doc = alinha(json.loads(x.transcript.read_text(encoding="utf-8")), j)
            x.alinha.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"transcrição alinhada: {x.alinha}")
    elif x.cmd == "le":
        m = le(x.alvo, x.out, max(2, x.n))
        print(json.dumps(m, ensure_ascii=False, indent=1))
    else:
        r = compara(x.ref, x.final, x.out, max(2, x.n))
        print(tabela(r["ref"], r["seu"]))
        ver = veredito(r["ref"], r["seu"])
        if ver:
            print("\n" + "\n".join(ver[:1] + [f"  - {l}" for l in ver[1:]]))
        print(f"\nfolha: {x.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
