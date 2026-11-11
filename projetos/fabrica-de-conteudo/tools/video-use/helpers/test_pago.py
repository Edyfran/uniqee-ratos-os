"""O Pago: paga uma vez por conteúdo, recusa acima do teto, registra tudo. Sem rede: o adapter é falso."""
import ast
import json
import os
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

with tempfile.TemporaryDirectory() as d:
    os.environ["PAGO_PASTA"] = str(Path(d) / "pago")
    import pago

    chamadas = []

    def gera(destino: Path, conteudo=b"voz", usd=0.02):
        chamadas.append(destino)
        destino.write_bytes(conteudo)
        return usd

    # paga na primeira, reaproveita na segunda: o mesmo texto, voz e take
    saida = Path(d) / "a.mp3"
    p = pago.faz("elevenlabs", "voz", ["oi", "voz1", {"take": 1}], gera, sufixo=".mp3", estimativa=0.03, saida=saida)
    assert p == saida and saida.read_bytes() == b"voz" and len(chamadas) == 1
    saida.unlink()
    pago.faz("elevenlabs", "voz", ["oi", "voz1", {"take": 1}], gera, sufixo=".mp3", estimativa=0.03, saida=saida)
    assert len(chamadas) == 1 and saida.read_bytes() == b"voz", "pagou de novo o mesmo conteúdo"

    # outro take, outro texto: paga
    pago.faz("elevenlabs", "voz", ["oi", "voz1", {"take": 2}], gera, sufixo=".mp3")
    pago.faz("elevenlabs", "voz", ["oi!", "voz1", {"take": 1}], gera, sufixo=".mp3")
    assert len(chamadas) == 3

    # o arquivo entra pelo conteúdo, não pelo caminho nem pela data
    f1, f2 = Path(d) / "x.png", Path(d) / "y.png"
    f1.write_bytes(b"foto"); f2.write_bytes(b"foto")
    pago.faz("openai", "capa", ["prompt", f1], gera, sufixo=".jpg")
    pago.faz("openai", "capa", ["prompt", f2], gera, sufixo=".jpg")
    assert len(chamadas) == 4, "mesma foto em outro caminho pagou de novo"
    f2.write_bytes(b"outra")
    pago.faz("openai", "capa", ["prompt", f2], gera, sufixo=".jpg")
    assert len(chamadas) == 5, "foto nova não pagou"

    # dict em ordem diferente é o mesmo pedido
    pago.faz("higgsfield", "cena", [{"a": 1, "b": 2}], gera, sufixo=".mp4")
    pago.faz("higgsfield", "cena", [{"b": 2, "a": 1}], gera, sufixo=".mp4")
    assert len(chamadas) == 6

    # portão: estimativa acima do teto recusa sem chamar
    try:
        pago.faz("higgsfield", "cena", ["cara"], gera, sufixo=".mp4", estimativa=3.0, teto=1.0)
        raise AssertionError("passou do teto")
    except pago.Recusado as e:
        assert "3.00" in str(e) and "1.00" in str(e), e
    assert len(chamadas) == 6
    # falhou no meio: não guarda, e a próxima tenta de novo
    def quebra(destino):
        destino.write_bytes(b"pela metade")
        raise RuntimeError("rede caiu")
    try:
        pago.faz("openai", "capa", ["falha"], quebra, sufixo=".jpg")
    except RuntimeError:
        pass
    pago.faz("openai", "capa", ["falha"], gera, sufixo=".jpg")
    assert len(chamadas) == 7

    # novo=True paga mesmo com o guardado
    pago.faz("elevenlabs", "voz", ["oi", "voz1", {"take": 1}], gera, sufixo=".mp3", novo=True)
    assert len(chamadas) == 8

    # registro: toda passada, paga ou reaproveitada, e o que vem de fora (HeyGen pelo MCP)
    pago.registra("heygen", "avatar", creditos=13, usd=13 * 0.049, estimado=True, fonte="v1.mp4")
    linhas = [json.loads(l) for l in pago.REGISTRO.read_text(encoding="utf-8").splitlines()]
    assert sum(1 for l in linhas if l.get("reuso")) == 3, linhas
    r = pago.resumo(dias=1)
    assert r["elevenlabs"]["pagas"] == 4 and r["elevenlabs"]["reusos"] == 1, r
    assert abs(r["elevenlabs"]["usd"] - 0.08) < 1e-9, r
    assert r["heygen"]["creditos"] == 13 and abs(r["heygen"]["usd"] - 0.637) < 1e-9, r

    n = len(chamadas)
    # sem teto do chamador, vale o do ambiente (padrão US$ 5); sem estimativa o portão não age
    os.environ.pop("PAGO_TETO_USD", None)
    try:
        pago.faz("higgsfield", "cena", ["cara2"], gera, sufixo=".mp4", estimativa=6.0)
        raise AssertionError("passou do teto padrão")
    except pago.Recusado as e:
        assert "PAGO_TETO_USD" in str(e), e
    os.environ["PAGO_TETO_USD"] = "10"
    pago.faz("higgsfield", "cena", ["cara2"], gera, sufixo=".mp4", estimativa=6.0)
    os.environ.pop("PAGO_TETO_USD")
    assert len(chamadas) == n + 1
    pago.faz("higgsfield", "cena", ["cara3"], gera, sufixo=".mp4")
    assert len(chamadas) == n + 2

# só biblioteca padrão: vai no kit do aluno e roda no Windows
arv = ast.parse((AQUI / "pago.py").read_text(encoding="utf-8"))
mods = {n.name.split(".")[0] for x in ast.walk(arv) if isinstance(x, ast.Import) for n in x.names}
mods |= {x.module.split(".")[0] for x in ast.walk(arv) if isinstance(x, ast.ImportFrom) and x.module}
assert mods <= {"__future__", "hashlib", "json", "os", "shutil", "time", "pathlib", "typing"}, mods
print("ok")
