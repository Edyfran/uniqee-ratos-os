"""Render a video from an EDL.

Implements the HEURISTICS render pipeline in the correct order:

  1. Per-segment extract with color grade + 30ms audio fades baked in
  2. Lossless -c copy concat into base.mp4
  3. If overlays or subtitles: single filter graph that overlays animations
     (with PTS shift so frame 0 lands at the overlay window start)
     and applies `subtitles` filter LAST → final.mp4

Optionally builds a master SRT from the per-source transcripts + EDL
output-timeline offsets, applies the proven force_style (2-word
UPPERCASE chunks, Helvetica 18 Bold, MarginV=35).

Usage:
    python helpers/render.py <edl.json> -o final.mp4
    python helpers/render.py <edl.json> -o preview.mp4 --preview
    python helpers/render.py <edl.json> -o final.mp4 --build-subtitles
    python helpers/render.py <edl.json> -o final.mp4 --no-subtitles
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import ff
from concurrent.futures import ThreadPoolExecutor

try:
    from grade import get_preset, auto_grade_for_clip  # same directory
except Exception:
    def get_preset(name: str) -> str:
        return ""

    def auto_grade_for_clip(video, start=0.0, duration=None, verbose=False):  # type: ignore
        return "eq=contrast=1.03:saturation=0.98", {}


# -------- Subtitle style (bold-overlay, proven at 1920×1080 and 1080×1920) --
#
# MarginV is NOT taste — it is a platform safe-zone rule.
# TikTok / IG Reels / Shorts UI (caption, username, music, right-rail actions)
# covers roughly the bottom ~25–30% of a 1080×1920 frame. Captions placed near
# the bottom edge get clipped or obscured by the UI. libass auto-scales the
# render canvas relative to PlayResY=288, so MarginV=90 lands the caption
# baseline roughly 30% up from the bottom on any aspect — clear of the UI on
# every major vertical-video platform. Do not drop this below ~75 without a
# specific reason.
# Quantos trechos são extraídos ao mesmo tempo. Medido: com 4 o tempo caiu de
# 9,2 s para 5,7 s em 27 trechos; com 8 subiu para 5,9 s, porque o encoder já usa
# os núcleos por dentro de cada processo.
TRABALHADORES = 4

SUB_FORCE_STYLE = (
    "FontName=Helvetica,FontSize=18,Bold=1,"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=90"
)

# -------- Helpers ------------------------------------------------------------


tem_libass = ff.tem_libass
run = ff.run


def resolve_grade_filter(grade_field: str | None) -> str:
    """The EDL's 'grade' field can be a preset name, a raw ffmpeg filter, or 'auto'.

    Returns the filter string to embed into the per-segment -vf chain.
    For 'auto', returns the sentinel "__AUTO__" which is resolved per-segment.
    """
    if not grade_field:
        return ""
    if grade_field == "auto":
        return "__AUTO__"
    # Preset names are short identifiers, filter strings contain '=' or ','.
    if re.fullmatch(r"[a-zA-Z0-9_\-]+", grade_field):
        try:
            return get_preset(grade_field)
        except KeyError:
            print(f"warning: unknown preset '{grade_field}', using as raw filter")
            return grade_field
    return grade_field


def resolve_path(maybe_path: str, base: Path) -> Path:
    """Resolve a path that may be absolute or relative to `base`."""
    p = Path(maybe_path)
    if p.is_absolute():
        return p
    return (base / p).resolve()


# -------- HDR → SDR tone mapping (HLG / PQ sources) --------------------------
#
# iPhone defaults to HLG HDR in Rec.2020 (and many mirrorless cameras ship PQ).
# If the source is HDR and we only downconvert bit depth (yuv420p10le → yuv420p)
# without tone-mapping, the output is 8-bit but still carries HLG/PQ transfer
# metadata. Players that honor the metadata (screen recorders, most social
# upload re-encodes) interpret 8-bit values in an HDR container and the result
# looks oversaturated / blown out. QuickTime on macOS can hide this locally —
# screen recording and uploaded renders cannot.
#
# Fix: detect HDR via color_transfer and prepend a zscale+tonemap chain to the
# vf graph so the output is clean Rec.709 SDR.

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ (HDR10) and HLG

TONEMAP_CHAIN = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)


def is_hdr_source(video: Path) -> bool:
    """A fonte usa curva PQ ou HLG?"""
    try:
        return ff.probe(video).hdr
    except Exception:
        return False


def is_portrait_source(video: Path) -> bool:
    """A fonte é vertical?"""
    try:
        return ff.probe(video).retrato
    except Exception:
        return False


# -------- Per-segment extraction (Rule 2 + Rule 3) --------------------------


# Voice-enhance + denoise chain (applied before loudnorm). Moderate, natural —
# rumble cut, gentle broadband denoise, low-mud trim, presence + air lift, light
# leveling. Tuned for a single talking-head/lesson voice, not music.
VOICE_ENHANCE_CHAIN = (
    "highpass=f=80,"
    "afftdn=nr=10:nf=-25,"
    "equalizer=f=200:t=q:w=1.0:g=-2,"
    "equalizer=f=3000:t=q:w=1.8:g=2.5,"
    "equalizer=f=10000:t=h:g=1.5,"
    "acompressor=threshold=-20dB:ratio=2.5:attack=15:release=150:makeup=2"
)


_QUASE: dict[str, bool] = {}


def quase_na_taxa(source: Path, fps: int) -> bool:
    """A fonte anda num passo fixo QUASE igual a `fps` (o iPhone grava a 29,97: 1001/30000 s)?

    Levada a 30 pelo `-r`, ela ganha um quadro repetido a cada ~33 s: a imagem "trava um quadro"
    no meio da fala (o dono, no Treinando #3: "alguns momentos eu fiquei travado um frame"). Nesse
    caso o trecho troca o relógio (`setpts=N/fps`): cada quadro da fonte vira um quadro da saída,
    sem cópia, e a imagem adianta 1 ms por segundo sobre o som, que recomeça junto a cada trecho.
    Só com o passo regular: fonte com buraco no meio (o iPhone segura um quadro por 133 ms às
    vezes) desencontraria o som pelo tamanho do buraco, e fica no `-r` de sempre."""
    chave = f"{source}@{fps}"
    if chave not in _QUASE:
        r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                    "-of", "csv=p=0", str(source)], capture=True, quiet=True, check=False)
        ts = sorted(float(x) for x in (r.stdout or "").split() if x.strip())
        ts = ts[:-2]                                         # o último quadro do iPhone dura o que quiser
        ds = [b - a for a, b in zip(ts, ts[1:])]
        passo = 1 / fps
        # o MOV do iPhone conta em 1/600 s: o passo de 1001/30000 sai 20 ou 21 tiques, nunca igual
        media = (ts[-1] - ts[0]) / len(ds) if len(ds) > 30 else 0.0
        _QUASE[chave] = bool(media and all(abs(d - passo) < 0.0021 for d in ds)
                             and 1e-5 < abs(media - passo) < passo * 0.005)
    return _QUASE[chave]


def extract_segment(
    source: Path,
    seg_start: float,
    duration: float,
    grade_filter: str,
    out_path: Path,
    preview: bool = False,
    draft: bool = False,
    out_height: int = 1080,
    fps: int = 24,
    voice_enhance: bool = False,
    canvas: str | None = None,
    mudo: bool = False,
    congela: float = 0.0,
    velocidade: float = 1.0,
    recorte: str | None = None,
    quadros: int | None = None,
) -> None:
    """Extract a cut range as its own MP4 with grade + 30ms audio fades baked in.

    `quadros`: quantos quadros da saída o trecho tem, exatos, e o som dura o mesmo `quadros / fps`.
    Sem ele a duração arredonda PARA CIMA na grade de quadros, em cada trecho; quem corta um EDL
    inteiro passa o número (ver `extract_all_segments`).

    `congela`: segundos de quadro parado no fim do trecho (o último quadro repetido),
    com silêncio no áudio pelo mesmo tempo. `velocidade`: acelera o trecho (2 = metade
    do tempo); o congelado vem depois, já na velocidade normal. `recorte`: um
    `crop=w:h:x:y` em pixels da fonte, antes de escalar — o vertical tirado de uma
    gravação deitada.

    `-ss` before `-i` for fast accurate seeking. Scale to 1080p from 4K.
    Portrait sources (height > width) are scaled by height to preserve orientation.

    A escada de qualidade (final / prévia / rascunho) mora na costura B.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    portrait = is_portrait_source(source)
    if recorte:
        # A largura sai calculada e par: o -2 arredondava 608x1080 pra 1082 de largura,
        # e o concat recusa trecho de tamanho diferente.
        w, h = (int(x) for x in recorte.split("=", 1)[1].split(":")[:2])
        oh = 1280 if draft else (1920 if h > w else out_height)
        ow = oh * 9 // 16
        if h > w and abs(w / h - 9 / 16) > 0.01:
            # Em pé, mas mais largo que 9:16 (menos zoom na cara): o recorte entra inteiro pela largura,
            # com TARJA PRETA sólida em cima e embaixo (dono, 12/10: nunca o fundo espelhado/borrado).
            scale = (f"{recorte},scale={ow}:-2,pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
        else:
            scale = f"{recorte},scale={round(oh * w / h / 2) * 2}:{oh},setsar=1"
    elif canvas:
        # Fit the whole frame into a fixed WxH canvas, letterbox/pillarbox the
        # rest (no crop, no distortion). Use for YouTube-standard 16:9 from a
        # 16:10 source. Draft halves it for speed.
        cw, ch = (int(x) for x in canvas.lower().split("x"))
        if draft:
            cw, ch = cw // 2 // 2 * 2, ch // 2 // 2 * 2
        scale = (f"scale={cw}:{ch}:force_original_aspect_ratio=decrease,"
                 f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
    elif draft:
        scale = "scale=-2:1280" if portrait else "scale=1280:-2"
    else:
        # Landscape: scale by target height (e.g. 1080 -> 1920x1080, 1440 -> 2560x1440).
        scale = "scale=-2:1920" if portrait else f"scale=-2:{out_height}"

    vf_parts: list[str] = []
    if is_hdr_source(source):
        vf_parts.append(TONEMAP_CHAIN)
    vf_parts.append(scale)
    if quase_na_taxa(source, fps):
        vf_parts.append(f"setpts=N/{fps}/TB")
    if grade_filter:
        vf_parts.append(grade_filter)
    if velocidade != 1:
        vf_parts.append(f"setpts=PTS/{velocidade:.4f}")
    if congela:
        vf_parts.append(f"tpad=stop_mode=clone:stop_duration={congela:.3f}")
    vf = ",".join(vf_parts)
    total = duration / velocidade + congela
    if quadros:
        total = quadros / fps

    # 30ms audio fades at both edges (Rule 3) — prevent pops.
    # Voice enhance/denoise runs BEFORE the fades so edges stay clean.
    fade_out_start = max(0.0, total - 0.03)
    fades = f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03"
    af = f"{VOICE_ENHANCE_CHAIN},{fades}" if voice_enhance else fades
    if mudo:
        # Bloco sem fala: a trilha cobre. Zerar aqui e não tirar a faixa, porque
        # o concat precisa de áudio em todo trecho.
        af = "volume=0"
    if congela or velocidade != 1:
        # acelera primeiro e só então completa com silêncio: na ordem inversa o atempo
        # comprimia o silêncio junto, e o áudio saía mais curto que o vídeo. O -t de
        # saída corta o apad no total.
        af = ",".join([f"atempo={velocidade:.4f}"] * (velocidade != 1) + ["apad", af])

    qualidade = "rascunho" if draft else ("previa" if preview else "final")

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{seg_start:.3f}",
        # com `congela`, o -t de entrada lê só o trecho e o de saída conta o quadro parado
        *(["-t", f"{duration:.3f}"] if congela or velocidade != 1 else []),
        "-i", str(source),
        "-t", f"{total:.6f}" if quadros else f"{total:.3f}",
        # `-t` sozinho conta os quadros de pts < t: n/fps com casas a menos dá n+1 quadros
        *(["-frames:v", str(quadros)] if quadros else []),
        "-vf", vf,
        "-af", af,
        *ff.args_video(qualidade, fps=fps),
        *ff.args_audio(),
        "-movflags", "+faststart",
        str(out_path),
    ]
    ff.run(cmd, quiet=True)


def extract_all_segments(
    edl: dict,
    edit_dir: Path,
    preview: bool,
    draft: bool = False,
    out_height: int = 1080,
    fps: int = 24,
    voice_enhance: bool = False,
    canvas: str | None = None,
    tag: str = "",
    mudo: bool = False,
) -> list[Path]:
    """Extract every EDL range into edit_dir/clips_<tag>/seg_NN.mp4.
    Returns the ordered list of segment paths.

    `tag` makes the clips dir unique per output so concurrent renders in the
    same edit_dir don't clobber each other's segments.

    If the EDL `grade` is "auto", analyze each segment range with
    `auto_grade_for_clip` and apply a per-segment subtle correction.
    Otherwise, apply the same preset/raw filter to every segment.
    """
    resolved = resolve_grade_filter(edl.get("grade"))
    is_auto = resolved == "__AUTO__"
    kind = "clips_draft" if draft else ("clips_preview" if preview else "clips_graded")
    clips_dir = edit_dir / (f"{kind}_{tag}" if tag else kind)
    clips_dir.mkdir(parents=True, exist_ok=True)

    ranges = edl["ranges"]
    sources = edl["sources"]

    # O ffmpeg arredonda a duração de cada trecho PARA CIMA na grade de quadros (meio quadro a mais,
    # em média, por trecho), e a legenda, as peças e os sons ficam no relógio exato do plano: 43 trechos
    # a 24 fps saíam 0,9 s maiores, e a voz chegava cada vez mais tarde. Aqui o fim de cada trecho cai
    # em round(soma * fps) quadros, e o trecho dura a diferença: o total é round(soma * fps) / fps e
    # nenhuma emenda desvia mais que meio quadro do plano.
    quadros: list[int] = []
    soma = fim_q = 0
    for r in ranges:
        soma += (float(r["end"]) - float(r["start"])) / float(r.get("velocidade", 1)) + float(r.get("congela", 0))
        n = max(1, int(soma * fps + 0.5) - fim_q)   # shortcut: trecho de menos de meio quadro vira 1 quadro e atrasa a conta, só importa com dezenas de trechos assim em fila
        quadros.append(n)
        fim_q += n

    seg_paths: list[Path] = []
    tarefas: list[tuple] = []
    print(f"extracting {len(ranges)} segment(s) → {clips_dir.name}/")
    if is_auto:
        print("  (auto-grade per segment: analyzing each range)")
    for i, r in enumerate(ranges):
        src_name = r["source"]
        src_path = resolve_path(sources[src_name], edit_dir)
        start = float(r["start"])
        end = float(r["end"])
        duration = end - start
        congela = float(r.get("congela", 0))
        velocidade = float(r.get("velocidade", 1))
        recorte = r.get("recorte")
        out_path = clips_dir / f"seg_{i:02d}_{src_name}.mp4"

        if is_auto:
            seg_filter, _stats = auto_grade_for_clip(src_path, start=start, duration=duration, verbose=False)
        else:
            seg_filter = resolved

        note = r.get("beat") or r.get("note") or ""
        print(f"  [{i:02d}] {src_name}  {start:7.2f}-{end:7.2f}  ({duration:5.2f}s)  {note}")
        if is_auto:
            print(f"        grade: {seg_filter or '(none)'}")
        tarefas.append((i, src_path, start, duration, seg_filter, out_path, congela, velocidade,
                        recorte, quadros[i]))
        seg_paths.append(out_path)

    # Os trechos são independentes, e rodavam um de cada vez. Em paralelo:
    # 9,2 s -> 5,7 s com quatro, medido em 27 trechos.
    #
    # Quatro e não doze: o x264 já usa os núcleos por DENTRO de cada encode,
    # então os processos disputam entre si. Com oito ficou 5,9 s — pior que com
    # quatro. O teto está medido, não chutado.
    def _um(t):
        i, src, start, dur, filtro, saida, congela, velocidade, recorte, n = t
        try:
            extract_segment(src, start, dur, filtro, saida,
                            preview=preview, draft=draft, out_height=out_height,
                            fps=fps, voice_enhance=voice_enhance, canvas=canvas, mudo=mudo,
                            congela=congela, velocidade=velocidade, recorte=recorte, quadros=n)
        except Exception as e:
            raise RuntimeError(f"o trecho [{i:02d}] {start:.2f}-{start + dur:.2f} falhou: {e}")

    if len(tarefas) > 1:
        with ThreadPoolExecutor(max_workers=min(TRABALHADORES, len(tarefas))) as ex:
            list(ex.map(_um, tarefas))
    else:
        for t in tarefas:
            _um(t)

    # A ordem da saída é a das JANELAS, não a de término. Costurar trecho fora de
    # ordem é requisito antigo, e o paralelo não pode mexer nisso.
    return seg_paths


# -------- Lossless concat ----------------------------------------------------


def concat_segments(segment_paths: list[Path], out_path: Path, edit_dir: Path,
                    tag: str = "") -> None:
    """Concat via the concat demuxer: imagem copiada, som recodificado no relógio.

    Cada trecho AAC traz os seus ~21 ms de preparo do codificador, e o demultiplexador
    cola os pacotes sobrepostos: o som ficava mais longo que a imagem, 21 ms por emenda.
    Com 53 janelas (o lote do Mercado Livre, carta a carta, 29/09) deu 1 s a mais, e o
    junta.py recusou a emenda. O `aresample=async` corta o som no carimbo de tempo."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list = edit_dir / (f"_concat_{tag}.txt" if tag else "_concat.txt")
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "copy",
        "-af", "aresample=async=1:min_hard_comp=0.01:first_pts=0",
        *ff.args_audio(),
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"concat → {out_path.name}")
    ff.run(cmd, quiet=True)
    concat_list.unlink(missing_ok=True)


# -------- Master SRT (Rule 5) ------------------------------------------------


PUNCT_BREAK = set(".,!?;:")


def _srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _words_in_range(transcript: dict, t_start: float, t_end: float) -> list[dict]:
    out: list[dict] = []
    for w in transcript.get("words", []):
        if w.get("type") != "word":
            continue
        ws = w.get("start")
        we = w.get("end")
        if ws is None or we is None:
            continue
        if we <= t_start or ws >= t_end:
            continue
        out.append(w)
    return out


def build_master_srt(edl: dict, edit_dir: Path, out_path: Path) -> None:
    """Build an output-timeline SRT from per-source transcripts.

    - 2-word chunks (break on any punctuation in between)
    - UPPERCASE text
    - Output times computed as word.start - segment_start + segment_offset
    """
    transcripts_dir = edit_dir / "transcripts"
    sources = edl["sources"]

    entries: list[tuple[float, float, str]] = []
    seg_offset = 0.0

    for r in edl["ranges"]:
        src_name = r["source"]
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        seg_duration = (seg_end - seg_start) / float(r.get("velocidade", 1)) + float(r.get("congela", 0))

        tr_path = transcripts_dir / f"{src_name}.json"
        if not tr_path.exists():
            print(f"  no transcript for {src_name}, skipping captions for this segment")
            seg_offset += seg_duration
            continue

        transcript = json.loads(tr_path.read_text(encoding="utf-8"))
        words_in_seg = _words_in_range(transcript, seg_start, seg_end)

        # Group into 2-word chunks, break on punctuation
        chunks: list[list[dict]] = []
        current: list[dict] = []
        for w in words_in_seg:
            text = (w.get("text") or "").strip()
            if not text:
                continue
            current.append(w)
            # Break if the current text ends in punctuation or we hit 2 words
            ends_in_punct = bool(text) and text[-1] in PUNCT_BREAK
            if len(current) >= 2 or ends_in_punct:
                chunks.append(current)
                current = []
        if current:
            chunks.append(current)

        for chunk in chunks:
            local_start = max(seg_start, chunk[0].get("start", seg_start))
            local_end = min(seg_end, chunk[-1].get("end", seg_end))
            out_start = max(0.0, local_start - seg_start) + seg_offset
            out_end = max(0.0, local_end - seg_start) + seg_offset
            if out_end <= out_start:
                out_end = out_start + 0.4
            text = " ".join((w.get("text") or "").strip() for w in chunk)
            text = re.sub(r"\s+", " ", text).strip()
            # Strip trailing punctuation for cleaner uppercase look
            text = text.rstrip(",;:")
            text = text.upper()
            entries.append((out_start, out_end, text))

        seg_offset += seg_duration

    # Sort and write as SRT
    entries.sort(key=lambda e: e[0])
    lines: list[str] = []
    for i, (a, b, t) in enumerate(entries, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(a)} --> {_srt_timestamp(b)}")
        lines.append(t)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"master SRT → {out_path.name} ({len(entries)} cues)")


# -------- Loudness normalization (social-ready audio) -----------------------


# O padrão das redes vive na costura B — aqui só o apelido, para o código
# existente continuar lendo os mesmos nomes.
LOUDNORM_I, LOUDNORM_TP, LOUDNORM_LRA = ff.LOUDNORM_I, ff.LOUDNORM_TP, ff.LOUDNORM_LRA


# A medida de loudness tem uma implementação só, na costura B. Aqui só o apelido.
measure_loudness = ff.loudness


def apply_loudnorm_two_pass(
    input_path: Path,
    output_path: Path,
    preview: bool = False,
) -> bool:
    """Loudness no alvo, copiando a imagem. Quem faz é o `normaliza`: este era uma cópia
    dele, linha por linha, e duas cópias da mesma regra divergem."""
    from normaliza import normaliza
    print(f"  loudnorm → {output_path.name}")
    normaliza(input_path, output_path, preview)
    return True


# -------- Final compositing (Rule 1 + Rule 4) -------------------------------


def build_final_composite(
    base_path: Path,
    overlays: list[dict],
    subtitles_path: Path | None,
    out_path: Path,
    edit_dir: Path,
) -> None:
    """Final pass: base → overlays (PTS-shifted) → subtitles LAST → out.

    If there are no overlays and no subtitles, just copy base to out.
    """
    has_overlays = bool(overlays)
    has_subs = subtitles_path is not None and subtitles_path.exists()

    if not has_overlays and not has_subs:
        # Nothing to do — just rename/copy base to final name
        run(["ffmpeg", "-y", "-i", str(base_path), "-c", "copy", str(out_path)], quiet=True)
        return

    inputs: list[str] = ["-i", str(base_path)]
    for ov in overlays:
        ov_path = resolve_path(ov["file"], edit_dir)
        inputs += ["-i", str(ov_path)]

    filter_parts: list[str] = []
    # PTS-shift every overlay so its frame 0 lands at start_in_output
    for idx, ov in enumerate(overlays, start=1):
        t = float(ov["start_in_output"])
        filter_parts.append(f"[{idx}:v]setpts=PTS-STARTPTS+{t}/TB[a{idx}]")

    # Chain overlays on top of base
    current = "[0:v]"
    for idx, ov in enumerate(overlays, start=1):
        t = float(ov["start_in_output"])
        dur = float(ov["duration"])
        end = t + dur
        next_label = f"[v{idx}]"
        filter_parts.append(
            f"{current}[a{idx}]overlay=enable='between(t,{t:.3f},{end:.3f})'{next_label}"
        )
        current = next_label

    # Subtitles LAST — Rule 1
    if has_subs:
        filter_parts.append(
            f"{current}subtitles={ff.caminho_no_filtro(subtitles_path.resolve())}:force_style='{SUB_FORCE_STYLE}'[outv]"
        )
        out_label = "[outv]"
    else:
        # Rename the last overlay output to [outv] for consistency
        if has_overlays:
            filter_parts.append(f"{current}null[outv]")
            out_label = "[outv]"
        else:
            out_label = "[0:v]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", out_label,
        "-map", "0:a",
        *ff.args_video("composicao", fps=None),
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"compositing → {out_path.name}")
    print(f"  overlays: {len(overlays)}, subtitles: {'yes' if has_subs else 'no'}")
    ff.run(cmd, quiet=True)


# -------- Main ---------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a video from an EDL")
    ap.add_argument("edl", type=Path, help="Path to edl.json")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output video path")
    ap.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: 1080p, medium, CRF 22 — evaluable for QC, faster than final.",
    )
    ap.add_argument(
        "--draft",
        action="store_true",
        help="Draft mode: 720p, ultrafast, CRF 28 — cut-point verification only.",
    )
    ap.add_argument(
        "--build-subtitles",
        action="store_true",
        help="Build master.srt from transcripts + EDL offsets before compositing",
    )
    ap.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Skip subtitles even if the EDL references one",
    )
    ap.add_argument(
        "--no-loudnorm",
        action="store_true",
        help="Skip audio loudness normalization. Default is on (-14 LUFS, -1 dBTP, LRA 11).",
    )
    ap.add_argument(
        "--height", type=int, default=1080,
        help="Output height for landscape final (default 1080). Use 1440 for native 1440p.",
    )
    ap.add_argument(
        "--fps", type=int, default=24,
        help="Output frame rate (default 24). Use 30 for screen-content/lessons.",
    )
    ap.add_argument(
        "--voice-enhance", action="store_true",
        help="Apply voice enhance + denoise (highpass, afftdn, presence EQ, light comp) before loudnorm.",
    )
    ap.add_argument(
        "--mudo", action="store_true",
        help="Zera o áudio (bloco sem fala: quem toca é a trilha).",
    )
    ap.add_argument(
        "--canvas", type=str, default=None, metavar="WxH",
        help="Fit each frame into a fixed canvas with letterbox/pillarbox (no crop). "
             "e.g. 2560x1440 to make 16:9 from a 16:10 source. Overrides --height scaling.",
    )
    args = ap.parse_args()

    edl_path = args.edl.resolve()
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")

    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    edit_dir = edl_path.parent
    out_path = args.output.resolve()
    # Unique per-output tag so concurrent renders in one edit_dir never collide
    # (clips dir, concat list, base file).
    tag = out_path.stem

    # 0. Corte suave (`"corte_suave": true` no EDL): mede as emendas de fala e acha o ponto de corte
    # antes de extrair. Rascunho e bloco mudo ficam como estão: não há o que suavizar.
    emendas = []
    if edl.get("corte_suave") and not args.draft and not args.mudo:
        import corte_suave
        emendas = corte_suave.planeja(edl, lambda p: resolve_path(p, edit_dir), fps=args.fps)
        corte_suave.ajusta(edl, emendas)
        print(f"corte suave: {corte_suave.resumo(emendas)}")

    # 1. Extract per-segment (auto-grade per range if EDL grade is "auto")
    segment_paths = extract_all_segments(
        edl, edit_dir, preview=args.preview, draft=args.draft,
        out_height=args.height, fps=args.fps, voice_enhance=args.voice_enhance,
        canvas=args.canvas, tag=tag, mudo=args.mudo,
    )
    if emendas or (edl.get("corte_suave") and (edl.get("zoom_motivo") or edl.get("zoom_lados") or edl.get("zoom_degraus")) and not args.draft and not args.mudo):
        import corte_suave
        corte_suave.aplica(edl, emendas, segment_paths, fps=args.fps,
                           qualidade="previa" if args.preview else "final",
                           filtro_som=VOICE_ENHANCE_CHAIN if args.voice_enhance else "")

    # 2. Concat → base
    kind = "base_draft" if args.draft else ("base_preview" if args.preview else "base")
    base_path = edit_dir / f"{kind}_{tag}.mp4"
    concat_segments(segment_paths, base_path, edit_dir, tag=tag)

    # 3. Subtitles: build if requested, resolve final path
    subs_path: Path | None = None
    if not args.no_subtitles:
        if args.build_subtitles:
            subs_path = edit_dir / "master.srt"
            build_master_srt(edl, edit_dir, subs_path)
        elif edl.get("subtitles"):
            subs_path = resolve_path(edl["subtitles"], edit_dir)
            if not subs_path.exists():
                print(f"warning: subtitles path in EDL does not exist: {subs_path}")
                subs_path = None

    # Sem libass o filtro `subtitles` não existe, e é o caso da maioria: o ffmpeg do
    # homebrew-core vem sem ele. Aí a legenda entra num passo depois, desenhada com
    # Pillow pelo legendar.py — mesma altura no quadro, nada pra instalar.
    subs_pil: Path | None = None
    if subs_path is not None and not tem_libass():
        subs_pil, subs_path = subs_path, None

    # 4. Composite (overlays + subtitles LAST) → intermediate (pre-loudnorm) path
    overlays = edl.get("overlays") or []
    if args.no_loudnorm:
        # Composite directly to final output
        build_final_composite(base_path, overlays, subs_path, out_path, edit_dir)
    else:
        # Composite to a temp file, then run loudnorm → final output
        tmp_composite = out_path.with_suffix(".prenorm.mp4")
        build_final_composite(base_path, overlays, subs_path, tmp_composite, edit_dir)
        print("loudness normalization → social-ready (-14 LUFS / -1 dBTP / LRA 11)")
        apply_loudnorm_two_pass(tmp_composite, out_path, preview=args.draft)
        tmp_composite.unlink(missing_ok=True)

    # Legenda POR ÚLTIMO, depois dos overlays e do loudnorm — a mesma ordem da regra 1,
    # só que num passo separado porque o desenho não é filtro do ffmpeg.
    if subs_pil is not None:
        import legendar
        sem = out_path.with_suffix(".semlegenda.mp4")
        out_path.replace(sem)
        if legendar.queimar(sem, subs_pil, out_path):
            sem.unlink(missing_ok=True)
        else:
            sem.replace(out_path)
            print(f"aviso: legenda não queimada; o .srt ficou em {subs_pil}")

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
