"""Âncora: o segundo em que uma coisa entra, dito pela fala.

    ancora.tempo(palavras, "meia hora")      # o começo da sequência
    ancora.resolve(plano, palavras, fim=12.4) # todo "{…}" do plano vira segundos

Cinco scripts de vídeo tinham cada um a sua cópia de "achar a palavra na fala", com sintaxes
diferentes, e por isso todo plano que queria cair na fala tinha que ser Python. Esta é a sintaxe
mais rica delas (a do `em` do eu-nao-gravei-esse-audio):

    'meia hora'   o começo da sequência          'labs>'   o fim dela
    '|quando'     o corte antes dela: no meio do vão com a palavra anterior, no máximo 0,25 s antes
    '#2'          a segunda ocorrência           '+0.1' / '-0.12'  desloca
    '2/dois'      tenta uma, depois a outra      'fim'     o fim da fala (`fim=`)
    número        passa direto

Palavra é dict com `text`/`start`/`end` (Whisper, Scribe), `tx`/`t0`/`t1` (o `mr.palavras`) ou
tupla (texto, início, fim).
"""
from __future__ import annotations

import re

SINTAXE = re.compile(r"^(\|)?(.+?)(>)?(?:#(\d+))?([+-]\d+(?:\.\d+)?)?$")
CHAVE = re.compile(r"\{([^{}]+)\}")
# Só campo de tempo é âncora: `{…}` num texto de card, num CSS ou num exemplo continua sendo texto.
# Numa lista (as janelas do bloco) todo item conta; num dict, só estas chaves (e o `tempos` da query).
TEMPO = {"t0", "t1", "t", "em", "ate", "inicio", "fim", "tempos"}


class Faltou(ValueError):
    """A âncora que a fala não tem."""


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def _palavra(w) -> tuple[str, float, float]:
    if isinstance(w, dict):
        tx = w.get("text", w.get("tx", w.get("word", "")))
        return tx, float(w.get("start", w.get("t0", 0))), float(w.get("end", w.get("t1", 0)))
    return w[0], float(w[1]), float(w[2])


def tempo(palavras: list, ancora, fim: float | None = None) -> float:
    """O segundo de uma âncora na fala. Âncora que a fala não tem é `Faltou`, não um número."""
    if isinstance(ancora, (int, float)):
        return float(ancora)
    m = SINTAXE.match(str(ancora).strip())
    if not m:
        raise Faltou(f"âncora vazia: {ancora!r}")
    corte, txt, ate_o_fim, n, desl = (m.group(1), m.group(2), m.group(3),
                                      int(m.group(4) or 1), float(m.group(5) or 0))
    if txt == "fim":
        if fim is None:
            raise Faltou("âncora 'fim' sem o fim da fala")
        return round(fim + desl, 3)
    ws = [_palavra(w) for w in palavras]
    ns = [_norm(w[0]) for w in ws]
    for alt in txt.split("/"):
        seq = [k for k in (_norm(x) for x in alt.split()) if k]
        if not seq:
            continue
        achados = [i for i in range(len(ns) - len(seq) + 1) if ns[i:i + len(seq)] == seq]
        if len(achados) < n:
            continue
        i = achados[n - 1]
        if ate_o_fim:
            t = ws[i + len(seq) - 1][2]
        elif corte:
            ini, ant = ws[i][1], ws[i - 1][2] if i else 0.0
            t = max((ant + ini) / 2, ini - .25)
        else:
            t = ws[i][1]
        return round(t + desl, 3)
    raise Faltou(f"âncora que a fala não tem: {ancora!r}")


def tem(obj, campo: bool = True) -> bool:
    """O plano pede alguma âncora (num campo de tempo)?"""
    if isinstance(obj, str):
        return campo and bool(CHAVE.search(obj))
    if isinstance(obj, dict):
        return any(tem(v, k in TEMPO) for k, v in obj.items())
    if isinstance(obj, list):
        return any(tem(v, campo) for v in obj)
    return False


def resolve(obj, palavras: list, fim: float | None = None, campo: bool = True):
    """Uma cópia do plano com cada "{âncora}" de campo de tempo trocada pelo segundo dela. O campo que
    é só a âncora vira número; a âncora no meio de um texto (uma lista de tempos) vira o número escrito."""
    if isinstance(obj, str):
        if not campo:
            return obj
        inteira = CHAVE.fullmatch(obj)
        if inteira:
            return tempo(palavras, inteira.group(1), fim)
        return CHAVE.sub(lambda m: f"{tempo(palavras, m.group(1), fim):g}", obj)
    if isinstance(obj, dict):
        return {k: resolve(v, palavras, fim, k in TEMPO) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v, palavras, fim, campo) for v in obj]
    return obj


def _autoteste() -> None:
    ws = [{"text": "Olá,", "start": 0.0, "end": 0.4}, {"text": "meia", "start": 1.0, "end": 1.2},
          {"text": "hora", "start": 1.3, "end": 1.6}, {"text": "meia", "start": 3.0, "end": 3.2}]
    assert tempo(ws, "meia hora") == 1.0 and tempo(ws, "meia hora>") == 1.6
    assert tempo(ws, "meia#2") == 3.0 and tempo(ws, "olá+0.1") == 0.1
    assert tempo(ws, "|meia") == 0.75, tempo(ws, "|meia")       # meio do vão 0.4–1.0, no máx. 0,25 antes
    assert tempo(ws, "xis/hora") == 1.3 and tempo(ws, "fim-1", fim=10) == 9.0 and tempo(ws, 2.5) == 2.5
    assert tempo([("a", 1, 2)], "a>") == 2.0
    p = resolve({"t0": "{meia}", "q": {"tempos": "{olá},{hora>}"}, "n": 3, "tx": "a{color:red}"}, ws)
    assert p == {"t0": 1.0, "q": {"tempos": "0,1.6"}, "n": 3, "tx": "a{color:red}"}, p
    assert not tem({"cards": [{"tx": "{nome}"}]}), "texto com chave não é âncora"
    assert resolve([["{meia}", "{hora>}"]], ws) == [[1.0, 1.6]]
    try:
        tempo(ws, "banana")
        raise AssertionError("âncora que não existe virou número")
    except Faltou:
        pass
    print("autoteste ok")


if __name__ == "__main__":
    _autoteste()
