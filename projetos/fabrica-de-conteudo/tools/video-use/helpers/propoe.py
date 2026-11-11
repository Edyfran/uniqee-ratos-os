"""A Fábrica rascunha o plano de movimento do vídeo do celular sozinha, pela densidade que o aluno gravou.

O `--storyboard` chama isto quando o plano não traz peça, zoom, palavra atrás nem som: lê a fala já cortada e devolve os
campos que o agente escreveria no `reel.json` (`pecas`, `camera`, `palavras_atras`, `fundo`, `sons`), do mesmo jeito.
Determinístico: a mesma fala e a mesma densidade dão sempre o mesmo plano. Só biblioteca padrão (vai no kit do aluno).

    gancho            nos 3 primeiros segundos, da 1ª frase (g_gancho)
    número dito       k_palavra_gigante com o número (o d_linha pede uma série que a fala não dá, e inventá-la é mentir)
    chamada           g_comenta no fim, com a palavra mais forte da fala
    troca de layout   o rosto passa pro fundo trocado atrás da palavra forte (palavra_atras + fundo), no mínimo o da densidade
    vão maior que o   zoom, ou uma palavra gigante / headline da fala, até nenhum vão passar da densidade
    máximo            (batida do visual mais longa que o vão: palavra gigante na palavra forte dentro dela, a cada vão)
    sons              de 1 a 3, `hit` nas batidas de peso 3 (as trocas de layout)

Só peças do `v2.py cardapio`; respeita `efeitos` e `vetos`; nada de casca de página; no máximo 1/4 do vídeo em peso 3.

    python propoe.py <fala_cortada.json> <duracao>        # imprime o plano proposto
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import movimento
import transcript as tr

COR = "#F2C744"
PALAVRA_ATRAS_DUR = 0.8
STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para pra com sem sob sobre entre até
que quê como mas porque pois quando onde qual quais quem isso isto esse essa esses essas este esta estes estas aquele aquela
você vocês eu ele ela eles elas nós meu minha meus minhas seu sua seus suas teu tua nosso nossa
também ainda muito muita muitos muitas mais menos tudo todo toda todos todas cada outro outra outros outras mesmo mesma
então assim aqui ali lá agora hoje depois antes sempre nunca já só fazer faz fazendo feito fiz vai vou vamos foi era ser
está estou estamos estão estava tenho tem têm temos tinha pode posso podem dá dar dei coisa coisas gente vez vezes
né tá então bom bem aí""".split())
NEGACAO = {"sem", "não", "nao", "nunca", "nada", "nem", "jamais", "nenhum", "nenhuma", "ninguém"}      # inverte o sentido se a palavra vizinha sai da frase
NUMEROS = {"dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "cem": 100, "mil": 1000}


def _limpa(tx: str) -> str:
    return re.sub(r"^[^\w$%]+|[^\w$%]+$", "", tx or "")


def _seguro(tx: str) -> str:
    """O texto vai na query da peça: o que a quebraria sai."""
    return re.sub(r"[|&=#<>*_]", "", tx).strip()


def _forte(w: dict) -> int:
    """A força de uma palavra como chave: o tamanho, se não é conectivo nem número. 0 = não serve."""
    tx = _limpa(w["text"]).lower()
    if len(tx) < 5 or tx in STOP or any(c.isdigit() for c in tx) or tx in NUMEROS:
        return 0
    return min(len(tx), 8)      # acima de 8 letras a palavra não cabe como chamada nem ganha mais peso


def propoe(palavras: list[dict], dur: float, mov: dict | None = None, ids=(), cobertos=()) -> tuple[dict, str]:
    """(fragmento de plano, resumo numa linha). `palavras`: a fala no tempo do vídeo cortado (`transcript.palavras`);
    `mov`: o que `movimento.le()` devolve (o que falta vira o do primeiro vídeo); `ids`: as peças do cardápio;
    `cobertos`: os trechos `(t0, t1)` que o `visual.json` já cobre (tela dividida ou cheia): nada é proposto por cima deles,
    e cada começo de um conta como mudança na imagem pro vão da densidade."""
    mov = {**movimento.PRIMEIRO_VIDEO, **{k: v for k, v in (mov or {}).items() if v}}
    dens = mov["densidade"]
    lim = movimento.DENSIDADES[dens]
    quer, vetos = set(mov["efeitos"]), set(mov.get("vetos") or [])

    def livre(tipo: str, peca: str | None = None) -> bool:
        return (tipo in quer and tipo not in vetos and peca not in vetos
                and (peca is None or not ids or peca in ids))

    pode_layout = livre("palavra_atras") and "layout" not in vetos
    ws = [w for w in palavras if _limpa(w["text"])]
    if dur < 3 or not ws:
        return {}, "sem fala pra propor"

    pecas, camera, cards = [], [], []
    ocupado: list[tuple[float, float]] = [(float(a), float(b)) for a, b in cobertos]      # peça e palavra atrás não se sobrepõem (a câmera é leve e cruza com peça)
    usadas: set[str] = set()

    def cabe(a: float, b: float) -> bool:
        return a >= 0 and b <= dur + 1e-6 and all(b <= c - 0.1 or a >= d + 0.1 for c, d in ocupado)

    def peca(nome, q, t0, d, peso=2):
        t0, d = round(t0, 2), round(d, 2)
        pecas.append({"peca": nome, "q": q, "em": t0, "dur": d, "peso": peso})
        ocupado.append((t0, t0 + d))

    def inicios() -> list[float]:
        return [p["em"] for p in pecas] + [c["em"] for c in camera] + [c["em"] for c in cards] + [float(a) for a, _ in cobertos]

    chaves = sorted((w for w in ws if _forte(w)), key=lambda w: (-_forte(w), w["start"]))

    # o gancho: a 1ª frase, nos 3 primeiros segundos, inteira desde o primeiro quadro
    if livre("pecas", "g_gancho") and dur >= 3.5 and not any(a < 2.8 and b > 0.2 for a, b in cobertos):
        frase = []
        for w in ws[:8]:
            frase.append(_seguro(_limpa(w["text"])))
            if re.search(r"[.?!]$", w["text"].strip()):
                break
        frase = [f for f in frase if f]
        n = len(frase)
        tam = math.ceil(n / 3) if n > 3 else n
        linhas = [" ".join(frase[i:i + tam]) for i in range(0, n, tam)]
        linhas = [("*" if i == (1 if len(linhas) > 1 else 0) else "_" if i == 2 else "") + l for i, l in enumerate(linhas)]
        peca("g_gancho", {"l": "|".join(linhas)}, 0.2, min(2.6, dur - 0.5))

    # a batida do visual mais longa que o vão: o quadro ficaria parado. A palavra forte entra por cima dela (zoom não: a pessoa
    # sai do alinhamento na dividida e some na cheia), a cada vão, e a mudança conta pro vão da densidade
    if livre("pecas", "k_palavra_gigante"):
        for a, b in sorted(cobertos):
            n = math.ceil((b - a) / lim) - 1        # as paradas que partem a batida em vãos de até `lim`, repartidas por igual
            for k in range(1, n + 1):
                alvo = a + k * (b - a) / (n + 1)
                c = [w for w in chaves if abs(w["start"] - alvo) <= 0.45 and a + 0.3 <= w["start"] <= b - 0.7
                     and _limpa(w["text"]).lower() not in usadas
                     and all(w["start"] + 0.9 <= d - 0.1 or w["start"] >= e + 0.1 for d, e in ocupado if (d, e) not in cobertos)]
                if c:
                    w = min(c, key=lambda w: abs(w["start"] - alvo))
                    pecas.append({"peca": "k_palavra_gigante", "q": {"l": _seguro(_limpa(w["text"])).upper()}, "em": round(w["start"], 2), "dur": 0.9, "peso": 2})
                    ocupado.append((round(w["start"], 2), round(w["start"], 2) + 0.9))
                    usadas.add(_limpa(w["text"]).lower())
    # a chamada: no fim, com a palavra mais forte (sem prometer nada que o aluno não disse)
    if livre("pecas", "g_comenta") and dur >= 8 and chaves:
        t0 = dur - 2.8
        if cabe(t0, dur - 0.2):
            palavra = _seguro(_limpa(chaves[0]["text"])).upper()[:14]
            peca("g_comenta", {"rot": "Comenta a palavra", "palavra": palavra}, t0, 2.6)
            usadas.add(palavra.lower())

    # o número dito vira a palavra gigante dele
    if livre("pecas", "k_palavra_gigante"):
        for w in ws:
            tx = _limpa(w["text"]).lower()
            if w["start"] >= 0.6 and (re.fullmatch(r"\d+([.,]\d+)?", tx) or tx in NUMEROS) and cabe(w["start"], w["start"] + 0.9):
                peca("k_palavra_gigante", {"l": tx.upper()}, w["start"], 0.9)
                usadas.add(tx)
                break

    def melhor(lo: float, hi: float, d: float, sem_ocupar: bool = False):
        """A palavra forte e ainda não usada que começa em [lo, hi] e deixa `d` s livres; a mais forte, a mais cedo."""
        c = [w for w in chaves if lo <= w["start"] <= hi and _limpa(w["text"]).lower() not in usadas
             and (sem_ocupar or cabe(w["start"], w["start"] + d))]
        return c[0] if c else None

    # a troca de layout: o rosto passa pro fundo trocado atrás da palavra forte, repartida pelo vídeo
    cada = movimento.LAYOUT_CADA.get(dens)
    if pode_layout and cada and dur >= 4:
        piso = max(1, math.ceil(dur / cada))        # o mínimo da densidade (pouca-variacao)
        # a proposta passa do mínimo (impressionar), até uma troca a cada 9 s (intensa) ou 15 s (média) e 22 % do vídeo
        quer_n = max(piso, min(math.ceil(dur / {"intensa": 9.0}.get(dens, 15.0)), int(0.22 * dur / PALAVRA_ATRAS_DUR)))
        for k in range(quer_n):
            alvo = dur * (k + 1) / (quer_n + 1)
            for raio in (1.2, 2.5):
                w = melhor(max(0.6, alvo - raio), min(dur - 1.0, alvo + raio), PALAVRA_ATRAS_DUR)
                if w:
                    t0 = round(w["start"], 2)
                    cards.append({"em": t0, "texto": _seguro(_limpa(w["text"])).upper()[:14], "dur": PALAVRA_ATRAS_DUR, "cor": COR})
                    ocupado.append((t0, t0 + PALAVRA_ATRAS_DUR))
                    usadas.add(_limpa(w["text"]).lower())
                    break

    # onde ficou vão maior que a densidade: zoom ou uma palavra da fala, até fechar
    def zoom(alvo: float, i: int) -> bool:
        if not livre("zoom"):
            return False
        t1 = min(alvo + (0.5 if i % 2 else 1.0), dur)
        if any(alvo < b and t1 > a for a, b in cobertos):      # a pessoa nem aparece na tela cheia, e na dividida o zoom a desalinha
            return False
        for c in cards:      # a câmera fica em 1,0 com palavra atrás da cabeça (aviso `camera-atras`)
            if alvo < c["em"] + c["dur"] and t1 > c["em"]:
                if alvo < c["em"] - 0.4:
                    t1 = c["em"] - 0.05
                else:
                    return False
        if t1 - alvo < 0.3 or any(alvo < z["em"] + z["dur"] and t1 > z["em"] for z in camera):
            return False
        item = ({"em": round(alvo, 2), "dur": round(t1 - alvo, 2), "zoom": [1.0, 1.3], "ease": "crava", "borrao": 4} if i % 2
                else {"em": round(alvo, 2), "dur": round(t1 - alvo, 2), "zoom": [1.0, 1.2], "ease": "sine"})
        camera.append(item)
        return True

    def palavra(a: float, alvo: float, i: int) -> bool:
        if not livre("pecas", "k_palavra_gigante") and not livre("pecas", "t_headline"):
            return False
        w = melhor(a + 0.3, a + lim, 0.9)
        if not w:
            return False
        j = ws.index(w)
        tx = _limpa(w["text"])
        if i % 2 and livre("pecas", "t_headline"):
            ini = j
            while ini > max(0, j - 3) and not re.search(r"[.?!]$", ws[ini - 1]["text"].strip()):
                ini -= 1
            # a frase de antes não leva negação: "sem editar" na tela vira o contrário do que a pessoa disse
            while ini < j and any(_limpa(x["text"]).lower() in NEGACAO for x in ws[ini:j]):
                ini += 1
            ant = " ".join(_seguro(_limpa(x["text"])) for x in ws[ini:j])
            if cabe(w["start"], w["start"] + 2.0):
                peca("t_headline", {"l": f"{ant} <i>{_seguro(tx)}</i>".strip()}, w["start"], 2.0)
                usadas.add(tx.lower())
                return True
        if livre("pecas", "k_palavra_gigante"):
            peca("k_palavra_gigante", {"l": _seguro(tx).upper()}, w["start"], 0.9)
            usadas.add(tx.lower())
            return True
        return False

    inviaveis: set[float] = set()       # vão que nada cabe nele: segue pros outros, o aviso `ritmo-vao` diz o que sobrou
    for i in range(60):
        m = sorted({0.0, dur, *inicios()})
        buracos = [a for a, b in zip(m, m[1:]) if b - a > lim and a not in inviaveis]
        if not buracos:
            break
        a = buracos[0]
        feito = False
        for f in (0.95, 0.8, 0.65, 0.5, 0.35):
            alvo = min(a + f * lim, dur - 0.3)
            if alvo <= a + 0.1:
                continue
            for t in ((zoom, palavra) if i % 2 == 0 else (palavra, zoom)):
                feito = zoom(alvo, i) if t is zoom else palavra(a, alvo, i)
                if feito:
                    break
            if feito:
                break
        if not feito:
            inviaveis.add(a)

    sons = []
    if livre("sons"):
        sons = [{"tipo": "hit", "t": c["em"]} for c in sorted(cards, key=lambda c: c["em"])[:3]]

    plano = {}
    if pecas:
        plano["pecas"] = sorted(pecas, key=lambda p: p["em"])
    if camera:
        plano["camera"] = sorted(camera, key=lambda c: c["em"])
    if cards:
        cards.sort(key=lambda c: c["em"])
        plano["palavras_atras"] = cards
        plano["fundo"] = {"de": cards[0]["em"], "ate": round(cards[-1]["em"] + cards[-1]["dur"], 2)}
    if sons:
        plano["sons"] = sons
    resumo = (f"proposta automática ({dens}): {len(pecas)} peças, {len(camera)} zooms, {len(cards)} trocas de layout, "
              f"{len(sons)} sons")
    return plano, resumo


# ---- peças pela fala, na densidade do estilo (recurso `pecas`) ---------------------------------------------------------
#
# O plano mínimo do aluno não traz peça nenhuma: a fala escolhe. Cada gatilho vira uma peça da biblioteca que mostra o que
# a frase diz (a "peça é a prova", não a transcrição repetida): o comando vira o terminal, o número que sobe vira o
# gráfico, a venda vira o toast, a enumeração vira a lista, a marca ou sigla vira o chip. Gatilho que a fala não tem, a peça
# não entra: nada de dado inventado, só os rótulos que ele disse. O que sobra de vão é preenchido pelas palavras fortes
# (chip, manchete), até a densidade pedida (`movimento.ALVOS`: peças por 10 s e fatia do tempo coberta).
# Casca de página (checks.CASCA) fica de fora. A abertura (0 a 3 s) é do gancho escrito, que outro passo desenha.

ABERTURA = 3.0
FOLGA = 0.12
NUMERAIS = set("um uma dois duas tres quatro cinco seis sete oito nove dez vinte trinta meia menos mais".split())
UNIDADES = set("meses mes horas hora minutos minuto dias dia semanas semana anos ano segundos".split())
GATILHO = {"toast": set("notificacao notificacoes venda vendas vendeu vendi".split()),
           "terminal": {"comando", "prompt", "terminal"},
           "painel": set("faturamento metricas metrica relatorio relatorios ticket cac resultados receita lucro".split())}
LEAD = set("eles ela elas ele iam ia ter que precisar precisaria e vai vamos tem tinha preciso fazer depois".split()) - {"fazer"}
SOLTA = set("a o as os um uma uns umas meu minha seus suas de do da dos das com em para pra e".split())
CTA = {"comenta", "comente", "escreve", "escreva", "manda", "mande"}


def _nu(tx: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", _limpa(tx).lower()) if not unicodedata.combining(c))


def _frase(ws: list[dict], i: int, n: int, ate: int | None = None) -> str:
    """Até `n` palavras a partir de `i`, sem passar do fim da frase, limpas pro texto de uma peça."""
    out = []
    for w in ws[i:ate if ate is not None else len(ws)][:n]:
        t = re.sub(r'[|&=#<>*_;@"]', "", _limpa(w["text"]))
        if t:
            out.append(t)
        if re.search(r"[.?!]$", w["text"].strip()):
            break
    return " ".join(out)


def _enumeracao(ws: list[dict]):
    """A primeira frase com 3 ou mais trechos separados por vírgula: [(índice da 1ª palavra, índice depois da última)]."""
    inicio, trechos = 0, []
    for i, w in enumerate(ws):
        t = w["text"].strip()
        if t.endswith(",") or re.search(r"[.?!]$", t) or i == len(ws) - 1:
            trechos.append((inicio, i + 1))
            inicio = i + 1
            if re.search(r"[.?!]$", t) or i == len(ws) - 1:
                if len(trechos) >= 3 and all(b - a <= 9 for a, b in trechos):
                    return trechos
                trechos = []
    return None


def _item(ws: list[dict], a: int, b: int, primeiro: bool) -> tuple[str, str]:
    """(rótulo, o que veio antes dele): sem a entrada da frase ("eles iam ter que"), até 4 palavras, sem preposição pendurada."""
    ps = [t for t in (re.sub(r'[|&=#<>*_;@"]', "", _limpa(w["text"])) for w in ws[a:b]) if t]
    k = 0
    while k < len(ps) - 1 and _nu(ps[k]) in LEAD:
        k += 1
    ps = [p for p in ps[k:] if _nu(p) not in ("a", "o", "os", "as", "meu", "minha")]
    ps = ps[:4]
    while len(ps) > 1 and _nu(ps[-1]) in SOLTA:
        ps.pop()
    ant = " ".join(re.sub(r'[|&=#<>*_;@"]', "", _limpa(w["text"])) for w in ws[a:a + k]) if primeiro else ""
    return (" ".join(ps)[:1].upper() + " ".join(ps)[1:]), ant


def candidatos(ws: list[dict], dur: float) -> list[dict]:
    """As peças que a fala pede, em ordem de prioridade (`prio` menor entra primeiro). Cada uma: peca, q, em, dur, peso,
    e opcionais `larg`/`y`/`ar` (peça alta demais pro terço de cima entra encolhida) e `som` (peça muda ganha o golpe dela)."""
    nus = [_nu(w["text"]) for w in ws]
    cs: list[dict] = []

    def add(prio, peca, q, em, d, **kw):
        cs.append({"prio": prio, "peca": peca, "q": {**q, "dur": round(d, 2)}, "em": round(max(em, 0), 2),
                   "dur": round(d, 2), "peso": kw.pop("peso", 2), **kw})

    # a chamada final: a palavra que ele manda comentar
    cta_t = dur
    for i, n in enumerate(nus):
        if n in CTA and ws[i]["start"] > dur * 0.5:
            j = i + 1
            while j < len(ws) - 1 and nus[j] in ("a", "o", "aqui", "la"):
                j += 1
            pal = re.sub(r"[|&=#<>*_;@\"]", "", _limpa(ws[j]["text"])).upper()[:14]
            if pal and len(pal) > 2:
                cta_t = ws[i]["start"]
                t0 = max(ws[i]["start"] - 0.1, dur - 4.2)
                add(0, "g_comenta", {"rot": "Comenta a palavra", "palavra": pal}, t0, min(3.2, dur - t0 - 0.1))
                break
    # o comando: o terminal digitando o que ele pediu
    for i, n in enumerate(nus):
        if n in GATILHO["terminal"] and ws[i]["start"] >= ABERTURA and i + 3 < len(ws):
            k = i + 1
            while k < len(ws) - 3 and _nu(ws[k]["text"]) in ("e", "o", "a", "que", "um", "uma"):
                k += 1
            frase = _frase(ws, k, 6)
            if len(frase.split()) >= 3:
                add(1, "i_terminal", {"cmd": f'claude "{frase}"@0.5'}, ws[i]["start"] - 0.2, 5.0, larg=0.62, y=10, peso=3)
                break
    # a métrica: a linha que cresce, com o rótulo que ele disse
    for i, n in enumerate(nus):
        if n in GATILHO["painel"] and ws[i]["start"] >= ABERTURA:
            add(2, "d_linha", {"pts": "12,18,15,26,31,44,58", "rot": _nu(ws[i]["text"]).upper(), "pre": "", "suf": "",
                               "selo": "SUBINDO"}, ws[i]["start"] - 0.4, 4.0, ar="920x730", larg=0.74, y=50, peso=3)
            break
    # a enumeração: a lista que acende item a item, no tempo da fala
    tr_ = _enumeracao(ws)
    if tr_:
        itens = [(_item(ws, a, b, k == 0), ws[a]["start"]) for k, (a, b) in enumerate(tr_[:4])]
        t0 = itens[0][1] - 0.5
        if t0 >= ABERTURA - 0.5:
            ant = itens[0][0][1]
            hd = (ant + "..." if ant else "Em sequência").capitalize()
            it = ";".join(f"{r}@{max(0.3, s - t0):.2f}" for (r, _), s in itens)
            fim = ws[tr_[min(3, len(tr_) - 1)][1] - 1]["end"]
            add(3, "t_lista_cel", {"hd": hd, "it": it}, t0, min(8.0, fim - t0 + 1.4), larg=0.74, y=40, peso=3)
    # o aviso de venda: o toast que empilha
    for i, n in enumerate(nus):
        if n in GATILHO["toast"] and ws[i]["start"] >= ABERTURA:
            toast = "Nova venda|Pagamento aprovado|agora@"
            add(4, "r_notif", {"n": ";".join(f"{toast}{t}" for t in ("0.3", "1.2", "2.1"))}, ws[i]["start"] - 0.3, 4.2)
            break
    # a duração dita (meses, uma hora): a palavra gigante, com o golpe dela
    for i, n in enumerate(nus):
        if n in UNIDADES and ws[i]["start"] >= ABERTURA:
            txt = (nus[i - 1] + " " if i and nus[i - 1] in NUMERAIS and nus[i - 1] not in ("menos", "mais") else "") + _limpa(ws[i]["text"])
            add(5, "k_palavra_gigante", {"l": txt.upper()}, ws[i]["start"] - 0.05, 0.9, som="impact", peso=3)
            break
    # a marca ou a sigla: o chip com o nome, no alto
    vistos: set[str] = set()
    for i, w in enumerate(ws):
        tx = _limpa(w["text"])
        meio = i > 0 and not re.search(r"[.?!]$", ws[i - 1]["text"].strip())
        sigla = tx.isupper() and 2 <= len(tx) <= 6 and tx.isalpha() and tx not in ("EU", "OK")
        marca = (meio and tx[:1].isupper() and len(tx) >= 5 and tx.isalpha() and not tx.isupper()
                 and _nu(tx) not in STOP and _nu(tx) not in CTA)
        if not (sigla or marca) or w["start"] < ABERTURA or w["start"] >= cta_t - 0.1:
            continue
        nome = tx
        if marca and i + 1 < len(ws) and _limpa(ws[i + 1]["text"])[:1].isupper() and _limpa(ws[i + 1]["text"]).isalpha():
            nome = f"{tx} {_limpa(ws[i + 1]['text'])}"
        if nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        add(6, "r_termo", {"termo": _seguro(nome), "def": "", "x": 56, "y": 130 + 90 * (len(vistos) % 2)}, w["start"] - 0.1, 2.4)
    return cs


def pecas_da_fala(palavras: list[dict], dur: float, dens: str = "media", mov: dict | None = None, ids=()) -> list[dict]:
    """O plano de peças do vídeo, pela fala e pela densidade: [{peca, q, em, dur, peso, ...}] sem sobreposição.
    `mov`: o que `movimento.le()` devolve (efeitos e vetos do aluno); `ids`: o cardápio (vazio = qualquer peça da biblioteca)."""
    import movimento
    por10, cobertura = movimento.ALVOS.get(dens, movimento.ALVOS["media"])
    mov = mov or {}
    vetos = set(mov.get("vetos") or [])
    if (mov.get("efeitos") and "pecas" not in mov["efeitos"]) or "pecas" in vetos or dur < 6:
        return []
    ws = [w for w in palavras if _limpa(w["text"])]
    if not ws:
        return []
    ocupado: list[tuple[float, float]] = [(0.0, ABERTURA)]      # a abertura é do gancho escrito
    escolhidas: list[dict] = []

    def livre(a: float, b: float) -> bool:
        return a >= 0 and b <= dur + 1e-6 and all(b <= c - FOLGA or a >= d + FOLGA for c, d in ocupado)

    def poe(p: dict) -> bool:
        if p["peca"] in vetos or (ids and p["peca"] not in ids):
            return False
        a, b = p["em"], p["em"] + p["dur"]
        if p["peca"] in ("r_termo", "r_notif"):      # peça pequena: espera o vão se a grande ocupa a hora dela
            for k in range(9):
                if livre(a + 0.3 * k, b + 0.3 * k):
                    p["em"] = round(a + 0.3 * k, 2)
                    a, b = p["em"], p["em"] + p["dur"]
                    break
        if not livre(a, b):
            if p["peca"] in ("i_terminal", "d_linha", "t_lista_cel", "r_notif") and p["dur"] > 3.0:
                # a peça longa encurta até caber (o fim dela é a saída, que cabe em qualquer duração)
                while p["dur"] > 2.4 and not livre(a, a + p["dur"]):
                    p["dur"] = round(p["dur"] - 0.2, 2)
                    p["q"]["dur"] = p["dur"]
                b = a + p["dur"]
            if not livre(a, b):
                return False
        ocupado.append((a, b))
        escolhidas.append(p)
        return True

    for p in sorted(candidatos(ws, dur), key=lambda p: (p["prio"], p["em"])):
        poe(p)

    # o que falta pra densidade: manchete ou chip na palavra forte que cai no maior vão
    chaves = sorted((w for w in ws if _forte(w)), key=lambda w: (-_forte(w), w["start"]))
    usadas = {_limpa(w["text"]).lower() for w in ws if any(_limpa(w["text"]) == p["q"].get("termo") for p in escolhidas)}
    n_alvo, c_alvo = math.ceil(por10 * dur / 10), cobertura * dur

    def cobre() -> float:
        return sum(min(p["em"] + p["dur"], dur) - p["em"] for p in escolhidas)

    inviaveis: set[float] = set()
    for i in range(80):
        if len(escolhidas) >= n_alvo and cobre() >= c_alvo:
            break
        marcas = sorted({0.0, dur, *[x for p in escolhidas for x in (p["em"], p["em"] + p["dur"])], ABERTURA})
        vaos = [(b - a, a, b) for a, b in zip(marcas, marcas[1:])
                if b - a >= 1.5 and a not in inviaveis and livre(a + FOLGA, a + FOLGA + 0.5)]
        if not vaos:
            break
        _, a, b = max(vaos)
        d = round(min(3.0, b - a - 2 * FOLGA), 2)
        alvo = [w for w in chaves if a <= w["start"] <= b - 1.2 and _limpa(w["text"]).lower() not in usadas]
        if not alvo:
            inviaveis.add(a)
            continue
        w = alvo[0]
        tx = _seguro(_limpa(w["text"]))
        usadas.add(tx.lower())
        j = ws.index(w)
        # só manchete: chip sem marca nem sigla seria a transcrição repetida
        ini = j
        while ini > max(0, j - 3) and not re.search(r"[.?!]$", ws[ini - 1]["text"].strip()):
            ini -= 1
        ant = " ".join(_seguro(_limpa(x["text"])) for x in ws[ini:j])
        p = {"prio": 9, "peca": "t_headline", "q": {"l": f"{ant} <i>{tx}</i>".strip(), "dur": d},
             "em": round(max(a + FOLGA, w["start"] - 0.3), 2), "dur": d, "peso": 2}
        p["dur"] = round(min(p["dur"], b - p["em"] - FOLGA), 2)
        p["q"]["dur"] = p["dur"]
        if p["dur"] < 1.2 or not poe(p):
            inviaveis.add(a)
    return sorted(escolhidas, key=lambda p: p["em"])


def junta(cards: Path, brolls: Path, saida: Path) -> None:
    """A legenda e as peças num plano só, que o `captions_viral.py` lê: `brolls` entra no documento dos cards."""
    doc = json.loads(cards.read_text(encoding="utf-8"))
    doc = {"cards": doc} if isinstance(doc, list) else doc
    doc["brolls"] = json.loads(brolls.read_text(encoding="utf-8"))
    saida.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def do_arquivo(fala: Path, dur: float, mov: dict | None = None, ids=(), cobertos=()) -> tuple[dict, str]:
    return propoe(tr.palavras(fala), dur, mov, ids, cobertos)


if __name__ == "__main__":
    if sys.argv[1] == "--junta":       # propoe.py --junta cards.json brolls.json -o legenda.json
        junta(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[sys.argv.index("-o") + 1]))
        sys.exit(0)
    plano, resumo = do_arquivo(Path(sys.argv[1]), float(sys.argv[2]), movimento.le())
    print(json.dumps(plano, ensure_ascii=False, indent=1))
    print(resumo, file=sys.stderr)
