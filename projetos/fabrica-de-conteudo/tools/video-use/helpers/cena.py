"""Análise de cena: onde a pessoa está e onde a imagem se mexe, linha a linha, ao longo do tempo.

É o que decide onde a legenda pode sentar (`melhor_y`, `linha_do_ombro`) e de onde sai o recorte
do sujeito (`_alfa`, `alfa_do_arquivo`). Saiu do captions_viral, que só a consulta.

Os mapas guardam por CONTEÚDO do trecho, num cache só (`CACHE`): o mesmo trecho, refeito com
instante novo ou em outra pasta, não paga a análise de novo.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import ff

CACHE = Path(os.environ.get("CENA_CACHE") or Path.home() / ".cache" / "obs-optimize" / "cena")


@lru_cache(maxsize=64)
def _resumo(caminho: str, tamanho: int, instante: int) -> str:
    """O resumo do conteúdo do arquivo (o tamanho e o instante só dizem quando calcular de novo).
    ponytail: lê o arquivo inteiro, ~0,1 s a cada 100 MB (o trecho de um bloco); se a legenda passar
    a ler o vídeo longo inteiro, resumir por amostras."""
    h = hashlib.blake2b(digest_size=12)
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 22), b""):
            h.update(bloco)
    return h.hexdigest()


def _guardado(video: Path, *pedido) -> Path:
    st = Path(video).stat()
    chave = hashlib.blake2b(json.dumps([_resumo(str(Path(video).resolve()), st.st_size, st.st_mtime_ns),
                                        *pedido]).encode(), digest_size=12).hexdigest()
    return CACHE / f"{chave}.npy"


def _guarda(alvo: Path, a: np.ndarray) -> None:
    """Escreve e renomeia: duas legendas lendo o mesmo trecho nunca veem o mapa pela metade."""
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_name(f"{alvo.stem}.{os.getpid()}.tmp.npy")
    np.save(tmp, a)
    tmp.replace(alvo)


def mapa_movimento(video: Path, dur: float, largura: int, altura: int,
                   taxa: int = 4, lw: int = 160) -> tuple[np.ndarray, int]:
    """Quanto cada LINHA da imagem se mexe ao longo do tempo.

    Movimento é o sinal certo pra decidir onde o texto não pode sentar: a boca e
    as mãos se mexem, o fundo não. Devolve (n_amostras, lh) e a taxa.
    """
    lh = int(round(lw * altura / largura / 2)) * 2
    guardado = _guardado(video, "movimento", dur, taxa, lw)
    if guardado.exists():
        return np.load(guardado), taxa
    raw = ff.run(
        ["ffmpeg", "-v", "error", "-t", f"{dur}", "-i", str(video),
         "-vf", f"fps={taxa},scale={lw}:{lh},format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture=True, binario=True, quiet=True).stdout
    n = len(raw) // (lw * lh)
    if n < 2:
        return np.zeros((1, lh), dtype=np.float32), taxa
    a = np.frombuffer(raw[:n * lw * lh], np.uint8).reshape(n, lh, lw).astype(np.int16)
    mov = np.abs(np.diff(a, axis=0)).mean(axis=2).astype(np.float32)   # (n-1, lh)
    k = np.ones(7, dtype=np.float32) / 7                               # alisa por linha
    mov = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, mov)
    _guarda(guardado, mov)
    return mov, taxa


def linha_do_ombro(suj: np.ndarray, t_suj: int, t0: float, t1: float,
                   altura: int) -> int:
    """Onde a cabeça acaba e o tronco começa, em px do quadro.

    Legenda por cima do rosto tapa a boca e a expressão — o que se está
    assistindo. Só tela dividida justifica texto em cima. Achar "o mais quieto"
    não basta: em plano fechado o ponto mais quieto é a testa.

    A cabeça é estreita, o ombro é largo. Varrendo de cima, a linha onde a
    largura do sujeito passa de ~1.55x a largura mediana da cabeça é o ombro.
    """
    oc = _janela(suj, t_suj, t0, t1)
    lh = oc.shape[0]
    corpo = np.nonzero(oc > 0.03)[0]
    if corpo.size < 8:
        return int(altura * 0.55)
    topo, base = int(corpo[0]), int(corpo[-1])
    ext = base - topo
    if ext < 8:
        return int(altura * 0.55)

    # Pular a CURVA DO CABELO antes de medir. A largura sobe de 0.02 até o
    # platô da cabeça ao longo do topo; medir a mediana incluindo essa rampa dá
    # um valor baixo demais, o limiar dispara logo abaixo do cocuruto e a
    # legenda volta pro rosto — foi exatamente o que aconteceu.
    a = topo + int(ext * 0.15)
    b = topo + int(ext * 0.45)
    plato = oc[a:max(a + 2, b)]
    plato = plato[plato > 0.03]
    if plato.size < 2:
        return int(altura * 0.55)
    largura_cabeca = float(np.median(plato))
    limite = largura_cabeca * 1.35

    for y in range(b, lh):          # procura a partir do FIM do platô
        if oc[y] >= limite:
            return int(y / lh * altura)
    return int(altura * 0.55)


def _janela(m: np.ndarray, taxa: int, t0: float, t1: float) -> np.ndarray:
    i0 = min(m.shape[0] - 1, max(0, int(t0 * taxa)))
    i1 = min(m.shape[0], max(i0 + 1, int(t1 * taxa)))
    return m[i0:i1].max(axis=0)          # o pior instante do card é quem manda


def melhor_y(suj: np.ndarray, t_suj: int, mov: np.ndarray, t_mov: int,
             t0: float, t1: float, zona: tuple[float, float],
             caixa: int, altura: int) -> tuple[int, float]:
    """y (px, topo da caixa) e quanto dele cai em cima do sujeito (0-1)."""
    lh = suj.shape[1]
    ocup = _janela(suj, t_suj, t0, t1)
    m = _janela(mov, t_mov, t0, t1)
    m = m / (m.max() or 1.0)
    if m.shape[0] != lh:                                    # alinha as resoluções
        m = np.interp(np.linspace(0, 1, lh), np.linspace(0, 1, m.shape[0]), m)

    jan = max(1, int(round(caixa / altura * lh)))
    peso = np.ones(jan, dtype=np.float32)
    custo = np.convolve(ocup * 3.0 + m, peso, "valid")      # sujeito pesa 3x movimento
    ocup_jan = np.convolve(ocup, peso, "valid") / jan
    lo = int(zona[0] * lh)
    hi = min(len(custo), int(zona[1] * lh) - jan + 1)
    if hi <= lo:
        return int(zona[0] * altura), 1.0
    i = lo + int(np.argmin(custo[lo:hi]))
    return int(i / lh * altura), float(ocup_jan[i])


MATTE_PADRAO = "u2net_human_seg"     # 0.4s/frame; birefnet-portrait é 9.6s e limpo
_SESSOES: dict[str, object] = {}


def _sessao(modelo: str):
    if modelo not in _SESSOES:
        from rembg import new_session
        _SESSOES[modelo] = new_session(modelo)
    return _SESSOES[modelo]


def _maior_componente(m: np.ndarray) -> np.ndarray:
    """Só a maior mancha. O u2net confunde pôster com gente — aqui é um estúdio
    com uma máscara do Majora na parede, e ela vira 'sujeito' sem isto."""
    from scipy import ndimage
    lab, n = ndimage.label(m > 128)
    if n < 2:
        return m
    tam = ndimage.sum(m > 128, lab, range(1, n + 1))
    return np.where(lab == int(np.argmax(tam)) + 1, m, 0).astype(np.uint8)


def _alfa(img: Image.Image, modelo: str = MATTE_PADRAO, lado: int = 512) -> np.ndarray:
    """Máscara do sujeito, 0-255, no tamanho da imagem que entrou."""
    from rembg import remove
    w, h = img.size
    p = img.resize((lado, max(2, int(lado * h / w))), Image.BILINEAR)
    m = np.array(remove(p.convert("RGB"), session=_sessao(modelo),
                        only_mask=True, post_process_mask=True))
    m = _maior_componente(m)
    return np.array(Image.fromarray(m).resize((w, h), Image.BILINEAR)
                    .filter(ImageFilter.GaussianBlur(1.5)))


def alfa_do_arquivo(f: Path) -> np.ndarray | None:
    """Alpha que já veio no frame, se houver recorte de verdade.

    Avatar do HeyGen, greenscreen já chavetado, ProRes 4444 — nesses casos a
    silhueta é exata e sai de graça. Rodar rembg em cima seria pagar caro por
    um recorte pior, e foi o que eu quase fiz.
    """
    im = Image.open(f)
    if im.mode != "RGBA":
        return None
    a = np.array(im)[..., 3]
    # alpha tudo-255 é PNG opaco com canal sobrando, não recorte
    if (a < 250).mean() < 0.02:
        return None
    return a


def _alfa_cache(f: Path, cache: Path, modelo: str) -> np.ndarray:
    """Matte por frame com cache em disco — birefnet a 9.6s/frame só é usável
    se re-render não pagar de novo."""
    alvo = cache / f"{f.stem}.png"
    if alvo.exists():
        return np.array(Image.open(alvo))
    a = alfa_do_arquivo(f)
    if a is None:
        a = _alfa(Image.open(f), modelo)
    cache.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(alvo)
    return a


def mapa_sujeito(video: Path, dur: float, largura: int, altura: int,
                 taxa: int = 2, lw: int = 224) -> tuple[np.ndarray, int]:
    """Fração de cada LINHA ocupada pelo sujeito, ao longo do tempo.

    Movimento sozinho não resolve: num plano fechado o olho está parado e ainda
    assim é rosto. Isto sabe onde a pessoa está, não só onde ela se mexe.
    """
    # pelo conteúdo do trecho: o refeito com outra janela da mesma duração pegava o mapa do anterior
    # (a legenda sentava no ombro errado), e o refeito igual, com instante novo, pagava o recorte
    # de novo (25 s no r2-mesa do Treinando #2)
    cache = _guardado(video, "sujeito", dur, taxa, lw, MATTE_PADRAO)
    lh = int(round(lw * altura / largura / 2)) * 2
    if cache.exists():
        return np.load(cache), taxa
    with tempfile.TemporaryDirectory() as td:
        ff.run(
            ["ffmpeg", "-v", "error", "-t", f"{dur}", "-i", str(video),
             "-vf", f"fps={taxa},scale={lw}:{lh}", f"{td}/%05d.png"], quiet=True)
        arq = sorted(Path(td).glob("*.png"))
        if not arq:
            return np.zeros((1, lh), dtype=np.float32), taxa
        oc = np.stack([(_alfa(Image.open(f), lado=lw) > 128).mean(axis=1)
                       for f in arq]).astype(np.float32)
    _guarda(cache, oc)
    return oc, taxa
