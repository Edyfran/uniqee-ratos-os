"""O Transcript: a fala com tempo, palavra a palavra. Um leitor só pra fábrica inteira.

Todo helper que lê `transcripts/<nome>.json` passa por aqui, pra que a regra do que
é palavra falada more num lugar só:

- entrada sem `type` conta como palavra (o `spacing` e o `audio_event` não);
- palavra de duração zero (~1% dos tokens do Whisper e do Scribe) ganha PISO de 80 ms
  sem invadir a seguinte; colada na seguinte, ela entra junto com ela. Antes, uns
  leitores a jogavam fora e a legenda perdia o "Fala," da abertura e o "não" do meio.

Só biblioteca padrão: vai no kit do aluno e roda no Windows.

    palavras(fonte, ate=None)    as palavras faladas, em ordem
    frases(fonte, de, ate)       "[início-fim] texto", quebrando em silêncio ou troca de voz
    no_corte(fonte, trechos)     o transcript no tempo do vídeo cortado
    tempo_de_saida(trechos, t)   um instante da fonte no tempo do vídeo cortado

Na linha de comando, para o agente ler a fala sem carregar o JSON cru (uma linha por frase):

    python transcript.py frases <transcript.json|.srt> [--de S] [--ate S]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PISO = 0.08  # segundos; medido em 08/09/2026 no "Fala, ninja" que o corte comia

# O glossário de marca: o que o Whisper ouve errado -> o nome certo. Mora aqui, e não no
# renderer, porque a fala passa por três caminhos (cards da fala, legenda lisa de .srt e o
# captions_viral) e cada um corrigia por conta própria: o cards.json saía "CLÁUDIA" e quem
# lia o plano ou o .srt via o erro. O aluno acrescenta os dele em `marca/glossario.json`
# ({"errado": "Certo"}), na raiz da fábrica.
GLOSSARIO = {
    "cloud": "Claude", "clode": "Claude", "cláudio": "Claude", "claudio": "Claude",
    "cláudia": "Claude", "claudia": "Claude",   # "comenta CLAUDE aqui embaixo"
    "metaedge": "Meta Ads", "antrop": "Anthropic",
    # Nome de ferramenta que o Whisper nunca ouviu. Os dois primeiros saíram na
    # legenda do short de webhook: "NO NTYN VOCÊ PÕE" e "fingindo ser a QWi-Fi".
    "ntyn": "n8n", "n8m": "n8n", "enoiteene": "n8n",
    "qwifi": "Kiwify", "kiwifi": "Kiwify", "qwi-fi": "Kiwify", "kiwifai": "Kiwify",
    "ngrock": "ngrok", "engrok": "ngrok",
}
try:
    _g = Path(__file__).resolve().parents[3] / "marca" / "glossario.json"
    GLOSSARIO.update({k.lower(): v for k, v in json.loads(_g.read_text(encoding="utf-8")).items()})
except (OSError, ValueError, AttributeError):
    pass    # sem arquivo, ou arquivo torto: vale o glossário de cima


def corrigir_termo(txt: str) -> str:
    """A palavra com o nome de marca no lugar do erro, mantendo a pontuação da ponta."""
    # o Whisper põe aspas na palavra ("cloud") e o glossário só acha o núcleo
    nucleo, cabeca, cauda = txt.strip(), "", ""
    while nucleo and nucleo[0] in "\"'“”‘’«":
        cabeca, nucleo = cabeca + nucleo[0], nucleo[1:]
    while nucleo and nucleo[-1] in ".,!?;:\"'“”‘’»":
        cauda, nucleo = nucleo[-1] + cauda, nucleo[:-1]
    return cabeca + GLOSSARIO.get(nucleo.lower(), nucleo) + cauda
SILENCIO = 0.5


def carrega(fonte) -> dict:
    """O documento inteiro. `fonte` é caminho, dict já carregado ou lista de palavras."""
    if isinstance(fonte, dict):
        return fonte
    if isinstance(fonte, list):
        return {"words": fonte}
    return json.loads(Path(fonte).read_text(encoding="utf-8"))


def palavras(fonte, ate: float | None = None) -> list[dict]:
    """As palavras faladas, em ordem de início, cada uma uma cópia com `start` < `end`."""
    ws = sorted((dict(w, start=float(w["start"]), end=float(w["end"]))
                 for w in carrega(fonte).get("words", [])
                 if w.get("type", "word") == "word" and w.get("start") is not None and w.get("end") is not None),
                key=lambda w: w["start"])
    for i, w in enumerate(ws):
        if w["end"] <= w["start"]:
            seguinte = ws[i + 1]["start"] if i + 1 < len(ws) else None
            folga = seguinte - w["start"] if seguinte is not None else PISO
            w["end"] = w["start"] + (min(PISO, folga) if folga > 0 else PISO)
    if ate is not None:
        ws = [dict(w, end=min(w["end"], ate)) for w in ws if w["start"] < ate]
    return ws


def frases(fonte, de: float | None = None, ate: float | None = None,
           silencio: float = SILENCIO) -> list[str]:
    """Uma linha por frase: `[início-fim] texto`. Aceita `.srt` também."""
    if isinstance(fonte, (str, Path)) and Path(fonte).suffix.lower() == ".srt":
        lista = _srt(Path(fonte))
    else:
        lista = agrupa(carrega(fonte).get("words", []), silencio)
    return [f"[{f['start']:07.2f}-{f['end']:07.2f}] {f['text']}" for f in lista
            if (de is None or f["end"] >= de) and (ate is None or f["start"] <= ate)]


def agrupa(words: list[dict], silencio: float = SILENCIO) -> list[dict]:
    """As entradas do transcript em frases {start, end, text, speaker_id}.

    Quebra em `spacing` maior que `silencio`, em buraco entre palavras maior que
    `silencio` e em troca de voz. `audio_event` entra entre parênteses.
    """
    frases_, atual = [], []

    def fecha():
        partes = []
        for w in atual:
            tx = (w.get("text") or "").strip()
            if tx and w.get("type") == "audio_event" and not tx.startswith("("):
                tx = f"({tx})"
            if tx:
                partes.append(tx)
        if partes:
            texto = re.sub(r" ([,.?!])", r"\1", " ".join(partes))
            frases_.append({"start": float(atual[0]["start"]),
                            "end": float(atual[-1].get("end", atual[-1]["start"])),
                            "text": texto, "speaker_id": atual[0].get("speaker_id")})
        atual.clear()

    fim_anterior = None
    for w in words:
        tipo = w.get("type", "word")
        if tipo == "spacing":
            if w.get("start") is not None and w.get("end") is not None and w["end"] - w["start"] >= silencio:
                fecha()
            continue
        if w.get("start") is None:
            continue
        voz = w.get("speaker_id")
        if atual and voz is not None and atual[0].get("speaker_id") is not None and voz != atual[0]["speaker_id"]:
            fecha()
        if fim_anterior is not None and w["start"] - fim_anterior >= silencio:
            fecha()
        atual.append(w)
        fim_anterior = w.get("end", w["start"])
    fecha()
    return frases_


def tempo_de_saida(trechos: list[dict], t: float) -> float:
    """Converte tempo da FONTE para tempo do vídeo cortado.

    As âncoras de card são medidas assistindo a live, mas o card pousa no clipe
    já cortado. Sem esta conversão o card entra deslocado exatamente pelo
    silêncio que o corte tirou. Fora de qualquer trecho mantido, cai na emenda
    mais próxima — é onde o card faria menos estrago.
    """
    acumulado = 0.0
    for tr in trechos:
        ini, fim = float(tr["start"]), float(tr["end"])
        if ini - 0.05 <= t <= fim + 0.05:
            return round(acumulado + (t - ini), 3)
        acumulado += fim - ini
    if not trechos:
        return 0.0
    perto = min(range(len(trechos)),
                key=lambda i: min(abs(t - float(trechos[i]["start"])),
                                  abs(t - float(trechos[i]["end"]))))
    antes = sum(float(x["end"]) - float(x["start"]) for x in trechos[:perto])
    # Depois do fim do trecho vizinho, o card entra NA emenda. Mandá-lo para o
    # começo do trecho o joga segundos para trás, em cima de outra frase.
    if t > float(trechos[perto]["end"]):
        antes += float(trechos[perto]["end"]) - float(trechos[perto]["start"])
    return round(antes, 3)


def no_corte(fonte, trechos: list[dict]) -> dict:
    """O transcript no tempo do vídeo cortado. Palavra cujo meio o corte tirou sai."""
    doc = carrega(fonte)
    ws = [{**w, "start": tempo_de_saida(trechos, float(w["start"])),
           "end": tempo_de_saida(trechos, float(w["end"]))}
          for w in doc["words"]
          if any(float(t["start"]) <= (float(w["start"]) + float(w["end"])) / 2 <= float(t["end"]) for t in trechos)]
    return {**doc, "words": ws}


def _srt(p: Path) -> list[dict]:
    blocos = re.findall(r"(\d\d):(\d\d):(\d\d)[,.](\d+) --> (\d\d):(\d\d):(\d\d)[,.](\d+)\s*\n(.+?)(?:\n\s*\n|\Z)",
                        p.read_text(encoding="utf-8", errors="replace"), re.S)
    seg = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 10 ** len(ms)
    return [{"start": seg(*b[:4]), "end": seg(*b[4:8]), "text": " ".join(b[8].split())} for b in blocos]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("frases", help="uma frase por linha, com o tempo: [início-fim] texto")
    f.add_argument("transcript", type=Path)
    f.add_argument("--de", type=float, help="só as frases que acabam depois deste segundo")
    f.add_argument("--ate", type=float, help="só as frases que começam antes deste segundo")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # o console do Windows é cp1252; a fala tem acento
    print("\n".join(frases(a.transcript, a.de, a.ate)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
