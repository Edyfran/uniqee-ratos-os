"""A transcrição escolhe o adaptador pela máquina e escreve sempre o mesmo Transcript.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_transcribe.py

Sem rede e sem modelo: a máquina, a chave e o Scribe são falsos.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import transcribe as tr
import transcribe_scribe as ts

MAC = ("darwin", "arm64")
SEM_MLX = lambda: False
COM_MLX = lambda: True

# o que a API do Scribe devolve, escrito à mão: ids de falante, logprob e o evento de áudio
SCRIBE = {
    "language_code": "por", "language_probability": 0.98, "text": "Oi tudo (risos)",
    "words": [
        {"text": "Oi", "start": 0.1, "end": 0.3, "type": "word", "speaker_id": "speaker_0", "logprob": -0.1},
        {"text": " ", "start": 0.3, "end": 0.4, "type": "spacing", "speaker_id": "speaker_0", "logprob": 0.0},
        {"text": "tudo", "start": 0.4, "end": 0.7001, "type": "word", "speaker_id": "speaker_1", "logprob": -0.2},
        {"text": "(risos)", "start": 0.8, "end": 1.2, "type": "audio_event", "speaker_id": "speaker_1"},
    ],
}
FORMA = {"type", "text", "start", "end", "speaker_id"}


def test_chave_do_scribe_escolhe_scribe():
    assert tr.escolhe_adaptador(chave="k", plataforma=MAC, tem_mlx=COM_MLX) == "scribe"
    assert tr.escolhe_adaptador(chave="k", plataforma=("linux", "x86_64"), tem_mlx=SEM_MLX) == "scribe"


def test_sem_chave_o_mac_arm_com_mlx_escolhe_mlx():
    assert tr.escolhe_adaptador(chave="", plataforma=MAC, tem_mlx=COM_MLX) == "mlx"


def test_o_resto_cai_no_whisper():
    assert tr.escolhe_adaptador(chave="", plataforma=MAC, tem_mlx=SEM_MLX) == "whisper"
    assert tr.escolhe_adaptador(chave="", plataforma=("darwin", "x86_64"), tem_mlx=COM_MLX) == "whisper"
    assert tr.escolhe_adaptador(chave="", plataforma=("win32", "AMD64"), tem_mlx=COM_MLX) == "whisper"


def test_o_adaptador_forcado_vence_a_maquina():
    assert tr.escolhe_adaptador("whisper", chave="k", plataforma=MAC, tem_mlx=COM_MLX) == "whisper"
    assert tr.escolhe_adaptador("mlx", chave="k", plataforma=MAC, tem_mlx=COM_MLX) == "mlx"
    assert tr.escolhe_adaptador("auto", chave="", plataforma=MAC, tem_mlx=COM_MLX) == "mlx"
    try:
        tr.escolhe_adaptador("vosk")
    except ValueError as e:
        assert "scribe" in str(e) and "mlx" in str(e) and "whisper" in str(e)
    else:
        raise AssertionError("adaptador que não existe passou")


def test_a_chave_vem_do_arquivo_ou_do_ambiente(tmp: Path):
    env = tmp / ".env.local"
    env.write_text('# nada\nOUTRA=1\nELEVENLABS_API_KEY="abc"\n', encoding="utf-8")
    assert ts.chave(env={}, arquivos=[env]) == "abc"
    assert ts.chave(env={"ELEVENLABS_API_KEY": "xyz"}, arquivos=[tmp / "nao-existe"]) == "xyz"
    assert ts.chave(env={}, arquivos=[tmp / "nao-existe"]) == ""   # sem chave não é erro: é só "não há Scribe"


def test_scribe_vira_o_transcript_comum():
    r = ts.para_comum(SCRIBE, language="pt")
    assert set(r) == {"language", "language_probability", "duration", "text", "words"}
    assert r["language"] == "pt" and r["text"] == "Oi tudo (risos)" and r["duration"] == 1.2
    assert [w["type"] for w in r["words"]] == ["word", "spacing", "word", "audio_event"]
    assert all(set(w) == FORMA for w in r["words"]), "sobrou campo do Scribe (logprob?)"
    assert {w["speaker_id"] for w in r["words"]} == {"speaker_0"}, "a fala solo é um falante só"
    assert r["words"][2]["end"] == 0.7
    assert ts.para_comum(SCRIBE)["language"] == "por"   # sem idioma pedido, o que o Scribe achou


def test_o_comum_do_whisper_poe_espaco_nas_lacunas():
    r = tr._comum([("Oi", 0.0, 0.3), ("gente", 0.5, 0.9)], "pt", 0.99, 1.0)
    assert [w["type"] for w in r["words"]] == ["word", "spacing", "word"]
    assert r["words"][1]["start"] == 0.3 and r["words"][1]["end"] == 0.5
    assert r["text"] == "Oi gente" and r["language"] == "pt" and all(set(w) == FORMA for w in r["words"])


def test_mlx_vira_o_transcript_comum():
    saida = {"language": "pt", "text": " Oi gente", "segments": [
        {"words": [{"word": " Oi", "start": 0.0, "end": 0.3, "probability": 0.9}]},
        {"words": [{"word": " gente", "start": 0.5, "end": 0.9, "probability": 0.8}, {"word": " ", "start": 0.9, "end": 0.9}]},
    ]}
    r = tr._do_mlx(saida, "pt")
    assert [w["text"] for w in r["words"] if w["type"] == "word"] == ["Oi", "gente"]
    assert r["language"] == "pt" and r["duration"] == 0.9 and all(set(w) == FORMA for w in r["words"])


def test_o_modelo_do_mlx_e_o_large_v3():
    assert tr._repo_mlx("large-v3") == "mlx-community/whisper-large-v3-mlx"
    assert tr._repo_mlx("outro/repo") == "outro/repo"


def _com_cache(raiz: Path):
    ant = os.environ.get("HF_HUB_CACHE")
    os.environ["HF_HUB_CACHE"] = str(raiz)
    return ant


def test_modelo_baixado_conta_o_adaptador(tmp: Path):
    ant = _com_cache(tmp)
    try:
        assert tr.modelo_baixado(adaptador="scribe") is True, "o Scribe não baixa nada"
        assert tr.modelo_baixado(adaptador="whisper") is False and tr.modelo_baixado(adaptador="mlx") is False
        (tmp / "models--Systran--faster-whisper-large-v3/snapshots/a").mkdir(parents=True)
        (tmp / "models--Systran--faster-whisper-large-v3/snapshots/a/model.bin").write_bytes(b"x")
        (tmp / "models--mlx-community--whisper-large-v3-mlx/snapshots/a").mkdir(parents=True)
        (tmp / "models--mlx-community--whisper-large-v3-mlx/snapshots/a/weights.safetensors").write_bytes(b"x")
        assert tr.modelo_baixado(adaptador="whisper") is True and tr.modelo_baixado(adaptador="mlx") is True
    finally:
        os.environ.pop("HF_HUB_CACHE") if ant is None else os.environ.__setitem__("HF_HUB_CACHE", ant)


def _troca(**novos):
    velhos = {k: getattr(tr, k) for k in novos}
    for k, v in novos.items():
        setattr(tr, k, v)
    return lambda: [setattr(tr, k, v) for k, v in velhos.items()]


def test_scribe_que_falha_cai_no_local_com_uma_linha_de_aviso():
    def cai(*a, **k):
        raise RuntimeError("Scribe returned 429: quota")
    desfaz = _troca(_scribe=cai, _local=lambda *a, **k: {"words": [], "feita": "local"})
    aviso = io.StringIO()
    try:
        with contextlib.redirect_stderr(aviso):
            r = tr._transcribe_audio(Path("x.wav"), "large-v3", "cpu", "int8", "pt", adaptador="scribe")
    finally:
        desfaz()
    assert r["feita"] == "local"
    linhas = [l for l in aviso.getvalue().splitlines() if l.strip()]
    assert len(linhas) == 1 and "Scribe" in linhas[0] and "429" in linhas[0], linhas


def test_o_adaptador_pedido_chega_no_adaptador(tmp: Path):
    vistos = []
    desfaz = _troca(extract_audio=lambda v, d: d.write_bytes(b""),
                    _transcribe_audio=lambda *a, **k: vistos.append(k.get("adaptador")) or {"words": []})
    try:
        video = tmp / "voz.wav"
        video.write_bytes(b"")
        tr.transcribe_one(video, tmp, verbose=False, adaptador="mlx")
        (tmp / "transcripts" / "voz.json").unlink()
        tr.transcribe_one(video, tmp, verbose=False)
        (tmp / "transcripts" / "voz.json").unlink()
        sys.argv = ["transcribe.py", str(video), "--edit-dir", str(tmp), "--adaptador", "whisper"]
        tr.main()
    finally:
        desfaz()
    assert vistos == ["mlx", "auto", "whisper"], vistos


def main() -> int:
    casos = [(n[5:].replace("_", " "), f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    falhas = []
    for nome, caso in casos:
        try:
            if caso.__code__.co_varnames[:1] == ("tmp",):
                with tempfile.TemporaryDirectory() as d:
                    caso(Path(d))
            else:
                caso()
            print(f"  ok   {nome}")
        except Exception as e:
            falhas.append(nome)
            print(f"  FALHA {nome}: {e!r}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
