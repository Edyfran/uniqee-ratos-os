"""Transcribe a video (Scribe-compatible output). O adaptador sai da máquina:

    scribe   há ELEVENLABS_API_KEY (no ambiente ou no .env.local da raiz): a API da ElevenLabs, pago
    mlx      Mac com chip Apple e mlx-whisper instalado: o large-v3 na GPU, local e de graça
    whisper  o resto: faster-whisper large-v3 na CPU, local e de graça

`--adaptador` força um deles. Scribe que falha (rede, cota) cai no local com uma linha de aviso.
Os três escrevem o MESMO JSON, o que o resto do pipeline lê:

    {"language": "en", "text": "...",
     "words": [{"type": "word", "text": "Hello", "start": 0.12, "end": 0.41,
                "speaker_id": "speaker_0"}, ...]}

Downstream (pack_transcripts.py, render.py) only need `words` with
`type == "word"` and `text/start/end`. Speaker diarization is collapsed to a
single speaker (these are solo talking-head/lesson recordings).

Why local Whisper too: no API key, no cost, runs on-device.
Tradeoff: vanilla Whisper tends to normalize away disfluencies ("um", "uh").
We counter that with `hotwords` seeded with fillers + word-level timestamps
+ VAD, which keeps most of them. Silence-gap cutting works
regardless, since gaps come from word start/end deltas.

Usage:
    python helpers/transcribe.py <video_path>
    python helpers/transcribe.py <video_path> --edit-dir /custom/edit
    python helpers/transcribe.py <video_path> --language en
    python helpers/transcribe.py <video_path> --model small
    python helpers/transcribe.py <video_path> --adaptador whisper

Model is chosen via (highest priority first): --model, env
VIDEO_USE_WHISPER_MODEL, else the default below. CPU/int8 by default; override
with env VIDEO_USE_WHISPER_DEVICE / VIDEO_USE_WHISPER_COMPUTE.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import ff

# O modelo de transcrição é UM: o que a fábrica chama, o padrão daqui, a skill e o INSTALAR.md
# dizem o mesmo nome e o mesmo tamanho. large-v3 multilíngue (não ".en": o inglês só devolve lixo
# em áudio PT) acerta o português falado melhor que o medium, e o faster-whisper dele pesa
# 2,9 GB no disco (medido em ~/.cache/huggingface). Baixa uma vez, no primeiro vídeo.
# Para velocidade, "small" ou "medium" via VIDEO_USE_WHISPER_MODEL ou --model.
MODELO_PADRAO = "large-v3"
MODELO_GB = 3
DEFAULT_MODEL = os.environ.get("VIDEO_USE_WHISPER_MODEL", MODELO_PADRAO)
DEFAULT_DEVICE = os.environ.get("VIDEO_USE_WHISPER_DEVICE", "cpu")
DEFAULT_COMPUTE = os.environ.get("VIDEO_USE_WHISPER_COMPUTE", "int8")
# Language: default Portuguese (primary user). Set "" / "auto" to auto-detect,
# or any ISO code. CLI --language overrides this.
DEFAULT_LANG = os.environ.get("VIDEO_USE_WHISPER_LANG", "pt") or None
if DEFAULT_LANG in ("", "auto", "none"):
    DEFAULT_LANG = None

# Seed prompt biases Whisper toward transcribing disfluencies verbatim instead
# of silently cleaning them up. This is the single most important knob for
# filler-word editing. Per-language so PT fillers ("é", "tipo", "né") survive.
FILLER_PROMPTS = {
    "pt": "Então, é, tipo, né, hum, ãã, assim, sabe, quer dizer, "
          "bom, na verdade, basicamente, aí, então tá.",
    "en": "Okay, so, um, you know, like, uh, I mean, well, hmm, "
          "actually, basically, right, so yeah, uh-huh.",
}


def _filler_prompt(lang: str | None) -> str:
    return FILLER_PROMPTS.get((lang or "en").lower(), FILLER_PROMPTS["en"])


# Nomes que o canal fala o tempo todo e o whisper erra ("cloud code").
TERMOS = ("Claude Code, Claude, Anthropic, n8n, Kiwify, ngrok, ChatGPT, MCP, "
          "Composio, Hermes Agent, vibe coding, JSON, localhost.")


def _dica(lang: str | None) -> str:
    """Vai no `hotwords`, que entra em TODA janela de 30s. Era `initial_prompt`,
    que só valia na primeira: com `condition_on_previous_text=False` o
    faster-whisper descarta o prompt depois dela, e o resto da gravação saía sem
    os fillers que o `clean_edl` corta. Medido em 5 min de live, large-v3:
    fillers depois dos 30s 21 -> 32, "Claude" 0 -> 6 de 8 (o resto seguia
    "cloud"), nenhum termo da lista inventado. Custo: ~50% mais tempo."""
    return f"{_filler_prompt(lang)} {TERMOS}"

# Module-level model cache. CTranslate2 inference is thread-safe, so a single
# shared model serves transcribe_batch.py's parallel workers without N copies
# in RAM. Guarded so only one thread pays the load cost.
_MODEL_CACHE: dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def load_api_key() -> str:
    """Compatibility shim. The Scribe transcriber needed an API key; the local
    Whisper backend does not. transcribe_batch.py imports this symbol, so it
    must keep existing. Returns an empty string."""
    return ""


ADAPTADORES = ("scribe", "mlx", "whisper")


def _tem_chave() -> str:
    try:
        import transcribe_scribe
    except ImportError:   # o kit de aulas não leva o Scribe
        return ""
    return transcribe_scribe.chave()


def _tem_mlx() -> bool:
    try:
        import mlx_whisper  # noqa: F401
    except Exception:          # instalado e quebrado (sem Metal) também cai no faster-whisper
        return False
    return True


def escolhe_adaptador(forcado: str | None = None, chave: str | None = None,
                      plataforma: tuple[str, str] | None = None, tem_mlx=_tem_mlx) -> str:
    """Quem transcreve nesta máquina: o forçado; senão o Scribe, se há chave; senão o mlx, num Mac
    com chip Apple que o tem instalado; senão o faster-whisper. `chave` e `plataforma` só existem
    para o teste trocar a máquina."""
    if forcado and forcado != "auto":
        if forcado not in ADAPTADORES:
            raise ValueError(f"adaptador {forcado!r} não existe; use auto, {', '.join(ADAPTADORES)}")
        return forcado
    if (_tem_chave() if chave is None else chave):
        return "scribe"
    if (plataforma or (sys.platform, platform.machine())) == ("darwin", "arm64") and tem_mlx():
        return "mlx"
    return "whisper"


def _repo_mlx(nome: str) -> str:
    """O repositório do modelo no mlx: o `large-v3` é o mesmo que o faster-whisper carrega."""
    return nome if "/" in nome else f"mlx-community/whisper-{nome}-mlx"


def modelo_baixado(nome: str = MODELO_PADRAO, adaptador: str = "auto") -> bool:
    """O modelo já está no cache do Hugging Face? Só diz se falta baixar (o aviso antes do 1º vídeo).
    O Scribe não baixa nada."""
    adaptador = escolhe_adaptador(adaptador)
    if adaptador == "scribe":
        return True
    raiz = Path(os.environ.get("HF_HUB_CACHE")
                or Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub")
    if adaptador == "mlx":
        return any(raiz.glob(f"models--{_repo_mlx(nome).replace('/', '--')}/snapshots/*/weights.*"))
    return any(raiz.glob(f"models--Systran--faster-whisper-{nome}/snapshots/*/model.bin"))


def _get_model(model_name: str, device: str, compute_type: str):
    key = f"{model_name}|{device}|{compute_type}"
    cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            sys.exit(
                "o faster-whisper não está instalado. Rode `uv sync` na pasta do kit "
                "(ou `uv add faster-whisper`) e tente de novo."
            )
        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
        except Exception as erro:
            sys.exit(
                f"não consegui carregar o modelo de transcrição {model_name} "
                f"(baixa uma vez, ~{MODELO_GB} GB): {erro}"
            )
        _MODEL_CACHE[key] = model
        return model


def extract_audio(video_path: Path, dest: Path) -> None:
    # Normalize loud + level BEFORE transcription so whisper word-timestamps land
    # precisely on word edges. Quiet/variable audio makes faster-whisper report word
    # `end`s early (and VAD trim consonant tails) -> silence-cut clips mid-word.
    #   loudnorm  -> consistent perceived loudness (I=-14)
    #   dynaudnorm-> lifts quiet passages so soft consonants (s/t/d tails) stay audible
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-af", ff.TRANSCRICAO_AF,
        "-c:a", "pcm_s16le",
        str(dest),
    ]
    ff.run(cmd, quiet=True)


def _comum(palavras, language: str | None, probabilidade, duracao) -> dict:
    """O Transcript que os três adaptadores escrevem. `palavras` é (texto, início, fim) em ordem."""
    words: list[dict] = []
    text_parts: list[str] = []
    prev_end: float | None = None
    for raw, start, end in palavras:
        raw = (raw or "").strip()
        if not raw:
            continue
        start, end = float(start), float(end)
        # Synthesize a 'spacing' token in gaps so pack_transcripts.py
        # phrase-breaking has the same shape it expects from Scribe. The
        # gap-from-prev-end path also handles this, but emitting spacing
        # keeps the JSON maximally Scribe-like.
        if prev_end is not None and start - prev_end > 0.0:
            words.append({
                "type": "spacing",
                "text": " ",
                "start": round(prev_end, 3),
                "end": round(start, 3),
                "speaker_id": "speaker_0",
            })
        words.append({
            "type": "word",
            "text": raw,
            "start": round(start, 3),
            "end": round(end, 3),
            "speaker_id": "speaker_0",
        })
        text_parts.append(raw)
        prev_end = end
    return {
        "language": language or "en",
        "language_probability": probabilidade,
        "duration": duracao,
        "text": " ".join(text_parts),
        "words": words,
    }


def _do_mlx(saida: dict, language: str | None) -> dict:
    palavras = [(w.get("word"), w["start"], w["end"])
                for seg in saida.get("segments", []) for w in seg.get("words") or []]
    return _comum(palavras, saida.get("language") or language, None, palavras[-1][2] if palavras else None)


def _mlx(audio_path: Path, model_name: str, language: str | None) -> dict:
    try:
        import mlx_whisper
    except ImportError:
        sys.exit("o mlx-whisper não está instalado. Rode `uv add mlx-whisper` e tente de novo.")
    # sem VAD nem hotwords (o mlx não tem): a dica entra como prompt da primeira janela
    saida = mlx_whisper.transcribe(
        str(audio_path), path_or_hf_repo=_repo_mlx(model_name), language=language,
        word_timestamps=True, condition_on_previous_text=False, initial_prompt=_dica(language),
    )
    return _do_mlx(saida, language)


def _scribe(audio_path: Path, language: str | None, num_speakers: int | None) -> dict:
    import transcribe_scribe as ts
    chave = ts.chave()
    if not chave:
        raise RuntimeError("não achei ELEVENLABS_API_KEY")
    return ts.para_comum(ts.call_scribe(audio_path, chave, language, num_speakers), language)


def _local(audio_path: Path, model_name: str, device: str, compute_type: str,
           language: str | None) -> dict:
    """Quem transcreve sem rede nem chave nesta máquina: o mlx se der, senão o faster-whisper."""
    if escolhe_adaptador(chave="") == "mlx":
        return _mlx(audio_path, model_name, language)
    return _whisper(audio_path, model_name, device, compute_type, language)


def _transcribe_audio(
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    language: str | None,
    adaptador: str = "auto",
    num_speakers: int | None = None,
) -> dict:
    """Transcreve com o adaptador que a máquina pede (ou o forçado). O Scribe que falha cai no local."""
    nome = escolhe_adaptador(adaptador)
    if nome == "scribe":
        try:
            return _scribe(audio_path, language, num_speakers)
        except Exception as erro:
            print(f"aviso: o Scribe falhou ({str(erro)[:120]}); transcrevendo no local", file=sys.stderr)
            return _local(audio_path, model_name, device, compute_type, language)
    if nome == "mlx":
        return _mlx(audio_path, model_name, language)
    return _whisper(audio_path, model_name, device, compute_type, language)


def _whisper(
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    language: str | None,
) -> dict:
    model = _get_model(model_name, device, compute_type)

    # English-only models (".en") reject a language arg of anything else.
    lang = language
    if model_name.endswith(".en"):
        lang = "en"

    segments, info = model.transcribe(
        str(audio_path),
        language=lang,
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False,  # avoids runaway repetition loops
        hotwords=_dica(lang),
        beam_size=5,
    )

    palavras = ((w.word, w.start, w.end) for seg in segments for w in getattr(seg, "words", None) or [])
    return _comum(palavras, getattr(info, "language", lang), getattr(info, "language_probability", None),
                  getattr(info, "duration", None))


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str | None = None,  # ignored; kept for signature compatibility
    language: str | None = DEFAULT_LANG,
    num_speakers: int | None = None,  # só o Scribe usa; o Transcript sai com um falante
    model_name: str = DEFAULT_MODEL,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE,
    verbose: bool = True,
    adaptador: str = "auto",
) -> Path:
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    # A fonte refeita no mesmo nome (a voz gerada de novo) invalida a transcrição: o
    # cache só pelo nome devolvia o que a voz velha disse.
    if out_path.exists() and out_path.stat().st_mtime >= video.stat().st_mtime:
        if verbose:
            print(f"cached: {out_path}")
        return out_path

    if verbose:
        print(f"transcribing {video.name} with {escolhe_adaptador(adaptador)} [{model_name}] ...")
    t0 = time.time()

    with tempfile.TemporaryDirectory() as td:
        audio_path = Path(td) / "audio.wav"
        extract_audio(video, audio_path)
        result = _transcribe_audio(audio_path, model_name, device, compute_type, language,
                                   adaptador=adaptador, num_speakers=num_speakers)

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbose:
        n = sum(1 for w in result["words"] if w.get("type") == "word")
        print(f"  -> {out_path}  ({n} words, {time.time() - t0:.1f}s)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Transcribe a video (Scribe-compatible JSON): Scribe, mlx or faster-whisper"
    )
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument("--edit-dir", type=Path, default=None,
                    help="Edit output directory (default: <video_parent>/edit)")
    ap.add_argument("--language", type=str, default=DEFAULT_LANG,
                    help=f"ISO language code (default: {DEFAULT_LANG or 'auto'}). "
                         "Pass 'auto' to force detection.")
    ap.add_argument("--num-speakers", type=int, default=None,
                    help="Só o adaptador scribe usa. Kept for CLI compatibility.")
    ap.add_argument("--adaptador", choices=("auto", *ADAPTADORES), default="auto",
                    help="Quem transcreve. auto: scribe se há ELEVENLABS_API_KEY, senão mlx num Mac "
                         "com chip Apple, senão faster-whisper.")
    ap.add_argument("--model", type=str, default=DEFAULT_MODEL,
                    help=f"faster-whisper model (default: {DEFAULT_MODEL}). "
                         "e.g. small.en, medium.en, large-v3")
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()

    lang = args.language
    if lang in ("", "auto", "none"):
        lang = None

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        language=lang,
        model_name=args.model,
        num_speakers=args.num_speakers,
        adaptador=args.adaptador,
    )


if __name__ == "__main__":
    main()
