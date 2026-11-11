"""Auto-teste da costura B (ff.py). Sem framework — assert direto, um comando.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_ff.py

Nenhum caso renderiza vídeo de pipeline. O fixture é 1 segundo de 320x240 gerado
pelo próprio ffmpeg — é o preço de testar `probe` e `loudness` contra a saída real
em vez de contra um texto que eu inventei.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ff


# ---- fixtures ---------------------------------------------------------------


def _fixture(dir_: Path, com_audio: bool = True) -> Path:
    """1s de vídeo de teste. Gerado uma vez por execução, fora do modo seco."""
    saida = dir_ / ("com_audio.mp4" if com_audio else "sem_audio.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1"]
    if com_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(saida)]
    subprocess.run(cmd, check=True)
    return saida


# ---- modo seco --------------------------------------------------------------


def test_seco_nao_executa(tmp: Path):
    alvo = tmp / "nao_deve_existir.mp4"
    with ff.seco() as cmds:
        ff.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1", str(alvo)])
    assert not alvo.exists(), "modo seco executou o comando"
    assert len(cmds) == 1, f"esperava 1 comando gravado, veio {len(cmds)}"
    assert cmds[0][0] == "ffmpeg"
    assert str(alvo) in cmds[0]


def test_seco_devolve_sucesso():
    """O chamador não deve precisar de um `if seco` — o retorno tem a forma de sucesso."""
    with ff.seco():
        r = ff.run(["ffmpeg", "-version"])
    assert r.returncode == 0
    assert r.stdout == ""


def test_seco_grava_na_ordem():
    with ff.seco() as cmds:
        ff.run(["ffmpeg", "-i", "a.mp4", "a.out"])
        ff.run(["ffmpeg", "-i", "b.mp4", "b.out"])
    assert [c[2] for c in cmds] == ["a.mp4", "b.mp4"], "ordem dos comandos não foi preservada"


def test_seco_restaura_mesmo_com_erro(tmp: Path):
    try:
        with ff.seco():
            raise RuntimeError("estouro no meio do plano")
    except RuntimeError:
        pass
    alvo = tmp / "depois_do_erro.mp4"
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "testsrc=size=32x32:rate=1:duration=1", str(alvo)])
    assert alvo.exists(), "o modo seco vazou para fora do bloco depois de uma exceção"


def test_seco_aninhado_e_erro():
    """Aninhar seria estado global disfarçado — falha alto em vez de gravar no lugar errado."""
    erro = None
    with ff.seco():
        try:
            with ff.seco():
                pass
        except Exception as e:
            erro = e
    assert erro is not None, "seco aninhado passou calado"


# ---- medição ----------------------------------------------------------------


def test_probe_le_o_arquivo(video: Path):
    p = ff.probe(video)
    assert (p.largura, p.altura) == (320, 240), f"dimensões erradas: {p.largura}x{p.altura}"
    assert p.fps == 25, f"fps errado: {p.fps}"
    assert 0.9 <= p.duracao <= 1.2, f"duração fora do esperado: {p.duracao}"
    assert p.tem_audio is True


def test_probe_sem_faixa_de_audio(mudo: Path):
    """Vídeo sem áudio falha do mesmo jeito em todo lugar — respondendo, não estourando."""
    assert ff.probe(mudo).tem_audio is False


def test_probe_arquivo_que_nao_existe(tmp: Path):
    erro = None
    try:
        ff.probe(tmp / "fantasma.mp4")
    except Exception as e:
        erro = e
    assert erro is not None, "probe de arquivo inexistente passou calado"
    assert "fantasma.mp4" in str(erro), f"a mensagem não diz qual arquivo: {erro}"


def test_dur_bate_com_probe(video: Path):
    assert abs(ff.dur(video) - ff.probe(video).duracao) < 0.001


def test_dur_mede_arquivo_so_de_som(tmp: Path):
    """Efeito sonoro tem duração e não tem imagem. Exigir imagem travou o CRT."""
    som = tmp / "efeito.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.5", str(som)], check=True)
    assert 0.4 <= ff.dur(som) <= 0.6, f"duração errada num wav: {ff.dur(som)}"


def test_dur_de_arquivo_que_nao_existe_estoura(tmp: Path):
    erro = None
    try:
        ff.dur(tmp / "nao_existe.wav")
    except Exception as e:
        erro = e
    assert erro is not None and "nao_existe.wav" in str(erro)


def test_medicao_roda_no_modo_seco(video: Path):
    """probe e dur só leem — no modo seco continuam medindo, senão a cadeia não monta."""
    with ff.seco() as cmds:
        d = ff.dur(video)
    assert d > 0, "dur devolveu zero no modo seco"
    assert cmds == [], "medição entrou na lista de comandos a executar"


# ---- loudness ---------------------------------------------------------------


def test_loudness_devolve_os_cinco_valores(video: Path):
    m = ff.loudness(video)
    assert m is not None, "medição de loudness falhou no fixture"
    for chave in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
        assert chave in m, f"faltou {chave} na medição"


def test_limitador_segura_o_pico(tmp: Path):
    """O alimiter de fábrica corta no teto e depois sobe tudo de volta a 0 dBFS.
    Uma aula publicada saiu com pico em -0,6 dBTP, acima do teto do canal."""
    saida = tmp / "limitado.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1",
                    "-af", f"volume=12dB,{ff.limitador(0.5)}", "-c:a", "pcm_f32le",
                    str(saida)], check=True)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(saida), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    pico = float(r.stderr.split("max_volume:")[1].split("dB")[0])
    assert pico <= -5.7, f"o limitador deixou o pico em {pico} dBFS; o teto era -6,0"


def test_loudnorm_filtro_sem_medicao():
    f = ff.loudnorm_filter()
    assert f"I={ff.LOUDNORM_I}" in f
    assert f"TP={ff.LOUDNORM_TP}" in f
    assert f"LRA={ff.LOUDNORM_LRA}" in f
    assert "measured_I" not in f, "filtro de 1 passagem não pode carregar medida"


def test_loudnorm_segunda_passagem_carrega_os_cinco():
    """Invariante do ticket: a 2ª passagem sem os cinco valores é uma 1ª passagem cara."""
    m = {"input_i": "-19.4", "input_tp": "-3.2", "input_lra": "7.1",
         "input_thresh": "-29.8", "target_offset": "0.3"}
    f = ff.loudnorm_filter(m)
    assert "measured_I=-19.4" in f
    assert "measured_TP=-3.2" in f
    assert "measured_LRA=7.1" in f
    assert "measured_thresh=-29.8" in f
    assert "offset=0.3" in f
    assert "linear=true" in f


# ---- constantes de saída ----------------------------------------------------


def test_saida_padrao_do_canal():
    """1440p30 para de ser convenção lembrada."""
    assert ff.ALTURA == 1440
    assert ff.FPS == 30


def test_args_video_usam_as_constantes():
    a = ff.args_video()
    assert "libx264" in a
    assert a[a.index("-crf") + 1] == ff.CRF
    assert a[a.index("-preset") + 1] == ff.PRESET
    assert a[a.index("-pix_fmt") + 1] == ff.PIX_FMT


def test_args_video_por_qualidade():
    rascunho = ff.args_video("rascunho")
    final = ff.args_video()
    assert rascunho[rascunho.index("-preset") + 1] == "ultrafast"
    assert rascunho != final, "rascunho e final saíram com os mesmos parâmetros"


def test_args_video_qualidade_desconhecida_lista_as_validas():
    erro = None
    try:
        ff.args_video("cinema")
    except Exception as e:
        erro = e
    assert erro is not None, "qualidade inexistente passou calada"
    assert "final" in str(erro), f"o erro não lista as válidas: {erro}"


def test_args_audio():
    a = ff.args_audio()
    assert a[a.index("-b:a") + 1] == ff.AUDIO_BITRATE
    assert a[a.index("-ar") + 1] == ff.AUDIO_RATE


# ---- execução de verdade ----------------------------------------------------


def test_run_estoura_em_comando_que_falha():
    erro = None
    try:
        ff.run(["ffmpeg", "-i", "/caminho/que/nao/existe.mp4", "-f", "null", "-"], quiet=True)
    except Exception as e:
        erro = e
    assert erro is not None, "comando que falhou não levantou nada"


def test_run_calado_carrega_o_log_na_mensagem():
    """No modo calado ninguém viu o stderr — a mensagem tem que dizer o que houve."""
    erro = None
    try:
        ff.run(["ffmpeg", "-i", "/nao/existe.mp4", "-f", "null", "-"], quiet=True)
    except Exception as e:
        erro = e
    assert erro is not None
    assert "No such file" in str(erro), f"a mensagem não carrega o motivo: {erro}"


def test_run_sem_check_devolve_o_codigo():
    r = ff.run(["ffmpeg", "-i", "/nao/existe.mp4", "-f", "null", "-"], check=False, quiet=True)
    assert r.returncode != 0


def test_run_captura_a_saida():
    r = ff.run(["ffprobe", "-version"], capture=True, quiet=True)
    assert "ffprobe" in r.stdout


def test_taxa_mistura_e_guarda_o_alfa(tmp: Path):
    """25 → 30 por cópia repetia 1 quadro em 6 (o tranco no rosto); a mistura não repete nenhum, e o
    alfa, que o `framerate` sozinho joga fora, volta inteiro."""
    assert ff.taxa(30, 30) == "fps=30"
    fonte = tmp / "alfa25.mov"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=25:duration=1",
                    "-vf", "format=yuva444p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a='if(lt(X,32),0,255)'",
                    "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(fonte)], check=True)
    for alfa, esperado in (("", None), ("t", 0.5)):
        cad = ff.taxa(25, 30, alfa=alfa)
        saida = subprocess.run(["ffmpeg", "-v", "error", "-i", str(fonte), "-filter_complex", f"[0:v]{cad},format=rgba[v]",
                                "-map", "[v]", "-frames:v", "30", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        q = [saida[i:i + 64 * 64 * 4] for i in range(0, len(saida), 64 * 64 * 4)]
        assert len(q) == 30, f"{len(q)} quadros em 1 s a 30"
        assert len(set(q)) == 30, "a mistura repetiu quadro"
        transparente = sum(b == 0 for b in q[15][3::4]) / (64 * 64)
        if esperado:
            assert abs(transparente - esperado) < 0.05, f"o alfa não voltou: {transparente:.0%} transparente"


# ---- corrida ----------------------------------------------------------------


def test_hardware_tem_a_escada_inteira_e_so_quando_pedido():
    """Todo degrau da escada tem o seu no hardware, e o hardware só entra pedido."""
    import os
    assert set(ff.QUALIDADES) <= set(ff.QUALIDADES_HW), set(ff.QUALIDADES) - set(ff.QUALIDADES_HW)
    antes = os.environ.pop(ff.HARDWARE, None)
    try:
        assert ff.args_video()[1] == ff.CODEC_VIDEO, "o hardware entrou sem ninguém pedir"
        os.environ[ff.HARDWARE] = "1"
        esperado = ff.CODEC_HW if ff.tem_videotoolbox() else ff.CODEC_VIDEO
        args = ff.args_video("reel", fps=None)
        assert args[1] == esperado and "-g" in args, args
    finally:
        os.environ.pop(ff.HARDWARE, None)
        if antes is not None:
            os.environ[ff.HARDWARE] = antes


def test_hardware_auto_escolhe_por_degrau_e_nunca_toca_o_sem_perda():
    """`auto` põe o hardware só onde a medição de 23/10 mandou; "1" e "0" seguem como eram."""
    import os
    antes = os.environ.pop(ff.HARDWARE, None)
    tinha = ff.tem_videotoolbox
    try:
        ff.tem_videotoolbox = lambda: True
        os.environ[ff.HARDWARE] = "auto"
        for q in ("previa", "composicao", "efeito"):
            a = ff.args_video(q)
            assert a[1] == ff.CODEC_HW and a[a.index("-q:v") + 1] == ff.QUALIDADES_HW[q], (q, a)
        for q in ("final", "reel", "rascunho"):
            assert ff.args_video(q)[1] == ff.CODEC_VIDEO, f"auto pôs o hardware em {q}"
        assert ff.codificador() == ff.CODEC_VIDEO, "sem degrau, o auto não arrisca o hardware"
        assert ff.args_sem_perda()[1] == ff.CODEC_VIDEO and "-qp" in ff.args_sem_perda()
        os.environ[ff.HARDWARE] = "1"
        assert all(ff.args_video(q)[1] == ff.CODEC_HW for q in ff.QUALIDADES), "1 deixou de ser sempre"
        os.environ[ff.HARDWARE] = "0"
        assert all(ff.args_video(q)[1] == ff.CODEC_VIDEO for q in ff.QUALIDADES), "0 deixou de ser nunca"
        ff.tem_videotoolbox = lambda: False   # Windows, Linux, Mac Intel: tudo cai no x264
        for v in ("1", "auto"):
            os.environ[ff.HARDWARE] = v
            assert all(ff.args_video(q)[1] == ff.CODEC_VIDEO for q in ff.QUALIDADES), v
    finally:
        ff.tem_videotoolbox = tinha
        os.environ.pop(ff.HARDWARE, None)
        if antes is not None:
            os.environ[ff.HARDWARE] = antes


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        video = _fixture(tmp, com_audio=True)
        mudo = _fixture(tmp, com_audio=False)

        casos = [
            ("seco não executa",              lambda: test_seco_nao_executa(tmp)),
            ("seco devolve sucesso",          test_seco_devolve_sucesso),
            ("hardware só quando pedido",     test_hardware_tem_a_escada_inteira_e_so_quando_pedido),
            ("hardware auto por degrau",      test_hardware_auto_escolhe_por_degrau_e_nunca_toca_o_sem_perda),
            ("seco grava na ordem",           test_seco_grava_na_ordem),
            ("seco restaura após erro",       lambda: test_seco_restaura_mesmo_com_erro(tmp)),
            ("seco aninhado é erro",          test_seco_aninhado_e_erro),
            ("probe lê o arquivo",            lambda: test_probe_le_o_arquivo(video)),
            ("probe sem faixa de áudio",      lambda: test_probe_sem_faixa_de_audio(mudo)),
            ("probe de arquivo ausente",      lambda: test_probe_arquivo_que_nao_existe(tmp)),
            ("dur bate com probe",            lambda: test_dur_bate_com_probe(video)),
            ("dur mede arquivo só de som",    lambda: test_dur_mede_arquivo_so_de_som(tmp)),
        ("dur de arquivo ausente",        lambda: test_dur_de_arquivo_que_nao_existe_estoura(tmp)),
        ("medição roda no modo seco",     lambda: test_medicao_roda_no_modo_seco(video)),
            ("loudness dá os cinco valores",  lambda: test_loudness_devolve_os_cinco_valores(video)),
            ("limitador segura o pico",       lambda: test_limitador_segura_o_pico(tmp)),
            ("loudnorm 1ª passagem",          test_loudnorm_filtro_sem_medicao),
            ("loudnorm 2ª carrega os cinco",  test_loudnorm_segunda_passagem_carrega_os_cinco),
            ("saída padrão do canal",         test_saida_padrao_do_canal),
            ("args_video usa as constantes",  test_args_video_usam_as_constantes),
            ("args_video por qualidade",      test_args_video_por_qualidade),
            ("qualidade errada lista válidas", test_args_video_qualidade_desconhecida_lista_as_validas),
            ("args_audio",                    test_args_audio),
            ("run estoura em falha",          test_run_estoura_em_comando_que_falha),
            ("run calado carrega o log",      test_run_calado_carrega_o_log_na_mensagem),
            ("run sem check devolve código",  test_run_sem_check_devolve_o_codigo),
            ("run captura a saída",           test_run_captura_a_saida),
            ("taxa mistura e guarda o alfa",  lambda: test_taxa_mistura_e_guarda_o_alfa(tmp)),
            ("29,97 do iPhone troca o relógio", lambda: test_quase_na_taxa(tmp)),
            ("trechos somam na grade de quadros", lambda: test_trechos_somam_na_grade_de_quadros(tmp)),
            ("vfr guarda o fps antigo",       lambda: test_probe_vfr_guarda_o_fps_antigo_e_a_media_a_parte(tmp)),
        ]

        falhas = []
        for nome, caso in casos:
            try:
                caso()
                print(f"  ok   {nome}")
            except Exception as e:
                falhas.append((nome, e))
                print(f"  FALHA {nome}: {e}")

    print(f"\n{len(casos) - len(falhas)}/{len(casos)} passaram")
    if falhas:
        print("falhou: " + ", ".join(n for n, _ in falhas))
    return 1 if falhas else 0


def test_quase_na_taxa(tmp: Path):
    """O render.py troca o relógio só da fonte a 29,97 (o -r 30 copiava um quadro a cada ~33 s)."""
    import render
    for taxa, quer in (("30000/1001", True), ("30", False), ("25", False)):
        f = tmp / f"taxa-{taxa.replace('/', '_')}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=64x48:rate={taxa}:duration=3",
                        str(f)], check=True)
        assert render.quase_na_taxa(f, 30) is quer, f"{taxa}: esperava {quer}"


def _quadros_e_som(p: Path) -> tuple[int, float]:
    """Quadros de vídeo contados de verdade, e a duração da faixa de som."""
    q = ff.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                "stream=nb_read_frames", "-of", "csv=p=0", str(p)], capture=True, quiet=True).stdout
    a = ff.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                "stream=duration", "-of", "csv=p=0", str(p)], capture=True, quiet=True).stdout
    return int(q.split()[0]), float(a.split()[0])


def test_trechos_somam_na_grade_de_quadros(tmp: Path):
    """43 trechos de duração fora da grade, bruto a 30 fps, saída a 24: cada trecho arredondava PARA CIMA
    na grade e o corte saía 0,9 s maior que o plano (18,958 s contra 18,046 s), com a legenda, as peças e
    os sons adiantados sobre a voz. O fim de cada trecho agora é round(soma * fps) quadros: o desvio em
    qualquer emenda cabe em meio quadro, e a imagem e o som do trecho têm o mesmo tamanho."""
    import render
    fps = 24
    fonte = tmp / "denso.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=30:duration=30",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=30", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(fonte)], check=True)
    durs = [0.259 + 0.037 * (i % 7) for i in range(43)]        # 6,2 a 11,1 quadros: nunca na grade
    ranges, t = [], 0.2
    for d in durs:
        ranges.append({"source": "A", "start": round(t, 3), "end": round(t + d, 3)})
        t += d + 0.31
    plano = [r["end"] - r["start"] for r in ranges]
    edit = tmp / "denso"
    edl = {"version": 1, "sources": {"A": str(fonte)}, "ranges": ranges, "grade": "none", "overlays": []}
    partes = render.extract_all_segments(edl, edit, preview=False, out_height=120, fps=fps)
    base = edit / "base.mp4"
    render.concat_segments(partes, base, edit)

    soma, feitos = 0.0, 0
    for i, (p, d) in enumerate(zip(partes, plano)):
        soma += d
        n, som = _quadros_e_som(p)
        feitos += n
        assert abs(feitos / fps - soma) <= 0.5 / fps + 1e-6, \
            f"na emenda {i} o corte tem {feitos / fps:.3f} s e o plano {soma:.3f} s (mais que meio quadro)"
        assert abs(som - n / fps) < 0.005, f"trecho {i}: {n} quadros ({n / fps:.4f} s) e som de {som:.4f} s"
    n, som = _quadros_e_som(base)
    assert abs(n / fps - soma) <= 1 / fps, f"o corte tem {n / fps:.3f} s e o plano {soma:.3f} s"
    assert abs(som - n / fps) < 0.05, f"depois da costura, imagem {n / fps:.3f} s e som {som:.3f} s"


def test_probe_vfr_guarda_o_fps_antigo_e_a_media_a_parte(tmp: Path):
    """Taxa variável: `fps` continua o r_frame_rate (camera.py, checks.py leem isso); a média vai
    em `fps_medio`, que só a normalização do bruto do celular usa."""
    f = tmp / "vfr.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=64x48:rate=30:duration=5", "-vf", "select='gt(mod(n,5),0)'",
                    "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    p = ff.probe(f)
    assert p.vfr and p.fps == 30 and p.fps_medio == 24, p
    cfr = ff.probe(_fixture(tmp))
    assert not cfr.vfr and cfr.fps == cfr.fps_medio == 25, cfr


if __name__ == "__main__":
    sys.exit(main())
