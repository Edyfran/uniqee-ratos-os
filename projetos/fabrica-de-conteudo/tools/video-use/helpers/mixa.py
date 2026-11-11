#!/usr/bin/env python3
"""Fecha o áudio de um corte: cama de trilha, ducking e loudness igual ao resto.

    python mixa.py corte.mp4 --trilha acustico-inspirador -o final.mp4

Três coisas que só fazem sentido juntas, e por isso moram no mesmo passo:

**Nível igual entre os cortes.** Dois blocos com 2dB de diferença lêem como
falha de gravação quando emendados. A voz entra num alvo fixo e a mistura sai
noutro, os dois medidos e não estimados.

**A cama.** Trilha muito mais baixa que a voz — a referência é 13dB abaixo, que
é onde ela sustenta sem disputar. Entra e sai em fade; cortar trilha seco no fim
soa como cabo arrancado. Trilha com final composto (o ta-da cai depois da última
palavra) pede `--fade-fim` curto: o fade de 2,4s abafa justamente o final.

**Ducking.** Mesmo baixa, a trilha some a consoante quando ele fala. O
`sidechaincompress` abaixa a música no ataque da voz e devolve no respiro, então
a cama aparece justamente nos vãos — que é onde ela serve pra alguma coisa.

**Onde há voz.** `--fala a:b,c:d` diz onde ela está; fora dali só há efeito
(o curto de mãos, com uma moeda por carta). A voz é medida só nesses trechos, e
só ali o ducking abaixa a cama — sem isso cada moeda bombeava a trilha, e o
efeito sozinho era levado ao volume de fala. `--fala ""`: não há voz nenhuma.

**O áudio vai até o fim da imagem.** Voz sintética acaba antes do vídeo (a chamada
fica parada meio segundo depois da última palavra), e o `amix` segue a primeira
entrada: a trilha cortava seco no meio do fade (0,34 s antes do fim no Eleven v4).
A voz ganha silêncio até a duração da imagem, e o fade da trilha fecha antes dela.

Sem `--trilha` ele só normaliza, que é o suficiente pra emendar blocos.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import ff
import som

MUSICA = Path(__file__).resolve().parents[1] / "assets" / "musica"
# A raiz da pasta: é dela que o plano escreve `trilha.faixa`, e o comando pode rodar de outra.
RAIZ = Path(__file__).resolve().parents[3]
# os alvos moram no som (`som.mistura`): este é o programa de linha de comando dela
VOZ, CAMA, SAIDA = som.VOZ, som.CAMA, som.SAIDA


def lufs(p: Path, onde: str | None = None) -> float:
    """A medida da costura (ff.lufs), parando o programa com a mensagem se ela não sai."""
    try:
        return ff.lufs(p, onde)
    except RuntimeError as e:
        sys.exit(str(e))


def resolver(nome: str) -> Path:
    p = Path(nome)
    if p.exists():
        return p
    if not p.is_absolute() and (RAIZ / p).exists():
        return RAIZ / p
    # procura em subpasta também: as do HeyGen moram em musica/heygen/
    for padrao in (p.name, f"{nome}.*", f"{nome}"):
        achados = sorted(MUSICA.rglob(padrao))
        if achados:
            return achados[0]
    sys.exit(f"trilha não achada: {nome} (procurei em {MUSICA})")


# Em 03/10 a mesma faixa tocava em doze vídeos da fábrica, escrita à mão em cada plano.
USADAS = MUSICA / "usadas.json"


def escolhe(clima: str, video: str, grava: bool = True) -> str | None:
    """A faixa do clima que está há mais tempo sem tocar, dos `catalogo.json` em assets/musica.

    O mesmo vídeo leva sempre a mesma: rodar de novo não troca a música nem invalida o cache.
    `grava=False` (o modo seco) escolhe sem marcar. None = nenhum catálogo tem o clima, e o
    vídeo segue sem trilha, como antes; é o caso do kit, que não leva as nossas.
    """
    faixas = {f["nome"]: str(c.parent / f["arquivo"]) for c in sorted(MUSICA.rglob("catalogo.json"))
              for f in json.loads(c.read_text(encoding="utf-8"))["faixas"]
              if f["clima"] == clima and f.get("arquivo")}
    if not faixas:
        return None
    usadas = json.loads(USADAS.read_text(encoding="utf-8")) if USADAS.exists() else []
    ja = next((u["faixa"] for u in usadas if u["video"] == video and u["faixa"] in faixas), None)
    if ja:
        return faixas[ja]
    ultima = {u["faixa"]: i for i, u in enumerate(usadas)}
    nome = min(faixas, key=lambda n: ultima.get(n, -1))
    if grava:
        usadas.append({"video": video, "faixa": nome, "clima": clima, "data": date.today().isoformat()})
        USADAS.write_text(json.dumps(usadas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return faixas[nome]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--trilha", help="nome em assets/musica ou caminho")
    ap.add_argument("--cama", type=float, default=CAMA, help=f"LUFS da trilha ({CAMA})")
    ap.add_argument("--voz", type=float, default=VOZ, help=f"LUFS da voz ({VOZ})")
    ap.add_argument("--alvo", type=float, default=SAIDA, help=f"LUFS da mistura ({SAIDA})")
    ap.add_argument("--sem-duck", action="store_true")
    ap.add_argument("--fade-fim", type=float, default=2.4, help="fade da trilha no fim, em s (2.4)")
    # narração sem respiro (voz sintética de anúncio) com razão 12 deixa a cama 32dB
    # abaixo da voz o tempo todo: medido nos criativos ninjas, ninguém ouvia a trilha
    ap.add_argument("--duck-ratio", type=float, default=12, help="quanto a voz abaixa a trilha (12)")
    # limiar baixo = a voz abaixa a cama bem mais (Tinteiro, 14/10: "a música tá muito alta quando eu tô falando")
    ap.add_argument("--duck-limiar", type=float, default=0.03, help="nível da voz (0-1) a partir do qual a cama abaixa (0.03)")
    ap.add_argument("--duck-solta", type=int, default=420, help="ms que a cama leva pra voltar no respiro (420)")
    ap.add_argument("--fala", help="trechos com voz, 'a:b,c:d' em s; fora deles só há efeito")
    ap.add_argument("--sons", type=Path, help="os efeitos (o `sons` e os `brolls` de um plano, como no som.py), "
                    "na mesma mistura")
    ap.add_argument("--mestre", type=float, default=som.MESTRE_DB, help="com --sons: nível dos efeitos contra a voz, dB")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    evs = som.do_plano(json.loads(a.sons.read_text(encoding="utf-8")), a.sons.parent, a.mestre) if a.sons else []
    try:
        som.mistura(a.video, a.out, evs, resolver(a.trilha) if a.trilha else None, voz=a.voz, cama=a.cama,
                    alvo=a.alvo, fala=a.fala, sem_duck=a.sem_duck, fade_fim=a.fade_fim, duck_ratio=a.duck_ratio,
                    duck_limiar=a.duck_limiar, duck_solta=a.duck_solta)
    except RuntimeError as e:          # a medida que não sai (silêncio) para com a frase, não com o traço
        sys.exit(str(e))


if __name__ == "__main__":
    sys.exit(main())
