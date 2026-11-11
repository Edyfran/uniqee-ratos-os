#!/usr/bin/env python3
"""A cadeia de microfone do OBS dele, aplicada a um take gravado fora do OBS.

    python trata_voz.py quicktime.m4a -o voz.wav

Ele grava no OBS com filtros ajustados e gosta do resultado; no QuickTime não há
filtro nenhum, e o take chega cru. Isto reproduz a mesma cadeia, lida da
configuração do próprio OBS:

    rnnoise -> EQ (low -3, mid +1.5, high +4)
            -> compressor 3:1 @ -18dB, atk 6ms, rel 80ms, makeup +2
            -> ganho -> limiter

Duas diferenças, as duas por medição e não por gosto:

O ganho dele é fixo (+7,3dB) porque o microfone sempre entra no mesmo nível no
OBS. Um take de QuickTime chega onde quiser — o dele veio 14,6dB mais baixo que
a aula gravada no OBS. Ganho fixo aqui erraria; o alvo é o nível medido nas
aulas dele, -18,9 LUFS, e o ganho sai disso.

O compressor tem limiar ABSOLUTO (-18dB). Num take 14dB mais baixo ele nunca
dispara. Por isso o nível é acertado ANTES dele, não depois.

O modelo do rnnoise é o `sh`: medido nos cinco de tools/quadro/public/rnnoise, é o
que mais separa a fala do ar entre as palavras (15,9dB contra 13,1 do take cru).
Só ele viaja, em assets/rnnoise. Sem o modelo, a voz sai tratada sem o rnnoise, e
avisa.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ff

# assets/ fica ao lado de helpers/ no tronco e no kit, como a fonte livre do
# captions_viral. O caminho antigo (parents[2]/quadro) saía da skill no kit plano.
MODELOS = Path(__file__).resolve().parents[1] / "assets" / "rnnoise"
ALVO = -18.9        # LUFS medido nas aulas que ele gravou no OBS
PRE = -26.0         # nível que o compressor de -18dB espera ver na entrada


def loudness(p: Path) -> float:
    try:
        return ff.lufs(p)
    except RuntimeError:
        sys.exit("não consegui medir o loudness da entrada")


def cadeia(pre_db: float, modelo: str, alvo: float) -> str:
    rn = MODELOS / f"{modelo}.rnnn"
    ruido = [f"arnndn=m={ff.caminho_no_filtro(rn)}"]
    if not rn.exists():
        # o rnnoise é acabamento: sem ele a voz leva o ar entre as palavras, mas
        # sai. Morrer aqui parava a VSL inteira.
        print(f"aviso: modelo do rnnoise não achado ({rn}); a voz segue sem ele",
              file=sys.stderr)
        ruido = []
    return ",".join([
        *ruido,
        "bass=g=-3",                                   # low  -3.0
        "equalizer=f=1000:width_type=o:width=2:g=1.5",  # mid  +1.5
        "treble=g=4",                                  # high +4.0
        f"volume={pre_db:.2f}dB",                      # põe o sinal onde o
        "acompressor=threshold=-18dB:ratio=3:attack=6:"  # compressor dele espera
        "release=80:makeup=2dB",
        f"loudnorm=I={alvo}:TP=-1.0:LRA=11",           # ganho + limiter, medidos
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=Path)
    ap.add_argument("--modelo", default="sh",
                    help="modelo do rnnoise em assets/rnnoise (sh é o medido como melhor)")
    ap.add_argument("--alvo", type=float, default=ALVO,
                    help=f"LUFS de saída (padrão {ALVO}, medido nas aulas dele)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    entrada = loudness(a.audio)
    ff.run(["ffmpeg", "-y", "-v", "error", "-i", str(a.audio),
            "-af", cadeia(PRE - entrada, a.modelo, a.alvo),
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(a.out)],
           quiet=True)
    rn = a.modelo if (MODELOS / f"{a.modelo}.rnnn").exists() else "ausente"
    print(f"{a.out}  {entrada:.1f} -> {loudness(a.out):.1f} LUFS "
          f"(alvo {a.alvo}, rnnoise {rn})")


def _autoteste() -> None:
    f = cadeia(7.1, "sh", -18.9)
    assert "arnndn=m=" in f and f.index("arnndn") < f.index("acompressor"), f
    # o nível é acertado ANTES do compressor: limiar absoluto não dispara num
    # take baixo, e foi por isso que a ordem importa
    assert f.index("volume=") < f.index("acompressor"), f
    assert f.index("acompressor") < f.index("loudnorm"), f
    assert "volume=7.10dB" in f, f
    assert MODELOS.is_dir(), f"pasta dos modelos sumiu: {MODELOS}"
    print("ok")


if __name__ == "__main__":
    if "--autoteste" in sys.argv:
        _autoteste()
    else:
        sys.exit(main())
