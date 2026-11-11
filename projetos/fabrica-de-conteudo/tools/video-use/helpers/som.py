#!/usr/bin/env python3
"""O som do vídeo: os cues das peças, os do plano, e a mistura de todo mundo.

    som.grafo(voz, efeitos, …)      a voz com os efeitos por baixo, num filtro (criativo, receita,
                                    abertura de aula, este programa)
    som.mistura(vídeo, saída, …)    voz, efeitos e cama com ducking, normalizada por último, com teto
                                    de pico (o mixa.py é a linha de comando dela)
    som.grafo_fecho(regra, …)       a trilha que sobe na chamada final (a fábrica, `trilha: fecho`)

    python som.py bloco.mp4 --plan plano.json -o bloco_som.mp4 [--mestre -2] [--corta 74.2]
    python som.py --cues peca.json -o trilha.wav [--em 12.4] [--ganho -6]

No plano, um som é um CUE ou um ARQUIVO:

    "sons": [{"tipo": "pop", "t": 3.2},                                  ← ganho do sfx.json
             {"arquivo": "heygen/notif_b.mp3", "t": 23.74, "ganho": 0.5}]  ← ganho linear

E toda peça do plano (`brolls[]`) que publicou cues — o render grava duração e
cues em <peça>.json — soa sozinha, a partir do instante em que entra. O `sons`
do plano é só o extra: o whoosh na saída de uma peça renderizada com `sai=0`,
a notificação do print. Converter cue em som era o que três scripts da VSL
faziam à mão, cada um com seu MESTRE_DB.

O banco é um só, tools/v2/sfx/: um arquivo por nome de cue, o sfx.json com o
ganho de cada um, e as subpastas com o que não é cue (heygen/, avulsos/).
`arquivo` relativo procura ao lado do plano e depois no banco.

Depois do render e não antes: o áudio que vai pro HeyGen é o que ele usa pra
sincronizar a boca. Um bipe no meio dele confunde o lipsync e volta no vídeo
gerado, onde não dá mais pra tirar.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import ff

SFX = Path(__file__).resolve().parents[2] / "v2" / "sfx"
# o banco de efeitos não vai no kit de aulas, que leva só a mistura: lá o mapa fica vazio
MAPA = json.loads((SFX / "sfx.json").read_text(encoding="utf-8"))["sons"] if (SFX / "sfx.json").exists() else {}

# Nível dos cues contra a voz. Medido em 24/09 na VSL: com -8 o tick-roll
# ficava 17 dB debaixo da voz, inaudível. É do estilo; este é o padrão.
MESTRE_DB = -2.0

# Os de cinema pesam: no máximo três por vídeo (tools/v2/CUES.md).
CINEMA = {"riser", "boom", "sub-drop", "hit", "swell", "tom", "shimmer", "tape-stop", "glitch"}
DOSE_CINEMA = 3


def eventos(cues):
    """Cue → (t, arquivo no banco, ganho em dB). Cue com `dur` vira sequência."""
    for c in cues:
        s = MAPA.get(c["tipo"])
        if not s:
            print(f"  cue sem som: {c['tipo']}", file=sys.stderr)
            continue
        dur = c.get("dur")
        if dur and c["tipo"] == "tick-roll":
            for i in range(18):
                yield c["t"] + dur * .92 * (1 - (1 - i / 18) ** .35), s["unidade"], s["ganho_db"]
        elif dur and c["tipo"] == "type":
            for i in range(max(1, round(dur / .075))):
                yield c["t"] + i * .075, s["unidade"], s["ganho_db"]
        elif s.get("ancora") == "fim":
            # riser/swell: o som TERMINA no cue — começa `dur` antes
            yield c["t"] - s["dur"], s["arquivo"], s["ganho_db"]
        else:
            # som de golpe: o PICO medido cai no cue, não o começo do arquivo (o `certo` tem o
            # dele a 0,15 s, o `erro` a 0,29). O de movimento (whoosh, zoom-in) não tem `pico`:
            # ele começa junto com o que anda. Skillry #225, 04/10/2026
            yield c["t"] - s.get("pico", 0.0), s["arquivo"], s["ganho_db"]


def mede_pico(arq: Path) -> float:
    """O instante do golpe: o máximo da energia em janelas de 5 ms, em segundos do arquivo.
    `som.py --picos certo erro` mede e grava no sfx.json."""
    import wave
    import numpy as np
    with wave.open(str(arq)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        if w.getsampwidth() != 2:
            sys.exit(f"{arq.name}: o banco é PCM de 16 bits; converta antes de medir o pico")
        a = np.frombuffer(w.readframes(n), "<i2").astype(float).reshape(-1, ch)
    jan = int(sr * .005)
    energia = np.convolve(np.abs(a).max(1) ** 2, np.ones(jan) / jan, "same")
    return round(float(np.argmax(energia)) / sr, 3)


def resolver(nome: str, base: Path) -> Path:
    p = Path(nome)
    for cand in (p if p.is_absolute() else base / p, SFX / p):
        if cand.exists():
            return cand
    achados = sorted(SFX.rglob(p.name))
    if achados:
        return achados[0]
    sys.exit(f"efeito não achado: {nome} (procurei ao lado do plano e em {SFX})")


def _cues_da_peca(arquivo: Path) -> list | None:
    for meta in (arquivo.with_suffix(".json"), arquivo.with_suffix(".cues.json")):
        if meta.exists():
            d = json.loads(meta.read_text(encoding="utf-8"))
            if isinstance(d, dict) and "cues" in d:
                return d["cues"]
    return None


def do_plano(plano: dict, base: Path, mestre: float = MESTRE_DB) -> list[tuple[float, Path, float]]:
    """Todos os sons de um plano como (t, arquivo, ganho em dB), em ordem."""
    saida, tipos = [], []
    # `cues_de`: mídia que soa e não é b-roll do plano — a receita de talking
    # head, que troca a imagem da base e publica os cues ao lado do .mp4.
    for b in (plano.get("brolls") or []) + (plano.get("cues_de") or []):
        arq = Path(b["arquivo"]) if Path(b["arquivo"]).is_absolute() else base / b["arquivo"]
        cues = _cues_da_peca(arq)
        # `mudo`: a peça entra calada — quem soa ali é o plano (a moeda de cada carta,
        # não o stamp e o whoosh de doze etiquetas seguidas)
        if cues is None or b.get("mudo"):
            continue
        t0, t1 = float(b["t0"]), float(b["t1"])
        # `inicio`: o captions_viral busca o clipe a partir dali, então o cue
        # que cai antes nunca aparece, e os outros andam junto.
        ini = float(b.get("inicio") or 0)
        tocam = [c for c in cues if ini <= c["t"] < ini + (t1 - t0)]
        tipos += [c["tipo"] for c in tocam]
        saida += [(t0 + t - ini, SFX / nome, db + mestre) for t, nome, db in eventos(tocam)]
    for s in plano.get("sons") or []:
        t = float(s["t"])
        if "tipo" in s:
            tipos.append(s["tipo"])
            saida += [(tt, SFX / nome, db + mestre) for tt, nome, db in eventos([s])]
        else:
            ganho = float(s.get("ganho", 0.5))
            saida.append((t, resolver(s["arquivo"], base), 20 * math.log10(max(ganho, 1e-6))))
    n = sum(1 for t in tipos if t in CINEMA)
    if n > DOSE_CINEMA:
        sys.exit(f"{n} sons de cinema neste plano; o teto é {DOSE_CINEMA} por vídeo (tools/v2/CUES.md)")
    return sorted(saida, key=lambda e: e[0])


def _grafo(evs, primeiro: int) -> tuple[list[str], list[str], list[str]]:
    """Uma entrada por ARQUIVO, não por evento: 216 ticks são um -i e um asplit."""
    usos = defaultdict(list)
    for i, (_, arq, _) in enumerate(evs):
        usos[arq].append(i)
    entradas, filtros, rotulos = [], [], []
    for k, (arq, idx) in enumerate(usos.items()):
        entradas += ["-i", str(arq)]
        n = primeiro + k
        if len(idx) == 1:
            filtros.append(f"[{n}:a]anull[r{idx[0]}]")
        else:
            filtros.append(f"[{n}:a]asplit={len(idx)}" + "".join(f"[r{i}]" for i in idx))
    for i, (t, _, db) in enumerate(evs):
        # Som que começaria antes do zero (o riser de um cue no primeiro
        # segundo) perde a cabeça, não o fim: ele tem que terminar no cue.
        cabeca = f"atrim=start={-t:.3f},asetpts=PTS-STARTPTS," if t < 0 else ""
        filtros.append(f"[r{i}]{cabeca}adelay={max(0, round(t * 1000))}:all=1,"
                       f"volume={db:.2f}dB[s{i}]")
        rotulos.append(f"[s{i}]")
    return entradas, filtros, rotulos


def grafo(base: str | None, evs, primeira: int, teto: float | None = None) -> tuple[list[str], list[str], str]:
    """A voz (o rótulo `base`, ex. "0:a") com os efeitos por baixo, num filtro só: (entradas, filtros,
    rótulo da saída). O efeito fica no ganho dele, sem a soma normalizar (`normalize=0`), e a duração é
    a da voz: o efeito perto do fim não estica o áudio. Sem `base`, só os efeitos. `teto` fecha com o
    limitador. É a mistura de todo mundo: a fábrica, o criativo, a receita e a abertura de aula."""
    entradas, filtros, rotulos = _grafo(evs, primeira) if evs else ([], [], [])
    lim = f",{ff.limitador(teto)}" if teto else ""
    if base and evs:
        filtros.append(f"[{base}]" + "".join(rotulos) + f"amix=inputs={len(evs) + 1}:duration=first:normalize=0{lim}[mix]")
    elif evs:
        filtros.append("".join(rotulos) + f"amix=inputs={len(evs)}:normalize=0{lim}[mix]")
    else:
        filtros.append(f"[{base}]{lim[1:] or 'anull'}[mix]")
    return entradas, filtros, "mix"


# A cama e o nível, do mixa (medidos nas aulas dele): a voz num alvo, a trilha 13 dB abaixo, a soma no
# padrão da web. O teto de pico (linear, a 4×) deixa a margem do AAC sob o -1 dBTP do checks.
VOZ, CAMA, SAIDA, TETO = -18.9, -31.5, -16.0, 0.85


def mistura(video: Path, saida: Path, evs=(), trilha: Path | None = None, voz: float = VOZ,
            cama: float = CAMA, alvo: float = SAIDA, fala: str | None = None, sem_duck: bool = False,
            fade_fim: float = 2.4, duck_ratio: float = 12, duck_limiar: float = 0.03,
            duck_solta: int = 420, teto: float = TETO) -> Path:
    """O áudio final do vídeo, numa mistura só: a voz no alvo dela, os efeitos por baixo dela (`evs`,
    do `do_plano`), a cama da `trilha` com ducking onde há fala, e a soma normalizada por último, com
    o teto de pico. A imagem é copiada.

    `fala` ("a:b,c:d") diz onde há voz: só ali ela é medida e só ali a cama abaixa ("" = voz
    nenhuma; o efeito fica no nível em que foi posto, que já é contra a voz)."""
    dur = _duracao_imagem(video)
    onde = "+".join(f"between(t,{a},{b})" for a, b in (x.split(":") for x in fala.split(",") if x)) \
        if fala is not None else None
    fonte, vin = video, "0:a"
    if evs:
        # a voz com os efeitos sem perda, medida como ela vai entrar (o mixa antigo media o AAC que
        # o som.py gravava)
        fonte = saida.with_name(f"{saida.stem}.voz.wav")
        ent, fs, rot = grafo("vp", evs, 1)
        # a voz vai até o fim da imagem antes de receber os efeitos: o efeito depois da última
        # palavra (o carimbo da chamada) soa, em vez de cair fora com a voz
        fs.insert(0, f"[0:a]apad=whole_dur={dur:.3f}[vp]")
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), *ent, "-filter_complex", ";".join(fs),
                "-map", f"[{rot}]", "-c:a", "pcm_f32le", str(fonte)], quiet=True)
        vin = "1:a"
    try:
        gv = 0.0 if onde == "" else voz - ff.lufs(fonte, onde)
        ate_o_fim = f"apad=whole_dur={dur:.3f}"   # a fala acaba antes da imagem: o resto é silêncio
        entradas = ["-i", str(video), *(["-i", str(fonte)] if evs else [])]
        lim = ff.limitador(teto)
        if not trilha:
            graf, gm = f"[{vin}]volume={gv:.2f}dB,{ate_o_fim}[a]", None
        else:
            gm = cama - ff.lufs(trilha)
            fim = max(0.5, dur - fade_fim - 0.1)
            k = len(entradas) // 2
            entradas += ["-i", str(trilha)]
            # `aloop` antes do atrim: trilha mais curta que o corte tem que dar a volta
            m = lambda corta: (f"[{k}:a]aloop=loop=-1:size=2000000000,{corta}asetpts=N/SR/TB,volume={gm:.2f}dB,"
                               f"afade=t=in:d=1.2,afade=t=out:st={fim:.3f}:d={fade_fim}[m]")
            corte = f"atrim=0:{dur:.3f}"
            if sem_duck or onde == "":
                graf = f"[{vin}]volume={gv:.2f}dB,{ate_o_fim}[v];{m(corte + ',')};[v][m]amix=inputs=2:duration=first:normalize=0,{lim}[a]"
            else:
                # fora da fala a chave cala: o efeito passa por cima da cama sem abaixá-la
                chave = f"[k]volume=0:enable='not({onde})'," if onde else "[k]"
                # O sidechaincompress do ffmpeg 6.1 (o do Ubuntu) manda o fim da entrada que acabar primeiro e joga fora o que a
                # outra ainda tinha na fila: a cama sumia da metade pra frente, de vez em quando (CI do Linux, "trilha 0.0").
                # Com as duas entradas sem fim e o corte depois dele, nenhuma acaba antes.
                graf = (f"[{vin}]volume={gv:.2f}dB,{ate_o_fim},asplit=2[v][k];{chave}apad[k2];{m('')};"
                        f"[m][k2]sidechaincompress=threshold={duck_limiar}:ratio={duck_ratio}:attack=15:release={duck_solta}:makeup=1,"
                        f"{corte},asetpts=N/SR/TB[d];"
                        f"[v][d]amix=inputs=2:duration=first:normalize=0,{lim}[a]")
        ff.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", graf, "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", ff.CODEC_AUDIO, "-b:a", "192k", str(saida)], quiet=True)
    finally:
        if evs:
            fonte.unlink(missing_ok=True)
    final = ff.lufs(saida)
    # normaliza por último: a soma de voz e cama não cai exatamente no alvo, e acerta numa segunda
    # passada com o ganho medido no resultado, sob o mesmo teto. Sem trilha, só o nível da voz.
    passou = bool(trilha) and abs(final - alvo) > 0.8
    if passou:
        tmp = saida.with_suffix(".tmp.mp4")
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(saida), "-af", f"volume={alvo - final:.2f}dB,{lim}",
                "-c:v", "copy", "-c:a", ff.CODEC_AUDIO, "-b:a", "192k", str(tmp)], quiet=True)
        tmp.replace(saida)
    print(f"{saida}  voz {gv:+.1f}dB" + (f" · {len(evs)} efeito(s)" if evs else "")
          + (f" · cama {gm:+.1f}dB ({Path(trilha).name})" if trilha else "")
          + f" · saída {ff.lufs(saida) if passou else final:.1f} LUFS")
    return saida


def grafo_fecho(t: dict, duracao: float, voz: str, faixa: tuple[str, str], fecho: bool) -> tuple[list[str], str]:
    """A trilha do fecho (a regra `trilha` do estilo): por baixo da fala o vídeo inteiro, subindo na
    chamada final quando há `fecho`. Devolve (filtros, rótulo do som final).

    A faixa entra DUAS vezes (`faixa`, dois rótulos do mesmo arquivo) e cruza consigo mesma — é o que
    faz o laço não ter costura audível quando a música é mais curta que o vídeo. O volume fica no piso
    até `antes_do_fecho` e sobe em rampa; sem isso a trilha disputa com a voz, e com ela o fecho não
    tem energia nenhuma. `amix` com `normalize=0` e `dropout_transition` alto: normalizar faria a
    trilha subir sozinha toda vez que a fala desse uma pausa."""
    piso, cruz = t["sob_fala"], t["cruzamento"]
    total = duracao + (t["outro_dur"] if fecho else 0.0)
    sobe = round(duracao - t["antes_do_fecho"], 2)
    fim_fade = round(total - t["saida"], 2)
    volume = (f"volume='clip({piso}+{1 - piso:.2f}*(t-{sobe})/{t['subida']},"
              f"{piso},1.0)':eval=frame" if fecho else f"volume={piso}")
    musica = (f"acrossfade=d={cruz}:c1=tri:c2=tri[loop];"
              f"[loop]atrim=0:{round(total, 2)},loudnorm=I={t['alvo']},{volume},"
              f"afade=t=in:st=0:d={t['entrada']},"
              f"afade=t=out:st={fim_fade}:d={t['saida']}[mus]")
    mix = ("amix=inputs=2:normalize=0:dropout_transition=99999,"
           f"{ff.limitador(0.95)}[a]")
    return [f"[{faixa[0]}][{faixa[1]}]{musica}", f"[{voz}][mus]{mix}"], "a"


def _duracao_imagem(p: Path) -> float:
    """A duração da imagem, que é o que o áudio tem que cobrir; sem ela, a do arquivo."""
    r = ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=duration", "-of", "csv=p=0", str(p)], capture=True, quiet=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return ff.dur(p)


def mixa(cues, saida, em=0.0, ganho=0.0):
    """A trilha dos cues de uma peça, sozinha, em `saida` (a receita chama direto)."""
    evs = [(t + em, SFX / nome, db + ganho) for t, nome, db in eventos(cues)]
    if not evs:
        sys.exit("nenhum cue")
    entradas, filtros, rot = grafo(None, evs, 0)
    ff.run(["ffmpeg", "-y", "-loglevel", "error", *entradas,
            "-filter_complex", ";".join(filtros), "-map", f"[{rot}]",
            "-ar", ff.AUDIO_RATE, str(saida)])
    print(f"wrote {saida}  ({len(evs)} eventos)")


def no_video(video: Path, evs, saida: Path, corta: float | None = None) -> None:
    if evs:
        # o som em cima da voz passa do teto: o reel do celular saiu com -0,6 dBTP (22/10)
        entradas, filtros, rot = grafo("0:a", evs, 1, TETO)
        mapas = ["-filter_complex", ";".join(filtros), "-map", "0:v", "-map", f"[{rot}]"]
    else:
        entradas, mapas = [], ["-map", "0:v", "-map", "0:a"]
    corte = ["-t", f"{corta:.3f}"] if corta else []
    ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), *entradas, *mapas, *corte,
            "-c:v", "copy", "-c:a", ff.CODEC_AUDIO, "-b:a", ff.AUDIO_BITRATE, str(saida)],
           quiet=True)
    print(f"{saida}  {len(evs)} efeito(s)  {ff.dur(saida):.2f}s")


def _autoteste() -> None:
    """Cue de peça + cue do plano + arquivo avulso, a dose de cinema, e o vídeo
    que sai com a mesma duração que entrou."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "peca.json").write_text(json.dumps({"cues": [{"tipo": "pop", "t": .5},
                                                         {"tipo": "stamp", "t": 9}]}), encoding="utf-8")
        plano = {"brolls": [{"arquivo": "peca.mov", "t0": 1.0, "t1": 3.0}],
                 "sons": [{"tipo": "riser", "t": 2.0}, {"arquivo": "heygen/notif_b.mp3", "t": .2}]}
        evs = do_plano(plano, d, mestre=-2)
        nomes = [(round(t, 2), a.name) for t, a, _ in evs]
        pico = MAPA["pop"].get("pico", 0.0)
        assert (round(1.5 - pico, 2), "pop.wav") in nomes, "cue da peça cai em t0 + t, menos o pico"
        assert not any(a == "stamp.wav" for _, a in nomes), "cue depois do t1 da peça não toca"
        assert (round(2.0 - MAPA["riser"]["dur"], 2), "riser.wav") in nomes, "riser termina no cue"
        pop = next(db for t, a, db in evs if a.name == "pop.wav")
        assert abs(pop - (MAPA["pop"]["ganho_db"] - 2)) < 1e-9, "ganho do sfx.json mais o mestre"
        notif = next(db for t, a, db in evs if a.name == "notif_b.mp3")
        assert abs(notif - 20 * math.log10(.5)) < 1e-9, "arquivo sem ganho = 0,5 linear"
        buscada = {"brolls": [{"arquivo": "peca.mov", "t0": 1.0, "t1": 3.0, "inicio": .4}]}
        assert [(round(t, 2), a.name) for t, a, _ in do_plano(buscada, d)] == [(round(1.1 - pico, 2), "pop.wav")], (
            "clipe buscado a partir de `inicio`: o cue anda junto")
        calada = {"brolls": [{"arquivo": "peca.mov", "t0": 1.0, "t1": 3.0, "mudo": True}]}
        assert do_plano(calada, d) == [], "peça muda não soa"
        cedo = do_plano({"sons": [{"tipo": "riser", "t": .5}]}, d)
        assert cedo[0][0] < 0, "riser no começo começa antes do zero"
        filtro = ";".join(_grafo(cedo, 0)[1])
        assert "atrim=start=" in filtro and "adelay=0" in filtro, "a cabeça tem que ser cortada"
        muitos = {"sons": [{"tipo": "boom", "t": float(i)} for i in range(DOSE_CINEMA + 1)]}
        try:
            do_plano(muitos, d)
            raise AssertionError("passou do teto de cinema sem recusar")
        except SystemExit:
            pass
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest",
                *ff.args_video(), *ff.args_audio(), str(d / "v.mp4")], quiet=True)
        no_video(d / "v.mp4", evs, d / "s.mp4")
        assert abs(ff.dur(d / "s.mp4") - ff.dur(d / "v.mp4")) < .05, "o som esticou o vídeo"
    print("autoteste ok")


def main() -> None:
    if "--autoteste" in sys.argv:
        return _autoteste()
    if sys.argv[1:2] == ["--picos"]:
        arq = SFX / "sfx.json"
        doc = json.loads(arq.read_text(encoding="utf-8"))
        for nome in sys.argv[2:]:
            doc["sons"][nome]["pico"] = mede_pico(SFX / doc["sons"][nome]["arquivo"])
            print(f"{nome:12} pico {doc['sons'][nome]['pico']:.3f}s")
        arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, nargs="?")
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--cues", type=Path, help="só a trilha de uma peça, sem vídeo")
    ap.add_argument("--mestre", type=float, default=MESTRE_DB, help="nível dos cues contra a voz, dB")
    ap.add_argument("--corta", type=float, default=None,
                    help="duração final, pra aparar respiro do fim")
    ap.add_argument("--em", type=float, default=0.0, help="com --cues: onde a peça entra")
    ap.add_argument("--ganho", type=float, default=0.0, help="com --cues: ganho da trilha, dB")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    if a.cues:
        return mixa(json.loads(a.cues.read_text(encoding="utf-8"))["cues"], a.out, a.em, a.ganho)
    if not (a.video and a.plan):
        ap.error("som de vídeo pede o vídeo e --plan; trilha de peça pede --cues")
    evs = do_plano(json.loads(a.plan.read_text(encoding="utf-8")), a.plan.parent, a.mestre)
    if not evs and a.corta is None:
        # Bloco sem som nenhum passa direto: a fábrica chama o som em todo bloco.
        print("nenhum som neste plano; o vídeo passa como está")
    no_video(a.video, evs, a.out, a.corta)


if __name__ == "__main__":
    sys.exit(main())
