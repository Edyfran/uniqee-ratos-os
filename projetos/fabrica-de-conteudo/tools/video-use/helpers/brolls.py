#!/usr/bin/env python3
"""O b-roll aprovado no get-brolls, traduzido para beats do plano.

    python brolls.py --projeto ~/gb/meu-video --ancoras ancoras.json -o broll.json

O recurso `broll` era consumido pela cadeia e ninguém o produzia: dois planos no
repositório inteiro tinham a lista, os dois escritos à mão, clipe por clipe. Isto
é o produtor que faltava — o mesmo papel que o `cards_da_fala` faz para a legenda.

**A divisão de trabalho é o ponto.** O get-brolls sabe O QUÊ e DE QUEM: busca por
beat, identifica a fonte, guarda os direitos e entrega o corte que você aprovou no
storyboard. Ele não sabe QUANDO — o instante em que o clipe entra depende do
corte, da âncora na fala, e isso é informação daqui.

Por isso um candidato sem âncora fica de fora em vez de virar `em: 0.0`. Chutar o
zero põe o clipe em cima da primeira frase, e o erro só aparece assistindo.

Contrato de entrada: `candidate.schema.json` do get-brolls — `segment`,
`approval`, `rights`, `delivery.path`. Saída: a forma de beat que o `fabrica.beats`
confere, com a procedência junto.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CANDIDATOS = "brolls/candidates.json"


def _aprovado(c: dict) -> bool:
    """Aprovado é decisão explícita, não ausência de recusa.

    Tratar "sem decisão" como sim põe no vídeo um clipe que ninguém olhou — e o
    storyboard existe justamente para alguém olhar.
    """
    return (c.get("approval") or {}).get("decision") == "approved"


def _fonte(c: dict) -> dict:
    """De onde veio, sob que condição, e por onde voltar ao candidato.

    Não é uma linha de texto: uma frase montada perde o id e o nome de quem
    aprovou, e é justamente isso que alguém vai querer quando a reclamação
    chegar — achar de volta o candidato no get-brolls e a evidência guardada lá.
    """
    d = c.get("rights") or {}
    seg = c.get("segment") or {}
    return {
        "id": c.get("id"),
        "provedor": c.get("provider"),
        "licenca": d.get("license") or "licença não declarada",
        "url": c.get("source_url"),
        "evidencia": d.get("evidence") or "",
        "aprovado_por": (c.get("approval") or {}).get("by"),
        "trecho": [seg.get("start"), seg.get("end")],
    }


def beats_de(candidatos: list[dict], ancoras: dict[str, float],
             raiz: Path) -> list[dict]:
    """Candidatos aprovados + âncoras por beat -> lista de beats do plano.

    `ancoras` mapeia o nome do beat (o mesmo do brief do get-brolls) para o
    instante no vídeo JÁ CORTADO. Quem não tem âncora não entra.
    """
    saida = []
    for c in candidatos:
        if not _aprovado(c):
            continue
        seg = c.get("segment") or {}
        nome = seg.get("beat")
        if nome not in ancoras:
            continue
        caminho = (c.get("delivery") or {}).get("path")
        if not caminho:
            continue
        dur = round(float(seg["end"]) - float(seg["start"]), 3)
        if dur <= 0:
            continue
        saida.append({
            "arquivo": str(raiz / caminho),
            "em": float(ancoras[nome]),
            "dur": dur,
            "fonte": _fonte(c),
        })
    return sorted(saida, key=lambda b: b["em"])


def carrega(projeto: Path) -> list[dict]:
    """Os candidatos do projeto do get-brolls. Ausente devolve vazio, não estoura:
    não ter coletado ainda é estado normal, e quem avisa é a fábrica."""
    arq = projeto / CANDIDATOS
    if not arq.exists():
        return []
    dados = json.loads(arq.read_text(encoding="utf-8"))
    return dados if isinstance(dados, list) else dados.get("candidates", [])


def main() -> None:
    ap = argparse.ArgumentParser(description="B-roll aprovado no get-brolls -> beats")
    ap.add_argument("--projeto", type=Path, required=True,
                    help="pasta do projeto no get-brolls")
    ap.add_argument("--ancoras", type=Path, required=True,
                    help='json {"nome do beat": segundo no vídeo cortado}')
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    candidatos = carrega(a.projeto)
    if not candidatos:
        sys.exit(
            f"nenhum candidato em {a.projeto / CANDIDATOS}.\n"
            f"Colete e aprove primeiro: /get-brolls-brief, depois /get-brolls-review"
        )
    ancoras = json.loads(a.ancoras.read_text(encoding="utf-8"))
    lista = beats_de(candidatos, ancoras, a.projeto)
    if not lista:
        sys.exit(
            f"{len(candidatos)} candidato(s), nenhum virou beat. "
            "Falta aprovar no storyboard, ou falta âncora para o beat."
        )
    a.out.write_text(json.dumps(lista, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(lista)} beats -> {a.out}")


if __name__ == "__main__":
    main()
