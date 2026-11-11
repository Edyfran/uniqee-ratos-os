"""O estilo de edição, como dado.

Antes disto, "o estilo consolidado da aula" não existia em lugar nenhum: era a
sequência de programas que o editor lembrava de rodar, com as flags que lembrava
de passar, sobre constantes que lembrava de não mexer. Por isso não dava para
escolher, listar nem herdar.

    e = estilo("aula-ccnp")                      # o conjunto inteiro, por nome
    e = estilo("reel-mono", imagem={"fps": 24})  # com ajuste de um vídeo só

Um nome resolve os oito eixos: **corte**, **voz**, **imagem**, **graduacao**,
**efeito**, **desenho**, **trilha**, **entrega**.

**A orientação é campo do eixo de imagem, não uma coisa acima do estilo.** O
recorte do rosto não é do formato: dentro do vertical já existem três tratamentos
diferentes, e são três estilos. Um estilo que serve os dois formatos — o vídeo de
quadro — deixa de ser dois.

**Recurso é camada nomeada com posição declarada.** O estilo lista quais quer; o
plano liga e desliga. Ninguém no meio precisa saber o nome de um recurso.

Cada eixo segue o molde que a graduação já usava neste projeto: um dicionário de
nomes, uma função que resolve, e um erro que lista os válidos quando o nome não
existe. Nada aqui é padrão novo — é aquele eixo, oito vezes.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import clean_edl
import ff


# ---- os oito eixos ----------------------------------------------------------
#
# O valor de cada chave é o padrão. Um estilo declara só o que muda.

EIXOS: dict[str, dict[str, Any]] = {
    # O que é cortado — a costura A.
    "corte": {
        "afinacao": "aula",        # aula | tight | silencio | silencio-gagueira
        "ajuste": {},              # sobrescritas da afinação, botão a botão
        # Corte suave (corte_suave.py): a emenda de fala entre dois trechos do mesmo bruto leva ponte de
        # quadros, zoom leve e ruído de sala; a hesitação dentro da frase vira corte. Só talking head.
        "suave": False,
        # Segundos que o vídeo segura depois da última palavra, em vez de acabar nela (fabrica._segura_o_fim):
        # primeiro a cauda que o bruto tem (a boca fecha, o corpo assenta), e o que faltar vira quadro parado
        # com silêncio. Serve ao estilo que fecha numa chamada que só termina de entrar quando a fala acaba.
        # 0 = o corte acaba onde sempre acabou.
        "congela_fim": 0.0,
    },
    # Como a voz é tratada antes de normalizar.
    "voz": {
        "tratamento": "realce",    # realce | cru | isola (serviço, para gravação barulhenta)
        "alvo": ff.LOUDNORM_I,
        # Bloco com a fala dele (não mudo, sem `voz` à parte) passa pelo trata_voz e sai no nível
        # da voz gravada à parte. Para episódio montado de microfones diferentes.
        "por_bloco": False,
        # Depois da emenda, a fala de cada bloco no mesmo nível (`nivela_fala.py`): {"alvo": dBFS, "forca", "faixa"}.
        # None = sem o passo. O `nivela_fala` do plano manda sobre este.
        "nivela_fala": None,
        # A voz que nasce do texto, quando nasce: {modelo, stability, similarity_boost,
        # sotaque (a marca que vai na frente do texto), tentativas (o teto de gerações)}.
        "sintese": None,
    },
    # O quadro: proporção, tamanho, taxa e quanto se aperta.
    "imagem": {
        "orientacao": "16:9",      # 16:9 | 9:16
        "altura": ff.ALTURA,
        "fps": ff.FPS,
        "canvas": None,            # "2560x1440" encaixa 16:10 num quadro 16:9
        "qualidade": "final",
        # auto | x264 | hardware (o VideoToolbox do Mac, na mesma escada: ff.QUALIDADES_HW). O
        # auto põe o hardware só nos degraus intermediários (ff.AUTO_HARDWARE) e deixa o que sai
        # no x264. Onde não existe hardware, é x264 de qualquer jeito.
        "codificador": "auto",
        # Os blocos recortam de uma cópia do bruto na altura da saída (fabrica._proxy), feita
        # uma vez por bruto, em vez do 4K.
        "proxy": False,
        # Como o vertical é montado. Três tratamentos que já existiam, cada um de
        # um estilo — é o que prova que o recorte do rosto é do estilo e não do
        # formato:
        #   pilha        rosto em cima, desenho embaixo (reel de live)
        #   sobreposicao rosto em quadro cheio, desenho por cima (reel com cenas)
        #   cheio        sem montagem (reel de câmera, quadro)
        "composicao": "cheio",
        # Recorte do rosto no quadro da LIVE. A fábrica devolve o vídeo às
        # dimensões da live antes de aplicar — o render pode ter reescalado. Com a
        # `chapa`, é a bolinha que o OBS gravou (bruto live) ou o pedaço do quadro do
        # celular que vai no cartão (obs+celular; sem ele, o quadro inteiro).
        "recorte": None,           # "crop=810:1440:555:0"
        "banda": [1080, 900],      # o tamanho da faixa do rosto na pilha
        #   editorial    o molde do Nick: painel em cima, rosto num cartão embaixo
        #   cenas        voz em off sobre cenas do banco, cada uma no trecho dela (o criativo)
        # O que vai atrás do rosto gerado (caminho a partir da raiz), na escala e
        # no lugar do avatar. None = o que veio com ele.
        "fundo": None,
        # A tela dividida reta com cena embaixo: [y da costura, altura do degradê].
        "costura": None,
    },
    "graduacao": {
        "preset": "none",          # os nomes vivem no grade.py
    },
    # Abertura, fecho e emenda.
    "efeito": {
        # crt | None | uma peça da biblioteca, {"peca": ..., "q": {...}}, que abre o vídeo
        "abertura": None,
        "fecho": None,             # a peça que fecha o vídeo, no mesmo formato. Peça troca o CRT
        "som": True,
        # Nível dos sons das peças contra a voz, em dB. Medido na VSL em 24/09:
        # com -8 o tick-roll ficava 17 dB debaixo da voz, inaudível.
        "sfx_db": -2.0,
        "emenda": None,            # glitch | None
        "emenda_min": 30.0,        # vão de origem que merece glitch, em s
        "emenda_forca": "subtle",
    },
    # O que é desenhado por cima. Cor, letra e movimento NÃO moram aqui: são do
    # núcleo de tools/v2, e o estilo só escolhe entre os dois chãos dele. A
    # direção que vale por padrão é a da VSL — papel claro, nada atrás da pessoa.
    "desenho": {
        # claro | tinta | tinteiro (canal de Lorcana) | marca (a marca/tema.css do aluno) — o ?tema=
        # de toda peça
        "tema": "claro",
        # A letra da legenda viral: um nome do FONTES do captions_viral, ou o caminho de um .ttf/.otf
        # a partir da raiz (`marca/fontes/x.ttf`, `#Black` no fim escolhe a instância da variável).
        # None = a padrão dele.
        "fonte": None,
        # Texto atrás da pessoa (palavra-herói recortada, peça em camadas). A
        # VSL fechou isso: ênfase vem de peso e escala, nunca de profundidade.
        "atras": False,
        # Cadência da legenda viral, [entrada, passo] em s. None = a do captions_viral.
        "ritmo": None,
        # O token do núcleo que acende a palavra em destaque na legenda viral: `ac`, o azul
        # do bloco, ou `mk`, o amarelo do marcador.
        "destaque": "ac",
        # O preset da legenda viral, por nome (`captions_viral.py --presets` lista): letra, cor,
        # caixa e movimento de uma vez, com a paleta dele. None = a legenda de sempre.
        "legenda": None,
        # O layout de todo card da legenda viral (`topo`, `centro`, `faixa`, `rodape`, `entre`, `alto`,
        # `faixa_criativo`: LAYOUTS do captions_viral). None = a faixa. Quem lê é o criativo e o
        # cards_da_fala (--layout), que vale para o reel de câmera e o de avatar.
        "legenda_layout": None,
        # Até quantas palavras cheias cabem num cartão da legenda (o --max do cards_da_fala; as átonas
        # não contam). None = quatro. A referência que mostra uma ou duas por vez pede 2.
        "legenda_palavras": None,
        # O y onde começa a faixa da legenda do Instagram: letra nenhuma desce dali.
        "legenda_ig": None,
        # A zona segura do 9:16, [x0, y0, x1, y1]: fora dela a interface da rede cobre a letra. Fundo,
        # cenário e rosto podem sangrar; o que precisa ser lido, não.
        "zona": None,
        # A coluna de botões da rede, [x, y]: de x pra direita e de y pra baixo também não tem letra.
        "botoes": None,
        # Ele na tela: {"janela": [x, y, w, h] em px de 1920x1080, "recorte": [cx, cy, cw, ch] em fração da
        # fonte}. None = a peça toma o quadro inteiro, como sempre.
        "pip": None,
        # O tempo mínimo de uma peça com texto no ar, {"minimo", "base", "por_palavra"} em s. None = o da fala.
        "leitura": None,
        # Quanto o vídeo se mexe, no recurso `pecas`: calma | media | intensa (movimento.ALVOS: peças por 10 s e fatia do
        # tempo coberta). None = sem peças. O que o aluno gravou em `movimento.py` ganha deste; o `desenho` do plano ganha dos dois.
        "densidade": None,
    },
    "trilha": {
        "faixa": None,
        # Sem faixa, a fábrica escolhe uma deste clima no catálogo (`mixa.escolhe`): a que está
        # há mais tempo sem tocar. Faixa no plano ganha.
        "clima": None,
        "alvo": ff.LOUDNORM_MUSICA,
        "sob_fala": 0.03,          # volume da trilha enquanto ele fala
        "cama": None,              # LUFS da cama (adaptador cama); None = a do mixa (-31,5)
        # A faixa entra duas vezes e cruza consigo mesma: é o que faz o laço não
        # ter costura audível quando a música é mais curta que o vídeo.
        "cruzamento": 4.0,
        "entrada": 2.2,            # fade de entrada
        "saida": 0.9,              # fade de saída
        # A subida no fecho. A trilha fica embaixo da fala o reel inteiro e só
        # sobe na chamada final — sem isso ela disputa com a voz.
        "subida": 1.2,
        "antes_do_fecho": 0.4,     # começa a subir este tanto antes do outro
        "outro": None,             # vídeo de fecho, se houver
        "outro_dur": 5.0,
        # Pedaços da faixa, [{de, ate, em, entra, sai}]: o trecho dela que entra onde no
        # vídeo. None = a faixa do começo. Quem lê é o reel editorial.
        "pedacos": None,
        "duck": None,              # quanto a voz abaixa a cama (adaptador cama); None = a do mixa (12)
        "fade_fim": None,          # fade da cama no fim, em s; None = o do mixa (2,4)
        "duck_limiar": None,       # nível da voz em que a cama abaixa; menor = abaixa mais; None = o do mixa (0,03)
        "duck_solta": None,        # ms pra cama voltar no respiro; None = o do mixa (420)
    },
    "entrega": {
        "pasta": "videos",         # a fábrica completa com o projeto
        "alvo": None,              # LUFS da mistura com cama de trilha; None = o do mixa (-16, web)
    },
}


# ---- recursos ---------------------------------------------------------------
#
# `posicao` é o que faz um recurso ligado entrar no lugar dele em vez de no fim
# da fila. É o mínimo para a lista funcionar — não é ordem declarada genérica,
# que fica de fora até um segundo estilo pedir outra ordem.

# `exige` é o campo do plano sem o qual a camada não tem o que desenhar. Não é
# validação: é o que deixa a fábrica DIZER que o recurso não vai entrar, em vez
# de deixá-lo sumir calado. O estilo `vsl` pedia explicador, o plano nunca trazia
# `overlays`, e o vídeo saía sem — sem uma linha na tela sobre isso.
RECURSOS: dict[str, dict[str, Any]] = {
    # Sem `exige`: no bruto live o rosto é a bolinha do OBS, e no modo 2 a fábrica recusa o
    # plano sem `celular` antes de começar, em vez de deixar a camada sumir.
    "chapa":       {"posicao": 10, "o_que_faz": "a tela numa janela sobre o papel, e o rosto num "
                                                "cartão: a bolinha do OBS ou o celular do modo 2"},
    "explicador":  {"posicao": 20, "o_que_faz": "cartão gráfico sobre a gravação",
                    "exige": "overlays"},
    # Dois jeitos de entregar a mesma camada, e por isto a costura é real: o
    # `viral` tem direção (cadência, ênfase, palavra-herói) e come um plano de
    # cards; o `liso` queima um .srt e não decide nada. Enquanto havia um só, o
    # nome do recurso bastava — com dois, quem escolhe tem que ser o estilo, e
    # não o programa que por acaso chamou.
    # `exige` aqui é a segunda fonte possível: sem o plano de cards pronto, a
    # legenda nasce da transcrição. Sem nenhuma das duas ela não tem o que dizer.
    "legenda":     {"posicao": 30, "o_que_faz": "legenda queimada",
                    "adaptadores": {"viral": "captions_viral.py", "liso": "legendar.py"},
                    "padrao": "viral", "exige": "transcript"},
    # A camada que um módulo de estilo traz: os momentos da fala (título que entra quando é dito,
    # lista que acende palavra a palavra, legenda onde nada mais fala), desenhados por cima do
    # corte. Quem desenha é o `scripts/momentos.py` da skill do estilo (ver `_motor_do_estilo` no
    # fabrica.py); o tronco só sabe pedir. Sem `momentos` no plano ela não tem o que desenhar.
    "momentos":    {"posicao": 35, "o_que_faz": "blocos desenhados sobre a fala, no tempo dela",
                    "exige": "momentos"},
    # O que a fala pede, desenhado com a biblioteca (painel, toast, chip, dado, lista), sem o plano trazer nada:
    # `propoe.py` escolhe pela fala e pela densidade do estilo, e cada peça entra com o som dela.
    "pecas":       {"posicao": 36, "o_que_faz": "peças da biblioteca nos momentos fortes da fala, na densidade do estilo",
                    "exige": "transcript"},
    "broll":       {"posicao": 40, "o_que_faz": "corte de apoio por cima da fala",
                    "exige": "broll"},
    "emenda":      {"posicao": 50, "o_que_faz": "glitch nas emendas grandes"},
    "abertura":    {"posicao": 60, "o_que_faz": "CRT de liga e desliga, ou a peça que abre e a que fecha"},
    # Normalizar por último, depois dos passos que mexem no som — hoje o CRT
    # mistura o efeito sonoro DEPOIS da normalização, então ela mede uma coisa e
    # entrega outra.
    #
    # DESLIGADO EM TODOS OS ESTILOS, de propósito. O critério que este spec
    # fixou era: integrado, pico e faixa do final não podem mudar mais que
    # 0,5 LU. Medido em 14/09/2026 no único material que eu tinha — uma onda
    # senoidal — o integrado moveu 0,3 LU (passa) mas o pico moveu 3,4 dB e a
    # faixa 1,3 LU (reprova).
    #
    # Onda senoidal é material péssimo para medir faixa de loudness, e o
    # resultado provavelmente não vale para fala. Mas o critério não abre
    # exceção para material ruim: para ligar, meça numa aula de verdade. Ligar é
    # acrescentar "normalizar" aos recursos do estilo.
    "normalizar":  {"posicao": 65, "o_que_faz": "loudness no alvo das redes (ver nota)"},
    # Dois jeitos: o `fecho` deixa a trilha no piso e sobe na chamada final (o
    # reel); a `cama` fica 13 dB sob a voz o vídeo inteiro, com ducking (a VSL).
    "trilha":      {"posicao": 70, "o_que_faz": "música sob a fala",
                    "adaptadores": {"fecho": "fabrica.py", "cama": "mixa.py"},
                    "padrao": "fecho", "exige": "faixa"},
}


def exige(recurso: str) -> str:
    """O campo do plano sem o qual este recurso não entra. Vazio = não precisa."""
    return RECURSOS.get(recurso, {}).get("exige", "")


@dataclass(frozen=True)
class Estilo:
    nome: str
    bruto: str                      # live | camera | obs+celular | board | avatar | banco
    eixos: dict[str, dict[str, Any]]
    recursos: list[str] = field(default_factory=list)
    # Qual implementação entrega cada recurso. Vazio = a padrão do catálogo.
    adaptadores: dict[str, str] = field(default_factory=dict)

    @property
    def orientacao(self) -> str:
        return self.eixos["imagem"]["orientacao"]

    @property
    def vertical(self) -> bool:
        return self.orientacao == "9:16"

    def afinacao(self) -> clean_edl.Afinacao:
        """A afinação de corte pronta — o elo com a costura A."""
        c = self.eixos["corte"]
        # com o corte suave a emenda quase não se vê, e a hesitação ("ééé", "hum") passa a ser corte
        extra = {"hesitacao_interna": True} if c.get("suave") else {}
        return clean_edl.afinacao(c["afinacao"], **{**extra, **c["ajuste"]})

    def tem(self, recurso: str) -> bool:
        return recurso in self.recursos

    def adaptador(self, recurso: str) -> str:
        """Qual implementação entrega este recurso.

        Recurso com um jeito só devolve o próprio nome — quem chama não precisa
        saber se a costura existe ou não, e o dia em que o segundo adaptador
        aparecer, nenhum chamador muda.
        """
        escolhas = RECURSOS.get(recurso, {}).get("adaptadores")
        if not escolhas:
            return recurso
        return self.adaptadores.get(recurso, RECURSOS[recurso]["padrao"])


# ---- as zonas seguras: o único lugar dos números ------------------------------
#
# Fora da zona a interface da rede cobre a letra. `zona` = [x0, y0, x1, y1] no quadro do destino (px, `quadro` = [largura,
# altura]); `botoes` = [x, y]: a coluna de botões do Reels, de x pra direita e de y pra baixo. Orgânico e anúncio dividem os lados e
# os botões e diferem no pé: o texto do Instagram começa em y 1500 no Short orgânico (dono, 28/10: "a safezone do instagram é BEM mais
# em baixo"; a prosa dizia 1880, o conserto pôs 1250, a do anúncio) e em 1250 no anúncio (medido em 02/10 no "Do Zero ao Pronto" V1).
# O longo deitado deixa 65 px dos lados e 60 do alto e do pé (o k_frase aprovado do jabá assenta a 60 do pé); a etiqueta de carta do longo
# tem o pé em 1000, acima da barra do player (`etiqueta`: Trove, 28/10; o ep. 7 usou 1020).
# Quem lê: `encaixe_carta` (SEG, BOTOES, ZONA_LONGO), `notas_lorcana` (peca-na-zona, rascunho-na-zona), o estilo `anuncio-editorial` abaixo.
ZONAS: dict[str, dict[str, Any]] = {
    "organico": {"quadro": [1080, 1920], "zona": [65, 270, 1015, 1500], "botoes": [960, 1000]},
    "anuncio":  {"quadro": [1080, 1920], "zona": [65, 270, 1015, 1250], "botoes": [960, 1000]},
    "longo":    {"quadro": [1920, 1080], "zona": [65, 60, 1855, 1020], "botoes": None, "etiqueta": [65, 60, 1855, 1000]},
}


def zona(destino: str) -> dict[str, Any]:
    """A zona segura de um destino (`ZONAS`), numa cópia que o chamador pode mexer. Nome que não existe lista os válidos."""
    if destino not in ZONAS:
        raise KeyError(f"destino '{destino}' não tem zona segura. Disponíveis: {', '.join(sorted(ZONAS))}")
    return copy.deepcopy(ZONAS[destino])


# ---- o catálogo -------------------------------------------------------------
#
# Os estilos, extraídos do que já era feito. A extração não é hora de
# melhorar o molde: cada um nasce igual ao que já sai hoje.

ESTILOS: dict[str, dict[str, Any]] = {
    "aula-ccnp": {
        "bruto": "live",
        "corte": {"afinacao": "aula"},
        "imagem": {"orientacao": "16:9", "canvas": "2560x1440"},
        "efeito": {"abertura": "crt", "emenda": "glitch"},
        "entrega": {"pasta": "videos"},
        "recursos": ["explicador", "emenda", "abertura"],
    },
    # A aula sem ninguém gravando: a tela de verdade (o agente trabalhando no
    # terminal) com a voz clonada dele por cima, em blocos. Cada bloco é uma
    # janela do bruto com a fala do bloco, e as peças `h_` entram pelo plano
    # dele. A voz chega pronta do Eleven v4; CRT e glitch são do CCnP, não daqui.
    "aula-narrada": {
        "herda": "aula-ccnp",
        "voz": {"tratamento": "cru"},
        "desenho": {"tema": "claro"},
        "recursos": [],
    },
    # A aula que ele grava, na cara da Fábrica: o modo 2 (a tela no OBS, ele no celular, uma
    # palma no começo; decisão dele em 05/10, pela qualidade) com o corte do CCnP, sem o CRT e o
    # glitch, que são de lá. A tela vai numa janela sobre o papel, o celular num cartão ao lado,
    # e a marca abre e fecha. O tema claro já é a paleta e a letra da página da Fábrica.
    "aula-fabrica": {
        "herda": "aula-ccnp",
        "bruto": "obs+celular",
        "imagem": {"canvas": None},
        "efeito": {"emenda": None,
                   "abertura": {"peca": "t_marca", "q": {"t0": 0.1, "t_cacos": 0.55, "t_placa": 1.45,
                                                         "t_nome": 1.75, "dur": 3}},
                   # o fecho segura o nome escrito por mais de 1 s: com 3 s ele acabava no meio da palavra
                   "fecho": {"peca": "t_marca", "q": {"t0": 0.1, "t_cacos": 0.55, "t_placa": 1.45,
                                                      "t_nome": 1.75, "dur": 4, "sai": 0}}},
        "recursos": ["chapa", "explicador", "abertura"],
    },
    # A mesma aula gravada com a câmera dentro do OBS (a aula do kit, as de julho): o cartão cobre
    # a bolinha e salta do canto. O recorte é a bolinha da cena dele, medida no bruto de 17/07
    # (2560x1600); se a cena mudar, o plano traz `imagem.recorte`.
    "aula-fabrica-live": {
        "herda": "aula-fabrica",
        "bruto": "live",
        "imagem": {"recorte": "crop=471:313:2089:1287"},
    },
    "reel-mono": {
        "bruto": "live",
        "corte": {"afinacao": "tight"},
        "imagem": {"orientacao": "9:16", "altura": 1920, "qualidade": "reel",
                   "composicao": "pilha", "banda": [1080, 900]},
        # O reel de live ainda desenha no molde escuro do make_reel_v3 (a fase 2
        # do tools/v2 porta as cenas); o chão tinta é o que mais se parece.
        "desenho": {"tema": "tinta", "atras": True},
        "trilha": {"sob_fala": 0.03},
        "entrega": {"pasta": "videos/reels"},
        "recursos": ["explicador", "legenda", "trilha"],
    },
    "reel-camera": {
        "bruto": "camera",
        # Corte por energia mais a gaguejada ("meu projeto meu projeto"): o primeiro vídeo do aluno sai
        # sem repetição colada, e nenhuma outra palavra cai (o texto não decide verbo nem filler).
        "corte": {"afinacao": "silencio-gagueira"},
        "imagem": {"orientacao": "9:16", "altura": 1920, "fps": 24, "qualidade": "reel"},
        # Contraste leve e curva em S, sem mexer na cor e sem LUT: a imagem sai com o mesmo cuidado
        # da fala. LUT licenciada (`cereja-*`) nunca é padrão; o corretivo `camera_escura` o kit não leva.
        "graduacao": {"preset": "neutral_punch"},
        # Densidade média: 2 a 3 peças por 10 s e ~80% do tempo coberto (movimento.ALVOS), como o Reel editado à mão
        # que a régua do teste da Fábrica (07/11) mede. O aluno que gravou outra densidade, ou o plano, ganha deste.
        "desenho": {"atras": True, "densidade": "media"},
        "entrega": {"pasta": "videos/reels"},
        "recursos": ["broll", "legenda", "pecas"],
    },
    "quadro": {
        "bruto": "board",
        # O corte do quadro é mais apertado que o da aula e mais solto que o do
        # reel: ele respira entre blocos, mas não guarda pausa de live.
        "corte": {"afinacao": "aula", "ajuste": {"sil_cut": 0.45, "pad_in": 0.06,
                                                 "pad_out": 0.10, "pause_keep": 0.0}},
        "imagem": {"orientacao": "16:9"},
        "desenho": {"tema": "tinta"},
        "entrega": {"pasta": "videos"},
        "recursos": ["trilha"],
    },
    # O quadro vertical. Nove boards já existiam em `tools/quadro/projetos/*/
    # vertical.tsx` e renderizavam — mas a orientação estava no NOME DO ARQUIVO, e
    # aqui ela é campo. Sem esta declaração não havia como pedir um quadro 9:16 à
    # fábrica, e o molde 7a continuava molde. São quatro linhas porque o resto do
    # quadro já está resolvido no pai.
    "quadro-vertical": {
        "herda": "quadro",
        "imagem": {"orientacao": "9:16", "altura": 1920},
        "entrega": {"pasta": "videos/reels"},
    },
    # A VSL de avatar. O apresentador é gerado pelo HeyGen a partir da voz real
    # dele, então a costura A roda no ÁUDIO, antes de existir imagem: não há
    # quadro para cortar quando o corte acontece. É o que o bruto `avatar` declara.
    #
    # Os números não são gosto — saem do take medido: -18,9 LUFS é o nível das
    # aulas gravadas no OBS, e 0,04 de silêncio é o que a narração aguenta sem
    # soar picotada.
    # O que a VSL chama de "cards" é a LEGENDA com direção, não explicador: o
    # `cards_da_fala` gera o plano e o `captions_viral` queima. Declarar
    # `explicador` aqui prometia o cartão de aula, que é outro desenho e exige
    # `overlays` no plano — sem eles o recurso sumia calado.
    "vsl": {
        "bruto": "avatar",
        "corte": {"afinacao": "tight", "ajuste": {"sil_cut": 0.04}},
        "voz": {"tratamento": "realce", "alvo": -18.9},
        "imagem": {"orientacao": "9:16", "altura": 1920, "qualidade": "reel"},
        # A direção que virou padrão nasceu aqui. O ritmo é o de 21 dos 22
        # planos da VSL do Hermes, que o escreviam um por um.
        "desenho": {"tema": "claro", "ritmo": [0.167, 0.033]},
        "entrega": {"pasta": "videos"},
        "recursos": ["legenda", "trilha"],
        "adaptadores": {"legenda": "viral", "trilha": "cama"},
    },
    # O reel de topo de funil: o avatar da VSL com a voz dele clonada no Eleven v4
    # (`tools/quadro/voz.mjs`), rosto só onde a boca tem que aparecer e b-roll no
    # resto. A voz chega pronta — o voz.mjs já normaliza em -18 LUFS — e a cadeia
    # do microfone do OBS por cima dela tiraria ruído que não existe; `cru` pula o
    # trata_voz e deixa o apara, o ouvido e o portão.
    "reel-avatar": {
        "herda": "vsl",
        "voz": {"tratamento": "cru"},
        "entrega": {"pasta": "videos/reels"},
        "recursos": {"+": ["broll"]},
    },
    # O anúncio clonado de uma referência (skill `clonar-referencia`): o reel-avatar em blocos, com o
    # avatar na tela, peça de motion por cima e atrás dele, e a legenda no molde da ref. Os dois
    # primeiros clones (DezyUA7PPnR, DeUUFJQu8cw) repetiam no plano o tema tinta, o texto atrás da pessoa
    # e o amarelo do marcador; agora o plano só diz o que é dele (bloco, cards, peças, cor).
    "anuncio-clone": {
        "herda": "reel-avatar",
        "desenho": {"tema": "tinta", "atras": True, "destaque": "mk", "legenda": "placa-serifa"},
    },
    # O curto do canal de Lorcana: só mãos e cartas, em blocos (abertura, um
    # pacote, encerramento) tirados de JANELAS do bruto — o conteúdo é a carta,
    # e o corte por fala jogaria fora o rasgo e o reveal. Enquanto as cartas
    # passam, o bloco é mudo: trilha e efeito de dinheiro. A fala é a abertura e
    # o encerramento, que ele grava à parte (decisão dele, 29/09).
    "lorcana-curto": {
        "herda": "reel-camera",
        "imagem": {"fps": 30},
        # O corte e a cor do canal são os de antes do reel-camera sair pronto: o Tinteiro não muda de
        # olhar porque o primeiro vídeo do aluno ganhou graduação e corte de gaguejada.
        "corte": {"afinacao": "silencio"},
        "graduacao": {"preset": "none"},
        # A marca do canal (direção 12a "Tinteiro noturno"), não a Ninja.
        "desenho": {"tema": "tinteiro", "atras": True},
        # -14: o integrado dos curtos outliers falados com trilha (-13,1 a -15,9).
        "entrega": {"pasta": "videos", "alvo": -14.0},
        # Metade do curto é mão sem fala: a cama de aula (-31,5) deixava a trilha
        # 14 dB abaixo da voz e o bloco mudo soava vazio.
        "trilha": {"cama": -27.0},
        # A trilha é parte do curto (as cartas passam com música e efeito de
        # dinheiro), e é a cama dela que acerta o volume do episódio inteiro — o
        # bloco recortado não se normaliza sozinho. O `normalizar` segue desligado
        # (ver a nota dele em RECURSOS).
        "recursos": ["trilha"],
        "adaptadores": {"trilha": "cama"},
    },
    # O episódio longo do canal de Lorcana, deitado: o mesmo semanal, com o talking head e as
    # mesmas peças (cada uma no `ar` 1920x1080 dela). Ele grava deitado pra servir aos dois
    # formatos; o curto recorta em pé, o longo usa o quadro inteiro.
    "lorcana-longo": {
        "herda": "lorcana-curto",
        # hardware: num longo de 7 min, a emenda caiu de 82 para 35 s e a rodada de ajuste de 5,6
        # para 2,5 min, com o VMAF igual ou acima do x264 (07/10, docs/velocidade-da-fabrica.md)
        "imagem": {"orientacao": "16:9", "altura": 1080, "qualidade": "final",
                   "codificador": "hardware"},
        # O SOM do longo do Tinteiro, a receita do Treinando 7+8 (2ª rodada, 27/10) e da Trove (28/10), aprovada pelo dono: o plano do
        # episódio não a repete nem a sobrescreve (`serie_tinteiro.Longo` só aceita desligar a voz por bloco com o motivo escrito).
        # Os limites que ela cumpre moram em `som_tinteiro.py` (fala por bloco em 3 dB; música a 20 dB ou mais da fala, alvo 24; -14 LUFS
        # ±1), e o `test_serie_tinteiro` confere que os números daqui batem com ele (o kit não leva o módulo, então não se importa).
        # - cada bloco no mesmo nível de voz (o episódio junta o talking head de casa, os áudios da loja e o fone: ele, 02/10), e dentro do
        #   bloco um nivelador suave (`nivela_fala`, depois da emenda, alvo -22 dBFS de mediana de fala): ganho, sem tratar o som;
        # - a cama 24 dB abaixo da fala em repouso (-43 LUFS contra os -18,9 da voz), e o ducking a abaixa mais onde ele fala, voltando em 150 ms
        "voz": {"por_bloco": True, "nivela_fala": {"alvo": -22.0}},
        # o talking head tem emenda suave (blocos mudos e b-roll ficam como estão: o render só liga onde há fala)
        "corte": {"suave": True},
        # TRILHA COM FALA (dono, 14/10: "a música tá muito alta quando eu tô falando"; 27/10: "a minha voz ainda ta mais baixa que a musica
        # em algumas partes"): sob a voz a cama é quase imperceptível e sobe nos respiros e no b-roll mudo
        "trilha": {"cama": -43, "duck": 20, "duck_limiar": 0.006, "duck_solta": 150},   # -43 inteiro: o comando do mixa sai igual ao dos planos do T7, T8 e Trove (cache)
    },
    # O vídeo longo do YouTube, gravado deitado na câmera ou no celular (módulo YouTube Completo): o
    # longo do canal sem a marca do canal. Corte no silêncio, a trilha por baixo da fala, o quadro
    # inteiro; o Short sai do mesmo vídeo pelo reel-camera com recorte. Nada gerado: a voz é a gravada.
    "video-longo": {
        "herda": "lorcana-longo",
        "desenho": {"tema": "claro"},
        # O som do aluno segue o de antes: a receita do Tinteiro (nivelador por bloco e cama a 24 dB) é do canal, e o kit não leva o
        # `nivela_fala.py`
        "voz": {"nivela_fala": None},
        "trilha": {"cama": -27.0, "duck_solta": 250},
        # O corte do reel (silencio, 0,04) deixa a fala sem ar, e num vídeo de 9 a 12 min isso
        # cansa. Aqui o corte é o do quadro (só vão acima de 0,45 s sai, e a pausa mantém 0,3 s de
        # fôlego): corta entre pensamentos, na respiração. Ponto de partida, não medido: afinar de
        # ouvido no vídeo 2 (pesquisa/howtoyoutube/ESTUDO.md, C7).
        "corte": {"afinacao": "aula", "suave": False,
                  "ajuste": {"sil_cut": 0.45, "pad_in": 0.06, "pad_out": 0.10, "pause_keep": 0.3}},
    },
    # A aula que o dono grava sozinho, deitado, na câmera do celular (a Aula 0): o corte do vídeo
    # longo, o explicador da aula por cima do quadro inteiro (nada atrás dele) e a marca que abre e
    # fecha, como no aula-fabrica. Sem trilha: aula fala por cima de silêncio.
    "aula-fabrica-camera": {
        "herda": "video-longo",
        "graduacao": {"preset": "camera_escura"},   # corretivo nosso (lut/LEIA-ME); o pack do dono (cereja-N, lut/terceiros) entra pelo plano
        # Ele fica na tela (dono, 22/10): a peça que tomaria o quadro inteiro encolhe pra esquerda e ele
        # aparece num cartão 4:5 à direita. Peça com `"pip": false` no plano toma o quadro (a tela mostrada
        # precisa dele todo). Os números do cartão são os de `html.pip` no direcao-h.css; o
        # test_lesson_overlays confere que são os mesmos.
        "desenho": {"tema": "claro", "atras": False,
                    "pip": {"janela": [1188, 60, 672, 840], "recorte": [0.375, 0.0, 0.45, 1.0]},
                    # Tempo de leitura: peça com texto fica no ar max(minimo, base + por_palavra × palavras),
                    # mesmo passando da fala dele. Peças que se tocam não se sobrepõem: a seguinte espera.
                    "leitura": {"minimo": 4.0, "base": 1.5, "por_palavra": 0.4}},
        "efeito": {"abertura": {"peca": "t_marca", "q": {"t0": 0.1, "t_cacos": 0.55, "t_placa": 1.45,
                                                         "t_nome": 1.75, "dur": 3}},
                   "fecho": {"peca": "t_marca", "q": {"t0": 0.1, "t_cacos": 0.55, "t_placa": 1.45,
                                                      "t_nome": 1.75, "dur": 4, "sai": 0}}},
        # "normalizar": os sons das peças e da marca somam por cima da fala depois do loudnorm do render, e o
        # pico da aula passava de -1 dBTP (-0,8). O passo roda por último e põe o pico no teto (ver nota do recurso).
        "recursos": ["explicador", "abertura", "normalizar"],
    },
    # O reel de topo de funil no molde do Nick Saraev (a peça e_editorial): a voz
    # clonada no Eleven v4, o avatar num cartão arredondado embaixo, o painel em cima
    # com a fala, as capturas e as peças. Três monta.py copiados faziam isso, e cada
    # ajuste do dono virava conserto em três lugares. Quem monta é o reel_editorial.py.
    #
    # O que o dono decidiu em 30/09 mora aqui como padrão (tools/v2/LEIA-ME.md, a voz
    # editorial); o que é regra e não número (cartão só com rosto, chamada só no fim,
    # sem selo de IA, gancho no quadro 0) o `confere` do helper cobra no modo seco.
    # A fala na tela quem desenha é a e_editorial, então a legenda não é recurso aqui.
    "reel-editorial": {
        "herda": "reel-avatar",
        "voz": {"alvo": -19.0,
                "sintese": {"modelo": "eleven_v4", "stability": 0.25, "similarity_boost": 0.85,
                            # sem marca de emoção. O sotaque é de quem grava: vem da marca
                            # (VOZ_SOTAQUE no .env.local) e, vazio, a voz clonada fala como é
                            "sotaque": "",
                            "tentativas": 3}},
        # O fundo atrás do rosto não tem padrão: é a placa do look de quem grava, e vem do
        # plano (`imagem.fundo`). O confere do helper cobra quando falta.
        "imagem": {"composicao": "editorial", "costura": [768, 120]},
        "desenho": {"legenda_ig": 1450},
        # medidos no teste cego e no Eleven v4: com a razão 12 do mixa a cama sumia
        # sob a narração sem respiro, e o fade de 2,4 s abafava a chamada
        "trilha": {"cama": -21.0, "duck": 3.0, "fade_fim": 0.6, "clima": "editorial"},
        "entrega": {"pasta": "videos/topo"},
        "recursos": ["trilha"],
    },
    # O mesmo reel editorial como anúncio de Reels e Stories da Meta. A interface do anúncio cobre o
    # topo (~14%), a base (~35%) e as laterais (~6%), mais a coluna de botões; medido no "Do Zero ao
    # Pronto" V1 em 02/10, o placar, a legenda sobre o rosto, o título da capa e o "Saiba mais"
    # caíam embaixo dela. Vale também pro trial reel e pra página, que cortam do mesmo render.
    "anuncio-editorial": {
        "herda": "reel-editorial",
        "desenho": {"legenda_ig": ZONAS["anuncio"]["zona"][3], "zona": ZONAS["anuncio"]["zona"],
                    "botoes": ZONAS["anuncio"]["botoes"]},
        "trilha": {"clima": "vitrine"},
        "entrega": {"pasta": "videos"},
    },
    # O criativo de anúncio: voz em off sobre cenas do banco (câmera de segurança, plantão,
    # documentário), cada cena no trecho da fala que ilustra. Morou meses fora da fábrica, num
    # monta_criativo.py na pasta dos anúncios; quem monta agora é o criativo.py. Da VSL vem a
    # legenda viral no ritmo dela e a cama sob a voz o vídeo inteiro.
    #
    # O bruto é o banco, não um take: a imagem já existe antes da voz, e a voz nasce do texto.
    # A cama é a de 23 dos 24 roteiros dos ninjas, e o destaque é o amarelo do marcador.
    "criativo": {
        "herda": "vsl",
        "bruto": "banco",
        "voz": {"tratamento": "cru",
                "sintese": {"modelo": "eleven_multilingual_v2", "tentativas": 3}},
        "imagem": {"composicao": "cenas"},
        "desenho": {"destaque": "mk", "legenda_layout": "faixa_criativo"},
        "trilha": {"cama": -20.0, "duck": 1.5, "fade_fim": 0.3},
        "entrega": {"pasta": "videos/criativos"},
    },
    # O mesmo criativo no Reels orgânico: sem o botão do anúncio, a legenda desce pra faixa, e
    # a trilha sai devagar no fim (os seis roteiros -reels repetiam as duas coisas).
    "criativo-reel": {
        "herda": "criativo",
        "desenho": {"legenda_layout": "faixa"},
        "trilha": {"fade_fim": 1.2},
    },
    # Herdar é uma linha. Este existe para provar que o molde não precisa ser
    # copiado quando muda uma coisa só.
    "reel-mono-claro": {
        "herda": "reel-mono",
        "desenho": {"tema": "claro"},
    },
}


# ---- resolver ---------------------------------------------------------------


def _funde(base: dict, novo: dict, onde: str) -> dict:
    """Funde eixo a eixo, recusando botão que não existe."""
    saida = copy.deepcopy(base)
    for eixo, valores in novo.items():
        if eixo not in EIXOS:
            raise KeyError(
                f"eixo '{eixo}' não existe em {onde}. "
                f"Disponíveis: {', '.join(sorted(EIXOS))}"
            )
        if not isinstance(valores, dict):
            raise TypeError(f"o eixo '{eixo}' em {onde} tem que ser um dicionário")
        desconhecidos = set(valores) - set(EIXOS[eixo])
        if desconhecidos:
            raise KeyError(
                f"botão que não existe no eixo '{eixo}' de {onde}: "
                f"{', '.join(sorted(desconhecidos))}. "
                f"Disponíveis: {', '.join(sorted(EIXOS[eixo]))}"
            )
        saida[eixo].update(copy.deepcopy(valores))
    return saida


def _recursos(atuais: list[str], pedido: Any, onde: str) -> list[str]:
    """Aceita a lista inteira, ou {"+": [...], "-": [...]}. Sempre sai em ordem
    de posição — recurso ligado entra no lugar dele, não no fim."""
    if isinstance(pedido, dict):
        saida = list(atuais)
        for r in pedido.get("+", []):
            if r not in saida:
                saida.append(r)
        for r in pedido.get("-", []):
            if r in saida:
                saida.remove(r)
    else:
        saida = list(pedido)

    desconhecidos = [r for r in saida if r not in RECURSOS]
    if desconhecidos:
        raise KeyError(
            f"recurso que não existe em {onde}: {', '.join(desconhecidos)}. "
            f"Disponíveis: {', '.join(sorted(RECURSOS))}"
        )
    return sorted(saida, key=lambda r: RECURSOS[r]["posicao"])


def _adaptadores(base: dict, pedido: Any, onde: str) -> dict[str, str]:
    """Funde a escolha de adaptador, recusando recurso ou adaptador que não existe.

    Errar aqui é escolher um jeito de entregar que ninguém implementou, e
    descobrir isso no meio do render. O erro sai na entrada, listando os válidos.
    """
    saida = dict(base)
    for recurso, escolha in (pedido or {}).items():
        escolhas = RECURSOS.get(recurso, {}).get("adaptadores")
        if not escolhas:
            tem_costura = sorted(r for r, v in RECURSOS.items() if v.get("adaptadores"))
            raise KeyError(
                f"o recurso '{recurso}' em {onde} não tem adaptador para escolher. "
                f"Com escolha: {', '.join(tem_costura) or '(nenhum)'}"
            )
        if escolha not in escolhas:
            raise KeyError(
                f"adaptador '{escolha}' não existe para o recurso '{recurso}' em "
                f"{onde}. Disponíveis: {', '.join(sorted(escolhas))}"
            )
        saida[recurso] = escolha
    return saida


def resolver(declaracao: dict, nome: str = "?", catalogo: dict | None = None,
             _vistos: tuple[str, ...] = ()) -> Estilo:
    """Resolve uma declaração de estilo, seguindo a herança até a raiz."""
    catalogo = ESTILOS if catalogo is None else catalogo

    if nome in _vistos:
        volta = " -> ".join(_vistos + (nome,))
        raise ValueError(f"herança em ciclo: {volta}")

    pai_nome = declaracao.get("herda")
    if pai_nome:
        if pai_nome not in catalogo:
            raise KeyError(
                f"o estilo '{nome}' herda de '{pai_nome}', que não existe. "
                f"Disponíveis: {', '.join(sorted(catalogo))}"
            )
        pai = resolver(catalogo[pai_nome], pai_nome, catalogo, _vistos + (nome,))
        base_eixos, base_recursos, base_bruto = pai.eixos, pai.recursos, pai.bruto
        base_adapt = pai.adaptadores
    else:
        base_eixos = {e: copy.deepcopy(v) for e, v in EIXOS.items()}
        base_recursos, base_bruto, base_adapt = [], "live", {}

    proprios = {k: v for k, v in declaracao.items()
                if k not in ("herda", "bruto", "recursos", "adaptadores")}
    eixos = _funde(base_eixos, proprios, f"o estilo '{nome}'")
    recursos = _recursos(base_recursos, declaracao.get("recursos", base_recursos),
                         f"o estilo '{nome}'")
    adapt = _adaptadores(base_adapt, declaracao.get("adaptadores"),
                         f"o estilo '{nome}'")
    return Estilo(nome=nome, bruto=declaracao.get("bruto", base_bruto),
                  eixos=eixos, recursos=recursos, adaptadores=adapt)


# ---- a marca do aluno -------------------------------------------------------
#
# A pasta `marca/`, na raiz da fábrica, é do aluno e sobrevive à atualização do kit:
# o kit novo troca tools/, a marca fica. Os estilos dela entram no catálogo no mesmo
# molde dos daqui (herda, eixos, recursos) e só acrescentam nome: trocar um que o kit
# traz faria a aula e o vídeo dele divergirem calados.

MARCA = Path(__file__).resolve().parents[3] / "marca"


def da_marca(pasta: Path = MARCA) -> dict[str, dict[str, Any]]:
    """Os estilos de `pasta/estilos.json`, conferidos contra o catálogo. Sem o arquivo, nada.

    O erro sai na importação, com o arquivo no começo: estilo de marca quebrado não
    pode ser descoberto no meio do render. Chave que começa com `_` é nota."""
    arq = pasta / "estilos.json"
    if not arq.is_file():
        return {}
    try:
        lidos = json.loads(arq.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{arq}: JSON quebrado na linha {e.lineno}, coluna {e.colno}: {e.msg}") from None
    if not isinstance(lidos, dict) or not all(isinstance(d, dict) for n, d in lidos.items()
                                              if not n.startswith("_")):
        raise ValueError(f"{arq}: tem que ser {{\"nome-do-estilo\": {{\"herda\": ..., ...}}}}")
    novos = {n: {k: v for k, v in d.items() if not k.startswith("_")}
             for n, d in lidos.items() if not n.startswith("_")}
    # o que já está no catálogo com a mesma declaração é esta marca, lida na importação: ler de novo vale
    repetidos = sorted(n for n in set(novos) & set(ESTILOS) if ESTILOS[n] != novos[n])
    if repetidos:
        raise ValueError(f"{arq}: '{repetidos[0]}' já existe no kit. Dê outro nome e herde dele "
                         f"(\"herda\": \"{repetidos[0]}\")")
    juntos = {**ESTILOS, **novos}
    for nome, decl in novos.items():
        try:
            resolver(decl, nome, juntos)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{arq}: {e.args[0]}") from None
    return novos


def padrao_da_marca(pasta: Path | None = None) -> str | None:
    """O estilo que o onboarding grava em `_padrao` (`<slug>-celular`), se o catálogo o conhece.

    Lê de novo o arquivo que `da_marca` já conferiu, porque o `da_marca` descarta as chaves com `_` e
    o retorno dele é só de estilos. Nome que não existe, arquivo ausente ou JSON quebrado dão None: o
    JSON quebrado quem acusa é o `da_marca`, na importação, com o arquivo no começo da frase."""
    arq = (pasta or MARCA) / "estilos.json"
    try:
        nome = json.loads(arq.read_text(encoding="utf-8")).get("_padrao")
    except (OSError, ValueError, AttributeError):
        return None
    return nome if isinstance(nome, str) and nome in ESTILOS else None


ESTILOS.update(da_marca())


def estilo(nome: str, **sobrescritas) -> Estilo:
    """Resolve um estilo por nome, com sobrescritas do plano do vídeo.

    Nome que não existe estoura listando os válidos — o erro não pode ser
    descoberto no meio do render.
    """
    if nome not in ESTILOS:
        raise KeyError(
            f"estilo '{nome}' não existe. Disponíveis: {', '.join(sorted(ESTILOS))}"
        )
    base = resolver(ESTILOS[nome], nome)
    if not sobrescritas:
        return base

    recursos = sobrescritas.pop("recursos", None)
    adapt = sobrescritas.pop("adaptadores", None)
    eixos = _funde(base.eixos, sobrescritas, f"o plano (sobre '{nome}')")
    lista = (_recursos(base.recursos, recursos, f"o plano (sobre '{nome}')")
             if recursos is not None else base.recursos)
    return Estilo(nome=nome, bruto=base.bruto, eixos=eixos, recursos=lista,
                  adaptadores=_adaptadores(base.adaptadores, adapt,
                                           f"o plano (sobre '{nome}')"))


def catalogo() -> list[dict[str, Any]]:
    """O que existe, para um comando listar. A prosa aponta para aqui em vez de
    repetir a lista e envelhecer sozinha."""
    linhas = []
    for nome in sorted(ESTILOS):
        e = estilo(nome)
        linhas.append({
            "nome": nome,
            "orientacao": e.orientacao,
            "bruto": e.bruto,
            "corte": e.eixos["corte"]["afinacao"],
            "recursos": e.recursos,
            "entrega": e.eixos["entrega"]["pasta"],
        })
    return linhas


# ---- pedidos de personalização ----------------------------------------------
#
# `estilo.py pedidos <estilo>` entrega três pedidos prontos, na fala do aluno, cada um com o pedaço
# do plano que o realiza. Saem dos botões que o estilo tem de verdade e que o aluno vê no vídeo:
# nada de afinação interna ou número de LUFS. A marca dele (cor, música) vem primeiro.

# A legenda que o aluno reconhece pela cara; `captions_viral.py --presets` descreve as outras.
_LEGENDAS = (
    ("caixa-cor", "Quero a legenda com uma caixa colorida atrás da palavra falada."),
    ("karaoke-ciclo", "Quero a legenda acendendo palavra a palavra, com a cor trocando a cada frase."),
    ("minimal", "Quero a legenda branca e simples, sem caixa."),
    ("gigante", "Quero a legenda com uma palavra por vez, bem grande."),
)
_COR = {"ac": "azul", "mk": "amarelo"}   # o que `desenho.destaque` acende nos temas claro e tinta
_COM_IMAGEM_DE_CAMERA = ("camera", "live", "obs+celular")   # onde a graduação tem o que graduar


def _cores_da_marca(pasta: Path) -> dict[str, str]:
    """`ac` e `mk` do tema.css da marca. O `#TROQUE` do molde não é cor e fica de fora."""
    css = pasta / "tema.css"
    if not css.is_file():
        return {}
    return dict(re.findall(r"--(ac|mk)\s*:\s*(#[0-9a-fA-F]{3,8})\b", css.read_text(encoding="utf-8")))


def _faixa_da_marca(pasta: Path, decls: dict[str, dict]) -> str | None:
    """A primeira música que um estilo da marca declara e que existe (o caminho parte da raiz da fábrica,
    que é a pasta de cima da marca). Música que não existe quebraria o render, e não entra em pedido."""
    for nome in sorted(decls):
        faixa = (decls[nome].get("trilha") or {}).get("faixa")
        if faixa and (pasta.parent / faixa).is_file():
            return faixa
    return None


def _candidatos(e: Estilo, cores: dict[str, str], faixa: str | None):
    """(grupo, pedido, plano) em ordem de prioridade. Candidato do grupo "cor" não convive com outro
    do mesmo grupo: o preset da legenda traz paleta própria e apaga a cor que o outro pediu."""
    d, t = e.eixos["desenho"], e.eixos["trilha"]
    viral = e.tem("legenda") and e.adaptador("legenda") == "viral"
    paleta_do_estilo = d["legenda"] in (None, "padrao")   # preset com paleta própria ignora o destaque
    if cores and d["tema"] in ("claro", "tinta"):
        k = "mk" if "mk" in cores else "ac"
        yield "cor", f"Quero as cores da minha marca ({cores[k]}) no vídeo.", \
            {"desenho": {"tema": "marca", "destaque": k}}
    if len(cores) == 2 and d["tema"] == "marca" and viral and paleta_do_estilo:
        k = "ac" if d["destaque"] == "mk" else "mk"
        yield "cor", f"Quero a palavra em destaque na outra cor da minha marca ({cores[k]}).", \
            {"desenho": {"destaque": k}}
    if faixa and t["faixa"] != faixa:
        yield "trilha", "Quero a música da minha marca no fundo.", \
            {**({"recursos": {"+": ["trilha"]}} if not e.tem("trilha") else {}), "trilha": {"faixa": faixa}}
    if viral:
        try:
            import captions_viral
            for nome, texto in _LEGENDAS:
                if nome in captions_viral.PRESETS and nome != d["legenda"]:
                    yield "cor", texto, {"desenho": {"legenda": nome}}
                    break
        except ImportError:
            pass
    if viral and paleta_do_estilo and d["tema"] in ("claro", "tinta"):
        k = "mk" if d["destaque"] == "ac" else "ac"
        yield "cor", f"Quero a palavra em destaque em {_COR[k]}.", {"desenho": {"destaque": k}}
    if e.bruto in _COM_IMAGEM_DE_CAMERA:
        if e.eixos["graduacao"]["preset"] == "none":
            yield "imagem", "Quero a imagem com cor quente, de cinema.", {"graduacao": {"preset": "warm_cinematic"}}
        else:
            yield "imagem", "Quero a imagem sem filtro de cor.", {"graduacao": {"preset": "none"}}
    if viral and d["legenda_palavras"] != 2:
        yield "palavras", "Quero a legenda com duas palavras por vez.", {"desenho": {"legenda_palavras": 2}}
    if e.tem("trilha") and e.adaptador("trilha") == "cama":
        try:
            import som
            yield "volume", "Quero a música um pouco mais alta.", \
                {"trilha": {"cama": round((t["cama"] if t["cama"] is not None else som.CAMA) + 4, 1)}}
        except ImportError:
            pass
    if e.bruto != "board" and e.eixos["corte"]["afinacao"] in ("aula", "tight"):
        tight = e.eixos["corte"]["afinacao"] == "aula"
        yield "corte", ("Quero os cortes mais secos, sem pausa." if tight else "Quero deixar a fala respirar entre as frases."), \
            {"corte": {"afinacao": "tight" if tight else "aula"}}
    if d["tema"] in ("claro", "tinta"):
        escuro = d["tema"] == "claro"
        yield "tema", ("Quero as peças em fundo escuro." if escuro else "Quero as peças em fundo claro."), \
            {"desenho": {"tema": "tinta" if escuro else "claro"}}
    cru = e.eixos["voz"]["tratamento"] == "realce"
    if e.eixos["voz"]["tratamento"] in ("realce", "cru"):
        yield "voz", ("Quero minha voz do jeito que gravei." if cru else "Quero minha voz com mais clareza."), \
            {"voz": {"tratamento": "cru" if cru else "realce"}}
    if e.tem("trilha"):
        yield "sem-trilha", "Quero o vídeo sem música.", {"recursos": {"-": ["trilha"]}}
    if e.tem("abertura"):
        yield "sem-abertura", "Quero o vídeo sem a abertura.", {"recursos": {"-": ["abertura"]}}


def pedidos(nome: str, marca: Path | str | None = None) -> list[dict[str, Any]]:
    """Três pedidos de personalização do estilo, `[{"pedido": texto, "plano": sobrescrita}]`.

    O `plano` é o que o aluno cola no plano do vídeo, e passa por `estilo(nome, **plano)` antes de
    sair daqui. Com a pasta da marca (cor no tema.css, música no estilos.json), a marca vem primeiro."""
    pasta = Path(marca) if marca else MARCA
    decls = da_marca(pasta)
    novos = [n for n in decls if n not in ESTILOS]
    ESTILOS.update({n: decls[n] for n in novos})   # o estilo da marca de outra pasta, só durante a conta
    try:
        base = estilo(nome)
        saida, grupos = [], set()
        for grupo, pedido, plano in _candidatos(base, _cores_da_marca(pasta), _faixa_da_marca(pasta, decls)):
            if grupo in grupos:
                continue
            try:
                muda = estilo(nome, **copy.deepcopy(plano)) != base
            except (KeyError, TypeError):
                muda = False   # candidato que o catálogo não aceita não vira pedido
            if muda:
                grupos.add(grupo)
                saida.append({"pedido": pedido, "plano": plano})
            if len(saida) == 3:
                break
        return saida
    finally:
        for n in novos:
            ESTILOS.pop(n, None)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Os estilos de edição que existem")
    ap.add_argument("nome", nargs="*", help="o estilo a mostrar inteiro; ou `pedidos <estilo>`, "
                                            "três pedidos de personalização prontos")
    ap.add_argument("--marca", type=Path, help="a pasta da marca (padrão: marca/): cor e música entram nos pedidos")
    args = ap.parse_args()

    if args.nome[:1] == ["pedidos"]:
        if len(args.nome) != 2:
            ap.error("uso: estilo.py pedidos <estilo> [--marca <pasta>]")
        for i, p in enumerate(pedidos(args.nome[1], args.marca), 1):
            print(f"{i}. {p['pedido']}\n   {json.dumps(p['plano'], ensure_ascii=False)}")
        return

    if len(args.nome) > 1:
        ap.error("um estilo por vez")
    if args.nome:
        e = estilo(args.nome[0])
        print(f"{e.nome}  ({e.orientacao}, parte de {e.bruto})")
        print(f"  recursos: {', '.join(e.recursos) or '(nenhum)'}")
        for eixo, valores in e.eixos.items():
            print(f"  {eixo}:")
            for k, v in valores.items():
                print(f"    {k} = {v}")
        return

    print(f"{'estilo':<18} {'quadro':<7} {'bruto':<12} {'corte':<9} recursos")
    for l in catalogo():
        print(f"{l['nome']:<18} {l['orientacao']:<7} {l['bruto']:<12} "
              f"{l['corte']:<9} {', '.join(l['recursos'])}")


if __name__ == "__main__":
    main()
