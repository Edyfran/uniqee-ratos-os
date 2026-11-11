"""A câmera: o vídeo que sai do lugar antes da legenda (zoom, encolher e descer, tela dividida).

Não é legenda: move o vídeo, e o painel da tela dividida anda na mesma curva (`curva_tela`).
Saiu do captions_viral, que a chama antes de compor. Quem acompanha a câmera (o recorte do
sujeito, a paralaxe do herói) lê a posição dela pelo `zoom_em`, na mesma curva do ffmpeg.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import ff


# TELA DIVIDIDA: painel e câmera num movimento só. Uma curva `p` de 0 a 1 manda
# nos dois; o painel fica em y = -PH + PH·p e a câmera desce atrás da borda dele.
def curva_da_janela(c: dict) -> tuple[float, float]:
    """(entra, sai) da cena. `abre` e `sobe` são nomes antigos de `sai`."""
    sai = c.get("sai", c.get("abre", c.get("sobe", 0.45)))
    return float(c.get("entra", 0.6) or 0), float(sai or 0)


def curva_tela(rel: float, dur: float, entra: float, sai: float) -> float:
    """p do painel: entra em mola curta (back-out c1 1,15, passa de 1 e
    assenta), sai em ease-in-out cúbico. Janela curta encolhe as duas."""
    if dur > 0 and entra + sai > dur:
        k = dur / (entra + sai)
        entra, sai = entra * k, sai * k
    if entra > 0 and rel < entra:
        x = max(0.0, rel) / entra - 1
        return 1 + 2.15 * x ** 3 + 1.15 * x ** 2
    if sai > 0 and rel > dur - sai:
        u = min(1.0, (rel - (dur - sai)) / sai)
        return 1 - (4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2)
    return 1.0


def desce_camera(p: float, ph: float, desce: float, margem: float) -> float:
    """Quanto a câmera desce com o painel em `p`. Ela só sai do lugar depois
    que o painel cobriu `margem` px do alto dela e anda sempre ATRÁS da borda:
    não existe quadro com a câmera à frente do painel, então não existe tarja."""
    pc = min(1.02, max(0.0, (ph * p - margem) / (ph - margem)))
    return desce * pc * ((1 - 0.15 * (1 - pc)) if pc < 1 else 1.0)


def _desce(c: dict) -> tuple[float, float]:
    """`desce`: quanto a pessoa desce no quadro (fração da altura), um número ou [do, ao]. Passa do teto do foco: a
    cena que usa tem de ter algo opaco atrás da pessoa (a placa), porque o alto da fonte acaba e entra preto."""
    d = c.get("desce", 0.0)
    return (float(d[0]), float(d[1])) if isinstance(d, (list, tuple)) else (float(d), float(d))


def moldura_cartao(c: dict, largura: int, altura: int, out: Path) -> Path:
    """A tela dividida do reel editorial, a parte de baixo: o papel cobre tudo do `topo` pra baixo, menos o cartão de
    cantos redondos onde o vídeo aparece. Medidas do e_editorial (editorial.css), em px de 1080x1920; `cor` é o papel
    do painel de cima. A cabeça passa da borda porque o recorte da pessoa fura a peça opaca que fica acima do topo."""
    k = largura / 1080
    topo, raio, lado = (float(c.get(n, v)) * k for n, v in (("topo", 1240), ("raio", 130), ("margem", 18)))
    im = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, topo, largura, altura], fill=c.get("cor", "#FFFFFF"))
    # o furo vai até depois do pé do quadro: os cantos de baixo não existem, o cartão sangra no pé
    d.rounded_rectangle([lado, topo, largura - lado, altura + raio], radius=raio, fill=(0, 0, 0, 0))
    im.save(out)
    return out


def filtro_vf(filtro: str | None, vf: str | None) -> str:
    """A cadeia de filtros do segmento, pra encaixar entre `[0:v]` e a moldura. Só o caminho do `-vf` (zoom ou escala)
    serve: a tela dividida da `janela` já é um filter_complex."""
    if filtro or not vf:
        raise ValueError("`cartao` vale com `zoom` (e `desce`) ou `escala`, não com `janela`")
    return vf


def camera_cenas(video: Path, cenas: list[dict], dur: float, fps: int,
                 largura: int, altura: int, tmp: Path) -> Path:
    """Pré-passo: move a CÂMERA antes de qualquer composição.

    Tela dividida não é painel por cima do vídeo — é a câmera saindo do lugar.
    Com painel de 40% e o cabelo dele começando aos 26% da tela, sobrepor sempre
    vai recortar cabelo e armação de óculos, e o recorte serrilha. Encolher e
    descer a câmera deixa o topo limpo e o corte desaparece.

    Cada cena: {t0, t1, escala, dy} — escala 1 é o quadro cheio.
    """
    if not cenas:
        return video

    # Por SEGMENTO, não por expressão de tempo. Escala variável no meio do
    # stream muda a dimensão do frame e o codificador recusa, mesmo com `pad`
    # normalizando depois. Cortar, transformar cada pedaço com valor constante
    # e concatenar é mais código e funciona.
    #
    # TODO segmento leva `fps=` na frente. Sem isso, o trecho com zoompan sai na
    # taxa pedida e os outros na taxa da fonte; a concatenação some com a
    # diferença e, num bruto de 25fps, a legenda dos 53s aparece aos 50.
    cortes = sorted(cenas, key=lambda x: x["t0"])
    zooms: dict[tuple[float, float], list] = {}
    janelas: dict[tuple[float, float], list] = {}
    cartoes: dict[tuple[float, float], dict] = {}
    faixas: list[tuple[float, float, float, float]] = []
    t = 0.0
    for c in cortes:
        if c["t0"] > t:
            faixas.append((t, min(float(c["t0"]), dur), 1.0, 0.0))
        a, b = max(t, float(c["t0"])), min(float(c["t1"]), dur)
        esc, dy = float(c.get("escala", 1.0)), float(c.get("dy", 0))
        faixas.append((a, b, esc, dy))
        if c.get("zoom"):
            # o terceiro item é o andamento e o quarto é o foco; escritos à
            # parte no plano pra não obrigar quem já tem `[1.0, 1.08]` a mexer
            zooms[(a, b)] = (list(c["zoom"])[:2] + [c.get("ease", "sine")]
                             + [c.get("foco", (0.0, 0.0))] + [int(c.get("borrao") or 0)] + [_desce(c)])
        if c.get("janela"):
            janelas[(a, b)] = (*c["janela"], *curva_da_janela(c))
        if c.get("cartao"):
            cartoes[(a, b)] = c["cartao"] if isinstance(c["cartao"], dict) else {}
        t = min(float(c["t1"]), dur)
    if t < dur:
        faixas.append((t, dur, 1.0, 0.0))

    # a câmera a 25 (o HeyGen) ia a 30 por cópia: 5 trancos por segundo no rosto. ff.taxa mistura
    taxa = ff.taxa(ff.probe(video).fps, fps)
    partes = []
    for i, (a0, a1, esc, dy) in enumerate(faixas):
        # menos de um frame não é cena: `fps=` não produz quadro nenhum e o
        # segmento sai só com áudio. Concatenado, o container perde o vídeo de
        # referência e a duração declarada infla (14s viraram 45s uma vez).
        if a1 - a0 < 1.0 / fps:
            continue
        # Quantos quadros ESTE segmento ocupa na linha do tempo final. Vem da
        # diferença entre os índices absolutos, não da duração: com `-t` cada
        # trecho arredonda por conta própria e o erro acumula — no corte s4e5 a
        # janela acabava 0.13s depois do painel que a preenchia, e nesse vão
        # aparecia a tarja preta da tela dividida.
        quadros = int(round(a1 * fps)) - int(round(a0 * fps))
        p_seg = tmp / f"cam{i:03d}.mp4"
        filtro = None                     # filter_complex, quando o -vf não basta
        vf = None
        zm = zooms.get((a0, a1))
        if zm:
            # perspective devolve dimensão FIXA enquanto amplia — é o que permite
            # zoom de verdade. Com scale+pad a dimensão varia por frame e o
            # codificador recusa, que foi o que me obrigou a segmentar. Não o
            # zoompan: ele arredonda a janela pro pixel, e o zoom lento parava
            # 12 a 17 quadros em 120 (tranco a 15 Hz); o perspective amostra em
            # ponto flutuante, 0 parados, ao dobro do custo (medido em 03/10).
            n_fr = max(1, quadros)
            z0, z1 = float(zm[0]), float(zm[1])
            # `borrao`: o borrão de movimento de verdade no crash zoom. A cena
            # anda a N vezes a taxa e cada quadro é a média dos N instantes do
            # obturador (tmix), não um blur parado por cima
            sub = zm[4] if len(zm) > 4 and zm[4] > 1 else 1
            n_fr *= sub
            u = f"(on/{n_fr})"
            # O andamento do movimento, e não só o quanto ele anda.
            #
            # Linear era o padrão, e é por isso que todo zoom parecia o mesmo:
            # velocidade constante faz o movimento ANUNCIAR que começou e que
            # parou. `sine` entra e sai macio — a câmera já está andando quando
            # você percebe, e já parou quando você olha.
            #
            # `solta` desacelera no fim e serve pra chegada; `dura` acelera e
            # serve pra sair de uma peça. `reta` existe só pra quando o zoom
            # cobre um corte e qualquer curva denunciaria a emenda.
            prog = {
                "reta":  u,
                "sine":  f"(0.5*(1-cos(PI*{u})))",
                "solta": f"(1-pow(1-{u},2))",
                "dura":  f"(pow({u},2))",
                "crava": f"(1-pow(1-min(1,{u}),4))",
            }.get(str(zm[2] if len(zm) > 2 else "sine"), f"(0.5*(1-cos(PI*{u})))")
            # A taxa VEM ANTES: o `on` conta quadro, e numa fonte de 25fps o
            # zoom de 30 quadros acabaria depois da cena.
            # O FOCO desloca o recorte do centro. Dois enquadramentos do mesmo
            # take, cortados secos, lêem como duas câmeras — que é o jeito mais
            # barato de fazer acontecer alguma coisa num plano parado.
            #
            # O deslocamento é limitado pelo zoom: em 1.2 sobram 8% de imagem de
            # cada lado, e pedir 15% encosta a borda preta no quadro. Por isso
            # ele é aparado aqui e não confiado a quem escreve o plano.
            fx, fy = (list(zm[3]) + [0, 0])[:2] if len(zm) > 3 else (0.0, 0.0)
            teto = (1 - 1 / max(z0, z1)) / 2
            fx = max(-teto, min(teto, float(fx)))
            fy = max(-teto, min(teto, float(fy)))
            d0, d1 = zm[5] if len(zm) > 5 else (0.0, 0.0)
            # o retângulo da fonte que enche o quadro: meia janela pra cada lado
            # do centro (deslocado pelo foco)
            z = f"({z0:.4f}+({z1 - z0:.4f})*{prog})"
            x0, x1 = f"W/2-W/2/{z}+({fx:.4f})*W", f"W/2+W/2/{z}+({fx:.4f})*W"
            # `desce` (fora do teto do foco): a pessoa desce essa fração do quadro; o que sobra acima fica vazio
            dz = f"(({d0:.4f}+({d1 - d0:.4f})*{prog})*H/{z})"
            y0, y1 = f"H/2-H/2/{z}+({fy:.4f})*H-{dz}", f"H/2+H/2/{z}+({fy:.4f})*H-{dz}"
            vf = (f"{taxa},{f'fps={fps * sub},' if sub > 1 else ''}"
                  f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':"
                  f"x2='{x0}':y2='{y1}':x3='{x1}':y3='{y1}':interpolation=cubic:eval=frame,"
                  f"{f'tmix=frames={sub},fps={fps},' if sub > 1 else ''}"
                  f"scale={largura}:{altura}:flags=lanczos")
        elif janelas.get((a0, a1)):
            # Tela dividida: a câmera em largura cheia, DESLOCADA pra baixo — o
            # que passa do pé some. Encolher deixaria barra preta dos lados.
            #
            # Sem `crop`: recorte de altura variável o codificador recusa, e foi
            # isso que virou escada. O quadro inteiro, em tamanho fixo, é
            # posicionado por `overlay` sobre uma tela do tamanho final, com o y
            # quadro a quadro. Os y vêm da MESMA função que desenha o painel
            # (`curva_tela`), então os dois não descolam. A `janela` diz onde a
            # câmera assenta: a linha `jy` da fonte fica no topo da faixa.
            #
            # A tentativa anterior saía toda preta; o que a faz compor: o fundo
            # com `r=` e `d=`, o vídeo com `setpts=PTS-STARTPTS`, `eval=frame`
            # e `shortest=1`.
            jy, jh, ent, sai = janelas[(a0, a1)]
            ph = altura * (1 - float(jh))
            desce = altura * (1 - float(jy) - float(jh))
            margem = 120 * largura / 1080
            parado = int(desce)
            expr = str(parado)
            for k in reversed(range(quadros)):
                yk = int(desce_camera(curva_tela(k / fps, a1 - a0, ent, sai),
                                      ph, desce, margem))
                # pelo `t` do fundo, não pelo `n`: o `n` do overlay chega
                # adiantado um quadro, e a câmera descia antes do painel
                if yk != parado:
                    expr = f"if(eq(round(t*{fps}),{k}),{yk},{expr})"
            filtro = (f"color=c=black:s={largura}x{altura}:r={fps}:"
                      f"d={quadros / fps + 1:.3f}[bg];"
                      f"[0:v]{taxa},setpts=PTS-STARTPTS[v];"
                      f"[bg][v]overlay=x=0:y='{expr}':eval=frame:shortest=1,"
                      f"format={ff.PIX_FMT}[o]")
        elif abs(esc - 1.0) < 1e-3 and abs(dy) < 1e-3:
            vf = taxa
        else:
            lw = int(largura * esc) // 2 * 2
            lh = int(altura * esc) // 2 * 2
            vf = (f"{taxa},scale={lw}:{lh},pad={largura}:{altura}:"
                  f"{(largura - lw) // 2}:{int(dy * altura)}:color=black")
        extra = []
        cart = cartoes.get((a0, a1))
        if cart is not None:
            # a moldura do cartão entra por cima do quadro já movido (use com `zoom` + `desce`, que põem a cabeça lá)
            png = moldura_cartao(cart, largura, altura, tmp / f"cartao{i:03d}.png")
            extra = ["-loop", "1", "-i", str(png)]
            filtro = (f"[0:v]{filtro_vf(filtro, vf)}[m];[m][1:v]overlay=0:0:format=auto,"
                      f"format={ff.PIX_FMT}[o]")
        ff.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{a0:.3f}",
             "-i", str(video), *extra,
             *(["-filter_complex", filtro, "-map", "[o]"] if filtro else ["-vf", vf]),
             "-frames:v", str(quadros),
             # SEM ÁUDIO. Cada segmento nasce de uma busca rápida, e busca
             # rápida em áudio é aproximada: sessenta segmentos concatenados
             # acumulam a aproximação e o som anda em relação à imagem. O áudio
             # final vem do arquivo original, que nunca foi cortado.
             "-an",
             # sem perda: o segmento só existe até o encode da legenda, que é o que conta
             *ff.args_sem_perda(),
             str(p_seg)], check=True)
        partes.append(p_seg)

    lista = tmp / "cam_lista.txt"
    lista.write_text("".join(f"file '{x}'\n" for x in partes), encoding="utf-8")
    saida = tmp / "camera.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lista), "-c", "copy", str(saida)], check=True)
    return saida


# os andamentos do `camera_cenas`, em Python: quem acompanha a câmera (o recorte
# do sujeito, a paralaxe do herói) tem que andar na MESMA curva que o ffmpeg
_ANDAMENTO = {
    "reta": lambda u: u,
    "sine": lambda u: 0.5 * (1 - math.cos(math.pi * u)),
    "solta": lambda u: 1 - (1 - u) ** 2,
    "dura": lambda u: u ** 2,
    "crava": lambda u: 1 - (1 - min(1.0, u)) ** 4,
}


def zoom_em(t: float, cenas: list[dict], fps: int = 30) -> tuple[float, tuple[float, float]]:
    """(zoom, foco) da câmera no instante t, contado em quadros como o ffmpeg conta."""
    for c in cenas:
        if c.get("zoom") and float(c["t0"]) <= t < float(c["t1"]):
            a, b = float(c["t0"]), float(c["t1"])
            n = max(1, round(b * fps) - round(a * fps))
            u = (round(t * fps) - round(a * fps)) / n
            z0, z1 = float(c["zoom"][0]), float(c["zoom"][1])
            prog = _ANDAMENTO.get(str(c.get("ease", "sine")), _ANDAMENTO["sine"])(max(0.0, u))
            foco = tuple(c.get("foco", (0.0, 0.0)))[:2]
            if c.get("desce"):
                d0, d1 = _desce(c)
                foco += (d0 + (d1 - d0) * prog,)
            return z0 + (z1 - z0) * prog, foco
    return 1.0, (0.0, 0.0)


def na_camera(alfa: np.ndarray, z: float, foco: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    """O recorte do sujeito tirado do quadro PARADO, levado pra onde a câmera foi.
    Recortar o quadro já ampliado custaria o matte de novo a cada plano."""
    if abs(z - 1.0) < 1e-4 and not any(foco):
        return alfa
    H, W = alfa.shape
    teto = (1 - 1 / z) / 2
    fx, fy = (max(-teto, min(teto, float(v))) for v in foco[:2])
    desce = float(foco[2]) if len(foco) > 2 else 0.0      # terceiro valor do foco: a descida, fora do teto
    x0, y0 = W / 2 - W / 2 / z + fx * W, H / 2 - H / 2 / z + fy * H - desce * H / z
    im = Image.fromarray(alfa).transform((W, H), Image.EXTENT, (x0, y0, x0 + W / z, y0 + H / z),
                                         Image.BILINEAR)
    return np.array(im)
