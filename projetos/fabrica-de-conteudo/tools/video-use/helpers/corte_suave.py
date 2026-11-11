"""Corte suave: a emenda de um corte de fala que o olho não percebe.

O corte seco de uma hesitação ("ééé", uma pausa) pula a cabeça e a boca de um pose para outro.
O corte suave faz quatro coisas, e as quatro foram aprovadas juntas (X2, 12/10/2026):

  1. acha o ponto de corte: em ±3 quadros do silêncio, o par A/B em que o rosto e a boca mais se parecem;
  2. põe N=3 quadros que o interpolador da Apple (VTFrameRateConversion) inventa entre A e B;
  3. dá um zoom em ~0,4 s que esconde o que sobrou. Ele VARIA a cada emenda (dono, 13/10): entra ou sai,
     de 1,04 a 1,15, nunca igual ao da emenda anterior, centrado no rosto (Vision) ou, quando uma peça
     ocupa um lado (`zoom_lados` do EDL), empurrando o rosto pro lado livre: esse começa quando a peça
     entra e acaba quando ela sai (rampas de 0,35 s), não na emenda;
  4. cobre a emenda do som com o ruído do quarto (sem buraco de −80 dB).

Só vale para emenda entre dois trechos do MESMO bruto. O critério é medido: se a diferença de luma entre
A e B passa de `LIMITE`, o interpolador inventaria um fantasma, e a emenda fica seca (com o zoom e o
ruído de sala). Sem o interpolador (outro sistema, outro chip, macOS antigo) tudo cai nesse mesmo caminho.

Dois tempos, ligados no render.py pela chave `"corte_suave": true` do EDL:
  `planeja` + `ajusta`  antes de extrair: mede cada emenda e move o ponto de corte (a duração do trecho não
                        muda: o par anda junto, então cada palavra continua no mesmo segundo do vídeo);
  `aplica`              depois de extrair: troca os quadros da emenda pelos interpolados, põe o zoom e a
                        cama de som, trecho por trecho. O som de cada trecho fica onde estava: a imagem
                        anda N/2 quadros pra cada lado da emenda, nunca mais que isso.

O lado Apple mora em corte_suave.swift, compilado na primeira vez com swiftc e guardado em cache.
"""
from __future__ import annotations

import hashlib
import os
import random
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

import ff

N = 3                    # quadros inventados por emenda
LIMITE = 10.0            # diferença de luma A×B (0–255) a partir da qual a emenda fica seca
BUSCA = 3                # o ponto de corte anda até ±3 quadros
PUNCH = 0.06             # o zoom antigo (fixo): ainda é o que `zoom=True` pede ao _retoca
PUNCH_S = 0.4            # o zoom antigo leva 0,4 s, freando no fim (só o `Zoom()` sem argumento; emenda não usa mais)
EMENDA_S = 1.8           # o zoom que esconde emenda é LENTO (≥1,5 s), entra e sai suave: chicote toda hora o dono reprovou (14/10)
CADA = 3                 # e só em 1 de cada 3 emendas; as outras se escondem só pela ponte
MOTIVO_MIN, MOTIVO_MAX = 0.8, 3.0   # o zoom com motivo (jogada decisiva) anda de 0,8 a 3 s: devagar, pra pesar
FORCAS = (0.04, 0.06, 0.08, 0.10, 0.12, 0.15)   # leve (1,04) a forte (1,15)
PECA_S = 0.35            # zoom com peça: entra em t0 e sai em t1 da peça, cada rampa em ~0,35 s (curta, sem chicote)
DEGRAU_S = 0.12         # o zoom em degraus (`zoom_degraus`) sobe cada degrau em ~0,12 s: um empurrão leve, sem chicote
MIN_PECA = 0.1           # peça que toca menos que isso de um trecho não mexe no zoom dele
FORTES = (0.10, 0.12, 0.15)                     # o que empurra o rosto pro lado: precisa de folga pra cortar
LUGAR_DO_ROSTO = 0.70    # com peça num lado, o rosto vai pra 70% (ou 30%) da largura, até onde o zoom deixa
MIN_SOBRA = 0.5          # peça que cobre menos que isso do trecho não conta
CAMA_S = 0.5             # a cama de ruído de sala dura meio segundo, centrada na emenda
MIN_TRECHO = 0.5         # trecho mais curto que isso não leva emenda
BOCA = 300               # peso da boca aberta no placar do ponto (medido no teste de 12/10)
TRABALHADORES = 4

FONTE = Path(__file__).with_name("corte_suave.swift")


# -------- o lado Apple -------------------------------------------------------


def binario() -> Path | None:
    """O executável do Swift, compilado uma vez por versão do fonte. None onde não há swiftc."""
    if sys.platform != "darwin" or not shutil.which("swiftc") or not FONTE.exists():
        return None
    exe = Path(tempfile.gettempdir()) / f"corte_suave-{hashlib.md5(FONTE.read_bytes()).hexdigest()[:8]}"
    if not exe.exists():
        tmp = exe.with_suffix(f".{os.getpid()}")
        r = subprocess.run(["swiftc", "-O", str(FONTE), "-o", str(tmp)], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            tmp.unlink(missing_ok=True)
            return None
        os.replace(tmp, exe)             # dois processos compilando juntos: o último a chegar vale
    return exe


_SUPORTE: tuple[bool, str] | None = None


def suporte() -> tuple[bool, str]:
    """(há interpolador aqui?, por que não). Compila e pergunta ao sistema: macOS 26 num chip Apple."""
    global _SUPORTE
    if _SUPORTE is None:
        if sys.platform != "darwin":
            _SUPORTE = (False, "o interpolador é do macOS")
        elif (exe := binario()) is None:
            _SUPORTE = (False, "sem swiftc (ou o macOS não tem a API: precisa do 26)")
        elif subprocess.run([str(exe), "suporte"], capture_output=True).returncode != 0:
            _SUPORTE = (False, "este chip não tem o interpolador de quadros")
        else:
            _SUPORTE = (True, "")
    return _SUPORTE


def decide(dif: float) -> bool:
    """O critério: a diferença de luma entre A e B abaixo do limite liga o interpolador."""
    return dif < LIMITE


# -------- as emendas ---------------------------------------------------------


@dataclass
class Emenda:
    i: int                    # a emenda entre o trecho i e o i+1 do EDL
    fonte: str                # o bruto (caminho resolvido)
    fim: float                # onde o trecho i acaba no bruto, já com o ponto movido
    ini: float                # onde o trecho i+1 recomeça
    passo: int = 0            # quadros que o par andou (positivo = mais tarde)
    dif: float = 0.0          # diferença de luma A×B no par escolhido
    placar: tuple[float, float] | None = None   # (placar do ponto nominal, do escolhido); None sem rosto
    sala: float | None = None  # onde, no bruto, está o ruído de sala que cobre a emenda
    suave: bool = False       # interpolador ligado nesta emenda
    motivo: str = ""          # por que ficou seca, quando ficou


def candidatas(edl: dict) -> list[int]:
    """Os índices i em que a emenda i→i+1 é um corte de fala dentro do mesmo bruto: trechos normais
    (sem quadro parado nem aceleração, mesmo recorte), o segundo vindo depois do primeiro."""
    rs, saida = edl["ranges"], []
    for i in range(len(rs) - 1):
        a, b = rs[i], rs[i + 1]
        if a["source"] != b["source"] or a.get("recorte") != b.get("recorte"):
            continue
        if any(r.get("congela") or float(r.get("velocidade", 1)) != 1 for r in (a, b)):
            continue
        if float(b["start"]) - float(a["end"]) < 0.05:          # continuação, não corte
            continue
        if min(float(r["end"]) - float(r["start"]) for r in (a, b)) < MIN_TRECHO:
            continue
        saida.append(i)
    return saida


def _cinza(png: Path, tam: tuple[int, int], caixa=None):
    from PIL import Image
    import numpy as np
    im = Image.open(png).convert("L")
    if caixa:
        im = im.crop(caixa)
    return np.asarray(im.resize(tam, Image.BICUBIC), dtype=np.float32)


def diferenca(a: Path, b: Path) -> float:
    """A diferença média de luma entre dois quadros, em escala 192×108 (0–255)."""
    import numpy as np
    return float(np.abs(_cinza(a, (192, 108)) - _cinza(b, (192, 108))).mean())


def _quadros(fonte: Path, t0: float, n: int, fps: int, onde: Path, nome: str) -> list[Path]:
    """`n` quadros do bruto a partir de `t0`, a 960×540, na grade de `fps`."""
    onde.mkdir(parents=True, exist_ok=True)
    ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(t0, 0):.4f}", "-i", str(fonte),
            "-vf", f"fps={fps},scale=960:540", "-frames:v", str(n), str(onde / f"{nome}%d.png")], quiet=True)
    return [onde / f"{nome}{k}.png" for k in range(1, n + 1)]


def _rosto(imgs: list[Path]) -> list[tuple[float, float, float, float, float]]:
    """(x, y, w, h, boca) de cada imagem, ou zeros onde o Vision não vê rosto."""
    exe = binario()
    if exe is None or not imgs:
        return [(0.0,) * 5] * len(imgs)
    r = subprocess.run([str(exe), "rosto", *map(str, imgs)], capture_output=True, text=True, encoding="utf-8")
    linhas = []
    for l in r.stdout.splitlines():
        try:
            v = tuple(float(x) for x in l.split())
        except ValueError:
            continue
        if len(v) == 5:
            linhas.append(v)
    return linhas if len(linhas) == len(imgs) else [(0.0,) * 5] * len(imgs)


def _audio(fonte: Path, t0: float, t1: float):
    import numpy as np
    r = ff.run(["ffmpeg", "-v", "error", "-ss", f"{max(t0, 0):.3f}", "-t", f"{max(t1 - max(t0, 0), 0.1):.3f}",
                "-i", str(fonte), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
               capture=True, binario=True, quiet=True, check=False)
    return np.frombuffer(r.stdout or b"", dtype=np.int16).astype(np.float32), max(t0, 0.0)


JANELA = 1600            # 100 ms a 16 kHz
BIN = 533                # ~33 ms


def _sala(trechos) -> tuple[float | None, float]:
    """O trecho de 100 ms mais quieto que ainda é ruído de quarto (não o silêncio digital do celular,
    abaixo de −55 dBFS). Devolve (segundo no bruto, rms dele) ou (None, 0)."""
    import numpy as np
    piso = (10 ** (-55 / 20) * 32768) ** 2
    melhor = (None, 0.0, float("inf"))
    for audio, t0 in trechos:
        if len(audio) < JANELA:
            continue
        pot = np.convolve(audio * audio, np.ones(JANELA, dtype=np.float32), "valid")[::800] / JANELA
        ok = pot > piso
        if ok.any():
            k = int(np.argmin(np.where(ok, pot, np.inf)))
            if pot[k] < melhor[2]:
                melhor = (t0 + k * 800 / 16000, float(np.sqrt(pot[k])), float(pot[k]))
    return melhor[0], melhor[1]


def _livre(trechos, rms_sala: float, ta: float, tb: float) -> bool:
    """O intervalo [ta, tb] do bruto só tem ruído de quarto (nenhum compasso de 33 ms passa de 12 dB
    sobre a sala)? Mexer o corte por cima de fala cortaria uma palavra."""
    import numpy as np
    lo, hi = min(ta, tb), max(ta, tb)
    if hi - lo < 1e-6:
        return True
    for audio, t0 in trechos:
        if t0 - 1e-3 <= lo and hi <= t0 + len(audio) / 16000 + 1e-3:
            a, b = int((lo - t0) * 16000), int((hi - t0) * 16000) + 1
            seg = audio[a:b]
            for k in range(0, max(len(seg) - BIN + 1, 1), BIN):
                if np.sqrt(np.mean(seg[k:k + BIN] ** 2)) > rms_sala * 4:
                    return False
            return True
    return False


def _uma(edl: dict, i: int, resolve, fps: int, busca: int, pasta: Path) -> Emenda:
    import numpy as np
    a, b = edl["ranges"][i], edl["ranges"][i + 1]
    fonte = Path(resolve(edl["sources"][a["source"]]))
    ea, sb, dt = float(a["end"]), float(b["start"]), 1.0 / fps
    em = Emenda(i, str(fonte), ea, sb)
    onde = pasta / f"e{i}"

    # o som: o ruído do quarto (cobre a emenda) e quais movimentos do ponto não cortam fala
    aud = [_audio(fonte, ea - 6, ea + 0.5), _audio(fonte, sb - 0.5, sb + 6)]
    em.sala, rms = _sala(aud)
    j_ok = [0]
    if busca and em.sala is not None:
        j_ok = [j for j in range(-busca, busca + 1)
                if j == 0 or (_livre(aud, rms, ea, ea + j * dt) and _livre(aud, rms, sb, sb + j * dt))]

    n = 2 * busca + 1
    # O último quadro de A é o que tem carimbo logo antes do corte (ea - dt); o primeiro de B, o de sb.
    qa = _quadros(fonte, ea - (busca + 1) * dt - dt / 2, n, fps, onde, "a")
    qb = _quadros(fonte, sb - busca * dt - dt / 2, n, fps, onde, "b")
    if len(qa) != n or not all(q.exists() for q in qa + qb):
        em.motivo = "não consegui ler os quadros do bruto"
        return em
    m = busca                                           # o índice do quadro nominal (j = 0)

    melhor = 0
    face = _rosto([*qa, *qb]) if busca and len(j_ok) > 1 and binario() else None
    if face and face[m][2] > 0:
        x, y, w, h, _ = face[m]
        caixa = (int(x * 960), int((1 - y - h) * 540), int((x + w) * 960), int((1 - y) * 540))
        ca = [_cinza(q, (64, 64), caixa) for q in qa]
        cb = [_cinza(q, (64, 64), caixa) for q in qb]

        def placar(j: int) -> float:
            return float(np.abs(ca[m + j] - cb[m + j]).mean()) + BOCA * (face[m + j][4] + face[n + m + j][4])

        melhor = min(j_ok, key=lambda j: (placar(j), abs(j)))
        em.placar = (round(placar(0), 2), round(placar(melhor), 2))
    em.passo = melhor
    em.fim, em.ini = ea + melhor * dt, sb + melhor * dt
    em.dif = round(diferenca(qa[m + melhor], qb[m + melhor]), 2)
    return em


def planeja(edl: dict, resolve, fps: int = 30, busca: int = BUSCA) -> list[Emenda]:
    """Mede cada emenda candidata do EDL. `resolve` leva o caminho do EDL ao do arquivo.
    `busca=0` só mede (sem mover o ponto nem olhar o rosto): é o que o `--seco` da fábrica usa."""
    idx = candidatas(edl)
    if not idx:
        return []
    ok, porque = suporte()
    with tempfile.TemporaryDirectory(prefix="corte_suave_") as d, ThreadPoolExecutor(TRABALHADORES) as ex:
        saida = list(ex.map(lambda i: _uma(edl, i, resolve, fps, busca, Path(d)), idx))
    for em in saida:
        if em.motivo:
            continue
        if not ok:
            em.motivo = porque
        elif not decide(em.dif):
            em.motivo = f"diferença {em.dif:.1f} ≥ {LIMITE:g}: o interpolador inventaria um fantasma"
        else:
            em.suave = True
    return saida


def ajusta(edl: dict, emendas: list[Emenda]) -> None:
    """Move o ponto de corte no EDL. O par anda junto, então o trecho que acaba ganha o que o seguinte
    perde: a duração total e o segundo de cada palavra ficam como estavam."""
    for em in emendas:
        if em.passo:
            edl["ranges"][em.i]["end"] = round(em.fim, 4)
            edl["ranges"][em.i + 1]["start"] = round(em.ini, 4)


def resumo(emendas: list[Emenda]) -> str:
    suaves = sum(e.suave for e in emendas)
    return f"{len(emendas)} emendas, {suaves} suaves, {len(emendas) - suaves} secas"


# -------- a emenda: ponte, zoom, cama ---------------------------------------


def _quadro_do(trecho: Path, idx: int, fps: int, destino: Path) -> Path:
    """O quadro `idx` (de 0) do trecho já extraído, em tamanho cheio, sem mexer na cor: o interpolador
    recebe o mesmo quadro que o vizinho tem."""
    antes = min(idx, 15)
    ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(idx - antes - 0.5, 0) / fps:.5f}", "-i", str(trecho),
            "-vf", f"select=eq(n\\,{antes})", "-frames:v", "1", "-fps_mode", "passthrough", str(destino)],
           quiet=True)
    return destino


def _quadros_de(trecho: Path) -> int:
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(trecho)],
               capture=True, quiet=True, check=False)
    return int((r.stdout or "0").strip().split()[0] or 0) if (r.stdout or "").strip() else 0


def _cama(em: Emenda, destino: Path, filtro: str) -> Path | None:
    """O meio segundo de ruído de quarto: 100 ms do bruto em laço, com entrada e saída de 0,1 s."""
    if em.sala is None:
        return None
    af = ",".join(x for x in [
        "aresample=48000", "aloop=loop=6:size=4800", f"atrim=0:{CAMA_S}", "asetpts=PTS-STARTPTS", filtro,
        "afade=t=in:d=0.1", f"afade=t=out:st={CAMA_S - 0.1}:d=0.1"] if x)
    ff.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{em.sala:.3f}", "-t", "0.1", "-i", em.fonte, "-vn",
            "-af", af, "-ac", "2", "-ar", "48000", str(destino)], quiet=True)
    return destino if destino.exists() else None

@dataclass(frozen=True)
class Zoom:
    """O zoom de um trecho: vai de z0 a z1 em PUNCH_S e fica em z1. (fx, fy) é onde o rosto está no quadro
    (fração a partir do canto de cima à esquerda) e lx onde ele deve ficar na tela: lx = fx é o zoom centrado
    no rosto (o rosto não anda), outro lx empurra o rosto pra lá (até onde o recorte deixa)."""
    z0: float = 1.0
    z1: float = 1.0 + PUNCH
    fx: float = 0.5
    fy: float = 0.5
    lx: float | None = None
    dur: float = PUNCH_S      # quanto o zoom leva; o zoom com motivo é mais lento que o que esconde emenda
    ini: float = 0.0          # quando ele começa, em segundos do trecho; o zoom com motivo chega à jogada, não parte do começo
    suave: bool = False       # True = curva S (entra e sai devagar); False = freia no fim
    degraus: tuple = ()       # zoom em degraus: ((a, escala), ...) em segundos do trecho, centrado; sobe a cada `escala` em [a-DEGRAU_S, a]
    janelas: tuple = ()       # zoom com peça: ((a, b), ...) em segundos do trecho (a<0 = a peça já estava; b além do fim = segue).
                              # O zoom sobe a z1 em [a, a+PECA_S] e volta a 1 em [b, b+PECA_S]; fora das janelas, 1.

    @property
    def sentido(self) -> str:
        return "entra" if self.z1 >= self.z0 else "sai"


def varia(n: int, semente: str, lados: list[int] | None = None) -> list[tuple[str, float]]:
    """(sentido, força) do zoom de n trechos seguidos. Nunca o mesmo duas vezes seguidas: o mesmo sentido
    pede força a ≥ 0,03 da anterior. `lados[k]` ≠ 0 = há peça nesse lado, e o trecho entra forte.
    Determinístico pela `semente` (o mesmo bloco renderiza igual)."""
    rng = random.Random(int(hashlib.md5(semente.encode()).hexdigest()[:12], 16))
    lados = lados or [0] * n
    saida: list[tuple[str, float]] = []
    for k in range(n):
        while True:
            if lados[k]:
                s, f = "entra", rng.choice(FORTES)
            else:
                s, f = ("entra" if rng.random() < 0.55 else "sai"), rng.choice(FORCAS)
            ant = saida[-1] if saida else None
            if ant is None or s != ant[0] or abs(f - ant[1]) >= 0.03:
                break
        saida.append((s, f))
    return saida


def motivos_do(edl: dict) -> dict[int, tuple[float, float, float, float]]:
    """{trecho: (t, força, duração, início)} do zoom com motivo: `edl["zoom_motivo"]` = [[t, força]], com t o segundo do
    bloco em que a jogada decisiva acontece. O zoom dura de MOTIVO_MIN a MOTIVO_MAX s e termina nela (começa no
    começo do trecho se a jogada vem logo)."""
    spans, saida = _spans(edl), {}
    for t, forca in edl.get("zoom_motivo") or []:
        k = next((i for i, (a, b) in enumerate(spans) if a <= t < b), None)
        if k is None:
            continue
        local = float(t) - spans[k][0]
        dur = round(min(max(local, MOTIVO_MIN), MOTIVO_MAX), 2)
        saida[k] = (float(t), float(forca), dur, round(max(local - dur, 0.0), 2))
    return saida


def degraus_do(edl: dict) -> dict[int, tuple[tuple[float, float], ...]]:
    """{trecho: ((t, escala), ...)} do zoom em degraus: `edl["zoom_degraus"]` = [[t, escala]], com t o segundo do bloco
    em que o degrau chega (a escala é absoluta: 1.03, 1.06, 1.09 = três empurrões seguidos, centrados). O degrau
    com t fora do bloco some; cada trecho começa em 1 de novo."""
    spans, saida = _spans(edl), {}
    for t, esc in sorted(edl.get("zoom_degraus") or []):
        k = next((i for i, (a, b) in enumerate(spans) if a <= t < b), None)
        if k is not None:
            saida.setdefault(k, []).append((round(float(t) - spans[k][0], 3), float(esc)))
    return {k: tuple(v) for k, v in saida.items()}


def _spans(edl: dict) -> list[tuple[float, float]]:
    """O intervalo de cada trecho no tempo de saída do bloco."""
    t, out = 0.0, []
    for r in edl["ranges"]:
        d = (float(r["end"]) - float(r["start"])) / float(r.get("velocidade", 1)) + float(r.get("congela") or 0)
        out.append((t, t + d))
        t += d
    return out


def _lado(span: tuple[float, float], lados: list) -> int:
    """-1 / +1 = a peça que mais cobre o trecho está à esquerda / à direita do rosto; 0 = nenhuma passa de MIN_SOBRA."""
    soma = {-1: 0.0, 1: 0.0}
    for t0, t1, lado in lados:
        if lado in soma:
            soma[lado] += max(0.0, min(span[1], float(t1)) - max(span[0], float(t0)))
    lado = max(soma, key=soma.get)
    return lado if soma[lado] >= MIN_SOBRA else 0


def pecas_do(edl: dict, spans: list[tuple[float, float]] | None = None) -> dict[int, tuple[int, tuple]]:
    """{trecho: (lado, janelas)} do zoom com peça. Cada peça de `zoom_lados` ([t0, t1, lado], no tempo do bloco)
    vira uma janela em todo trecho que ela toca por ≥ MIN_PECA; o zoom entra em t0 e sai em t1, nem antes nem
    depois. Trecho com peças dos dois lados fica com o lado que mais cobre. Peça < MIN_SOBRA no total não conta."""
    spans = spans or _spans(edl)
    saida: dict[int, dict[int, list]] = {}
    for t0, t1, lado in edl.get("zoom_lados") or []:
        if lado not in (-1, 1) or float(t1) - float(t0) < MIN_SOBRA:
            continue
        for k, (a, b) in enumerate(spans):
            if min(b, float(t1)) - max(a, float(t0)) >= MIN_PECA:
                saida.setdefault(k, {}).setdefault(lado, []).append((round(float(t0) - a, 4), round(float(t1) - a, 4)))
    r = {}
    for k, por in saida.items():
        lado = max(por, key=lambda l: sum(min(b, spans[k][1] - spans[k][0]) - max(a, 0) for a, b in por[l]))
        r[k] = (lado, tuple(por[lado]))
    return r


def _ease(p: float, suave: bool) -> float:
    return p * p * (3 - 2 * p) if suave else 1 - (1 - p) ** 2


def _expr(z: Zoom, larg: int, alt: int, t: str = "t") -> tuple[str, str, str]:
    """(escala em função do tempo, x, y do recorte) do zoom `z`."""
    if z.degraus:
        zt, ant = "1", 1.0
        for a, esc in z.degraus:
            q = f"clip(({t}-({a - DEGRAU_S:.4f}))/{DEGRAU_S},0,1)"
            zt += f"+({esc - ant:.4f})*({q}*{q}*(3-2*{q}))"
            ant = esc
        zt = f"({zt})"
    elif z.janelas:
        def s(a):
            q = f"clip(({t}-({a:.4f}))/{PECA_S},0,1)"
            return f"({q}*{q}*(3-2*{q}))"
        bumps = [f"{s(a)}*(1-{s(b)})" for a, b in z.janelas]
        pico = bumps[0]
        for b in bumps[1:]:
            pico = f"max({pico},{b})"
        zt = f"(1+{z.z1 - 1:.4f}*{pico})"
    else:
        p = f"clip(({t}-{z.ini:.4f})/{z.dur:.4f},0,1)"
        e = f"({p}*{p}*(3-2*{p}))" if z.suave else f"(1-pow(1-{p},2))"
        zt = f"({z.z0:.4f}+({z.z1 - z.z0:.4f})*{e})"
    lx = z.fx if z.lx is None else z.lx
    x = f"clip({z.fx:.4f}*{larg}*{zt}-{lx:.4f}*{larg},0,{larg}*({zt}-1))"
    y = f"clip({z.fy:.4f}*{alt}*{zt}-{z.fy:.4f}*{alt},0,{alt}*({zt}-1))"
    return zt, x, y


def _zoom_em(z: Zoom, t: float) -> float:
    """A escala de `z` no instante t do trecho (o mesmo que `_expr` pede ao ffmpeg)."""
    if z.degraus:
        zt, ant = 1.0, 1.0
        for a, esc in z.degraus:
            q = min(max((t - (a - DEGRAU_S)) / DEGRAU_S, 0.0), 1.0)
            zt += (esc - ant) * q * q * (3 - 2 * q)
            ant = esc
        return zt
    if z.janelas:
        def s(x):
            q = min(max(x / PECA_S, 0.0), 1.0)
            return q * q * (3 - 2 * q)
        return 1 + (z.z1 - 1) * max(s(t - a) * (1 - s(t - b)) for a, b in z.janelas)
    return z.z0 + (z.z1 - z.z0) * _ease(min(max((t - z.ini) / z.dur, 0), 1), z.suave)


def _recorte_fixo(z: Zoom, larg: int, alt: int) -> tuple[float, float]:
    """(x, y) do recorte quando o zoom já parou em z1."""
    lx = z.fx if z.lx is None else z.lx
    x = min(max(z.fx * larg * z.z1 - lx * larg, 0), larg * (z.z1 - 1))
    y = min(max(z.fy * alt * z.z1 - z.fy * alt, 0), alt * (z.z1 - 1))
    return round(x), round(y)


def _retoca(seg: Path, saida: Path, fps: int, qualidade: str, cabeca, cauda, cama_cabeca, cama_cauda,
            zoom: "Zoom | bool | None") -> None:
    """Um trecho com a emenda dele posta. `cabeca`/`cauda` = lista de PNGs que trocam os primeiros/últimos
    quadros (a duração não muda: o som segue onde estava). `zoom`: o zoom do começo. As camas de som
    entram por baixo da fala, a de cabeça com a segunda metade da cama e a de cauda com a primeira."""
    sonda = ff.probe(seg)
    larg, alt = sonda.largura, sonda.altura
    total = _quadros_de(seg)
    kq, kp = len(cabeca or []), len(cauda or [])
    entradas, filtros = ["-i", str(seg)], []
    nxt = 1
    base = "format=yuv420p,setsar=1"

    filtros.append(f"[0:v]trim=start_frame={kq}:end_frame={total - kp},setpts=PTS-STARTPTS,fps={fps},{base}[m]")
    partes = "[m]"
    if kq:
        entradas += ["-framerate", str(fps), "-start_number", "1", "-i", str(cabeca[0].parent / "c_%d.png")]
        filtros.append(f"[{nxt}:v]fps={fps},{base}[h]")
        partes, nxt = "[h][m]", nxt + 1
    filtros.append(f"{partes}concat=n=2:v=1:a=0[hm]" if kq else "[m]null[hm]")
    if zoom is True:
        zoom = Zoom()
    if zoom and sys.platform == "win32":
        # ponytail: o ffmpeg do Windows (9.0.2, gyan) cai no scale de tamanho variável abaixo (0xC0000005,
        # testa de 16/10); lá a emenda sai sem zoom. Nenhum estilo do kit liga o corte suave; se um ligar, zoompan.
        zoom = None
    if zoom:
        zt, zx, zy = _expr(zoom, larg, alt)
        filtros.append(f"[hm]scale=w='trunc({larg}*{zt}/2)*2':h='trunc({alt}*{zt}/2)*2':eval=frame"
                       f":flags=bicubic,crop={larg}:{alt}:x='{zx}':y='{zy}',setsar=1[z]")
        # a cauda (a ponte da próxima emenda) sai com o zoom em que este trecho parou
        z_fim = _zoom_em(zoom, total / fps)
        cx, cy = _recorte_fixo(replace(zoom, z1=z_fim, z0=z_fim, janelas=(), degraus=()), larg, alt)
    else:
        filtros.append("[hm]null[z]")
        z_fim, cx, cy = 1.0, 0, 0
    if kp:
        entradas += ["-framerate", str(fps), "-start_number", "1", "-i", str(cauda[0].parent / "t_%d.png")]
        zt = f",scale=trunc({larg}*{z_fim:.5f}/2)*2:trunc({alt}*{z_fim:.5f}/2)*2:flags=bicubic,crop={larg}:{alt}:{cx}:{cy}" \
            if abs(z_fim - 1) > 0.0001 else ""
        filtros.append(f"[{nxt}:v]fps={fps},{base}{zt},setsar=1[t]")
        filtros.append("[z][t]concat=n=2:v=1:a=0[v]")
        nxt += 1
    else:
        filtros.append("[z]null[v]")

    audio = ["-c:a", "copy"]
    if cama_cabeca or cama_cauda:
        ent, mix = ["[0:a]"], []
        dur = ff.dur(seg)
        for cama, ini, fim, atraso in ((cama_cabeca, CAMA_S / 2, CAMA_S, 0.0),
                                       (cama_cauda, 0.0, CAMA_S / 2, max(dur - CAMA_S / 2, 0.0))):
            if cama:
                entradas += ["-i", str(cama)]
                ms = int(atraso * 1000)
                mix.append(f"[{nxt}:a]atrim={ini}:{fim},asetpts=PTS-STARTPTS,adelay={ms}|{ms}[c{nxt}]")
                ent.append(f"[c{nxt}]")
                nxt += 1
        filtros += mix
        filtros.append(f"{''.join(ent)}amix=inputs={len(ent)}:duration=first:normalize=0[a]")
        audio = ["-map", "[a]", *ff.args_audio()]
    else:
        audio = ["-map", "0:a", *audio]

    ff.run(["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(filtros), "-map", "[v]", *audio,
            *ff.args_video(qualidade, fps=fps), "-movflags", "+faststart", str(saida)], quiet=True)


def _zooms(edl: dict, emendas: list[Emenda], segmentos: list[Path], total: dict, fps: int, pasta: Path) -> dict:
    """{trecho: Zoom}. A sequência vem de `varia` (semente = o bruto e o primeiro ponto do bloco); o rosto,
    do Vision num quadro do meio do trecho. Três origens, nesta precedência: o zoom com motivo (jogada
    decisiva); o zoom com peça (`pecas_do`: rosto pro lado livre, começa quando a peça entra e acaba quando
    sai, mesmo sem emenda); o zoom de emenda (centrado, lento, 1 em cada CADA emendas sem peça)."""
    seams = [e.i + 1 for e in emendas]
    spans = _spans(edl)
    motivos = motivos_do(edl)
    pecas = pecas_do(edl, spans)
    degraus = degraus_do(edl)
    for k in degraus:         # o degrau manda no trecho: ele já escolheu a escala e o centro
        motivos.pop(k, None)
        pecas.pop(k, None)
    lado_de = {k: _lado(spans[k], edl.get("zoom_lados") or []) for k in motivos}
    livres = [k for k in seams if k not in pecas]
    com_zoom = [livres[g] for g in range(0, len(livres), CADA)]
    alvos = sorted(set(com_zoom) | set(motivos) | set(pecas) | set(degraus))
    lados = [pecas[k][0] if k in pecas else 0 for k in alvos]
    semente = f"{edl['sources']}{edl['ranges'][0]['start']}"
    # a sequência que varia é a das emendas com zoom e das peças; o zoom com motivo sozinho não entra nela
    seq_seams = iter(varia(sum(1 for k in alvos if k in pecas or k in com_zoom), semente,
                           [l for k, l in zip(alvos, lados) if k in pecas or k in com_zoom]))
    seq = [next(seq_seams) if (k in pecas or k in com_zoom) else ("entra", 0.0) for k in alvos]
    imgs = []
    for k in alvos:
        d = pasta / f"z{k}"
        d.mkdir(exist_ok=True)
        imgs.append(_quadro_do(segmentos[k], max(total[k] // 2, 0), fps, d / "rosto.png"))
    rostos = _rosto([i for i in imgs if i.exists()]) if all(i.exists() for i in imgs) else [(0.0,) * 5] * len(imgs)
    saida = {}
    for k, (sentido, f), lado, (x, y, w, h, _) in zip(alvos, seq, lados, rostos):
        fx, fy = (x + w / 2, 1 - (y + h / 2)) if w > 0 else (0.5, 0.5)   # o y do Vision conta de baixo
        z0, z1 = (1.0, 1.0 + f) if sentido == "entra" else (1.0 + f, 1.0)
        lx = None if not lado else (LUGAR_DO_ROSTO if lado < 0 else 1 - LUGAR_DO_ROSTO)
        dur, suave, jan = EMENDA_S, True, ()
        if k in pecas:            # peça no trecho: o zoom acompanha a peça
            jan = pecas[k][1]
        if k in motivos:          # jogada decisiva: empurra devagar até ela, sempre pra dentro
            lx = None if not lado_de[k] else (LUGAR_DO_ROSTO if lado_de[k] < 0 else 1 - LUGAR_DO_ROSTO)
            z0, z1, dur, suave, jan = 1.0, 1.0 + motivos[k][1], motivos[k][2], False, ()
        if k in degraus:          # empurrões centrados: o rosto não anda
            saida[k] = Zoom(1.0, degraus[k][-1][1], 0.5, 0.5, None, degraus=degraus[k])
            continue
        saida[k] = Zoom(z0, z1, round(fx, 4), round(fy, 4), lx, dur, motivos[k][3] if k in motivos else 0.0, suave, janelas=jan)
    return saida


def aplica(edl: dict, emendas: list[Emenda], segmentos: list[Path], fps: int = 30, qualidade: str = "final",
           filtro_som: str = "") -> list[Path]:
    """Põe a emenda (ponte + zoom + cama) nos trechos já extraídos. Reescreve o arquivo de cada trecho
    que tem emenda e devolve a mesma lista de caminhos. `filtro_som`: a cadeia de voz que os trechos
    já passaram, para a cama de ruído soar como o resto."""
    if not emendas and not motivos_do(edl) and not pecas_do(edl) and not degraus_do(edl):
        return segmentos
    kp, kq = N // 2, N - N // 2
    pasta = segmentos[0].parent / "corte_suave"
    pasta.mkdir(parents=True, exist_ok=True)
    solos = [k for k in {*motivos_do(edl), *pecas_do(edl), *degraus_do(edl)} if k not in {e.i + 1 for e in emendas}]
    total = {k: _quadros_de(segmentos[k]) for k in {*(k for e in emendas for k in (e.i, e.i + 1)), *solos}}

    # só emenda cujos dois trechos aguentam a troca de quadros
    for e in emendas:
        if e.suave and min(total[e.i], total[e.i + 1]) < 2 * N + 4:
            e.suave, e.motivo = False, "trecho curto demais para a ponte"

    # 1. os quadros A e B de cada emenda suave, tirados dos trechos já graduados
    lote = []
    for e in emendas:
        if not e.suave:
            continue
        d = pasta / f"e{e.i}"
        d.mkdir(exist_ok=True)
        a = _quadro_do(segmentos[e.i], total[e.i] - kp - 1, fps, d / "A.png")
        b = _quadro_do(segmentos[e.i + 1], kq, fps, d / "B.png")
        lote.append(f"{a}\t{b}\t{d / 'i'}\t{N}")

    # 2. uma sessão do interpolador para todas
    if lote:
        r = subprocess.run([str(binario()), "lote"], input="\n".join(lote) + "\n", capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(f"aviso: o interpolador falhou ({(r.stdout + r.stderr).strip()[-200:]}); emendas ficam secas")
            for e in emendas:
                e.suave, e.motivo = False, "o interpolador falhou"

    # 3. a cama de som de cada emenda
    camas = {e.i: _cama(e, pasta / f"cama{e.i}.wav", filtro_som) for e in emendas}

    # 4. o zoom de cada trecho que vem depois de uma emenda: varia, e acompanha o rosto e as peças
    zooms = _zooms(edl, emendas, segmentos, total, fps, pasta)

    # 5. o que cada trecho recebe
    tarefas = {}
    for e in emendas:
        d = pasta / f"e{e.i}"
        if e.suave:
            for k in range(1, N + 1):
                src = d / f"i_{k}.png"
                dst = (d / f"t_{k}.png") if k <= kp else (d / f"c_{k - kp}.png")
                src.replace(dst)
        cauda = [d / f"t_{k}.png" for k in range(1, kp + 1)] if e.suave else None
        cabeca = [d / f"c_{k}.png" for k in range(1, kq + 1)] if e.suave else None
        t = tarefas.setdefault(e.i, dict(cabeca=None, cauda=None, cama_cabeca=None, cama_cauda=None, zoom=None))
        t["cauda"], t["cama_cauda"] = cauda, camas[e.i]
        u = tarefas.setdefault(e.i + 1, dict(cabeca=None, cauda=None, cama_cabeca=None, cama_cauda=None, zoom=None))
        u["cabeca"], u["cama_cabeca"], u["zoom"] = cabeca, camas[e.i], zooms.get(e.i + 1)

    for k, z in zooms.items():       # o zoom com motivo ou com peça num trecho sem emenda (o 1º, ou o que a emenda não pegou)
        if k in solos:
            tarefas.setdefault(k, dict(cabeca=None, cauda=None, cama_cabeca=None, cama_cauda=None, zoom=None))["zoom"] = z

    def um(k: int) -> None:
        t, seg = tarefas[k], segmentos[k]
        tmp = seg.with_name(seg.stem + ".suave.mp4")
        _retoca(seg, tmp, fps, qualidade, **t)
        os.replace(tmp, seg)

    with ThreadPoolExecutor(TRABALHADORES) as ex:
        list(ex.map(um, sorted(tarefas)))
    shutil.rmtree(pasta, ignore_errors=True)
    return segmentos
