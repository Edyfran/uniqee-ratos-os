"""Auto-teste da capa. Um comando, uma capa de uma foto que não é de ninguém.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_capa.py

A capa vai pro aluno com a foto dele: nada aqui pode depender do rosto, do quarto
ou das expressões do dono. A foto é uma silhueta desenhada na hora, já sem fundo
(o rembg fica de fora: é lento e baixa modelo no primeiro uso).
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import ff
from capa import W, H, YT_MAX, capa_nick, capa_yt


def _silhueta(out: Path) -> Path:
    """Cabeça e ombros cinza sobre alfa zero, 600×700."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (600, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((190, 60, 410, 330), fill=(150, 120, 100, 255))
    d.rounded_rectangle((60, 380, 540, 760), 120, fill=(30, 30, 34, 255))
    im.save(out)
    return out


def test_a_capa_sai_inteira_da_foto_do_plano(tmp: Path):
    """O bloco `capa` com uma foto qualquer, um ícone `@arquivo` e um quadro de cena
    vira um JPEG 1080×1920, e a foto recortada desce até a borda de baixo."""
    from PIL import Image
    _silhueta(tmp / "eu.png")
    Image.new("RGB", (200, 200), (40, 90, 200)).save(tmp / "icone.png")
    ff.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=720x1280:rate={ff.FPS}:duration=1",
            "-pix_fmt", "yuv420p", str(tmp / "cena.mp4")], quiet=True)
    bloco = {"foto": "eu.png", "titulo": "uma capa|qualquer", "destaque": "qualquer", "topo": "Ferramenta",
             "lados": "@icone.png", "cena": ["cena.mp4", .5, .5], "larg": 900, "ry": 450, "iy": 640,
             "_por_que": "nota, não vai pra peça"}
    # com caminho relativo, como o aluno chama: o file:// da peça não aceita, então a capa resolve antes
    atras = os.getcwd()
    os.chdir(tmp)
    try:
        out = capa_nick(bloco, Path("."), Path("capa.jpg"), Path("trab"))
    finally:
        os.chdir(atras)
    with Image.open(out) as im:
        assert im.size == (W, H) == (1080, 1920), f"a capa saiu {im.size}"
    with Image.open(tmp / "trab" / "recorte-eu.png") as r:
        assert r.height >= 2 * r.width, f"o tronco não esticou: {r.size}"


def test_a_capa_tinteiro_com_letreiro_e_base_que_esmaece(tmp: Path):
    """Pose pronta: a base esmaece (alfa zero na última linha, sem tronco espelhado); letreiro e lado "~" são imagens."""
    from PIL import Image
    if not (AQUI.parents[1] / "v2" / "midia" / "tinteiro").is_dir():
        return  # a capa do Tinteiro é do canal: o kit não leva a letra dela
    _silhueta(tmp / "eu.png")
    Image.new("RGBA", (1200, 300), (232, 174, 79, 255)).save(tmp / "letreiro.png")
    Image.new("RGBA", (300, 300), (40, 90, 200, 255)).save(tmp / "logo.png")
    out = capa_nick({"foto": "eu.png", "base": "esmaece", "titulo": "uma capa|qualquer", "destaque": "qualquer",
                     "letreiro": "@letreiro.png", "lados": "~@logo.png,@logo.png"},
                    tmp, tmp / "capa.jpg", tmp / "trab", peca="g_capa_tinteiro")
    with Image.open(out) as im:
        assert im.size == (W, H), f"a capa saiu {im.size}"
    with Image.open(tmp / "trab" / "recorte-esmaece-eu.png") as r:
        assert r.height < 2 * r.width and r.getchannel("A").getpixel((r.width // 2, r.height - 1)) == 0, "a base não esmaeceu"


def test_a_foto_sai_do_webm_do_avatar(tmp: Path):
    """O aluno com o webm da HeyGen e sem foto: `foto` [vídeo, t] tira o quadro dele, e o webm vem
    com alfa, então o recorte não passa pelo rembg."""
    from PIL import Image
    _silhueta(tmp / "eu.png")
    ff.run(["ffmpeg", "-y", "-loop", "1", "-i", str(tmp / "eu.png"), "-t", "1", "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", str(tmp / "rosto.webm")], quiet=True)
    out = capa_nick({"foto": ["rosto.webm", 0.5], "titulo": "do webm|à capa", "destaque": "à capa"},
                    tmp, tmp / "capa.jpg", tmp / "trab")
    with Image.open(out) as im:
        assert im.size == (W, H), f"a capa saiu {im.size}"
    recortes = list((tmp / "trab").glob("recorte-foto_rosto_*.png"))
    assert recortes, f"a foto não saiu do webm: {list((tmp / 'trab').iterdir())}"
    with Image.open(recortes[0]) as r:
        assert r.mode == "RGBA" and r.height >= 2 * r.width, f"o recorte do quadro: {r.mode} {r.size}"


def test_a_capa_do_youtube_sai_16_9(tmp: Path):
    """A capa do vídeo longo: a foto no terço direito e três desenhos (uma imagem `@arquivo`, um termo grifado e
    um número) viram um JPEG 3840×2160 que cabe nos 2 MB de quem sobe pelo celular."""
    from PIL import Image
    _silhueta(tmp / "eu.png")
    Image.new("RGB", (640, 360), (40, 90, 200)).save(tmp / "print.png")
    bloco = {"foto": "eu.png", "itens": [["termo", "Application/Programming/*Interface*"], ["img", "@print.png"],
                                         ["num", "4 min"]], "seta": 1, "_nota": "não vai pra peça"}
    out = capa_yt(bloco, tmp, tmp / "capa-a.jpg", tmp / "trab")
    with Image.open(out) as im:
        assert im.size == (3840, 2160), f"a capa saiu {im.size}"
    assert out.stat().st_size <= YT_MAX, f"a capa tem {out.stat().st_size} bytes"
    # caminho relativo (o agente roda da raiz e passa `videos/<slug>/...`): a peça lê por file://, que só
    # aceita absoluto; quebrava no `as_uri` do recorte
    import os
    antes = os.getcwd()
    try:
        os.chdir(tmp)
        assert capa_yt(bloco, Path("."), Path("rel") / "capa-b.jpg").exists()
    finally:
        os.chdir(antes)


def test_capa_de_um_comando_le_o_json_e_chama_a_capa(tmp: Path):
    import json
    import capa
    visto, antes = {}, capa.capa_nick
    capa.capa_nick = lambda bloco, pasta, out, **k: visto.update(bloco=bloco, pasta=pasta, out=out) or out
    (tmp / "capa.json").write_text(json.dumps({"capa": {"foto": "eu.jpg"}}), encoding="utf-8")
    try:
        assert capa.main([str(tmp / "capa.json"), str(tmp / "c.jpg")]) == 0
    finally:
        capa.capa_nick = antes
    assert visto["bloco"] == {"foto": "eu.jpg"} and visto["pasta"] == tmp.resolve()


def main() -> int:
    casos = [
        ("a capa sai inteira da foto do plano", test_a_capa_sai_inteira_da_foto_do_plano),
        ("a capa tinteiro: letreiro e base que esmaece", test_a_capa_tinteiro_com_letreiro_e_base_que_esmaece),
        ("a foto sai do webm do avatar", test_a_foto_sai_do_webm_do_avatar),
        ("a capa do YouTube sai 16:9", test_a_capa_do_youtube_sai_16_9),
        ("a capa de um comando", test_capa_de_um_comando_le_o_json_e_chama_a_capa),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        for nome, caso in casos:
            sub = Path(td) / re.sub(r"[^\w-]+", "_", nome)
            sub.mkdir()
            try:
                caso(sub)
                print(f"  ok   {nome}")
            except Exception as e:
                falhas.append((nome, e))
                print(f"  FALHA {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
