#!/usr/bin/env python3
"""Os checks da fábrica: cada nota do dono vira teste, e a máquina confere o que dá.

    python checks.py plano.json              # antes: o que dá pra checar sem renderizar
    python checks.py final.mp4 [--plano p.json]   # depois: o que dá pra medir no arquivo

A lista humana é `docs/checks-do-dono.md` (nota dele, data, o que mede, onde roda).
Aqui mora o que roda. O `fabrica.py` chama `antes` no `--seco` e no render, e `depois`
no final entregue. Um check que falha diz a nota do dono e o que mediu.

Quem já confere em outro lugar fica lá e aparece aqui só como ponteiro (`manual`):
zona segura (folha a 4 qps), quebra de linha (`check_lines.py` do ccnp-aula), letra
no celular (olho, na folha). Todo ffmpeg passa pelo `ff.run`.
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import ff

PARADO_MAX = 1.5      # s sem mudar o quadro (criativo-sem-preguica)
CHAPADO_MIN = 0.5     # s de quadro preto ou de uma cor só
FLASH_SALTO = 60      # brilho médio (0-255) que sobe e volta em <= 4 quadros
PICO_MAX = -1.0       # dBTP
LEITURA_PISO = 1.0    # s somados a palavras/3
CONTRASTE_MIN = 4.5
# molde-igual no arquivo: velocidade constante, pela diferença entre quadros vizinhos (luma em 120 px).
# Calibrado nos 23 finais aprovados (videos/reels/*_reel_FINAL.mp4): 0 a 1,3 trechos por minuto, então o
# teto é 3. A parada seca NÃO entra aqui: no arquivo ela não se separa de saída nem de corte (os mesmos
# finais dão 5 a 118 por minuto); quem pega é o qa.js, na timeline. A conta no
# pesquisa/animacao-principios/ESTUDO.md, "Checks".
MOV_PISO = 1.0        # diferença média (0-255) abaixo disto é quadro parado
MOV_RETO_MIN = 3.0    # trechos de velocidade constante por minuto

# id -> (nota do dono ou origem, quando roda). A tabela do docs/ tem o resto.
NOTAS = {
    "voz-sem-ia": ("\"a voz da eleven labs caga tudo\" (08/10): nunca \"IA\" solta no texto da voz", "antes"),
    "avatar-look-6": ("\"não usa mais esse avatar 17 pra nada. Usa apenas o 6\" (08/10)", "antes"),
    "nada-parado": ("\"algum trecho parado ou em branco por mais de 1,5 s?\" (07/10)", "depois"),
    "sem-xadrez": ("\"fundo xadrez de transparência vazando num quadro\" (07/10)", "depois"),
    "quadro-vazio": ("estudo 0xmovez: quadro preto ou de uma cor só", "depois"),
    "sem-flash": ("estudo 0xmovez: salto de brilho entre quadros vizinhos", "depois"),
    "pico-audio": ("estudo 0xmovez: true peak acima de -1 dBTP", "depois"),
    "leitura": ("estudo 0xmovez: texto na tela menos que palavras/3 + 1 s", "antes"),
    "contraste": ("estudo 0xmovez: contraste do texto abaixo de 4,5:1", "antes"),
    "zona-segura": ("\"antes de postar, revisa tudo pra corrigir safezones\" (02/10)", "manual"),
    "sem-quebra": ("\"eu já pedi isso\": quebra de linha no meio da frase (11/09)", "manual"),
    "letra-celular": ("overlay legível no celular, piso 58 px em painel e 44 px em tela cheia (18/09)", "manual"),
    "molde-igual": ("\"cara de molde montado com peça pronta\" (12/10): tudo entra igual, para seco, anda em velocidade constante", "depois"),
    # o que o aluno pediu em `movimento.py` e o que o estudo motionmaxxing-regras.md (R11, §4) manda
    "ritmo-vao": ("a densidade que o aluno escolheu: algo muda na tela dentro do limite dela (calma 6 s, media 3,5 s, intensa 2 s)", "antes"),
    "pouca-variacao": ("o primeiro vídeo tem que impressionar (dono, 29/10): troca de layout (rosto sobre o fundo trocado) no mínimo a cada 12 s na intensa e 20 s na média", "antes"),
    "peso-3": ("no máximo 25 % do vídeo em peso 3, a batida que para tudo (R11)", "antes"),
    "veto": ("o aluno tirou este efeito (ou nunca o escolheu): não volta (movimento.py)", "antes"),
    "casca-de-pagina": ("contador, rótulo de canto, chip parado, barra de progresso e título digitado são casca de página, não movimento (estudo §4)", "antes"),
    "camera-atras": ("zoom com palavra atrás da cabeça: o recorte da pessoa não acompanha a câmera e a letra cai pra frente (rodada de 23/10)", "antes"),
    "chamada-final": ("o vídeo termina com chamada (21/10, crivo do vídeo do ensaio 2026.11.06): vídeo de 8 s ou mais acaba no `g_comenta`; sem a palavra e a promessa ditas, o agente pergunta ao aluno", "antes"),
    "carimbo-sem-negacao": ("carimbo e palavra gigante não levam negação (\"SEM EDITAR\", 6/6 do crivo do ensaio 2026.11.06 leu o contrário do produto): a palavra forte da frase", "antes"),
    # o sensor de um projeto que barra (Vision, ffmpeg, swiftc) falhou: "não consegui olhar" não é "nada achado" (28/10: `depois` engolia o erro)
    "sensor-falhou": ("conferência sem sensor não é conferência: o que não se mediu barra o render do projeto que barra, em vez de passar calado (plano de qualidade, 28/10)", "depois"),
}
PONTEIROS = {
    "zona-segura": "folha a 4 qps com a zona riscada (videos/*/folha_zona.py); `v2.py qa` para peça com caixa",
    "sem-quebra": ".claude/skills/ccnp-aula/scripts/check_lines.py <deck.html>",
    "letra-celular": "olhar a folha a 400 px de largura; `v2.py qa` mede vaza/cortado/fora, não o tamanho",
}


@dataclass
class Resultado:
    id: str
    ok: bool | None      # None = não deu pra medir / é manual
    mediu: str = ""
    barra: bool = False  # falhou e barra o render (a nota é erro, não gosto)
    quando: list = field(default_factory=list)   # os segundos do vídeo onde falhou: a folha do `confere_episodio` fotografa só esses

    @property
    def nota(self) -> str:
        return NOTAS[self.id][0]


# ---- antes de renderizar -----------------------------------------------------


def _textos_da_voz(plano: dict) -> list[str]:
    """O texto que vai pra voz: `narracao` (string, lista ou {texto}), ou `voz_texto`."""
    out: list[str] = []
    for k in ("narracao", "voz_texto"):
        v = plano.get(k)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, dict):
                x = x.get("texto") or x.get("text")
            if isinstance(x, str) and x.strip() and not x.startswith("(voz"):
                out.append(x)
    return out


def voz_sem_ia(texto: str) -> Resultado:
    achou = [texto[max(0, m.start() - 15):m.end() + 15].replace("\n", " ")
             for m in re.finditer(r"\bIA\b", texto)]
    return Resultado("voz-sem-ia", not achou,
                     f"{len(achou)}x \"IA\" no texto da voz: …{achou[0]}…" if achou else "nenhum \"IA\" solto", barra=True)


def _looks(plano: dict) -> list[str]:
    ls = [plano.get("look")] + [b.get("look") for b in plano.get("blocos") or [] if isinstance(b, dict)]
    return [str(x) for x in ls if x]


def avatar_look(looks: list[str], valido: str | None) -> Resultado:
    """O look único é o `HEYGEN_LOOK` do .env.local (o id do dono não viaja no código nem no kit)."""
    erra = [x for x in looks if valido and x != valido]
    return Resultado("avatar-look-6", not erra,
                     f"look {erra[0]} no plano; o único válido é o do HEYGEN_LOOK" if erra else
                     (f"{len(looks)} look(s), todos o do HEYGEN_LOOK" if looks and valido else
                      "sem look no plano ou sem HEYGEN_LOOK para comparar"), barra=True)


def _linhas_das_pecas(plano: dict):
    """(inicio, fim, texto) de cada linha de texto das peças: `linhas` = 'a|b|t_in|t_out;...'."""
    for p in plano.get("pecas") or []:
        q = p.get("q") or {}
        for lin in str(q.get("linhas") or "").split(";"):
            partes = lin.split("|")
            if len(partes) < 3:
                continue
            try:
                ini = float(partes[2])
            except ValueError:
                continue
            texto = " ".join(x for x in partes[:2] if x.strip())
            if texto.strip():
                yield p["em"] + ini, p["ate"], texto


def tempo_de_leitura(linhas) -> Resultado:
    """Cada texto fica na tela pelo menos palavras/3 + 1 s."""
    curtos = [f"\"{t[:28]}\" {fim - ini:.1f}s < {len(t.split()) / 3 + LEITURA_PISO:.1f}s"
              for ini, fim, t in linhas if fim - ini < len(t.split()) / 3 + LEITURA_PISO]
    n = len(list(linhas))
    return Resultado("leitura", None if not n else not curtos,
                     "; ".join(curtos[:3]) if curtos else (f"{n} texto(s) com tempo de sobra" if n else "plano sem texto de peça"))


def luminancia(hexcor: str) -> float:
    h = hexcor.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def razao(fg: str, bg: str) -> float:
    a, b = sorted((luminancia(fg), luminancia(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def contraste(pares: list[dict]) -> Resultado:
    """Mede só onde o plano declara `textos: [{cor, fundo, texto}]`: sem OCR, não se lê cor em quadro."""
    ruins = [f"\"{p.get('texto', '')[:20]}\" {razao(p['cor'], p['fundo']):.1f}:1"
             for p in pares if razao(p["cor"], p["fundo"]) < CONTRASTE_MIN]
    return Resultado("contraste", None if not pares else not ruins,
                     ", ".join(ruins[:3]) if ruins else (f"{len(pares)} par(es) acima de {CONTRASTE_MIN}:1" if pares
                                                         else "plano não declara `textos` com cor/fundo"))


# peça que é casca de página (estudo motionmaxxing-regras.md §4): `lint.mjs` falha nelas sem exceção
CASCA = frozenset(
    "g_contador g_contagem k_abertura_timecode g_distintivo_versao h_capitulo g_progresso h_progresso "
    "g_cartao_capitulos e_painel_lista h_passos o_estados r_lower h_lower r_rotulo h_termo r_bancada "
    "t_flutua g_chip_segue r_pilula_segue g_sticker k_gancho_digita k_rotulo_digita".split())
CHAMADA_DESDE = 8.0     # s: de um vídeo deste tamanho em diante a chamada final é obrigatória
NEGACAO = frozenset("sem não nao nunca nada nem jamais nenhum nenhuma ninguém".split())
PESO3_MAX = 0.25        # fatia do vídeo em peso 3: o plano não carrega as batidas, o tempo é a medida que ele tem


def _cardapio() -> list[str]:
    """Os ids do `v2.py cardapio`, na ordem dele (import tardio: tools/v2 mora ao lado de tools/video-use)."""
    v2 = Path(__file__).resolve().parents[2] / "v2"
    if str(v2) not in sys.path:
        sys.path.append(str(v2))
    try:
        import v2 as biblioteca
    except ImportError:         # o kit sem tools/v2 (kit-v2): o aviso fica sem a lista de trocas
        return []
    return [i for i, _, _ in biblioteca.CARDAPIO]


def tipo_do_efeito(peca: str) -> str:
    """Em qual tipo de efeito do `movimento.py` uma peça cai: transição (família x), linhas de velocidade, ou peça."""
    return "transicao" if peca.startswith("x_") else "linhas" if "linhas" in peca else "pecas"


def ritmo(ev: list[dict], dur: float, mov: dict) -> list[Resultado]:
    """O plano contra o que o aluno pediu. `ev`: [{t0, t1, tipo, peca?, peso?}] no tempo do vídeo cortado; `mov`: o que
    `movimento.le()` devolveu. Sem densidade escolhida o vão não se mede (ok None): quem pergunta é o agente."""
    import movimento
    rs, lim = [], movimento.DENSIDADES.get(mov.get("densidade"))
    if lim and dur:
        # o vão é de começo a começo de mudança na imagem (som não muda o quadro); 0 e o fim do vídeo fecham as pontas
        marcas = sorted({0.0, dur, *(e["t0"] for e in ev if e["tipo"] != "sons" and 0 <= e["t0"] <= dur)})
        v, a = max((b - a, a) for a, b in zip(marcas, marcas[1:]))
        rs.append(Resultado("ritmo-vao", v <= lim + 0.005,
                            f"maior vão {v:.1f} s a partir de {a:.1f} s; {mov['densidade']} aceita {lim:g} s"))
    else:
        rs.append(Resultado("ritmo-vao", None, "o aluno ainda não escolheu a densidade (movimento.py ler)"))
    fatia = sum(min(e["t1"], dur) - max(e["t0"], 0) for e in ev if e.get("peso") == 3) / dur if dur else 0
    rs.append(Resultado("peso-3", fatia <= PESO3_MAX + 1e-9, f"{fatia:.0%} do vídeo em peso 3, teto {PESO3_MAX:.0%}"))
    vetados = set(mov.get("vetos") or [])
    quer = set(mov.get("efeitos") or [])
    if "palavra_atras" in quer:
        quer.add("layout")      # a troca de layout é o fundo trocado atrás da palavra: quem aceitou uma aceitou a outra
    fora = [e.get("peca") or e["tipo"] for e in ev
            if e["tipo"] in vetados or e.get("peca") in vetados or (quer and e["tipo"] not in quer)]
    rs.append(Resultado("veto", not fora, f"{', '.join(dict.fromkeys(fora))} no plano" if fora else
                        f"{len(ev)} efeito(s), nenhum vetado"))
    cada = movimento.LAYOUT_CADA.get(mov.get("densidade"))
    trocas = sum(1 for e in ev if e["tipo"] == "layout")
    pode = "palavra_atras" not in vetados and "layout" not in vetados and (not quer or "layout" in quer)
    if cada and dur >= 4 and pode:
        falta = max(1, math.ceil(dur / cada)) - trocas
        rs.append(Resultado("pouca-variacao", falta <= 0, f"{trocas} troca(s) de layout em {dur:.0f} s; "
                            f"{mov['densidade']} pede ao menos uma a cada {cada:g} s" + (f" (faltam {falta})" if falta > 0 else "")))
    else:
        rs.append(Resultado("pouca-variacao", None, "sem exigência de troca de layout (calma, vídeo curto, ou o aluno tirou o fundo trocado)"))
    if dur >= CHAMADA_DESDE:
        ok = any(str(e.get("peca")).startswith("g_comenta") and e["t1"] >= dur - 4.0 for e in ev)
        rs.append(Resultado("chamada-final", ok, "chamada nos últimos segundos" if ok else
                            f"vídeo de {dur:.0f} s termina sem chamada: ponha o g_comenta no fim; se a fala não traz a palavra e a promessa, "
                            "pergunte ao aluno numa frase (que palavra comentar, e o que a pessoa recebe)"))
    casca = [e["peca"] for e in ev if e.get("peca") in CASCA or str(e.get("peca")).startswith("k_contador_")]
    usadas = {e.get("peca") for e in ev}
    troca = [i for i in _cardapio() if i not in usadas][:5]
    rs.append(Resultado("casca-de-pagina", not casca, ", ".join(dict.fromkeys(casca)) + (
        f" é casca de página; no lugar, do cardápio: {', '.join(troca)} (v2.py cardapio)" if troca else "") if casca
        else "nenhuma peça de casca"))
    atras = [e for e in ev if e["tipo"] == "palavra_atras"]
    mexe = [e for e in ev if e["tipo"] == "zoom" and e.get("zoom") not in (None, [1.0, 1.0])
            and any(e["t0"] < a["t1"] and e["t1"] > a["t0"] for a in atras)]
    rs.append(Resultado("camera-atras", not mexe, ", ".join(f"{e['t0']:.1f}–{e['t1']:.1f} s" for e in mexe)
                        or "a câmera fica parada onde há palavra atrás da cabeça"))
    return rs


def sobre(r: dict, ls: list[dict], livres=frozenset()) -> list[dict]:
    """As peças de `ls` que ficam na tela junto com `r` por 0,8 s ou mais. A legenda corre por baixo de toda peça e `leve`
    (câmera, som) não é peça: só peça com peça é defeito (o dono reprovou carta por cima de lista e tarja por cima de
    tarja, 19/10 e 20/10). `livres`: pares de nomes de peça que o dono desenhou pra viverem juntos."""
    return [o for o in ls if o is not r and not (o.get("legenda") or r.get("legenda") or o.get("leve") or r.get("leve"))
            and frozenset((o.get("peca"), r.get("peca"))) not in livres
            and min(o["t1"], r["t1"]) - max(o["t0"], r["t0"]) >= 0.8]


def _adaptador(plano: dict):
    """O módulo de notas do projeto (`notas_<projeto>.py`), se existe: o kit do aluno não leva o do Tinteiro, e sem ele
    o projeto roda só as notas de cima. Cada nota nova entra em `NOTAS` pra `Resultado.nota` achar a citação.
    O módulo dá `antes(plano)` e, se quiser olhar o vídeo pronto, `depois(video, plano)`."""
    import importlib
    projeto = str(plano.get("projeto") or "")
    if not re.fullmatch(r"\w+", projeto):
        return None
    try:
        m = importlib.import_module(f"notas_{projeto}")
    except ModuleNotFoundError as e:
        if e.name != f"notas_{projeto}":
            raise
        return None
    NOTAS.update(m.NOTAS)
    return m


def carimbo_sem_negacao(plano: dict) -> Resultado:
    """O carimbo e a palavra gigante são o texto mais lido do vídeo e não têm contexto: com "sem", "não" ou "nunca" o leitor
    entende o contrário do produto. Fica a palavra forte da frase (a que o `propoe.py` escolhe)."""
    ruins = [f"{p['peca']} “{t}”" for p in plano.get("pecas") or [] if p.get("peca") in ("e_carimbo", "k_palavra_gigante")
             for t in [str((p.get("q") or {}).get("txt") or (p.get("q") or {}).get("l") or "")]
             if NEGACAO & set(re.findall(r"\w+", t.lower()))]
    return Resultado("carimbo-sem-negacao", not ruins, ", ".join(ruins) + ": negação inverte o sentido; use a palavra forte da frase" if ruins
                     else "nenhum carimbo ou palavra gigante com negação")


def antes(plano: dict) -> list[Resultado]:
    rs = [voz_sem_ia(t) for t in _textos_da_voz(plano)]
    rs = [r for r in rs if not r.ok] or rs[:1]
    rs.append(carimbo_sem_negacao(plano))
    import pre_voo
    rs.append(avatar_look(_looks(plano), pre_voo.look_padrao()))
    rs.append(tempo_de_leitura(list(_linhas_das_pecas(plano))))
    rs.append(contraste(plano.get("textos") or []))
    m = _adaptador(plano)
    return rs + (m.antes(plano) if m else [])


# ---- depois de renderizar ----------------------------------------------------


def _stats(video: Path) -> list[tuple[float, float, float, float]]:
    """(t, YMIN, YAVG, YMAX) por quadro, num quadro pequeno (a conta é de brilho, não de pixel)."""
    r = ff.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                "scale=96:-2,signalstats,metadata=print:file=-", "-f", "null", "-"],
               capture=True, quiet=True)
    out, t, cur = [], 0.0, {}
    for lin in (r.stdout or "").splitlines():
        if lin.startswith("frame:"):
            if cur:
                out.append((t, cur["YMIN"], cur["YAVG"], cur["YMAX"]))
            m = re.search(r"pts_time:([\d.]+)", lin)
            t, cur = float(m.group(1)) if m else t, {}
        else:
            m = re.match(r"lavfi\.signalstats\.(YMIN|YAVG|YMAX)=([\d.]+)", lin)
            if m:
                cur[m.group(1)] = float(m.group(2))
    if cur:
        out.append((t, cur["YMIN"], cur["YAVG"], cur["YMAX"]))
    return out


def _corridas(marcas: list[bool], ts: list[float]):
    ini = None
    for i, m in enumerate(marcas + [False]):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            yield ts[ini], ts[min(i, len(ts) - 1)] + (ts[1] - ts[0] if len(ts) > 1 else 0), ini
            ini = None


def quadro_vazio(st) -> Resultado:
    ts = [s[0] for s in st]
    corridas = [(a, b, i) for a, b, i in _corridas([s[3] - s[1] <= 10 for s in st], ts) if b - a >= CHAPADO_MIN]
    achados = [f"{a:.1f}-{b:.1f}s {'preto' if st[i][2] < 24 else 'uma cor só'}" for a, b, i in corridas]
    return Resultado("quadro-vazio", not achados, "; ".join(achados[:4]) or "nenhum quadro preto ou chapado", quando=[a for a, _, _ in corridas[:8]])


def sem_flash(st) -> Resultado:
    ys, ts = [s[2] for s in st], [s[0] for s in st]
    achados, quando = [], []
    for i in range(1, len(ys) - 1):
        if abs(ys[i] - ys[i - 1]) >= FLASH_SALTO and any(
                abs(ys[i + k] - ys[i - 1]) <= 25 for k in range(1, 5) if i + k < len(ys)):
            achados.append(f"{ts[i]:.2f}s salto de {abs(ys[i] - ys[i - 1]):.0f}/255")
            quando.append(ts[i])
    return Resultado("sem-flash", not achados, "; ".join(achados[:4]) or "nenhum salto que volta em 4 quadros", quando=quando[:8])


def parado(video: Path, liberados: list | None = None) -> Resultado:
    """O `freezedetect` do ffmpeg; `liberados` ([[ini, fim]], do plano) é parada de propósito."""
    r = ff.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                f"scale=192:-2,freezedetect=n=-55dB:d={PARADO_MAX}", "-f", "null", "-"],
               capture=True, quiet=True)
    err = r.stderr or ""
    ini = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", err)]
    fim = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", err)]
    achados, quando = [], []
    for i, a in enumerate(ini):
        b = fim[i] if i < len(fim) else ff.dur(video)
        if any(l[0] - 0.2 <= a and b <= l[1] + 0.2 for l in liberados or []):
            continue
        achados.append(f"{a:.1f}-{b:.1f}s ({b - a:.1f}s)")
        quando.append((a + b) / 2)
    return Resultado("nada-parado", not achados, "; ".join(achados[:4]) or f"nada parado acima de {PARADO_MAX}s", quando=quando[:8])


def sem_xadrez(video: Path, dur: float) -> Resultado:
    """Procura o xadrez de transparência: blocos de 32 px com dois tons que se invertem a cada quadradinho."""
    try:
        import numpy as np
    except ImportError:     # o kit do aluno pode não ter numpy: pula, não derruba o render
        return Resultado("sem-xadrez", None, "sem numpy")
    L, A = 540, 960
    r = ff.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                f"fps=1,scale={L}:{A}:force_original_aspect_ratio=decrease,pad={L}:{A},format=gray",
                "-frames:v", "120", "-f", "rawvideo", "-"], capture=True, quiet=True, binario=True)
    quadros = np.frombuffer(r.stdout, np.uint8)
    quadros = quadros[:len(quadros) // (L * A) * L * A].reshape(-1, A, L)
    achados = []
    for n, q in enumerate(quadros):
        blocos = 0
        for y in range(0, A - 32, 32):
            for x in range(0, L - 32, 32):
                b = q[y:y + 32, x:x + 32].astype(int)
                if b.max() - b.min() < 8 or b.max() - b.min() > 90:
                    continue
                m = b > (b.max() + b.min()) / 2
                for s in range(2, 13):
                    if (m[:, s:] != m[:, :-s]).mean() > .85 and (m[s:] != m[:-s]).mean() > .85 \
                            and (m[s:, s:] == m[:-s, :-s]).mean() > .85:
                        blocos += 1
                        break
        if blocos >= 6:
            achados.append(f"{n}s ({blocos} blocos)")
    return Resultado("sem-xadrez", not achados, "xadrez de transparência em " + ", ".join(achados[:4])
                     if achados else "nenhum xadrez")


def pico(video: Path) -> Resultado:
    if not ff.probe(video).tem_audio:
        return Resultado("pico-audio", None, "sem áudio")
    m = ff.loudness(video)
    tp = float(m["input_tp"]) if m else float("nan")
    return Resultado("pico-audio", tp <= PICO_MAX if tp == tp else None, f"true peak {tp:.1f} dBTP (teto {PICO_MAX})")


def _energia(video: Path) -> tuple[list[float], float]:
    """A diferença média de luma entre quadros vizinhos, num quadro de 120 px de largura."""
    import numpy as np
    sonda = ff.probe(video)
    L = 120
    A = max(2, round(sonda.altura * L / sonda.largura / 2) * 2)
    r = ff.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                f"scale={L}:{A},format=gray", "-f", "rawvideo", "-"], capture=True, quiet=True, binario=True)
    q = np.frombuffer(r.stdout, np.uint8)
    q = q[:len(q) // (L * A) * L * A].reshape(-1, A, L).astype(np.int16)
    # fps = quadros lidos / duração: o r_frame_rate de uma prévia reencodada pode vir 240 e inflar a taxa por minuto 8x
    return np.abs(np.diff(q, axis=0)).mean(axis=(1, 2)).tolist(), len(q) / max(ff.dur(video), 1e-3)


def em_reta(e: list[float]) -> int:
    """Trechos de 8 quadros com variação abaixo de 6 % (desvio/média), num movimento de até 26 quadros:
    velocidade constante, o ease linear visto de fora. Movimento mais longo é filmagem ou deriva, que
    pode ser linear (motionmaxxing: deriva de 26 quadros ou mais)."""
    retos = i = 0
    n = len(e)
    while i < n:
        if e[i] < MOV_PISO:
            i += 1
            continue
        j = i
        while j + 1 < n and e[j + 1] >= MOV_PISO:
            j += 1
        trecho, k = e[i:j + 1], 0
        while len(trecho) <= 26 and k + 8 <= len(trecho):
            jan = trecho[k:k + 8]
            m = sum(jan) / 8
            if (sum((x - m) ** 2 for x in jan) / 8) ** .5 / m < .06:
                retos += 1
                k += 8
            else:
                k += 1
        i = j + 1
    return retos


def molde(video: Path) -> Resultado:
    try:
        import numpy  # noqa: F401
    except ImportError:     # o kit do aluno pode não ter numpy
        return Resultado("molde-igual", None, "sem numpy")
    e, fps = _energia(video)
    retos = em_reta(e)
    por_min = retos / max(len(e) / fps / 60, 1 / 60)
    return Resultado("molde-igual", por_min <= MOV_RETO_MIN,
                     f"{retos} movimento(s) em velocidade constante ({por_min:.1f}/min, teto {MOV_RETO_MIN})")


def depois_do_video(video: Path | str, plano: dict | None = None) -> list[Resultado]:
    """Os checks que valem pra todo vídeo pronto, sem o adaptador do projeto."""
    video = Path(video)
    st = _stats(video)
    return [quadro_vazio(st), sem_flash(st), parado(video, (plano or {}).get("parado_ok")),
            sem_xadrez(video, ff.dur(video)), pico(video), molde(video)]


def depois(video: Path | str, plano: dict | None = None) -> list[Resultado]:
    video = Path(video)
    rs = depois_do_video(video, plano)
    m = _adaptador(plano) if plano else None
    if m and hasattr(m, "depois"):
        try:
            rs += m.depois(video, plano)
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            if getattr(m, "BLOQUEIA_DEPOIS", False):
                # o projeto que barra no vídeo pronto não aceita sensor mudo: o que não se mediu é falha, com a causa escrita
                rs.append(Resultado("sensor-falhou", False, msg, barra=True))
            else:   # olhar o vídeo pronto nunca derruba a entrega dos outros projetos: sensor que falha vira "sem o que medir"
                print(f"aviso: notas de {plano.get('projeto')} sobre o vídeo não rodaram ({msg})", file=sys.stderr)
    return rs


def bloqueia_depois(plano: dict | None) -> bool:
    """O adaptador do projeto barra a entrega (`BLOQUEIA_DEPOIS`)? Hoje só o Tinteiro; os outros projetos só avisam."""
    m = _adaptador(plano) if plano else None
    return bool(m and getattr(m, "BLOQUEIA_DEPOIS", False))


def entrega(video: Path | str, plano: dict) -> list[Resultado]:
    """O que a fábrica chama com o final pronto: roda os checks, mostra e, no projeto que barra, grava o relatório do adaptador (`relatorio`) e levanta
    `ValueError` se alguma nota com `barra` falhou (o final fica no disco pra quem for ver o porquê, mas o render falha). Os outros projetos só mostram."""
    rs = depois(video, plano)
    mostra(rs)
    if bloqueia_depois(plano):
        m = _adaptador(plano)
        if hasattr(m, "relatorio"):
            m.relatorio(Path(video), plano, rs)
        barram = [r for r in rs if r.ok is False and r.barra]
        if barram:
            raise ValueError("; ".join(f"{r.id}: {r.mediu}" for r in barram[:3]) + (f" (+{len(barram) - 3} nota(s) que barram)" if len(barram) > 3 else "")
                             + f". O final ficou em {video}, reprovado.")
    return rs


# ---- saída ------------------------------------------------------------------


def mostra(rs: list[Resultado]) -> int:
    """Imprime só o que falhou (nota do dono + o que mediu). Devolve quantos falharam."""
    falhou = [r for r in rs if r.ok is False]
    for r in falhou:
        print(f"CHECK {r.id}: {r.nota}\n       mediu: {r.mediu}")
    sem = [r.id for r in rs if r.ok is None]
    print(f"checks: {sum(r.ok is True for r in rs)} ok, {len(falhou)} falharam"
          + (f", {len(sem)} sem o que medir ({', '.join(sem)})" if sem else ""))
    return len(falhou)


def main() -> int:
    ap = __import__("argparse").ArgumentParser(description=__doc__,
                                               formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("alvo", type=Path, help="plano.json (antes) ou vídeo (depois)")
    ap.add_argument("--plano", type=Path)
    a = ap.parse_args()
    plano = json.loads((a.plano or a.alvo).read_text(encoding="utf-8")) if (a.plano or a.alvo.suffix == ".json") else {}
    rs = antes(plano) if a.alvo.suffix == ".json" else antes(plano) + depois(a.alvo, plano)
    return 1 if mostra(rs) else 0


if __name__ == "__main__":
    sys.exit(main())
