"""Costura A — o que é cortado.

Recebe palavras em memória e devolve os trechos a manter. Sem ler arquivo, sem
estado de módulo: a afinação entra como argumento, então o modo aula e o modo
reel rodam no mesmo processo sem um contaminar o outro.

    trechos = cortar(palavras, drops=[...], janelas=[...], afinacao=AULA)

O que a regra garante, por construção:
  - Ar morto cortado onde o vão entre palavras mantidas passa de `sil_cut`.
  - Filler genérico (né/sabe/assim/...) só sai se houver `filler_gap` de silêncio
    do áudio ORIGINAL de um dos lados — a emenda cai numa pausa de verdade, e um
    vão criado pelos nossos próprios drops nunca qualifica um filler.
  - "tá" tique sai em todo lugar; "tá" verbo (= está: "tá usando", "tá no") fica.
  - "tipo"/"aí" nunca saem sozinhos — em português são conteúdo com frequência
    demais.
  - Gaguejada e recomeço saem; anáfora deliberada de três ou mais fica.

Três afinações nomeadas: `AULA` (preserva pausa natural), `TIGHT` (reel, zero
silêncio) e `SILENCIO` (corte por energia do áudio, não por palavra — é o que o
`silence_edl` fazia como segundo motor). `afinacao(nome, **sobrescritas)` resolve
por nome e recusa nome que não existe listando os válidos.

Retake e recomeço longo são do conteúdo, não da regra: passe como drop.

Uso pela linha de comando:
    python helpers/clean_edl.py --video <v.mp4> --transcript <t.json> -o <edl.json>
    python helpers/clean_edl.py --video V --transcript T -o E --tight \
        --drop 140.89 142.88 --drop 595.5 598.3
"""
from __future__ import annotations
import argparse, json, re
from dataclasses import dataclass, replace
from pathlib import Path
import transcript as tr


@dataclass(frozen=True)
class Afinacao:
    """Os botões do corte. Congelado de propósito: sobrescrever devolve outra
    afinação em vez de mexer na que tem nome."""

    # Vão de silêncio que vira corte. A aula preserva pausa natural (2s), o reel não.
    sil_cut: float = 2.0
    # Silêncio de um dos lados do filler para que cortá-lo caia numa pausa real.
    filler_gap: float = 0.18
    # Fôlego que sobra na emenda de ar morto. Sem ele, o pad deixa 0.48s onde havia
    # 3s de pausa e o aluno não tem tempo de processar a virada de tópico. Metade
    # para cada lado, nunca mais que 90% da pausa original — o resto é o que de
    # fato encurta a aula.
    pause_keep: float = 0.9
    # "é" seguido de pelo menos este silêncio é hesitação.
    hes_gap: float = 0.40
    # Um "ééé" arrastado dura pelo menos isto; o verbo "é/é o/é um" é mais curto.
    hes_dur: float = 0.30
    pad_in: float = 0.20
    # Alto de propósito: o whisper marca o fim da palavra na vogal, mas consoante
    # final surda (s/t/d de "dashboard", "vps") arrasta 0.2-0.3s além. Pad curto
    # clipa a cauda.
    pad_out: float = 0.28
    min_seg: float = 0.15
    # Corte automático de gaguejada, recomeço e repetição imediata.
    disfluencia: bool = True
    # Repetição colada só conta como gaguejada se as palavras estiverem tão perto.
    stammer_gap: float = 0.80
    # Recomeço de frase só conta se os dois começos estiverem tão perto.
    restart_gap: float = 1.20
    # Lê o texto das palavras? O corte por energia não tem texto para ler.
    usa_texto: bool = True
    # Com `voz` (trechos falados medidos no áudio), a borda nunca corta voz no ar:
    # estica até o silêncio, sem passar da palavra vizinha no áudio original. Em
    # 22/09/2026 o tight (pad_out 0.02) comeu "e seis centavos" das três versões do
    # preço da VSL: o whisper fechou "41,06" como um token só, cedo demais.
    cauda_max: float = 1.5
    cabeca_max: float = 0.4
    pad_voz: float = 0.04
    # Corte suave ligado (estilo `corte.suave`): a emenda quase não se vê, então a hesitação DENTRO da
    # frase vira corte. O som puro ("hum", "ã", "ahn") sai sem precisar de silêncio ao lado, e o "é" de
    # hesitação sai a partir de HES_DUR_SUAVE (o verbo "é" continua protegido pelo complemento).
    hesitacao_interna: bool = False


AULA = Afinacao()
TIGHT = replace(AULA, sil_cut=0.08, pad_in=0.0, pad_out=0.02, min_seg=0.04, pause_keep=0.0)
# Corte por energia do áudio: as "palavras" são os trechos falados que o
# silencedetect achou, sem texto. Só o construtor de segmento e o pad valem.
SILENCIO = Afinacao(sil_cut=0.04, pad_in=0.06, pad_out=0.06, pause_keep=0.0,
                    min_seg=0.18, disfluencia=False, usa_texto=False)

# O mesmo corte por energia, mais a repetição colada ("meu projeto meu projeto"). É a do reel de
# câmera: tira a gaguejada e só ela. "é", "tá" e fillers seguem onde foram ditos, porque ler o texto
# é o que derruba verbo (ver `usa_texto`).
SILENCIO_GAGUEIRA = replace(SILENCIO, disfluencia=True)

AFINACOES: dict[str, Afinacao] = {"aula": AULA, "tight": TIGHT, "silencio": SILENCIO,
                                  "silencio-gagueira": SILENCIO_GAGUEIRA}


def afinacao(nome: str, **sobrescritas) -> Afinacao:
    """Resolve uma afinação por nome, com sobrescritas. Nome que não existe
    estoura listando os válidos — o erro não pode ser descoberto no render."""
    if nome not in AFINACOES:
        raise KeyError(
            f"afinação '{nome}' não existe. Disponíveis: {', '.join(sorted(AFINACOES))}"
        )
    base = AFINACOES[nome]
    if not sobrescritas:
        return base
    desconhecidos = set(sobrescritas) - set(base.__dataclass_fields__)
    if desconhecidos:
        raise KeyError(
            f"botão que não existe: {', '.join(sorted(desconhecidos))}. "
            f"Disponíveis: {', '.join(sorted(base.__dataclass_fields__))}"
        )
    return replace(base, **sobrescritas)


def palavras_de_trechos(trechos: list[tuple[float, float]]) -> list[dict]:
    """Trechos de fala (detecção por energia) no formato que `cortar` lê.

    Sem texto: as regras de filler, "tá", "é" e gaguejada não têm o que morder, e
    sobra o que interessa — construir segmento, juntar o que está colado, e pad.
    """
    return [{"text": "", "start": float(a), "end": float(b), "type": "word"}
            for a, b in trechos]

# Generic fillers (NOT "tá"/"tipo"/"aí" — handled specially / excluded).
FILLERS = {"né","ne","sabe","assim","hum","ã","ãã","hã","ahn","eh","viu"}
SOM_PURO = {"hum", "ã", "ãã", "hã", "ahn", "eh"}      # não é palavra: sair é sempre certo
HES_DUR_SUAVE = 0.22
# If "tá" is followed by one of these (or a gerund) it's the verb "está" -> KEEP.
KEEP_AFTER_TA = {
    "no","na","nos","nas","num","numa","com","sem","lá","la","aqui","ali","em",
    "de","do","da","dos","das","pra","pro","por","a","o","as","os","bom","boa",
    "certo","tudo","meio","mais","quase","sempre","só","so","muito","bem",
    "tranquilo","ligado","perto","longe","pronto","rodando","funcionando","dando","indo",
    # irregular past participles (tá feito/aberto/visto... = está + participle)
    "feito","feita","aberto","aberta","posto","visto","dito","escrito","cheio","cheia",
}

def norm(t): return re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", t.strip().lower())

# Se "é" é seguido por um destes (ou por um infinitivo), é o verbo -> MANTÉM.
KEEP_AFTER_E = {
    "o","a","os","as","um","uma","uns","umas","isso","isto","aquilo",
    "esse","essa","este","esta","esses","essas","aquele","aquela",
    "ele","ela","eles","elas","você","voce","meu","minha","seu","sua","nosso","nossa",
    "de","do","da","dos","das","em","no","na","nos","nas","por","pra","para","com",
    "que","quando","onde","como","porque","só","so","mais","menos","muito","bem",
    "melhor","pior","igual","tipo","assim","sempre","quase","meio","tudo","nada",
    "verdade","fácil","facil","difícil","dificil","importante","possível","possivel",
    "claro","óbvio","obvio","normal","comum","raro","caro","barato","rápido","rapido",
    "grátis","gratis","gratuito","exclusivo","opcional","obrigatório","obrigatorio",
}

def is_verb_e(nxt_norm):
    """"é o", "é um", "é isso", "é ver", "é gratuito" -> verbo. Sem próxima palavra,
    não dá pra afirmar, então devolve False e deixa os outros sinais decidirem."""
    if not nxt_norm:
        return False
    # "ver", "ser", "ter", "ir" são infinitivos de 2-3 letras. O teto de tamanho
    # deixava "é ver o vídeo" virar "ver o vídeo". Na dúvida, MANTÉM: hesitação que
    # sobra é defeito pequeno, verbo apagado quebra a frase.
    if re.search(r"(ar|er|ir)$", nxt_norm) and len(nxt_norm) >= 2:
        return True
    return nxt_norm in KEEP_AFTER_E

def is_verb_ta(tok, nxt_norm):
    if tok.strip().endswith("?"):                  # "tá?" is always the tic
        return False
    if not nxt_norm:
        return False
    if re.search(r"(ando|endo|indo)$", nxt_norm):           # tá usando/fazendo/indo
        return True
    if re.search(r"(ad[oa]s?|id[oa]s?)$", nxt_norm):        # tá fechado/ligada/perdidos (particípio)
        return True
    return nxt_norm in KEEP_AFTER_TA


def _strip_disfluency(words, af: Afinacao):
    """Drop immediate word/phrase repetitions (stammers, false-starts), keep the LAST clean
    utterance. Conservative: protects deliberate 3+ anaphora ('vai poder X, vai poder Y, vai poder Z').

    - D-phrase: an m-token run (m=5..2) repeated IMMEDIATELY after itself ('São poucos São
      poucos', 'meu projeto meu projeto', 'a meta a meta') -> drop the first run. Only the
      back-to-back case (g=0): a one-word gap is almost always a real 2-item list
      ('pode criar carrossel, pode criar post' / 'lá no Instagram, lá no Facebook'), never cut.
      Also skipped if the prefix occurs 3+ times nearby or the restart is slow (> af.restart_gap).
    - D-word: an exact single-token repeat back-to-back ('esse esse', 'então então') within
      af.stammer_gap -> drop the earlier.
    """
    if not af.disfluencia or len(words) < 2:
        return words
    n = len(words)
    nrm = [norm(w["text"]) for w in words]
    st = [float(w["start"]) for w in words]
    en = [float(w["end"]) for w in words]
    rm = [False] * n

    def occurs(seq, center, span=14):
        L = len(seq); c = 0
        for k in range(max(0, center - span), min(n - L, center + span) + 1):
            if nrm[k:k + L] == seq:
                c += 1
        return c

    for m in (5, 4, 3, 2):                             # longer phrases first
        i = 0
        while i + m <= n:
            seq = nrm[i:i + m]
            if any(rm[i:i + m]) or "" in seq:
                i += 1; continue
            hit = False
            for g in (0,):                             # back-to-back only (g=1 = real 2-item list)
                j = i + m + g
                if j + m > n or any(rm[i:j + m]):
                    continue
                if m <= 3:
                    perto = st[j] - st[i] <= af.restart_gap
                else:
                    # Quatro palavras ou mais levam mais que `restart_gap` só pra
                    # serem ditas; nelas, o que separa recomeço de retomada é a pausa
                    # entre as duas vezes. "eu vou te mostrar como eu vou te mostrar
                    # como" passava. E a repetição que abre frase nova é de propósito:
                    # "não é a primeira camada do projeto. A primeira camada do
                    # projeto são os arquivos brutos" — cortar a primeira quebra o sentido.
                    fim, ini = words[j - 1]["text"].strip(), words[j]["text"].strip()
                    frase_nova = fim[-1:] in ".?!" or (
                        ini[:1].isupper() and not words[i]["text"].strip()[:1].isupper())
                    perto = st[j] - en[j - 1] <= af.stammer_gap and not frase_nova
                if nrm[j:j + m] == seq and perto and occurs(seq, i) < 3:
                    for k in range(i, j):              # drop first run (+ the junk word)
                        rm[k] = True
                    hit = True; break
            i += (m if hit else 1)

    for i in range(n - 1):                             # single-word back-to-back repeat
        if rm[i] or rm[i + 1] or not nrm[i]:
            continue
        if nrm[i] == nrm[i + 1] and st[i + 1] - en[i] <= af.stammer_gap and occurs(nrm[i:i + 1], i) < 3:
            rm[i] = True

    return [w for k, w in enumerate(words) if not rm[k]]


VOGAIS = re.compile(r"[aeiouáéíóúâêôãõàüy]+")


def suspeitas(palavras: list[dict], fator: float = 2.2, piso: float = 0.6) -> list[dict]:
    """Palavras longas demais para as próprias sílabas, no meio da frase.

    O whisper apaga o falso começo e estica a palavra seguinte por cima dele:
    "olha esses cri- olha esses criativos" vira um "criativos" de 1.04s. O texto
    não tem o que cortar, então a regra só aponta: confira no ouvido. Nos takes da
    VSL do Hermes pegou 3 dos 4 engolidos, com 7 alarmes falsos em 7 minutos.
    """
    W = [w for w in palavras if w.get("type", "word") == "word" and w.get("text")]
    if len(W) < 5:
        return []
    sil = lambda w: max(1, len(VOGAIS.findall(w["text"].lower())))
    dur = lambda w: float(w["end"]) - float(w["start"])
    ritmo = sorted(dur(w) / sil(w) for w in W)[len(W) // 2]
    out = []
    for i, w in enumerate(W[:-1]):
        final = w["text"].strip()[-1:] in ".,?!:;" or float(W[i + 1]["start"]) - float(w["end"]) > 0.15
        if not final and dur(w) >= piso and dur(w) / sil(w) > fator * ritmo:
            out.append({"start": float(w["start"]), "end": float(w["end"]), "text": w["text"].strip()})
    return out


def _estica_pela_voz(ps, pe, s, e, lo, hi, voz, af: Afinacao):
    """Borda que cai com voz no ar anda até o silêncio. `lo`/`hi` são as palavras
    vizinhas no áudio ORIGINAL: esticar nunca devolve uma palavra que saiu."""
    for a, b in voz:
        if a <= e + 0.05 and b > e:
            pe = max(pe, min(b + af.pad_voz, hi - 0.001, e + af.cauda_max))
            break
    for a, b in voz:
        if a < s and b >= s - 0.05:
            ps = min(ps, max(a - af.pad_voz, lo + 0.001, s - af.cabeca_max))
            break
    return ps, pe


def _clean_window(Wall, drops, rng, stem, af: Afinacao, voz=None):
    """Limpa uma janela da fonte -> trechos a manter, em ordem."""
    W = Wall if rng is None else [w for w in Wall
        if float(w["start"]) >= rng[0] and float(w["end"]) <= rng[1]]
    if not W:
        return []
    W = [dict(w) for w in W]                        # não escreve no que o chamador passou
    for i, w in enumerate(W):                       # vizinhos no áudio ORIGINAL
        w["_i"] = i
        w["_pe"] = float(W[i-1]["end"]) if i > 0 else None
        w["_pt"] = norm(W[i-1]["text"]) if i > 0 else None
        w["_ns"] = float(W[i+1]["start"]) if i+1 < len(W) else None
        w["_nt"] = norm(W[i+1]["text"]) if i+1 < len(W) else None

    def in_drop(w):
        s, e = float(w["start"]), float(w["end"])
        return any(s >= a and e <= b for a, b in drops)
    kept = [w for w in W if not in_drop(w)]

    keep2 = []
    for w in kept:
        if not af.usa_texto:            # corte por energia: não há texto para ler
            keep2.append(w); continue
        nrm = norm(w["text"])
        if nrm in ("tá", "ta"):
            if not is_verb_ta(w["text"], w.get("_nt")):
                continue
            keep2.append(w); continue
        if nrm in ("é", "eh", "éh") or re.fullmatch(r"[ée]{2,}h?", nrm):
            # Hesitation vs verb "é". Whisper gives them the SAME gap (0.0, flows on),
            # so the tell is DURATION: verb "é/é o/é um" is short (~0.06-0.25s); a dragged
            # "ééé..." hesitation is long (>= af.hes_dur). Also drop on trailing "..." or a real gap.
            raw = w["text"].strip()
            dur = float(w["end"]) - float(w["start"])
            ga = w["_ns"] - float(w["end"]) if w["_ns"] is not None else 99
            # A DURAÇÃO SOZINHA NÃO DECIDE, e apostar nela derruba o verbo. Num take de
            # 2026-09-08 os cinco "é," de hesitação mediram 0.00–0.26 s (passavam
            # inteiros) e dois verbos mediram 0.32 e 0.34 s — um deles fechando a última
            # frase da aula, que virou "Então isso, faça bom proveito".
            #
            # Os sinais que valem, nesta ordem:
            #   1. vírgula  -> hesitação. O verbo "é" pede complemento e não fecha
            #      oração, salvo depois de "que" ("não sei o que é, mas...").
            #   2. complemento na sequência -> verbo, seja qual for a duração.
            #   3. só então a duração / o "..." / o silêncio depois.
            if raw.endswith(",") and w.get("_pt") not in ("que", "quê", "qual", "quais"):
                continue
            if is_verb_e(w.get("_nt")):
                keep2.append(w); continue
            hes_dur = min(af.hes_dur, HES_DUR_SUAVE) if af.hesitacao_interna else af.hes_dur
            if raw.endswith("...") or ga >= af.hes_gap or dur >= hes_dur:
                continue
            keep2.append(w); continue
        if nrm in FILLERS:
            gb = float(w["start"]) - w["_pe"] if w["_pe"] is not None else 99
            ga = w["_ns"] - float(w["end"]) if w["_ns"] is not None else 99
            if gb >= af.filler_gap or ga >= af.filler_gap or (af.hesitacao_interna and nrm in SOM_PURO):
                continue
        keep2.append(w)
    if not keep2:
        return []
    keep2 = _strip_disfluency(keep2, af)
    if not keep2:
        return []

    # Segmentos como [início, fim, corte_na_entrada, corte_na_saída], onde corte_* diz
    # que aquela borda nasceu de uma palavra REMOVIDA e não de silêncio natural.
    #
    # Toda remoção obriga a emenda. Sem isso, o vão deixado pela palavra removida fica
    # menor que `sil_cut`, os dois lados viram um segmento só, e a palavra continua no
    # vídeo mesmo tendo saído da lista — vale para filler, para gaguejada e para drop
    # à mão. É o índice no áudio original que denuncia: se a próxima palavra mantida
    # não é a vizinha imediata, alguma coisa saiu dali no meio.
    segs = []; cur = None; anterior = None
    for w in keep2:
        s, e = float(w["start"]), float(w["end"])
        # No começo não há vizinha anterior mantida, mas pode haver palavra removida
        # antes dela — e aí o pad de entrada voltaria por cima do que acabou de sair.
        removeu_antes = (w["_i"] != anterior["_i"] + 1) if anterior is not None else (w["_i"] != 0)
        # [início, fim, corte_entrada, corte_saída, primeira_palavra, última_palavra]
        if cur is None:
            cur = [s, e, removeu_antes, False, w, w]
        elif removeu_antes or s - cur[1] >= af.sil_cut:
            cur[3] = removeu_antes; segs.append(cur); cur = [s, e, removeu_antes, False, w, w]
        else:
            cur[1] = e; cur[5] = w
        anterior = w
    if cur: segs.append(cur)

    merged = [list(segs[0])]
    for s, e, cs, ce, wf, wl in segs[1:]:
        if s - merged[-1][1] < 0.001: merged[-1][1] = e; merged[-1][3] = ce; merged[-1][5] = wl
        else: merged.append([s, e, cs, ce, wf, wl])

    # Pad edges: full PAD near natural silence (protects consonant tails), but ~0 near a
    # removal (don't re-swallow the filler/hesitation we just cut out).
    out = []
    for i, (s, e, cs, ce, wf, wl) in enumerate(merged):
        pi = 0.02 if cs else af.pad_in
        po = 0.02 if ce else af.pad_out
        if not cs and i > 0:                       # borda de silêncio real: devolve o fôlego
            pi = max(pi, min(af.pause_keep / 2, (s - merged[i-1][1]) * 0.45))
        if not ce and i < len(merged) - 1:
            po = max(po, min(af.pause_keep / 2, (merged[i+1][0] - e) * 0.45))
        ps = max(0.0, s - pi); pe = e + po
        if voz:
            lo = wf["_pe"] if wf["_pe"] is not None else 0.0
            hi = wl["_ns"] if wl["_ns"] is not None else float("inf")
            ps, pe = _estica_pela_voz(ps, pe, s, e, lo, hi, voz, af)
        if i > 0: ps = max(ps, merged[i-1][1] + 0.001)
        if out: ps = max(ps, out[-1]["end"] + 0.001)   # a voz esticou o anterior até aqui
        if i < len(merged)-1: pe = min(pe, merged[i+1][0] - 0.001)
        if rng is not None:          # o pad não escapa da janela que o editor escolheu
            ps = max(ps, rng[0]); pe = min(pe, rng[1])
        # Palavra de verdade nunca cai por ser curta: com `sil_cut` de 0.04 o "as" de "corta as
        # pausas" (0.1 s, vão de 0.04 antes e 0.06 depois) virava ilha menor que `min_seg` e sumia
        # do vídeo. O `min_seg` só varre o estalo sem texto, que é o que o corte por energia acha.
        # O corte pelo texto (aula, tight) fica como era: é o que a aula demonstra.
        if pe - ps >= af.min_seg or (not af.usa_texto and wf["text"].strip()):
            out.append({"source": stem, "start": round(ps,3), "end": round(pe,3)})
    return out


def cortar(palavras: list[dict],
           drops: list[tuple[float, float]] | None = None,
           janelas: list[tuple[float, float]] | None = None,
           afinacao: Afinacao = AULA,
           fonte: str = "",
           voz: list[tuple[float, float]] | None = None) -> list[dict]:
    """A costura A. Palavras em memória entram, trechos a manter saem.

    `janelas` é uma lista ORDENADA de janelas da fonte: cada uma é limpa e elas
    saem concatenadas NA ORDEM PEDIDA, não na do relógio — é assim que se costura
    trecho espalhado e se reorganiza a aula sem regravar. `None` limpa tudo.

    `voz` são os trechos falados medidos no áudio (`fala_do_audio`). Com eles, borda
    nenhuma corta palavra no meio, mesmo com o tempo do whisper errado.

    Não lê arquivo, não escreve arquivo, não toca em estado de módulo.
    """
    palavras = [w for w in palavras
                if w.get("type", "word") == "word" and float(w["end"]) > float(w["start"])]
    trechos: list[dict] = []
    for janela in (janelas if janelas else [None]):
        for t in _clean_window(palavras, drops or [], janela, fonte, afinacao, voz):
            # a voz esticou o trecho até o vizinho: sem vão, é um trecho só (cada emenda leva fade)
            if trechos and trechos[-1]["end"] <= t["start"] <= trechos[-1]["end"] + 0.0015:
                trechos[-1]["end"] = t["end"]
            else:
                trechos.append(t)
    return trechos


def fala_do_audio(video: Path, noise: str = "-35dB", min_sil: float = 0.08) -> list[tuple[float, float]]:
    """Trechos com voz no áudio inteiro: a duração menos os silêncios medidos."""
    import ff
    from silence_edl import detect      # aqui dentro: silence_edl importa este módulo
    total = ff.dur(video)
    falados, prev = [], 0.0
    for a, b in sorted(detect(video, 0.0, total, noise, min_sil)):
        if a > prev:
            falados.append((prev, a))
        prev = max(prev, b)
    if total > prev:
        falados.append((prev, total))
    return falados


def build(video: Path, transcript: Path, out: Path, drops: list[tuple[float, float]],
          ranges: list[tuple[float, float]] | None = None,
          afinacao: Afinacao = AULA, voz: bool = True):
    """Casca fina: lê o transcript, mede a voz, chama `cortar`, escreve o EDL."""
    d = tr.carrega(transcript)
    stem = video.stem
    falados = fala_do_audio(video) if voz else None
    all_ranges = cortar(d["words"], drops, ranges, afinacao, stem, falados)
    sus = suspeitas(d["words"])

    windows = ranges if ranges else [None]
    total = sum(r["end"]-r["start"] for r in all_ranges)
    src_dur = float(d.get("duration") or 0)
    out.write_text(json.dumps({"version":1,"sources":{stem:str(video)},"ranges":all_ranges,
        "grade":"none","overlays":[],"total_duration_s":round(total,2),"suspeitas":sus},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"windows {len(windows)} | segments {len(all_ranges)} | runtime {total/60:.2f}min"
          + (f" (src {src_dur/60:.2f}min)" if src_dur else ""))
    for s in sus:
        print(f"  confira no ouvido {s['start']:.2f}s: '{s['text']}' durou {s['end']-s['start']:.2f}s"
              " — falso começo engolido pelo whisper?")
    return out


def main():
    ap = argparse.ArgumentParser(description="Build a cleanup EDL from a whisper transcript")
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--transcript", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--drop", nargs=2, type=float, action="append", default=[],
                    metavar=("START","END"), help="Retake/false-start span to remove (repeatable)")
    ap.add_argument("--range", nargs=2, type=float, action="append", default=None,
                    metavar=("START","END"),
                    help="Keep words in this window; REPEATABLE & ORDERED (stitch/reorganize scattered segments)")
    ap.add_argument("--afinacao", default="aula", choices=sorted(AFINACOES),
                    help="afinação de corte (default: aula)")
    ap.add_argument("--sil-cut", type=float, default=None,
                    help=f"vão de silêncio que vira corte, em s (aula: {AULA.sil_cut}); menor = corta mais")
    ap.add_argument("--pad-in", type=float, default=None)
    ap.add_argument("--pad-out", type=float, default=None)
    ap.add_argument("--pause-keep", type=float, default=None,
                    help=f"fôlego mantido em cada emenda de ar morto, em s (aula: {AULA.pause_keep}; 0 = sem fôlego)")
    ap.add_argument("--tight", action="store_true",
                    help="apelido para --afinacao tight (reel, zero silêncio)")
    ap.add_argument("--sem-voz", action="store_true",
                    help="não mede a voz no áudio (a borda confia só no tempo do whisper)")
    args = ap.parse_args()

    sobrescritas = {k: v for k, v in (("sil_cut", args.sil_cut), ("pad_in", args.pad_in),
                                      ("pad_out", args.pad_out), ("pause_keep", args.pause_keep))
                    if v is not None}
    af = afinacao("tight" if args.tight else args.afinacao, **sobrescritas)

    build(args.video.resolve(), args.transcript.resolve(), args.output.resolve(),
          [(a, b) for a, b in args.drop],
          [(a, b) for a, b in args.range] if args.range else None,
          afinacao=af, voz=not args.sem_voz)


if __name__ == "__main__":
    main()
