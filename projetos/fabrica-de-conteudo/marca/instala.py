#!/usr/bin/env python3
"""Instala e confere a marca na fábrica. Roda da raiz da fábrica, depois que a pasta marca/ está lá:

    uv run python marca/instala.py             # junta os ids no .env.local e confere tudo, sem rede
    uv run python marca/instala.py --chave     # e confere a chave da ElevenLabs com a voz (não gasta crédito)
    uv run python marca/instala.py --amostra   # e desenha marca/_confere/amostra.jpg com a cor e a letra
    uv run python marca/instala.py --sem-voz --amostra   # só a cara: a marca feita antes da aula da voz

Nunca imprime o valor de uma chave. Sai com código 1 e a lista do que corrigir, na ordem.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MARCA = Path(__file__).resolve().parent
RAIZ = MARCA.parent
ENV = RAIZ / ".env.local"
HELPERS = RAIZ / "tools" / "video-use" / "helpers"
CONFERE = MARCA / "_confere"


def le_env(arq: Path) -> dict[str, str]:
    vals = {}
    if arq.is_file():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            k, sep, v = linha.partition("=")
            if sep and not k.lstrip().startswith("#"):
                vals[k.strip()] = v.strip().strip("'\"")
    return vals


def junta_ids() -> list[str]:
    """As linhas do ids.env entram no .env.local: a do mesmo nome (comentada ou não) é trocada, a que
    falta vai pro fim, e nenhuma outra linha muda. Id vazio ou ainda TROQUE no pacote não apaga o que já
    estava lá: a marca feita pelo aluno a partir do molde não pode trocar a voz dele por TROQUE."""
    ids = {k: v for k, v in le_env(MARCA / "ids.env").items() if v and "TROQUE" not in v}
    linhas = ENV.read_text(encoding="utf-8").splitlines() if ENV.is_file() else []
    feitos = set()
    for i, linha in enumerate(linhas):
        k = linha.partition("=")[0].strip().lstrip("#").strip()
        if k in ids and k not in feitos and "=" in linha:
            linhas[i] = f"{k}={ids[k]}"
            feitos.add(k)
    linhas += [f"{k}={v}" for k, v in ids.items() if k not in feitos]
    ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return sorted(ids)


def confere(voz: bool = True) -> list[str]:
    erros: list[str] = []
    if not (RAIZ / ".fabrica-ok").is_file():
        return ["fábrica: não existe .fabrica-ok na raiz. Rode antes a \"Primeira vez nesta máquina\" "
                "(AGENTS.md) e volte a este pedido"]
    sys.path.insert(0, str(HELPERS))
    try:
        import estilo as es
    except ValueError as e:                     # o estilos.json da marca, com o arquivo no começo
        return [f"estilos.json: {e}"]
    except ImportError:
        return [f"fábrica: não achei {HELPERS / 'estilo.py'}. A pasta marca/ tem que ficar na raiz da fábrica"]
    if not hasattr(es, "da_marca"):
        return ["kit: este kit é anterior ao pacote de marca. Baixe o kit novo na área de membros e "
                "descompacte por cima desta pasta (a marca/ e o .env.local ficam)"]

    nomes = list(es.da_marca(MARCA))
    if not nomes:
        erros.append("estilos.json: nenhum estilo")
    for nome in nomes:
        e = es.estilo(nome)
        fonte = (e.eixos["desenho"]["fonte"] or "").partition("#")[0]
        usados = {"imagem.fundo": e.eixos["imagem"]["fundo"], "trilha.faixa": e.eixos["trilha"]["faixa"],
                  "desenho.fonte": fonte if Path(fonte).suffix else None}   # sem extensão é nome do kit
        for campo, rel in usados.items():
            if rel and not (RAIZ / rel).is_file():
                erros.append(f"estilos.json: o {campo} de '{nome}' aponta {rel}, que não existe")
        if e.eixos["desenho"]["tema"] == "marca" and not (MARCA / "tema.css").is_file():
            erros.append(f"tema.css: o estilo '{nome}' pede o tema marca, e não existe marca/tema.css")

    css = MARCA / "tema.css"
    if css.is_file():
        for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", css.read_text(encoding="utf-8")):
            if not url.startswith(("http:", "https:", "data:")) and not (MARCA / url).is_file():
                erros.append(f"tema.css: a letra aponta {url}, e não existe marca/{url}")

    for arq in sorted(MARCA.rglob("*")):
        if arq.suffix in (".css", ".json", ".md", ".env") and "_confere" not in arq.parts \
                and arq.name != "INSTALAR-MARCA.md" and "TROQUE" in arq.read_text(encoding="utf-8"):
            erros.append(f"{arq.relative_to(MARCA)}: sobrou TROQUE, o pacote não foi preenchido")

    env = le_env(ENV) if voz else {"VOZ_ID": "-", "ELEVENLABS_API_KEY": "-"}
    if not env.get("VOZ_ID"):
        erros.append("ids: falta VOZ_ID no .env.local (vem no marca/ids.env)")
    if not env.get("ELEVENLABS_API_KEY"):
        erros.append("chave: falta ELEVENLABS_API_KEY no .env.local. Abra o arquivo num editor, cole a chave "
                     "nova na linha ELEVENLABS_API_KEY= e salve")
    if not erros:
        erros += seco(es, nomes)
    return erros


def seco(es, nomes: list[str]) -> list[str]:
    """O --seco do exemplo do reel editorial, no estilo -reel da marca: a cadeia tem que parar só no
    passo que cobra. Não gasta nada."""
    def editorial(nome: str | None) -> bool:
        return nome == "reel-editorial" or bool(nome in es.ESTILOS and editorial(es.ESTILOS[nome].get("herda")))
    reel = next((n for n in nomes if editorial(n)), None)
    exemplo = RAIZ / "exemplos" / "reel-editorial" / "reel.json"
    if not reel or not exemplo.is_file():
        return []
    plano = json.loads(exemplo.read_text(encoding="utf-8"))
    plano.update(estilo=reel, slug=f"{reel}-confere")
    if es.estilo(reel).eixos["imagem"]["fundo"]:
        plano.pop("imagem", None)               # a placa é a da marca, que o estilo já traz
    CONFERE.mkdir(exist_ok=True)
    (CONFERE / "reel.json").write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, str(HELPERS / "fabrica.py"), str(CONFERE / "reel.json"), "--seco"],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return [f"seco: o --seco do reel no estilo {reel} falhou:\n{(r.stdout + r.stderr).strip()[-1500:]}"]
    return []


def chave() -> list[str]:
    """GET da voz com a chave: confere a chave, a permissão de Voices e o VOZ_ID de uma vez, sem crédito."""
    env = le_env(ENV)
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/voices/{env['VOZ_ID']}",
                                 headers={"xi-api-key": env["ELEVENLABS_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            nome = json.load(r).get("name", "?")
        print(f"ok  a chave abre a voz \"{nome}\"")
        return []
    except urllib.error.HTTPError as e:
        motivo = {401: "a chave não vale, ou não tem a permissão Voices (crie de novo, com Text to Speech e Voices)",
                  404: "o VOZ_ID não existe nesta conta: a chave é de outra conta, ou o id está errado"}
        return [f"chave: a ElevenLabs respondeu {e.code}: {motivo.get(e.code, e.reason)}"]
    except urllib.error.URLError as e:
        return [f"chave: sem conexão com a ElevenLabs ({e.reason})"]


def amostra() -> Path:
    """Uma peça parada no tema da marca: o chão, o bloco, o marcador e a letra dela."""
    sys.path.insert(0, str(HELPERS))
    from capa import parada
    CONFERE.mkdir(exist_ok=True)
    out = CONFERE / "amostra.jpg"
    return parada("e_fundo", ["forma=circulo", "cor=ac", "x=540", "y=1150", "tam=900", "kick=A sua marca",
                              "hd=Na sua <b>fábrica</b>.", "placa=topo", "dur=4"], out, tema="marca",
                  t=2.5)   # depois do marcador: antes dele, a palavra grifada some no chão escuro


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chave", action="store_true", help="confere a chave da ElevenLabs com a voz (sem crédito)")
    ap.add_argument("--amostra", action="store_true", help="desenha marca/_confere/amostra.jpg")
    ap.add_argument("--sem-voz", action="store_true", help="não confere VOZ_ID nem a chave: só a cara da marca")
    a = ap.parse_args()
    juntos = junta_ids()
    print(f"ok  ids no .env.local: {', '.join(juntos) or '(nenhum)'}")
    erros = confere(voz=not a.sem_voz)
    if not erros and a.chave:
        erros = chave()
    if not erros and a.amostra:
        print(f"ok  amostra em {amostra().relative_to(RAIZ)}")
    if erros:
        print("\nA marca não instalou. Corrija, na ordem:")
        for e in erros:
            print(f"  - {e}")
        return 1
    print("ok  a marca está instalada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
