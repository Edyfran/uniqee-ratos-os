"""Custo de leitura: uma chamada de ferramenta entra, a decisão sai.

`avalia` é a interface única. O hook pergunta "nego, e devolvo o quê?"; o placar
pergunta a mesma coisa com `barato=False`, sem rodar nada pesado. As regras moram
só aqui:

- código com mais de LINHAS linhas, sem offset/limit      -> mapa
- regra (CLAUDE.md, SKILL.md...) acima de DOC tokens      -> mapa (menos o SKILL.md das skills fabrica-* do kit: passa inteiro)
- doc .md/.txt acima de DOC tokens                        -> mapa (+ frase local por título, se FRASES_LOCAIS)
- transcript (words.json, transcripts/*.json, .srt)       -> frases com tempo
- 3ª imagem da mesma pasta na sessão                      -> olhar (resumo + folha); depois
  passam DEPOIS quadros e o próximo volta pro resumo, até a pasta ganhar quadro novo

    python tools/economia/leitura.py frases transcripts/voz.json 30 90
    python tools/economia/leitura.py resumo docs/oferta/CORE.md
"""
import hashlib, json, os, re, subprocess, sys, tempfile, time
from dataclasses import dataclass
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "video-use" / "helpers"))
from mapa import mapa, md  # noqa: E402
import transcript as tr  # noqa: E402

TMP = Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")  # Mac e Linux: o /tmp de sempre; o Windows não tem
POR_TOKEN = 3.5
LINHAS = 800
DOC = 3000
TRANSCRIPT = 1000
TETO_FRASES = 3000  # tokens devolvidos de transcript; acima disso, pede a janela
LIVRES = 2
DEPOIS = 4  # quadros soltos depois do resumo, pra ver de perto o que a tabela apontou
POR_IMAGEM = 970  # média medida nas sessões (12/10/2026)
TRECHO = 6000  # caracteres por chamada do modelo local (janela de ~4k tokens)
POR_TRECHO = 15  # segundos por chamada do modelo local
ORCAMENTO = 60  # segundos por arquivo; o hook tem 120
# Desligado em 12/10/2026: no PACOTE.md, 2 de 9 frases do modelo do Mac enganavam e o título já dizia mais.
# Religar quando testar um modelo maior (MLX) ou o modelo da Apple mudar.
FRASES_LOCAIS = False
CACHE = Path.home() / "Library" / "Caches" / "economia"

CODIGO = {".py", ".ts", ".tsx", ".js", ".html", ".swift", ".sh"}
TEXTO = {".md", ".txt"}
IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
REGRAS = re.compile(r"(^|/)(CLAUDE|CONTEXT|SKILL|MEMORY|AGENTS|RTK)\.md$|docs/direcao\.md$")
# O SKILL.md das skills do próprio kit é a instrução de trabalho do agente do aluno: ele lê inteiro. Um mapa no lugar
# dela faz o agente seguir só os títulos. Vale pra qualquer skill fabrica-*, na pasta do Claude e na do Codex.
SKILL_DO_KIT = re.compile(r"(^|/)\.(claude|agents)/skills/fabrica-[^/]+/SKILL\.md$")
E_TRANSCRIPT = re.compile(r"(words[^/]*\.json|/transcripts?/[^/]+\.json|\.srt)$")
LIVRE = re.compile(re.escape((TMP / "olhar").as_posix()) + "/|/crivo/")


@dataclass
class Decisao:
    tipo: str
    alvo: str
    bruto: int  # tokens que a leitura crua custaria
    motivo: str = ""  # a versão barata; vazio quando barato=False

    @property
    def devolvido(self):
        return int(len(self.motivo) / POR_TOKEN)


def tokens(p):
    return int(p.stat().st_size / POR_TOKEN)


def alvo(nome, entrada, cwd):
    """O arquivo que a chamada lê inteiro, ou None."""
    if nome == "Read":
        p = Path(entrada.get("file_path", "")).expanduser()
        if p.suffix.lower() in IMAGEM:
            return p
        return p if entrada.get("offset") is None and entrada.get("limit") is None else None
    if nome == "Bash":
        m = re.fullmatch(r"\s*(?:cd\s+(['\"]?)([^\s;&|'\"]+)\1\s*(?:&&|;)\s*)?"
                         r"cat\s+(['\"]?)([^\s|;&<>'\"]+)\3\s*(2>\s*/dev/null)?\s*", entrada.get("command", ""))
        if m:
            base = Path(cwd) / Path(m.group(2) or ".").expanduser()
            p = Path(m.group(4)).expanduser()
            return p if p.is_absolute() else base / p
    return None


def avalia(nome, entrada, cwd=".", estado=None, barato=True):
    p = alvo(nome, entrada or {}, cwd)
    if p is None:
        return None
    s, ext = p.as_posix(), p.suffix.lower()  # as regras casam com "/", e o caminho do Windows vem com "\"
    if ext in IMAGEM:
        return _imagem(p, {} if estado is None else estado, barato)
    if not p.is_file():
        return None
    if E_TRANSCRIPT.search(s) and tokens(p) > TRANSCRIPT:
        return Decisao("transcript", s, tokens(p), _frases_motivo(p) if barato else "")
    if ext in TEXTO and tokens(p) > DOC and not SKILL_DO_KIT.search(s):
        regra = bool(REGRAS.search(s))
        d = Decisao("regra" if regra else "doc", s, tokens(p))
        if barato:
            frases_locais = FRASES_LOCAIS and not regra
            corpo = mapa(p, _frases_por_titulo(p)) if frases_locais else mapa(p)
            d.motivo = (f"{p.name} tem ~{d.bruto:,} tokens. "
                        + ("É regra: leia o trecho que precisa, não um resumo. " if regra else
                           "Frases feitas no modelo local (podem errar; confira no trecho). " if frases_locais else
                           "Mapa por título abaixo. ")
                        + f"Leia com offset/limit; inteiro mesmo = Read com limit.\n\n{corpo}")
        return d
    if ext in CODIGO:
        with p.open("rb") as f:
            n = sum(1 for _ in f)
        if n > LINHAS:
            d = Decisao("codigo", s, tokens(p))
            if barato:
                d.motivo = (f"{p.name} tem {n} linhas. Mapa abaixo; leia só o trecho (Read com offset/limit, "
                            f"ou sed -n a,bp). Precisa do arquivo inteiro mesmo? Read com limit={n}.\n\n{mapa(p)}")
            return d
    return None


# ---- imagens -------------------------------------------------------------------------

def _imagem(p, estado, barato):
    """Estado por pasta: int = imagens lidas antes do resumo; dict = já resumida
    ({"m": quadro mais novo na hora do resumo, "d": lidas depois, "s": pasta do resumo})."""
    if LIVRE.search(p.as_posix()) or re.match(r"(folha|sheet)", p.name, re.I):
        return None
    pasta, v = str(p.parent), estado.get(str(p.parent), 0)
    imgs = [q for q in p.parent.iterdir() if q.suffix.lower() in IMAGEM] if p.parent.is_dir() else []
    novo = max((q.stat().st_mtime for q in imgs), default=0)  # mtime da pasta não muda quando o ffmpeg -y sobrescreve
    if isinstance(v, dict) and novo <= v["m"]:
        if v["d"] < DEPOIS:
            v["d"] += 1
            return None
        d = Decisao("imagens", pasta, POR_IMAGEM)
        if barato:
            d.motivo = (f"Já li {DEPOIS} quadros soltos de {pasta} depois do resumo. A pasta não mudou: use a folha "
                        f"({v['s']}/folha1.jpg) e o resumo abaixo.\n\n" + (Path(v["s"]) / "RESUMO.md").read_text(encoding="utf-8"))
        return d
    if isinstance(v, int) and v < LIVRES:
        estado[pasta] = v + 1
        return None
    # resumo novo: 3ª imagem, ou a pasta ganhou quadro depois do último resumo
    saida = TMP / "olhar" / f"{p.parent.name}-{hashlib.md5(pasta.encode()).hexdigest()[:6]}"
    estado[pasta] = {"m": novo, "d": 0, "s": str(saida)}
    d = Decisao("imagens", pasta, POR_IMAGEM * max(1, min(len(imgs) - LIVRES, 24)))
    if not barato:
        return d
    r = subprocess.run([sys.executable, AQUI / "olhar.py", pasta, "-o", saida], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=110)
    if r.returncode:
        estado[pasta] = v  # ponytail: olhar falhou (pasta esquisita); deixa ler em vez de travar o trabalho
        return None
    porque = "A pasta mudou desde o último resumo" if isinstance(v, dict) else f"3ª imagem de {pasta} nesta sessão"
    d.motivo = (f"{porque}. Rodei o olhar.py: leia a folha ({saida}/folha1.jpg) e o resumo abaixo. "
                f"Depois disso, {DEPOIS} quadros soltos desta pasta passam; o próximo volta pra cá.\n\n"
                + (saida / "RESUMO.md").read_text(encoding="utf-8"))
    return d


# ---- transcript ----------------------------------------------------------------------

def frases(p, de=None, ate=None):
    """[início-fim] texto, uma linha por frase (quebra em silêncio >= 0,5 s ou troca de voz)."""
    return tr.frases(Path(p), de, ate)


def _frases_motivo(p):
    linhas, total, cortou = [], 0, False
    for l in frases(p):
        total += len(l) / POR_TOKEN
        if total > TETO_FRASES:
            cortou = True
            break
        linhas.append(l)
    cab = f"{p.name} é transcript palavra a palavra (~{tokens(p):,} tokens). Frases com tempo abaixo."
    if cortou:
        cab += (f" Cortei em ~{TETO_FRASES} tokens; o resto por janela: "
                f"python {AQUI / 'leitura.py'} frases {p} <de> <até>")
    return cab + "\n\n" + "\n".join(linhas)


# ---- frase local por título -----------------------------------------------------------

def _trechos(p):
    """{linha do título: texto da seção até o próximo título} — sem sobrepor."""
    fonte = p.read_text(encoding="utf-8", errors="replace").split("\n")
    inicios = sorted({ini for _, ini, _, _, _ in md("\n".join(fonte))}) or [1]
    if inicios[0] != 1:
        inicios.insert(0, 1)
    fins = inicios[1:] + [len(fonte) + 1]
    return {a: "\n".join(fonte[a - 1:b - 1]) for a, b in zip(inicios, fins)}


def _frases_por_titulo(p):
    if sys.platform != "darwin" or not (AQUI / "resumo.swift").exists():
        return {}  # o modelo local é da Apple e o pacote do aluno não leva o fonte: o mapa sai só com os títulos
    trechos = {k: v[:TRECHO] for k, v in _trechos(p).items() if len(v.strip()) > 200}
    chave = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in trechos.items()}
    CACHE.mkdir(parents=True, exist_ok=True)
    fim = time.time() + ORCAMENTO
    for k in trechos:
        if (CACHE / chave[k]).exists() or time.time() > fim:
            continue  # ponytail: estourou o orçamento, o resto sai "(sem resumo)" e entra no cache na próxima
        try:
            r = subprocess.run([binario("resumo")], input=json.dumps([trechos[k]]),
                               capture_output=True, text=True, timeout=POR_TRECHO)
            f = json.loads(r.stdout)[0]
            if f:
                (CACHE / chave[k]).write_text(f)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError, IndexError):
            pass  # modelo fora ou recusou: o título fica "(sem resumo)", a negação não muda
    return {k: ((CACHE / chave[k]).read_text() if (CACHE / chave[k]).exists() else "(sem resumo)")
            for k in trechos}


def binario(nome):
    """Compila <nome>.swift uma vez; recompila se o fonte mudou."""
    fonte, bin_ = AQUI / f"{nome}.swift", AQUI / ".bin" / nome
    if not bin_.exists() or bin_.stat().st_mtime < fonte.stat().st_mtime:
        bin_.parent.mkdir(exist_ok=True)
        subprocess.run(["swiftc", "-O", str(fonte), "-o", str(bin_)], check=True, capture_output=True)
    return bin_


if __name__ == "__main__":
    cmd, arq, *janela = sys.argv[1:]
    if cmd == "frases":
        print("\n".join(frases(arq, *map(float, janela))))
    elif cmd == "resumo":
        print(mapa(arq, _frases_por_titulo(Path(arq))))
