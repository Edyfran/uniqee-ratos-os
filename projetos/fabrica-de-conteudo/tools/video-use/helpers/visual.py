"""O `visual.json`: a pauta de prova do vídeo de celular (fase (b) do plano visual, `docs/kit/plano-visual.md`).

Uma batida por ideia dita: o que MOSTRAR (`tipo`, `fonte`), em que `layout`, e a `alternativa` pra quando a
fonte não vier. Tempos em segundos do vídeo CORTADO, ou na palavra dita (`{"palavra": "Wi-Fi", "n": 1}`,
resolvida pela transcrição cortada, que é a âncora do repo). Só biblioteca padrão e o `movimento.py`.

    python visual.py visual.json [--dur 46.2] [--fala fala_cortada.json]     # confere; sai 1 se reprova
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import movimento

TIPOS = ("print", "marca", "numero", "antes_depois", "tela_aluno", "demo", "animacao", "texto")
LAYOUTS = ("dividida", "cheia", "rosto", "rosto_cartao")
# O que cada `origem` pede em `fonte` (campo obrigatório -> mensagem). `arquivo` é o que o aluno mandou.
ORIGENS = {"url": ("url",), "busca": ("consulta",), "busca_imagem": ("consulta",), "marca": ("nome",),
           "numero": ("valor",), "aluno": ("pedido",), "peca": ("peca",), "arquivo": ("caminho",),
           "par": ("antes", "depois"),
           "midia": ("url",)}                     # `midia`: foto do post (X), imagem do README ou capa (og:image) da fonte citada; `n` escolhe, `recorte` corta            # `par`: o antes e o depois, cada um uma fonte de imagem (ORIGENS_DE_IMAGEM)
ORIGENS_DE_IMAGEM = ("midia", "url", "busca", "busca_imagem", "marca", "aluno", "arquivo")
# Fora do código: depende de rede ou do aluno, então a pauta já traz a saída (`alternativa`).
PRECISA_ALTERNATIVA = {"url", "busca", "busca_imagem", "marca", "aluno", "arquivo", "par", "midia"}
# A escada da prova (mostrar, não dizer): 1) a mídia real da fonte que a fala cita (foto do post, imagem do README, capa do site:
# `origem: midia`), 2) o que o aluno manda, 3) foto de licença livre, 4) a DEMONSTRAÇÃO animada da biblioteca, que mostra a coisa
# acontecendo (`origem: peca`), 5) texto, só como último recurso. Imagem real entra por peça (antes e depois, cartão da dividida,
# `r_print` na cheia), nunca crua em tela cheia. As peças que o kit leva pra
# demonstrar, e os parâmetros de cada uma, estão no `pauta-visual.md`; o código confere o nome e não deixa vir peça de fora do kit.
PECAS_DE_DEMO = ("i_terminal", "i_tv", "d_grade", "d_linha")
# A mídia de uma fonte já citada serve toda batida que fala da mesma coisa: se o vídeo já mostra a foto de um post (`midia` do X),
# a batida que mostra a TV mudando (`i_tv` em `limpa`/`instala`) usa a foto dele (com `recorte`), e o desenho vai na `alternativa`.
HOSTS_POST = ("x.com", "twitter.com", "www.x.com", "www.twitter.com")
TEXTO_MAX_ATE_45S = 1       # batidas de texto puro (painel de texto) num vídeo de até 45 s; acima disso, 1 por 45 s
COBERTURA_MIN = 0.80        # fração do tempo com prova na tela (rosto e rosto sem prova ficam de fora)
SEM_PROVA = ("rosto",)
# Confiança da batida (prevê se vai ficar bom antes de renderizar): fraca vira pergunta ao aluno.
FORTE, MEDIA, FRACA = "forte", "média", "fraca"
_RANK = {FRACA: 0, MEDIA: 1, FORTE: 2}
FRACAS_SEM_PERGUNTA_POR_45S = 1   # batida fraca que ninguém perguntou: 1 por 45 s de vídeo
MAX_PERGUNTAS = 5                 # a pergunta única do aluno tem no máximo 5 itens
# Variedade (rodada de 21/10: 5 terminais seguidos num vídeo de celular): o mesmo tipo de peça no máximo 2 vezes seguidas e em 40% das batidas.
MAX_SEGUIDAS, MAX_FRACAO_TIPO, MIN_BATIDAS_FRACAO = 2, 0.40, 5
# Prova real: com menos de 30% das batidas fortes, a pergunta ao aluno é obrigatória (até 5 itens) e oferece o antes×depois do vídeo dele.
FORTES_MIN = 0.30
MIN_PERGUNTAS_PROVA_BAIXA = 3
CHAMADA_ROSTO = 2.8         # s de `rosto` no fim do vídeo de 8 s ou mais: é onde a chamada final (g_comenta) cabe
DOIS_CHEIA_MAX = 7.0        # dois `cheia` seguidos só se somam menos que isto (docs/direcao.md)


def le(caminho: Path) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def ancora(doc: dict, palavras: list[dict]) -> dict:
    """Troca `t0`/`t1` dados como `{"palavra", "n"}` pelo início da palavra dita (a n-ésima vez que aparece), no tempo
    do vídeo cortado. Devolve uma cópia; palavra que não aparece estoura com a frase de quem escreveu."""
    def acha(ref, onde):
        alvo, n = ref["palavra"].lower().strip(".,!?;:"), int(ref.get("n", 1))
        vistas = [w for w in palavras if w["text"].lower().strip(".,!?;:") == alvo]
        if len(vistas) < n:
            raise ValueError(f"batida {onde}: a palavra “{ref['palavra']}” não aparece {n}x na fala")
        return round(vistas[n - 1]["start"], 3)
    out = json.loads(json.dumps(doc))
    for b in out.get("batidas", []):
        for k in ("t0", "t1"):
            if isinstance(b.get(k), dict):
                b[k] = acha(b[k], b.get("id", "?"))
    return out


def _conf_fonte(f) -> tuple[str, str]:
    o = (f or {}).get("origem")
    if o in ("aluno", "arquivo", "midia", "url") or (o == "busca" and f.get("url")):
        return FORTE, "prova real da fonte citada ou do aluno"
    if o == "numero":
        return (FORTE, "número com fonte") if f.get("github_repo") or str(f.get("de", "")).startswith("http") else (MEDIA, "número dito, sem fonte pública")
    if o == "marca":
        return FRACA, "logo solto não é prova"
    if o in ("busca_imagem", "busca"):
        return FRACA, "foto genérica"
    if o == "par":
        return min((_conf_fonte(f.get(k)) for k in ("antes", "depois")), key=lambda c: _RANK[c[0]])
    return FRACA, "demonstração genérica"


_STOP_CASA = {"para", "pra", "como", "mais", "isso", "esse", "essa", "tudo", "aqui", "você", "voce", "pelo", "pela", "uma", "que", "com", "por", "dos", "das", "num", "numa"}


def _palavras(t: str) -> set[str]:
    """Raízes (4 letras, ou o número inteiro) das palavras com conteúdo de um texto: serve pra ver se a peça fala do que a fala fala."""
    import re
    return {w[:4] if not w.isdigit() else w for w in re.findall(r"\w+", str(t).lower()) if (len(w) >= 4 or w.isdigit()) and w not in _STOP_CASA}


def casa_confere(b: dict) -> bool:
    """`casa` só conta se a peça mostra a AÇÃO exata da frase. O código não entende a ação, mas pega a casa falsa mais comum: a peça
    (comando, rótulo, números) não tem nenhuma palavra da fala. Sem `fala` na batida não há com o que comparar: confia."""
    if not str(b.get("casa", "")).strip():
        return False
    fala = _palavras(b.get("fala", ""))
    if not fala:
        return True
    q = ((b.get("fonte") or {}).get("q") or {})
    return bool(fala & _palavras(" ".join(str(v) for v in q.values())))


def familia(b: dict) -> str | None:
    """O tipo de peça da batida pra variedade: a peça de demonstração da biblioteca (`i_terminal`, `d_grade`...). Print, foto e número
    de fontes diferentes não são o mesmo tipo de peça; eles (e o `rosto`) quebram a sequência."""
    f = b.get("fonte") or {}
    return f.get("peca") if b.get("layout") != "rosto" and f.get("origem") == "peca" else None


def baixa_prova(bs: list[dict]) -> bool:
    """Menos de 30% das batidas com prova (não `rosto`) são fortes: a pergunta ao aluno deixa de ser opcional."""
    com = [b for b in bs if (c := confianca(b))]
    return bool(com) and sum(c[0] == FORTE for c in map(confianca, com)) < FORTES_MIN * len(com)


def a_perguntar(bs: list[dict]) -> list[dict]:
    """As batidas que entram na pergunta única, as de mais tempo primeiro: as fracas perguntadas, e com prova baixa também as médias."""
    if not baixa_prova(bs):
        return fracas(bs)[0]
    nao_forte = [b for b in bs if (c := confianca(b)) and c[0] != FORTE and isinstance(b.get("pergunta"), dict)]
    return sorted(nao_forte, key=lambda b: b["t0"] - b["t1"])[:MAX_PERGUNTAS]


def confianca(b: dict) -> tuple[str, str] | None:
    """(forte|média|fraca, por quê) de uma batida, por regra; `None` no `rosto` (gancho e chamada não pedem prova).
    forte: prova real da fonte citada ou do aluno. média: demonstração que mostra exatamente a ação dita (o agente afirma
    em `casa` o que da peça é o que a fala diz). fraca: texto, logo solto, foto genérica ou demonstração sem `casa`."""
    if b.get("layout") == "rosto":
        return None
    if b.get("tipo") == "texto":
        return FRACA, "texto na tela"
    if b.get("tipo") == "marca":
        return FRACA, "logo solto não é prova"
    f = b.get("fonte") or {}
    if f.get("origem") == "peca":
        if not str(b.get("casa", "")).strip():
            return FRACA, "demonstração genérica (falta `casa`)"
        return (MEDIA, "demonstração da ação dita") if casa_confere(b) else (FRACA, "casa falsa: a peça não mostra nada do que a fala diz")
    return _conf_fonte(f)


def mmss(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def pergunta_da(b: dict, antes_depois: bool = False) -> str:
    """O item da pergunta única ao aluno para uma batida fraca: `pergunta` = {x, demo}, preenchido pelo agente da pauta.
    `antes_depois` (prova baixa no vídeo): a opção 3 vira o antes×depois do próprio vídeo dele, que a Fábrica já tem."""
    q = b["pergunta"]
    if antes_depois:
        return (f"No trecho “{b.get('fala', '')}” ({mmss(b['t0'])}), o que você quer mostrar? 1) um print/vídeo seu de {q['x']}, "
                f"2) {q['demo']}, 3) o antes×depois do seu próprio vídeo (o bruto e o editado, a Fábrica já tem os dois), 4) deixa comigo")
    return (f"No trecho “{b.get('fala', '')}” ({mmss(b['t0'])}), o que você quer mostrar? 1) um print/vídeo seu de {q['x']}, "
            f"2) {q['demo']}, 3) um trecho do seu próprio vídeo, 4) deixa comigo")


def fracas(bs: list[dict]) -> tuple[list[dict], list[dict]]:
    """(perguntadas, sem pergunta) entre as batidas fracas. Só as 5 de maior tempo contam como perguntadas (o limite da pergunta)."""
    f = [b for b in bs if (c := confianca(b)) and c[0] == FRACA]
    com = sorted((b for b in f if isinstance(b.get("pergunta"), dict)), key=lambda b: b["t0"] - b["t1"])[:MAX_PERGUNTAS]
    return com, [b for b in f if b not in com]


def _alternativa(b: dict, n: str) -> list[str]:
    a = b.get("alternativa")
    if not isinstance(a, dict):
        return [f"{n}: a alternativa é obrigatória (a fonte depende de rede ou do aluno e pode não vir)"]
    erros = []
    if a.get("tipo") == "animacao":      # a demonstração da biblioteca vale mais que o texto (escada da prova): vem com a peça
        erros += [f"{n}: alternativa: {e}" for e in _fonte_peca(a.get("fonte"))]
    elif a.get("tipo") != "texto" or not (a.get("texto") or "").strip():
        erros.append(f"{n}: a alternativa é `animacao` (uma peça de demonstração) ou `texto` com o texto escrito (a frase citada, marcada como citação, ou a chamada)")
    if a.get("layout") not in LAYOUTS:
        erros.append(f"{n}: a alternativa precisa de layout ({', '.join(LAYOUTS)})")
    return erros


def _midias(f) -> list[str]:
    """As `url` de `origem: midia` de uma fonte (dentro do `par`, as duas pontas)."""
    if not isinstance(f, dict):
        return []
    if f.get("origem") == "midia":
        return [str(f.get("url", ""))]
    return [u for k in ("antes", "depois") for u in _midias(f.get(k))] if f.get("origem") == "par" else []


def _fonte_peca(f) -> list[str]:
    """A fonte `origem: peca`: a peça é de demonstração do kit e os parâmetros (`q`) são pares simples."""
    if not isinstance(f, dict) or f.get("origem") != "peca":
        return ["a fonte da demonstração é `{\"origem\": \"peca\", \"peca\": ..., \"q\": {...}}`"]
    if f.get("peca") not in PECAS_DE_DEMO:
        return [f"a peça “{f.get('peca')}” não é de demonstração do kit ({', '.join(PECAS_DE_DEMO)})"]
    q = f.get("q", {})
    if not isinstance(q, dict) or any(isinstance(v, (dict, list)) for v in q.values()):
        return ["`q` é um dicionário de parâmetros simples (texto ou número)"]
    return []


def valida(doc: dict, dur: float | None = None) -> list[str]:
    """As mensagens do que reprova (lista vazia = passa). É o `confere` da seção 1 da spec: tipos, layouts, fonte e
    alternativa, tempo, densidade (vão e cobertura) e alternância. `dur` (s do vídeo cortado) liga a cobertura."""
    if doc.get("versao") != 1:
        return ["versao: tem que ser 1"]
    dens = doc.get("densidade", "media")
    if dens not in movimento.DENSIDADES:
        return [f"densidade “{dens}” não existe: {', '.join(movimento.DENSIDADES)}"]
    vao = movimento.DENSIDADES[dens]
    bs = doc.get("batidas")
    if not isinstance(bs, list) or not bs:
        return ["batidas: precisa de pelo menos uma"]
    erros, ids = [], set()
    for i, b in enumerate(bs):
        n = f"batida {b.get('id', i + 1)}"
        if b.get("id") in ids:
            erros.append(f"{n}: id repetido")
        ids.add(b.get("id"))
        if not (b.get("prova") or "").strip():
            erros.append(f"{n}: `prova` em branco (diga o que isto prova, em frase)")
        tipo, lay = b.get("tipo"), b.get("layout")
        if tipo not in TIPOS:
            erros.append(f"{n}: tipo “{tipo}” não existe ({', '.join(TIPOS)})")
        if lay not in LAYOUTS:
            erros.append(f"{n}: layout “{lay}” não existe ({', '.join(LAYOUTS)})")
        t0, t1 = b.get("t0"), b.get("t1")
        if not all(isinstance(t, (int, float)) for t in (t0, t1)):
            erros.append(f"{n}: t0 e t1 são segundos do vídeo cortado (ou a palavra dita, resolvida antes por `ancora`)")
        elif t1 <= t0 or t0 < 0 or (dur and t1 > dur + 0.05):
            erros.append(f"{n}: tempo fora do vídeo ({t0}–{t1}{f', vídeo de {dur:.1f} s' if dur else ''})")
        elif t1 - t0 > vao and not (b.get("muda") or "").strip() and lay != "rosto":
            erros.append(f"{n}: {t1 - t0:.1f} s passa do vão da densidade {dens} ({vao} s): diga em `muda` o que muda por dentro")
        f = b.get("fonte")
        if tipo == "texto":
            if not (b.get("porque") or "").strip():
                erros.append(f"{n}: `texto` só entra com `porque` (por que nenhuma prova serve)")
            if not (b.get("texto") or "").strip():
                erros.append(f"{n}: `texto` precisa do campo `texto`")
        elif lay != "rosto":
            if not isinstance(f, dict) or f.get("origem") not in ORIGENS:
                erros.append(f"{n}: fonte.origem tem que ser uma de {', '.join(ORIGENS)}")
            else:
                if tipo == "tela_aluno" and f["origem"] not in ("aluno", "arquivo"):
                    erros.append(f"{n}: `tela_aluno` vem da tela do aluno (origem aluno ou arquivo)")
                if tipo in ("demo", "animacao") and f["origem"] not in ("aluno", "arquivo", "peca"):
                    erros.append(f"{n}: `{tipo}` vem da tela do aluno (origem aluno ou arquivo) ou da demonstração da biblioteca (origem peca)")
                if f["origem"] == "peca":
                    erros += [f"{n}: {e}" for e in _fonte_peca(f)]
                for campo in ORIGENS[f["origem"]]:
                    if f["origem"] == "par":
                        sub = f.get(campo)
                        if not isinstance(sub, dict) or sub.get("origem") not in ORIGENS_DE_IMAGEM:
                            erros.append(f"{n}: o par precisa de `{campo}` com origem em {', '.join(ORIGENS_DE_IMAGEM)}")
                        else:
                            erros += [f"{n}: {campo}: precisa de `{c}`" for c in ORIGENS[sub["origem"]] if not str(sub.get(c, "")).strip()]
                    elif not str(f.get(campo, "")).strip():
                        erros.append(f"{n}: a fonte “{f['origem']}” precisa de `{campo}`")
                if f["origem"] == "numero" and not (f.get("de") or f.get("github_repo")):
                    erros.append(f"{n}: número sem fonte: diga em fonte.de de onde vem (“fala”, a URL) ou ponha github_repo (regra 6)")
                if f["origem"] == "url" and f.get("url") and not str(f["url"]).startswith("http"):
                    erros.append(f"{n}: fonte.url precisa começar com http")
            if (isinstance(f, dict) and f.get("origem") in PRECISA_ALTERNATIVA) or tipo in ("print", "marca"):
                erros += _alternativa(b, n)
    # a escada vale entre batidas: foto de post já citada vence o desenho da mesma coisa
    posts = [u for b in bs for u in _midias(b.get("fonte")) if urlparse(u).hostname in HOSTS_POST]
    if posts:
        for b in bs:
            f = b.get("fonte")
            if isinstance(f, dict) and f.get("peca") == "i_tv" and (f.get("q") or {}).get("modo", "limpa") in ("limpa", "instala"):
                erros.append(f"batida {b.get('id', '?')}: o vídeo já cita o post {posts[0]}; use a foto dele (`origem: midia`, com `recorte`) "
                             "e deixe o `i_tv` na `alternativa` (escada da prova: a mídia da fonte já citada vem antes do desenho)")
    # mostrar, não dizer: painel de texto é o último recurso (rosto com texto é gancho ou chamada, não painel)
    tempo = dur or max((b["t1"] for b in bs if isinstance(b.get("t1"), (int, float))), default=0)
    teto = max(TEXTO_MAX_ATE_45S, int(tempo // 45)) if tempo else TEXTO_MAX_ATE_45S
    so_texto = [b.get("id", "?") for b in bs if b.get("tipo") == "texto" and b.get("layout") != "rosto"]
    if len(so_texto) > teto:
        erros.append(f"batidas {', '.join(map(str, so_texto))}: {len(so_texto)} painéis de texto puro, o teto é {teto} num vídeo de {tempo:.0f} s. "
                     "Mostre em vez de escrever: escada da prova (a prova real, depois a demonstração da biblioteca, e só então o texto)")
    # prever: batida fraca vira pergunta ao aluno; fraca sem pergunta passa de 1 por 45 s = reprova (logo solto conta)
    for b in bs:
        q = b.get("pergunta")
        if q is not None and (not isinstance(q, dict) or not all(str(q.get(k, "")).strip() for k in ("x", "demo"))):
            erros.append(f"batida {b.get('id', '?')}: `pergunta` é {{\"x\": o que o aluno pode ter (print, vídeo), \"demo\": a demonstração concreta que você sugere}}")
        elif q and b.get("tipo") == "texto" and b.get("layout") != "rosto":
            erros.append(f"batida {b.get('id', '?')}: batida perguntada não cai em texto se o aluno não responder: ponha a melhor opção que não é texto "
                         "em `fonte` e deixe o texto na `alternativa`")
    perg, sem = fracas([b for b in bs if isinstance(b.get("t0"), (int, float))])
    tf = max(FRACAS_SEM_PERGUNTA_POR_45S, int(tempo // 45)) if tempo else FRACAS_SEM_PERGUNTA_POR_45S
    if len(sem) > tf:
        erros.append(f"batidas {', '.join(str(b.get('id', '?')) for b in sem)}: {len(sem)} batidas de confiança fraca sem pergunta ao aluno "
                     f"(texto, logo solto, foto genérica ou demonstração sem `casa`); o teto é {tf} num vídeo de {tempo:.0f} s. "
                     "Melhore a prova, ou preencha `pergunta` ({x, demo}; máx. 5 no vídeo) para o aluno escolher o que mostrar")
    # prova baixa: a pergunta ao aluno é obrigatória (a rodada de 21/10 marcou tudo "média" e não perguntou nada)
    if baixa_prova(bs) and sum(1 for b in bs if b.get("layout") != "rosto") >= 3:      # vídeo de 1 ou 2 batidas não tem o que perguntar
        nao_forte = [b for b in bs if (c := confianca(b)) and c[0] != FORTE]
        perg = [b for b in nao_forte if isinstance(b.get("pergunta"), dict)]
        falta = min(MIN_PERGUNTAS_PROVA_BAIXA, len(nao_forte)) - len(perg)
        if falta > 0:
            erros.append(f"prova real em menos de {100 * FORTES_MIN:.0f}% das batidas: a pergunta ao aluno é obrigatória; preencha `pergunta` "
                         f"({{x, demo}}) em mais {falta} batida(s) sem prova forte (até {MAX_PERGUNTAS} no vídeo). A Fábrica põe sozinha a opção do antes×depois do vídeo dele")
    # variedade: o mesmo tipo de peça, no máximo 2 seguidas e em 40% das batidas com prova
    com_prova = [b for b in sorted((b for b in bs if isinstance(b.get("t0"), (int, float))), key=lambda b: b["t0"])]
    fams = [familia(b) for b in com_prova]
    seguidas = 0
    for k, fam in enumerate(fams):
        seguidas = seguidas + 1 if k and fam and fam == fams[k - 1] else 1
        if fam and seguidas == MAX_SEGUIDAS + 1:
            erros.append(f"batidas {com_prova[k - MAX_SEGUIDAS].get('id')}–{com_prova[k].get('id')}: {seguidas} batidas seguidas de `{fam}` "
                         f"(o máximo é {MAX_SEGUIDAS}): troque a prova de uma por outro tipo de peça, ou pelo antes×depois do vídeo do aluno")
    n_prova = sum(1 for b in com_prova if b.get("layout") != "rosto")
    if n_prova >= MIN_BATIDAS_FRACAO:
        for fam in dict.fromkeys(f for f in fams if f):
            if fams.count(fam) > MAX_FRACAO_TIPO * n_prova + 1e-9:
                erros.append(f"`{fam}` é {fams.count(fam)} de {n_prova} batidas ({100 * fams.count(fam) / n_prova:.0f}%): o máximo por tipo é "
                             f"{100 * MAX_FRACAO_TIPO:.0f}%. Varie a prova")
    # alternância e cobertura só fazem sentido com os tempos em ordem
    if not erros:
        bs = sorted(bs, key=lambda b: b["t0"])
        for a, b in zip(bs, bs[1:]):
            if b["t0"] < a["t1"] - 0.05:
                erros.append(f"batida {b.get('id')}: começa em {b['t0']} antes de a {a.get('id')} acabar ({a['t1']})")
        for k in range(len(bs) - 2):
            tres = {b["layout"] for b in bs[k:k + 3]}
            if len(tres) == 1 and tres <= {"cheia", "dividida"}:
                erros.append(f"batidas {bs[k].get('id')}–{bs[k + 2].get('id')}: 3 `{bs[k]['layout']}` seguidas (alterne os layouts)")
        for a, b in zip(bs, bs[1:]):
            if a["layout"] == b["layout"] == "cheia" and b["t1"] - a["t0"] >= DOIS_CHEIA_MAX:
                erros.append(f"batidas {a.get('id')}–{b.get('id')}: dois `cheia` seguidos somam {b['t1'] - a['t0']:.1f} s (máx. {DOIS_CHEIA_MAX:.0f}), lê como slide")
        if dur and dur >= 8 and not (bs[-1]["layout"] == "rosto" and bs[-1]["t1"] - bs[-1]["t0"] >= CHAMADA_ROSTO - 0.05 and bs[-1]["t1"] >= dur - 0.6):
            erros.append(f"o vídeo de {dur:.0f} s precisa terminar em `rosto` de pelo menos {CHAMADA_ROSTO:g} s (a chamada final, `g_comenta`, entra aí); "
                         "se a fala não traz a palavra e a promessa, pergunte ao aluno numa frase")
        if dur:
            prova = sum(b["t1"] - b["t0"] for b in bs if b["layout"] not in SEM_PROVA)
            if bs[-1]["layout"] == "rosto" and dur >= 8:        # a chamada final é rosto por regra: não pesa na cobertura
                dur -= bs[-1]["t1"] - bs[-1]["t0"]
            if prova < COBERTURA_MIN * dur:
                erros.append(f"cobertura: {100 * prova / dur:.0f}% do vídeo com prova na tela, o mínimo é {100 * COBERTURA_MIN:.0f}%")
    return erros


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("visual", type=Path)
    p.add_argument("--dur", type=float)
    p.add_argument("--fala", type=Path, help="fala cortada (`fala.json`), pra resolver as palavras-âncora")
    a = p.parse_args()
    doc = le(a.visual)
    if a.fala:
        import transcript as tr
        doc = ancora(doc, tr.palavras(a.fala))
    erros = valida(doc, a.dur)
    print("\n".join(erros) or f"ok: {len(doc['batidas'])} batidas")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
