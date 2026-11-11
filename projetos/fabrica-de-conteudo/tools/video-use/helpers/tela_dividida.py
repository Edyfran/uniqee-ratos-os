"""A tela dividida no vídeo de celular: um trecho do take com o visual num painel em cima e a
pessoa recortada na frente do cartão de baixo. Fase (a) do plano visual (`docs/kit/plano-visual.md`).

    python tela_dividida.py take.mp4 --ini 10 --fim 15 --img print.png --saida saida.mp4 [--leg "Prova na tela"]
    python tela_dividida.py take.mp4 --ini 10 --fim 15 --img print.png --saida saida.mp4 \\
        --seg "0,2,dividida;2,3.5,cheia;3.5,5,rosto"

Os quatro layouts (`dividida`, `cheia`, `rosto`, `cartao`) vêm da peça `e_dividida` da biblioteca v2; a pessoa vem
do `recorte.py` e entra ENTRE as duas camadas da peça, só nos trechos `dividida`. O `cartao` é a saída quando o recorte
não presta (`recorte.confere`): o vídeo da pessoa INTEIRO, com o fundo do bruto, no vão do cartão de baixo. Tempos de `--seg`
em segundos do TRECHO (0 = `--ini`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

import ff
import recorte

V2 = Path(__file__).resolve().parents[2] / "v2"
LAYOUTS = ("dividida", "cheia", "rosto", "cartao")
# o vão do cartão do layout `cartao` (a mesma geometria da peça e_dividida): x, topo, largura e a altura que cabe no quadro
CARTAO_X, CARTAO_Y, CARTAO_L, CARTAO_H = 80, 1060, 920, 1920 - 1060
CARTAO_CABELO = 130      # o cabelo cai a 130 px do topo do cartão


def _v2():
    if str(V2) not in sys.path:
        sys.path.insert(0, str(V2))
    import v2
    return v2


def trechos(seg: str, dur: float, lay: str = "dividida") -> list[tuple[float, float, str]]:
    """`"0,2,dividida;2,5,cheia"` -> [(0.0, 2.0, 'dividida'), (2.0, 5.0, 'cheia')]; vazio vale o `lay` o trecho todo."""
    if not seg:
        seg = f"0,{dur},{lay}"
    out = []
    for s in seg.split(";"):
        a, b, l = s.split(",")
        if l not in LAYOUTS:
            raise ValueError(f"layout '{l}' não existe: {', '.join(LAYOUTS)}")
        out.append((float(a), float(b), l))
    return out


def cartao_y0(meta: dict | None) -> int:
    """A linha do vídeo (já em 920 de largura) onde o recorte do cartão começa: o cabelo cai a CARTAO_CABELO do topo
    do cartão. Sem medida, pega o cabelo onde os takes de celular costumam tê-lo (12% da altura)."""
    k = CARTAO_L / 1080
    topo = (meta or {}).get("topo", 0.12 * 1920)
    return int(min(max(0, round(topo * k) - CARTAO_CABELO), 1920 * k - CARTAO_H))


def grafo(seg: list[tuple[float, float, str]], enq: dict | None, meta: dict | None, fps: int = ff.FPS) -> str:
    """O filtro que põe tras, pessoa (só nas `dividida`) e frente sobre o take. Entradas: 0 take, 1 tras,
    2 o take de novo (vira a pessoa), 3 a máscara dela, 4 frente. Nas `cartao` o próprio take, em 920 de largura,
    entra no vão que a `tras` deixa aberto."""
    quando = "+".join(f"between(t,{a:.3f},{b - .001:.3f})" for a, b, l in seg if l == "dividida")
    cart = "+".join(f"between(t,{a:.3f},{b - .001:.3f})" for a, b, l in seg if l == "cartao")
    base = f"[0:v]fps={fps},scale=1080:1920,setsar=1"
    base += (f",split[b0][k0];[k0]scale={CARTAO_L}:-2:flags=lanczos,crop={CARTAO_L}:{CARTAO_H}:0:{cartao_y0(meta)}[k];"
             f"[b0][k]overlay={CARTAO_X}:{CARTAO_Y}:enable='{cart}'[b];") if cart else "[b];"
    if not quando:      # sem `dividida` não há pessoa recortada: entradas 0 take, 1 tras, 2 frente
        return (f"{base}[b][1:v]overlay=format=auto[b1];"
                f"[b1][2:v]overlay=format=auto,format={ff.PIX_FMT}[v]")
    s = enq["escala"]
    return (f"{base}"
            f"[b][1:v]overlay=format=auto[b1];"
            f"{recorte.grafo_alfa(2, 3, meta, 'p0')};"
            f"[p0]fps={fps},scale=trunc({meta['largura']}*{s:.5f}/2)*2:trunc({meta['altura']}*{s:.5f}/2)*2:flags=lanczos,format=yuva444p10le[p];"
            f"[b1][p]overlay={enq['x']:.1f}:{enq['y']:.1f}:format=auto:enable='{quando}'[b2];"
            f"[b2][4:v]overlay=format=auto,format={ff.PIX_FMT}[v]")


def _monta_peca(take: Path, ini: float, fim: float, saida: Path, painel: dict, trab: Path, fps: int, tema: str | None = None) -> dict:
    """Tela cheia por uma peça da biblioteca (o print: `r_print`) em vez de imagem: a peça opaca sobre o take, sem pessoa."""
    painel = dict(painel)
    peca = painel.pop("peca")
    pq = painel.pop("pq", "")
    dur = fim - ini
    if "img" in painel:
        painel["img"] = Path(painel["img"]).resolve().as_uri()
    arq = trab / f"{peca}.mp4"
    _v2().render(peca, [f"dur={dur:.3f}", "chao=1", *[f"{k}={v}" for k, v in urllib.parse.parse_qsl(pq, keep_blank_values=True)], *[f"{k}={v}" for k, v in painel.items()]], arq, alfa=False, tema=tema)
    arq.with_suffix(".json").unlink(missing_ok=True)
    saida.parent.mkdir(parents=True, exist_ok=True)
    ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ini}", "-t", f"{dur}", "-i", take, "-i", arq,
            "-filter_complex", f"[0:v]fps={fps},scale=1080:1920,setsar=1[b];[1:v]fps={fps},scale=1080:1920,setsar=1[p];"
                               f"[b][p]overlay=format=auto,format={ff.PIX_FMT}[v]",
            "-map", "[v]", "-map", "0:a?", *ff.args_video("final", fps), *ff.args_audio(),
            "-t", f"{dur}", "-movflags", "+faststart", saida], quiet=True)
    return {"meta": None, "enquadra": None, "saida": str(saida), "camadas": {}}


def caixa_da_peca(painel: dict) -> tuple[float, float] | None:
    """Onde a peça de tela cheia ocupa a tela 1080x1920 (y de cima, y de baixo), medido no navegador com os parâmetros
    da batida (`v2.mede`). A legenda nesses trechos fica fora dessa faixa. Sem medida (peça sem caixa, erro): `None`."""
    try:
        q = {**dict(urllib.parse.parse_qsl(painel.get("pq", ""), keep_blank_values=True)),
             **{k: (Path(v).resolve().as_uri() if k == "img" else v) for k, v in painel.items() if k not in ("peca", "pq")}}
        r = _v2().mede([(painel["peca"], q, "1080x1920")])[0]
        c = r.get("caixa")
        return (float(c["y"]), float(c["y"] + c["h"])) if c else None
    except Exception:      # medir não derruba o vídeo: a legenda fica onde o estilo a põe
        return None


def fundo_da_legenda(parte: Path, caixa: tuple[float, float]) -> float | None:
    """A luminância (0..1) do que fica atrás da legenda numa parte `cheia`, medida no quadro do meio, na faixa onde a legenda
    senta (fora da caixa da peça). A legenda usa o número pra ter contraste com o fundo. Sem medida: `None` (a cor do estilo fica)."""
    try:
        import numpy as np
        import captions_viral as cv
        y0, y1 = cv.faixa_da_legenda(cv.layout_do_vao(*caixa))      # sem vão, a legenda fica na faixa do estilo
        bruto = ff.run(["ffmpeg", "-v", "error", "-ss", f"{ff.dur(parte) / 2:.3f}", "-i", parte, "-frames:v", "1", "-vf", "scale=1080:1920",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture=True, binario=True, quiet=True).stdout
        return round(cv.luminancia_do_vao(np.frombuffer(bruto, np.uint8).reshape(1920, 1080, 3), y0, y1), 4)
    except Exception:      # medir não derruba o vídeo: a legenda fica com a cor do estilo
        return None


AVISO_CARTAO = "recorte fraco: usei a pessoa no cartão"


def monta(take: Path, ini: float, fim: float, img: Path | None, saida: Path, seg: str = "",
          leg: str = "", trab: Path | None = None, painel: dict | None = None, fps: int = ff.FPS, tema: str | None = None,
          forcar_cartao: bool = False) -> dict:
    """Monta o trecho e devolve o que mediu: meta do recorte, enquadramento, os caminhos das camadas e os `tempos` (s).
    `painel` ({"img"|"txt","tag"|"num","suf","rot"}) é o que a peça mostra no lugar de `img`: o que o `acha.py` devolve.
    `tema` (claro|tinta|marca) é o do estilo do vídeo: vai às peças `e_dividida` e `r_print`, e com `marca` elas pegam as quatro
    cores e a forma do estilo (o chão, a letra, o bloco e o marcador).
    A trava de qualidade: se a máscara do trecho não passa em `recorte.confere` (ou `forcar_cartao`), o layout `dividida` vira
    `cartao` (a pessoa inteira no cartão) e o retorno traz `aviso`."""
    take, saida = Path(take), Path(saida)
    dur = fim - ini
    trechos_ = trechos(seg, dur)
    tempos = {"recorte": 0.0, "pecas": 0.0, "ffmpeg": 0.0}
    t0_ = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        trab = Path(trab or td)
        trab.mkdir(parents=True, exist_ok=True)
        if (painel or {}).get("peca") and all(l not in ("dividida", "cartao") for _, _, l in trechos_):      # a peça por inteiro, na tela toda
            r = _monta_peca(take, ini, fim, saida, painel, trab, fps, tema)
            return {**r, "tempos": {**tempos, "pecas": round(time.perf_counter() - t0_, 2)}, "aviso": ""}
        pessoa = any(l == "dividida" for _, _, l in trechos_)
        cartao = any(l == "cartao" for _, _, l in trechos_)
        meta, aviso, pergunta = None, "", ""
        if pessoa or cartao:       # o cartão só precisa de onde está o cabelo: 2 qps bastam
            meta = recorte.recorta_pessoa(take, ini, fim, trab / "mascara.mov", **({} if pessoa else {"taxa": 2}))
            tempos["recorte"] = round(time.perf_counter() - t0_, 2)
        if pessoa:
            ok, motivo = recorte.confere(meta)
            if not ok and not forcar_cartao:
                pergunta = recorte.pergunta(motivo)       # a linha pro agente: ele pergunta ao aluno; sem resposta, cartão
                print(pergunta, flush=True)
            if forcar_cartao or not ok:
                aviso = AVISO_CARTAO + (f" ({motivo})" if motivo else "")
                trechos_ = [(a, b, "cartao" if l == "dividida" else l) for a, b, l in trechos_]
                pessoa = False
        enq = recorte.enquadra(meta) if pessoa else None
        pares = [f"dur={dur:.3f}", "seg=" + ";".join(f"{a},{b},{l}" for a, b, l in trechos_)]
        painel = dict(painel or {})
        if img:
            painel["img"] = img
        if "img" in painel:
            painel["img"] = Path(painel["img"]).resolve().as_uri()
        pares += [f"{k}={v}" for k, v in painel.items()]
        if leg:
            pares.append(f"leg={leg}")
        v2 = _v2()
        camadas = {}
        t1_ = time.perf_counter()
        for c in ("tras", "frente"):
            camadas[c] = trab / f"ed.{c}.mov"
            v2.render("e_dividida", pares, camadas[c], camada=c, tema=tema)
            camadas[c].with_suffix(".json").unlink(missing_ok=True)
        tempos["pecas"] = round(time.perf_counter() - t1_, 2)
        saida.parent.mkdir(parents=True, exist_ok=True)
        entradas = ["-ss", f"{ini}", "-t", f"{dur}", "-i", take, "-i", camadas["tras"]]
        entradas += (["-ss", f"{ini}", "-t", f"{dur}", "-i", take, "-i", meta["mascara"]] if pessoa else []) + ["-i", camadas["frente"]]
        t2_ = time.perf_counter()
        ff.run(["ffmpeg", "-y", "-v", "error", *entradas,
                "-filter_complex", grafo(trechos_, enq, meta, fps),
                "-map", "[v]", "-map", "0:a?", *ff.args_video("final", fps), *ff.args_audio(),
                "-t", f"{dur}", "-movflags", "+faststart", saida], quiet=True)
        tempos["ffmpeg"] = round(time.perf_counter() - t2_, 2)
        if trab == Path(td):
            camadas = {}
    return {"meta": meta, "enquadra": enq, "saida": str(saida), "camadas": {k: str(v) for k, v in camadas.items()},
            "tempos": tempos, "aviso": aviso, "pergunta": pergunta, "layouts": [l for _, _, l in trechos_]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("take", type=Path)
    p.add_argument("--ini", type=float, default=0.0)
    p.add_argument("--fim", type=float)
    p.add_argument("--img", type=Path)
    p.add_argument("--visual", type=Path, help="`visual.json` resolvido + `--achados`: monta o vídeo todo (o passo da fábrica)")
    p.add_argument("--achados", type=Path)
    p.add_argument("--decisoes", type=Path, help="o `decisoes.json` do storyboard: a batida tirada pelo número não entra")
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--tema", default=None, help="o tema do estilo (claro|tinta|marca): vai às peças")
    p.add_argument("--seg", default="")
    p.add_argument("--leg", default="")
    p.add_argument("--trab", type=Path, help="guarda a máscara e as camadas aqui")
    a = p.parse_args()
    if a.visual:
        if not a.achados or not a.trab:
            sys.exit("--visual pede --achados e --trab")
        ach = json.loads(a.achados.read_text(encoding="utf-8"))
        if a.decisoes and a.decisoes.exists():
            fica = json.loads(a.decisoes.read_text(encoding="utf-8")).get("visual")
            if fica is not None:
                ach = [x for x in ach if x["id"] in {v["id"] for v in fica}]
        print(json.dumps(monta_visual(a.take, ach, a.saida, a.trab, a.tema)))
        return
    if a.fim is None:
        sys.exit("falta --fim")
    r = monta(a.take, a.ini, a.fim, a.img, a.saida, a.seg, a.leg, a.trab, tema=a.tema)
    print(f"wrote {r['saida']}" + (f"  (recorte {r['meta']['ms_quadro']:.0f} ms/quadro, escala {r['enquadra']['escala']:.3f})" if r["enquadra"] else "")
          + (f"\naviso: {r['aviso']}" if r["aviso"] else ""))


def _snap(t: float, fps: int = ff.FPS) -> float:
    """O tempo no quadro mais perto: as partes somam um número inteiro de quadros e a emenda não deixa fresta."""
    return round(t * fps) / fps


def plano_de_partes(batidas: list[dict], dur: float, fps: int = ff.FPS) -> list[dict]:
    """O vídeo cortado em partes seguidas: cada batida `dividida`/`cheia` é uma parte montada; o que fica entre elas (e o
    `rosto`) segue como está. `[{"t0", "t1", "layout" ou None, "batida"}]`."""
    partes, t = [], 0.0
    for b in sorted((b for b in batidas if b["layout"] in ("dividida", "cheia")), key=lambda b: b["t0"]):
        a, z = _snap(b["t0"], fps), min(_snap(b["t1"], fps), _snap(dur, fps))
        if z - a < 1 / fps or a < t:
            continue
        if a > t:
            partes.append({"t0": t, "t1": a, "layout": None})
        partes.append({"t0": a, "t1": z, "layout": b["layout"], "batida": b})
        t = z
    if _snap(dur, fps) > t:
        partes.append({"t0": t, "t1": _snap(dur, fps), "layout": None})
    return partes


def _hash_de(*arqs: Path) -> str:
    h = hashlib.blake2b(digest_size=8)
    for a in arqs:
        h.update(Path(a).read_bytes() if Path(a).is_file() else b"-")
    return h.hexdigest()


def _codigo(peca: str = "") -> str:
    """O que, fora o pedido, muda o resultado de um trecho: este módulo, o recorte, o ff, a peça `e_dividida`, o núcleo da
    biblioteca e a peça do painel. Mexeu em qualquer um, o cache velho não vale."""
    A = Path(__file__).resolve().parent
    nuc = sorted((V2 / "nucleo").glob("direcao-v2.*"))
    return _hash_de(Path(__file__), A / "recorte.py", A / "ff.py", V2 / "pecas" / "e_dividida.html", *nuc,
                    *([V2 / "pecas" / f"{peca}.html"] if peca else []))


def chave_do_trecho(video: Path, p: dict, fps: int, tema: str | None, painel: dict | None, forcar: bool) -> str:
    """A chave de um trecho do vídeo cortado: o take (o conteúdo, como o cache do recorte), a janela, o layout, o que a batida
    mostra (a imagem pelo conteúdo, não pelo caminho), o tema, o modelo do recorte e o código. Mesma chave, mesmo render."""
    import cena
    st = Path(video).stat()
    pedido = {"take": cena._resumo(str(Path(video).resolve()), st.st_size, st.st_mtime_ns), "t0": round(p["t0"], 4), "t1": round(p["t1"], 4),
              "layout": p["layout"], "fps": fps, "versao": 1}
    if p["layout"]:
        pn = dict(painel or {})
        pedido.update(tema=tema, forcar=forcar, recorte=[recorte.MODELO, recorte.TAXA, recorte.VERSAO], codigo=_codigo(pn.get("peca", "")),
                      painel={k: (_hash_de(Path(v)) if k == "img" and Path(str(v)).is_file() else v) for k, v in sorted(pn.items())})
    return hashlib.blake2b(json.dumps(pedido, sort_keys=True, default=str).encode(), digest_size=12).hexdigest()


def monta_visual(video: Path, achados: list[dict], saida: Path, trab: Path, tema: str | None = None) -> dict:
    """O vídeo cortado com o visual em cada batida `dividida`/`cheia` (o `achados.json` do `acha.py`). Cada batida passa
    por `monta` (o recorte da pessoa só nas `dividida`, e em cache); o resto é o take cortado no mesmo codec; a emenda é
    a `junta.py`, que copia quando as partes batem. Devolve os tempos pro relatório.

    Cada trecho (batida ou corte) fica em `trab/trechos/<chave>.mp4`, com a chave do conteúdo (`chave_do_trecho`): editar uma
    ou duas batidas refaz só elas, e o que sobrou de chave velha é apagado no fim. A trava de qualidade é do VÍDEO: se a
    máscara de qualquer `dividida` não passa em `recorte.confere`, todas viram `cartao` (um vídeo, um layout de pessoa)."""
    import junta
    video, saida, trab = Path(video), Path(saida), Path(trab)
    trab.mkdir(parents=True, exist_ok=True)
    dur = ff.dur(video)
    ach = {a["id"]: a for a in achados if a["status"] != "rosto"}
    caixas = [{"layout": a["layout"], "t0": a["t0"], "t1": a["t1"], "id": a["id"]} for a in ach.values()]
    fps = round(ff.probe(video).fps)
    partes = plano_de_partes(caixas, dur, fps)
    t_ini = time.perf_counter()
    # a trava: mede a máscara de cada batida `dividida` (em cache: o `monta` a reusa) antes de montar qualquer uma
    motivos, t_rec, pergunta = [], 0.0, ""
    for p in partes:
        if p["layout"] == "dividida":
            a = ach[p["batida"]["id"]]
            tr = time.perf_counter()
            meta = recorte.recorta_pessoa(video, p["t0"], p["t1"], trab / f"b{a['id']}" / "mascara.mov")
            t_rec += time.perf_counter() - tr
            ok, motivo = recorte.confere(meta)
            if not ok:
                motivos.append(f"batida {a['id']}: {motivo}")
                if len(motivos) == 1:
                    pergunta = recorte.pergunta(motivo)
    forcar = bool(motivos)
    if forcar:
        print(pergunta, flush=True)       # uma linha só pro vídeo todo: o agente pergunta ao aluno; sem resposta, cartão
    pasta = trab / "trechos"
    pasta.mkdir(exist_ok=True)
    arqs, usados, feitos, tempos = [], set(), 0, {"recorte": 0.0, "pecas": 0.0, "ffmpeg": 0.0}
    for p in partes:
        a = ach[p["batida"]["id"]] if p["layout"] else None
        ch = chave_do_trecho(video, p, fps, tema, a["painel"] if a else None, forcar)
        arq = pasta / f"{ch}.mp4"
        usados.add(arq.name)
        arqs.append(arq)
        if arq.exists() and arq.stat().st_size > 0:
            continue
        tmp = pasta / f"{ch}.tmp.mp4"
        feitos += 1
        if p["layout"] is None:
            t0_ = time.perf_counter()
            ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{p['t0']:.4f}", "-t", f"{p['t1'] - p['t0']:.4f}", "-i", video,
                    "-vf", f"fps={fps},scale=1080:1920,setsar=1", *ff.args_video("final", fps), *ff.args_audio(),
                    "-movflags", "+faststart", tmp], quiet=True)
            tempos["ffmpeg"] += time.perf_counter() - t0_
        else:
            r = monta(video, p["t0"], p["t1"], None, tmp, seg=f"0,{p['t1'] - p['t0']:.3f},{p['layout']}", trab=trab / f"b{a['id']}",
                      painel=a["painel"], fps=fps, tema=tema, forcar_cartao=forcar)
            for k, v in r["tempos"].items():
                tempos[k] += v
        tmp.replace(arq)
    for velho in pasta.iterdir():      # órfãos: chave que este plano não usa mais
        if velho.name not in usados:
            velho.unlink(missing_ok=True)
    # onde a pessoa está sob a legenda: a `captions_viral.py --dividida` põe a legenda desses trechos acima do cabelo (a `cartao`
    # tem a mesma zona); `[t0, t1, y0, y1]` na cheia com peça (a legenda fica fora da caixa dela)
    saidas = [[round(p["t0"], 3), round(p["t1"], 3)] for p in partes if p["layout"] in ("dividida", "cartao")]
    for p, arq in zip(partes, arqs):
        if p["layout"] == "cheia" and (pn := ach[p["batida"]["id"]]["painel"]).get("peca") and (cx := caixa_da_peca(pn)):
            fundo = fundo_da_legenda(arq, cx)
            saidas.append([round(p["t0"], 3), round(p["t1"], 3), round(cx[0]), round(cx[1]), *([] if fundo is None else [fundo])])
    (trab / "dividida.json").write_text(json.dumps(saidas), encoding="utf-8")
    avisos = [AVISO_CARTAO + " (" + "; ".join(motivos) + ")"] if forcar else []
    (trab / "avisos.json").write_text(json.dumps(avisos, ensure_ascii=False), encoding="utf-8")
    if len(arqs) == 1:
        saida.write_bytes(arqs[0].read_bytes())
    else:
        junta.juntar(arqs, saida, fps=fps, quiet=True)
    return {"partes": len(partes), "refeitas": feitos, "recorte_s": round(t_rec + tempos["recorte"], 1), "pecas_s": round(tempos["pecas"], 1),
            "ffmpeg_s": round(tempos["ffmpeg"], 1), "total_s": round(time.perf_counter() - t_ini, 1), "avisos": avisos, "pergunta": pergunta}


if __name__ == "__main__":
    main()
