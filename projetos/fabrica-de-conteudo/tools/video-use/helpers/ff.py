"""Costura B — o único lugar onde este projeto chama ffmpeg.

Antes disto, `run` estava escrito de novo em cinco arquivos, `dur`/`probe` em
quatro, e as constantes de saída em cada um que renderiza. "A saída do canal é
1440p30" era convenção lembrada, não linha escrita.

Quatro verbos e um bloco de constantes:

    run       executa (ou grava, no modo seco)
    probe     largura, altura, fps, duração, tem áudio
    dur       duração em segundos
    loudness  a medida de loudnorm, com os cinco valores da 2ª passagem

**Modo seco.** `run` dentro de `seco()` não executa: grava o comando e devolve
uma resposta com cara de sucesso. O chamador não muda de caminho — é o que
permite conferir uma cadeia de filtros sem esperar um render.

    with ff.seco() as cmds:
        monta_a_aula(plano)
    for c in cmds:
        print(" ".join(c))

`probe`, `dur` e `loudness` continuam medindo dentro do `seco()`. Elas só leem, e
sem elas a cadeia não monta — quem precisa do tamanho do quadro para escrever o
filtro precisa dele também no modo seco.

**Fora do escopo, de propósito:** abstração sobre filtergraph. As cadeias de
filtros continuam escritas à mão em cada helper. Elas são a parte artística,
mudam por vídeo, e uma camada por cima delas teria interface tão complicada
quanto a implementação.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterator

# ---- Windows ------------------------------------------------------------------
#
# No Windows, o Python que escreve num cano (e o Claude Code lê tudo por cano)
# escreve em cp1252, e o primeiro "→" de um print estoura. Os filhos herdam o
# modo utf-8 pela variável; este processo, que já começou, troca a saída aqui.
# No Mac e no Linux já é utf-8 e nada muda.
os.environ.setdefault("PYTHONUTF8", "1")
for _fluxo in (sys.stdout, sys.stderr):
    if (hasattr(_fluxo, "reconfigure")
            and (_fluxo.encoding or "").lower().replace("-", "") != "utf8"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")


def caminho_no_filtro(p: Path | str) -> str:
    """O caminho de um arquivo pronto para entrar numa cadeia de filtros, sem aspas.

    `arnndn=m=`, `metadata=print:file=`, `subtitles=`: dentro do filtro, `:`
    separa opção e `\\` escapa. O caminho do Windows é `C:\\Users\\…`, e o ffmpeg
    lia `C` como o arquivo e o resto como outra opção. A barra vira `/`, que o
    ffmpeg aceita no Windows, e o resto escapa nos dois níveis do filtergraph: o
    da opção (`\\` `'` `:`) e o da cadeia (`\\` `'` `[` `]` `,` `;`). Caminho comum
    do Mac sai como entrou.
    """
    s = (p if isinstance(p, PurePath) else Path(p)).as_posix()
    for c in "\\':":
        s = s.replace(c, "\\" + c)
    for c in "\\'[],;":
        s = s.replace(c, "\\" + c)
    return s


# ---- saída padrão do canal --------------------------------------------------
#
# Trocar o encoder é editar aqui. Em nenhum outro lugar.

ALTURA = 1440                 # 1440p — a fonte é 16:10, o canvas 16:9 vem do plano
FPS = 30
PIX_FMT = "yuv420p"
CODEC_VIDEO = "libx264"
CODEC_HW = "h264_videotoolbox"   # o do Mac; só onde existe (tem_videotoolbox)
CODEC_AUDIO = "aac"
AUDIO_BITRATE = "192k"
AUDIO_RATE = "48000"

# Distância máxima entre quadros-chave, em quadros.
#
# O padrão do x264 é 250 — oito segundos a 30fps —, e quem paga por isso é a
# emenda: para trocar 0,4 s de vídeo ela precisa recodificar o grupo inteiro.
# Com grupo de 8 s, um efeito custa 8 s de encode; o ganho de copiar o resto
# quase evapora.
#
# O preço de encurtar é arquivo maior. Medido em 14/09/2026, 20 s a 1440p:
#
#   grupo 250 (8,3 s)  ..... referência
#   grupo 120 (4,0 s)  ..... +3,6%
#   grupo  60 (2,0 s)  ..... +12,0%
#   grupo  30 (1,0 s)  ..... +30,0%
#
# Dois segundos é o joelho da curva: recodifica quatro vezes menos que o padrão
# por 12% de tamanho. Trocar este número é uma linha, e a conta está aqui para
# quem quiser trocar.
GOP = 2 * FPS

# A escada de qualidade: final é o que vai pro ar, prévia dá pra avaliar,
# rascunho serve só pra conferir ponto de corte.
QUALIDADES: dict[str, tuple[str, str]] = {
    "final":    ("fast", "20"),
    "previa":   ("medium", "22"),
    "rascunho": ("ultrafast", "28"),
    # A composição roda uma geração depois do corte, então ela aperta menos:
    # o que ela comprime já passou por um encode.
    "composicao": ("fast", "18"),
    # Efeito (CRT, glitch) reencoda o vídeo inteiro por causa de poucos quadros:
    # mesmo alvo da composição, preset mais lento porque o arquivo sai maior.
    "efeito": ("medium", "18"),
    # Reel: o destino é o feed, que reencoda tudo de novo do outro lado. Aperta
    # um pouco mais que a composição de aula porque o ganho não sobrevive à
    # viagem.
    "reel": ("medium", "19"),
}
PRESET, CRF = QUALIDADES["final"]

# A mesma escada no codificador de hardware do Mac, para quem pede (`codificador()`). Ele não tem
# crf: o `-q:v` é a qualidade constante dele, e cada degrau leva o q que empata ou passa o crf do
# x264. Medido em 07/10/2026 num trecho real do longo de Lorcana (10 s, 1080p30, VMAF contra o
# quadro sem perda), com o tamanho ao lado:
#
#   x264 fast crf20 ..... 95,7   6,7 MB      VT q70 ..... 95,4   6,2 MB
#                                            VT q75 ..... 96,4   8,3 MB
#                                            VT q80 ..... 97,2  12,2 MB
#
# O ganho é de tempo: o x264 é o que pesa no render, na legenda e na emenda.
QUALIDADES_HW: dict[str, str] = {
    "final": "75", "previa": "70", "rascunho": "55",
    "composicao": "80", "efeito": "80", "reel": "78",
    # o proxy substitui o bruto: 97,5 contra o 4K escalado, ~32 Mbps em 1080p
    "proxy": "85",
}

# Padrão das redes: -14 LUFS integrado, -1 dBTP de pico, 11 LU de faixa.
# Bate com a normalização do YouTube, Instagram, TikTok e X.
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0

# A trilha não disputa com a fala: ela entra 3 LU abaixo do alvo da voz e ainda
# é abaixada por volume no filtro. Alvo diferente porque a função é diferente,
# não porque alguém esqueceu de alinhar.
LOUDNORM_MUSICA = -17.0

def limitador(teto: float) -> str:
    """O alimiter que fica no teto. O padrão do ffmpeg liga `level`, que depois
    de limitar sobe tudo de volta até 0 dBFS: baixar o teto não baixava o pico,
    e uma aula publicada saiu com -0,6 dBTP. `latency` compensa o atraso de
    leitura adiantada do limitador, que senão desloca o som da imagem.

    Limita a 4× a taxa: o pico que importa é o ENTRE amostras (dBTP), e a 48 kHz o
    limitador não o vê. Em 29/09 um curto saiu com +1,0 dBTP com teto 0.91; a 192 kHz,
    o mesmo teto dava -0,6."""
    return (f"aresample={4 * int(AUDIO_RATE)},alimiter=limit={teto}:level=disabled:latency=true,"
            f"aresample={AUDIO_RATE}")


def taxa(fonte: int, fps: int = FPS, alfa: str = "") -> str:
    """A cadeia que leva um vídeo de `fonte` qps a `fps`. Na mesma taxa, o `fps` de sempre.
    Fora dela, mistura os dois quadros vizinhos (`framerate`) em vez de repetir um: o avatar
    da HeyGen (25, travado pela HeyGen) levado a 30 por cópia parava o rosto 5 vezes por
    segundo (medido em 03/10: 5,25 cópias/s → 0,12, por +0,5 s de máquina por s de vídeo).
    O `minterpolate` dá o mesmo número a 47 s por s: fica de fora.

    O `framerate` joga o alfa fora: com `alfa` (sufixo de rótulo, único no grafo), o alfa
    vai num ramo à parte e volta no fim. Conta de quadros igual à do `fps` (medido: ±1 por
    trecho, como ele)."""
    if fonte == fps:
        return f"fps={fps}"
    if not alfa:
        return f"framerate=fps={fps}"
    c, a = f"tc{alfa}", f"ta{alfa}"
    return (f"format=yuva444p,split[{c}0][{a}0];[{c}0]framerate=fps={fps}[{c}1];"
            f"[{a}0]alphaextract,framerate=fps={fps}[{a}1];[{c}1][{a}1]alphamerge")


# Preparo do áudio para a transcrição: teto mais baixo e nivelamento dinâmico
# atrás. Não é som que alguém vá ouvir — é entrada de modelo, e o que importa é
# a consoante fraca não sumir.
TRANSCRICAO_AF = f"loudnorm=I={LOUDNORM_I}:TP=-1.5:LRA={LOUDNORM_LRA},dynaudnorm=f=150:g=15"


# ---- modo seco --------------------------------------------------------------

_gravando: list[list[str]] | None = None


@contextmanager
def seco() -> Iterator[list[list[str]]]:
    """Dentro do bloco, `run` grava em vez de executar. Devolve a lista gravada.

    Aninhar é erro: duas listas abertas ao mesmo tempo é o estado global que a
    costura A existe pra matar, entrando por outra porta.
    """
    global _gravando
    if _gravando is not None:
        raise RuntimeError("seco() aninhado — já existe um bloco gravando comandos")
    _gravando = []
    try:
        yield _gravando
    finally:
        _gravando = None


def _resposta_seca(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


# ---- verbos -----------------------------------------------------------------


def run(cmd: list[str], *, quiet: bool = False, check: bool = True,
        capture: bool = False, binario: bool = False,
        cwd: Path | str | None = None) -> subprocess.CompletedProcess:
    """Executa um comando. Dentro de `seco()`, grava e devolve sucesso.

    `check=True` estoura com o comando na mensagem — um passo que falha diz qual
    passo foi, sem exigir a leitura do log inteiro.

    `binario=True` quando a saída NÃO é texto: rawvideo, PCM, qualquer pipe de
    mídia. Sem isso o decode em utf-8 estoura no primeiro byte alto — e estoura
    longe, no meio do subprocess, sem dizer que o problema era o modo de leitura.
    """
    cmd = [str(c) for c in cmd]
    if _gravando is not None:
        _gravando.append(cmd)
        return _resposta_seca(cmd)

    if not quiet:
        cabeca = " ".join(cmd[:6])
        print(f"  $ {cabeca}{' …' if len(cmd) > 6 else ''}")

    # O ffmpeg escreve progresso no stderr. Se ele está indo pra tela, deixa ir —
    # quem está olhando já viu o erro, e engolir o stderr mata a barra de progresso
    # de um render de vinte minutos. No modo calado ninguém viu nada, então a
    # mensagem de falha tem que carregar a ponta do log.
    pega_stderr = capture or quiet
    r = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if pega_stderr else None,
        text=not binario,
        # a saída do ffmpeg é utf-8 em todo sistema; o padrão do Windows é cp1252
        encoding=None if binario else "utf-8",
        errors=None if binario else "replace",
        cwd=str(cwd) if cwd else None,
    )
    if check and r.returncode != 0:
        err = r.stderr
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        detalhe = (err or "").strip().splitlines()[-3:]
        raise RuntimeError(
            f"passo falhou (código {r.returncode}): {' '.join(cmd[:8])}"
            + ("\n  " + "\n  ".join(detalhe) if detalhe else "")
        )
    return r


@dataclass(frozen=True)
class Sonda:
    largura: int
    altura: int
    fps: int
    duracao: float
    tem_audio: bool
    transferencia: str = ""     # a curva de transferência: pq/hlg = HDR
    codec: str = ""             # hevc, h264...
    vfr: bool = False           # taxa variável: o celular grava assim
    giro: int = 0               # graus de rotação nos metadados (90, 180, 270)
    fps_medio: int = 0          # a taxa média real; só difere de `fps` em taxa variável

    @property
    def retrato(self) -> bool:
        return self.altura > self.largura

    @property
    def hdr(self) -> bool:
        return self.transferencia in ("smpte2084", "arib-std-b67")


def _razao(texto: str | None) -> float:
    """`30000/1001` em número; `0/0` (faixa sem taxa) em 0."""
    num, _, den = (texto or "0/1").partition("/")
    return float(num) / float(den) if float(den or 1) else 0.0


def probe(path: Path | str) -> Sonda:
    """Mede o arquivo. Um vídeo sem faixa de áudio responde `tem_audio=False`,
    não estoura — o chamador decide o que fazer com isso."""
    path = Path(path)
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,color_transfer",
         "-show_entries", "stream_side_data=rotation:stream_tags=rotate",
         "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        detalhe = (r.stderr or "").strip().splitlines()[-1:] or ["sem detalhe"]
        raise RuntimeError(f"ffprobe falhou em {path}: {detalhe[0]}")

    dados = json.loads(r.stdout or "{}")
    fluxos = dados.get("streams", [])
    video = next((s for s in fluxos if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError(f"{path} não tem faixa de vídeo")

    r = _razao(video.get("r_frame_rate"))
    # `fps` segue sendo o r_frame_rate (quem chamava antes lê isso: uma gravação de tela em taxa
    # variável não pode virar a média baixa). A média real vai à parte, em `fps_medio`.
    media = _razao(video.get("avg_frame_rate")) or r
    vfr = bool(r and media and abs(r - media) / r > 0.002)
    fps = round(r or media)
    giro = 0
    for lado in video.get("side_data_list") or []:
        if "rotation" in lado:
            giro = int(round(float(lado["rotation"])))
    giro = (giro or int(video.get("tags", {}).get("rotate") or 0)) % 360
    duracao = float(dados.get("format", {}).get("duration") or 0.0)
    tem_audio = any(s.get("codec_type") == "audio" for s in fluxos)
    # o ffmpeg decodifica já girado: largura e altura são as de quem assiste
    larg, alt = int(video["width"]), int(video["height"])
    if giro in (90, 270):
        larg, alt = alt, larg
    return Sonda(larg, alt, fps, duracao, tem_audio, video.get("color_transfer") or "",
                 video.get("codec_name") or "", vfr, giro, round(media))


_LIBASS: bool | None = None


def tem_libass() -> bool:
    """Este ffmpeg sabe queimar legenda?

    O `brew install ffmpeg` do homebrew-core vem sem libass, e sem libass o filtro
    `subtitles` não existe. A mensagem que o ffmpeg devolve nesse caso fala em
    sintaxe ("No option name near ..."), o que manda quem lê consertar a linha de
    comando — o que falta é a biblioteca. Por isso a checagem é pelo nome do filtro,
    e não pelo erro.
    """
    global _LIBASS
    if _LIBASS is None:
        saida = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace").stdout
        _LIBASS = any(l.split()[1:2] == ["subtitles"] for l in saida.splitlines() if l.strip())
    return _LIBASS


# Quem escolhe o hardware é o estilo (`imagem.codificador`); a fábrica passa a escolha aos helpers
# que ela chama por esta variável ("1", "auto" ou "0"), e ela entra na impressão de cada passo.
HARDWARE = "FF_HARDWARE"
_VT: bool | None = None


def tem_videotoolbox() -> bool:
    """O codificador de hardware do Mac funciona aqui, com qualidade constante? No Windows e no
    Linux ele não existe, e o kit do aluno roda lá também: quem pergunta cai no libx264 quando a
    resposta é não. Pergunta codificando um quadro, e não pela lista: o Mac Intel lista o
    codificador e pode recusar o `-q:v`."""
    global _VT
    if _VT is None:
        _VT = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x64:d=0.1",
                              "-c:v", CODEC_HW, "-q:v", QUALIDADES_HW["final"], "-f", "null", "-"],
                             capture_output=True).returncode == 0
    return _VT


# `FF_HARDWARE=auto`: o hardware só onde a medição de 23/10/2026 (10 s por perfil: 9:16 de câmera,
# 16:9 de câmera a 1440p e 9:16 gráfico; VMAF contra o quadro sem perda) deu ganho sem custo que
# alguém veja. Nos três degraus abaixo o VT gasta 4 a 8 vezes menos CPU e roda 2 a 4 vezes mais
# rápido (com a máquina carregada); o arquivo sai 30% a 90% maior, que não pesa em quem é lido uma vez e apagado.
#
#   degrau      VMAF do VT contra o x264 (câmera 9:16, 16:9, gráfico)
#   previa      +0,7  +1,6  -0,3
#   composicao  +1,5  +1,7  -0,1
#   efeito      +1,3  +1,6  -0,2
#
# Ficam no x264: final e reel, porque são o que sai (no q75 o VT dá +31% a +94% de bytes, e no q70,
# que empata o tamanho, o gráfico perde 1,0 de VMAF); e rascunho, onde o VT perde 2 a 3,4 de VMAF e
# nem ganha tempo do `ultrafast`.
AUTO_HARDWARE = frozenset({"previa", "composicao", "efeito"})


def codificador(qualidade: str | None = None) -> str:
    """O codificador de vídeo desta execução, se existir hardware aqui. `FF_HARDWARE=1` pede o
    hardware em todo degrau; `auto` só nos de `AUTO_HARDWARE` (sem `qualidade`, no x264); qualquer
    outro valor, o x264."""
    modo = os.environ.get(HARDWARE)
    quer = modo == "1" or (modo == "auto" and qualidade in AUTO_HARDWARE)
    return CODEC_HW if quer and tem_videotoolbox() else CODEC_VIDEO


def dur(path: Path | str) -> float:
    """Duração em segundos — de vídeo ou de som.

    Não passa pelo `probe`: duração é do formato, não da faixa de vídeo. Um wav
    de efeito sonoro tem duração e não tem imagem, e exigir imagem para responder
    quanto ele dura foi um erro que travou o CRT da aula.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    saida = (r.stdout or "").strip()
    if r.returncode != 0 or not saida:
        detalhe = (r.stderr or "").strip().splitlines()[-1:] or ["sem detalhe"]
        raise RuntimeError(f"não deu para medir a duração de {path}: {detalhe[0]}")
    return float(saida)


def legivel(path: Path | str) -> bool:
    """O ffprobe consegue abrir este arquivo?

    Existe para quem lida com arquivo quebrado de propósito — a recuperação do
    cache do CapCut desofusca bytes e precisa perguntar "já deu?" a cada tentativa,
    sem que a resposta "não" seja um erro.
    """
    try:
        probe(path)
        return True
    except Exception:
        return False


def loudness(path: Path | str, onde: str | None = None) -> dict[str, str] | None:
    """Primeira passagem do loudnorm: mede e devolve os cinco valores que a
    segunda passagem precisa. `None` quando a medida não sai. `onde` mede só os
    trechos em que a expressão do ffmpeg vale 1 (a fala, o fim).

    Uma implementação só, de propósito. O `ebur128` que o vídeo de quadro usa dá
    só o LRA; quem quiser só o LRA lê o campo daqui, e aí as duas medidas não
    podem discordar. O `mixa`, o `trata_voz` e o `pre_voo` mediam cada um do seu
    jeito (um deles decodificando a imagem junto); agora todos passam pelo `lufs`.
    """
    so = f"aselect='{onde}'," if onde else ""
    filtro = f"{so}loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(path),
         "-af", filtro, "-vn", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # o loudnorm imprime o JSON no stderr, no fim da corrida
    stderr = r.stderr or ""
    ini, fim = stderr.rfind("{"), stderr.rfind("}")
    if ini == -1 or fim <= ini:
        return None
    try:
        dados = json.loads(stderr[ini:fim + 1])
    except json.JSONDecodeError:
        return None
    preciso = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    return dados if preciso.issubset(dados) else None


def lufs(path: Path | str, onde: str | None = None) -> float:
    """O loudness integrado, em LUFS. Estoura quando a medida não sai: medir errado
    calado é pior que parar."""
    import math
    m = loudness(path, onde)
    valor = float(m["input_i"]) if m else math.nan
    if not math.isfinite(valor):
        # silêncio (ou o `onde` sem trecho nenhum) mede -inf: virar ganho infinito estoura longe daqui
        raise RuntimeError(f"não consegui medir o loudness de {path} (deu {m and m['input_i']})")
    return valor


# ---- montadores de argumento ------------------------------------------------


def loudnorm_filter(medida: dict[str, str] | None = None) -> str:
    """O filtro de loudnorm. Com medida, é a 2ª passagem — e ela carrega os cinco
    valores, senão é uma 1ª passagem cara que não normaliza direito."""
    base = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
    if not medida:
        return base
    return (f"{base}"
            f":measured_I={medida['input_i']}"
            f":measured_TP={medida['input_tp']}"
            f":measured_LRA={medida['input_lra']}"
            f":measured_thresh={medida['input_thresh']}"
            f":offset={medida['target_offset']}"
            f":linear=true")


def args_video(qualidade: str = "final", fps: int | None = FPS) -> list[str]:
    """Os argumentos de vídeo da saída. Trocar encoder é mexer nas constantes.

    `fps=None` não fixa a taxa: a saída herda a da entrada. Serve para o passo de
    composição, onde forçar a taxa remendaria um render de 24 para 30.
    """
    if qualidade not in QUALIDADES:
        raise KeyError(
            f"qualidade '{qualidade}' não existe. Disponíveis: {', '.join(QUALIDADES)}"
        )
    if codificador(qualidade) == CODEC_HW:
        return (["-c:v", CODEC_HW, "-q:v", QUALIDADES_HW[qualidade], "-pix_fmt", PIX_FMT,
                 "-g", str(GOP)] + (["-r", str(fps)] if fps else []))
    preset, crf = QUALIDADES[qualidade]
    args = ["-c:v", CODEC_VIDEO, "-preset", preset, "-crf", crf, "-pix_fmt", PIX_FMT,
            # `-g` aqui, e não em cada chamador: é o que deixa a emenda cortar
            # fino em vez de recodificar um grupo inteiro para trocar meio
            # segundo.
            "-g", str(GOP)]
    return args + (["-r", str(fps)] if fps else [])


def args_sem_perda() -> list[str]:
    """O vídeo intermediário que o passo seguinte do MESMO processo lê e apaga: x264 sem perda, no
    preset mais rápido. É uma geração de perda a menos, e grava mais rápido que o crf 16 veryfast
    que a câmera usava; o arquivo é grande, mas vive só no temporário."""
    return ["-c:v", CODEC_VIDEO, "-preset", "ultrafast", "-qp", "0"]


def args_audio() -> list[str]:
    """Os argumentos de áudio da saída."""
    return ["-c:a", CODEC_AUDIO, "-b:a", AUDIO_BITRATE, "-ar", AUDIO_RATE]
