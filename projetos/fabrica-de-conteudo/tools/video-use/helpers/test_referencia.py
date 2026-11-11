"""O referencia.py mede o que a referência tem e monta a folha lado a lado.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_referencia.py

O vídeo de prova é feito aqui, pelo `ff.run`: três cores (cortes aos 2 s e aos 4 s) e um tom,
um vão mudo, um tom (a pausa de 2 s). O de layout tem ruído (rosto cheio), painel liso em cima com ruído embaixo
(tela dividida, com uma peça nova no meio) e tela lisa (só painel). Nada de rede: o link do yt-dlp não entra no teste.
"""
import json
import tempfile
from pathlib import Path

from PIL import Image

import ff
import referencia as rf


def video(pasta: Path) -> Path:
    cor = lambda c: ["-f", "lavfi", "-i", f"color=c={c}:s=180x320:r=15:d=2"]
    out = pasta / "ref.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", *cor("red"), *cor("blue"), *cor("green"),
            "-f", "lavfi", "-i", "sine=f=440:r=44100:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=2",
            "-f", "lavfi", "-i", "sine=f=440:r=44100:d=2",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a][4:a][5:a]concat=n=3:v=0:a=1[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out],
           quiet=True)
    return out


def video_so_ruido(pasta: Path) -> Path:
    out = pasta / "ruido.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x808080:s=180x320:r=15:d=4,noise=alls=90:allf=t+u,format=yuv420p",
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", out], quiet=True)
    return out


def video_de_layout(pasta: Path) -> Path:
    """10 s, 9:16: rosto cheio (2 s) · dividida (4 s, com uma peça nova aos 2 s) · só painel (2 s) · rosto cheio (2 s)."""
    ruido = lambda d: f"color=c=0x808080:s=180x320:r=15:d={d},noise=alls=90:allf=t+u,format=yuv420p"
    partes = []

    def faz(nome: str, entradas: list[str], grafo: str | None, ate: str) -> Path:
        out = pasta / f"{nome}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", *[x for e in entradas for x in ("-f", "lavfi", "-i", e)]]
        if grafo:
            cmd += ["-filter_complex", grafo, "-map", ate]
        cmd += ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", out]
        ff.run(cmd, quiet=True)
        partes.append(out)
        return out

    faz("a", [ruido(2)], None, "")
    faz("b", [ruido(2), "color=c=white:s=180x140:r=15:d=2"], "[0:v][1:v]overlay=0:0[v]", "[v]")
    faz("c", [ruido(2), "color=c=0xc8c8c8:s=180x140:r=15:d=2,drawbox=x=20:y=50:w=140:h=30:color=black:t=fill"], "[0:v][1:v]overlay=0:0[v]", "[v]")
    faz("d", ["color=c=white:s=180x320:r=15:d=2,format=yuv420p"], None, "")
    faz("e", [ruido(2)], None, "")
    lista = pasta / "l.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    out = pasta / "layout.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", out], quiet=True)
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        v = video(d)

        # os cortes: dois, aos 2 s e aos 4 s
        ts = rf.trocas(v)
        assert len(ts) == 2 and abs(ts[0] - 2.0) < 0.15 and abs(ts[1] - 4.0) < 0.15, ts

        # o som: uma pausa de 2 s, e nada sob a fala
        s = rf.som(v)
        assert s["pausas"] == 1 and abs(s["maior_pausa_s"] - 2.0) < 0.2, s
        assert s["som_continuo_sob_a_fala"] is False, s

        # as vozes (a `janelas` do plano): o tom de 0 a 2 s e de 4 a 6 s, cada um com a folga
        j = rf.vozes(v, 0.2)
        assert len(j) == 2 and abs(j[0][1] - 2.06) < 0.1 and abs(j[1][0] - 3.94) < 0.1, j
        assert len(rf.vozes(v, 3.0)) == 1, "vão de 2 s menor que --pausa 3 não separa as vozes"
        # com a transcrição, a voz sem palavra por perto (a segunda) cai
        tr = d / "t.json"
        tr.write_text(json.dumps({"words": [{"type": "word", "text": "oi", "start": 0.2, "end": 1.8}]}), encoding="utf-8")
        assert len(rf.vozes(v, 0.2, transcript=tr)) == 1, "a janela sem palavra devia cair"

        # a palavra que o Whisper pôs antes da voz entra na janela; a que está longe fica onde está
        doc = {"words": [{"type": "word", "text": "eu", "start": 0.6, "end": 0.9},
                         {"type": "word", "text": "oi", "start": 1.1, "end": 1.5},
                         {"type": "word", "text": "longe", "start": 9.0, "end": 9.3},
                         {"type": "spacing", "text": " "}]}
        a = rf.alinha(doc, [[1.0, 3.0]])["words"]
        assert (a[0]["start"], a[0]["end"]) == (1.0, 1.15), a[0]
        assert (a[1]["start"], a[1]["end"]) == (1.1, 1.5) and (a[2]["start"], a[2]["end"]) == (9.0, 9.3), a
        assert a[3]["type"] == "spacing", "o que não é palavra passa como veio"

        # `le`: folha, plano mais longo (os 2 s de cada cor) e medidas
        m = rf.le(str(v), d / "ref", 4)
        assert m["formato"] == "9:16" and m["trocas"] == 2 and m["folhas"] == ["folha-1.png"], m
        assert (d / "ref" / "folha-1.png").exists() and (d / "ref" / "plano-longo.png").exists()
        assert json.loads((d / "ref" / "medidas.json").read_text(encoding="utf-8"))["trocas"] == 2

        # `compara`: a referência em cima, o resultado embaixo, uma folha só
        r = rf.compara(v, v, d / "lado.png", 3)
        assert Image.open(d / "lado.png").width == 3 * 300, "uma coluna por instante"
        assert Image.open(d / "lado.png").height > 2 * 300 * 320 // 180, "duas fileiras"
        assert "trocas de imagem" in rf.tabela(r["ref"], r["seu"])

        # o instante 0,1 s (o gancho) abre a lista, e o resto fica dentro do vídeo
        t = rf.tempos(6.0, 5)
        assert t[0] == 0.1 and len(t) == 5 and max(t) < 6.0, t

        # arquivo que existe vale como está; o que não existe e não é link, para
        assert rf.baixa(str(v), d) == v
        try:
            rf.baixa(str(d / "nao-existe.mp4"), d)
        except SystemExit:
            pass
        else:
            raise AssertionError("aceitou um caminho que não existe")

        # o layout e as peças (9:16): rosto cheio, dividida (duas peças: a que entra e a que troca aos 2 s do trecho), só painel
        lv = video_de_layout(d)
        m = rf.medidas(lv)
        nomes = [t[2] for t in m["layout_trechos"]]
        assert nomes == ["cheio", "dividida", "tela", "cheio"], m["layout_trechos"]
        assert abs(m["layout"]["dividida"] - 0.4) < 0.05 and abs(m["layout"]["tela"] - 0.2) < 0.05 and abs(m["layout"]["cheio"] - 0.4) < 0.05, m["layout"]
        assert m["trocas_de_layout"] == 3 and m["pecas"] == 3, (m["trocas_de_layout"], m["pecas"])
        assert abs(m["cobertura_de_pecas"] - 0.6) < 0.05 and abs(m["pecas_por_s"] - 0.3) < 0.03, m
        assert m["layout_trechos"][1][3] == "claro" and len(m["layout_trechos"][1][4]) == 1, "a peça nova aos 2 s do trecho de painel"
        assert m["eventos"] >= 5, "os 3 cortes de layout e a peça nova são eventos"
        # o vídeo só de rosto não tem layout: 100% cheio, nenhuma peça
        solo = rf.medidas(video_so_ruido(d))
        assert solo["layout"]["cheio"] == 1.0 and solo["pecas"] == 0 and solo["cobertura_de_pecas"] == 0, solo
        # a tabela mostra o motion, e o veredito acusa a diferença grande (a referência com painel contra o rosto cheio)
        tab = rf.tabela(m, solo)
        assert "layout (cheio·dividida·tela)" in tab and "eventos de motion por s" in tab and "40% · 40% · 20%" in tab, tab
        ver = rf.veredito(m, solo)
        assert ver and ver[0].startswith("ATENÇÃO") and any("layout" in x for x in ver) and any("peças" in x for x in ver), ver
        assert rf.veredito(m, m) == [], "resultado igual à referência: sem aviso"
        assert rf.veredito(solo, solo) == [] and rf.veredito(solo, m) == [], "referência sem painel: nada a copiar"

        # o esboço: as cenas da referência no tamanho do seu vídeo (5 s), cada borda no fim de uma palavra
        fala = [[w, round(0.5 * i, 2), round(0.5 * i + 0.45, 2)] for i, w in enumerate("um dois tres quatro cinco seis sete oito nove dez".split())]
        e = rf.esboco(m, fala, 5.0)
        assert [c[2] for c in e["cenas"]] == ["rosto", "split", "tela", "rosto"] and e["cenas"][0][0] == 0.0 and e["cenas"][-1][1] == 5.0, e["cenas"]
        assert all(b[0] > a[0] for a, b in zip(e["cenas"], e["cenas"][1:])) and all(c[1] > c[0] + 0.4 for c in e["cenas"]), e["cenas"]
        assert len(e["graficos"]) == 3, e["graficos"]
        assert e["cenas"][1][3] == "claro" and e["cenas"][0][4] == 1.08, "o painel claro e o zoom do rosto"
        fins = {w[2] for w in fala}
        assert all(round(c[1], 2) in fins or c[1] == 5.0 for c in e["cenas"][:-1]), "a cena troca no fim da palavra"
        # o plano só vai à montagem com as peças preenchidas e dentro de uma cena de painel
        erros = rf.confere_plano(e)
        assert len(erros) == 3 and all("sem preencher" in x for x in erros), erros
        for g in e["graficos"]:
            g.pop("_preencher")
            g["g"] = "lista"
            g["titulo"] = "x"
        assert rf.confere_plano(e) == [], rf.confere_plano(e)
        assert any("fora de uma cena" in x for x in rf.confere_plano({**e, "graficos": [{"t": 0.1, "ate": 0.3, "g": "lista"}]})), "peça na cena de rosto não aparece"
        assert any("buraco" in x for x in rf.confere_plano({**e, "cenas": [[0, 1, "rosto"], [2, 3, "rosto"]]}))
        # o r da e_editorial: a fala vem do cards.json (no tempo do vídeo cortado), o take dá a duração
        (d / "cards.json").write_text(json.dumps({"cards": [{"words": [{"tx": "oi", "t0": 0.1, "t1": 0.3}, {"tx": "tudo", "t0": 0.3, "t1": 0.6}]}]}), encoding="utf-8")
        r = rf.r_do_plano({**e, "take": "layout.mp4", "fala_de": "cards.json"}, d)
        assert r["fala"] == [["oi", 0.1, 0.3], ["tudo", 0.3, 0.6]] and "take" not in r and "fala_de" not in r, r
        assert r["dur"] == 5.0, "a duração do plano manda"
        sem = rf.r_do_plano({**{k: v for k, v in e.items() if k != "dur"}, "take": "layout.mp4", "fala_de": "cards.json"}, d)
        assert abs(sem["dur"] - 10.0) < 0.2, "sem `dur`, a do take"
        assert rf.fala_de(d / "cards.json")[1][0] == "tudo"
        # a dividida recusa o plano que não está pronto (sem renderizar nada)
        (d / "ruim.json").write_text(json.dumps({"take": "layout.mp4", "fala_de": "cards.json", "cenas": [[0, 5, "split", "claro"]],
                                                 "graficos": [{"t": 0, "ate": 5, "g": "?", "_preencher": "x"}]}), encoding="utf-8")
        try:
            rf.dividida(d / "ruim.json", d / "x.mp4")
        except SystemExit as ex:
            assert "não está pronto" in str(ex)
        else:
            raise AssertionError("montou um plano com peça sem preencher")

        # as legendas que o agente escolhe pelo nome
        lista = rf.presets()
        assert "editorial" in lista and "fita" in lista and "caixa-cor" in lista and "letras (desenho.fonte)" in lista
    print("ok test_referencia")


if __name__ == "__main__":
    main()
