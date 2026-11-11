"""Atualiza a Fábrica de Conteúdo com o ZIP novo, sem tocar no que é do aluno.

    uv run python tools/video-use/helpers/atualiza.py [ZIP ...] [--seco]
    uv run python tools/video-use/helpers/atualiza.py --aviso   # o que o agente roda no começo da conversa

Rode da raiz da Fábrica. Sem ZIP no comando, procura em ~/Downloads e ao lado da pasta o
`fabrica-de-conteudo-com-ia*.zip` (com o "(1)" que o navegador põe) e o ZIP de cada módulo
instalado, e fica com o de VERSAO mais nova de cada um: a data do arquivo não conta.

O que acontece:
  - ZIP com VERSAO igual ou mais velha que a da pasta: não mexe em nada.
  - arquivo do ZIP que mudou: o antigo vai para `.fabrica/copia/<versão antiga>/<caminho>` e entra o novo.
  - arquivo novo no ZIP: entra.
  - arquivo que saiu do kit: vai para a mesma cópia. Nunca se apaga nada.
  - o que não está no ZIP não é tocado. O que é do aluno (`DO_ALUNO`) nunca é escrito nem movido,
    mesmo que um ZIP traga arquivo com esse caminho.
  - ZIP com caminho que foge da pasta (absoluto, `..`, letra de unidade) é recusado inteiro,
    antes de escrever qualquer coisa.

`.fabrica/arquivos.txt` guarda o que o ZIP trouxe (um por módulo: `arquivos-<módulo>.txt`), com a
versão na primeira linha: é por ele que a próxima atualização sabe o que saiu do kit.
Só stdlib: roda igual no Mac, no Windows e no Linux.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]      # raiz/tools/video-use/helpers/atualiza.py
PASTA_NO_ZIP = "fabrica-de-conteudo"            # a pasta raiz do ZIP da Fábrica; o do módulo não tem
ZIP_DA_FABRICA = "fabrica-de-conteudo-com-ia"
ESTADO = ".fabrica"                             # copia/<versão>/ e as listas arquivos*.txt

# O que é do aluno, pelo primeiro nome do caminho: a chave, a marca, as escolhas do /onboarding, os
# vídeos, o marcador e o relato da conferência. A biblioteca.html sai da marca dele (`v2.py biblioteca`
# refaz), e a pasta ESTADO é esta ferramenta.
DO_ALUNO = {".env.local", ".fabrica-ok", "conferencia.txt", "marca", "onboarding", "onboarding.log",
            "videos", "biblioteca.html", ESTADO}
# A única coisa do kit que mora numa pasta do aluno.
DO_KIT_NA_PASTA_DO_ALUNO = {"videos/LEIA-ME.md"}

# Pastas que só o kit escreve: nenhum módulo, nenhum Pack e nenhuma skill manda o agente gravar ali.
# Ficam de fora tools/video-use/helpers (os módulos põem helper e teste lá) e tools/v2/pecas (a skill
# fabrica-movimento manda a peça nova do aluno para lá).
SO_DO_KIT = ("tools/v2/nucleo", "tools/onboarding", "docs/guia-de-estilos", "tools/marca/molde")

SETE_DIAS = 7

# O .claude/settings.json é do kit (o hook do porteiro de leitura) e do aluno (permissões, outros hooks): na
# atualização junta, não troca. O kit é dono só da entrada que cita PORTEIRO.
SETTINGS = ".claude/settings.json"
PORTEIRO = "tools/economia/hook.py"


def junta_settings(atual: bytes, novo: bytes) -> bytes:
    """O settings do aluno com a entrada do porteiro do ZIP: sai a entrada velha do porteiro, entra a nova, e o resto
    (permissões, outros hooks, outras chaves) fica como está. JSON que não lê, ou já em dia: devolve o do aluno."""
    try:
        meu, kit = json.loads(atual.decode("utf-8")), json.loads(novo.decode("utf-8"))
        for evento, grupos in kit["hooks"].items():
            fica = []
            for g in meu.setdefault("hooks", {}).get(evento, []):
                livres = [h for h in g["hooks"] if PORTEIRO not in h.get("command", "")]
                if livres or len(livres) == len(g["hooks"]):    # grupo que só tinha o porteiro some
                    fica.append({**g, "hooks": livres})
            meu["hooks"][evento] = fica + grupos
        junto = json.dumps(meu, indent=2, ensure_ascii=False) + "\n"
        return atual if json.loads(junto) == json.loads(atual.decode("utf-8")) else junto.encode("utf-8")
    except (ValueError, TypeError, AttributeError, KeyError):
        return atual


def versao_em_tupla(texto: str) -> tuple[int, ...]:
    """'2026.10.22.2 a0fafaf' -> (2026, 10, 22, 2); '2026.10.22' -> (2026, 10, 22, 0); sem número -> ()."""
    nums = tuple(int(n) for n in re.findall(r"\d+", (texto.split() or [""])[0]))
    return nums + (0,) * (4 - len(nums)) if nums else ()


def _tag(versao: str) -> str:
    return (versao.split() or ["sem-versao"])[0]


def aviso_de_versao(raiz: Path, hoje: date) -> str | None:
    """A frase de aviso quando a tag da Fábrica tem 7 dias ou mais. Sem VERSAO (o tronco do dono): None."""
    arq = raiz / "VERSAO"
    if not arq.is_file():
        return None
    try:
        dia = date(*versao_em_tupla(arq.read_text(encoding="utf-8"))[:3])
    except (TypeError, ValueError):
        return None
    if (hoje - dia).days < SETE_DIAS:
        return None
    return (f"Esta Fábrica é de {dia:%d/%m}. Sai versão nova toda semana: baixe o ZIP na aula da Fábrica "
            f"e diga /atualizar (no Codex: atualiza a fábrica).")


def _nome_ruim(nome: str) -> bool:
    """Caminho que foge da pasta: absoluto, com `..`, com letra de unidade ou com barra invertida."""
    return nome.startswith("/") or "\\" in nome or ":" in nome or ".." in nome.split("/")


def _do_aluno(rel: str) -> bool:
    return rel not in DO_KIT_NA_PASTA_DO_ALUNO and rel.split("/")[0].lower() in DO_ALUNO


def _produto(zp: Path) -> str:
    """'fabrica-posta (1).zip' -> 'fabrica-posta'."""
    return re.sub(r"\s*\(\d+\)$", "", zp.stem)


def _versao_do_zip(zp: Path) -> str:
    try:
        with zipfile.ZipFile(zp) as z:
            nome = next(n for n in (f"{PASTA_NO_ZIP}/VERSAO", "VERSAO") if n in z.namelist())
            return z.read(nome).decode("utf-8").strip()
    except (zipfile.BadZipFile, StopIteration, OSError, UnicodeDecodeError):
        return ""


def procura(pastas: list[Path], raiz: Path) -> list[Path]:
    """O ZIP de VERSAO mais nova da Fábrica e de cada módulo instalado (a skill dele está em .agents/skills)."""
    melhor: dict[str, tuple[tuple[int, ...], Path]] = {}
    for pasta in pastas:
        for zp in sorted(pasta.glob("fabrica-*.zip")):
            produto = _produto(zp)
            if produto != ZIP_DA_FABRICA and not (raiz / ".agents" / "skills" / produto).is_dir():
                continue
            v = versao_em_tupla(_versao_do_zip(zp))
            if v and v > melhor.get(produto, ((), zp))[0]:
                melhor[produto] = (v, zp)
    return [zp for _, zp in melhor.values()]


class Pacote:
    """Um ZIP lido e conferido. `produto` é '' na Fábrica e o nome do módulo nos outros."""

    def __init__(self, zp: Path):
        try:
            z = zipfile.ZipFile(zp)
        except zipfile.BadZipFile:
            sys.exit(f"{zp.name} não é um ZIP inteiro. Baixe de novo na aula da Fábrica.")
        with z:
            itens = [i for i in z.infolist() if not i.filename.startswith("__MACOSX/")]
            if z.testzip():
                sys.exit(f"{zp.name} veio quebrado. Baixe de novo na aula da Fábrica.")
            arquivos = [i for i in itens if not i.is_dir()]
            da_fabrica = bool(arquivos) and all(i.filename.startswith(PASTA_NO_ZIP + "/") for i in arquivos)
            corte = len(PASTA_NO_ZIP) + 1 if da_fabrica else 0
            conteudo = {i.filename[corte:]: z.read(i) for i in arquivos}
            # confere o nome já sem a pasta raiz: 'fabrica-de-conteudo//abs' vira '/abs'
            ruim = next((r for r in conteudo if _nome_ruim(r)), None)
            if ruim:
                sys.exit(f"{zp.name} recusado, não escrevi nada: o caminho '{ruim}' sai da pasta da Fábrica. "
                         f"Baixe de novo na aula da Fábrica.")
        self.nome = zp.name
        self.produto = "" if da_fabrica else _produto(zp)
        self.versao = conteudo.pop("VERSAO", b"").decode("utf-8").strip()
        if not versao_em_tupla(self.versao):
            sys.exit(f"{zp.name} não tem VERSAO legível: não é um ZIP da Fábrica. Baixe de novo na aula da Fábrica.")
        self.arquivos = conteudo


def _lista(raiz: Path, produto: str) -> Path:
    return raiz / ESTADO / (f"arquivos-{produto}.txt" if produto else "arquivos.txt")


def _le_lista(raiz: Path, produto: str) -> tuple[str, list[str]] | None:
    """(versão, caminhos) da última atualização; None se este aluno nunca atualizou por aqui."""
    arq = _lista(raiz, produto)
    if not arq.is_file():
        return None
    linhas = arq.read_text(encoding="utf-8").splitlines()
    return (linhas[0].lstrip("# ") if linhas else "",
            [c for c in linhas[1:] if c and not _nome_ruim(c) and not _do_aluno(c)])


def _versao_local(raiz: Path, produto: str) -> str:
    if not produto:
        return (raiz / "VERSAO").read_text(encoding="utf-8").strip()
    lista = _le_lista(raiz, produto)
    return lista[0] if lista else ""


def _sumiram(raiz: Path, p: Pacote, gerido: set[str]) -> list[str]:
    """Os arquivos do kit que o ZIP novo não traz mais e que ainda estão na pasta."""
    lista = _le_lista(raiz, p.produto)
    if lista:
        velhos = set(lista[1]) - gerido
    elif p.produto:
        return []       # módulo sem lista: não há como separar o que é dele
    else:
        # shortcut: sem a lista da versão anterior, só vale o que sumiu das SO_DO_KIT; troque quando
        # todo aluno tiver a lista (depois da primeira atualização por esta ferramenta)
        velhos = {a.relative_to(raiz).as_posix() for pasta in SO_DO_KIT for a in (raiz / pasta).rglob("*")
                  if a.is_file() and "__pycache__" not in a.parts and a.name != ".DS_Store"} - gerido
    return sorted(r for r in velhos if (raiz / r).is_file() and not _do_aluno(r))


def _linha(rotulo: str, caminhos: list[str]) -> str:
    resto = f" … e mais {len(caminhos) - 5}" if len(caminhos) > 5 else ""
    return f"  {rotulo}: {len(caminhos)}" + (f" ({', '.join(caminhos[:5])}{resto})" if caminhos else "")


def _aplica(raiz: Path, p: Pacote, seco: bool) -> list[str]:
    """Atualiza com um pacote (ou só mostra, no seco). Devolve os caminhos que mudaram."""
    local = _versao_local(raiz, p.produto)
    nome = p.produto or "Fábrica"
    if local and versao_em_tupla(p.versao) <= versao_em_tupla(local):
        print(f"{nome}: já está na versão {_tag(local)}. Não mexi em nada.")
        return []

    gerido = {r for r in p.arquivos if not _do_aluno(r)}
    if SETTINGS in gerido and (raiz / SETTINGS).is_file():      # o settings pode ser do aluno também
        p.arquivos[SETTINGS] = junta_settings((raiz / SETTINGS).read_bytes(), p.arquivos[SETTINGS])
    do_aluno = sorted(set(p.arquivos) - gerido)
    novos = sorted(r for r in gerido if not (raiz / r).exists())
    trocados = sorted(r for r in gerido - set(novos) if (raiz / r).read_bytes() != p.arquivos[r])
    sairam = _sumiram(raiz, p, gerido)

    copia = raiz / ESTADO / "copia" / _tag(local)
    print(f"{nome}: {_tag(local) if local else 'sem registro'} -> {_tag(p.versao)}" + (" (seco, não escrevi nada)" if seco else ""))
    print(_linha("trocados", trocados))
    print(_linha("novos", novos))
    print(_linha("movidos para a cópia", sairam))
    if do_aluno:
        print(_linha("do aluno, o ZIP trazia e eu não toquei", do_aluno))
    if seco:
        return trocados + novos + sairam

    for r in trocados + sairam:
        (copia / r).parent.mkdir(parents=True, exist_ok=True)
    for r in trocados:
        shutil.copy2(raiz / r, copia / r)
    for r in sairam:
        shutil.move(str(raiz / r), copia / r)
    for r in trocados + novos:
        (raiz / r).parent.mkdir(parents=True, exist_ok=True)
        (raiz / r).write_bytes(p.arquivos[r])
    _lista(raiz, p.produto).parent.mkdir(parents=True, exist_ok=True)
    _lista(raiz, p.produto).write_text("\n".join([f"# {p.versao}", *sorted(gerido)]) + "\n", encoding="utf-8")
    if not p.produto:       # por último: se parar no meio, a próxima rodada ainda acha a pasta velha
        (raiz / "VERSAO").write_text(p.versao + "\n", encoding="utf-8")
    if trocados + sairam:
        print(f"  cópia do que saiu ou mudou: {copia.relative_to(raiz).as_posix()}/")
    return trocados + novos + sairam


def atualiza(raiz: Path, zips: list[Path], seco: bool = False) -> None:
    if not (raiz / "VERSAO").is_file():
        sys.exit("Esta pasta não tem o arquivo VERSAO: não é uma Fábrica que veio de ZIP. Não mexi em nada.")
    if not zips:
        zips = procura([Path.home() / "Downloads", raiz.parent], raiz)
    if not zips:
        sys.exit("Não achei o ZIP novo em Downloads nem ao lado desta pasta. Baixe na aula da Fábrica, "
                 "na Academy, e rode de novo.")
    pacotes = sorted((Pacote(z) for z in zips), key=lambda p: bool(p.produto))   # lê todos antes de escrever; a Fábrica primeiro
    mudou = [r for p in pacotes for r in _aplica(raiz, p, seco)]
    if not mudou:
        return
    passos = (["uv sync"] if {"pyproject.toml", "uv.lock"} & set(mudou) else []) + [
        "uv run python tools/v2/v2.py biblioteca", "uv run python tools/video-use/helpers/confere.py"]
    print("Para valer, rode de novo sem --seco." if seco else "Agora rode, nesta ordem:\n  " + "\n  ".join(passos))


def main() -> None:
    ap = argparse.ArgumentParser(description="Atualiza a Fábrica com o ZIP novo, sem tocar no que é do aluno")
    ap.add_argument("zips", nargs="*", type=Path, help="o ZIP novo (sem ele, procura em Downloads e ao lado da pasta)")
    ap.add_argument("--seco", action="store_true", help="mostra o que mudaria e não escreve nada")
    ap.add_argument("--aviso", action="store_true", help="só a frase de aviso, se a versão tem 7 dias ou mais")
    args = ap.parse_args()
    if args.aviso:
        print(aviso_de_versao(RAIZ, date.today()) or "", end="")
        return
    atualiza(RAIZ, args.zips, args.seco)


if __name__ == "__main__":
    main()
