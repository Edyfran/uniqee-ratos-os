"""O Pago: todo passo que custa dinheiro passa por aqui.

Uma chamada faz o que cada script fazia sozinho, e quase sempre mal (14/10/2026: cache pelo nome
do arquivo, portão em poucos, o custo em quatro formatos ou em lugar nenhum):

- a chave é o CONTEÚDO do que entra (texto, prompt, voz, take, os bytes de cada arquivo),
  nunca o nome nem a data: o mesmo pedido não paga duas vezes, e pedido novo não vira o velho;
- o portão: estimativa acima do teto recusa antes de chamar;
- o que saiu é guardado e copiado pra saída; o que falhou no meio não fica;
- toda passada vai num registro só, paga ou reaproveitada, e o placar lê dali.

    faz(fornecedor, o_que, partes, chama, sufixo=...)   chama(destino) grava o resultado e devolve o US$ real
    registra(fornecedor, o_que, usd=..., creditos=...)  o que não passa pelo faz (a HeyGen pelo MCP)
    resumo(dias)                                        por fornecedor: pagas, reusos, US$, créditos

O take entra nas partes: "a mesma fala, take 2" é outra chave, então o cache nunca impede pedir
outra leitura. Só biblioteca padrão: vai no kit do aluno e roda no Windows.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable

PASTA = Path(os.environ.get("PAGO_PASTA") or Path.home() / ".cache" / "pago")
REGISTRO = PASTA / "registro.jsonl"


class Recusado(Exception):
    """O portão: a estimativa passou do teto."""


def chave(*partes) -> str:
    """Hash do conteúdo de cada parte. Path vale pelos bytes; dict e lista, pelo JSON em ordem."""
    h = hashlib.sha256()
    for p in partes:
        if isinstance(p, Path):
            h.update(b"arquivo:")
            with open(p, "rb") as f:
                for bloco in iter(lambda: f.read(1 << 20), b""):
                    h.update(bloco)
        elif isinstance(p, bytes):
            h.update(b"bytes:" + p)
        else:
            h.update(b"json:" + json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode())
        h.update(b"\0")
    return h.hexdigest()[:32]


def faz(fornecedor: str, o_que: str, partes: list, chama: Callable[[Path], float | None], *, sufixo: str,
        estimativa: float | None = None, teto: float | None = None, saida: Path | None = None,
        novo: bool = False) -> Path:
    """Paga uma vez por conteúdo. Devolve `saida` (copiada do guardado) ou o próprio guardado.
    O portão só vale com `estimativa`; o teto é o do chamador ou PAGO_TETO_USD (padrão US$ 5)."""
    k = chave(fornecedor, o_que, *partes)
    if teto is None:
        teto = float(os.environ.get("PAGO_TETO_USD", "5"))   # sem teto do chamador, vale o do ambiente
    guardado = PASTA / fornecedor / f"{k}{sufixo}"
    if guardado.exists() and not novo:
        registra(fornecedor, o_que, usd=0.0, reuso=True, chave=k, fonte=saida)
        return _entrega(guardado, saida)
    if teto is not None and estimativa is not None and estimativa > teto:
        raise Recusado(f"{fornecedor} {o_que}: estimativa US$ {estimativa:.2f} passa do teto US$ {teto:.2f} "
                           f"(pra subir: PAGO_TETO_USD={max(10, int(estimativa) + 1)} comando...)")
    guardado.parent.mkdir(parents=True, exist_ok=True)
    parcial = guardado.with_name(guardado.stem + ".parcial" + sufixo)
    try:
        usd = chama(parcial)
        parcial.replace(guardado)
    finally:
        parcial.unlink(missing_ok=True)
    real = usd is not None
    registra(fornecedor, o_que, usd=float(usd if real else (estimativa or 0.0)), estimado=not real,
             chave=k, fonte=saida)
    return _entrega(guardado, saida)


def _entrega(guardado: Path, saida: Path | None) -> Path:
    if saida is None:
        return guardado
    saida.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(guardado, saida)
    return saida


def registra(fornecedor: str, o_que: str, *, usd: float = 0.0, creditos: float | None = None,
             estimado: bool = False, reuso: bool = False, chave: str | None = None, fonte=None) -> None:
    """Uma linha no registro. Crédito (ElevenLabs, HeyGen) vai junto do US$ que ele vale."""
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    linha = {"ts": int(time.time()), "fornecedor": fornecedor, "o_que": o_que, "usd": round(usd, 5),
             **({"creditos": creditos} if creditos is not None else {}),
             **({"estimado": True} if estimado else {}), **({"reuso": True} if reuso else {}),
             **({"chave": chave} if chave else {}), **({"fonte": str(fonte)} if fonte else {})}
    with open(REGISTRO, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def resumo(dias: float = 7) -> dict:
    """{fornecedor: {pagas, reusos, usd, creditos, estimado}} dos últimos `dias`."""
    corte = time.time() - dias * 86400
    out: dict = {}
    if not REGISTRO.exists():
        return out
    for l in REGISTRO.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        if r.get("ts", 0) < corte:
            continue
        s = out.setdefault(r["fornecedor"], {"pagas": 0, "reusos": 0, "usd": 0.0, "creditos": 0.0, "estimado": 0.0})
        if r.get("reuso"):
            s["reusos"] += 1
            continue
        s["pagas"] += 1
        s["usd"] += r.get("usd", 0.0)
        s["creditos"] += r.get("creditos") or 0
        if r.get("estimado"):
            s["estimado"] += r.get("usd", 0.0)
    return out


if __name__ == "__main__":
    for f, s in sorted(resumo(7).items(), key=lambda kv: -kv[1]["usd"]):
        est = f" ({s['estimado']:.2f} estimado)" if s["estimado"] else ""
        cr = f", {s['creditos']:.0f} créditos" if s["creditos"] else ""
        print(f"{f:12} US$ {s['usd']:7.2f}{est}  {s['pagas']} pagas, {s['reusos']} reaproveitadas{cr}")
