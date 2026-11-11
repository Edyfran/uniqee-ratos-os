"""O Transcript: a regra de palavra falada, as frases, o tempo no corte, e só biblioteca padrão."""
import ast
import json
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
import transcript as tr  # noqa: E402

W = lambda tx, a, b, **k: {"type": "word", "text": tx, "start": a, "end": b, **k}

# palavra de duração zero ganha o piso; colada na seguinte, entra junto com ela
ws = tr.palavras([W("Fala,", 0.0, 0.0), W("ninja", 0.5, 0.9), W("não", 1.2, 1.2), W("vai", 1.2, 1.5),
                  W("é", 2.0, 2.0), W("isso", 2.03, 2.3), {"type": "spacing", "text": " ", "start": 0.9, "end": 1.2}])
assert [w["text"] for w in ws] == ["Fala,", "ninja", "não", "vai", "é", "isso"], ws
assert ws[0]["end"] == tr.PISO  # folga grande: piso inteiro
assert abs(ws[2]["end"] - ws[2]["start"] - tr.PISO) < 1e-9  # colada: entra junto, com o piso
assert abs(ws[4]["end"] - 2.03) < 1e-9  # folga pequena: até a seguinte, sem invadir
assert all(w["end"] > w["start"] for w in ws)

# sem type conta; spacing e audio_event não; fora de ordem volta em ordem
ws = tr.palavras([{"text": "b", "start": 1, "end": 2}, W("a", 0, 0.5), {"type": "audio_event", "text": "riso", "start": 3, "end": 4}])
assert [w["text"] for w in ws] == ["a", "b"]
assert [w["text"] for w in tr.palavras([W("a", 0, 1), W("b", 2, 3)], ate=2.5)] == ["a", "b"]
assert tr.palavras([W("a", 0, 1), W("b", 2, 3)], ate=2.5)[-1]["end"] == 2.5
assert tr.palavras([W("a", 0, 1), W("b", 3, 4)], ate=2.5)[-1]["text"] == "a"

# frases: silêncio quebra; janela filtra; srt lê
doc = {"words": [W("Oi", 0, 0.3), W("gente", 0.35, 0.7), {"type": "spacing", "start": 0.7, "end": 1.5},
                 W("tudo", 1.5, 1.8), W("bem?", 1.85, 2.1)]}
assert tr.frases(doc) == ["[0000.00-0000.70] Oi gente", "[0001.50-0002.10] tudo bem?"], tr.frases(doc)
assert len(tr.frases(doc, de=1.0)) == 1
with tempfile.TemporaryDirectory() as d:
    srt = Path(d) / "a.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,500\nOlá\nmundo\n\n2\n00:00:03,000 --> 00:00:04,000\nnão\n", encoding="utf-8")
    assert tr.frases(srt) == ["[0001.00-0002.50] Olá mundo", "[0003.00-0004.00] não"], tr.frases(srt)
    j = Path(d) / "voz.json"
    j.write_text(json.dumps({"words": [W("ação", 0, 0.4)]}, ensure_ascii=False), encoding="utf-8")
    assert tr.palavras(j)[0]["text"] == "ação"

# linha de comando: `transcript.py frases` imprime o mesmo que a função, uma frase por linha, e a janela vale
import contextlib
import io
import subprocess
with tempfile.TemporaryDirectory() as d:
    j = Path(d) / "t.json"
    j.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert tr.main(["frases", str(j)]) == 0
    assert buf.getvalue() == "\n".join(tr.frases(doc)) + "\n", buf.getvalue()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tr.main(["frases", str(j), "--de", "1.0", "--ate", "5"])
    assert buf.getvalue() == "[0001.50-0002.10] tudo bem?\n", buf.getvalue()
    # e como programa, que é como o agente chama (a acentuação sai em utf-8)
    j.write_text(json.dumps({"words": [W("ação", 0, 0.4)]}, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(AQUI / "transcript.py"), "frases", str(j)], capture_output=True)
    assert r.returncode == 0 and r.stdout.decode("utf-8").replace("\r\n", "\n") == "[0000.00-0000.40] ação\n", (r.stdout, r.stderr)

# no corte: tempo de saída, e a palavra cujo meio o corte tirou sai
trechos = [{"start": 10, "end": 12}, {"start": 20, "end": 22}]
assert tr.tempo_de_saida(trechos, 21) == 3.0
nc = tr.no_corte({"words": [W("a", 10.5, 11), W("b", 15, 16), W("c", 20.5, 21)]}, trechos)
assert [(w["text"], w["start"]) for w in nc["words"]] == [("a", 0.5), ("c", 2.5)], nc

# glossário de marca: acha o núcleo mesmo com aspas e pontuação em volta ("cloud" no CTA saía errado)
assert tr.corrigir_termo('"cloud"') == '"Claude"', tr.corrigir_termo('"cloud"')
assert tr.corrigir_termo("“cloud”.") == "“Claude”."
assert tr.corrigir_termo("casa,") == "casa,"

# só biblioteca padrão: o kit do aluno roda no Windows
PADRAO = {"__future__", "argparse", "json", "re", "sys", "pathlib"}
importa = {n.name.split(".")[0] for no in ast.walk(ast.parse((AQUI / "transcript.py").read_text(encoding="utf-8")))
           if isinstance(no, ast.Import) for n in no.names}
importa |= {no.module.split(".")[0] for no in ast.walk(ast.parse((AQUI / "transcript.py").read_text(encoding="utf-8")))
            if isinstance(no, ast.ImportFrom) and no.module}
assert importa <= PADRAO, importa - PADRAO
print("ok")
