"""Ajusta uma imagem ao tamanho de impressão de uma peça da Uniqee (PNG, 300 dpi).

Uso:
  python ajustar.py <imagem> --peca caneca --modo preencher --saida <arquivo.png>
  python ajustar.py <imagem> --largura 21 --altura 9.8 --modo caber --fundo "#ffffff" --saida <arquivo.png>

Modos:
  preencher  ocupa a peça toda e corta a sobra (use --foco pra escolher o que preservar)
  caber      a imagem inteira aparece; o espaço que sobra vira fundo na cor --fundo
"""
import argparse
import sys

from PIL import Image

DPI = 300
PECAS = {  # largura x altura em cm, já com a sobra
    "caneca": (21.0, 9.8),
    "azulejo15": (15.7, 15.7),
    "azulejo20": (20.7, 20.7),
}
FOCOS = {
    "centro": (0.5, 0.5), "topo": (0.5, 0.0), "base": (0.5, 1.0),
    "esquerda": (0.0, 0.5), "direita": (1.0, 0.5),
}


def cm_para_px(cm):
    return round(cm / 2.54 * DPI)


def cor(hexa):
    hexa = hexa.lstrip("#")
    if len(hexa) != 6:
        sys.exit(f"Cor de fundo inválida: #{hexa}. Use o formato #RRGGBB.")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("imagem")
    ap.add_argument("--peca", choices=sorted(PECAS))
    ap.add_argument("--largura", type=float, help="cm")
    ap.add_argument("--altura", type=float, help="cm")
    ap.add_argument("--modo", choices=["preencher", "caber"], default="preencher")
    ap.add_argument("--foco", choices=sorted(FOCOS), default="centro")
    ap.add_argument("--fundo", default="#ffffff")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()

    if a.peca:
        larg_cm, alt_cm = PECAS[a.peca]
    elif a.largura and a.altura:
        larg_cm, alt_cm = a.largura, a.altura
    else:
        sys.exit("Informe --peca ou --largura e --altura em cm.")

    alvo_w, alvo_h = cm_para_px(larg_cm), cm_para_px(alt_cm)
    fundo = cor(a.fundo)

    img = Image.open(a.imagem)
    img.load()
    # transparência vira a cor de fundo (sublimação não imprime transparente)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        base = Image.new("RGB", img.size, fundo)
        base.paste(img, mask=img.split()[-1])
        img = base
    else:
        img = img.convert("RGB")

    src_w, src_h = img.size
    if a.modo == "preencher":
        escala = max(alvo_w / src_w, alvo_h / src_h)
    else:
        escala = min(alvo_w / src_w, alvo_h / src_h)

    novo_w, novo_h = max(1, round(src_w * escala)), max(1, round(src_h * escala))
    redim = img.resize((novo_w, novo_h), Image.LANCZOS)

    if a.modo == "preencher":
        fx, fy = FOCOS[a.foco]
        x = round((novo_w - alvo_w) * fx)
        y = round((novo_h - alvo_h) * fy)
        final = redim.crop((x, y, x + alvo_w, y + alvo_h))
    else:
        final = Image.new("RGB", (alvo_w, alvo_h), fundo)
        final.paste(redim, ((alvo_w - novo_w) // 2, (alvo_h - novo_h) // 2))

    final.save(a.saida, "PNG", dpi=(DPI, DPI))

    # resolução real da imagem original no tamanho impresso
    dpi_real = round(DPI / escala)
    if dpi_real >= 220:
        qualidade = "boa"
    elif dpi_real >= 150:
        qualidade = "aceitável (pode perder um pouco de nitidez)"
    else:
        qualidade = "baixa (vai sair borrada; amplie a imagem antes)"

    print(f"saida: {a.saida}")
    print(f"tamanho: {larg_cm} x {alt_cm} cm = {alvo_w} x {alvo_h} px a {DPI} dpi")
    print(f"original: {src_w} x {src_h} px · ampliacao: {escala:.2f}x")
    print(f"resolucao real no impresso: {dpi_real} dpi · qualidade {qualidade}")


if __name__ == "__main__":
    main()
