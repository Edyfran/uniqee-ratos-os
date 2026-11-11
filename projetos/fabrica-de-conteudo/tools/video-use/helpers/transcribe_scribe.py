"""Transcribe a video with ElevenLabs Scribe.

Extracts mono 16kHz audio via ffmpeg, uploads to Scribe with verbatim +
diarize + audio events + word-level timestamps, writes the full response
to <edit_dir>/transcripts/<video_stem>.json.

Modelo scribe_v2 desde 07/10/2026 (o v1 ficou travado aqui desde o começo). O v2 transcreve
como foi falado por padrão: falso começo, repetição e "é…" ficam no texto, que é o que o
corte precisa ver (o Whisper apaga e completa a palavra comida). --termos manda até 1000
nomes pra ele reconhecer melhor (cartas, marcas, apelidos): +20% no custo da transcrição.

Cached: if the output file already exists, the upload is skipped.

Usage:
    python helpers/transcribe.py <video_path>
    python helpers/transcribe.py <video_path> --edit-dir /custom/edit
    python helpers/transcribe.py <video_path> --language en
    python helpers/transcribe.py <video_path> --num-speakers 2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import ff


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MODELO = "scribe_v2"
PROIBIDO = set("<>{}[]\\")  # caracteres que a API recusa num termo


def termos_validos(termos: list[str]) -> list[str]:
    """Os limites da API: até 1000 termos, cada um com menos de 50 caracteres e até 5 palavras.
    Nome de carta "Personagem - Versão" vira dois termos: é assim que se fala, e cabe no limite."""
    vistos, ok = set(), []
    for t in (parte for termo in termos for parte in termo.split(" - ")):
        t = " ".join(t.split())
        if not t or len(t) >= 50 or len(t.split()) > 5 or PROIBIDO & set(t) or t.lower() in vistos:
            continue
        vistos.add(t.lower()); ok.append(t)
    return ok[:1000]


def chave(env: dict | None = None, arquivos: list[Path] | None = None) -> str:
    """A chave da ElevenLabs, ou "" se não há: sem chave não é erro, é só "não há Scribe"
    (é assim que o transcribe.py decide o adaptador). Os arquivos antes do ambiente, como sempre."""
    # A chave do projeto mora no .env.local da raiz do repo.
    for candidate in (arquivos if arquivos is not None else
                      [Path(__file__).resolve().parent.parent / ".env", Path(".env"),
                       Path(__file__).resolve().parents[3] / ".env.local"]):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "ELEVENLABS_API_KEY":
                    return v.strip().strip('"').strip("'")
    return (os.environ if env is None else env).get("ELEVENLABS_API_KEY", "")


def load_api_key() -> str:
    v = chave()
    if not v:
        sys.exit("ELEVENLABS_API_KEY not found in .env or environment")
    return v


def para_comum(payload: dict, language: str | None = None) -> dict:
    """O que o Scribe devolve no formato que o transcribe.py escreve (o dos três adaptadores):
    um falante só (a fala é solo; o speaker_1 que o Scribe inventa em ruído quebraria a frase),
    sem logprob nem caracteres. O `audio_event` fica: o transcript.py sabe lê-lo. Quem quer a
    diarização inteira roda este arquivo direto, que grava o JSON cru."""
    palavras = [{"type": w.get("type", "word"), "text": w.get("text", ""),
                 "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3),
                 "speaker_id": "speaker_0"}
                for w in payload.get("words", []) if "start" in w and "end" in w]
    return {
        "language": language or payload.get("language_code"),
        "language_probability": payload.get("language_probability"),
        "duration": palavras[-1]["end"] if palavras else None,
        "text": payload.get("text", ""),
        "words": palavras,
    }


def extract_audio(video_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    ff.run(cmd, quiet=True)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    termos: list[str] | None = None,
) -> dict:
    data: list[tuple[str, str]] = [
        ("model_id", MODELO),
        ("diarize", "true"),
        ("tag_audio_events", "true"),
        ("timestamps_granularity", "word"),
    ]
    if language:
        data.append(("language_code", language))
    if num_speakers:
        data.append(("num_speakers", str(num_speakers)))
    data += [("keyterms", t) for t in termos_validos(termos or [])]

    import requests   # aqui dentro: quem só importa o módulo (a escolha do adaptador) não paga

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")

    return resp.json()


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    termos: list[str] | None = None,
) -> Path:
    """Transcribe a single video. Returns path to transcript JSON.

    Cached: returns existing path immediately if the transcript already exists.
    """
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    if verbose:
        print(f"  extracting audio from {video.name}", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"{video.stem}.wav"
        extract_audio(video, audio)
        size_mb = audio.stat().st_size / (1024 * 1024)
        if verbose:
            print(f"  uploading {video.stem}.wav ({size_mb:.1f} MB)", flush=True)
        payload = call_scribe(audio, api_key, language, num_speakers, termos)

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a video with ElevenLabs Scribe")
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known. Improves diarization accuracy.",
    )
    ap.add_argument(
        "--termos",
        type=Path,
        default=None,
        help="Arquivo com um termo por linha (nomes de carta, marca, apelido) pra o Scribe reconhecer melhor.",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    api_key = load_api_key()

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
        termos=args.termos.read_text(encoding="utf-8").splitlines() if args.termos else None,
    )


if __name__ == "__main__":
    main()
