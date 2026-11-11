#!/usr/bin/env python3
"""Apara um take de narração: áudio limpo + transcrição remapeada.

    python apara_pausas.py voz.wav --transcript t.json -o limpo.wav \
        --out-transcript t_limpo.json

Quem decide o que sai é o `clean_edl` — a mesma costura das aulas. Ele já sabe
mais do que silêncio: corta filler ("né", "sabe"), hesitação arrastada, gaguejada
e recomeço de frase, lendo o texto da transcrição. A primeira versão disto media
energia e só achava pausa; passava respiro no meio da frase e deixava toda
muleta de pé.

O que sobra aqui é o que o `clean_edl` não faz porque não é o trabalho dele:
montar o wav a partir dos trechos e devolver a transcrição com os tempos já
deslocados — assim o plano da legenda não precisa de uma transcrição nova.

Afinação padrão `tight` com `sil_cut` 0.04 — o tratamento aprovado da narração
dele, medido e não chutado. Rodar sem flag nenhuma já dá o resultado certo. Pra
aula, que preserva pausa natural, use `--afinacao aula`.
"""
from __future__ import annotations

import argparse
import json, re
import sys
from pathlib import Path

import clean_edl
import ff
import transcript as tr


def manter(fora: list[tuple[float, float]], fim: float) -> list[tuple[float, float]]:
    """O complemento de uma lista de cortes."""
    fica, t = [], 0.0
    for a, b in fora:
        if a > t:
            fica.append((round(t, 3), round(a, 3)))
        t = b
    if t < fim:
        fica.append((round(t, 3), round(fim, 3)))
    return fica


def buracos(fica: list[tuple[float, float]], fim: float) -> list[tuple[float, float]]:
    """O inverso: dos trechos mantidos para os removidos."""
    fora, t = [], 0.0
    for a, b in fica:
        if a > t:
            fora.append((round(t, 3), round(a, 3)))
        t = max(t, b)
    if t < fim:
        fora.append((round(t, 3), round(fim, 3)))
    return fora


HOP = 0.01          # 10ms: fino o bastante pra achar o fim de uma consoante


def envelope(audio: Path) -> tuple[list[float], float]:
    """dB por quadro de 10ms, e o limiar entre a voz dele e o fundo dele."""
    import numpy as np

    import ff
    # `binario=True` porque o que volta é PCM, não texto: decodificar em utf-8
    # estoura no primeiro byte alto, e estoura longe de onde o erro é.
    raw = ff.run(["ffmpeg", "-v", "error", "-i", str(audio),
                  "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                 capture=True, binario=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    h = int(16000 * HOP)
    n = len(x) // h
    rms = np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    baixo, alto = np.percentile(db, 10), np.percentile(db, 90)
    return db.tolist(), float(baixo + 0.30 * (alto - baixo))


def encostar(fica: list[tuple[float, float]], db: list[float], lim: float,
             teto: float = 0.40,
             drops: list[tuple[float, float]] | None = None
             ) -> list[tuple[float, float]]:
    """Empurra cada borda até onde o SOM de fato acaba.

    O Whisper marca o fim da palavra na vogal; consoante surda no fim ("vps",
    "processo", "instruções") arrasta 0,2 a 0,3s além disso. Cortar no tempo que
    ele diz decepa o "s" — foi o que aconteceu com a afinação `tight`, que usa
    0,02s de folga.

    Folga fixa grande resolveria e devolveria a pausa junto. Aqui a borda só
    anda ENQUANTO houver som: numa palavra que acaba seco ela não anda nada, e
    numa que arrasta ela acompanha. Quem decide o que cortar continua sendo o
    `clean_edl`; isto só decide onde a tesoura encosta.
    """
    # A borda NUNCA entra num `--drop`. Sem isso ela engole o corte pequeno:
    # uma gaguejada de 0.08s tem fala dos dois lados, a extensão acha som e
    # fecha o buraco — o áudio sai certo e a repetição volta na transcrição.
    drops = drops or []
    n = len(db)
    saida: list[tuple[float, float]] = []
    for i, (a, b) in enumerate(fica):
        piso = saida[-1][1] if saida else 0.0
        topo = fica[i + 1][0] if i + 1 < len(fica) else n * HOP
        for da, dbp in drops:
            if dbp <= a:
                piso = max(piso, dbp)
            if da >= b:
                topo = min(topo, da)
        k = max(0, int(round(a / HOP)))
        while (k > 0 and db[k - 1] >= lim
               and (int(round(a / HOP)) - (k - 1)) * HOP <= teto
               and (k - 1) * HOP >= piso):
            k -= 1
        m = min(n, int(round(b / HOP)))
        while (m < n and db[min(m, n - 1)] >= lim
               and (m - int(round(b / HOP))) * HOP <= teto
               and m * HOP <= topo):
            m += 1
        ini, fim = round(k * HOP, 3), round(m * HOP, 3)
        if saida and ini <= saida[-1][1]:
            saida[-1] = (saida[-1][0], max(saida[-1][1], fim))
        else:
            saida.append((ini, max(fim, ini + HOP)))
    return saida


def quietos(db: list[float], lim: float, a: float, b: float) -> list[tuple[float, float]]:
    """Corridas abaixo do limiar dentro de [a, b)."""
    ia, ib = int(round(a / HOP)), min(len(db), int(round(b / HOP)))
    fora, i = [], ia
    while i < ib:
        if db[i] >= lim:
            i += 1
            continue
        j = i
        while j < ib and db[j] < lim:
            j += 1
        fora.append((i * HOP, j * HOP))
        i = j
    return fora


def aparar_dentro(fica: list[tuple[float, float]], db: list[float], lim: float,
                  minimo: float = 0.26, resta: float = 0.13
                  ) -> list[tuple[float, float]]:
    """Corta o respiro que o `clean_edl` não enxerga.

    Ele só corta onde a TRANSCRIÇÃO tem vão entre duas palavras. Quando o
    Whisper cola duas palavras sem vão e há meio segundo de respiro no meio, o
    corte nunca acontece — e essa é metade do ar morto de um take.

    Aqui o vão é achado na onda, então cortá-lo não pode decepar consoante: por
    construção não há som nenhum ali. Sobra `resta` de fôlego em cada um, porque
    respiro zerado soa metralhada.
    """
    saida: list[tuple[float, float]] = []
    for a, b in fica:
        t = a
        for qa, qb in quietos(db, lim, a, b):
            if qb - qa < minimo:
                continue
            meio = (qa + qb) / 2
            corte_a, corte_b = meio - (qb - qa - resta) / 2, meio + (qb - qa - resta) / 2
            if corte_a > t:
                saida.append((round(t, 3), round(corte_a, 3)))
            t = corte_b
        if b > t:
            saida.append((round(t, 3), round(b, 3)))
    return saida


def respiros(palavras: list[dict], db: list[float], lim: float,
             teto_rel: float, minimo: float = 0.09) -> list[tuple[float, float]]:
    """Trechos de respiro audível, para abafar.

    Um respiro forte fica ACIMA do limiar de silêncio — o dele mede -44dB com a
    fala a -28 — então não é pausa e não some no corte. Baixar o limiar até
    pegá-lo comeria consoante fraca junto.

    A saída é o que separa: só conta o que está DENTRO de um vão da transcrição,
    isto é, entre o fim de uma palavra e o começo da próxima. Som fraco dentro da
    palavra é fala e fica intocado; som fraco entre palavras não tem o que ser
    além de ar.
    """
    import numpy as np
    arr = np.array(db)
    alto, baixo = np.percentile(arr, 90), np.percentile(arr, 10)
    corte = baixo + teto_rel * (alto - baixo)
    fora = []
    for a, b in zip(palavras, palavras[1:]):
        ini, fim = float(a["end"]), float(b["start"])
        if fim - ini < minimo:
            continue
        t = ini
        while t < fim:
            i = int(round(t / HOP))
            if i >= len(db) or db[i] >= corte:
                t += HOP
                continue
            j = i
            while j < len(db) and j * HOP < fim and db[j] < corte:
                j += 1
            if (j - i) * HOP >= minimo:
                fora.append((round(i * HOP, 3), round(j * HOP, 3)))
            t = j * HOP + HOP
    return fora


def clipes(fica: list[tuple[float, float]], db: list[float], lim: float) -> int:
    """Quantas emendas caem em cima de som — cada uma é uma palavra decepada."""
    n = len(db)
    return sum(1 for _, b in fica
               if int(round(b / HOP)) < n and db[int(round(b / HOP))] >= lim)


def subtrai(fica: list[tuple[float, float]],
            drops: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Tira os `--drop` dos trechos mantidos, ao pé da letra.

    O `clean_edl` respeita o drop escolhendo quais PALAVRAS ficam, mas depois
    aplica `pad_in`/`pad_out` nas bordas das vizinhas — e o pad reentra no
    buraco. Numa gaguejada de 0.12s os dois trechos voltam a se tocar e o corte
    simplesmente não acontece.

    Aqui o drop é lei: o que o usuário marcou sai, por mais que a costura
    automática queira costurar por cima.
    """
    saida = list(fica)
    for da, db in sorted(drops):
        nova = []
        for a, b in saida:
            if b <= da or a >= db:
                nova.append((a, b))
                continue
            if a < da:
                nova.append((a, round(da, 3)))
            if b > db:
                nova.append((round(db, 3), b))
        saida = nova
    return [(a, b) for a, b in saida if b - a > 1e-6]


def instante(t: float, fora: list[tuple[float, float]]) -> float:
    """Onde o instante `t` do original cai no aparado.

    Um `t` DENTRO de um trecho removido colapsa no começo dele. Sem isso, a
    palavra cujo fim o Whisper esticou pra dentro da pausa não desloca junto com
    a seguinte, e as duas se sobrepõem na linha do tempo.
    """
    removido = 0.0
    for a, b in fora:
        if b <= t:
            removido += b - a
        elif a < t:
            return round(a - removido, 3)
        else:
            break
    return round(t - removido, 3)


def dentro(w: dict, fora: list[tuple[float, float]], parte: float = 0.6,
           db: list[float] | None = None, lim: float = 0.0) -> bool:
    """A palavra caiu dentro do que foi removido?

    Deslocar não basta: `--drop` tira uma frase inteira do ÁUDIO, e se a palavra
    continua na transcrição a legenda mostra o que ninguém ouve. Aqui ela sai de
    vez quando a maior parte dela estava no trecho cortado.
    """
    ini, fim = float(w["start"]), float(w["end"])
    # O QUE DECIDE É O SOM DA PALAVRA, NÃO O VÃO EM VOLTA DELA.
    #
    # O Whisper dá a uma palavra curta um intervalo generoso, com silêncio nas
    # pontas. Aparar esse silêncio cobre a maior parte do intervalo sem tocar na
    # fala — e medir por sobreposição de intervalo apagava "Quando", "Só", "O"
    # do começo de dezenas de frases, que estavam lá e audíveis.
    if db is not None and fim - ini >= 0.02:
        i0 = int(ini / HOP)
        i1 = max(i0 + 1, min(int(fim / HOP), len(db)))
        altos = [i for i in range(i0, i1) if db[i] >= lim]
        if altos:
            sumiu = sum(1 for i in altos
                        if any(a <= i * HOP < b for a, b in fora))
            # E conta o que FICOU, não a proporção. O intervalo do Whisper pega
            # som vizinho (o fim da frase anterior, um respiro) que o corte leva;
            # a proporção passava de 60% e apagava da legenda o "Eu" de "Eu sou o
            # Matheus", que estava no áudio. Com 50 ms de fala mantida, fica.
            return sumiu / len(altos) > parte and (len(altos) - sumiu) * HOP < 0.05
    # Palavra de duração zero não tem sobreposição pra medir, e o Whisper as
    # produz justamente nas gaguejadas — "disso. isso." vem com o segundo
    # "isso" de 31.47 a 31.47. Nesses casos vale o ponto: se ele caiu dentro do
    # corte, a palavra saiu do áudio e tem que sair da legenda junto.
    if fim - ini < 0.02:
        return any(a <= ini <= b for a, b in fora)
    coberto = sum(max(0.0, min(fim, b) - max(ini, a)) for a, b in fora)
    return coberto / (fim - ini) > parte


def norm_(t: str) -> str:
    return re.sub(r"[^\wÀ-ÿ]", "", t.lower())


def remapear(palavras: list[dict], fora: list[tuple[float, float]],
             db: list[float] | None = None, lim: float = 0.0) -> list[dict]:
    """Os tempos de cada palavra no aparado, sem sobreposição e sem o que saiu."""
    saida: list[dict] = []
    for k, w in enumerate(palavras):
        if dentro(w, fora, db=db, lim=lim):
            # Palavra curta que abre frase depois de pausa ("Eu sou", "A edição",
            # "E dá") vem do Whisper com o intervalo NO SILÊNCIO antes do som e
            # colado na seguinte: o som dela mora no começo da vizinha. Se a
            # vizinha fica, ela fica também — o áudio tem a palavra.
            nx = palavras[k + 1] if k + 1 < len(palavras) else None
            if not (nx and float(nx["start"]) - float(w["end"]) < 0.02
                    and len(norm_(w["text"])) <= 3 and not dentro(nx, fora, db=db, lim=lim)):
                continue
        ini, fim = instante(w["start"], fora), instante(w["end"], fora)
        if saida:
            ini = max(ini, saida[-1]["end"])
        saida.append({**w, "start": ini, "end": max(fim, ini)})
    return saida


def montar(entrada: Path, fica: list[tuple[float, float]], saida: Path,
           abafar: list[tuple[float, float]] | None = None,
           ganho: float = 0.14) -> None:
    # A rampa de 8ms vem ANTES do asetpts. Depois dele o relógio do trecho volta
    # a zero, e um `afade=t=in:st=12.4` deixa o trecho MUDO esperando um segundo
    # 12,4 que nunca chega — foi assim que a primeira versão devolveu um arquivo
    # com 83% de silêncio digital.
    # O abafamento entra ANTES dos cortes, no relógio do original — é onde os
    # trechos de respiro foram medidos. Depois do concat os tempos já mudaram.
    pre = ""
    fonte = "0:a"
    if abafar:
        cond = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in abafar)
        pre = f"[0:a]volume={ganho}:enable='{cond}'[q];"
        fonte = "q"
    partes = pre + "".join(
        f"[{fonte}]atrim={a:.3f}:{b:.3f},"
        f"afade=t=in:st={a:.3f}:d=0.008,"
        f"afade=t=out:st={b - 0.008:.3f}:d=0.008,"
        f"asetpts=N/SR/TB[p{i}];"
        for i, (a, b) in enumerate(fica))
    ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(entrada),
            "-filter_complex",
            partes + "".join(f"[p{i}]" for i in range(len(fica)))
            + f"concat=n={len(fica)}:v=0:a=1[o]",
            "-map", "[o]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1",
            str(saida)], quiet=True)


def duracao(p: Path) -> float:
    return float(ff.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "csv=p=0", str(p)], capture=True, quiet=True).stdout.strip())


def retomadas(palavras: list[dict], pausa: float = 0.45, minimo: int = 4,
              limiar: float = 0.7) -> list[tuple[float, float, str]]:
    """Acha trecho dito duas vezes — ele fala, não gosta, pausa, e refaz.

    O `clean_edl` pega a repetição quando as palavras batem. Não pega quando ele
    refaz com OUTRAS palavras: "…copiar tudo para uma conversa" vira "…ficar
    copiando tudo para uma conversa", e as duas versões ficam no arquivo.

    Duas escolhas que fazem isto funcionar, e as duas custaram uma versão errada:

    **Compara frase com frase, não janela com janela.** Retomada tem forma: ele
    termina, cala, recomeça. Janela deslizante acha a si mesma e inventa aviso a
    cada três palavras.

    **A medida é de CONTIDO, não de parecido.** Começo falso é prefixo do
    refeito: "Agora, eu tenho uma…" some inteiro dentro de "Agora, eu tenho tempo
    pra tirar novos projetos". Por Jaccard isso dá 0,3 e passa batido, porque a
    segunda frase é muito maior. Dividindo pela MENOR das duas, dá 0,75.

    Só avisa. Qual das versões é a boa é de quem ouve — quase sempre a segunda.
    """
    import unicodedata

    def cru(s: str) -> str:
        s = unicodedata.normalize('NFD', s.lower())
        return ''.join(c for c in s
                       if unicodedata.category(c) != 'Mn' and c.isalnum())

    grupos: list[list[dict]] = [[]]
    for i, w in enumerate(palavras):
        if i and w["start"] - palavras[i - 1]["end"] >= pausa:
            grupos.append([])
        grupos[-1].append(w)

    achados: list[tuple[float, float, str]] = []
    for g1, g2 in zip(grupos, grupos[1:]):
        a = {cru(w["text"]) for w in g1} - {""}
        b = {cru(w["text"]) for w in g2} - {""}
        if len(a) < minimo or len(b) < minimo:
            continue
        if len(a & b) / min(len(a), len(b)) >= limiar:
            achados.append((g1[0]["start"], g2[0]["start"],
                            " ".join(w["text"] for w in g1)))
    return achados


def drops_em_voz(drops, ws, voz, fim, folga=0.15):
    """Borda de --drop que cai com voz no ar corta palavra, e o drop vale ao pé
    da letra (`subtrai`), então nada conserta depois. Em 20/09/2026 um drop em
    72.40 cortou "atendimento" (72.04-72.46) e outro em 22.40 comeu "e seis
    centavos" do preço, com voz até 22.92. Devolve (borda, motivo, silêncio mais
    perto) para cada borda suspeita."""
    achados = []
    for ini, fim_drop in drops:
        for borda, lado in ((ini, "início"), (fim_drop, "fim")):
            if borda <= 0.05 or borda >= fim - 0.05:
                continue
            # a palavra do whisper só conta se o áudio tiver voz na borda: ele
            # estica a palavra por cima do silêncio vizinho (24/09/2026: "Nesse"
            # marcado em 10.90 com a voz começando em 11.16 recusou um drop limpo
            # em 11.10 e sugeriu 11.30, que cortaria a palavra no meio)
            em_voz = any(a < borda < b for a, b in voz)
            dentro = [w for w in ws if float(w["start"]) + 0.03 < borda < float(w["end"]) - 0.03] if em_voz else []
            if dentro:
                w = dentro[0]
                achados.append((borda, f"{lado} do drop dentro de '{w['text'].strip()}' "
                                       f"({float(w['start']):.2f}-{float(w['end']):.2f})",
                                float(w["end"]) if lado == "início" else float(w["start"])))
                continue
            for a, b in voz:
                # início de drop com voz seguindo depois = cauda da fala cortada;
                # fim de drop com voz já rolando antes = cabeça cortada
                if lado == "início" and a < borda and b - borda > folga:
                    achados.append((borda, f"início do drop com voz até {b:.2f}", b))
                if lado == "fim" and a < borda < b and borda - a > folga:
                    achados.append((borda, f"fim do drop com voz desde {a:.2f}", a))
    return achados


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=Path)
    ap.add_argument("--transcript", type=Path, required=True)
    ap.add_argument("--afinacao", default="tight", choices=sorted(clean_edl.AFINACOES))
    # 0.04 e não o 0.08 do `tight`: medido no take dele. Com 0.08 sobram
    # respiros no meio da frase; com 0.04 não sobra vão nenhum acima de 0.30s e
    # a fala continua inteira. Mexer aqui é mexer no tratamento aprovado.
    ap.add_argument("--sil-cut", type=float, default=0.04,
                    help="vão de silêncio que vira corte (padrão 0.04, medido "
                         "na narração dele); menor = corta mais")
    ap.add_argument("--respiro-teto", type=float, default=0.62,
                    help="nível, entre fundo (0) e voz (1), abaixo do qual o som "
                         "ENTRE palavras é respiro e vai ser abafado; 0 desliga")
    ap.add_argument("--respiro", type=float, default=0.13,
                    help="fôlego que sobra num respiro no meio da frase")
    ap.add_argument("--respiro-min", type=float, default=0.26,
                    help="respiro a partir do qual vale aparar")
    ap.add_argument("--pause-keep", type=float, default=None,
                    help="fôlego mantido em cada emenda (0 = nenhum)")
    # curto de propósito: `encostar` acha a borda de verdade na onda depois.
    # Pad grande aqui devolveria a pausa junto com a consoante.
    ap.add_argument("--pad-out", type=float, default=0.06)
    ap.add_argument("--drop", nargs=2, type=float, action="append", default=[],
                    metavar=("INI", "FIM"), help="retake a jogar fora (repetível)")
    ap.add_argument("--drop-em-voz", action="store_true",
                    help="aceita borda de --drop com voz no ar (corta palavra de propósito)")
    ap.add_argument("--out-transcript", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    sobre = {k: v for k, v in (("sil_cut", a.sil_cut), ("pause_keep", a.pause_keep),
                               ("pad_out", a.pad_out)) if v is not None}
    af = clean_edl.afinacao(a.afinacao, **sobre)

    d = tr.carrega(a.transcript)
    ws = tr.palavras(d)
    fim = duracao(a.audio)
    voz = clean_edl.fala_do_audio(a.audio)
    ruins = drops_em_voz(a.drop, ws, voz, fim)
    if ruins and not a.drop_em_voz:
        for borda, motivo, sil in ruins:
            print(f"  drop em {borda:.2f}s: {motivo} — silêncio mais perto em {sil:.2f}s", file=sys.stderr)
        sys.exit("borda de --drop corta palavra. Mova para o silêncio sugerido "
                 "ou passe --drop-em-voz se o corte no meio da fala é de propósito")
    trechos = clean_edl.cortar(ws, drops=[(x, y) for x, y in a.drop], afinacao=af, voz=voz)
    fica = [(round(float(t["start"]), 3), round(float(t["end"]), 3)) for t in trechos]
    if not fica:
        sys.exit("clean_edl não devolveu trecho nenhum")
    db, lim = envelope(a.audio)
    antes = clipes(fica, db, lim)
    fica = encostar(fica, db, lim, drops=[(x, y) for x, y in a.drop])
    fica = aparar_dentro(fica, db, lim, a.respiro_min, a.respiro)
    depois = clipes(fica, db, lim)
    ar = respiros(ws, db, lim, a.respiro_teto) if a.respiro_teto > 0 else []
    fica = subtrai(fica, [(x, y) for x, y in a.drop])
    fora = buracos(fica, fim)
    montar(a.audio, fica, a.out, abafar=ar)

    novo = duracao(a.out)
    palavras = remapear(ws, fora, db=db, lim=lim)
    # O CHECK: a última palavra tem que caber no arquivo. Se o remapeamento
    # divergir da montagem, a legenda inteira sai fora de sincronia e isso só
    # aparece olhando o vídeo pronto.
    if palavras[-1]["end"] > novo + 0.25:
        sys.exit(f"remapeamento fora do arquivo: fala vai a "
                 f"{palavras[-1]['end']:.2f}s e o áudio tem {novo:.2f}s")

    if a.out_transcript:
        a.out_transcript.write_text(json.dumps(
            {**d, "duration": round(novo, 3), "words": palavras}, ensure_ascii=False), encoding="utf-8")
    print(f"{a.out}  {fim:.1f}s -> {novo:.1f}s ({fim - novo:.1f}s fora, "
          f"{len(fica)} trechos, afinação {a.afinacao}) | "
          f"emendas em cima de som: {antes} -> {depois} | "
          f"respiros abafados: {len(ar)}")
    # em cima do ORIGINAL: o --drop que ele sugere é pra rodar de novo,
    # e --drop fala o relógio do arquivo de entrada, não o do remapeado
    for t0, t1, trecho in retomadas(ws):
        # já resolvido por --drop: não repetir o aviso a cada rodada
        if any(da <= t0 and t1 <= dbp + 0.3 for da, dbp in a.drop):
            continue
        print(f"  ATENÇÃO retomada em {t0:.2f}s (a boa começa em {t1:.2f}s): "
              f"“{trecho}” — confira e corte com --drop {t0:.2f} {t1:.2f}")


def _autoteste() -> None:
    def fala(txt, t0, passo=0.2):
        return [{"text": w, "start": round(t0 + i * passo, 2),
                 "end": round(t0 + i * passo + 0.15, 2), "type": "word"}
                for i, w in enumerate(txt.split())]
    # começo falso: prefixo do refeito, e por Jaccard passaria batido
    p = fala("Agora eu tenho uma", 0.0) + fala("Agora eu tenho tempo pra tirar novos projetos", 2.0)
    assert len(retomadas(p)) == 1, "não achou o começo falso"
    # retake com outras palavras
    p = (fala("e assim que o agente trabalha com informacoes reais da empresa", 0.0)
         + fala("e assim que o agente trabalha com as informacoes reais da empresa", 4.0))
    assert len(retomadas(p)) == 1, "não achou o retake reescrito"
    # frases vizinhas normais não podem disparar
    p = fala("voce aprende a criar um agente do zero", 0.0) + fala("com a biblioteca voce escolhe o cargo", 3.0)
    assert not retomadas(p), f"falso positivo: {retomadas(p)}"
    # "Eu" com o intervalo no silêncio cortado, colado em "sou": fica na legenda
    ws = [{"text": "mim.", "start": 0.0, "end": 0.3}, {"text": "Eu", "start": 1.0, "end": 1.36},
          {"text": "sou", "start": 1.36, "end": 1.6}]
    r = remapear(ws, [(0.35, 1.3)])
    assert [w["text"] for w in r] == ["mim.", "Eu", "sou"], r
    # palavra cortada à mão, sem vizinha colada, sai
    ws = [{"text": "isso", "start": 0.0, "end": 0.3}, {"text": "não", "start": 1.0, "end": 1.2},
          {"text": "vai", "start": 2.0, "end": 2.2}]
    assert [w["text"] for w in remapear(ws, [(0.9, 1.3)])] == ["isso", "vai"]
    print("autoteste de retomadas ok")

    fica = [(0.0, 2.0), (3.5, 5.0), (7.0, 9.0)]
    fora = buracos(fica, 10.0)
    assert fora == [(2.0, 3.5), (5.0, 7.0), (9.0, 10.0)], fora
    assert manter(fora, 10.0) == fica, manter(fora, 10.0)
    ws = [{"start": 1.0, "end": 1.8}, {"start": 3.6, "end": 4.9},
          {"start": 7.2, "end": 8.8}]
    novo = remapear(ws, fora)
    assert novo[0]["start"] == 1.0 and novo[1]["start"] == 2.1, novo
    assert all(a["end"] <= b["start"] for a, b in zip(novo, novo[1:])), novo
    # palavra cujo fim o Whisper esticou pra dentro do corte não atravessa a seguinte
    esticada = [{"start": 1.0, "end": 3.0}, {"start": 3.6, "end": 4.0}]
    m = remapear(esticada, fora)
    assert m[0]["end"] <= m[1]["start"], m
    # palavra inteiramente dentro de um corte SAI da transcrição: senão a
    # legenda mostra o que foi tirado do áudio
    # palavra de duração zero dentro do corte também sai
    zero = [{"tx": "a", "start": 1.0, "end": 1.4},
            {"tx": "gaguejada", "start": 5.5, "end": 5.5},
            {"tx": "b", "start": 7.2, "end": 7.6}]
    assert [x["tx"] for x in remapear(zero, fora)] == ["a", "b"], remapear(zero, fora)
    cortada = [{"tx": "fica", "start": 1.0, "end": 1.5},
               {"tx": "sai", "start": 5.2, "end": 5.9},
               {"tx": "fica2", "start": 7.2, "end": 7.9}]
    r = remapear(cortada, fora)
    assert [x["tx"] for x in r] == ["fica", "fica2"], r
    # o drop vale ao pé da letra, mesmo que a costura tente fechar por cima
    s = subtrai([(0.0, 2.0), (2.04, 5.0)], [(1.9, 2.3)])
    assert s == [(0.0, 1.9), (2.3, 5.0)], s
    # borda de drop dentro de palavra, ou com a voz seguindo, é recusada
    ws = [{"text": "atendimento", "start": 72.04, "end": 72.46},
          {"text": "do", "start": 72.46, "end": 72.6}]
    assert drops_em_voz([(72.40, 74.8)], ws, [(71.0, 72.9)], 75.0), "não viu o drop no meio da palavra"
    assert drops_em_voz([(22.40, 40.0)], [], [(20.47, 22.92)], 41.0), "não viu a voz seguindo"
    assert not drops_em_voz([(72.95, 74.8)], ws, [(71.0, 72.9)], 75.0), "recusou drop no silêncio"
    # palavra que o whisper esticou por cima do silêncio não trava drop que cai no silêncio
    nesse = [{"text": "Nesse", "start": 10.90, "end": 11.30}]
    assert not drops_em_voz([(11.10, 17.25)], nesse, [(9.7, 10.52), (11.16, 13.69), (17.28, 19.9)], 30.0), \
        "recusou drop em silêncio real por causa do tempo esticado do whisper"
    print("ok")


if __name__ == "__main__":
    if "--autoteste" in sys.argv:
        _autoteste()
    else:
        sys.exit(main())
