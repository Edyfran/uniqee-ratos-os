#!/usr/bin/env python3
"""Transcrição -> cards de legenda viral, prontos para o plano.

    python cards_da_fala.py t1.json t2.json:31.4 -o cards.json

Cada argumento é um transcript do `transcribe.py`, com deslocamento opcional
depois de `:` — é assim que dois blocos concatenados viram uma linha do tempo só.

A quebra acontece na pontuação e na pausa da fala, nunca no meio de um sintagma:
um card que terminasse em "e", "do" ou "que" deixa a frase pendurada e o olho
lê duas vezes. Por isso a última palavra nunca é átona — ela vai para o card
seguinte, mesmo que isso deixe o card com três palavras em vez de quatro.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
import transcript as tr

# átonas: não seguram o fim de um card nem merecem peso na tela
ATONAS = {
    "o", "a", "os", "as", "e", "de", "do", "da", "dos", "das", "que", "um",
    "uma", "no", "na", "nos", "nas", "em", "com", "pra", "para", "por", "se",
    "ao", "à", "às", "aos", "ou", "mas", "meu", "meus", "minha", "minhas",
    "seu", "sua", "teu", "tua", "esse", "essa", "este", "esta", "isso", "aqui",
    "aí", "eu", "ele", "ela", "você", "te", "me", "lhe", "já", "e/ou",
    "pelo", "pela", "pelos", "pelas", "num", "numa", "seus", "suas", "teus", "tuas", "sem",
    "é",  # não é átona, mas pendura igual: "CADA NINJA DESSES É | UM AGENTE"
}
MAX_PALAVRAS = 4
PAUSA = 0.24          # silêncio que o ouvido já lê como fim de frase
PISO = 0.35           # menos que isso e o card pisca antes de ser lido
LARGURA = 22          # caracteres que cabem numa linha da legenda

# Espelham o `ritmo` padrão do plano no `captions_viral`. Acoplamento consciente:
# entrar não é estar legível, e a entrada cresce com o número de palavras. Piso
# fixo aprova um card de 0,37s com quatro palavras — 0,27s entrando e 0,10s na
# tela. Se um plano mudar o ritmo, quem reclama é o lint do renderer.
ENTRA, PASSO = 0.167, 0.033
INTEIRO = 0.14        # tempo mínimo com a frase toda parada


def piso_do_card(n: int) -> float:
    """O mínimo que um card de `n` palavras precisa durar.

    Nunca abaixo de PISO: o renderer cobra as duas coisas, tempo de leitura e
    tempo com a frase inteira parada, e a conta por palavra só ultrapassa o piso
    fixo a partir de três. Sem o `max`, um card de duas palavras sai em 0,34s e
    passa aqui pra ser reprovado no lint.
    """
    return max(PISO, ENTRA + PASSO * (n - 1) + INTEIRO)


FIM = (".", "?", "!", ",", ";", ":")


def _spec(spec: str) -> tuple[str, float]:
    """`caminho.json` ou `caminho.json:12.5` (deslocamento em segundos). Só é deslocamento
    o que vem depois do último `:` e é número: no Windows o caminho começa com `D:`."""
    caminho, _, off = spec.rpartition(":")
    try:
        return caminho, float(off)
    except ValueError:
        return spec, 0.0


def ler(spec: str) -> list[dict]:
    caminho, desloc = _spec(spec)
    return colar_moeda([{"tx": tr.corrigir_termo(w["text"]), "t0": w["start"] + desloc,
                         "t1": w["end"] + desloc}
                        for w in tr.palavras(caminho)])


def colar_moeda(palavras: list[dict]) -> list[dict]:
    """Junta o que o Whisper parte em pedaços: `R` `$197` `,00` são três
    palavras na transcrição e uma coisa só na tela. Sem isso a legenda de um
    preço sai "DE R $197 00" — e preço é o que a VSL inteira constrói.
    """
    saida: list[dict] = []
    for w in palavras:
        tx = w["tx"].strip()
        anterior = saida[-1]["tx"].strip() if saida else ""
        cola = (saida and (
            (anterior.rstrip(".,").upper() == "R" and tx.startswith("$"))
            or (tx.startswith(",") and anterior and anterior[-1].isdigit())))
        if cola:
            saida[-1] = {"tx": anterior + tx, "t0": saida[-1]["t0"], "t1": w["t1"]}
        else:
            saida.append(dict(w))
    return saida


def corrigir(palavras: list[dict], pares: list[tuple[str, str]]) -> list[dict]:
    """Troca uma sequência de palavras por outra, mantendo os tempos.

    A legenda é a fala literal, então o que o Whisper ouve errado vai pra tela
    errado — "seu agente não vai esquecer" virou "só a gente não vai esquecer",
    e ninguém percebe até ver o vídeo. Aqui a correção é declarada uma vez e
    some do caminho.

    O intervalo da sequência trocada é repartido entre as palavras novas por
    tamanho: sem isso o karaokê perde o passo no resto do card.
    """
    def nu(t: str) -> str:
        return t.strip(" ,.!?;:—").lower()

    for errado, certo in pares:
        alvo = [nu(x) for x in errado.split()]
        novas = certo.split()
        i = 0
        while i + len(alvo) <= len(palavras):
            if [nu(w["tx"]) for w in palavras[i:i + len(alvo)]] != alvo:
                i += 1
                continue
            trecho = palavras[i:i + len(alvo)]
            t0, t1 = trecho[0]["t0"], trecho[-1]["t1"]
            # a pontuação final era da última palavra trocada; ela continua
            cauda = trecho[-1]["tx"][len(trecho[-1]["tx"].rstrip(" ,.!?;:—")):]
            total = sum(len(x) for x in novas)
            marca, saida = t0, []
            for k, x in enumerate(novas):
                passo = (t1 - t0) * len(x) / total
                saida.append({"tx": x + (cauda if k == len(novas) - 1 else ""),
                              "t0": round(marca, 3),
                              "t1": round(t1 if k == len(novas) - 1 else marca + passo, 3)})
                marca += passo
            palavras[i:i + len(alvo)] = saida
            i += len(novas)
    return palavras


def agrupar(palavras: list[dict], max_palavras: int = MAX_PALAVRAS,
            pausa: float = PAUSA, largura: int = LARGURA) -> list[list[dict]]:
    cards: list[list[dict]] = []
    inicio = 0                                    # primeira palavra do card atual
    for i, w in enumerate(palavras):
        n = i - inicio + 1
        prox = palavras[i + 1]["t0"] if i + 1 < len(palavras) else None
        silencio = 9.0 if prox is None else prox - w["t1"]
        pontua = w["tx"].rstrip().endswith(FIM)
        # o card que não cabe numa linha é quebrado pelo renderer, e a quebra
        # cai no meio da frase — fechar antes é o que mantém a leitura inteira
        larga = sum(len(x["tx"].strip(" ,.!?;:")) + 1
                    for x in palavras[inicio:i + 1]) - 1 >= largura
        if not (pontua or silencio >= pausa or n >= max_palavras or larga):
            continue
        # Estourou a linha: a palavra que estourou abre o card seguinte, senão o
        # corte só acontece depois do estouro e a linha continua larga demais.
        #
        # A largura ganha da pontuação, e isso é deliberado. "O processo fica
        # registrado." fecha no ponto e sai com 26 caracteres, que o renderer
        # quebra em duas linhas no meio da frase. Sobrando a última palavra pro
        # card seguinte, ela vira ênfase — que é como essa legenda já lê.
        fim = i if (larga and n > 1) else i + 1
        # Estourou com uma vírgula no meio do card: o corte vai pra vírgula. Senão o
        # card junta o fim de uma oração com o verbo da seguinte: "Eles analisaram
        # os anúncios, cruzaram com as vendas" saía "OS ANÚNCIOS CRUZARAM"
        if larga and n > 2:
            virgula = [k for k in range(inicio + 1, fim - 1) if palavras[k]["tx"].rstrip().endswith(FIM)]
            if virgula:
                fim = virgula[-1] + 1
        # não deixar átona pendurada no fim — a não ser que a pontuação mande;
        # a devolvida abre o card seguinte, que é onde ela pertence
        # A pontuação que manda é a da palavra que FICOU no fim, não a da que
        # estourou: com "celular," empurrado pela largura, "ELE APROVA PELO"
        # passava porque a vírgula do "celular" isentava o "pelo".
        while (fim - inicio > 1 and not palavras[fim - 1]["tx"].rstrip().endswith(FIM)
               and palavras[fim - 1]["tx"].strip(" ,.!?;:").lower() in ATONAS):
            fim -= 1
        cards.append(palavras[inicio:fim])
        inicio = fim
        # a que estourou abre o card seguinte, mas o ponto dela ainda fecha a frase:
        # sem isto o card novo segue pela frase de lá ("ARTIFICIAL O MATHEUS"), e a
        # átona devolvida vai junto ("PELO CELULAR."). Vírgula não: "ALUNOS | DE DIA"
        # picota o que "ALUNOS DE DIA" lia inteiro
        if fim <= i and w["tx"].rstrip().endswith((".", "!", "?")):
            cards.append(palavras[fim:i + 1])
            inicio = i + 1
    if inicio < len(palavras):
        cards.append(palavras[inicio:])
    # Dois cards que ninguém lê: a átona sozinha ("E"), que é um piscar sem
    # significado, e o card curto demais para o olho — abaixo de PISO segundos a
    # palavra aparece e some antes de ser lida. Os dois se resolvem fundindo no
    # vizinho, e a pontuação que os criou não some: ela está no texto.
    i = 0
    while i < len(cards):
        c = cards[i]
        so_atona = len(c) == 1 and c[0]["tx"].strip(" ,.!?;:").lower() in ATONAS
        curto = len(cards) > 1 and c[-1]["t1"] - c[0]["t0"] < PISO
        if so_atona or curto:
            # Átona sozinha vai SEMPRE pra frente: ela se apoia no que vem
            # depois ("que eu já te mostrei"), e jogá-la pra trás recria
            # exatamente o card terminado em átona que o agrupamento evitou.
            # Card curto que não é átona pode ir pro vizinho menor, pra não
            # estourar a linha de um card que já estava cheio.
            larg = lambda c: sum(len(w["tx"].strip(" ,.!?;:")) + 1 for w in c) - 1
            antes = larg(cards[i - 1]) if i else 10 ** 6
            depois = larg(cards[i + 1]) if i + 1 < len(cards) else 10 ** 6
            # Escolher o vizinho menor não basta: o menor também pode estourar.
            # Card de 0.3s pisca; card em duas linhas quebra a frase no meio, e
            # essa é a regra dura. Quando as duas opções estouram, o curto fica.
            eu = larg(c)
            # A fusão não atravessa ponto final: "ARTIFICIAL." curto ia pra frente e saía
            # "ARTIFICIAL ELE GRAVOU", juntando duas frases. Sem vizinho da mesma frase, o
            # curto fica e toma tempo emprestado lá embaixo.
            fecha = lambda k: cards[k][-1]["tx"].rstrip().endswith((".", "!", "?"))
            pode_frente = i + 1 < len(cards) and not fecha(i)
            pode_tras = i > 0 and not fecha(i - 1)
            if not (pode_frente or pode_tras):
                i += 1
                continue
            pra_frente = pode_frente and (so_atona or not pode_tras or depois <= antes)
            cabe = (depois if pra_frente else antes) + 1 + eu <= largura
            if not cabe and not so_atona:
                i += 1
                continue
            if pra_frente:
                cards[i + 1] = c + cards[i + 1]
            else:
                cards[i - 1] = cards[i - 1] + c
            cards.pop(i)
            continue
        i += 1

    # Sobrou card curto porque as duas fusões estouravam a linha. A legenda pode
    # entrar um pouco antes da palavra sem soar errada — a fala não se mexe, só o
    # texto aparece um piscar mais cedo. Então ele toma emprestado do vizinho de
    # trás, e só se o vizinho puder pagar sem ficar curto ele mesmo.
    # O PRIMEIRO card não tem vizinho de trás, mas tem o silêncio do começo do
    # take. Sem isso ele fica curto pra sempre — e é justamente o card que abre
    # o bloco, o mais caro de perder.
    if cards:
        c = cards[0]
        falta = piso_do_card(len(c)) + 0.01 - (c[-1]["t1"] - c[0]["t0"])
        if falta > 0 and c[0]["t0"] > 0:
            c[0] = {**c[0], "t0": round(max(0.0, c[0]["t0"] - falta), 3)}
    for i in range(1, len(cards)):
        c, ant = cards[i], cards[i - 1]
        # mira um fio acima do piso: arredondar pra milissegundo pode deixar o
        # card em 0,3499 e o lint cobra `>= 0,35`
        falta = piso_do_card(len(c)) + 0.01 - (c[-1]["t1"] - c[0]["t0"])
        folga = (ant[-1]["t1"] - ant[0]["t0"]) - piso_do_card(len(ant)) - 0.01
        if falta > 0 and folga > 0:
            paga = min(falta, folga)
            c[0] = {**c[0], "t0": round(c[0]["t0"] - paga, 3)}
            ant[-1] = {**ant[-1], "t1": round(ant[-1]["t1"] - paga, 3)}
    # Ainda curto (o card que fecha a frase e não pode mais se fundir com a
    # seguinte): fica na tela pelo silêncio que vem depois dele, sem invadir o
    # próximo card. A fala não se mexe; o texto só demora um piscar pra sair.
    for i, c in enumerate(cards):
        falta = piso_do_card(len(c)) + 0.01 - (c[-1]["t1"] - c[0]["t0"])
        if falta <= 0:
            continue
        teto = cards[i + 1][0]["t0"] if i + 1 < len(cards) else c[-1]["t1"] + falta
        c[-1] = {**c[-1], "t1": round(min(teto, c[-1]["t1"] + falta), 3)}
    return cards


def montar(cards: list[list[dict]], fonte: str,
           punch: set[str], filler_extra: set[str], alta: bool = True) -> list[dict]:
    fora = {p.lower() for p in filler_extra} | ATONAS
    saida = []
    for c in cards:
        words = []
        for w in c:
            limpo = w["tx"].strip(" ,.!?;:")
            # sem a caixa alta, o "Eu" que o Whisper põe no meio da frase vira
            # "eu"; átona nunca é nome próprio
            limpo = limpo.upper() if alta else limpo.lower() if limpo.lower() in ATONAS else limpo
            nu = limpo.lower()
            item = {"tx": limpo, "t0": round(w["t0"], 2), "t1": round(w["t1"], 2)}
            if nu in punch:
                item["enf"] = "punch"
            elif nu in fora:
                item["enf"] = "filler"
            words.append(item)
        card = {"t0": round(c[0]["t0"], 2), "t1": round(c[-1]["t1"], 2),
                "fonte": fonte, "words": words}
        if alta:
            # Uma palavra de destaque por cartão, parada, como na referência: a de marca ou a mais
            # comprida entre as cheias. O destaque que andava com a fala acendia 2 a 3 palavras por cartão.
            marcas = {v.lower() for v in tr.GLOSSARIO.values()}
            cheias = [w for w in words if w.get("enf") is None and len(w["tx"]) >= 4]
            if cheias and not any(w.get("enf") == "punch" for w in words):
                max(cheias, key=lambda w: (w["tx"].lower() in marcas, len(w["tx"])))["enf"] = "chave"
            card["modo"] = "chave"
            card["largura"] = 0.86      # a palavra de destaque cresce 20%: sem isto a linha encosta na borda (Vision: <3%)
        saida.append(card)
    return saida


# Frase de abertura que prometeria ganho: o gancho não pode prometer dinheiro nem resultado (regra do dono).
PROMESSA = re.compile(r"\b(r\$|reais|mil|milh|dinheiro|lucr|fatur|ganh|renda|rico|fortuna|garant|milagre)", re.I)
GANCHO_LINHA = 18     # caracteres das duas primeiras linhas do gancho
GANCHO_ULTIMA = 24    # a terceira pode ser mais larga: a peça g_gancho encolhe a laje que não cabe


def gancho(palavras: list[dict], limite: float = 2.6) -> dict | None:
    """O gancho escrito dos primeiros ~2,5 s: até 3 linhas tiradas da fala de abertura, na ordem em que
    foram ditas, parando antes de uma palavra átona. Devolve a peça da biblioteca (`g_gancho`) no formato do
    `pecas` do plano, ou None se a abertura promete ganho ou tem menos de 4 palavras."""
    abre = [w for w in palavras if w["t0"] < limite + 3.0][:14]
    texto = " ".join(w["tx"] for w in abre)
    if len(abre) < 4 or PROMESSA.search(texto):
        return None
    pendura = ATONAS | {"só"}          # linha que acaba nelas deixa a frase pendurada
    palavras_g = [w["tx"].strip(" ,.!?;:").upper() for w in abre if w["tx"].strip(" ,.!?;:")]
    linhas: list[list[str]] = [[]]
    for tx in palavras_g:
        if linhas[-1] and len(" ".join(linhas[-1] + [tx])) > (GANCHO_LINHA if len(linhas) < 3 else GANCHO_ULTIMA):
            if len(linhas) == 3:
                break
            # as átonas do fim da linha descem junto com a palavra que elas seguram
            sobe = []
            while len(linhas[-1]) > 1 and linhas[-1][-1].lower() in pendura:
                sobe.insert(0, linhas[-1].pop())
            linhas.append(sobe)
        linhas[-1].append(tx)
    while len(linhas[-1]) > 1 and linhas[-1][-1].lower() in pendura:
        linhas[-1].pop()
    linhas = [" ".join(l) for l in linhas if l]
    if len(linhas) < 2:
        return None
    linhas[-1] = "_" + linhas[-1]          # a última linha no marcador amarelo, como o verde da referência
    return {"peca": "g_gancho", "t0": 0.0, "t1": limite,
            "q": {"l": "|".join(linhas), "pos": "topo", "dur": limite}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts", nargs="+", help="t.json ou t.json:deslocamento")
    ap.add_argument("--fonte", default="creato")
    ap.add_argument("--max", type=int, default=MAX_PALAVRAS)
    ap.add_argument("--pausa", type=float, default=PAUSA)
    ap.add_argument("--corrigir", action="append", default=[], metavar="ERRADO=CERTO",
                    help="o que o Whisper ouviu errado: --corrigir "
                         "\"só a gente=seu agente\" (repetível)")
    ap.add_argument("--punch", default="", help="palavras em destaque, separadas por vírgula")
    ap.add_argument("--filler", default="", help="átonas extras deste vídeo")
    ap.add_argument("--acento", help="cor da palavra que acende; com ele sai o plano inteiro")
    ap.add_argument("--ritmo", help="entrada,passo em s (ex. 0.167,0.033)")
    ap.add_argument("--legenda", help="preset do captions_viral (--presets lista); a caixa "
                                      "da letra fica com ele, então o texto sai como foi dito")
    ap.add_argument("--layout", choices=["topo", "centro", "faixa", "faixa_criativo", "rodape", "entre", "alto"],
                    help="onde a legenda assenta em todo card (captions_viral, LAYOUTS); sem ele, a faixa")
    ap.add_argument("--sem-gancho", action="store_true", help="não escreve o gancho dos primeiros 2,5 s")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    palavras: list[dict] = []
    for spec in a.transcripts:
        palavras += ler(spec)
    palavras.sort(key=lambda w: w["t0"])
    palavras = corrigir(palavras, [tuple(c.split("=", 1)) for c in a.corrigir])

    cards = montar(agrupar(palavras, a.max, a.pausa), a.fonte,
                   {p.strip().lower() for p in a.punch.split(",") if p.strip()},
                   {p.strip() for p in a.filler.split(",") if p.strip()}, alta=not a.legenda)
    if a.layout:
        for c in cards:
            c["layout"] = a.layout
    saida = cards
    if a.acento or a.ritmo or a.legenda:
        # A direção vem do estilo, pela fábrica: sem isto cada plano de VSL
        # escrevia o mesmo acento e o mesmo ritmo à mão, 21 vezes.
        saida = {"cards": cards}
        if a.acento:
            saida["acento"] = a.acento
        if a.ritmo:
            ent, passo = (float(x) for x in a.ritmo.split(","))
            saida["ritmo"] = {"entrada": ent, "stagger": passo}
        if a.legenda:
            saida["legenda"] = a.legenda
        # `--acento` só vem quando a biblioteca v2 existe (fabrica.py); sem ela não há peça pra renderizar.
        g = None if a.sem_gancho or not a.acento else gancho(palavras)
        if g:
            saida["pecas"] = [g]
    a.out.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.out}  {len(palavras)} palavras -> {len(cards)} cards")


def _autoteste() -> None:
    ws = [{"tx": t, "t0": i * 0.3, "t1": i * 0.3 + 0.25}
          for i, t in enumerate("me trouxe o que vale manter".split())]
    cards = agrupar(ws, max_palavras=4, pausa=9.0)
    assert sum(len(c) for c in cards) == len(ws), "palavra sumiu no agrupamento"
    assert cards[0][-1]["tx"] not in ATONAS, cards[0]
    assert [w["tx"] for w in sum(cards, [])] == [w["tx"] for w in ws], "ordem trocou"
    piscada = [{"tx": "olha", "t0": 0.0, "t1": 0.1},
               {"tx": "isso.", "t0": 0.1, "t1": 0.2},
               {"tx": "aqui", "t0": 0.5, "t1": 1.4}]
    assert all(c[-1]["t1"] - c[0]["t0"] >= PISO for c in agrupar(piscada)), "card pisca"

    # a átona que sobra sozinha volta pra FRENTE; jogá-la pra trás recria o
    # card terminado em átona que o agrupamento tinha acabado de desfazer
    frase = "e os bônus que eu já te mostrei".split()
    ws = [{"tx": t, "t0": i * 0.3, "t1": i * 0.3 + 0.28} for i, t in enumerate(frase)]
    for c in agrupar(ws):
        assert c[-1]["tx"] not in ATONAS, [w["tx"] for w in c]

    # a palavra do ponto que estoura a linha vai pro card seguinte, e fecha ele
    frase = "um agente de inteligência artificial. O Matheus só confere".split()
    ws = [{"tx": t, "t0": i * 0.4, "t1": i * 0.4 + 0.38} for i, t in enumerate(frase)]
    for c in agrupar(ws):
        assert not any(w["tx"].endswith((".", "!", "?")) for w in c[:-1]), [w["tx"] for w in c]
    # átona antes da palavra que estourou: não fica pendurada, com vírgula ou com ponto
    for frase in ("ele aprova pelo celular, sem nem levantar do sofá.", "ele aprova pelo celular. Toca no botão"):
        ws = [{"tx": t, "t0": i * 0.4, "t1": i * 0.4 + 0.38} for i, t in enumerate(frase.split())]
        for c in agrupar(ws):
            assert c[-1]["tx"] not in ATONAS, [w["tx"] for w in c]
            assert not any(w["tx"].endswith((".", "!", "?")) for w in c[:-1]), [w["tx"] for w in c]

    # card curto no fim da frase não se funde com a frase seguinte
    frase = "um agente de inteligência artificial. Ele gravou uma apresentação".split()
    ws = [{"tx": w, "t0": i * 0.4, "t1": i * 0.4 + (0.2 if w == "artificial." else 0.38)} for i, w in enumerate(frase)]
    for c in agrupar(ws):
        assert not any(w["tx"].endswith((".", "!", "?")) for w in c[:-1]), [w["tx"] for w in c]
    ws = [{"tx": w, "t0": i * 0.4, "t1": i * 0.4 + 0.38} for i, w in enumerate("ele cruza seus anúncios".split())]
    assert agrupar(ws)[0][-1]["tx"] != "seus", [w["tx"] for w in agrupar(ws)[0]]
    ws = [{"tx": w, "t0": i * 0.4, "t1": i * 0.4 + 0.38} for i, w in enumerate("eles analisaram os anúncios, cruzaram com as vendas".split())]
    assert "anúncios, cruzaram" not in " ".join(" ".join(w["tx"] for w in c) + " |" for c in agrupar(ws)), \
        [[w["tx"] for w in c] for c in agrupar(ws)]
    ws = [{"tx": w, "t0": i * 0.4, "t1": i * 0.4 + 0.38} for i, w in enumerate("cada ninja desses é um agente".split())]
    assert agrupar(ws)[0][-1]["tx"] != "é", [w["tx"] for w in agrupar(ws)[0]]

    c = corrigir([{"tx": "Só", "t0": 1.0, "t1": 1.2},
                  {"tx": "a", "t0": 1.2, "t1": 1.3},
                  {"tx": "gente", "t0": 1.3, "t1": 1.6},
                  {"tx": "esquecer.", "t0": 1.6, "t1": 2.0}],
                 [("só a gente", "seu agente")])
    assert [w["tx"] for w in c] == ["seu", "agente", "esquecer."], c
    assert c[0]["t0"] == 1.0 and c[1]["t1"] == 1.6, c    # o intervalo não escorrega

    m = colar_moeda([{"tx": "R", "t0": 0.0, "t1": 0.2},
                     {"tx": "$197", "t0": 0.2, "t1": 0.6},
                     {"tx": ",00", "t0": 0.6, "t1": 0.8},
                     {"tx": "à", "t0": 0.8, "t1": 0.9}])
    assert [w["tx"] for w in m] == ["R$197,00", "à"], m
    assert m[0]["t1"] == 0.8, m
    print("ok")


if __name__ == "__main__":
    if "--autoteste" in sys.argv:
        _autoteste()
    else:
        sys.exit(main())
