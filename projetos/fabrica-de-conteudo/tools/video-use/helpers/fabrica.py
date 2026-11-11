"""A fábrica: estilo, bruto e plano entram, o final sai.

Uma só, para aula e para reel. A orientação é campo do estilo, não nome de
módulo — o recorte do rosto não é do formato, e o vídeo de quadro, que tem molde
horizontal e nove verticais, deixa de nascer partido em dois.

    fabrica(plano)                     # renderiza e entrega
    fabrica(plano, seco=True)          # monta a cadeia e imprime, sem executar
    fabrica(plano, desde="desenho")    # reaproveita o que já está em disco

O plano diz o que é **daquele vídeo**: bruto, transcrição, janelas, drops,
conteúdo. O estilo diz o que vale para **todo vídeo daquele tipo**. Sobrescrita
de eixo no plano é o ajuste de um vídeo só; quando ela se repete, vira estilo
novo herdando.

**O modo seco é o ponto.** Ele monta a cadeia inteira e devolve os comandos, o
EDL calculado, o estilo resolvido e a pilha de recursos — sem esperar render. É
a única superfície de teste barata que um pipeline de vídeo tem.

Uso pela linha de comando:
    python helpers/fabrica.py <plano.json>
    python helpers/fabrica.py <plano.json> --seco
    python helpers/fabrica.py <plano.json> --seco --detalhe   # o comando e o "muda" de cada passo
    python helpers/fabrica.py <plano.json> --desde desenho
    python helpers/fabrica.py <plano.json> --rascunho   # corte seco 720p pro storyboard (plano em blocos)
    python helpers/fabrica.py <plano.json> --storyboard # vídeo do celular: decide, numera cada overlay e para
"""
from __future__ import annotations

import importlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import re
import tempfile
import threading
import time
import traceback
import unicodedata
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import checks
import clean_edl
import corte_suave
import estilo as es
import grade
import ancora
import ff
import impressao
import mixa
import regua
import transcribe as tsc
import transcript as tr
import vagas
import visual
from transcript import tempo_de_saida  # noqa: F401  (o test_fabrica e quem importa daqui)

AQUI = Path(__file__).resolve().parent
PY = sys.executable
# A biblioteca de peças: núcleo (cor, letra, movimento), catálogo e render.
V2 = AQUI.parents[1] / "v2"


def _v2():
    """Import tardio: o kit do aluno não leva a biblioteca, e só o bloco da VSL
    e a legenda precisam dela."""
    if str(V2) not in sys.path:
        sys.path.insert(0, str(V2))
    import v2
    return v2

# As etapas, em ordem. `desde` escolhe onde começar — é o que absorve o programa
# separado que refazia só o layout de um reel.
ETAPAS = ["corte", "render", "desenho", "composicao", "trilha", "entrega"]

OBRIGATORIOS = ("estilo", "fonte", "slug")
# O estilo de quem só traz o vídeo que gravou no celular.
ESTILO_DO_CELULAR = "reel-camera"
# A música do primeiro vídeo: a primeira das três faixas CC0 que o kit leva em `exemplos/trilhas/`
# (ver o LEIA-ME de lá). O tronco não tem a pasta, e a música dele (`assets/musica`) não tem licença
# para ir pra aluno: sem o arquivo, o plano mínimo sai sem trilha, como saía.
FAIXA_DO_KIT = AQUI.parents[2] / "exemplos" / "trilhas" / "lofi-calma.m4a"
# Quanto a duração do `fala.json` ao lado do bruto pode destoar da do bruto para valer como dele (s).
TOLERANCIA_FALA = 0.25
# O que cabe num plano mínimo. Com mais que isso (janelas, transcript, recorte...) o plano já diz
# como cortar, e a fábrica não transcreve nem normaliza por conta própria.
# Entram também os ajustes de um vídeo só que não dizem como cortar (trilha, voz, desenho...) e os
# botões do corte automático (`corte.congela_fim`, `corte.ajuste`): eles mudam como a fábrica corta, não onde.
MINIMO = {"fonte", "estilo", "slug", "projeto", "saida", "trabalho", "drops", "_dir",
          "paralelo", "faixa", "bruto", "recursos", "adaptadores",
          "voz", "graduacao", "efeito", "desenho", "trilha", "entrega", "momentos", "corte", "pecas",
          # o movimento do vídeo do celular (storyboard.py `_entra_do_plano`): não dizem como cortar
          "camera", "palavras_atras", "fundo", "sons",
          # a pauta de prova do vídeo de celular (visual.py): tela dividida e cheia com o visual achado
          "visual"}

# De que bruto cada estilo parte. Mandar uma live para um estilo de câmera é erro
# de entrada, não coisa para descobrir vinte minutos depois.
#
# `avatar` é o único que não parte de imagem: a fonte é a voz gravada, e o quadro
# só nasce depois que o HeyGen gera. Por isso a costura A dele roda no áudio.
#
# `banco` é o do criativo: as cenas já existem no banco, e a voz nasce do texto.
BRUTOS = {"live", "camera", "obs+celular", "board", "avatar", "banco"}

# Quanto custa, mais ou menos, processar um segundo de vídeo nesta máquina.
# Medido em 14/09/2026: 1440p30 num laptop de doze núcleos. Serve para comparar
# passos entre si; não é promessa de relógio.
SEGUNDOS_POR_SEGUNDO = 0.28

# Abaixo disto, o passo custa o vídeo inteiro e muda quase nada.
PISO_APROVEITAMENTO = 0.10

# Quantos passos rodam ao mesmo tempo (o plano muda com `paralelo`). Os blocos de um episódio
# não dependem um do outro, e um ajuste que mexia em dois refazia um depois do outro. Dois e
# não doze: o render já abre quatro ffmpeg por dentro, e com quatro workers montando ao mesmo
# tempo o Mac reiniciou (28/09). A medida da troca está no `_executa`.
PARALELO = 2

# Quantas corridas o tempo medido guarda por tipo de passo (`tempos.json`, no cache do usuário).
MOSTRAS = 5


@dataclass(frozen=True)
class Passo:
    """Um passo da cadeia: o que ele roda, o que produz, e quanto do vídeo muda.

    `toca` é o que separa um passo caro e honesto de um passo caro e bobo. O
    render toca tudo e custa tudo; o glitch tocava 0,4 s e custava 16,5 s. Com o
    número declarado, o segundo se denuncia no modo seco em vez de virar uma
    sensação de que "o pipeline está lento".
    """
    nome: str
    cmd: list[str]
    saida: Path
    entradas: list[Path] = field(default_factory=list)
    # Segundos do vídeo que este passo muda. None = muda tudo, e aí custar o
    # vídeo inteiro é o preço certo.
    toca: float | None = None
    # O que a fábrica calculou em memória e este passo consome — o EDL, por
    # exemplo. TEM que entrar na impressão: ler de volta do disco devolve o
    # arquivo da corrida anterior, e mudar a janela passava despercebido.
    extra: str = ""
    # Arquivo que a fábrica calcula em memória e o comando lê do disco — o plano
    # de um bloco, o de uma receita. Escrito na execução, antes do comando, e
    # só se mudou: reescrever igual dá instante novo e invalida o cache.
    arquivo: tuple[Path, str] | None = None
    # Preenchido pela fábrica: o cache já tem este trabalho?
    pulavel: bool = False
    # Passo cujo custo não vem do tamanho do vídeo: um portão mede e sai, e mede
    # o mesmo tanto num vídeo de 30s ou de 30min. Sem isto ele entra na conta
    # como se processasse o vídeo inteiro, e ainda é marcado de suspeito por não
    # mudar nada — que é exatamente o trabalho dele.
    custo_fixo: float | None = None
    # Quanto vídeo este passo processa, quando não é o vídeo inteiro: um passo
    # de bloco da VSL custa o bloco, e é contra o bloco que ele é suspeito.
    sobre: float | None = None
    # Quem cobra por este passo (a ElevenLabs, a HeyGen). A fábrica não gasta:
    # passo que cobra sai impresso com o comando, e ninguém o executa sozinho.
    cobra: str = ""
    # A etapa em que o passo mora (ETAPAS). A cadeia é montada inteira e o `--desde` filtra no
    # fim: o caminho entre os passos é o mesmo com ou sem desde. Vazio: roda em qualquer desde.
    etapa: str = ""

    def custo(self, duracao: float) -> float:
        """Estimativa grosseira, em segundos. É conta de guardanapo e está dita
        assim — serve para comparar passos entre si, não para prometer relógio."""
        if self.custo_fixo is not None:
            return self.custo_fixo
        return max(0.1, (self.sobre or duracao) * SEGUNDOS_POR_SEGUNDO)

    @property
    def chave(self) -> str:
        """O tipo do passo, igual de um vídeo para outro: o nome sem o bloco (`bloco 3: recorte`), sem
        o arquivo (`transcreve voz.mp3`) e sem o parêntese. A unidade vai junto, para que segundos fixos
        e segundos por segundo de vídeo nunca se misturem."""
        nome = re.sub(r"^(?!rascunho:)[^:]+: ", "", self.nome).split(" (")[0]
        nome = re.sub(r"^(transcreve|proxy de|peça|receita) .*", r"\1", nome)
        return f"{nome} ({'s' if self.custo_fixo is not None else 's/s'})"

    def estima(self, duracao: float, medidos: dict | None = None) -> tuple[float, bool]:
        """(segundos, medido nesta máquina?): a mediana das corridas medidas do tipo, se há; senão a
        conta de guardanapo de `custo`."""
        amostras = (medidos or {}).get(self.chave)
        if not amostras:
            return self.custo(duracao), False
        mediana = statistics.median(amostras)
        return (mediana if self.custo_fixo is not None else mediana * (self.sobre or duracao)), True

    def suspeito(self, duracao: float) -> bool:
        """Custa o vídeo inteiro e muda quase nada?

        É a regra que encontrou os dois passos caros deste projeto — o glitch
        gastava 16,5 s para trocar 0,4 s. Fica no código para encontrar o
        próximo, em vez de depender de alguém desconfiar de novo.
        """
        duracao = self.sobre or duracao
        if self.custo_fixo is not None or self.toca is None or duracao <= 0:
            return False
        return (self.toca / duracao) < PISO_APROVEITAMENTO


_TRAVA_TEMPOS = threading.Lock()


def _tempos_json() -> Path:
    return vagas.pasta_de_cache() / "tempos.json"


def tempos_medidos() -> dict[str, list[float]]:
    """O que cada tipo de passo levou nesta máquina (as últimas `MOSTRAS` corridas). Vazio se nunca
    mediu ou se o arquivo não presta: a estimativa de fábrica cobre."""
    try:
        return {k: [float(x) for x in v]
                for k, v in json.loads(_tempos_json().read_text(encoding="utf-8")).items()}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def grava_tempo(passo: Passo, duracao: float, segundos: float) -> None:
    """Anota quanto o passo levou. Passo que custa o vídeo guarda segundos por segundo de vídeo (vale
    para outro vídeo); passo fixo guarda os segundos. Disco que falha não derruba o render."""
    if passo.custo_fixo is None:
        base = passo.sobre or duracao
        if base <= 0:
            return
        segundos /= base
    with _TRAVA_TEMPOS:
        # shortcut: lê-muda-grava sem trava entre processos; duas corridas juntas podem perder uma amostra
        todos = tempos_medidos()
        todos[passo.chave] = [*todos.get(passo.chave, []), round(segundos, 4)][-MOSTRAS:]
        arquivo = _tempos_json()
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            novo = arquivo.with_name(f"{arquivo.name}.{os.getpid()}.tmp")
            novo.write_text(json.dumps(todos, ensure_ascii=False), encoding="utf-8")
            os.replace(novo, arquivo)
        except OSError:
            pass


@dataclass
class Seco:
    """O que a fábrica devolve quando não executa."""
    estilo: es.Estilo
    edl: list[dict]
    passos: list[Passo] = field(default_factory=list)
    final: Path = Path()
    duracao: float = 0.0
    pulados: list[str] = field(default_factory=list)
    # Recurso que o estilo pediu e que não vai entrar, porque o plano não trouxe
    # o dado dele. Some calado é o defeito; dizer na tela é o conserto.
    mudos: list[tuple[str, str]] = field(default_factory=list)
    # Os finais que já existem e não foram feitos pela fábrica.
    alheio: list[Path] = field(default_factory=list)
    # As notas do dono que o plano já descumpre (`checks.antes`).
    checks: list = field(default_factory=list)
    # Onde o corte suave liga (`_suave_linhas`): vazio quando o estilo não pede.
    suave: list[str] = field(default_factory=list)

    @property
    def comandos(self) -> list[list[str]]:
        return [p.cmd for p in self.passos]

    def custo_total(self, medidos: dict | None = None) -> float:
        """Segundos que faltam: o medido nesta máquina onde há, a estimativa de fábrica no resto."""
        medidos = tempos_medidos() if medidos is None else medidos
        return sum(p.estima(self.duracao, medidos)[0] for p in self.passos if not p.pulavel and not p.cobra)

    def imprime(self, detalhe: bool = False) -> None:
        """Uma linha por passo: número, nome, tempo e de onde o número vem. Com `detalhe`, o comando e
        o quanto do vídeo cada passo muda. O passo que cobra mostra o comando sempre: é o que o dono
        precisa ver antes de dizer sim."""
        e = self.estilo
        print(f"estilo   {e.nome}  ({e.orientacao}, parte de {e.bruto})")
        print(f"recursos {', '.join(e.recursos) or '(nenhum)'}")
        print(f"corte    {e.eixos['corte']['afinacao']} -> {len(self.edl)} trechos, "
              f"{_total(self.edl):.1f}s")
        for linha in self.suave:
            print(linha)
        print(f"final    {self.final}")
        for alheio in self.alheio:
            print(f"PERIGO   {alheio.name} já existe e não foi a fábrica que fez — "
                  f"a execução recusa; mude o slug ou tire o arquivo de lá")
        for recurso, campo in self.mudos:
            print(f"MUDO     {recurso}: o estilo pede e o plano não trouxe '{campo}' "
                  f"— esta camada não vai entrar")
        checks.mostra(self.checks)
        if self.pulados:
            print(f"cache    {len(self.pulados)} de {len(self.passos)} já feitos: "
                  f"{', '.join(self.pulados)}")

        medidos = tempos_medidos()
        n_medidos = 0
        print(f"\n{len(self.passos)} passos:")
        for k, p in enumerate(self.passos, 1):
            if p.pulavel:
                marca = "="
                custo = "já feito"
            elif p.cobra:
                marca = "$"
                custo = f"cobra: {p.cobra}"
            else:
                marca = "!" if p.suspeito(self.duracao) else " "
                segundos, medido = p.estima(self.duracao, medidos)
                n_medidos += medido
                custo = f"~{segundos:.0f}s {'medido' if medido else 'estimado'}"
            linha = f"{k:>3} {marca} {p.nome:<24} {custo:>20}"
            if detalhe:
                linha += "   " + ("muda tudo" if p.toca is None
                                  else f"muda {p.toca:.1f}s de {p.sobre or self.duracao:.0f}s")
            print(linha)
            if detalhe or p.cobra:
                print(f"      {' '.join(p.cmd)}")

        contam = [p for p in self.passos if not p.pulavel and not p.cobra]
        suspeitos = [p.nome for p in contam if p.suspeito(self.duracao)]
        print(f"\n~{self.custo_total(medidos) / 60:.1f} min no total ({n_medidos} de {len(contam)} medidos "
              f"nesta máquina, o resto é estimativa de fábrica)"
              + (f", {len(suspeitos)} passo(s) suspeito(s): {', '.join(suspeitos)}" if suspeitos else ""))


def _rel(plano: dict, caminho: str | Path) -> Path:
    """Caminho do plano: relativo à pasta dele, não a de quem chamou."""
    p = Path(caminho)
    return p if p.is_absolute() else Path(plano.get("_dir", ".")) / p


def _lista(x) -> list:
    return [] if not x else (x if isinstance(x, list) else [x])


def _caminhos(plano: dict) -> dict:
    """Os arquivos que a cadeia lê do plano, a partir da pasta dele: a regra do editorial e do
    criativo. Antes eles iam crus para o Path() e valia a pasta de quem rodou o comando. O
    `_confere` achava a fonte (procura nas duas) e o corte caía em FileNotFoundError."""
    def acha(c):
        p = _rel(plano, c)
        # ponytail: plano antigo, escrito a partir da raiz do repositório (videos/troco), ainda roda de lá
        return str(p if p.exists() or not Path(c).exists() else Path(c))
    novo = {**plano}
    for k in ("fonte", "transcript", "legenda", "camada", "celular", "visual"):
        if novo.get(k):
            novo[k] = acha(novo[k])
    if novo.get("gerado"):
        novo["gerado"] = [acha(g) for g in _lista(novo["gerado"])]
    if novo.get("broll"):
        novo["broll"] = [{**b, "arquivo": acha(b["arquivo"])} if b.get("arquivo") else b
                         for b in novo["broll"]]
    return novo


# ---- o plano mínimo e o bruto do celular ------------------------------------

def _slug(fonte: str | Path) -> str:
    """O nome do vídeo a partir do bruto: sem acento, sem espaço, em minúsculas."""
    base = unicodedata.normalize("NFKD", Path(fonte).stem).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "video"


def _completa(plano: dict) -> dict:
    """O plano mínimo (só o bruto) ganha o resto do que o estilo já sabe: o estilo do celular e o
    slug do nome do arquivo. Quem trouxe estilo de outro bruto, ou blocos, segue como estava."""
    if plano.get("blocos") or not plano.get("fonte"):
        return plano
    novo = {**plano}
    minimo = not set(plano) - MINIMO
    # o estilo-padrão é do plano mínimo; plano com janelas, transcript... precisa dizer o estilo.
    # O do aluno (`_padrao`, que o onboarding grava na marca) vem antes do reel-camera.
    if minimo:
        novo.setdefault("estilo", es.padrao_da_marca() or ESTILO_DO_CELULAR)
    try:
        e = es.estilo(novo["estilo"])
    except KeyError:
        e = None
    camera = e is not None and e.bruto == "camera"
    if camera and not novo.get("slug"):
        novo["slug"] = _slug(novo["fonte"])
    # O primeiro vídeo leva a música do kit por baixo da fala. Só se o aluno não decidiu nada sobre
    # música: faixa no plano ou no estilo, clima, `recursos` (inclusive o que tira a trilha).
    t = e.eixos["trilha"] if camera else {}
    if (minimo and camera and FAIXA_DO_KIT.is_file()
            and not (novo.get("faixa") or novo.get("recursos") or (novo.get("trilha") or {}).get("faixa")
                     or t["faixa"] or t["clima"])):
        novo["faixa"] = str(FAIXA_DO_KIT)
        if not e.tem("trilha"):
            novo["recursos"] = {"+": ["trilha"]}
    return novo


def motivos_de_normalizar(s: ff.Sonda) -> list[str]:
    """O que no bruto do celular o corte e a legenda não aguentam: HEVC, taxa variável, giro."""
    return ([f"codec {s.codec.upper()}"] if s.codec == "hevc" else []) \
        + (["taxa variável"] if s.vfr else []) \
        + ([f"girado {s.giro}°"] if s.giro else [])


def _taxa_fixa(s: ff.Sonda) -> int:
    """A taxa fixa do bruto normalizado: a média real do celular, arredondada para uma taxa
    padrão. Média solta (19, 27) deixaria o vídeo estranho no resto da cadeia."""
    alvo = s.fps_medio if s.vfr and s.fps_medio else s.fps
    return min((24, 25, 30, 50, 60), key=lambda t: abs(t - alvo)) if s.vfr else (alvo or ff.FPS)


def normaliza_bruto(fonte: Path, trabalho: Path) -> Passo | None:
    """O passo que deixa o bruto do celular como o corte espera: H.264, taxa fixa, giro aplicado e
    apagado dos metadados, num nome seguro na pasta de trabalho. Bruto limpo: None, nada a fazer.

    ponytail: HDR do iPhone sai sem mapa de tons (só vira 8 bits); fazer quando aparecer."""
    s = ff.probe(fonte)
    motivos = motivos_de_normalizar(s)
    if not motivos:
        return None
    saida = trabalho / "bruto.mp4"
    return Passo(f"normaliza o bruto ({', '.join(motivos)})",
                 ["ffmpeg", "-y", "-v", "error", "-i", str(fonte), "-map", "0:v:0", "-map", "0:a:0?",
                  "-vf", f"fps={_taxa_fixa(s)}", "-fps_mode", "cfr",
                  *ff.args_video("composicao", fps=None), *ff.args_audio(),
                  "-metadata:s:v:0", "rotate=0", str(saida)],
                 saida, [fonte], sobre=s.duracao)


def _avisa_modelo(passos: list[Passo]) -> None:
    """Antes do primeiro download, diz em português que vai baixar e quanto."""
    if any(p.nome.startswith("transcreve") and not ja_feito(p) for p in passos) \
            and not tsc.modelo_baixado():
        print(f"Vou baixar o modelo de transcrição ({tsc.MODELO_PADRAO}, ~{tsc.MODELO_GB} GB). "
              f"É uma vez só: nos próximos vídeos ele já está na máquina.", flush=True)


def _visual_json(plano: dict) -> Path | None:
    """O `visual.json` do plano: o que ele aponta em `visual`, ou o que mora ao lado dele. Só o vídeo de celular lê."""
    c = plano.get("visual")
    p = _rel(plano, c) if c else _rel(plano, "visual.json")
    if c and not p.exists():
        raise FileNotFoundError(f"o plano aponta visual {c}, que não existe")
    return p if p.exists() and not plano.get("blocos") else None


def _falta_pauta(plano: dict, e, fala: Path) -> str | None:
    """`--storyboard` do celular sem `visual.json` ao lado do plano: a linha que manda fazer a pauta antes (None se não falta).
    Só vale onde a pauta é lida: bruto de câmera em tela cheia, sem blocos. O `propoe.py` só completa os vãos depois dela."""
    if e.bruto != "camera" or e.eixos["imagem"]["composicao"] != "cheio" or plano.get("blocos") or _visual_json(plano):
        return None
    try:
        vj = _rel(plano, "visual.json").relative_to(Path.cwd())
    except ValueError:
        vj = _rel(plano, "visual.json")
    return (f"pauta: falta o visual.json — leia .claude/skills/fabrica-de-conteudo/pauta-visual.md, escreva {vj} com as "
            f"frases de {fala} (pode delegar a um subagente barato), rode acha.py e depois --storyboard de novo "
            f"(sem prova na tela, rode sem --pauta)")


def _confere(plano: dict) -> None:
    """Tudo o que dá para recusar antes do primeiro comando, recusado aqui."""
    obrig = ("estilo", "slug", "blocos") if plano.get("blocos") else OBRIGATORIOS
    faltando = [c for c in obrig if not plano.get(c)]
    if faltando:
        raise KeyError(
            f"o plano não tem: {', '.join(faltando)}. "
            f"Obrigatórios: {', '.join(obrig)}"
        )
    if plano.get("blocos"):
        for i, b in enumerate(plano["blocos"], 1):
            nome = b.get("nome") or f"#{i}"
            if not b.get("nome"):
                raise KeyError(f"o bloco #{i} não tem nome")
            if isinstance(b.get("pronto"), list):
                raise TypeError(f"bloco {nome}: `pronto` é o corte de um arquivo só")
            if b.get("janelas"):
                if not plano.get("fonte"):
                    raise KeyError(f"o bloco {nome} recorta janelas e o plano não tem "
                                   f"`fonte` — o bruto de onde elas saem")
                # o bloco pode recortar de outro bruto: o dia gravado em vários clipes
                fontes = _lista(b.get("fonte")) or [plano["fonte"]]
            else:
                fontes = (_lista(b.get("pronto")) or _lista(b.get("gerado"))
                          or _lista(b.get("fonte")))
            if not fontes:
                raise KeyError(f"o bloco {nome} não tem pronto, gerado nem fonte — "
                               f"não há de onde partir")
            for f in fontes + _lista(b.get("plano")) + _lista(b.get("voz")):
                if not _rel(plano, f).exists():
                    raise FileNotFoundError(f"bloco {nome}: não existe {_rel(plano, f)}")
    elif not plano.get("narracao") and not plano.get("trechos"):
        # Plano com `narracao` (ou os `trechos` do criativo) parte do texto: a voz,
        # que é a fonte, nasce no portão da ElevenLabs, e a cadeia para lá enquanto
        # ela não existir.
        fonte = Path(plano["fonte"])
        # relativa à pasta do plano também: é assim que o reel editorial lê todo caminho
        if not fonte.exists() and not _rel(plano, fonte).exists():
            raise FileNotFoundError(f"a fonte não existe: {fonte}")

    # O visual.json (a pauta de prova do celular): tipo, layout, fonte, alternativa e alternância recusam aqui;
    # a cobertura, que pede a duração do corte, recusa no passo `acha o visual`
    if (vj := _visual_json(plano)):
        doc = visual.le(vj)
        # o que ancora em palavra dita só tem tempo depois do corte: esse a `_visual` confere
        if (erros := [] if any(isinstance(b.get(k), dict) for b in doc.get("batidas", []) for k in ("t0", "t1")) else visual.valida(doc)):
            raise ValueError("o visual.json reprovou:\n  " + "\n  ".join(erros))

    # A régua de desenho: uma aula que virou slide de texto é defeito, e ele
    # aparece aqui em vez de aparecer no gate de alunos depois do render.
    if plano.get("overlays"):
        v = regua.confere(plano["overlays"])
        if not v.passou:
            raise ValueError(f"a régua de desenho reprovou:\n  {v}")


def _dura(j) -> float:
    """Uma janela `[de, até]`, `[de, até, congela]` ou `[de, até, congela, velocidade]`.
    O terceiro número são os segundos de quadro parado no fim dela (carta que passou
    rápido demais pra ler); o quarto acelera o trecho (a demora com uma carta na mão)."""
    congela = float(j[2]) if len(j) > 2 else 0.0
    vel = float(j[3]) if len(j) > 3 else 1.0
    return (float(j[1]) - float(j[0])) / vel + congela


def _total(trechos: list[dict]) -> float:
    """A duração do corte, com o quadro parado do fim (`congela`) que uma faixa carregar."""
    return sum(t["end"] - t["start"] + float(t.get("congela") or 0) for t in trechos)


def _segura_o_fim(trechos: list[dict], segundos: float, bruto_dur: float,
                  palavras: list[dict] = (), janelas: list = ()) -> list[dict]:
    """`corte.congela_fim`: o vídeo segura o fim por `segundos`, em vez de acabar na última palavra.

    A última faixa estica primeiro até o que o bruto tem depois dela, a cauda natural: a boca fecha, o
    corpo assenta. Essa cauda para antes de palavra que o corte deixou de fora e antes do fim da janela
    que o plano escolheu, pra o fim não devolver fala que o editor tirou. O que faltar dos `segundos`
    vira `congela` na faixa: o render.py repete o último quadro e cobre o áudio com silêncio.
    Com 0 (o padrão) o corte sai como veio."""
    segundos = float(segundos or 0)
    if segundos < 0:
        raise ValueError(f"corte.congela_fim não pode ser negativo (veio {segundos:g})")
    if not (segundos and trechos):
        return trechos
    *antes, ultimo = trechos
    fim = float(ultimo["end"])
    teto = float(bruto_dur)
    if janelas:                                   # a última janela pedida é a dona da última faixa
        teto = min(teto, float(janelas[-1][1]))
    fora = [float(w["start"]) for w in palavras
            if w.get("type", "word") == "word" and float(w["end"]) > fim + 0.001]
    if fora:
        teto = min(teto, min(fora) - 0.05)
    natural = max(0.0, min(segundos, teto - fim))
    novo = {**ultimo, "end": round(fim + natural, 3)}
    if segundos - natural >= 0.02:
        novo["congela"] = round(segundos - natural, 3)
    return [*antes, novo]


def _edl(plano: dict, e: es.Estilo, seco: bool = False) -> list[dict]:
    """A costura A, com a afinação que o estilo mandou."""
    if e.eixos["imagem"]["composicao"] == "editorial":
        # A voz sintética já sai sem ar morto, e o relógio do reel é o dela.
        return [{"source": plano["slug"], "start": 0.0, "end": float(plano.get("dur") or 0)}]
    if e.eixos["imagem"]["composicao"] == "cenas":
        # O criativo também: a voz inteira e a cauda. Sem a voz ainda, não há relógio.
        voz = _rel(plano, plano["fonte"])
        return [{"source": plano["slug"], "start": 0.0,
                 "end": ff.dur(voz) + _cr().CAUDA if voz.exists() else 0.0}]
    if plano.get("blocos"):
        # Na VSL em blocos o corte já aconteceu no áudio de cada take; cada
        # bloco entra inteiro, na ordem do plano.
        return [{"source": b["nome"], "start": 0.0,
                 "end": (ff.dur(_rel(plano, b["voz"])) + FOLGA_VOZ if b.get("voz") else
                         sum(_dura(j) for j in b["janelas"]) if b.get("janelas") else
                         sum(ff.dur(_rel(plano, f)) for f in
                             _lista(b.get("pronto")) or _lista(b.get("gerado"))
                             or _lista(b.get("fonte"))))}
                for b in plano["blocos"]]
    transcript = plano.get("transcript")
    fonte = Path(plano["fonte"])
    if transcript and not Path(transcript).exists() and not (seco or plano.get("_transcript_auto")):
        # Caminho digitado errado: cortar o vídeo inteiro calado esconderia o erro. Só vale quando a
        # transcrição vai nascer na cadeia (plano mínimo) ou no seco.
        raise FileNotFoundError(f"o `transcript` do plano não existe: {transcript}")
    if not transcript or not Path(transcript).exists():
        # Sem transcrição não há corte por palavra: o vídeo entra inteiro, e quem
        # corta por energia é uma afinação, não outro caminho. No seco do plano mínimo a
        # transcrição e o bruto normalizado ainda não existem: vale a duração do original.
        inteiro = ff.dur(fonte) if fonte.exists() else float(plano.get("_dur_bruto") or 0)
        return _segura_o_fim([{"source": fonte.stem, "start": 0.0, "end": inteiro}],
                             e.eixos["corte"].get("congela_fim", 0), inteiro)

    palavras = tr.carrega(transcript)["words"]
    janelas = [tuple(j) for j in plano.get("janelas", [])]
    trechos = clean_edl.cortar(
        palavras,
        drops=[tuple(d) for d in plano.get("drops", [])],
        janelas=janelas or None,
        afinacao=e.afinacao(),
        fonte=fonte.stem,
        # mede a voz no áudio: o `end` do whisper fecha antes do som (palavra cortada no fim)
        voz=clean_edl.fala_do_audio(fonte) if fonte.exists() else None,
    )
    return _segura_o_fim(trechos, e.eixos["corte"].get("congela_fim", 0),
                         ff.dur(fonte) if fonte.exists() else float(plano.get("_dur_bruto") or 0),
                         palavras, janelas)


def _fonte_isolada(trabalho: Path) -> Path:
    """Onde mora o bruto com a voz isolada (`voz.tratamento = isola`)."""
    return trabalho / "fonte_isolada.mp4"


def _transcricao(voz: Path, fala: Path) -> Passo | None:
    """A transcrição da voz, sempre na cadeia, guardada pela impressão, que olha a voz: voz
    refeita refaz a transcrição, voz igual pula. Antes ela entrava só quando o arquivo faltava,
    e a voz nova saía cortada e legendada no tempo da velha.

    Só a de `transcripts/<voz>.json`, que é onde o transcribe.py escreve. Transcrição em outro
    caminho é do usuário, e ninguém escreve por cima dela. A correção à mão na de `transcripts/`
    também fica: o transcribe.py só refaz quando a voz é mais nova que ela."""
    if (fala.parent.name, fala.name) != ("transcripts", f"{voz.stem}.json"):
        return None
    return Passo(f"transcreve {voz.name}",
                 [PY, str(AQUI / "transcribe.py"), str(voz), "--model", tsc.MODELO_PADRAO,
                  "--language", "pt", "--edit-dir", str(fala.parent.parent)],
                 fala, [voz], custo_fixo=60.0)


def _fala_pronta(bruto: Path, duracao: float) -> Path | None:
    """O Transcript que veio ao lado do bruto (o `fala.json` da demo do kit), se for o dele.

    Vale só com a mesma duração: um `fala.json` esquecido ao lado de outro vídeo cortaria o vídeo
    pela fala errada, e isso não se vê no seco. Na dúvida, nenhum: a fábrica transcreve."""
    arq = bruto.with_name("fala.json")
    try:
        doc = json.loads(arq.read_text(encoding="utf-8"))
        ok = abs(float(doc["duration"]) - duracao) <= TOLERANCIA_FALA and bool(doc["words"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return arq if ok else None


def _fala_no_corte(transcript: Path, trechos: list[dict]) -> str:
    """A transcrição no tempo do vídeo cortado. Palavra cujo meio o corte tirou sai."""
    return json.dumps(tr.no_corte(transcript, trechos), ensure_ascii=False)


def _pecas_da_fala(plano: dict, e: es.Estilo, fala, edl_texto: str) -> list[dict]:
    """As peças que a fala pede (recurso `pecas`), no tempo do vídeo cortado: [{peca, q, t0, t1, larg, y, ar?, som?}].

    A densidade: o `desenho` do plano, senão a que o aluno gravou (`movimento.py`), senão a do estilo. Sem nenhuma, sem peças.
    Plano que já traz as peças (`pecas` no storyboard aprovado, `legenda` pronta) não passa por aqui: o que o dono decidiu vale."""
    import movimento
    import propoe
    mov = movimento.le()
    dens = (plano.get("desenho") or {}).get("densidade") or mov.get("densidade") or e.eixos["desenho"]["densidade"]
    if not dens or plano.get("pecas") is not None:
        return []
    if not isinstance(fala, str) and not Path(fala).exists():
        return []           # o modo seco roda antes da transcrição: sem fala, o que a peça diria ainda não existe
    # a fala com os nomes de marca no lugar do erro do Whisper (o glossário do transcript), como a legenda a lê
    ws = [{**w, "text": tr.corrigir_termo(re.sub('["“”]', "", w["text"]))} for w in tr.palavras(json.loads(fala) if isinstance(fala, str) else Path(fala))]
    dur = sum(r["end"] - r["start"] for r in json.loads(edl_texto)["ranges"]) if edl_texto else (ws[-1]["end"] if ws else 0.0)
    pecas = [{"peca": x["peca"], "q": x["q"], "t0": x["em"], "t1": round(x["em"] + x["dur"], 2),
              **{k: x[k] for k in ("larg", "y", "ar", "som") if k in x}}
             for x in propoe.pecas_da_fala(ws, dur, dens, mov, checks._cardapio())]
    # a abertura (0 a 3 s) é do gancho escrito, que o `cards_da_fala.gancho` escolhe da fala de abertura
    import cards_da_fala
    g = cards_da_fala.gancho([{"tx": w["text"], "t0": w["start"], "t1": w["end"]} for w in ws]) if hasattr(cards_da_fala, "gancho") else None
    return ([{"peca": g["peca"], "q": g["q"], "t0": g["t0"], "t1": g["t1"]}] if g else []) + pecas


def _composicao(plano: dict, e: es.Estilo, corrente: Path, trabalho: Path,
                desenho: Path | None = None) -> tuple[list[list[str]], Path]:
    """Monta o quadro vertical: recorte do rosto mais o desenho.

    O recorte é medido no quadro da LIVE, e o render pode ter reescalado a fonte
    — então o vídeo volta às dimensões da live antes de recortar. Pular isso tira
    o rosto do lugar, e foi o defeito que custou mais retrabalho no reel.
    """
    img = e.eixos["imagem"]
    modo = img["composicao"]
    if modo == "cheio" or not img["recorte"]:
        return [], corrente

    fonte = Path(plano["fonte"])
    sonda = ff.probe(fonte)
    lw, lh = sonda.largura, sonda.altura
    bw, bh = img["banda"]
    topo = trabalho / "rosto.mp4"
    brutos = [["ffmpeg", "-y", "-i", str(corrente), "-vf",
             f"scale={lw}:{lh},{img['recorte']},"
             f"scale={bw}:{bh}:force_original_aspect_ratio=increase,"
             f"crop={bw}:{bh},setsar=1,fps={img['fps']}",
             "-an", *ff.args_video("efeito", fps=None), str(topo)]]
    cmds = [Passo("recorte do rosto", brutos[0], topo, [corrente])]

    if desenho is None:
        return cmds, topo

    saida = trabalho / "composto.mp4"
    largura, altura = (1080, 1920)
    if modo == "pilha":
        fc = "[0:v][1:v]vstack=inputs=2[v]"
    else:   # sobreposicao — o desenho vem com chroma magenta por cima do rosto
        fc = (f"[0:v]pad={largura}:{altura}:0:0:color=0x1a1614[b];"
              f"[1:v]colorkey=0xff00ff:0.30:0.12[k];[b][k]overlay=0:0[v]")
    cmds.append(Passo("montagem do quadro",
                      ["ffmpeg", "-y", "-i", str(topo), "-i", str(desenho),
                       "-i", str(corrente), "-filter_complex", fc,
                       "-map", "[v]", "-map", "2:a",
                       *ff.args_video(img["qualidade"]), *ff.args_audio(),
                       "-shortest", str(saida)],
                      saida, [topo, desenho, corrente]))
    return cmds, saida


# A forma de um beat de b-roll. Obrigatório é o que o `broll_cmd` lê sem `get`;
# opcional é o que ele lê com padrão. `fonte` não é desenho: é a procedência do
# clipe, e viaja junto para o final poder dizer de onde cada quadro veio.
# `nota` é documental e ninguém a lê — é o lugar de escrever por que aquele clipe
# está ali, que é a única coisa que um plano não consegue dizer sozinho.
BEAT_OBRIGATORIOS = ("arquivo", "em", "dur")
BEAT_OPCIONAIS = ("anim", "largura", "altura", "x", "y", "fonte", "nota")

# O vocabulário de antes da fábrica, que sobreviveu num plano. Recusar sem
# ensinar a tradução manda quem escreveu adivinhar.
BEAT_VELHO = {"file": "arquivo", "start": "em", "scale_w": "largura",
              "x_off": "x", "y_off": "y", "note": "nota",
              # `sfx` não tem para onde ir: nenhum passo da cadeia lia esse
              # campo, então o som que ele pedia nunca tocou. Quem tem efeito
              # sonoro para colocar usa o `som.py`, depois da emenda.
              "sfx": "(nada lia este campo; use o som.py)"}


def confere_beats(lista: list[dict]) -> list[dict]:
    """Confere a forma de cada beat de b-roll, e devolve a lista intacta.

    Antes disto o erro aparecia como `KeyError: 'arquivo'` no meio da montagem do
    filtro, sem dizer qual beat nem o que era esperado.
    """
    validos = set(BEAT_OBRIGATORIOS) | set(BEAT_OPCIONAIS)
    for i, b in enumerate(lista, 1):
        velhas = {k: BEAT_VELHO[k] for k in b if k in BEAT_VELHO}
        if velhas:
            traducao = ", ".join(f"{v} -> {n}" for v, n in sorted(velhas.items()))
            raise KeyError(
                f"o beat #{i} usa o vocabulário antigo: {traducao}. "
                f"Campos de hoje: {', '.join(sorted(validos))}"
            )
        faltando = [c for c in BEAT_OBRIGATORIOS if c not in b]
        if faltando:
            raise KeyError(
                f"o beat #{i} não tem: {', '.join(faltando)}. "
                f"Obrigatórios: {', '.join(BEAT_OBRIGATORIOS)}"
            )
        sobrando = sorted(set(b) - validos)
        if sobrando:
            raise KeyError(
                f"o beat #{i} tem campo que não existe: {', '.join(sobrando)}. "
                f"Disponíveis: {', '.join(sorted(validos))}"
            )
    return lista


def procedencia(plano: dict) -> list[dict]:
    """O que entrou no final e não é seu.

    Só o que declara `fonte`: material próprio não precisa de licença, e listá-lo
    junto transformaria a declaração num inventário onde ninguém acha nada.
    """
    return [{"arquivo": b["arquivo"], "fonte": b["fonte"]}
            for b in (plano.get("broll") or []) if b.get("fonte")]


def broll_cmd(e: es.Estilo, corrente: Path, beats: list[dict], saida: Path) -> list[str]:
    """B-roll por cima da fala, entrando e saindo por deslize.

    Cada corte de apoio é um clipe com alpha que desliza para dentro e para fora.
    O deslocamento é escrito como expressão do tempo, e não como fade de posição,
    porque o overlay só aceita uma posição por quadro — a rampa TEM que estar na
    coordenada.
    """
    d = e.eixos["desenho"].get("broll_fade", 0.28)
    largura, altura = 1080, 674

    entradas = ["-i", str(corrente)]
    for b in beats:
        entradas += ["-i", str(b["arquivo"])]

    partes, anterior = [], "[0:v]"
    for i, b in enumerate(beats, 1):
        em, dur = float(b["em"]), float(b["dur"])
        fim, larg = em + dur, int(b.get("largura", largura))
        partes.append(
            f"[{i}:v]trim=0:{dur},setpts=PTS-STARTPTS,scale={larg}:-2,format=yuva420p,"
            f"fade=t=in:st=0:d={d}:alpha=1,fade=t=out:st={dur - d}:d={d}:alpha=1,"
            f"setpts=PTS-STARTPTS+{em}/TB[b{i}]"
        )

    for i, b in enumerate(beats, 1):
        em, dur = float(b["em"]), float(b["dur"])
        fim, anim = em + dur, b.get("anim", "top")
        x0, y0 = int(b.get("x", 0)), int(b.get("y", 0))
        larg = int(b.get("largura", largura))
        dentro = f"clip((t-{em})/{d}\\,0\\,1)"
        fora = f"clip((t-{fim}+{d})/{d}\\,0\\,1)"
        if anim == "top":
            alt = int(b.get("altura", altura))
            x, y = str(x0), f"{y0}+{-alt}*(1-{dentro})+{-alt}*{fora}"
        elif anim == "left":
            x, y = f"{x0}+{-larg}*(1-{dentro})+{-larg}*{fora}", str(y0)
        elif anim == "static":
            x, y = str(x0), str(y0)
        else:                                           # right
            x, y = f"{x0}+{largura}*(1-{dentro})+{largura}*{fora}", str(y0)
        alvo = f"[v{i}]" if i < len(beats) else "[v]"
        partes.append(f"{anterior}[b{i}]overlay=x='{x}':y='{y}':"
                      f"enable='between(t,{em - d},{fim + d})'{alvo}")
        anterior = f"[v{i}]"

    return ["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(partes),
            "-map", "[v]", "-map", "0:a?",
            *ff.args_video(e.eixos["imagem"]["qualidade"], fps=None),
            "-c:a", "copy", str(saida)]


def ja_feito(passo: Passo) -> bool:
    """O cache já tem o trabalho deste passo?"""
    return impressao.pronto(passo.saida, _digital(passo))


def _do_bloco(passo: Passo, refaz) -> bool:
    """O passo é de um dos blocos do `--refaz`? Os passos de bloco se chamam `<bloco>: <o que faz>`."""
    return ":" in passo.nome and passo.nome.split(":", 1)[0] in refaz


def _esquece_blocos(passos: list[Passo], refaz) -> None:
    """`--refaz <bloco>`: apaga só a marca dos passos desses blocos. Os que leem a saída deles refazem sozinhos (o instante do
    arquivo novo muda a impressão deles); os outros blocos ficam no cache."""
    for p in passos:
        if _do_bloco(p, refaz):
            impressao.esquece(p.saida)


def _confere_refaz(plano: dict, refaz) -> None:
    nomes = [b.get("nome") for b in plano.get("blocos") or []]
    if refaz and not nomes:
        raise ValueError("--refaz vale pro plano em blocos")
    if falta := [r for r in refaz if r not in nomes]:
        raise ValueError(f"--refaz {', '.join(falta)}: o plano não tem esse bloco. Blocos: {', '.join(map(str, nomes))}")


def _modo_hardware(codificador: str | None) -> str:
    """O `imagem.codificador` do estilo no valor que o `ff` lê em `FF_HARDWARE`."""
    return {"hardware": "1", "auto": "auto"}.get(codificador, "0")


def _digital(passo: Passo) -> str:
    # o codificador de hardware muda todo encode sem mudar o comando: entra pela variável
    hw = {"1": [ff.HARDWARE], "auto": [ff.HARDWARE + "=auto"]}.get(os.environ.get(ff.HARDWARE), [])
    return impressao.de(passo.cmd + ([passo.extra] if passo.extra else []) + hw,
                        _entradas(passo), helpers=_helpers(passo))


def _entradas(passo: Passo) -> list[Path]:
    """Todo arquivo que o comando lê entra na impressão.

    Curar essa lista à mão era o erro: três dos cinco passos que recebem arquivo
    por argumento — o explicador, o b-roll e a legenda — ficaram de fora, e o
    efeito é o pior que existe. O comando não muda, a impressão não muda, e o
    cache entrega o vídeo com o card velho sem avisar ninguém.

    A saída do próprio passo fica de fora: ela existe da corrida anterior, e o
    instante dela mudaria a impressão a cada corrida.
    """
    achados = list(passo.entradas)
    for arg in passo.cmd:
        if not isinstance(arg, str) or arg.startswith("-"):
            continue
        p = Path(arg)
        try:
            # Perguntar a um `filter_complex` de b-roll se ele é arquivo estoura
            # `File name too long` — são milhares de caracteres, e o sistema
            # recusa antes de responder que não existe. O que não dá para
            # perguntar não é entrada.
            if p == passo.saida or not p.exists() or p.is_dir():
                continue
        except OSError:
            continue
        if p not in achados:
            achados.append(p)
    return achados


def _helpers(passo: Passo) -> list[Path]:
    """Os arquivos de código que produzem esta saída.

    É isto que faz corrigir uma heurística refazer o que ela produziu, sem
    ninguém lembrar de subir um número de versão. Um passo que chama ffmpeg
    direto não tem helper: o comando já está na impressão inteiro.
    """
    proprios = [Path(c) for c in passo.cmd
                if isinstance(c, str) and c.endswith(".py") and Path(c).exists()]
    return proprios + [AQUI / m for c in proprios for m in JUNTO.get(c.name, ()) if (AQUI / m).exists()]


# O código que um helper importa e que decide a saída dele: a legenda move a câmera e assenta o card
# pela análise de cena, que moram em módulos próprios. Mexer neles refaz a legenda.
# O render põe a emenda do corte suave (ponte de quadros, zoom, cama de som): mexer nela refaz o corte.
JUNTO = {"captions_viral.py": ("camera.py", "cena.py"),
         "render.py": ("corte_suave.py", "corte_suave.swift")}


def _final(plano: dict, e: es.Estilo) -> Path:
    """Onde o final limpo mora. Não é campo livre: quem manda é o estilo."""
    pasta = e.eixos["entrega"]["pasta"]
    # As pastas de reel são planas: o final mora nelas direto, sem pasta de projeto.
    # videos/topo guarda os reels de topo de funil, e a pasta de cada um é a de trabalho.
    reel = pasta.endswith(("reels", "topo"))
    projeto = plano.get("projeto", "sem-projeto")
    if plano.get("saida"):
        # `saida` é a pasta dos projetos, no lugar de videos/
        raiz = _rel(plano, plano["saida"]).resolve()
        destino = raiz / Path(pasta).name if reel else raiz / projeto
    else:
        # Sem `saida`, a pasta do estilo manda. Antes ela só servia para testar
        # se terminava em "reels", e todo final caía em obs-optimize/<projeto>/,
        # fora de videos/ — nenhum plano real passava `saida`, os testes sim.
        destino = AQUI.parents[2] / pasta / ("" if reel else projeto)
    return destino / f"{plano['slug']}.mp4"


def trabalho_do(plano: dict, e: es.Estilo) -> Path:
    """A pasta de trabalho do vídeo: a que o plano aponta, ou `_trabalho/<slug>` ao lado do final.
    Quem inspeciona o corte depois da fábrica (os comandos das skills de estilo) acha a pasta por aqui."""
    return (_rel(plano, plano["trabalho"]) if plano.get("trabalho")
            else _final(plano, e).parent / "_trabalho" / plano["slug"]).resolve()


def _marca_final(final: Path) -> Path:
    return final.with_name(final.name + ".fabrica")


def _final_alheio(final: Path) -> bool:
    """Já existe um final com este nome, e não foi a fábrica que fez?

    Os finais publicados moram em videos/ e ficam fora do git. Em 26/09 o slug
    de um plano novo da VSL era o nome do vídeo que estava no ar, e o copy do
    fim da cadeia o apagaria sem aviso.
    """
    return final.exists() and not _marca_final(final).exists()


def _preparo_avatar(plano: dict, e: es.Estilo, trabalho: Path) -> tuple[list[Passo], Path]:
    """A costura A do bruto `avatar`: ela roda no ÁUDIO, antes de existir imagem.

    O apresentador da VSL é gerado pelo HeyGen a partir da voz real dele, então
    não há quadro para cortar na hora do corte. Trata a voz, apara as pausas com
    a mesma afinação que o estilo declara, e para no portão.

    **O portão não é burocracia: é o passo mais barato da cadeia.** 83% dos
    créditos de uma sessão foram embora no mesmo padrão, quatro vezes — gerar,
    descobrir que o áudio estava errado, gerar de novo. Medir antes custa um
    segundo; gerar custa crédito e cinco minutos.
    """
    fonte = Path(plano["fonte"])
    voz = trabalho / "voz.wav"
    limpo = trabalho / "voz_limpa.wav"
    t_limpo = trabalho / "transcript_limpo.json"
    c = e.eixos["corte"]

    passos = [p for p in [_transcricao(fonte, Path(plano["transcript"]))] if p]
    if e.eixos["voz"]["tratamento"] == "cru":
        # Voz sintética já sai limpa e no nível; o portão ainda mede o loudness.
        voz = fonte
    else:
        passos.append(Passo("voz tratada",
                            [PY, str(AQUI / "trata_voz.py"), str(fonte), "-o", str(voz),
                             "--alvo", str(e.eixos["voz"]["alvo"])],
                            voz, [fonte]))

    apara = [PY, str(AQUI / "apara_pausas.py"), str(voz),
             "--transcript", str(plano["transcript"]),
             "-o", str(limpo), "--out-transcript", str(t_limpo),
             "--afinacao", c["afinacao"]]
    # A afinação do estilo manda aqui também. Sem isto o corte da VSL e o corte
    # que a fábrica calcula seriam dois números diferentes com o mesmo nome.
    for botao, flag in (("sil_cut", "--sil-cut"), ("pause_keep", "--pause-keep"),
                        ("pad_out", "--pad-out")):
        if botao in c["ajuste"]:
            apara += [flag, str(c["ajuste"][botao])]
    for d in plano.get("drops", []):
        apara += ["--drop", str(d[0]), str(d[1])]
    # Emenda de dois takes no meio da frase ("Funciona" de um, "assim, se você decidir" do outro):
    # a borda cai em voz de propósito, e o plano diz isso em vez de a trava do apara barrar.
    if plano.get("drop_em_voz"):
        apara.append("--drop-em-voz")
    passos.append(Passo("apara pausas", apara, limpo, [voz]))

    # O whisper escreve a frase como devia ser e apaga o falso começo; o
    # clean_edl lê esse texto e não enxerga o tropeço. Um modelo que OUVE
    # reprova antes do portão — o V1 da VSL saiu com quatro gaguejadas e os
    # centavos do preço cortados. Sem chave da OpenRouter ele avisa e passa.
    ouvido = trabalho / "ouvido.json"
    passos.append(Passo("ouvido confere",
                        [PY, str(AQUI / "ouvido.py"), "confere", str(limpo), "--json", str(ouvido), "--inteiro"],
                        ouvido, [limpo], toca=0.0, custo_fixo=30.0))

    portao = [PY, str(AQUI / "pre_voo.py"), str(limpo), "--transcript", str(t_limpo)]
    if plano.get("creditos"):
        portao += ["--creditos", str(plano["creditos"])]
    # O look é de quem gera: o plano escolhe; sem ele, o pre_voo lê o HEYGEN_LOOK.
    if plano.get("look"):
        portao += ["--look", str(plano["look"])]
    # Não produz arquivo: é portão, e sair 0 é o produto. A saída é um nome que
    # nunca existe, então ele roda toda vez — custa um segundo. Apontar para o
    # áudio limpo fazia o portão e o apara apagarem a marca de cache um do
    # outro: o apara refazia sempre, e o ouvido, que é pago, vinha atrás.
    passos.append(Passo("portão do HeyGen", portao, trabalho / "portão", [limpo],
                        toca=0.0, custo_fixo=1.0))
    return passos, limpo


# ---- a VSL em blocos ---------------------------------------------------------
#
# Um bloco é um take: voz própria, geração própria no HeyGen e um plano próprio
# (cards, peças, câmera, sons) com o tempo contado do zero dele. Era o que o
# monta.sh da VSL do Hermes fazia à mão, com a direção copiada em cada plano.

# O que um item de receita diz à fábrica, e não à receita.
RECEITA_ORQUESTRA = {"id", "de", "ate", "tira", "sem_legenda", "rosto"}


def _direcao(doc: dict, base: Path, e: es.Estilo, nome: str) -> dict:
    """O plano de um bloco com o que é do ESTILO preenchido, e os caminhos
    absolutos — ele vai ser lido de outra pasta, a de trabalho."""
    d = json.loads(json.dumps(doc))
    des = e.eixos["desenho"]
    d.setdefault("acento", _v2().token("ac", des["tema"]))
    # o preset de legenda do estilo (anuncio-clone); o do bloco, se houver, ganha
    if des["legenda"]:
        d.setdefault("legenda", des["legenda"])
    for c in d.get("cards") or [] if des["fonte"] else []:
        c.setdefault("fonte", des["fonte"])
    if des["ritmo"] and "ritmo" not in d:
        d["ritmo"] = {"entrada": des["ritmo"][0], "stagger": des["ritmo"][1]}
    if not des["atras"]:
        atras = [c.get("t0") for c in d.get("cards") or [] if c.get("atras")]
        if atras:
            raise ValueError(
                f"bloco {nome}: card com texto atrás da pessoa em {atras} — o estilo "
                f"'{e.nome}' não põe nada atrás do sujeito. Ênfase é peso e escala."
            )
    for chave in ("brolls", "sons"):
        for item in d.get(chave) or []:
            if "arquivo" in item and (base / item["arquivo"]).exists():
                item["arquivo"] = str((base / item["arquivo"]).resolve())
    return d


def _recorte_pip(fonte: Path, em: float, dur: float, base: list, cache: dict) -> list:
    """O recorte do cartão (fração da fonte) centrado nele: mediana do centro do rosto em ~4 quadros da peça.
    Horizontal no meio do cartão; vertical (se o recorte não for a altura toda) com a cabeça no terço de cima.
    Sem rosto na peça, ou sem Vision (kit, Windows, Linux): o centro do quadro."""
    cx, cy, cw, ch = base
    chave = f"{round(em, 2)}:{round(dur, 2)}"
    if chave not in cache:
        try:
            import olhar_camera as oc
            fim = em + min(dur, 4.0)
            qs = [q for q in oc.mede(fonte, em, fim, qps=1.0, largura=640) if not q.get("sem")]
            cache[chave] = [statistics.median(q["cx"] for q in qs), statistics.median(q["cy"] for q in qs)] if qs else None
        except Exception:
            cache[chave] = None
    centro = cache[chave]
    if centro is None:
        return [round((1 - cw) / 2, 4), round((1 - ch) / 2, 4), cw, ch]
    return [round(min(max(centro[0] - cw / 2, 0.0), 1 - cw), 4), round(min(max(centro[1] - ch / 3, 0.0), 1 - ch), 4), cw, ch]


def _peca(item: dict, e: es.Estilo, pasta: Path) -> Passo:
    """Uma peça pedida pelo nome do catálogo, renderizada no tema do estilo.

    O arquivo leva o hash do pedido no nome: a mesma peça com o mesmo texto não
    é renderizada duas vezes, e texto novo nunca cai em cima do velho.
    """
    import hashlib
    from urllib.parse import parse_qsl
    v2 = _v2()
    peca = item.pop("peca")
    q = item.pop("q", {})
    pares = [f"{k}={v}" for k, v in (q.items() if isinstance(q, dict)
                                     else parse_qsl(q.lstrip("?"), keep_blank_values=True))]
    ar = item.pop("ar", None)
    tema = item.pop("tema", None) or e.eixos["desenho"]["tema"]
    # `opaco`: a peça que toma a tela inteira sai em mp4, sem alfa (o explicador da aula)
    opaco = bool(item.pop("opaco", False))
    # `plana`: a peça em camadas renderizada inteira, por cima de tudo (o explicador da aula sempre
    # a pôs assim); sem ela, peça em camadas é texto atrás da pessoa
    if v2.acha(peca)[0]["camadas"] and not item.pop("plana", False) and not e.eixos["desenho"]["atras"]:
        raise ValueError(f"a peça {peca} põe texto atrás da pessoa, e o estilo "
                         f"'{e.nome}' não põe nada atrás do sujeito")
    # a peça sai no fps do estilo: a 30 num estilo a 24 (o reel-camera), o fps=24 do captions_viral
    # pulava 1 quadro da peça em 5
    fps = e.eixos["imagem"]["fps"]
    chave = hashlib.blake2b(json.dumps([peca, pares, ar, tema, *([fps] if fps != ff.FPS else []),
                                        *(["opaco"] if opaco else [])]).encode(), digest_size=4).hexdigest()
    saida = pasta / f"{peca}-{chave}.{'mp4' if opaco else 'mov'}"
    cmd = [PY, str(V2 / "v2.py"), "render", peca, *pares, "--tema", tema, "--fps", str(fps), "--out", str(saida)]
    if ar:
        cmd += ["--ar", ar]
    if opaco:
        cmd.append("--opaco")
    item["arquivo"] = str(saida)
    item["_peca"] = peca                    # o `tira` da receita acha pelo nome
    # Sem `alfa` o captions_viral perde o alpha e a peça transparente cobre o
    # vídeo com um retângulo preto. Quem sabe se ela é transparente é o catálogo.
    item.setdefault("alfa", not opaco and bool(v2.acha(peca)[0]["alfa"]))
    # O nome do arquivo guarda o pedido; o desenho está no HTML, no que ele inclui do núcleo e
    # nas imagens da query, e é por eles que mexer numa peça refaz o render. Refazer é barato:
    # o v2 guarda por conteúdo, e a peça que não mudou sai do cache dele.
    p, _, query = v2.pedido(peca, pares, ar, tema)
    desenho = v2.dependencias(p, query)
    return Passo(f"peça {peca}", cmd, saida, desenho, custo_fixo=10.0)


def _camera_parada(cams: list[dict], janelas: list[tuple[float, float]]) -> list[dict]:
    """Corta a câmera nas bordas das janelas; dentro delas, quadro parado — zoom
    por cima de receita corta o texto dela."""
    out = []
    for c in cams:
        a, z = float(c["t0"]), float(c["t1"])
        cortes = sorted({a, z, *[x for j in janelas for x in j if a < x < z]})
        for x, y in zip(cortes, cortes[1:]):
            dentro = any(j0 <= x and y <= j1 for j0, j1 in janelas)
            out.append({"t0": x, "t1": y, "zoom": [1.0, 1.0], "ease": "reta"} if dentro
                       else {**c, "t0": x, "t1": y})
    return out


def _receitas(plano: dict, b: dict, base: Path, doc: dict, e: es.Estilo,
              pasta: Path) -> tuple[list[Passo], Path]:
    """Janelas do bloco em que o rosto sem fundo volta sobre a placa, com a
    receita desenhada em volta dele. A boca da receita foi gerada com o mesmo
    trecho de áudio, então só a IMAGEM é trocada; o som fica o da base."""
    img = e.eixos["imagem"]
    placa = _rel(plano, b.get("placa") or plano["placa"])
    passos, janelas, partes = [], [], []
    for m in sorted(b["receitas"], key=lambda m: m["de"]):
        dur = round(m["ate"] - m["de"], 3)
        r = {k: v for k, v in m.items() if k not in RECEITA_ORQUESTRA}
        # O plano da receita é lido da pasta de trabalho: todo caminho que ele
        # cita (captura, take_b) tem que sair absoluto daqui.
        for k, v in list(r.items()):
            if isinstance(v, str) and ("/" in v or "." in v) and _rel(plano, v).exists():
                r[k] = str(_rel(plano, v).resolve())
        rosto = _rel(plano, m["rosto"]).resolve()
        rp = {"fonte": str(rosto), "placa": str(placa.resolve()),
              "receitas": [{**r, "de": 0.0, "ate": dur}]}
        texto = json.dumps(rp, ensure_ascii=False, indent=1)
        pj, mp4 = pasta / f"{m['id']}.plano.json", pasta / f"{m['id']}.mp4"
        citados = [Path(v) for v in r.values() if isinstance(v, str) and Path(v).is_absolute()]
        desenho = [V2 / "nucleo" / n for n in ("receita.html", "receitas-core.js", "legendas-core.js")]
        passos.append(Passo(f"receita {m['id']}",
                            [PY, str(AQUI / "receita_para_video.py"), str(pj), str(mp4)],
                            mp4, [rosto, placa, *citados, *desenho,
                                  AQUI / "receitas_prep.py", AQUI / "som.py"],
                            extra=texto, arquivo=(pj, texto)))
        janelas.append((m["de"], m["ate"]))
        partes.append((m, mp4))
        # os sons da receita: o som.py lê os cues dela quando o arquivo existir
        doc.setdefault("cues_de", []).append({"arquivo": str(mp4), "t0": m["de"], "t1": m["ate"]})

    for (a, z), (a2, _) in zip(janelas, janelas[1:]):
        if a2 < z:
            raise ValueError(f"bloco {b['nome']}: receitas sobrepostas em {a2:.2f}s — "
                             f"a emenda pularia a base e o vídeo sairia maior que o áudio")
    # Peça pedida pelo nome ainda não tem arquivo: o `tira` acha pelo nome dela.
    nome_de = lambda x: x.get("peca") or Path(x["arquivo"]).name
    tira = {n for m in b["receitas"] for n in m.get("tira", [])}
    doc["brolls"] = [x for x in doc.get("brolls") or [] if nome_de(x) not in tira]
    for x in doc["brolls"]:
        a, z = float(x["t0"]), float(x["t1"])
        if any(a < j1 and j0 < z for j0, j1 in janelas):
            raise ValueError(f"bloco {b['nome']}: b-roll {nome_de(x)} "
                             f"em cima de receita — tire com `tira`")
    doc["camera"] = _camera_parada(doc.get("camera") or [], janelas)
    mudas = [(m["de"], m["ate"]) for m in b["receitas"] if m.get("sem_legenda")]
    doc["cards"] = [c for c in doc.get("cards") or []
                    if not any(float(c["t0"]) < z and a < float(c["t1"]) for a, z in mudas)]

    # A base com cada janela trocada pelo vídeo da receita. A cauda vai até o
    # fim sem precisar saber a duração, que no modo seco ainda não existe.
    w, h = (1080, img["altura"]) if e.vertical else (img["altura"] * 16 // 9, img["altura"])
    ins, fc, t = ["-i", str(base)], [], 0.0
    for k, (m, mp4) in enumerate(partes, 1):
        ins += ["-i", str(mp4)]
        if m["de"] > t:
            fc.append(f"[0:v]trim={t:.3f}:{m['de']:.3f},setpts=PTS-STARTPTS[p{len(fc)}]")
        # a receita pode sair um quadro mais longa: corta na duração da janela
        fc.append(f"[{k}:v]fps={img['fps']},scale={w}:{h},setsar=1,"
                  f"trim=0:{m['ate'] - m['de']:.3f},setpts=PTS-STARTPTS[p{len(fc)}]")
        t = m["ate"]
    fc.append(f"[0:v]trim=start={t:.3f},setpts=PTS-STARTPTS[p{len(fc)}]")
    grafo = ";".join(fc) + ";" + "".join(f"[p{i}]" for i in range(len(fc))) \
        + f"concat=n={len(fc)}:v=1:a=0[v]"
    saida = pasta / "base.mp4"
    passos.append(Passo("receitas na base",
                        ["ffmpeg", "-y", *ins, "-filter_complex", grafo, "-map", "[v]",
                         "-map", "0:a", *ff.args_video(fps=img["fps"]), "-c:a", "copy", str(saida)],
                        saida, [base] + [mp4 for _, mp4 in partes],
                        toca=sum(m["ate"] - m["de"] for m, _ in partes)))
    return passos, saida


# Silêncio depois da última palavra de um bloco de voz gravada, antes do corte.
FOLGA_VOZ = 0.3


# A altura do proxy da entrada (`proxy.py`): a do longo do canal.
ALTURA_PROXY = 1080


def caminho_proxy(fonte: Path, alt: int) -> Path:
    return fonte.parent / "proxy" / f"{fonte.stem}-{alt}p.mov"


def selo_proxy(fonte: Path) -> str:
    """Tamanho e instante do bruto: o proxy só vale enquanto o bruto for o mesmo."""
    st = fonte.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def proxy_pronto(fonte: Path, alt: int) -> Path | None:
    """O proxy que o `proxy.py` deixou, inteiro e deste bruto (o selo `.pronto` ao lado dele). Serve a
    altura pedida ou a de 1080 p, se a pedida for menor (o rascunho de 720 p lê do proxy de 1080 p)."""
    for a in dict.fromkeys([alt, ALTURA_PROXY]):
        if a < alt:
            continue
        saida = caminho_proxy(fonte, a)
        try:
            if saida.exists() and saida.with_suffix(".mov.pronto").read_text(encoding="utf-8").strip() == selo_proxy(fonte):
                return saida
        except OSError:
            pass
    return None


def _proxy(fonte: Path, img: dict, passos: list[Passo], feitas: set) -> Path:
    """A cópia do bruto na altura da saída, que os blocos recortam no lugar do 4K (`imagem.proxy`).

    Feita uma vez por bruto, ao lado dele (`proxy/`), e por isso uma vez por episódio: o longo e
    os curtos do mesmo dia leem a mesma. O bloco com `recorte` (o vertical tirado do quadro
    deitado) continua no 4K, porque o recorte é em pixel dele. Lê no hardware do Mac e escreve
    nele; a escala é a mesma do render (o `scale_vt` deu VMAF 89 contra o 4K escalado, esta 97,5).

    ponytail: bruto em pé ou HDR fica sem proxy — o render escala o em pé pela outra medida e
    converte o HDR, e o proxy de 8 bits perderia a curva. Fazer quando aparecer bruto assim."""
    if not fonte.exists():
        return fonte
    if not img.get("proxy"):
        # o proxy.py fez a cópia na entrada do episódio: lê dela. Sem ela, o bruto, como sempre.
        return proxy_pronto(fonte, img["altura"]) or fonte
    if not ff.tem_videotoolbox():
        return fonte
    s = ff.probe(fonte)
    alt = img["altura"]
    if s.retrato or s.hdr or s.altura <= alt:
        return fonte
    saida = caminho_proxy(fonte, alt)
    if saida not in feitas:
        feitas.add(saida)
        passos.append(Passo(f"proxy de {fonte.name}", [
            "ffmpeg", "-y", "-v", "error", "-hwaccel", "videotoolbox", "-i", str(fonte),
            "-map", "0:v:0", "-map", "0:a:0?", "-vf", f"scale=-2:{alt}",
            # o relógio do bruto, quadro a quadro: a janela do plano cai no mesmo quadro nos dois.
            # Sem o `enc_time_base` o proxy saía em 1/30000 e o bruto do iPhone é 1/600: o quadro
            # que o fps=30 repete caía um quadro antes, e o vídeo andava 33 ms fora do 4K
            "-fps_mode", "passthrough", "-enc_time_base:v", "demux", "-c:v", ff.CODEC_HW, "-q:v", ff.QUALIDADES_HW["proxy"],
            "-pix_fmt", ff.PIX_FMT, "-g", str(ff.GOP), "-c:a", "copy", str(saida)],
            saida, [fonte], sobre=s.duracao))
    return saida


def _suave_no_bloco(e: es.Estilo, b: dict, voz) -> bool:
    """O bloco leva corte suave? Só o talking head: o bloco mudo (b-roll, abertura) e o de voz gravada
    à parte não têm a fala do bruto para emendar."""
    return bool(e.eixos["corte"].get("suave") and not b.get("mudo") and not voz)


def _suave_linhas(plano: dict, e: es.Estilo, trechos: list[dict]) -> list[str]:
    """O que o `--seco` mostra do corte suave: o interpolador existe aqui? e em quais emendas liga.
    Mede a diferença A×B no ponto nominal quando o bruto está na máquina (a execução ainda procura o
    melhor ponto em ±3 quadros, então a medida do render pode ser um pouco menor)."""
    if not e.eixos["corte"].get("suave"):
        return []
    ok, porque = corte_suave.suporte()
    fps = e.eixos["imagem"]["fps"]
    linhas = ["suave    ligado · interpolador " + ("disponível" if ok else
              f"ausente ({porque}): a emenda fica seca, com zoom e ruído de sala")]

    def olha(nome: str, fonte: Path, janelas: list, recorte=None) -> None:
        edl = {"sources": {"bruto": str(fonte)},
               "ranges": [{"source": "bruto", "start": float(j[0]), "end": float(j[1]),
                           **({"congela": j[2]} if len(j) > 2 and j[2] else {}),
                           **({"velocidade": j[3]} if len(j) > 3 and j[3] != 1 else {}),
                           **({"recorte": recorte} if recorte else {})} for j in janelas]}
        cand = corte_suave.candidatas(edl)
        if not cand:
            linhas.append(f"         {nome}: nenhuma emenda de fala")
        elif not fonte.exists():
            linhas.append(f"         {nome}: {len(cand)} emendas (bruto fora da máquina: não medi)")
        else:
            ems = corte_suave.planeja(edl, lambda p: p, fps=fps, busca=0)
            def marca(m):
                return f"{m.fim:.1f}s ({m.dif:.1f})"
            liga = [marca(m) for m in ems if m.suave]
            seca = [marca(m) for m in ems if not m.suave]
            linhas.append(f"         {nome}: {len(ems)} emendas · suave em {', '.join(liga) or '—'}"
                          + (f" · seca em {', '.join(seca)}" if seca else ""))

    if plano.get("blocos"):
        for b in plano["blocos"]:
            if b.get("janelas") and not b.get("pronto") and _suave_no_bloco(e, b, b.get("voz")):
                olha(b["nome"], _rel(plano, b.get("fonte") or plano["fonte"]), b["janelas"], b.get("recorte"))
    elif plano.get("fonte") and e.bruto != "avatar" and len(trechos) > 1:
        olha(Path(plano["fonte"]).stem, Path(plano["fonte"]),
             [[t["start"], t["end"]] for t in trechos])
    return linhas


def _lado_da_peca(item: dict) -> int:
    """-1 / +1: a peça ocupa o lado esquerdo / direito do quadro, e o rosto cede o outro. 0: o quadro todo,
    o meio, ou uma peça que não diz onde fica (então não empurra ninguém)."""
    q = item.get("q") or {}
    if not isinstance(q, dict):
        return 0

    def sinal(v) -> int:
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0
        return -1 if v < -100 else 1 if v > 100 else 0

    peca = item.get("peca")
    if peca in ("g_letreiro", "e_carimbo"):
        return sinal(q.get("x"))
    if peca == "g_traduz":
        return {"esq": -1, "dir": 1}.get(q.get("lado"), 0)
    if peca == "k_frase":
        return {"terco-esq": -1, "terco-dir": 1}.get(q.get("lugar"), 0)
    if peca == "l_promos":
        xs = [float(i.split("|")[2]) for i in str(q.get("it", "")).split(";") if i.count("|") >= 2]
        return sinal(sum(xs) / len(xs)) if xs else 0
    return 0


def _lados_das_pecas(brolls: list) -> list[list]:
    """[[t0, t1, lado]] das peças do plano do bloco que ficam num lado (tempo em segundos)."""
    out = []
    for x in brolls:
        try:
            a, z = float(x["t0"]), float(x["t1"])
        except (KeyError, TypeError, ValueError):
            continue
        if lado := _lado_da_peca(x):
            out.append([a, z, lado])
    return out


def _recorte(plano: dict, e: es.Estilo, b: dict, tb: Path, trabalho: Path,
             feitas: set, rascunho: bool = False) -> tuple[list[Passo], Path, float]:
    """O bloco que sai de janelas do bruto: um EDL só dele, pelo mesmo render.

    A voz é isolada uma vez para o bruto inteiro (`feitas` guarda), e todo
    recorte lê a fonte limpa — isolar janela por janela pagaria o serviço de novo.
    """
    img, passos = e.eixos["imagem"], []
    fonte = _rel(plano, b.get("fonte") or plano["fonte"])
    janelas = b["janelas"]
    if b.get("fonte") and e.eixos["voz"]["tratamento"] == "isola":
        raise ValueError(f"bloco {b['nome']}: a voz isolada é a do bruto do plano; "
                         f"bloco com `fonte` própria não isola")
    if not b.get("recorte") and e.eixos["voz"]["tratamento"] != "isola":
        fonte = _proxy(fonte, img, passos, feitas)
    voz = _rel(plano, b["voz"]) if b.get("voz") else None
    if voz:
        # Bloco de voz gravada à parte: a imagem dura o que a fala dura, a
        # partir do início da primeira janela.
        a0 = float(janelas[0][0])
        janelas = [[a0, round(a0 + ff.dur(voz) + FOLGA_VOZ, 3)]]
    if e.eixos["voz"]["tratamento"] == "isola":
        isolada = _fonte_isolada(trabalho)
        if isolada not in feitas:
            feitas.add(isolada)
            passos.append(Passo("isola a voz", [PY, str(AQUI / "isola_voz.py"), str(fonte),
                                                "-o", str(isolada)], isolada, [fonte]))
        fonte = isolada
    doc = {"version": 1, "sources": {"bruto": str(fonte)},
           "ranges": [{"source": "bruto", "start": j[0], "end": j[1],
                       **({"congela": j[2]} if len(j) > 2 and j[2] else {}),
                       **({"velocidade": j[3]} if len(j) > 3 and j[3] != 1 else {}),
                       **({"recorte": b["recorte"]} if b.get("recorte") else {})} for j in janelas],
           "grade": e.eixos["graduacao"]["preset"], "overlays": [],
           "total_duration_s": round(sum(_dura(j) for j in janelas), 2)}
    if _suave_no_bloco(e, b, voz):
        doc["corte_suave"] = True
        if b.get("plano"):
            # onde as peças do bloco ocupam o quadro: o zoom do corte suave empurra o rosto pro outro lado
            bp = _rel(plano, b["plano"])
            lados = _lados_das_pecas(json.loads(bp.read_text(encoding="utf-8")).get("brolls") or []) if bp.exists() else []
            if lados:
                doc["zoom_lados"] = lados
        if b.get("zoom_motivo"):
            # as jogadas decisivas do bloco: o zoom empurra devagar até elas (corte_suave.motivos_do)
            doc["zoom_motivo"] = b["zoom_motivo"]
        if b.get("zoom_degraus"):
            # empurrões centrados e seguidos (o gancho dos três nomes): corte_suave.degraus_do
            doc["zoom_degraus"] = b["zoom_degraus"]
    texto = json.dumps(doc, ensure_ascii=False, indent=2)
    base, edl = tb / "trecho.mp4", tb / "edl.json"
    # O volume é do vídeo inteiro, não do bloco: normalizado sozinho, um bloco
    # sem fala subia o resto de conversa 26 dB e virava ruído. Quem acerta o
    # episódio é o `normalizar` (ou a cama de trilha) depois da emenda.
    cmd = [PY, str(AQUI / "render.py"), str(edl), "-o", str(base),
           "--height", str(img["altura"]), "--fps", str(img["fps"]), "--no-loudnorm"]
    if rascunho:
        cmd.append("--draft")       # 720 p (1280 no vertical), qualidade de rascunho, sem a emenda suave
    # `voz.por_bloco`: a fala do próprio bloco passa pela mesma cadeia da voz gravada à parte
    # (trata_voz) e sai no mesmo nível. No longo do semanal cada bloco vinha de um microfone
    # (casa, loja, fone) e a cama da trilha passava por cima dos mais baixos.
    nivela = not (b.get("mudo") or voz) and e.eixos["voz"].get("por_bloco")
    if b.get("mudo") or voz:
        cmd.append("--mudo")
    elif e.eixos["voz"]["tratamento"] == "realce" and not nivela:
        cmd.append("--voice-enhance")
    dur = doc["total_duration_s"]
    if voz and e.eixos["voz"]["tratamento"] == "cru":
        # Voz sintética já chega limpa e no nível, como no `_preparo_avatar`: a
        # cadeia do microfone por cima trataria o que não tem ruído.
        tratada = voz
    elif voz:
        tratada = tb / "voz.wav"
        passos.append(Passo(f"{b['nome']}: trata a voz",
                            [PY, str(AQUI / "trata_voz.py"), str(voz), "-o", str(tratada)],
                            tratada, [voz]))
    passos.append(Passo(f"{b['nome']}: recorte", cmd, base, [fonte], extra=texto,
                        arquivo=(edl, texto), sobre=dur))
    if nivela:
        tratada = tb / "voz.wav"
        # `voz_alvo` no bloco: o celular longe da boca (a mesa do semanal) sai do rnnoise 5 dB abaixo
        # dos outros com o alvo padrão; o alvo desse bloco sobe até a fala bater com a dos vizinhos
        alvo = ["--alvo", str(b["voz_alvo"])] if b.get("voz_alvo") else []
        passos.append(Passo(f"{b['nome']}: trata a voz",
                            [PY, str(AQUI / "trata_voz.py"), str(base), *alvo, "-o", str(tratada)],
                            tratada, [base]))
    if voz or nivela:
        com_voz = tb / "trecho_voz.mp4"
        passos.append(Passo(f"{b['nome']}: voz do bloco",
                            [PY, str(AQUI / "poe_voz.py"), str(base), str(tratada),
                             "-o", str(com_voz)], com_voz, [base, tratada], sobre=dur))
        base = com_voz
    return passos, base, dur


def _fala_do_bloco(plano: dict, b: dict) -> Path | None:
    """A transcrição do bruto do bloco: `transcript` no bloco, ou a pasta `transcricoes` do plano
    com o nome do bruto (IMG_3644.MOV → IMG_3644.json)."""
    if b.get("transcript"):
        return _rel(plano, b["transcript"])
    if plano.get("transcricoes") and (b.get("fonte") or plano.get("fonte")):
        t = _rel(plano, plano["transcricoes"]) / (Path(b.get("fonte") or plano["fonte"]).stem + ".json")
        if not t.exists():
            raise ValueError(f"bloco {b.get('nome', '?')}: a transcrição {t} não existe")
        return t
    return None


def _ancorado(obj, fala, nome: str, onde: str, fim: float | None = None):
    """O `{âncora}` do plano trocado pelo segundo, ou o erro dizendo qual bloco e qual âncora."""
    if fala is None:
        raise ValueError(f"bloco {nome}: o plano tem âncora {{…}} e o bloco não tem transcrição "
                         f"(`transcript` no bloco ou `transcricoes` no plano)")
    palavras = tr.carrega(fala)["words"]
    try:
        return ancora.resolve(obj, palavras, fim)
    except ancora.Faltou as e:
        raise ValueError(f"bloco {nome}: {e} ({onde})") from None


def _blocos(plano: dict, e: es.Estilo, trabalho: Path,
            inicio: int) -> tuple[list[Passo], Path, bool]:
    """Cada bloco até o corte pronto dele, e os cortes emendados.

    Devolve (passos, corrente, completo). Incompleto = algum bloco ainda não foi
    gerado: a cadeia desse bloco para no portão e a emenda não entra.
    """
    img = e.eixos["imagem"]
    passos: list[Passo] = []
    cortes, falta, feitas = [], [], set()
    for b in plano["blocos"]:
        nome, tb = b["nome"], trabalho / b["nome"]
        if b.get("pronto"):
            cortes.append(_rel(plano, b["pronto"]))
            continue
        if b.get("janelas"):
            rec, base, dur = _recorte(plano, e, b, tb, trabalho, feitas)
            passos += rec
        elif not b.get("gerado"):
            if inicio <= ETAPAS.index("render"):
                preparo, _ = _preparo_avatar(
                    {**b, "fonte": str(_rel(plano, b["fonte"])),
                     "transcript": str(_rel(plano, b["transcript"])),
                     "creditos": plano.get("creditos"),
                     "look": b.get("look") or plano.get("look")}, e, tb)
                passos += [replace(p, nome=f"{nome}: {p.nome}") for p in preparo]
            falta.append(nome)
            continue
        else:
            gerado = [_rel(plano, g) for g in _lista(b["gerado"])]
            dur = sum(ff.dur(g) for g in gerado)
            base = gerado[0]
            if len(gerado) > 1:
                base = tb / "gerado.mp4"
                passos.append(Passo(f"{nome}: emenda do gerado",
                                    [PY, str(AQUI / "junta.py"), *map(str, gerado),
                                     "-o", str(base), "--fps", str(img["fps"])], base,
                                    gerado, sobre=dur))

        bp = _rel(plano, b["plano"]) if b.get("plano") else None
        doc = _direcao(json.loads(bp.read_text(encoding="utf-8")) if bp else {"cards": []},
                       bp.parent if bp else tb, e, nome)
        if ancora.tem(doc):
            # o plano do bloco cai na fala do próprio bloco: a transcrição do bruto no tempo do corte
            js = b.get("janelas") or []
            if b.get("voz") or not js or any((len(j) > 2 and j[2]) or (len(j) > 3 and j[3] != 1) for j in js):
                raise ValueError(f"bloco {nome}: âncora no plano do bloco só vale com janelas simples do "
                                 f"bruto (sem voz gravada à parte, sem gerado, sem congela nem velocidade); "
                                 f"aqui, use o segundo")
            trechos = [{"start": j[0], "end": j[1]} for j in js]
            fala = _fala_do_bloco(plano, b)
            no_bloco = tr.no_corte(fala, trechos)["words"] if fala else None
            doc = _ancorado(doc, no_bloco, nome, "no bloco", fim=dur)
        if b.get("vinheta"):
            # o jingle cantado abre o bloco; quem abaixa a cama embaixo dele é o _fala
            doc.setdefault("sons", []).append(
                {"arquivo": str(_rel(plano, b["vinheta"])), "t": 0.0, "ganho": 1.0})
        if b.get("receitas"):
            rec, base = _receitas(plano, b, base, doc, e, tb)
            passos += [replace(p, nome=f"{nome}: {p.nome}", sobre=dur) for p in rec]
        for item in doc.get("brolls") or []:
            if "peca" in item:
                passo = _peca(item, e, trabalho / "pecas")
                if passo.saida not in feitas:
                    feitas.add(passo.saida)
                    passos.append(passo)

        if doc.get("cor"):
            # a cor do próprio vídeo num trecho (o "antes e depois", o visual de filme): entra antes
            # das peças, que ficam por cima sem graduação, como o painel da referência
            cor = tb / "cor.mp4"
            passos.append(Passo(f"{nome}: cor por trecho",
                                [PY, str(AQUI / "grade.py"), str(base), "-o", str(cor),
                                 "--filter", grade.por_trecho(doc["cor"])], cor, [base],
                                toca=sum(float(c["t1"]) - float(c["t0"]) for c in doc["cor"]), sobre=dur))
            base = cor

        texto = json.dumps(doc, ensure_ascii=False, indent=1)
        pj, leg, corte = tb / "plano.json", tb / "legenda.mp4", tb / "corte.mp4"
        # O texto do plano entra na impressão, mas os arquivos que ele CITA não:
        # uma peça refeita no mesmo caminho passaria batida e o bloco sairia com
        # o painel velho.
        citados = [Path(x["arquivo"]) for x in doc.get("brolls") or []]
        sons = [*citados, *[Path(x["arquivo"]) for x in doc.get("cues_de") or []]]
        sons += [q.with_suffix(suf) for q in list(sons) for suf in (".json", ".cues.json")]
        sons += [Path(x["arquivo"]) for x in doc.get("sons") or [] if "arquivo" in x]
        sons.append(V2 / "sfx" / "sfx.json")
        passos.append(Passo(f"{nome}: legenda, peças e câmera",
                            [PY, str(AQUI / "captions_viral.py"), str(base), "--plan", str(pj),
                             "-o", str(leg)], leg, [base, *citados], extra=texto,
                            arquivo=(pj, texto), sobre=dur))
        som = [PY, str(AQUI / "som.py"), str(leg), "--plan", str(pj), "-o", str(corte),
               "--mestre", str(b.get("sfx_db", e.eixos["efeito"]["sfx_db"]))]   # `sfx_db` no bloco: efeito mais baixo onde a peça tem som e ele fala por cima
        if b.get("corta"):
            som += ["--corta", str(b["corta"])]
        passos.append(Passo(f"{nome}: som", som, corte, [leg, *sons], extra=texto, sobre=dur))
        cortes.append(corte)

    if falta:
        return passos, trabalho, False
    if len(cortes) == 1:
        return passos, cortes[0], True
    corrente = trabalho / "juntado.mp4"
    # junta.py e não `ffmpeg -f concat`: o HeyGen entrega a 25 fps, o projeto
    # roda a 30, e o concat mantém a taxa do primeiro arquivo.
    # `jl` no bloco = J/L-cut na emenda dele com o próximo (s; + J, − L): a fala entra antes da imagem, ou segue por cima dela
    jl = [float(b.get("jl") or 0) for b in plano["blocos"][:-1]]
    # `nivela_fala` no plano: a fala de cada bloco no mesmo nível (`nivela_fala.py`), depois da emenda e antes da trilha. O render
    # deixa cada bloco no nível do bruto, e o `por_bloco` (trata_voz) muda o som; aqui só entra ganho (27/10, ep. 7: 19 dB de pulo)
    # o estilo pode trazer o nivelador como padrão (`voz.nivela_fala`, o do longo do Tinteiro); a chave do plano manda, e `null` desliga
    nv = plano["nivela_fala"] if "nivela_fala" in plano else e.eixos["voz"].get("nivela_fala")
    if nv and any(jl):
        raise ValueError("`nivela_fala` não vale com J/L-cut (`jl`): o limite de cada bloco no áudio deixa de ser o do corte")
    emenda = trabalho / "emendado.mp4" if nv else corrente
    passos.append(Passo("emenda dos blocos",
                        [PY, str(AQUI / "junta.py"), *map(str, cortes), "-o", str(emenda),
                         "--fps", str(img["fps"]),
                         *(["--cortes", ",".join(map(str, jl))] if any(jl) else [])], emenda, cortes))
    if nv:
        mudos = ",".join("1" if (b.get("mudo") and not b.get("voz")) else "0" for b in plano["blocos"])
        botoes = nv if isinstance(nv, dict) else {}
        passos.append(Passo("nivela a fala por bloco",
                            [PY, str(AQUI / "nivela_fala.py"), str(emenda), "-o", str(corrente), "--cortes", *map(str, cortes),
                             "--mudos", mudos,
                             *[x for k in ("alvo", "forca", "faixa") if k in botoes for x in (f"--{k}", str(botoes[k]))]],
                            corrente, [emenda, *cortes]))
    return passos, corrente, True


def _rascunho(plano: dict, e: es.Estilo, trabalho: Path, seco: bool,
              sem_cache: bool, refaz=()) -> "Path | Seco":
    """O corte seco do plano em blocos, pro storyboard: 720 p, sem corte suave, sem peça, sem legenda, sem som
    de efeito, sem trilha e sem `por_bloco`. Cada bloco é um `render.py --draft` das janelas; a emenda é a
    mesma (J/L-cut), então o tempo do rascunho é o do final menos as peças. Mora em `<trabalho>/rascunho/`
    (o cache do final fica quieto) e não entrega nada: `rascunho/seco.mp4` é o vídeo da prévia do storyboard
    (`storyboard.py --rascunho plano.json saida`)."""
    img = e.eixos["imagem"]
    raiz = trabalho / "rascunho"
    passos, cortes, jl, feitas, fora = [], [], [], set(), []
    for b in plano["blocos"]:
        if b.get("pronto") or not b.get("janelas"):
            fora.append(b["nome"])          # gerado, pronto: não nasce de janelas do bruto
            continue
        rec, base, _ = _recorte(plano, e, b, raiz / b["nome"], raiz, feitas, rascunho=True)
        passos += rec
        cortes.append(base)
        jl.append(float(b.get("jl") or 0))
    if not cortes:
        raise ValueError("--rascunho: nenhum bloco com `janelas` neste plano")
    saida = raiz / "seco.mp4"
    cortes_jl = jl[:-1]
    if len(cortes) == 1:
        passos.append(Passo("rascunho: copia", ["ffmpeg", "-y", "-v", "error", "-i", str(cortes[0]), "-c", "copy", str(saida)],
                            saida, cortes))
    else:
        passos.append(Passo("rascunho: emenda dos blocos",
                            [PY, str(AQUI / "junta.py"), *map(str, cortes), "-o", str(saida), "--fps", str(img["fps"]),
                             *(["--cortes", ",".join(map(str, cortes_jl))] if any(cortes_jl) else [])], saida, cortes))
    if fora:
        print(f"rascunho: fora do corte seco (sem janelas): {', '.join(fora)}", flush=True)
    dur = sum(_dura(j) for b in plano["blocos"] if b.get("janelas") and not b.get("pronto") for j in b["janelas"])
    if seco:
        if not sem_cache:
            passos = [replace(p, pulavel=ja_feito(p) and not _do_bloco(p, refaz)) for p in passos]
        return Seco(estilo=e, edl=[], passos=passos, final=saida, duracao=dur,
                    pulados=[p.nome for p in passos if p.pulavel])
    raiz.mkdir(parents=True, exist_ok=True)
    _esquece_blocos(passos, refaz)
    pulados = _executa(passos, sem_cache, int(plano.get("paralelo") or PARALELO), dur)
    if pulados:
        print(f"pulados por já existirem: {', '.join(pulados)}")
    print(f"rascunho pronto: {saida}")
    return saida


def _reel():
    """Import tardio, como o `_v2`: o reel editorial desenha com tools/v2, que o kit não leva."""
    import reel_editorial
    return reel_editorial


def _args_cama(e: es.Estilo) -> list[str]:
    """Os botões da cama que o estilo mudou, em flags do mixa. O que é None fica no padrão dele."""
    t, args = e.eixos["trilha"], []
    for botao, flag in (("cama", "--cama"), ("duck", "--duck-ratio"), ("fade_fim", "--fade-fim"),
                          ("duck_limiar", "--duck-limiar"), ("duck_solta", "--duck-solta")):
        if t[botao] is not None:
            args += [flag, str(t[botao])]
    return args


# Em que etapa cada passo do reel editorial mora: é o que faz o `--desde` valer aqui também.
ETAPA_EDITORIAL = {"take": "render", "pessoa": "render", "camadas": "desenho", "pecas": "desenho",
                   "compor": "composicao", "junta": "composicao", "degraus": "composicao", "som": "trilha",
                   "yt": "trilha",
                   "capa": "entrega", "folha": "entrega"}


def _editorial(plano: dict, e: es.Estilo, trabalho: Path,
               inicio: int) -> tuple[list[Passo], Path | None]:
    """O reel editorial (o molde do Nick, a peça e_editorial): voz sintética, avatar no cartão ou
    cheio sobre o escritório, painel e peças por cima. Quem monta é o `reel_editorial.py`; aqui
    entra o que é do estilo, a conferência das regras e a ordem dos passos.

    O que custa dinheiro não roda: a voz e o avatar faltando viram passo que cobra, impresso
    com o comando, e a cadeia para ali."""
    re_ = _reel()
    img, tr = e.eixos["imagem"], e.eixos["trilha"]
    raiz = AQUI.parents[2]
    doc = {**plano, "_dir": str(Path(plano.get("_dir", ".")).resolve()),
           "trilha": {"faixa": tr["faixa"], "pedacos": tr["pedacos"]},
           "_estilo": {"nome": e.nome, "fundo": img["fundo"] and str(raiz / img["fundo"]), "costura": img["costura"],
                       "legenda_ig": e.eixos["desenho"]["legenda_ig"], "sintese": e.eixos["voz"]["sintese"],
                       # só quem declara zona (ou tema que não é o claro) leva: a impressão dos outros reels não muda
                       **{k: e.eixos["desenho"][k] for k in ("zona", "botoes") if e.eixos["desenho"][k]},
                       **({"tema": e.eixos["desenho"]["tema"]} if e.eixos["desenho"]["tema"] != "claro" else {}),
                       **({"atras": True} if e.eixos["desenho"]["atras"] else {}),
                       "alvo": e.eixos["voz"]["alvo"], "sfx_db": e.eixos["efeito"]["sfx_db"],
                       "mixa": _args_cama(e)}}
    if (plano.get("avatar") or {}).get("alinha"):
        # o webm que chegou pronto: o mapa sai do áudio dele (o passo `alinha`), não do passo heygen
        doc["avatar"] = {**plano["avatar"], "mapa": str(trabalho / "mapa.json")}
    erros = re_.confere(doc)
    if erros:
        raise ValueError("o reel editorial reprovou antes do render:\n  " + "\n  ".join(erros))

    pj = trabalho / "reel.json"
    texto = json.dumps(doc, ensure_ascii=False, indent=1)
    helper = str(AQUI / "reel_editorial.py")
    rel = lambda c: _rel(plano, c)
    voz = rel(plano["fonte"])
    fala = Path(doc["_dir"]) / "transcripts" / f"{voz.stem}.json"
    # sem trecho de rosto (o Reel todo tela), não há webm pra ler nem HeyGen pra pedir
    rosto = any("avatar" in s for s in plano["base"])
    av = plano.get("avatar") or {}
    webms = [rel(av["arquivo"])] if rosto else []
    mapa = [rel(doc["avatar"]["mapa"])] if (doc.get("avatar") or {}).get("mapa") else []
    fim_yt = Path(doc["_dir"]) / "vozes" / "fim-yt.wav"

    def passo(nome: str, saida: Path, entradas=(), chaves=(), **kw) -> Passo:
        # Cada passo leva na impressão só o pedaço do plano que ele lê: trocar um
        # som não refaz o take. O reel.json inteiro chega pelo `arquivo`.
        extra = json.dumps({k: doc.get(k) for k in (*chaves, "_estilo")}, ensure_ascii=False, sort_keys=True)
        return Passo(nome, [PY, helper, nome, str(trabalho)], saida, [*entradas], extra=extra,
                     arquivo=(pj, texto), **kw)

    def cobra(nome: str, quem: str, cmd: list[str], saida: Path) -> Passo:
        return Passo(nome, cmd, saida, arquivo=(pj, texto), cobra=quem, custo_fixo=0.0, toca=0.0)

    # O material é da pasta do vídeo, não do trabalho. A captura e o avatar saem quando faltam;
    # a transcrição segue a voz.
    passos: list[Passo] = []
    if not voz.exists():
        return [cobra("narração", "ElevenLabs", [PY, helper, "voz", str(trabalho)], voz)], None
    falta = [c for c in re_.capturas(doc) if not c.exists()]
    if falta:
        passos.append(passo("captura", falta[0], custo_fixo=30.0))
    passos.append(_transcricao(voz, fala))
    if webms and not webms[0].exists():
        geracao = Path(doc["_dir"]) / "avatar" / "geracao.wav"
        passos.append(passo("heygen", geracao, [voz], ("base", "dur"), custo_fixo=2.0))
        # quem gera é o agente, pelo MCP da HeyGen (créditos do plano), com o sim do usuário: skill fabrica-clone
        passos.append(cobra("avatar", "HeyGen", ["MCP da HeyGen (fabrica-clone):", str(geracao), "->", str(webms[0])],
                            webms[0]))
        return passos, None
    if webms and av.get("alinha"):
        passos.append(passo("alinha", mapa[0], [voz, *webms], ("base", "avatar", "dur"), custo_fixo=2.0))
    yt = plano.get("youtube")
    if yt and not fim_yt.exists():
        passos.append(cobra("frase do YouTube", "ElevenLabs", [PY, helper, "yt_voz", str(trabalho)], fim_yt))
    elif yt:
        passos.append(_transcricao(fim_yt, fala.parent / f"{fim_yt.stem}.json"))

    t = trabalho
    cenas = [rel(s.get("cena") or s["divide"]) for s in plano["base"] if "cena" in s or "divide" in s]
    # o cenário gerado atrás do rosto (`fundo` que é arquivo): trocar o arquivo refaz o take
    cenas += [rel(s["fundo"][1:]) for s in plano["base"] if str(s.get("fundo", "")).startswith("@")]
    faixa = [] if tr["faixa"] == re_.SEM_TRILHA else [re_.faixa_de(tr["faixa"])]
    # o que as peças e as imagens citam: recapturar uma página refaz a peça que a mostra
    citados = [rel(v[1:]) for x in plano.get("pecas", []) for v in (x.get("q") or {}).values()
               if isinstance(v, str) and v.startswith("@") and not v.startswith("@foco:")]
    citados += [rel(x["arquivo"]) for x in plano.get("imagens", [])]
    citados += [Path(doc["_dir"]) / "_trabalho" / "cap" / "focos.json"] if "@foco:" in json.dumps(plano.get("pecas")) else []
    capa = []
    if plano.get("capa"):
        # A foto, o logo e os lados que são arquivo: trocar a foto mantendo o nome refaz a capa.
        # `@x` é da pasta do vídeo; o resto, se for arquivo, é da pasta da peça.
        c = plano["capa"]
        foto = c.get("foto")
        arqs = [rel(foto[0] if isinstance(foto, list) else foto)] if foto else []    # [vídeo, t]: o quadro dele
        arqs += [rel(c["cena"][0])] if c.get("cena") else []
        for v in [c.get("logo", ""), *c.get("lados", "").split(",")]:
            arqs += [rel(v[1:])] if v.startswith("@") else [V2 / "pecas" / v] if v and (V2 / "pecas" / v).is_file() else []
        capa = [passo("capa", t / "capa-nick.jpg", arqs, chaves=("capa",), custo_fixo=15.0)]
    render = [
        passo("take", t / "take.mp4", [*webms, *mapa, *[Path(f) for f in [doc["_estilo"]["fundo"]] if f], *cenas],
              ("base", "avatar", "dur")),
        # com `recorte`, a pessoa é o Vision sobre o próprio take: refaz quando o take muda
        passo("pessoa", t / "pessoa.mov", [*webms, *mapa, *([t / "take.mp4"] if doc.get("recorte") else [])],
              ("base", "avatar", "dur", *(("recorte",) if doc.get("recorte") else ()))),
        # as peças entram: o `empurra` da câmera sai da hora de cada uma
        passo("camadas", t / "ed.json", [voz, fala], ("r", "css", "junta", "dur", "pecas")),
        # a capa antes das peças: a que mostra a capa no vídeo (o r_capa) cita o arquivo dela
        *capa,
        passo("pecas", t / "pecas.json", [voz, *citados], ("pecas",), custo_fixo=10.0 * len(plano.get("pecas", []))),
        passo("compor", t / "composto.mp4", [t / "take.mp4", t / "pessoa.mov", t / "ed.json"]),
        passo("junta", t / "imagem_voz.mp4", [t / "composto.mp4", t / "pecas.json", voz, *citados],
              ("imagens", "pecas", "dur")),
    ]
    imagem = t / "imagem_voz.mp4"
    if plano.get("degraus"):
        # o mesmo take com 0, 1… N skills, montado nas trocas: refaz se o take, a voz ou as peças mudaram
        imagem = t / "imagem_degraus.mp4"
        render.append(passo("degraus", imagem, [t / "imagem_voz.mp4", t / "pecas.json", *webms, *mapa, voz, fala],
                            ("degraus", "base", "avatar", "r", "pecas", "imagens", "dur", "junta", "css")))
    render.append(passo("som", t / "final.mp4", [imagem, voz, *faixa], ("sons", "trilha", "dur", "fechos")))
    if yt and fim_yt.exists():
        render.append(passo("yt", t / "final-yt.mp4", [t / "imagem_voz.mp4", voz, fim_yt, fala, *faixa],
                            ("youtube", "sons", "trilha", "dur", "junta")))
    render.append(passo("folha", t / "folha-1fps.png", [t / "final.mp4"], custo_fixo=5.0))
    passos += [p for p in render if ETAPAS.index(ETAPA_EDITORIAL[p.nome]) >= inicio]
    return passos, t / "final.mp4"


def _do_modulo(helper: str):
    """Import tardio de um helper que vem num módulo (o ZIP de um order bump): sem ele, a frase que
    diz onde achar, e não o ModuleNotFoundError no meio da cadeia."""
    if not (AQUI / f"{helper}.py").exists():
        raise FileNotFoundError(f"{helper}.py {MODULO}")
    return importlib.import_module(helper)


MODULO = ("não veio neste pacote: o da voz e do avatar vem no módulo Clone de IA, o das cenas no "
          "Cenas de Cinema, o do vídeo longo e da aula no YouTube Completo (o AGENTS.md diz como instalar)")

# O estilo que vem num módulo, pelo helper que diz que o módulo está na pasta. Vale pra quem herda (o
# estilo da marca do aluno que herda o video-longo também pede o YouTube Completo). A aula narrada é a
# voz clonada sobre a tela: pede o Clone de IA também. O seco mostra a cadeia assim mesmo.
DO_MODULO = {"video-longo": ["youtube"], "aula-fabrica": ["youtube"], "aula-narrada": ["youtube", "narra"]}


def pede_modulo(nome: str) -> list[str]:
    """Os helpers de módulo que o estilo pede (nome.py), subindo a herança até achar um estilo de
    módulo. No kit de aulas do CCnP, que não leva tools/v2, a aula é o produto: lá não há módulo."""
    while V2.exists() and nome in es.ESTILOS:
        if nome in DO_MODULO:
            return [f"{h}.py" for h in DO_MODULO[nome]]
        nome = es.ESTILOS[nome].get("herda")
    return []


def _cr():
    """Import tardio, como o `_reel`: só o criativo precisa do acabamento de filmagem achada."""
    return _do_modulo("criativo")


# Em que etapa cada passo do criativo mora: é o que faz o `--desde` valer aqui também.
ETAPA_CRIATIVO = {"base": "render", "cards": "desenho", "legenda": "desenho"}


def _cenas_do_lote(plano: dict) -> Passo | None:
    """As cenas do `lote` do plano que ainda não estão no disco: saem da Higgsfield, custam, e viram
    passo que cobra, com a estimativa pela tabela. Quem gera é o `lote.py`, que pergunta o preço à
    API antes de gastar e põe a ficha de cada cena no cenas.json da pasta do lote."""
    if not plano.get("lote"):
        return None
    lote = _do_modulo("lote")
    arq = _rel(plano, plano["lote"]).resolve()
    lo = lote.ler(arq)
    erros = lote.confere(lo)
    if erros:
        raise ValueError("o lote reprovou antes de gerar:\n  " + "\n  ".join(erros))
    falta = lote.faltam(lo)
    if not falta:
        return None
    return Passo("cenas", [PY, str(AQUI / "lote.py"), str(arq), "--gera"], lo["_pasta"] / f"{falta[0]}.mp4",
                 cobra=f"Higgsfield, {len(lote.a_gerar(lo))} cenas, ~US$ {lote.estimativa(lo):.2f}",
                 custo_fixo=0.0, toca=0.0)


def _criativo(plano: dict, e: es.Estilo, trabalho: Path,
              inicio: int) -> tuple[list[Passo], Path | None]:
    """O criativo: voz em off sobre cenas do banco, cada cena no trecho da fala que ilustra. Quem
    monta é o `criativo.py`; aqui entra o que é do estilo e a ordem dos passos. A trilha é a cama
    da fábrica, depois da legenda.

    A voz e as cenas do `lote` custam dinheiro e não rodam: faltando, viram passo que cobra,
    impresso com o comando, e a cadeia para ali."""
    cr = _cr()
    des = e.eixos["desenho"]
    doc = {**plano, "_dir": str(Path(plano.get("_dir", ".")).resolve()),
           "_estilo": {"nome": e.nome, "fps": e.eixos["imagem"]["fps"], "sintese": e.eixos["voz"]["sintese"],
                       "ritmo": des["ritmo"], "layout": des["legenda_layout"],
                       **({"fonte": des["fonte"]} if des["fonte"] else {}),
                       **({"legenda": des["legenda"]} if des["legenda"] else {}),
                       # o kit sem a biblioteca fica com a cor padrão do captions_viral
                       "acento": _v2().token(des["destaque"], des["tema"]) if V2.exists() else None}}
    pj = trabalho / "criativo.json"
    texto = json.dumps(doc, ensure_ascii=False, indent=1)
    helper = str(AQUI / "criativo.py")
    voz, fala, t = cr.fonte(doc), cr.transcript(doc), trabalho
    narracao = Passo("narração", [PY, helper, "voz", str(t)], voz, arquivo=(pj, texto),
                     cobra="ElevenLabs", custo_fixo=0.0, toca=0.0)

    # A cena nova é a primeira coisa que custa: sem ela o banco não tem o que conferir. O seco
    # mostra também a voz, se faltar, pra o custo inteiro aparecer de uma vez.
    cenas = _cenas_do_lote(plano)
    if cenas:
        return [cenas, *([] if voz.exists() else [narracao])], None
    erros = cr.confere(doc)
    if erros:
        raise ValueError("o criativo reprovou antes do render:\n  " + "\n  ".join(erros))

    def passo(nome: str, saida: Path, entradas=(), chaves=()) -> Passo:
        # Cada passo leva na impressão só o pedaço do plano que ele lê: trocar a palavra do
        # "comenta" não refaz as cenas. O criativo.json inteiro chega pelo `arquivo`.
        extra = json.dumps({k: doc.get(k) for k in (*chaves, "_estilo")}, ensure_ascii=False, sort_keys=True)
        return Passo(nome, [PY, helper, nome, str(t)], saida, [*entradas], extra=extra, arquivo=(pj, texto))

    if not voz.exists():
        return [narracao], None
    # A transcrição de outro caminho é do usuário; o confere já cobrou que ela exista.
    passos = [p for p in [_transcricao(voz, fala)] if p]
    # O acabamento de cada cena mora na base: ele é guardado no banco, por nome, e só roda na
    # cena que ainda não tem. Num passo à parte, a lista dele ficava abaixo do piso da impressão.
    render = [passo("base", t / "base.mp4", [voz, fala, *cr.brutas(doc), AQUI / "filmagem_achada.py"],
                    ("banco", "trechos", "cor", "zona"))]
    if e.tem("legenda"):
        render += [
            passo("cards", t / "legenda.json", [fala, AQUI / "cards_da_fala.py"], ("trechos", "punch", "funde")),
            Passo("legenda", [PY, str(AQUI / "captions_viral.py"), str(t / "base.mp4"),
                              "--plan", str(t / "legenda.json"), "-o", str(t / "legendado.mp4")],
                  t / "legendado.mp4", [t / "base.mp4", t / "legenda.json"]),
        ]
    passos += [p for p in render if ETAPAS.index(ETAPA_CRIATIVO[p.nome]) >= inicio]
    return passos, render[-1].saida


# As composições que montam a cadeia inteira por conta própria: o estilo diz qual, a fábrica só
# agenda, guarda e entrega. Composição nova é uma linha aqui, não mais um `if` no _cadeia.
COMPOSICOES = {"editorial": _editorial, "cenas": _criativo}


def _entregas(plano: dict, e: es.Estilo, final: Path, trabalho: Path) -> list[tuple[Path | None, Path]]:
    """O que sai da área de trabalho, e para onde. O `None` é o que a cadeia produziu por último.

    O reel editorial entrega o final, um final por fecho (`-<nome>`), a versão do YouTube ao lado
    dele e a capa na pasta do vídeo, onde a agenda do YouTube e a do Instagram vão buscar."""
    saidas: list[tuple[Path | None, Path]] = [(None, final)]
    if e.eixos["imagem"]["composicao"] == "editorial":
        # um final por fecho, ao lado do principal (que é o primeiro deles)
        for nome in plano.get("fechos") or {}:
            saidas.append((trabalho / f"final-{nome}.mp4", final.with_name(f"{final.stem}-{nome}.mp4")))
        if plano.get("youtube"):
            saidas.append((trabalho / "final-yt.mp4", final.with_name(f"{final.stem}-yt.mp4")))
        if plano.get("capa"):
            saidas.append((trabalho / "capa-nick.jpg", final.parent / plano["slug"] / "capa-nick.jpg"))
    return saidas


# A chapa, em pixel da peça (1920x1080): o papel em volta da tela, e quanto o cartão que cobre a
# bolinha do OBS salta da janela pra direita e pra baixo.
CHAPA_MARGEM, CHAPA_SALTO = 25, (60, 10)


def chapa_geo(fw: int, fh: int, altura: int, bolinha: str | None = None,
              celular: tuple[int, int] | None = None) -> dict:
    """Onde a tela e o rosto caem no quadro 16:9 da chapa, em pixel de saída.

    `bolinha` é a câmera que o OBS gravou dentro da tela (`crop=w:h:x:y` no quadro da live): o
    cartão cobre ela inteira, e passa da janela pelo salto. `celular` é o tamanho do rosto do
    modo 2: a tela encosta à esquerda e o cartão vai na faixa da direita, sem cobrir nada dela
    (quatro de quatro alunos reclamaram da câmera em cima do conteúdo)."""
    H = altura // 2 * 2
    W = H * 16 // 9 // 2 * 2
    k = H / 1080
    m = round(CHAPA_MARGEM * k)
    jh = (H - 2 * m) // 2 * 2
    jw = round(jh * fw / fh / 2) * 2
    if jw > W - 2 * m:
        jw = (W - 2 * m) // 2 * 2
        jh = round(jw * fh / fw / 2) * 2
    jx, jy = ((W - jw) // 2 if not celular else m), (H - jh) // 2
    geo = {"W": W, "H": H, "jan": (jx, jy, jw, jh), "cam": None}
    if bolinha:
        bw, bh, bx, by = (float(v) for v in bolinha.removeprefix("crop=").split(":"))
        sx, sy = jw / fw, jh / fh
        x0, y0, x1, y1 = jx + bx * sx, jy + by * sy, jx + (bx + bw) * sx, jy + (by + bh) * sy
        dx, dy = (v * k for v in CHAPA_SALTO)
        aspecto = (x1 - x0) / (y1 - y0)
        # o cartão nasce da bolinha e cresce até o salto, sem mudar a proporção do rosto
        cw = math.ceil(max(x1 + dx - x0, (y1 + dy - y0) * aspecto) / 2) * 2
        ch = math.ceil(cw / aspecto / 2) * 2
        geo["cam"] = (math.floor(x1 + dx) - cw, math.floor(y1 + dy) - ch, cw, ch)
    elif celular:
        aspecto = celular[0] / celular[1]
        cw = (W - (jx + jw) - 2 * m) // 2 * 2
        ch = round(cw / aspecto / 2) * 2
        if ch > jh:
            ch = jh
            cw = round(ch * aspecto / 2) * 2
        # na faixa da direita, embaixo: a zona do rosto no 16:9
        geo["cam"] = (jx + jw + (W - jx - jw - cw) // 2, jy + jh - ch, cw, ch)
    return geo


def _tela_do(arq: Path) -> tuple[int, int]:
    """O tamanho em que o vídeo aparece: o celular grava deitado e marca a rotação à parte, e o
    ffmpeg gira na leitura. O ff.probe dá o tamanho gravado."""
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=width,height:stream_side_data=rotation", "-of", "json", str(arq)],
               capture=True, quiet=True)
    v = json.loads(r.stdout)["streams"][0]
    giro = abs(int(next((d.get("rotation", 0) for d in v.get("side_data_list", [])), 0))) % 180
    return (v["height"], v["width"]) if giro == 90 else (v["width"], v["height"])


def _offset(plano: dict, trabalho: Path, seco: bool) -> float:
    """O deslocamento do celular (obs = celular + offset): o do plano, ou o medido pela palma,
    guardado na pasta de trabalho pra não medir de novo a cada corrida."""
    if plano.get("offset") is not None:
        return float(plano["offset"])
    palma = _do_modulo("palma")
    obs, cel = Path(plano["fonte"]), Path(plano["celular"])
    chave = [str(obs), obs.stat().st_size, str(cel), cel.stat().st_size]
    guardado = trabalho / "palma.json"
    if guardado.exists():
        doc = json.loads(guardado.read_text(encoding="utf-8"))
        if doc.get("chave") == chave:
            return doc["offset"]
    r = palma.offset(obs, cel)
    print(f"palma: obs = celular {r['offset']:+.3f}s (pico {r['pico']}, palma {r['palma']}). "
          f"Pra fixar, escreva \"offset\": {r['offset']} no plano")
    if not seco:
        trabalho.mkdir(parents=True, exist_ok=True)
        guardado.write_text(json.dumps({**r, "chave": chave}), encoding="utf-8")
    return r["offset"]


def _camera(plano: dict, e: es.Estilo, trabalho: Path, trechos: list[dict], altura: int,
            seco: bool) -> Passo:
    """O celular cortado nos mesmos trechos da tela, deslocado pela palma, já na altura do
    cartão: a única escala é a da fonte pro cartão. Com `microfone: celular`, a voz vem dele."""
    cel = Path(plano["celular"])
    off = _offset(plano, trabalho, seco)
    dur = ff.probe(cel).duracao
    recorte = e.eixos["imagem"]["recorte"]
    ranges = []
    for i, t in enumerate(trechos):
        a, b = float(t["start"]) - off, float(t["end"]) - off
        if a < 0 or b > dur + 0.05:
            raise ValueError(f"o trecho {i} ({t['start']:.1f}→{t['end']:.1f} no OBS) cai fora do "
                             f"celular ({a:.1f}→{b:.1f}, o celular tem {dur:.1f}s): ajuste a janela")
        ranges.append({"source": "celular", "start": round(a, 3), "end": round(b, 3),
                       **({"recorte": recorte} if recorte else {})})
    doc = json.dumps({"version": 1, "sources": {"celular": str(cel)}, "ranges": ranges,
                      "grade": e.eixos["graduacao"]["preset"], "overlays": []}, ensure_ascii=False, indent=2)
    edl, saida = trabalho / "camera.json", trabalho / "camera.mp4"
    voz = plano.get("microfone") == "celular"
    # sem a voz, o corte é mudo, e silêncio não se normaliza (o loudnorm mede -inf e estoura)
    cmd = [PY, str(AQUI / "render.py"), str(edl), "-o", str(saida), "--height", str(altura),
           "--fps", str(e.eixos["imagem"]["fps"]),
           *(["--voice-enhance"] if voz else ["--mudo", "--no-loudnorm"])]
    return Passo("câmera", cmd, saida, [cel], extra=doc, arquivo=(edl, doc))


def _geo(plano: dict, e: es.Estilo) -> dict:
    """A geometria da chapa deste plano: a bolinha do OBS no bruto `live`, o celular no modo 2
    (com o `imagem.recorte`, se houver, como o pedaço do quadro dele que vai no cartão)."""
    img = e.eixos["imagem"]
    fw, fh = _tela_do(Path(plano["fonte"]))
    if e.bruto != "obs+celular":
        return chapa_geo(fw, fh, img["altura"], bolinha=img["recorte"])
    cel = (tuple(int(v) for v in img["recorte"].removeprefix("crop=").split(":")[:2])
           if img["recorte"] else _tela_do(Path(plano["celular"])))
    return chapa_geo(fw, fh, img["altura"], celular=cel)


def _chapa(plano: dict, e: es.Estilo, corrente: Path, trabalho: Path,
           camera: Path | None = None) -> tuple[list[Passo], Path]:
    """A tela numa janela sobre o papel, e o rosto num cartão. Por baixo vão a tela e o rosto,
    cada um no retângulo dele; por cima, a h_chapa, que é papel com os buracos e a borda e a
    sombra da marca. O explicador vem depois, sobre o quadro inteiro.

    O rosto é a bolinha que o OBS gravou (o `imagem.recorte`, no bruto `live`) ou o celular
    do modo 2, que já chega cortado e na altura do cartão (`camera`)."""
    img = e.eixos["imagem"]
    g = _geo(plano, e)
    fw, fh = _tela_do(Path(plano["fonte"]))
    k = g["H"] / 1080
    ret = lambda r: ",".join(f"{v / k:.2f}" for v in r)
    peca = _peca({"peca": "h_chapa", "q": {"jan": ret(g["jan"]),
                                           **({"cam": ret(g["cam"])} if g["cam"] else {})}},
                 e, trabalho / "pecas")
    jx, jy, jw, jh = g["jan"]
    tela = f"scale={jw}:{jh}:flags=lanczos,setsar=1,pad={g['W']}:{g['H']}:{jx}:{jy}"
    ins = ["-i", str(corrente), "-i", str(peca.saida)]
    if g["cam"] and camera:
        cx, cy, cw, ch = g["cam"]
        ins += ["-i", str(camera)]
        fc = (f"[0:v]{tela}[j];[2:v]scale={cw}:{ch}:flags=lanczos,setsar=1[r];"
              f"[j][r]overlay={cx}:{cy}:eof_action=repeat[a];")
    elif g["cam"]:
        cx, cy, cw, ch = g["cam"]
        # o recorte é medido no quadro da live: o vídeo volta às dimensões dela antes (ver _composicao)
        fc = (f"[0:v]split[t][c];[t]{tela}[j];"
              f"[c]scale={fw}:{fh},{img['recorte']},scale={cw}:{ch},setsar=1[r];"
              f"[j][r]overlay={cx}:{cy}[a];")
    else:
        fc = f"[0:v]{tela}[a];"
    fc += f"[1:v]scale={g['W']}:{g['H']}[m];[a][m]overlay=0:0:eof_action=repeat[v]"
    voz = "2:a" if camera and plano.get("microfone") == "celular" else "0:a"
    saida = trabalho / "com_chapa.mp4"
    return [peca, Passo("chapa", ["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", "[v]",
                                  "-map", voz, *ff.args_video(img["qualidade"]), "-c:a", "copy",
                                  str(saida)],
                        saida, [corrente, peca.saida, *([camera] if camera else [])])], saida


def _pontas(e: es.Estilo, corrente: Path, trabalho: Path) -> tuple[list[Passo], Path]:
    """A peça que abre e a que fecha, no tamanho do vídeo, com os sons dela, emendadas nas
    pontas pelo junta.py (que acerta o relógio de cada parte)."""
    ef, img = e.eixos["efeito"], e.eixos["imagem"]
    H = img["altura"] // 2 * 2
    W = H * 16 // 9 // 2 * 2 if not e.vertical else 1080
    passos, partes = [], {}
    for nome in ("abertura", "fecho"):
        pedido = ef[nome]
        if not isinstance(pedido, dict):
            continue
        # a peça sai no formato do vídeo: o t_marca nasce em pé, e esticado num 16:9 vira outra marca
        peca = _peca({"ar": "1080x1920" if e.vertical else "1920x1080", **pedido,
                      "q": dict(pedido.get("q") or {})}, e, trabalho / "pecas")
        parte = trabalho / f"{nome}.mp4"
        muda = trabalho / f"{nome}_muda.mp4" if ef["som"] else parte
        # o junta.py recusa parte sem faixa de áudio: a peça ganha silêncio, e os sons vêm depois
        passos += [peca, Passo(nome, [
            "ffmpeg", "-y", "-i", str(peca.saida), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-filter_complex", f"[0:v]scale={W}:{H}:flags=lanczos,setsar=1[v]", "-map", "[v]",
            "-map", "1:a", "-shortest", *ff.args_video(img["qualidade"], fps=img["fps"]),
            *ff.args_audio(), str(muda)], muda, [peca.saida], custo_fixo=3.0)]
        if ef["som"]:
            # os cues que a peça publicou soam a partir do 0; o t1 só precisa passar do fim dela
            plan = json.dumps({"brolls": [{"arquivo": str(peca.saida), "t0": 0.0, "t1": 1e6}]})
            pj = trabalho / f"{nome}.plano.json"
            passos.append(Passo(f"{nome}: som", [PY, str(AQUI / "som.py"), str(muda), "--plan", str(pj),
                                                 "-o", str(parte), "--mestre", str(ef["sfx_db"])],
                                parte, [muda, peca.saida.with_suffix(".json"), V2 / "sfx" / "sfx.json"],
                                extra=plan, arquivo=(pj, plan), custo_fixo=3.0))
        partes[nome] = parte
    saida = trabalho / "com_abertura.mp4"
    ordem = [p for p in (partes.get("abertura"), corrente, partes.get("fecho")) if p]
    passos.append(Passo("abertura e fecho", [PY, str(AQUI / "junta.py"), *map(str, ordem),
                                             "-o", str(saida), "--fps", str(img["fps"])],
                        saida, ordem))
    return passos, saida


MOTOR = "momentos"   # o recurso cujo motor vem na skill do estilo, não no tronco: o script tem o nome dele


def _motor_do_estilo(nome: str) -> Path | None:
    """O motor dos momentos do estilo: `.agents/skills/fabrica-<estilo>/scripts/momentos.py`.

    A skill de um estilo traz o motor dele; o tronco não conhece nenhum e o acha pelo nome do estilo,
    ou pelo de quem ele herda (um estilo da marca que herda de um módulo usa o motor do módulo).
    O nome do script sai da constante, não de um literal: `momentos.py` não é helper do tronco, e o
    `empacota_kit` cobra do pacote todo helper citado entre aspas."""
    skills = AQUI.parents[2] / ".agents" / "skills"
    while nome:
        achado = skills / f"fabrica-{nome}" / "scripts" / f"{MOTOR}.py"
        if achado.exists():
            return achado
        nome = es.ESTILOS.get(nome, {}).get("herda")
    return None


def _momentos(plano: dict, e: es.Estilo, corrente: Path, edl_path: Path, trabalho: Path,
              edl_texto: str = "") -> tuple[list[Passo], Path]:
    """Os momentos da fala, desenhados por cima do corte pelo motor da skill do estilo.

    O plano diz o quê (`momentos.lista`); o motor desenha no tempo da fala já cortada, e por isso
    recebe a transcrição e o EDL. Sem `momentos` no plano o passo não entra (o aviso de camada muda
    sai pelo `exige` do recurso)."""
    m = plano.get("momentos")
    if not (e.tem("momentos") and isinstance(m, dict) and m.get("lista")):
        return [], corrente
    motor = _motor_do_estilo(e.nome)
    if motor is None:
        raise FileNotFoundError(f"o estilo '{e.nome}' pede momentos e a skill dele não está em "
                                f".agents/skills (fabrica-{e.nome}/scripts/momentos.py)")
    if not plano.get("transcript"):
        raise ValueError("os momentos acendem na palavra dita: o plano precisa da transcrição. Deixe "
                         "só `fonte`, `estilo`, `slug` e `momentos` (a fábrica transcreve sozinha) "
                         "ou ponha o `transcript` dela")
    # `arquivos`: o que o plano entrega ao motor (a chapa de um assunto, por exemplo). O caminho vale
    # pela pasta do plano, como todo caminho dele, e o conteúdo entra na impressão
    arqs = {k: _rel(plano, v) for k, v in (m.get("arquivos") or {}).items()}
    for k, v in arqs.items():
        if not v.is_file():
            raise FileNotFoundError(f"momentos.arquivos.{k}: não achei {v} (o caminho vale a partir da pasta do plano)")
    m = {**m, "arquivos": {k: str(v) for k, v in arqs.items()}} if arqs else m
    pacote, saida = trabalho / "momentos.json", trabalho / "com_momentos.mp4"
    texto = json.dumps({"momentos": m, "transcript": plano["transcript"], "edl": str(edl_path)},
                       ensure_ascii=False, indent=1, sort_keys=True)
    # o que a página usa (motor, fontes, sons) entra na impressão: mexer nele refaz o desenho
    pecas = sorted(p for p in (motor.parent.parent / "assets").rglob("*") if p.is_file()) + list(arqs.values())
    duracao = json.loads(edl_texto)["total_duration_s"] if edl_texto else 0
    return [Passo("momentos", [PY, str(motor), "render", str(corrente), str(pacote), "-o", str(saida)],
                  saida, [corrente, edl_path, Path(plano["transcript"]), *pecas],
                  extra=texto, arquivo=(pacote, texto),
                  # uma foto da página por quadro: ~2,5 s por segundo de vídeo, mais a abertura do navegador
                  custo_fixo=15 + 2.5 * duracao, etapa="desenho")], saida


def _desde(cmds: list[Passo], inicio: int) -> list[Passo]:
    """O `--desde` corta uma vez, no fim: o passo de etapa anterior já está pronto no disco."""
    return [p for p in cmds if not p.etapa or ETAPAS.index(p.etapa) >= inicio]


def _visual(plano: dict, e: es.Estilo, vj: Path, corrente: Path, trabalho: Path,
            edl_texto: str) -> tuple[list[Passo], Path]:
    """Os dois passos do visual por batida: `acha o visual` (resolve as âncoras na fala cortada, confere a cobertura, busca
    print, logo e número, e cai na alternativa do que falhar) e `tela dividida` (monta a dividida e a cheia). O que o
    `decisoes.json` do storyboard tirou pelo número não entra."""
    import storyboard as sb
    doc = visual.le(vj)
    if any(isinstance(b.get(k), dict) for b in doc["batidas"] for k in ("t0", "t1")):
        if not plano.get("transcript") or not edl_texto:
            raise ValueError("o visual.json ancora em palavra dita e o plano não tem `transcript`")
        fala = trabalho / "fala_visual.json"
        fala.parent.mkdir(parents=True, exist_ok=True)
        fala.write_text(_fala_no_corte(Path(plano["transcript"]), json.loads(edl_texto)["ranges"]), encoding="utf-8")
        doc = visual.ancora(doc, tr.palavras(fala))
        if (erros := visual.valida(doc)):
            raise ValueError("o visual.json reprovou:\n  " + "\n  ".join(erros))
    resolvido, achados, saida = trabalho / "visual.resolvido.json", trabalho / "visual" / "achados.json", trabalho / "com_visual.mp4"
    texto = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True)
    dec = sb.pasta(plano) / "decisoes.json"
    passos = [Passo("acha o visual",
                    [PY, str(AQUI / "acha.py"), str(resolvido), "--trab", str(trabalho), "--video", str(corrente)],
                    achados, [corrente], extra=texto, arquivo=(resolvido, texto), etapa="desenho"),
              Passo("tela dividida",
                    [PY, str(AQUI / "tela_dividida.py"), str(corrente), "--visual", str(resolvido), "--achados", str(achados),
                     "--decisoes", str(dec), "--trab", str(trabalho / "tela_dividida"), "--saida", str(saida),
                     "--tema", e.eixos["desenho"]["tema"]],
                    saida, [corrente, achados, *([dec] if dec.exists() else [])], etapa="desenho")]
    return passos, saida


def _cadeia(plano: dict, e: es.Estilo, edl_path: Path, trabalho: Path,
            desde: str, edl_texto: str = "", seco: bool = False,
            rascunho: bool = False) -> tuple[list[Passo], Path]:
    """Monta a sequência de comandos. Nada executa aqui — é isso que deixa o modo
    seco existir sem um `if` espalhado por cada passo."""
    cmds: list[list[str]] = []
    img = e.eixos["imagem"]
    corrente = trabalho / "render.mp4"
    inicio = ETAPAS.index(desde)

    adaptador = COMPOSICOES.get(img["composicao"])
    if adaptador:
        return adaptador(plano, e, trabalho, inicio)

    legenda_feita = False
    dividida_json = None
    if plano.get("blocos"):
        blocos, corrente, completo = _blocos(plano, e, trabalho, inicio)
        cmds += blocos
        if not completo:
            return _desde(cmds, inicio), None
        legenda_feita = True          # entrou bloco a bloco, com o plano de cada um
    elif e.bruto == "avatar":
        # O adaptador de avatar substitui o render: o que produz imagem aqui é a
        # geração no HeyGen, que custa crédito e por isso não roda sozinha.
        limpo = trabalho / "voz_limpa.wav"
        preparo, limpo = _preparo_avatar(plano, e, trabalho)
        cmds += [replace(p, etapa="render") for p in preparo]
        gerado = [Path(p) for p in plano.get("gerado", [])]
        if gerado:
            corrente = trabalho / "juntado.mp4"
            # junta.py e não `ffmpeg -f concat`: o HeyGen entrega a 25 fps, o
            # projeto roda a 30, e o demultiplexador mantém a taxa do primeiro
            # arquivo sem reescrever o relógio. Em 19/09 um corte de 78s saiu
            # com 94s de imagem em cima de 70s de áudio.
            cmds.append(Passo("emenda dos blocos",
                              [PY, str(AQUI / "junta.py"), *[str(p) for p in gerado],
                               "-o", str(corrente), "--fps", str(img["fps"])],
                              corrente, gerado))
        else:
            # Sem os blocos gerados a cadeia para no portão, de propósito. A
            # fábrica não gera: ela prepara, mede e diz o que pedir.
            return _desde(cmds, inicio), None

    else:
        fonte = Path(plano["fonte"])
        if e.eixos["voz"]["tratamento"] == "isola":
            # O EDL já aponta para a fonte isolada (ver `fabrica`); aqui ela nasce.
            isolada = _fonte_isolada(trabalho)
            cmds.append(Passo("isola a voz", [PY, str(AQUI / "isola_voz.py"), str(fonte),
                                              "-o", str(isolada)], isolada, [fonte], etapa="render"))
            fonte = isolada
        render = [PY, str(AQUI / "render.py"), str(edl_path), "-o", str(corrente),
                  "--height", str(img["altura"]), "--fps", str(img["fps"])]
        if img["canvas"]:
            render += ["--canvas", img["canvas"]]
        # Voz isolada NÃO passa pelo realce: o afftdn dele (piso -25 dB) toma a
        # voz limpa por ruído e come o agudo (ver test_voz_isolada_entra_antes_do_render).
        # `voz.por_bloco` num bruto só: a mesma cadeia do microfone dele (rnnoise + EQ + compressor)
        # em vez do realce do render, que escurece a voz (medido na Aula 0: 2–5 kHz −5 dB).
        nivela = e.eixos["voz"]["tratamento"] == "realce" and e.eixos["voz"].get("por_bloco")
        if e.eixos["voz"]["tratamento"] == "realce" and not nivela:
            render.append("--voice-enhance")
        if e.tem("normalizar"):
            # A normalização sai daqui e vai para o fim da cadeia: os passos
            # seguintes mexem no som, e normalizar antes deles é medir uma coisa
            # e entregar outra.
            render.append("--no-loudnorm")
        if rascunho:
            render.append("--draft")        # o storyboard: 720 p, o mesmo corte do final
        cmds.append(Passo("render", render, corrente, [fonte],
                          extra=edl_texto, etapa="render"))
        if nivela:
            voz_tr, com_voz = trabalho / "voz.wav", trabalho / "render_voz.mp4"
            cmds.append(Passo("trata a voz", [PY, str(AQUI / "trata_voz.py"), str(corrente), "-o", str(voz_tr)],
                              voz_tr, [corrente], etapa="render"))
            cmds.append(Passo("voz do vídeo", [PY, str(AQUI / "poe_voz.py"), str(corrente), str(voz_tr),
                                               "-o", str(com_voz)], com_voz, [corrente, voz_tr], etapa="render"))
            corrente = com_voz

    # O modo 2: o celular cortado nos mesmos trechos, que a chapa põe no cartão.
    camera = None
    if e.bruto == "obs+celular" and edl_texto:
        camera = trabalho / "camera.mp4"
        # montar a câmera mede a palma nos dois brutos: com o --desde depois do render, nem monta
        if inicio <= ETAPAS.index("render"):
            cmds.append(replace(_camera(plano, e, trabalho, json.loads(edl_texto)["ranges"],
                                        _geo(plano, e)["cam"][3], seco), etapa="render"))

    # A chapa vem ANTES do explicador: a peça que toma a tela cobre o quadro inteiro, papel
    # incluído, e a que vai por cima mede a zona do rosto no 16:9 da saída, não no da gravação.
    if e.tem("chapa"):
        chapa, corrente = _chapa(plano, e, corrente, trabalho, camera)
        cmds += [replace(p, etapa="desenho") for p in chapa]

    # O visual por batida (visual.json): a tela dividida e a cheia, com o que a busca achou. Depois do corte e antes do
    # desenho; os trechos sem visual seguem como estão.
    if e.bruto == "camera" and e.eixos["imagem"]["composicao"] == "cheio" and (vj := _visual_json(plano)):
        vis, corrente = _visual(plano, e, vj, corrente, trabalho, edl_texto)
        cmds += [replace(p, etapa="desenho") for p in vis]
        dividida_json = trabalho / "tela_dividida" / "dividida.json"      # a legenda dos trechos `dividida` sobe acima do cabelo

    # A camada de desenho do vertical: cenas animadas ou cards fixos viram uma
    # composição HTML, que o hyperframes renderiza a vídeo. O plano pode trazer a
    # camada pronta em vez disso — é o que deixa refazer só o layout ser barato.
    camada = Path(plano["camada"]) if plano.get("camada") else None
    if camada is None and (plano.get("cenas") or plano.get("cards")):
        dirdesenho = Path(plano.get("dir_desenho") or (trabalho / "desenho"))
        gerador = "make_reel_v3.py" if plano.get("cenas") else "make_reel_v2.py"
        cfg = trabalho / "camada.json"
        cmds.append(Passo("composição do desenho",
                          [PY, str(AQUI / gerador), str(plano.get("transcript", "")),
                           str(edl_path), str(dirdesenho / "index.html"), str(cfg)],
                          dirdesenho / "index.html", [edl_path], extra=edl_texto, etapa="desenho"))
        cmds.append(Passo("render do desenho", ["npm", "run", "render"],
                          dirdesenho / "renders" / "camada.mp4",
                          [dirdesenho / "index.html"], etapa="desenho"))
        camada = dirdesenho / "renders" / "camada.mp4"

    if e.tem("explicador") and plano.get("overlays"):
        ov = trabalho / "overlays.json"
        saida = trabalho / "com_explicador.mp4"
        explica = [PY, str(AQUI / "lesson_overlays.py"), str(corrente),
                   str(edl_path), str(ov), "-o", str(saida)]
        # O explicador do tronco desenha com a biblioteca, no tema do estilo; o do
        # kit é o quadro-negro antigo, que não conhece a opção.
        pecas, colocadas = [], []
        # Sem o explicador na pasta (a aula vem no YouTube Completo), o seco mostra o passo sem as peças,
        # e o render recusa com a frase do MODULO, pelo helper que falta.
        if V2.exists() and (AQUI / "lesson_overlays.py").exists():
            explica += ["--tema", e.eixos["desenho"]["tema"]]
            # As peças são passos da fábrica, como as do bloco: o seco mostra, o lote renderiza,
            # e o explicador só as põe no lugar, recodificando a janela de cada uma.
            import lesson_overlays as lo
            edl = json.loads(edl_texto)
            des = e.eixos["desenho"]
            pip = des.get("pip")
            rosto_cache: dict = {}
            for lugar_ in lo.planeja(plano["overlays"], edl, des.get("leitura"), pip=bool(pip)):
                item = lugar_["item"]
                peca, pares, cheia = lo.traduz({**item, "dur": lugar_["dur"]})
                q = dict(x.split("=", 1) for x in pares)
                if lugar_["pip"]:
                    q["pip"] = "1"
                pecas.append(_peca({"peca": peca, "q": q, "ar": lo.AR, "opaco": cheia, "plana": True}, e, trabalho / "pecas"))
                colocada = {"arquivo": str(pecas[-1].saida), "em": lugar_["em"], "ate": round(lugar_["em"] + lugar_["dur"], 3)}
                if lugar_["pip"]:
                    x0, y0, w0, h0 = pip["janela"]
                    colocada["pip"] = {"x": x0 / 1920, "y": y0 / 1080, "w": w0 / 1920, "h": h0 / 1080, "recorte": _recorte_pip(Path(plano["fonte"]), lugar_["item"]["at"], lugar_["dur"], pip["recorte"], rosto_cache)}
                colocadas.append(colocada)
            cmds += [replace(p, etapa="desenho") for p in pecas]
            lugar = trabalho / "explicador.json"
            explica += ["--pecas", str(lugar)]
        cmds.append(Passo("explicador", explica,
                          saida, [corrente, edl_path, *(p.saida for p in pecas)],
                          arquivo=(lugar, json.dumps(colocadas, ensure_ascii=False, indent=1)) if pecas else None,
                          # recodifica só a janela de cada peça (v2.sobre): é isso que ele muda
                          toca=sum(c["ate"] - c["em"] for c in colocadas) if pecas else None,
                          sobre=sum(c["ate"] - c["em"] for c in colocadas) if pecas else None,
                          # O conteúdo dos cards é calculado em memória e só vira
                          # arquivo na hora de executar. Ler de volta do disco
                          # devolveria o da corrida anterior — o mesmo defeito
                          # que o EDL teve.
                          extra=edl_texto + json.dumps([plano["overlays"], e.eixos["desenho"].get("pip"),
                                                        e.eixos["desenho"].get("leitura"),
                                                        [c.get("pip") for c in colocadas]],
                                                       ensure_ascii=False,
                                                       sort_keys=True), etapa="desenho"))
        corrente = saida

    montagem, corrente = _composicao(plano, e, corrente, trabalho, camada)
    cmds += [replace(p, etapa="composicao") for p in montagem]

    passos, corrente = _momentos(plano, e, corrente, edl_path, trabalho, edl_texto)
    cmds += passos

    if e.tem("emenda"):
        ef = e.eixos["efeito"]
        saida = trabalho / "com_emenda.mp4"
        # O glitch toca poucos quadros por emenda. O número declarado é o que
        # faz o modo seco marcar este passo quando ele custa o vídeo inteiro.
        cmds.append(Passo("glitch de emenda",
                          [PY, str(AQUI / "glitch_cuts.py"), str(corrente), str(edl_path),
                           "-o", str(saida), "--min-gap", str(ef["emenda_min"]),
                           "--intensity", ef["emenda_forca"]],
                          saida, [corrente, edl_path], toca=0.4, extra=edl_texto, etapa="composicao"))
        corrente = saida

    # A abertura vem DEPOIS da emenda: o glitch é posicionado pelo tempo do EDL, e
    # o CRT muda a duração do vídeo. Invertendo, a emenda cai no lugar errado.
    pontas = any(isinstance(e.eixos["efeito"][p], dict) for p in ("abertura", "fecho"))
    if e.tem("abertura") and pontas:
        passos, corrente = _pontas(e, corrente, trabalho)
        cmds += [replace(p, etapa="composicao") for p in passos]
    elif e.tem("abertura"):
        saida = trabalho / "com_abertura.mp4"
        crt = [PY, str(AQUI / "tv_effect.py"), str(corrente), "-o", str(saida)]
        if not e.eixos["efeito"]["som"]:
            crt.append("--no-sound")
        cmds.append(Passo("abertura CRT", crt, saida, [corrente],
                          toca=2 * e.eixos["efeito"].get("dur", 0.4), etapa="composicao"))
        corrente = saida

    if e.tem("broll") and plano.get("broll"):
        lista = confere_beats(plano["broll"])
        saida = trabalho / "com_broll.mp4"
        cmds.append(Passo("b-roll", broll_cmd(e, corrente, lista, saida),
                          saida, [corrente],
                          toca=sum(float(b["dur"]) for b in lista), etapa="composicao"))
        corrente = saida

    if e.tem("normalizar"):
        saida = trabalho / "normalizado.mp4"
        cmds.append(Passo("loudness",
                          [PY, str(AQUI / "normaliza.py"), str(corrente), "-o", str(saida)],
                          saida, [corrente], etapa="trilha"))
        corrente = saida

    brolls, cues_de, sons_decididos, auto, sons_auto = [], [], None, [], []
    if e.tem("legenda") and not legenda_feita:
        como = e.adaptador("legenda")
        saida = trabalho / "com_legenda.mp4"
        if como == "liso":
            # O .srt sai do próprio render, pelos offsets do EDL.
            srt = plano.get("legenda") or (trabalho / "master.srt")
            cmds.append(Passo("legenda", [PY, str(AQUI / "legendar.py"), str(corrente),
                                          str(srt), "-o", str(saida)],
                              saida, [corrente], etapa="trilha"))
            corrente = saida
        else:
            plan = plano.get("legenda")
            if not plan:
                # o storyboard já decidiu (e o dono pode ter corrigido pelo número): o render desenha isso
                import storyboard as sb
                plan = sb.decisoes(plano, edl_texto, refaz=rascunho)
            if not plan and plano.get("transcript"):
                # O estilo pediu legenda e o plano não trouxe o plano de cards.
                # Antes disto o recurso sumia calado: `e.tem("legenda")` dava
                # verdadeiro e nenhum comando entrava na cadeia.
                plan = trabalho / "cards.json"
                fala, cortada = Path(plano["transcript"]), None
                if edl_texto and e.bruto != "avatar" and Path(plano["transcript"]).exists():
                    # A transcrição está no tempo do bruto e a legenda queima no
                    # vídeo cortado: sem isto, cada silêncio tirado atrasa a legenda.
                    fala = trabalho / "fala_cortada.json"
                    cortada = (fala, _fala_no_corte(Path(plano["transcript"]),
                                                    json.loads(edl_texto)["ranges"]))
                cards = [PY, str(AQUI / "cards_da_fala.py"), str(fala), "-o", str(plan)]
                # O kit do aluno não leva a biblioteca: lá a legenda fica com a
                # cor padrão do captions_viral, em vez de quebrar.
                if V2.exists():
                    cards += ["--acento", _v2().token(e.eixos["desenho"]["destaque"], e.eixos["desenho"]["tema"])]
                if e.eixos["desenho"]["fonte"]:
                    cards += ["--fonte", e.eixos["desenho"]["fonte"]]
                if e.eixos["desenho"]["legenda"]:
                    cards += ["--legenda", e.eixos["desenho"]["legenda"]]
                if e.eixos["desenho"]["legenda_layout"]:
                    cards += ["--layout", e.eixos["desenho"]["legenda_layout"]]
                if e.eixos["desenho"]["legenda_palavras"]:
                    cards += ["--max", str(e.eixos["desenho"]["legenda_palavras"])]
                ritmo = e.eixos["desenho"]["ritmo"]
                if ritmo:
                    cards += ["--ritmo", f"{ritmo[0]},{ritmo[1]}"]
                cmds.append(Passo("cards da fala", cards, Path(plan),
                                  [Path(plano["transcript"])],
                                  extra=cortada[1] if cortada else "", arquivo=cortada, etapa="trilha"))
                if e.tem("pecas") and not rascunho and e.eixos["imagem"]["composicao"] == "cheio" and not plano.get("blocos"):
                    auto = _pecas_da_fala(plano, e, cortada[1] if cortada else fala, edl_texto)
            if plan:
                entradas, arquivo, extra = [corrente, Path(plan), *([dividida_json] if dividida_json else [])], None, ""
                doc = json.loads(Path(plan).read_text(encoding="utf-8")) if Path(plan).exists() else {}
                doc = doc if isinstance(doc, dict) else {}
                sons_decididos = doc.get("sons")        # os que o aluno viu no storyboard (e os que tirou pelo número)
                if doc.get("pecas") and not rascunho and not auto:
                    # as peças que o dono aprovou no storyboard: renderizadas pela biblioteca e postas pelo
                    # captions_viral (largura cheia, y 0: a peça é o quadro 1080x1920). O rascunho não as renderiza.
                    brolls = [{"peca": x["peca"], "q": x["q"], "t0": x["t0"], "t1": x["t1"], "larg": 1.0, "y": 0,
                               **{k: x[k] for k in ("mudo", "atras") if k in x}}
                              for x in doc["pecas"]]
                    for b in brolls:
                        passo = _peca(b, e, trabalho / "pecas")
                        if passo.saida not in {c.saida for c in cmds}:
                            cmds.append(replace(passo, etapa="desenho"))
                if auto:
                    # as peças que a fala pediu: renderizadas pela biblioteca e postas pelo captions_viral, no plano da legenda
                    # que o `propoe.py --junta` monta quando os cards existem (eles nascem na execução, não aqui)
                    sons_auto = [{"tipo": b["som"], "t": b["t0"]} for b in auto if b.get("som")]
                    for b in auto:
                        b.setdefault("larg", 1.0)
                        b.setdefault("y", 0)
                        b.pop("som", None)
                        passo = _peca(b, e, trabalho / "pecas")
                        if passo.saida not in {c.saida for c in cmds}:
                            cmds.append(replace(passo, etapa="desenho"))
                    brolls = auto
                    pj, junta = trabalho / "pecas_da_fala.json", trabalho / "legenda.json"
                    cmds.append(Passo("junta as peças da fala", [PY, str(AQUI / "propoe.py"), "--junta", str(plan), str(pj), "-o", str(junta)],
                                      junta, [Path(plan), *(Path(b["arquivo"]) for b in brolls)],
                                      extra=json.dumps(brolls, ensure_ascii=False, sort_keys=True),
                                      arquivo=(pj, json.dumps(brolls, ensure_ascii=False, indent=1)), etapa="desenho"))
                    plan = junta
                    entradas = [corrente, plan, *(Path(b["arquivo"]) for b in brolls)]
                    extra = json.dumps(brolls, ensure_ascii=False, sort_keys=True)
                # o fundo trocado atrás das palavras: a peça `e_fundo` opaca é a `tela` dos cards. O rascunho não a
                # renderiza (os cards saem sem fundo); o final a renderiza uma vez, com o nome guardado pelo pedido.
                telas = [c for c in doc.get("cards", []) if (c.get("tela") or {}).get("fundo")]
                if telas:
                    fundo = None
                    if not rascunho:
                        passo = _peca({**doc["fundo"], "opaco": True}, e, trabalho / "pecas")
                        cmds.append(replace(passo, etapa="desenho"))
                        fundo = passo.saida
                    for c in telas:
                        if fundo:
                            c["tela"]["arquivo"] = str(fundo)
                        else:
                            del c["tela"]
                if (brolls and not auto) or telas:
                    plan = trabalho / "legenda.json"
                    extra = json.dumps({**doc, "brolls": brolls}, ensure_ascii=False, indent=1)
                    arquivo, entradas = (plan, extra), [corrente, *(Path(b["arquivo"]) for b in brolls)]
                # O storyboard não queima a legenda no vídeo (103–166 s a cada rodada): ele só precisa dos quadros e da
                # revisão, e o `storyboard.do_celular` desenha a legenda nos quadros que mostra (captions_viral --quadros).
                if not rascunho:
                    cmds.append(Passo("legenda",
                                      [PY, str(AQUI / "captions_viral.py"), str(corrente),
                                       "--plan", str(plan), "-o", str(saida), *(["--dividida", str(dividida_json)] if dividida_json else [])],
                                      saida, entradas, extra=extra, arquivo=arquivo, etapa="trilha"))
                    corrente = saida
                    # os golpes da legenda saem ao lado do vídeo, no tempo dele
                    cues_de = [{"arquivo": str(saida), "t0": 0.0, "t1": 1e6}]

    # O reel sem blocos nunca chamava o som.py: o aluno pedia efeito e ele não tocava (22/10).
    # Bloco tem o som dele; o rascunho do storyboard sai sem som.
    sons = [{**{k: v for k, v in s.items() if k != "n"}, **({"arquivo": str(_rel(plano, s["arquivo"]))} if "arquivo" in s else {})}
            for s in (plano.get("sons") if sons_decididos is None else sons_decididos) or []] + sons_auto
    if e.eixos["efeito"]["som"] and not plano.get("blocos") and not rascunho and (sons or brolls or cues_de):
        plan = json.dumps({"brolls": brolls, "cues_de": cues_de, "sons": sons}, ensure_ascii=False, indent=1)
        pj, saida = trabalho / "som.json", trabalho / "com_som.mp4"
        cmds.append(Passo("som", [PY, str(AQUI / "som.py"), str(corrente), "--plan", str(pj), "-o", str(saida),
                                  "--mestre", str(e.eixos["efeito"]["sfx_db"])],
                          saida, [corrente, V2 / "sfx" / "sfx.json", *(Path(b["arquivo"]) for b in brolls)],
                          extra=plan, arquivo=(pj, plan), etapa="trilha"))
        corrente = saida

    return _desde(cmds, inicio), corrente


def _fala(plano: dict, trechos: list[dict]) -> str | None:
    """Onde há voz no vídeo emendado, `a:b,c:d`. None = em todo lugar.

    Bloco `mudo` sem `voz` só tem efeito: medir a voz ali, ou deixar o efeito
    abaixar a trilha, é tratar moeda como fala."""
    blocos = plano.get("blocos") or []
    fala = [bool(b.get("voz") or not b.get("mudo")) for b in blocos]
    if all(fala):
        return None
    t, out = 0.0, []
    for b, f, tr in zip(blocos, fala, trechos):
        d = tr["end"] - tr["start"]
        # a vinheta cantada também tira a cama da frente, enquanto dura
        fim = t + d if f else t + min(d, ff.dur(_rel(plano, b["vinheta"]))) if b.get("vinheta") else None
        if fim is not None:
            out.append(f"{t:.2f}:{fim:.2f}")
        t += d
    return ",".join(out)


def _trilha(e: es.Estilo, corrente: Path, duracao: float, trabalho: Path,
            faixa: str, outro: str | None, fala: str | None = None) -> Passo:
    """O passo da trilha, pelo adaptador do estilo: `fecho` sobe na chamada
    final (reel), `cama` fica sob a voz o vídeo inteiro com ducking (VSL)."""
    saida = trabalho / "com_trilha.mp4"
    if e.adaptador("trilha") == "cama":
        cmd = [PY, str(AQUI / "mixa.py"), str(corrente), "--trilha", str(faixa),
               "-o", str(saida)]
        if fala is not None:
            cmd += ["--fala", fala]
        if e.eixos["entrega"]["alvo"] is not None:
            cmd += ["--alvo", str(e.eixos["entrega"]["alvo"])]
        cmd += _args_cama(e)
    else:
        cmd = trilha_cmd(e, corrente, duracao, saida, faixa, outro)
    return Passo("fecho com trilha", cmd, saida,
                 [corrente] + ([Path(faixa)] if Path(faixa).exists() else []))


def trilha_cmd(e: es.Estilo, corrente: Path, duracao: float, saida: Path,
               faixa: str, outro: str | None = None) -> list[str]:
    """O fecho: trilha por baixo da fala o vídeo inteiro, subindo na chamada final. A mistura
    (o laço da faixa, a rampa e o teto) é a do som (`som.grafo_fecho`); aqui só o vídeo e o fecho."""
    import som
    t = e.eixos["trilha"]
    musica, a = som.grafo_fecho(t, duracao, "voz" if outro else "0:a",
                                ("3:a", "4:a") if outro else ("1:a", "2:a"), bool(outro))

    if outro:
        # Com fecho, o vídeo e o som são concatenados antes; o outro entra mudo, e a
        # trilha é a única coisa que se ouve ali.
        fc = ";".join(["[0:v][0:a][1:v][2:a]concat=n=2:v=1:a=1[v][voz]", *musica])
        entradas = ["-i", str(corrente), "-i", outro,
                    "-f", "lavfi", "-t", str(t["outro_dur"]),
                    "-i", "anullsrc=r=48000:cl=stereo", "-i", faixa, "-i", faixa]
        mapa = ["-map", "[v]", "-map", f"[{a}]"]
    else:
        fc = ";".join(musica)
        entradas = ["-i", str(corrente), "-i", faixa, "-i", faixa]
        mapa = ["-map", "0:v", "-map", f"[{a}]"]

    # Sem fecho a imagem não muda: a trilha só mexe no áudio, e o vídeo é copiado.
    video = ff.args_video(e.eixos["imagem"]["qualidade"]) if outro else ["-c:v", "copy"]
    return (["ffmpeg", "-y", *entradas, "-filter_complex", fc, *mapa,
             *video, *ff.args_audio(),
             "-movflags", "+faststart", str(saida)])


def _dependencias(cmds: list[Passo]) -> list[set[int]]:
    """De quais passos anteriores cada passo lê a saída: pelo comando e pelas entradas, as mesmas
    listas que a impressão olha. É o que deixa dois blocos correrem juntos e o som do bloco
    esperar a legenda dele."""
    saidas = {p.saida: i for i, p in enumerate(cmds)}
    deps = []
    for i, p in enumerate(cmds):
        lidos = {*p.entradas, *(Path(c) for c in p.cmd if isinstance(c, str) and not c.startswith("-"))}
        deps.append({saidas[x] for x in lidos if saidas.get(x, i) < i})
    return deps


def _executa(cmds: list[Passo], sem_cache: bool, paralelo: int, duracao: float = 0.0) -> list[str]:
    """Roda a cadeia, até `paralelo` passos por vez, cada um só quando o que ele lê ficou pronto.
    Devolve o nome dos que o cache pulou, na ordem da cadeia.

    Cada passo de custo > 0 roda numa vaga da máquina (`vagas.ocupa`): duas corridas ao mesmo tempo
    não somam dois pools. Cada passo que termina escreve `passo k/n · nome · s · faltam ~m min`, o que
    falta vindo das mesmas estimativas do seco, e deixa o tempo que levou (`grava_tempo`). `duracao` é
    a do vídeo que a cadeia faz: sem ela, o passo que escala com o vídeo não deixa amostra.

    Só entra no pool quem já pode rodar: com a fila na ordem da cadeia, o 2º lugar pegava o passo
    seguinte do mesmo bloco, ficava esperando o 1º, e o episódio do zero rodava em fila do mesmo
    jeito (07/10). A impressão é tirada depois das dependências: a entrada refeita tem instante novo."""
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
    deps = _dependencias(cmds)
    pulou = [False] * len(cmds)
    medidos = tempos_medidos()
    previsto = [0.0 if p.cobra else p.estima(duracao, medidos)[0] for p in cmds]
    andamento = {"feitos": 0, "falta": sum(previsto)}
    aviso = threading.Lock()

    def terminou(quais: list[int], nome: str, levou: float | None = None) -> None:
        """Conta os passos que acabaram; se algum rodou de verdade (`levou`), escreve a linha de progresso."""
        with aviso:
            andamento["feitos"] += len(quais)
            andamento["falta"] -= sum(previsto[i] for i in quais)
            if levou is not None:
                print(f"passo {andamento['feitos']}/{len(cmds)} · {nome} · {levou:.1f} s · "
                      f"faltam ~{max(0.0, andamento['falta']) / 60:.1f} min", flush=True)

    # As peças que faltam saem num lote só: um navegador pro vídeo inteiro, não um processo e um
    # navegador por peça. Fica de fora a que lê saída de outro passo e a que o cache já tem.
    lote = [i for i, p in enumerate(cmds) if p.cmd[1:3] == [str(V2 / "v2.py"), "render"]
            and not deps[i] and not p.arquivo and (sem_cache or not ja_feito(p))]

    def um(i: int) -> None:
        passo = cmds[i]
        passo.saida.parent.mkdir(parents=True, exist_ok=True)
        if passo.arquivo:
            caminho, texto = passo.arquivo
            caminho.parent.mkdir(parents=True, exist_ok=True)
            if not caminho.exists() or caminho.read_text(encoding="utf-8") != texto:
                caminho.write_text(texto, encoding="utf-8")
        if passo.cobra:
            print(f"  $ {passo.nome}: cobra na {passo.cobra}, e a fábrica não gasta. Quando quiser, "
                  f"rode à mão:\n      {' '.join(passo.cmd)}")
            terminou([i], passo.nome)
            return
        digital = _digital(passo)
        if not sem_cache and impressao.pronto(passo.saida, digital):
            pulou[i] = True
            print(f"  = {passo.nome} (já feito)")
            terminou([i], passo.nome)
            return
        with (vagas.ocupa(paralelo) if passo.custo(duracao) > 0 else nullcontext()):
            inicio = time.monotonic()                   # o relógio começa na vaga: esperar por ela não é custo do passo
            ff.run(passo.cmd)
            levou = time.monotonic() - inicio
        if passo.saida.exists():
            impressao.marca(passo.saida, digital)
        grava_tempo(passo, duracao, levou)
        terminou([i], passo.nome, levou)

    def em_lote() -> None:
        pedidos = cmds[lote[0]].saida.parent / f".lote.{os.getpid()}.json"
        pedidos.parent.mkdir(parents=True, exist_ok=True)      # a pasta pecas/ do vídeo novo
        pedidos.write_text(json.dumps([cmds[i].cmd[3:] for i in lote], ensure_ascii=False), encoding="utf-8")
        digitais = [_digital(cmds[i]) for i in lote]
        try:
            with vagas.ocupa(paralelo):
                inicio = time.monotonic()
                ff.run([PY, str(V2 / "v2.py"), "lote", str(pedidos)])
                levou = time.monotonic() - inicio
        finally:
            pedidos.unlink(missing_ok=True)
        for i, digital in zip(lote, digitais):
            if cmds[i].saida.exists():
                impressao.marca(cmds[i].saida, digital)
        terminou(lote, f"{len(lote)} peças em lote", levou)       # um processo só: sem tempo por peça para guardar

    lugares = max(1, paralelo)
    falta, feitos, rodando = [i for i in range(len(cmds)) if i not in lote], set(), {}
    with ThreadPoolExecutor(max_workers=lugares) as ex:
        if lote:
            rodando[ex.submit(em_lote)] = lote
        while falta or rodando:
            # ponytail: varre a fila inteira a cada passo pronto; são uns 150 passos
            for i in [i for i in falta if deps[i] <= feitos][:lugares - len(rodando)]:
                falta.remove(i)
                rodando[ex.submit(um, i)] = [i]
            prontos, _ = wait(rodando, return_when=FIRST_COMPLETED)
            for f in prontos:
                f.result()                  # a falha para a cadeia: nada novo entra
                feitos.update(rodando.pop(f))
    return [p.nome for p, s in zip(cmds, pulou) if s]


def fabrica(plano: dict, seco: bool = False, desde: str = "corte",
            sem_cache: bool = False, rascunho: bool = False, storyboard: bool = False, pauta: bool = False,
            refaz=()) -> Path | Seco:
    """Recebe estilo, bruto e plano; devolve o final. Em modo seco, devolve a
    cadeia montada sem executar nada. `refaz`: nomes de blocos cujo cache cai (só o deles)."""
    if desde not in ETAPAS:
        raise KeyError(f"etapa '{desde}' não existe. Disponíveis: {', '.join(ETAPAS)}")

    plano = _completa(plano)
    _confere(plano)
    refaz = tuple(refaz or ())
    _confere_refaz(plano, refaz)
    # A nota do dono é erro, não gosto: a que declara `barra` (voz com "IA", avatar fora do look 6, as do projeto) recusa antes de gastar.
    notas = checks.antes(plano)
    if not seco:
        checks.mostra(notas)
        barra = [r for r in notas if r.ok is False and r.barra]
        if barra:
            raise ValueError(f"{barra[0].id}: {barra[0].nota} — {barra[0].mediu}")

    sobrescritas = {k: v for k, v in plano.items()
                    if k in es.EIXOS or k in ("recursos", "adaptadores")}
    e = es.estilo(plano["estilo"], **sobrescritas)
    # O estilo pede um clima e a fábrica escolhe a faixa, pra não tocar a mesma em todo vídeo.
    tr = e.eixos["trilha"]
    if tr["clima"] and not (tr["faixa"] or plano.get("faixa")):
        faixa = mixa.escolhe(tr["clima"], str(Path(plano.get("_dir", ".")).resolve()), grava=not seco)
        if faixa:
            sobrescritas["trilha"] = {**sobrescritas.get("trilha", {}), "faixa": faixa}
            e = es.estilo(plano["estilo"], **sobrescritas)
    # o estilo escolhe o codificador; os helpers que a fábrica chama leem a escolha no ff
    os.environ[ff.HARDWARE] = _modo_hardware(e.eixos["imagem"].get("codificador"))
    # O editorial e o criativo resolvem os deles pela pasta do plano e só por ela: lá a voz pode
    # ainda não existir, e procurar na pasta de quem rodou acharia a voz de outro vídeo.
    if e.eixos["imagem"]["composicao"] not in ("editorial", "cenas"):
        plano = _caminhos(plano)
    if any(ancora.tem(b.get("janelas")) for b in plano.get("blocos") or []):
        # a janela ancorada cai na fala do bruto antes de tudo: a duração do episódio sai dela
        plano = {**plano, "blocos": [
            {**b, "janelas": _ancorado(b["janelas"], _fala_do_bloco(plano, b), b.get("nome", "?"), "no bruto")}
            if ancora.tem(b.get("janelas")) else b for b in plano["blocos"]]}

    bruto = plano.get("bruto", e.bruto)
    if bruto != e.bruto:
        raise ValueError(
            f"o estilo '{e.nome}' parte de {e.bruto}, e o plano trouxe {bruto}. "
            f"Brutos: {', '.join(sorted(BRUTOS))}"
        )
    if e.bruto == "obs+celular" and not (plano.get("celular") and Path(plano["celular"]).exists()):
        raise FileNotFoundError(f"o estilo '{e.nome}' é o modo 2 e o plano não tem o `celular` "
                                f"(o vídeo dele, gravado junto com o OBS): {plano.get('celular')}")

    final = _final(plano, e)
    trabalho = trabalho_do(plano, e)
    if rascunho:
        # o corte seco 720 p do storyboard: não passa por trilha, entrega nem verificação do final
        if not plano.get("blocos"):
            raise ValueError("--rascunho vale pro plano em blocos (o longo e os Shorts do episódio)")
        seca = {**sobrescritas, "corte": {**sobrescritas.get("corte", {}), "suave": False},
                "voz": {**sobrescritas.get("voz", {}), "por_bloco": False}}
        return _rascunho(plano, es.estilo(plano["estilo"], **seca), trabalho, seco, sem_cache, refaz)
    # Estilo de módulo sem o módulo recusa antes da transcrição do plano mínimo, que já é comando e custa.
    if not seco and (falta := [h for h in pede_modulo(e.nome) if not (AQUI / h).exists()]):
        raise FileNotFoundError(f"este plano pede {', '.join(falta)}, que {MODULO}")

    # O plano mínimo (câmera, sem transcrição no plano): a fábrica normaliza o bruto do celular e
    # transcreve ela mesma. O corte por palavra precisa da transcrição pronta, então no run real
    # esses passos rodam antes do corte; no seco só entram na lista.
    previos: list[Passo] = []
    if e.bruto == "camera" and not set(plano) - MINIMO:
        fonte = Path(plano["fonte"])
        plano = {**plano, "_dur_bruto": ff.dur(fonte)}
        norma = normaliza_bruto(fonte, trabalho)
        if norma:
            previos.append(norma)
            fonte = norma.saida
        if pronta := _fala_pronta(Path(plano["fonte"]), plano["_dur_bruto"]):
            # a fala veio com o bruto: o corte lê ela, e transcrever de novo só gastaria a espera
            plano = {**plano, "fonte": str(fonte), "transcript": str(pronta)}
        else:
            fala = trabalho / "transcripts" / f"{fonte.stem}.json"
            previos.append(_transcricao(fonte, fala))
            plano = {**plano, "fonte": str(fonte), "transcript": str(fala), "_transcript_auto": True}
        if not seco and previos:
            _avisa_modelo(previos)
            trabalho.mkdir(parents=True, exist_ok=True)
            _executa(previos, sem_cache, int(plano.get("paralelo") or PARALELO),
                     float(plano.get("_dur_bruto") or 0))
            previos = []

    if (e.bruto == "camera" and not plano.get("transcript") and not plano.get("blocos")
            and e.eixos["imagem"]["composicao"] not in ("editorial", "cenas")):
        print("aviso: o vídeo vai sem corte (sem `transcript` no plano, a fábrica não tira pausas nem "
              "erros). Para ter o corte, deixe só `fonte` (e `estilo`) no plano e ela transcreve "
              "sozinha, ou ponha o `transcript`.", flush=True)
    trechos = _edl(plano, e, seco)
    if not trechos:
        raise ValueError("o corte não deixou nenhum trecho — confira janelas e drops")
    # O vertical tirado de um vídeo deitado (o Short do vídeo longo): no bruto `camera`, o `imagem.recorte`
    # é o pedaço da fonte, em pixel, que vai pro 9:16, e vale em todo trecho. Nos outros brutos ele é a
    # bolinha do rosto ou o cartão do celular, e quem lê é a composição.
    if e.bruto == "camera" and e.eixos["imagem"]["recorte"]:
        trechos = [{**t, "recorte": e.eixos["imagem"]["recorte"]} for t in trechos]

    # A legenda aceita duas fontes: o plano de cards pronto, ou a transcrição de
    # onde gerá-lo. Por isso ela é a única em que o próprio nome do recurso no
    # plano também satisfaz a exigência. Na VSL em blocos ela vem no plano de
    # cada bloco, e no criativo ela sai do texto dos trechos.
    atendidos = {"legenda"} if plano.get("blocos") or plano.get("trechos") else set()
    mudos = [(r, es.exige(r)) for r in e.recursos
             if es.exige(r) and not plano.get(es.exige(r)) and not plano.get(r)
             and r not in atendidos]
    # No modo seco quem mostra é o `Seco.imprime`, com o resto da conferência.
    # Imprimir aqui também faria a mesma frase sair duas vezes, em duas redações.
    if not seco:
        for recurso, campo in mudos:
            print(f"aviso: o estilo pede '{recurso}' e o plano não trouxe '{campo}' — "
                  f"esta camada não vai entrar")

    entregas = _entregas(plano, e, final, trabalho)
    alheios = [d for _, d in entregas if _final_alheio(d)]
    if not seco and alheios:
        raise FileExistsError(
            f"{alheios[0]} já existe e não foi a fábrica que fez. Mude o `slug` ou tire o "
            f"arquivo de lá — o final é copiado por cima, e fora do git não há volta."
        )

    # --storyboard: a mesma cadeia em 720 p, numa pasta à parte (o cache do final fica quieto), parando na
    # legenda queimada: o que ela decide vai pro storyboard, e o render final desenha exatamente isso
    if storyboard and (plano.get("blocos") or e.eixos["imagem"]["composicao"] in COMPOSICOES):
        raise ValueError("--storyboard vale pro vídeo do celular (um bruto, sem blocos). O plano em blocos "
                         "usa --rascunho e `storyboard.py --rascunho`")
    cadeia = trabalho / "rascunho" if storyboard else trabalho
    edl_path = cadeia / "edl.json"
    fonte_render = (str(_fonte_isolada(trabalho)) if e.eixos["voz"]["tratamento"] == "isola"
                    else plano.get("fonte"))
    edl_doc = {"version": 1, "sources": ({Path(plano["fonte"]).stem: fonte_render}
                                         if plano.get("fonte") else {}),
               "ranges": trechos, "grade": e.eixos["graduacao"]["preset"],
               "overlays": [], "total_duration_s": round(_total(trechos), 2)}
    if (e.eixos["corte"].get("suave") and not plano.get("blocos") and e.bruto in ("live", "camera")
            and len(trechos) > 1):
        edl_doc["corte_suave"] = True

    edl_texto = json.dumps(edl_doc, ensure_ascii=False, indent=2)
    cmds, corrente = _cadeia(plano, e, edl_path, cadeia, desde, edl_texto, seco, rascunho=storyboard)
    cmds = previos + cmds
    # a pauta é opt-in (`--pauta`, prova na tela): pedida e sem o visual.json, o storyboard do celular para na linha
    # dela: só o corte, a transcrição e a fala cortada (que a pauta lê) valem o trabalho; o resto espera o visual.json
    sem_pauta_pede = (storyboard and pauta
                      and _falta_pauta(plano, e, cadeia / "fala_cortada.json"))
    if sem_pauta_pede:
        cmds = [p for p in cmds if p in previos or p.nome == "cards da fala"]
    # None = a cadeia parou no portão: ainda não existe imagem, e sem ela não há
    # trilha nem final. Seguir mandava uma PASTA para o ffmpeg e para o copy.
    parou = corrente is None

    duracao = _total(trechos)
    # o movimento que o plano pede contra o que o aluno escolheu (`movimento.py`): o `--storyboard` confere com o plano
    # decidido, e diz no fim; o --seco e o render conferem aqui, pelo `decisoes.json` ou, sem ele, pelo plano
    if not storyboard and e.bruto == "camera" and any(plano.get(k) for k in ("pecas", "camera", "palavras_atras", "sons")):
        import storyboard as sb
        extra = sb.avisos_do_plano(plano, trabalho / "rascunho", duracao)
        notas = notas + extra
        if not seco:
            checks.mostra(extra)
    faixa = plano.get("faixa") or e.eixos["trilha"]["faixa"]
    outro = plano.get("outro") or e.eixos["trilha"]["outro"]
    # O editorial mistura a trilha no passo de som dele, em pedaços e com o ducking na fala
    # medida: a cama da fábrica por cima seria a segunda trilha.
    quer_trilha = (ETAPAS.index(desde) <= ETAPAS.index("trilha")
                   and e.tem("trilha") and faixa and not parou and not storyboard
                   and e.eixos["imagem"]["composicao"] != "editorial")

    if seco:
        # A trilha precisa da duração do vídeo, que só existe depois de render.
        # No seco ela sai do EDL: aproximada, e é o bastante para conferir a
        # cadeia. Na execução o valor é medido no arquivo.
        if quer_trilha:
            cmds = cmds + [_trilha(e, corrente, duracao, trabalho, faixa, outro,
                                   _fala(plano, trechos))]
        if not sem_cache:
            cmds = [replace(p, pulavel=ja_feito(p) and not _do_bloco(p, refaz)) for p in cmds]
        return Seco(estilo=e, edl=trechos, passos=cmds, final=final, checks=notas,
                    duracao=duracao, mudos=mudos, alheio=alheios,
                    pulados=[p.nome for p in cmds if p.pulavel],
                    suave=_suave_linhas(plano, e, trechos))

    # O ouvido da voz vem no Clone de IA: recusa antes do primeiro comando, não no meio do render. O
    # --seco mostra a cadeia assim mesmo (o kit confere no seco os estilos de aula, que não leva).
    falta = sorted({Path(c).name for p in cmds for c in p.cmd if c.endswith(".py") and not Path(c).exists()}
                   | {h for h in pede_modulo(e.nome) if not (AQUI / h).exists()})
    if falta:
        raise FileNotFoundError(f"este plano pede {', '.join(falta)}, que {MODULO}")
    cadeia.mkdir(parents=True, exist_ok=True)
    # O EDL em disco é entrada de passo; no bruto `avatar` nenhum passo o lê,
    # porque quem corta é o `apara_pausas`, no áudio. Gravar assim mesmo deixava
    # em disco um segundo cálculo do mesmo corte, pronto para divergir do
    # primeiro no dia em que alguém mexesse num lado só.
    if e.bruto != "avatar":
        # Só reescreve se mudou. Reescrever igual dá instante novo ao arquivo, e o
        # instante entra na impressão — um EDL idêntico invalidava a cadeia inteira.
        if not edl_path.exists() or edl_path.read_text(encoding="utf-8") != edl_texto:
            edl_path.write_text(edl_texto, encoding="utf-8")
    if plano.get("overlays"):
        (trabalho / "overlays.json").write_text(
            json.dumps(plano["overlays"], ensure_ascii=False), encoding="utf-8")

    _esquece_blocos(cmds, refaz)
    pulados = _executa(cmds, sem_cache, int(plano.get("paralelo") or PARALELO), duracao)

    if quer_trilha:
        passo = _trilha(e, corrente, ff.dur(corrente), trabalho, faixa, outro,
                        _fala(plano, trechos))
        digital = _digital(passo)
        if not sem_cache and impressao.pronto(passo.saida, digital):
            pulados.append("fecho com trilha")
            print("  = fecho com trilha (já feito)")
        else:
            ff.run(passo.cmd)
            impressao.marca(passo.saida, digital)
        corrente = passo.saida

    if pulados:
        print(f"pulados por já existirem: {', '.join(pulados)}")

    if storyboard:
        if sem_pauta_pede:
            print(sem_pauta_pede)
            return trabalho
        import storyboard as sb
        return sb.do_celular(plano, cadeia, corrente, trechos)

    if parou:
        print("parou no portão: gere o que ele pediu acima (no HeyGen, o arquivo vai em "
              "`gerado`, ou no lugar que o passo `$` mostrou) e rode de novo")
        return trabalho

    # Copia, não move. Mover leva embora o último intermediário, e sem ele a
    # corrida seguinte refaz o passo que o produziu — disco é mais barato que
    # uma geração de encode.
    for origem, destino in entregas:
        origem = origem or corrente
        if not origem.exists():
            print(f"não entregue: {destino.name} (falta {origem.name})")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(origem), str(destino))
        _marca_final(destino).write_text(plano["slug"] + "\n", encoding="utf-8")

    # A procedência viaja com o final, não com a área de trabalho: é lá que ela
    # vai ser procurada, meses depois, por quem precisa responder de onde veio
    # um quadro.
    fontes = procedencia(plano)
    if fontes:
        lado = final.with_suffix(".fontes.json")
        lado.write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"procedência: {len(fontes)} clipe(s) de terceiro -> {lado.name}")

    checks.entrega(final, plano)   # mostra; no Tinteiro também grava o relatório e recusa o final com nota que barra
    print(f"pronto: {final}")
    return final


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="A fábrica: estilo, bruto e plano -> o final")
    ap.add_argument("plano", type=Path)
    ap.add_argument("--seco", action="store_true",
                    help="monta a cadeia e imprime, sem renderizar")
    ap.add_argument("--detalhe", action="store_true",
                    help="com --seco: o comando inteiro e o quanto do vídeo cada passo muda "
                         "(sem a flag, uma linha por passo)")
    ap.add_argument("--desde", default="corte", choices=ETAPAS,
                    help="etapa em que começa (reaproveita o que já está em disco)")
    ap.add_argument("--storyboard", action="store_true",
                    help="o vídeo do celular: corta e decide a legenda em 720p, grava o storyboard numerado "
                         "e a página <slug>.storyboard/revisao.html, e para. Abra a revisão, marque e cole no chat; rode sem a flag")
    ap.add_argument("--pauta", action="store_true",
                    help="prova na tela (tela dividida): o --storyboard do celular exige o visual.json e para na linha "
                         "`pauta:` se faltar. Sem a flag o vídeo segue sem pauta visual")
    ap.add_argument("--rascunho", action="store_true",
                    help="só o corte seco em 720p (sem corte suave, peça, legenda nem trilha) em "
                         "<trabalho>/rascunho/seco.mp4, pro storyboard; não mexe no final nem no cache dele")
    ap.add_argument("--sem-cache", action="store_true",
                    help="refaz todo passo, mesmo os que o cache já tem")
    ap.add_argument("--refaz", nargs="+", default=[], metavar="BLOCO",
                    help="plano em blocos: refaz só estes blocos (o cache dos outros fica) e o que lê a saída deles")
    args = ap.parse_args()

    try:
        import atualiza     # o kit de aulas não leva o atualiza.py
    except ImportError:
        atualiza = None
    if atualiza and (aviso := atualiza.aviso_de_versao(AQUI.parents[2], date.today())):
        print(aviso)    # só avisa; não trava nada

    try:
        plano = json.loads(args.plano.read_text(encoding="utf-8"))
        plano.setdefault("_dir", str(args.plano.resolve().parent))
        r = fabrica(plano, seco=args.seco, desde=args.desde, rascunho=args.rascunho,
                    storyboard=args.storyboard, pauta=args.pauta, sem_cache=args.sem_cache, refaz=args.refaz)
    except Exception as erro:
        for linha in explica_erro(erro):
            print(linha, file=sys.stderr)
        if not isinstance(erro, (OSError, KeyError, ValueError, RuntimeError)):
            traceback.print_exception(erro, file=sys.stderr)   # bug interno: uma linha só não basta
        sys.exit(1)
    if isinstance(r, Seco):
        r.imprime(detalhe=args.detalhe)


def explica_erro(erro: Exception) -> list[str]:
    """Três linhas para o aluno: o que aconteceu, o que fazer, e a quem pedir ajuda. Os casos que
    a gente conhece ganham a frase deles; o resto mostra a mensagem que a fábrica já escreveu."""
    msg = " ".join(str(erro).split() if isinstance(erro, OSError) else
                   str(erro.args[0] if erro.args else erro).split()) or type(erro).__name__
    if isinstance(erro, FileNotFoundError) and "fonte" not in msg:
        faz = "Confira se o caminho está certo e se o arquivo existe; depois rode o mesmo comando."
    elif isinstance(erro, FileNotFoundError):
        faz = "Confira o caminho em `fonte` no plano (conta a partir da pasta do plano) e rode de novo."
    elif isinstance(erro, RuntimeError) and ("ffprobe falhou" in msg or "medir a duração" in msg):
        msg = f"O arquivo não é um vídeo que eu consiga ler. ({msg})"
        faz = "Abra o arquivo no player para ver se toca; se não tocar, exporte de novo em MP4 ou MOV."
    elif "transcribe.py" in msg or "modelo de transcrição" in msg:
        faz = (f"Confira a internet e rode de novo: o modelo ({tsc.MODELO_PADRAO}, ~{tsc.MODELO_GB} GB) "
               f"baixa uma vez e retoma de onde parou.")
    else:
        faz = "Corrija o que a mensagem aponta e rode o mesmo comando de novo."
    return [f"Deu erro: {msg}", faz,
            "Se não resolver, mande o conferencia.txt num Chamado da Academy."]


if __name__ == "__main__":
    main()
