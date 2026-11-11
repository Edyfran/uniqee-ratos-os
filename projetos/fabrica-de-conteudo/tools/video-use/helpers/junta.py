#!/usr/bin/env python3
"""Emenda vários cortes num vídeo só, e confere que a soma bateu.

    python junta.py r3.mp4 s2e3.mp4 s4e5.mp4 -o vsl.mp4

Parece trabalho pra `ffmpeg -f concat`, e é justamente aí que mora a armadilha.

**O demultiplexador não reescreve o relógio.** Ele cola os quadros e mantém a
taxa declarada do PRIMEIRO arquivo. Emendar um trecho de 25 fps com outro de 30
fps faz o segundo tocar a 25: a imagem estica 20%, o áudio não estica junto, e o
vídeo inteiro sai fora de sincronia depois da junção. Recodificar na saída não
salva — a essa altura os carimbos de tempo já estão errados.

Aqui a junção é por FILTRO, com `fps=` em cada entrada antes de concatenar. Custa
uma recodificação e entrega o relógio certo.

A conferência não é enfeite: mede a duração de cada entrada, soma, e compara com
o que saiu. Mais de um quadro de diferença é erro, não aviso — foi exatamente
assim que um corte de 78s virou um de 94s sem ninguém perceber.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ff


def _quadros(p: Path) -> int:
    """Quantos quadros a imagem tem. Contados, não calculados: um pacote é um quadro, e contar
    pacote não decodifica. O `-count_frames` decodificava as partes e a emenda inteira de novo
    só pra contar: 128 dos 210 s da emenda de um longo de 7 min (07/10)."""
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(p)],
               capture=True, quiet=True).stdout.strip()
    # um trecho com dado lateral (o perfil ICC de uma foto) sai "424," no csv
    return int(r.splitlines()[0].split(",")[0])


def faixas(quadros: list[int], cortes: list[float], fps: int) -> list[tuple[int, int, int, int]]:
    """(imagem de, até, som de, até), em quadros, do que cada parte entra na emenda. `cortes[i]` é a emenda entre
    a parte i e a i+1, em segundos: positivo = J-cut (a fala da i+1 entra antes da imagem dela, por cima do fim
    da imagem da i), negativo = L-cut (o som da i segue por cima da imagem da i+1). Nenhum dos dois move a
    sincronia: a imagem de cada parte continua colada ao som dela, e o que sai é só ponta sem fala."""
    out = [[0, n, 0, n] for n in quadros]
    for i, c in enumerate(cortes):
        k = round(abs(c) * fps)
        if k == 0:
            continue
        if k >= min(quadros[i], quadros[i + 1]):
            raise ValueError(f"emenda {i}: {c} s passa de uma parte inteira")
        if c > 0:      # J: o som do fim de A sai; a imagem do começo de B sai
            out[i][3] -= k
            out[i + 1][0] += k
        else:          # L: a imagem do fim de A sai; o som do começo de B sai
            out[i][1] -= k
            out[i + 1][2] += k
    return [tuple(x) for x in out]


def juntar(partes: list[Path], saida: Path, *, fps: int = ff.FPS,
           largura: int = 0, altura: int = 0, quiet: bool = False, cortes: list[float] | None = None) -> float:
    if len(partes) < 2:
        sys.exit("junta precisa de pelo menos dois arquivos")

    sondas = [ff.probe(p) for p in partes]
    largura = largura or sondas[0].largura
    altura = altura or sondas[0].altura
    if not all(s.tem_audio for s in sondas):
        mudas = [p.name for p, s in zip(partes, sondas) if not s.tem_audio]
        sys.exit(f"sem faixa de áudio: {', '.join(mudas)}")

    if not quiet:
        for p, s in zip(partes, sondas):
            marca = "" if s.fps == fps else f"  <- {s.fps} fps, vai pra {fps}"
            print(f"  {p.name:34} {s.duracao:7.2f}s  {s.largura}x{s.altura}{marca}")

    # Quantos quadros cada parte tem DE VERDADE. Não dá pra confiar na duração
    # do contêiner: ela é o maior entre imagem e som, e o som sempre passa uns
    # centésimos do último quadro. O `fps=` então completa a diferença inventando
    # quadro, uma vez por emenda — treze partes viraram 38 quadros a mais.
    # O corte acontece DEPOIS do `fps=`, então a conta é na taxa de saída: um
    # clipe de 25fps com 50 quadros vira 60 a 30fps, e aparar em 50 o encurtaria
    # em um terço. Contar na fonte e cortar no destino foi exatamente esse erro.
    contados = [_quadros(p) for p in partes]
    # Em taxa variável o r_frame_rate pode ser o dobro da real (um bloco de 30 fps com r=60): a
    # conta vai pela média, senão a parte sai com a metade dos quadros e a soma "bate" do mesmo jeito.
    taxas = [(s.fps_medio if s.vfr and s.fps_medio else s.fps) or fps for s in sondas]
    quadros = [max(1, round(c * fps / t)) for c, t in zip(contados, taxas)]
    # O esperado é a duração da IMAGEM de cada parte, na taxa dela. A do contêiner
    # é o maior entre imagem e som, e o som de cada bloco passa uns centésimos do
    # último quadro: num episódio de 19 blocos isso somou 0,67 s e reprovou um
    # vídeo certo. Contra a imagem na própria taxa, o defeito que a conferência
    # existe pra pegar (25fps tocando a 30) continua aparecendo inteiro.
    esperado = sum(c / t for c, t in zip(contados, taxas))
    cortes = list(cortes or [])
    if cortes and len(cortes) != len(partes) - 1:
        sys.exit(f"cortes: são {len(partes) - 1} emendas e vieram {len(cortes)} valores")
    if any(cortes):
        # J/L-cut: a imagem de uma parte perde um pedaço, o som de outra também; a conta fecha nas duas
        fx = faixas(quadros, cortes, fps)
        esperado -= sum(round(abs(c) * fps) for c in cortes) / fps
        _junta_recodificando(partes, quadros, sondas, fps, largura, altura, saida, fx)
    elif _copiavel(partes, sondas, fps, largura, altura):
        _junta_copiando(partes, quadros, fps, saida)
    else:
        _junta_recodificando(partes, quadros, sondas, fps, largura, altura, saida)

    saiu = _quadros(saida) / fps
    # Um quadro por parte, mais um pro contêiner. Tentei fechar no quadro exato
    # aparando cada entrada e não fecha: treze partes recodificadas acumulam
    # meio segundo em 387, e perseguir isso é precisão que o formato não dá.
    #
    # A folga continua três ordens de grandeza abaixo do defeito que isto existe
    # pra pegar — 25fps tocando a 30 estica 20%, o que num minuto dá 12s.
    folga = (len(partes) + 1) / fps
    if abs(saiu - esperado) > folga:
        sys.exit(f"a soma não bateu: esperava {esperado:.2f}s, saiu {saiu:.2f}s "
                 f"({abs(saiu - esperado):.2f}s de diferença, folga é {folga:.2f}s). "
                 f"Alguma entrada tem relógio quebrado.")
    if not quiet:
        print(f"{saida}  {saiu:.2f}s  ({len(partes)} partes, "
              f"deriva {abs(saiu - esperado) * 1000:.0f} ms)")
    return saiu


def _formato(p: Path) -> dict:
    import json
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=codec_name,profile,pix_fmt,time_base,r_frame_rate", "-of", "json", str(p)],
               capture=True, quiet=True).stdout
    return (json.loads(r).get("streams") or [{}])[0]


def _copiavel(partes, sondas, fps, largura, altura) -> bool:
    """Todas as partes já saíram iguais (taxa, tamanho, codificador, perfil, pixel) e com a imagem
    inteira aproveitada: aí a emenda copia a imagem em vez de codificar de novo. O caso comum é o
    longo, em que todo bloco sai do mesmo passo de legenda."""
    if any(s.fps != fps or (s.largura, s.altura) != (largura, altura) for s in sondas):
        return False
    formatos = [_formato(p) for p in partes]
    # a taxa exata, não a arredondada da sonda: 29,97 copiado levaria o relógio de 29,97 pro final
    return (all(f == formatos[0] for f in formatos) and formatos[0].get("codec_name") == "h264"
            and formatos[0].get("r_frame_rate") == f"{fps}/1")


def _junta_copiando(partes: list[Path], quadros: list[int], fps: int, saida: Path) -> None:
    """A imagem pelo demultiplexador, copiada, com a duração de cada parte dita em quadros (o
    relógio que ele não reescreve vem da lista, não do contêiner); o som pelo filtro, aparado e
    completado no quadro, como na emenda recodificada."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        lista = Path(d) / "lista.txt"
        # absoluto: o demultiplexador resolve o caminho relativo contra a pasta da lista, não a de quem chama
        esc = lambda p: str(Path(p).resolve()).replace("'", "'\\''")
        lista.write_text("".join(f"file '{esc(p)}'\nduration {n / fps:.6f}\n"
                                 for p, n in zip(partes, quadros)), encoding="utf-8")
        entradas, graf, rot = [], [], []
        for i, (p, n) in enumerate(zip(partes, quadros), start=1):
            entradas += ["-i", str(p)]
            graf.append(f"[{i}:a]aresample={ff.AUDIO_RATE},atrim=0:{n / fps:.5f},"
                        f"apad=whole_dur={n / fps:.5f},asetpts=N/SR/TB[a{i}];")
            rot.append(f"[a{i}]")
        graf.append("".join(rot) + f"concat=n={len(partes)}:v=0:a=1[a]")
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), *entradas,
                "-filter_complex", "".join(graf), "-map", "0:v", "-map", "[a]",
                # o bloco chega com a imagem um quadro e pouco depois do som (o atraso do codificador);
                # a emenda recodificada zerava isso, e a copiada leva a imagem pro zero do mesmo jeito
                "-c:v", "copy", "-bsf:v", "setts=pts=PTS-STARTPTS:dts=DTS-STARTPTS",
                *ff.args_audio(), "-movflags", "+faststart", str(saida)], quiet=True)


def _junta_recodificando(partes, quadros, sondas, fps, largura, altura, saida, fx=None) -> None:
    fx = fx or [(0, n, 0, n) for n in quadros]
    entradas: list[str] = []
    graf: list[str] = []
    rotulos: list[str] = []
    for i, (p, n, s) in enumerate(zip(partes, quadros, sondas)):
        vi, vf, ai, af = fx[i]
        entradas += ["-i", str(p)]
        # A taxa ANTES do concat, em cada entrada. É o passo que o demultiplexador
        # não tem como fazer, e sem ele a emenda desanda. O `trim` logo depois
        # fecha a parte num número inteiro de quadros, e aí a soma é exata. A
        # parte do HeyGen (25) mistura em vez de repetir quadro (ff.taxa).
        graf.append(f"[{i}:v]{ff.taxa(s.fps or fps, fps)},trim=start_frame={vi}:end_frame={vf},setpts=N/FRAME_RATE/TB,"
                    f"scale={largura}:{altura},setsar=1,format={ff.PIX_FMT}[v{i}];")
        graf.append(f"[{i}:a]aresample={ff.AUDIO_RATE},atrim={ai / fps:.5f}:{af / fps:.5f},asetpts=PTS-STARTPTS,"
                    f"apad=whole_dur={(af - ai) / fps:.5f},asetpts=N/SR/TB[a{i}];")
        rotulos.append(f"[v{i}][a{i}]")
    if any(f != (0, n, 0, n) for f, n in zip(fx, quadros)):
        # J/L-cut: imagem e som emendam em instantes diferentes, então cada um tem o próprio concat
        # (o concat de v=1:a=1 completa com silêncio o som que ficou mais curto que a imagem da parte)
        graf.append("".join(f"[v{i}]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=1:a=0[v];")
        graf.append("".join(f"[a{i}]" for i in range(len(partes))) + f"concat=n={len(partes)}:v=0:a=1[a]")
    else:
        graf.append("".join(rotulos) + f"concat=n={len(partes)}:v=1:a=1[v][a]")

    ff.run(["ffmpeg", "-y", "-v", "error", *entradas,
            "-filter_complex", "".join(graf), "-map", "[v]", "-map", "[a]",
            *ff.args_video(fps=fps), *ff.args_audio(), str(saida)], quiet=True)


def _autoteste_jl(d: Path) -> None:
    """J-cut e L-cut: a imagem muda num instante e o som em outro, e a soma continua fechando."""
    import numpy as np
    for nome, cor, hz in (("ja.mp4", "red", 440), ("jb.mp4", "blue", 880)):
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={cor}:size=320x180:rate={ff.FPS}:duration=2",
                "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=2", "-shortest",
                *ff.args_video(fps=ff.FPS), *ff.args_audio(), str(d / nome)], quiet=True)

    def sonda(arq: Path, t: float) -> tuple[str, int]:
        """(cor dominante da imagem, frequência) em t."""
        png = d / "q.png"
        ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(arq), "-frames:v", "1", "-vf", "scale=1:1", str(png)], quiet=True)
        from PIL import Image
        r, _, b = Image.open(png).convert("RGB").getpixel((0, 0))
        raw = ff.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-t", "0.06", "-i", str(arq), "-vn", "-ac", "1", "-ar", "16000",
                      "-f", "s16le", "-"], capture=True, binario=True, quiet=True).stdout
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        f = int(np.argmax(np.abs(np.fft.rfft(x * np.hanning(len(x))))) * 16000 / len(x))
        return ("vermelho" if r > b else "azul"), (440 if abs(f - 440) < abs(f - 880) else 880)

    j = d / "j.mp4"
    saiu = juntar([d / "ja.mp4", d / "jb.mp4"], j, quiet=True, cortes=[0.3])
    assert abs(saiu - 3.7) < 0.1, f"J: esperava ~3,7 s, saiu {saiu:.2f}"
    assert sonda(j, 1.6) == ("vermelho", 440) and sonda(j, 1.8) == ("vermelho", 880), "J: o som de B entra antes da imagem"
    assert sonda(j, 2.1) == ("azul", 880)
    saiu = juntar([d / "ja.mp4", d / "jb.mp4"], j, quiet=True, cortes=[-0.3])
    assert abs(saiu - 3.7) < 0.1, f"L: esperava ~3,7 s, saiu {saiu:.2f}"
    assert sonda(j, 1.6) == ("vermelho", 440) and sonda(j, 1.8) == ("azul", 440), "L: o som de A segue sobre a imagem de B"
    assert sonda(j, 2.1) == ("azul", 880)
    assert faixas([60, 60, 60], [0.0, -0.2], 30) == [(0, 60, 0, 60), (0, 54, 0, 60), (0, 60, 6, 60)], "faixas"
    try:
        faixas([10, 60], [0.5], 30)
        raise AssertionError("emenda maior que a parte passou")
    except ValueError:
        pass


def _autoteste() -> None:
    """Emenda 25 fps com 30 fps e confere que a soma bate — que é o caso que o
    demultiplexador erra."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for nome, taxa, dur in (("a.mp4", 25, 2.0), ("b.mp4", 30, 3.0)):
            ff.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=320x568:rate={taxa}:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-shortest", *ff.args_video(fps=taxa), *ff.args_audio(),
                    str(d / nome)], quiet=True)
        saiu = juntar([d / "a.mp4", d / "b.mp4"], d / "j.mp4", quiet=True)
        assert abs(saiu - 5.0) < 0.1, f"esperava ~5.0s, saiu {saiu:.2f}s"
        assert ff.probe(d / "j.mp4").fps == ff.FPS
        # doze blocos com o som 60 ms mais comprido que a imagem: a soma do contêiner
        # passava da folga e reprovava uma emenda certa
        for i in range(12):
            ff.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=320x568:rate={ff.FPS}:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1.06",
                    *ff.args_video(fps=ff.FPS), *ff.args_audio(), str(d / f"s{i}.mp4")], quiet=True)
        partes = [d / f"s{i}.mp4" for i in range(12)]
        assert _copiavel(partes, [ff.probe(p) for p in partes], ff.FPS, 320, 568), "partes iguais e recodificou"
        saiu = juntar(partes, d / "s.mp4", quiet=True)
        assert abs(saiu - 12.0) < 0.1, f"esperava ~12.0s, saiu {saiu:.2f}s"
        ini = ff.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=start_time",
                      "-of", "csv=p=0", str(d / "s.mp4")], capture=True, quiet=True).stdout.strip()
        assert abs(float(ini)) < 1e-3, f"a imagem copiada começa em {ini}s, fora do som"
        _autoteste_jl(d)
    print("autoteste ok: 25fps + 30fps -> 5.00s na taxa do projeto; som passando da imagem não reprova")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("partes", nargs="*", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--fps", type=int, default=ff.FPS)
    ap.add_argument("--cortes", help="J/L-cut por emenda, em segundos, separados por vírgula (positivo = J, negativo = L)")
    ap.add_argument("--autoteste", action="store_true")
    a = ap.parse_args()
    if a.autoteste:
        return _autoteste()
    if not a.partes or not a.out:
        ap.error("precisa dos arquivos e de -o")
    for p in a.partes:
        if not p.exists():
            sys.exit(f"não achei {p}")
    juntar(a.partes, a.out, fps=a.fps, cortes=[float(x) for x in a.cortes.split(",")] if a.cortes else None)


if __name__ == "__main__":
    sys.exit(main())
