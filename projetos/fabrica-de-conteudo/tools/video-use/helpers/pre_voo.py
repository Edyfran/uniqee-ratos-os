#!/usr/bin/env python3
"""Portão antes de gastar crédito no HeyGen. NÃO gerar sem passar aqui.

    python pre_voo.py voz_limpa.wav --transcript t_limpo.json --creditos 151 [--look <id>]

Sai 0 e imprime os parâmetros exatos da chamada quando tudo está pronto; sai 1 e
diz o que falta quando não está.

O look do avatar é de quem gera, não do código: `--look`, `"look"` no plano da
fábrica, ou `HEYGEN_LOOK` no ambiente ou no `.env.local` da raiz, ao lado das
chaves. Até 01/10/2026 o do dono estava escrito aqui e ia no pacote do aluno.
Sem look o portão passa e avisa: o agente lista os looks pelo MCP da HeyGen (skill fabrica-clone).

Existe porque 83% dos créditos de uma sessão foram embora no mesmo padrão,
repetido quatro vezes: gerar o vídeo, descobrir que o áudio estava errado, gerar
de novo. O erro nunca foi na hora de gerar — era sempre um passo antes que não
tinha sido feito. Um portão que mede antes custa um segundo; a geração custa
crédito e cinco minutos.

A aprovação por ouvido é obrigatória e não tem como o script adivinhar: ele exige
um arquivo `<audio>.ok` do lado, criado só depois de ELE ouvir. Áudio sem `.ok`
não gera, por mais verde que estejam as medidas.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import ff
import transcript as tr

# a receita travada: mudar qualquer um destes é mudar a peça, não o parâmetro
ENGINE = "avatar_v"
PROPORCAO = "9:16"
RESOLUCAO = "1080p"

LUFS_MIN, LUFS_MAX = -20.5, -16.0   # a faixa do `trata_voz` (alvo -18.9)
PAUSA_MAX = 0.60                    # acima disso o `apara_pausas` não rodou
CRED_POR_S = 0.80                   # tabela HeyGen: Avatar V = 48 créditos/min


def loudness(p: Path) -> float:
    try:
        return ff.lufs(p)
    except RuntimeError:
        return 0.0


def maior_pausa(p: Path) -> float:
    import apara_pausas as A
    db, lim = A.envelope(p)
    q = A.quietos(db, lim, 0.0, len(db) * A.HOP)
    return max((b - a for a, b in q), default=0.0)


def duracao(p: Path) -> float:
    return float(ff.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "csv=p=0", str(p)], capture=True, quiet=True).stdout.strip())


def look_padrao() -> str | None:
    """HEYGEN_LOOK do ambiente ou do .env.local da raiz. O valor nunca vai para o código."""
    if os.environ.get("HEYGEN_LOOK"):
        return os.environ["HEYGEN_LOOK"]
    env = Path(__file__).resolve().parents[3] / ".env.local"
    if env.is_file():
        for linha in env.read_text(encoding="utf-8").splitlines():
            k, _, v = linha.partition("=")
            if k.strip() == "HEYGEN_LOOK" and v.strip().strip("'\""):
                return v.strip().strip("'\"")
    return None


USD_POR_CREDITO_HEYGEN = 0.049   # US$ por crédito


def fecha_saldo(audio: Path, saldo: Path, depois: int) -> int:
    """Gasto da geração = saldo de antes (--abre-saldo) menos o de agora. Fica como estimado: o crédito
    vira US$ pela tabela, e o MCP da HeyGen cobra do plano."""
    if not saldo.exists():
        print(f"NÃO: falta {saldo.name} (rode antes de gerar com --abre-saldo)")
        return 1
    antes = int(saldo.read_text(encoding="utf-8").strip())
    gasto = antes - depois
    import pago
    pago.registra("heygen", "avatar", creditos=gasto, usd=gasto * USD_POR_CREDITO_HEYGEN, estimado=True, fonte=audio)
    saldo.unlink()
    print(f"heygen: {gasto} créditos (US$ {gasto * USD_POR_CREDITO_HEYGEN:.2f}, estimado) registrados no pago")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=Path)
    ap.add_argument("--transcript", type=Path)
    ap.add_argument("--creditos", type=int, help="saldo, pra avisar se não cabe")
    ap.add_argument("--abre-saldo", type=int, metavar="N",
                    help="créditos do get_current_user ANTES de gerar: fica num arquivo ao lado do áudio")
    ap.add_argument("--fecha-saldo", type=int, metavar="M",
                    help="créditos DEPOIS de gerar: registra N-M no pago (a HeyGen pelo MCP não passa pelo pago.faz)")
    ap.add_argument("--look", help="o look do avatar na HeyGen (padrão: HEYGEN_LOOK)")
    a = ap.parse_args()
    look = a.look or look_padrao()
    saldo = a.audio.with_suffix(a.audio.suffix + ".saldo")

    if a.fecha_saldo is not None:
        return fecha_saldo(a.audio, saldo, a.fecha_saldo)
    if not a.transcript:
        ap.error("pede --transcript (ou --fecha-saldo, depois de gerar)")

    falhas: list[str] = []
    if not a.audio.exists():
        print(f"NÃO: {a.audio} não existe")
        return 1

    if a.abre_saldo is not None:
        saldo.write_text(str(a.abre_saldo), encoding="utf-8")
    dur = duracao(a.audio)
    lu = loudness(a.audio)
    pausa = maior_pausa(a.audio)

    if not (LUFS_MIN <= lu <= LUFS_MAX):
        falhas.append(f"loudness {lu:.1f} LUFS fora de [{LUFS_MIN}, {LUFS_MAX}] "
                      f"— faltou `trata_voz.py`")
    if pausa > PAUSA_MAX:
        falhas.append(f"pausa de {pausa:.2f}s (teto {PAUSA_MAX}) "
                      f"— faltou `apara_pausas.py`")
    if not a.transcript.exists():
        falhas.append(f"transcrição {a.transcript.name} não existe — o plano da "
                      f"legenda precisa dela, e ela tem que ser do áudio FINAL")
    else:
        ws = tr.palavras(a.transcript)
        if not ws:
            falhas.append("transcrição sem palavras")
        elif abs(ws[-1]["end"] - dur) > 1.5:
            falhas.append(f"transcrição termina em {ws[-1]['end']:.1f}s e o áudio "
                          f"tem {dur:.1f}s — são de versões diferentes")
    ok = a.audio.with_suffix(a.audio.suffix + ".ok")
    if not ok.exists():
        falhas.append(f"falta a aprovação por ouvido: crie `{ok.name}` "
                      f"DEPOIS que ele ouvir o arquivo")

    custo = dur * CRED_POR_S
    print(f"{a.audio.name}  {dur:.1f}s | {lu:.1f} LUFS | maior pausa {pausa:.2f}s")
    print(f"custo estimado: {custo:.0f} créditos ({CRED_POR_S}/s, medido)")
    if a.creditos is not None:
        print(f"saldo: {a.creditos} — {'cabe' if custo <= a.creditos else 'NÃO CABE'}"
              f", sobrariam {a.creditos - custo:.0f}")
        if custo > a.creditos:
            falhas.append("não cabe no saldo")

    if falhas:
        print("\nNÃO GERAR:")
        for f in falhas:
            print(f"  - {f}")
        return 1

    print(f"\nPODE GERAR — create_video_from_avatar:")
    falta_look = 'falta o look: --look, "look" no plano ou HEYGEN_LOOK no .env.local'
    print(f"  avatarId    {look or falta_look}")
    print(f"  engine      {ENGINE}")
    print(f"  aspectRatio {PROPORCAO}      resolution {RESOLUCAO}")
    print(f"  audioAssetId  (subir {a.audio.name} como asset)")
    if a.abre_saldo is None:
        print(f"\nANTES de gerar: get_current_user e rode de novo com --abre-saldo <créditos>.")
    print(f"DEPOIS de gerar: get_current_user e rode `pre_voo.py {a.audio} --fecha-saldo <créditos>`"
          f" pra registrar o gasto no pago.")
    return 0


def _autoteste() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.wav"
        ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "sine=frequency=200:duration=3", "-ar", "48000",
                "-ac", "1", str(p)], quiet=True)
        assert abs(duracao(p) - 3.0) < 0.2, duracao(p)
        # sem o `.ok` do lado, o portão tem que fechar mesmo com o resto verde
        import subprocess
        r = subprocess.run([sys.executable, __file__, str(p),
                            "--transcript", str(Path(td) / "nada.json")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 1, r.stdout
        assert "aprovação por ouvido" in r.stdout, r.stdout
    # o look vem de quem gera; o ambiente manda sobre o .env.local
    os.environ["HEYGEN_LOOK"] = "f" * 32
    assert look_padrao() == "f" * 32, look_padrao()
    print("ok")


if __name__ == "__main__":
    if "--autoteste" in sys.argv:
        _autoteste()
    else:
        sys.exit(main())
