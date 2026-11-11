"""Auto-teste da emenda. Um comando, nada renderiza.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_emenda.py

A emenda existe porque um efeito que muda 0,4 s recodificava 54 s. O que se cobra
aqui é que o custo passe a seguir o que muda, e não a duração do vídeo.
"""
from __future__ import annotations

import subprocess
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import emenda as em
import ff


def _fonte(d: Path, dur=10) -> Path:
    p = d / "fonte.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=25:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-g", "25", "-c:a", "aac", "-shortest", str(p)], check=True)
    return p


# ---- o que a emenda monta ---------------------------------------------------


def test_sem_trecho_a_trocar_e_copia_pura(tmp: Path):
    plano = em.planeja(_fonte(tmp), [], tmp / "saida.mp4")
    assert plano.copiado == plano.total, "sobrou coisa para recodificar"
    assert all("-c" in c and "copy" in c for c in [plano.comandos[-1]]), \
        "a junção não copiou o fluxo"


def test_um_trecho_no_meio_codifica_so_ele(tmp: Path):
    fonte = _fonte(tmp)
    plano = em.planeja(fonte, [em.Trecho(4.0, 4.4, "glitch")], tmp / "saida.mp4")
    assert 0.3 < plano.recodificado < 1.5, \
        f"recodificou {plano.recodificado:.1f}s para mudar 0,4s"
    assert plano.copiado > 8.0, f"copiou só {plano.copiado:.1f}s de 10s"


def test_o_custo_segue_o_que_muda_e_nao_a_duracao(tmp: Path):
    """A afirmação central do candidato: dobrar o vídeo não dobra o trabalho."""
    curto = em.planeja(_fonte(tmp / "a", 10), [em.Trecho(4.0, 4.4, "g")], tmp / "a.mp4")
    longo = em.planeja(_fonte(tmp / "b", 40), [em.Trecho(4.0, 4.4, "g")], tmp / "b.mp4")
    assert abs(curto.recodificado - longo.recodificado) < 1.0, \
        "o vídeo quatro vezes maior recodificou mais para a mesma mudança"


def test_varios_trechos_saem_na_ordem(tmp: Path):
    plano = em.planeja(_fonte(tmp), [em.Trecho(2.0, 2.4, "a"),
                                     em.Trecho(6.0, 6.4, "b")], tmp / "s.mp4")
    inicios = [p.inicio for p in plano.pedacos]
    assert inicios == sorted(inicios), f"os pedaços saíram fora de ordem: {inicios}"


def test_a_juncao_usa_demultiplexador_e_nao_filtro(tmp: Path):
    """É a diferença entre copiar os bits e recodificá-los. Um teste para que
    ninguém troque de volta sem perceber."""
    plano = em.planeja(_fonte(tmp), [em.Trecho(4.0, 4.4, "g")], tmp / "s.mp4")
    juncao = " ".join(plano.comandos[-1])
    assert "-f concat" in juncao, "a junção não é pelo demultiplexador"
    assert "concat=n=" not in juncao, "a junção voltou a ser por filtro"


def test_trecho_fora_do_video_estoura(tmp: Path):
    erro = None
    try:
        em.planeja(_fonte(tmp), [em.Trecho(50.0, 50.4, "g")], tmp / "s.mp4")
    except Exception as e:
        erro = e
    assert erro is not None, "trecho depois do fim do vídeo passou"


def test_trechos_que_se_sobrepoem_estouram(tmp: Path):
    erro = None
    try:
        em.planeja(_fonte(tmp), [em.Trecho(2.0, 5.0, "a"),
                                 em.Trecho(4.0, 6.0, "b")], tmp / "s.mp4")
    except Exception as e:
        erro = e
    assert erro is not None and "sobrep" in str(erro).lower()


def test_dois_trechos_no_mesmo_grupo_nao_se_sobrepoem(tmp: Path):
    """Dois efeitos perto um do outro caem no MESMO grupo de quadros depois de
    ancorar. Antes deste caso, os pedaços saíam sobrepostos e a junção montava o
    vídeo com trecho repetido."""
    fonte = _fonte(tmp, 10)
    # 1,2s e 1,6s: com grupo de 1s, os dois ancoram em 1,0 e crescem até 2,0
    plano = em.planeja(fonte, [em.Trecho(1.2, 1.4, "a"),
                               em.Trecho(1.6, 1.8, "b")], tmp / "s.mp4")
    for x, y in zip(plano.pedacos, plano.pedacos[1:]):
        assert y.inicio >= x.fim - 0.001, \
            f"pedaços sobrepostos: {x.inicio:.2f}-{x.fim:.2f} e {y.inicio:.2f}-{y.fim:.2f}"
    assert abs(plano.total - em.ff.dur(fonte)) < 0.1, \
        f"os pedaços somam {plano.total:.2f}s de um vídeo de {em.ff.dur(fonte):.2f}s"


def test_trecho_no_comeco_exato(tmp: Path):
    plano = em.planeja(_fonte(tmp, 10), [em.Trecho(0.0, 0.4, "a")], tmp / "s.mp4")
    assert plano.pedacos[0].inicio == 0.0 and not plano.pedacos[0].copia


def test_trecho_no_fim_exato(tmp: Path):
    fonte = _fonte(tmp, 10)
    dur = em.ff.dur(fonte)
    plano = em.planeja(fonte, [em.Trecho(dur - 0.4, dur, "a")], tmp / "s.mp4")
    assert not plano.pedacos[-1].copia, "o último pedaço devia ser o substituído"
    assert abs(plano.total - dur) < 0.1


# ---- quadro-chave -----------------------------------------------------------


def test_o_corte_cai_num_quadro_chave(tmp: Path):
    """Cortar no meio de um grupo de quadros faz o vídeo piscar ou travar."""
    fonte = _fonte(tmp)
    chaves = em.quadros_chave(fonte)
    assert len(chaves) > 1, "o fixture não tem quadro-chave suficiente"
    plano = em.planeja(fonte, [em.Trecho(4.1, 4.5, "g")], tmp / "s.mp4")
    for p in plano.pedacos:
        if p.copia:
            assert any(abs(p.inicio - k) < 0.05 for k in chaves) or p.inicio == 0.0, \
                f"um pedaço copiado começa em {p.inicio}, fora de quadro-chave"


# ---- a prova de que não estragou --------------------------------------------


def test_o_miolo_copiado_e_identico_a_fonte(tmp: Path):
    """A prova mudou: antes eu comparava com a saída velha. Agora o miolo deixou
    de ser recodificado, então ele TEM que ser idêntico ao original."""
    fonte = _fonte(tmp, 10)
    saida = tmp / "saida.mp4"
    subs = {"g": _fonte(tmp / "sub", 1)}
    em.executa(em.planeja(fonte, [em.Trecho(4.0, 5.0, "g")], saida), subs)
    assert saida.exists(), "a emenda não produziu arquivo"
    assert abs(ff.dur(saida) - ff.dur(fonte)) < 0.3, "a emenda mudou a duração"

    # o trecho 6-9s não foi tocado: os quadros têm que ser os MESMOS.
    # Comparar por instante mediria o deslocamento de relógio da junção, não
    # degradação — os quadros batem e o PSNR por instante dá 40 dB.
    assert em.iguais(fonte, saida, 6.0, 3.0), "o miolo copiado divergiu da fonte"


def test_avisa_quando_nao_puder_copiar(tmp: Path):
    """Degradar calado transforma regressão de desempenho em mistério."""
    plano = em.planeja(_fonte(tmp), [], tmp / "s.mp4", forca_recodificar=True)
    assert plano.motivo_recodificou, "recodificou sem dizer por quê"


def test_a_emenda_sai_com_os_quadros_e_o_som_da_fonte(tmp: Path):
    """Com quadro B (o x264 de verdade), a cópia por `-to` levava os quadros até o próximo
    quadro-chave e o som de cada pedaço passava da imagem: o glitch saía com 2 quadros e 135 ms a
    mais em 10 s, e a imagem escorregava do som a cada emenda. Cada pedaço copiado leva os quadros
    dele e o som sai inteiro da fonte."""
    fonte = tmp / "b.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-shortest",
                    *ff.args_video("final", fps=None), *ff.args_audio(), str(fonte)], check=True)
    # a fonte emendada pela fábrica tem a imagem começando um quadro depois do som
    atrasada = tmp / "c.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-itsoffset", "0.033333", "-i", str(fonte), "-i", str(fonte),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", str(atrasada)], check=True)

    def mede(v):
        r = ff.run(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                    "stream=codec_type,nb_read_packets,duration", "-of", "csv=p=0", str(v)], capture=True, quiet=True)
        return {l.split(",")[0]: (float(l.split(",")[1]), int(l.split(",")[2])) for l in r.stdout.split()}
    for f in (fonte, atrasada):
        plano = em.planeja(f, [em.Trecho(5.0, 5.4, "g")], tmp / f"s{f.stem}.mp4")
        pd = next(p for p in plano.pedacos if not p.copia)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{pd.inicio:.3f}", "-to", f"{pd.fim:.3f}",
                        "-i", str(f), "-vf", "negate", *ff.args_video("efeito", fps=None), *ff.args_audio(),
                        str(tmp / "g.mp4")], check=True)
        em.executa(plano, {"g": tmp / "g.mp4"})
        a, b = mede(f), mede(plano.saida)
        assert b["video"][1] == a["video"][1], f"{f.name}: {b['video'][1]} quadros, a fonte tem {a['video'][1]}"
        assert abs(b["audio"][0] - a["audio"][0]) < 0.03, f"{f.name}: o som saiu com {b['audio'][0]:.3f}s, a fonte {a['audio'][0]:.3f}s"
        inicio = lambda v: float(ff.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                         "stream=start_time", "-of", "csv=p=0", str(v)], capture=True, quiet=True).stdout)
        assert abs(inicio(plano.saida) - inicio(f)) < 0.002, f"{f.name}: a imagem saiu {inicio(f) - inicio(plano.saida):.3f}s adiantada do som"
        # o quadro-chave em 6,0333 escrito 6.033 caía antes dele: a cópia voltava ao chave anterior
        assert em.iguais(f, plano.saida, 7.0, 2.0), f"{f.name}: o pedaço copiado depois da emenda não é a fonte"


def test_pedaco_que_comeca_fora_do_milesimo_nao_perde_quadro(tmp: Path):
    """O quadro-chave em 4,0666… escrito com três casas (4.067) caía depois dele: a busca exata
    pulava o primeiro quadro do pedaço recodificado, e o último saía duas vezes. `recorte` é a busca
    de quem recodifica um pedaço, e o vídeo sai com cada quadro no índice da fonte."""
    fonte = tmp / "k.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=8",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "1000", "-sc_threshold", "0",
                    "-force_key_frames", "expr:eq(n,122)+eq(n,182)", str(fonte)], check=True)
    plano = em.planeja(fonte, [em.Trecho(4.2, 4.5, "g")], tmp / "s.mp4")
    pd = next(p for p in plano.pedacos if not p.copia)
    assert abs(pd.inicio - 122 / 30) < 1e-3, plano.pedacos
    subprocess.run(["ffmpeg", "-y", "-v", "error", *em.recorte(pd), "-i", str(fonte), "-vf", "negate",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(tmp / "g.mp4")], check=True)
    em.executa(plano, {"g": tmp / "g.mp4"})

    def quadros(v):
        r = ff.run(["ffmpeg", "-v", "error", "-i", str(v), "-map", "0:v", "-f", "framemd5", "-"], capture=True, quiet=True)
        return [l.split(",")[-1].strip() for l in r.stdout.splitlines() if l and not l.startswith("#")]
    a, b = quadros(fonte), quadros(plano.saida)
    assert len(a) == len(b) == 240, (len(a), len(b))
    fora = [i for i in range(240) if not 122 <= i < 182 and a[i] != b[i]]
    assert not fora, f"quadros copiados fora do lugar: {fora[:5]}"
    dentro = quadros(tmp / "g.mp4")
    assert len(dentro) == 60, f"o pedaço recodificado saiu com {len(dentro)} quadros, não 60"


def main() -> int:
    casos = [
        ("sem trecho é cópia pura",        test_sem_trecho_a_trocar_e_copia_pura),
        ("um trecho codifica só ele",      test_um_trecho_no_meio_codifica_so_ele),
        ("custo segue o que muda",         test_o_custo_segue_o_que_muda_e_nao_a_duracao),
        ("vários trechos saem na ordem",   test_varios_trechos_saem_na_ordem),
        ("junção por demultiplexador",     test_a_juncao_usa_demultiplexador_e_nao_filtro),
        ("trecho fora do vídeo estoura",   test_trecho_fora_do_video_estoura),
        ("trechos sobrepostos estouram",   test_trechos_que_se_sobrepoem_estouram),
        ("dois trechos no mesmo grupo",    test_dois_trechos_no_mesmo_grupo_nao_se_sobrepoem),
        ("trecho no começo exato",         test_trecho_no_comeco_exato),
        ("trecho no fim exato",            test_trecho_no_fim_exato),
        ("o corte cai em quadro-chave",    test_o_corte_cai_num_quadro_chave),
        ("o miolo é idêntico à fonte",     test_o_miolo_copiado_e_identico_a_fonte),
        ("avisa quando não copiar",        test_avisa_quando_nao_puder_copiar),
        ("quadros e som da fonte",         test_a_emenda_sai_com_os_quadros_e_o_som_da_fonte),
        ("chave fora do milésimo",         test_pedaco_que_comeca_fora_do_milesimo_nao_perde_quadro),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        for nome, caso in casos:
            sub = Path(td) / re.sub(r"[^\w-]+", "_", nome)
            (sub / "a").mkdir(parents=True, exist_ok=True)
            (sub / "b").mkdir(parents=True, exist_ok=True)
            (sub / "sub").mkdir(parents=True, exist_ok=True)
            try:
                caso(sub)
                print(f"  ok   {nome}")
            except Exception as e:
                falhas.append((nome, e))
                print(f"  FALHA {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    if falhas:
        print("falhou: " + ", ".join(n for n, _ in falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
