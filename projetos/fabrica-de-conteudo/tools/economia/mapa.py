"""Mapa de um arquivo longo: o que tem e em que linha, numa página.

O agente lê o mapa e depois só o trecho (`sed -n 120,180p`), em vez do arquivo
inteiro ou de várias leituras às cegas.

    python tools/economia/mapa.py tools/video-use/helpers/fabrica.py
    python tools/economia/mapa.py docs/direcao.md
"""
import ast, re, sys
from pathlib import Path

TETO = 70  # linhas do mapa; acima disso só o nível de cima


def py(fonte):
    arvore = ast.parse(fonte)
    itens = []
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = (ast.get_docstring(no) or "").split("\n")[0][:80]
            tipo = "class" if isinstance(no, ast.ClassDef) else "def"
            itens.append((0, no.lineno, no.end_lineno, f"{tipo} {no.name}", doc))
            if isinstance(no, ast.ClassDef):
                for m in no.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        d = (ast.get_docstring(m) or "").split("\n")[0][:60]
                        itens.append((1, m.lineno, m.end_lineno, f"  .{m.name}", d))
        elif isinstance(no, ast.Assign) and no.end_lineno - no.lineno >= 5:  # tabelas grandes (ESTILOS etc.)
            nomes = ",".join(getattr(t, "id", "?") for t in no.targets)
            itens.append((0, no.lineno, no.end_lineno, f"{nomes} =", ""))
    return itens


def md(fonte):
    itens, cab = [], []
    linhas = fonte.split("\n")
    for i, l in enumerate(linhas, 1):
        m = re.match(r"(#{1,4}) (.+)", l)
        if m:
            cab.append((len(m.group(1)) - 1, i, m.group(2)[:90]))
    for k, (nivel, ini, titulo) in enumerate(cab):
        fim = next((c[1] - 1 for c in cab[k + 1:] if c[0] <= nivel), len(linhas))
        itens.append((nivel, ini, fim, "  " * nivel + titulo, ""))
    return itens


def generico(fonte):
    padrao = re.compile(r"^\s*(export |async )*(function|class|const|let|def|interface|type) +(\w+)|^\s*<(section|h[12])[^>]*>")
    return [(0, i, None, l.strip()[:90], "") for i, l in enumerate(fonte.split("\n"), 1) if padrao.match(l)]


def mapa(caminho, frases=None):
    """O mapa em texto. `frases` ({linha: frase}) põe uma frase ao lado de cada título."""
    caminho = Path(caminho).expanduser()
    fonte = caminho.read_text(encoding="utf-8", errors="replace")
    n = fonte.count("\n") + 1
    if caminho.suffix == ".py":
        itens = py(fonte)
    elif caminho.suffix in (".md", ".markdown"):
        itens = md(fonte)
    else:
        itens = generico(fonte)
    if len(itens) > TETO:
        itens = [x for x in itens if x[0] == 0]
    corte = len(itens) > TETO
    linhas = [f"# {caminho.name} — {n} linhas, ~{int(len(fonte) / 3.5):,} tokens se lido inteiro"]
    doc = ast.get_docstring(ast.parse(fonte)) if caminho.suffix == ".py" else None
    if doc:
        linhas.append(doc.split("\n\n")[0][:300])
    linhas.append("")
    for _, ini, fim, nome, d in itens[:TETO]:
        faixa = f"{ini}-{fim}" if fim else f"{ini}"
        d = (frases or {}).get(ini, d)
        linhas.append(f"{faixa:>11}  {nome}" + (f" — {d}" if d else ""))
    if corte:
        linhas.append(f"... +{len(itens) - TETO} itens. grep -n no nome pra achar o resto.")
    return "\n".join(linhas)


if __name__ == "__main__":
    print(mapa(sys.argv[1]))
