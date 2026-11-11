"""Auto-teste da fábrica, pelo modo seco. Um comando, nenhum render.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_fabrica.py

A fábrica em modo seco é a costura de teste do projeto: plano entra, cadeia de
comandos e EDL saem, sem esperar vídeo. Todo caso aqui existe porque o erro
correspondente já custou um render.
"""
from __future__ import annotations

import json
import subprocess
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fabrica as fb
import ff


def _fonte(dir_: Path, nome="live.mp4", dur=8) -> Path:
    saida = dir_ / nome
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=640x400:rate=25:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}",
                    # mudo nos vãos entre as palavras do `_transcript`: o corte mede a voz no áudio
                    "-af", "volume=0:enable='gte(mod(t+0.3,0.4),0.3)'",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(saida)], check=True)
    return saida


def _transcript(dir_: Path, fonte: Path) -> Path:
    palavras = []
    t = 0.5
    for tok in "essa aula mostra como cortar a a live inteira sem mexer na mão".split():
        palavras.append({"text": tok, "start": round(t, 2), "end": round(t + 0.3, 2),
                         "type": "word"})
        t += 0.4
    p = dir_ / "t.json"
    p.write_text(json.dumps({"words": palavras, "duration": 8.0}), encoding="utf-8")
    return p


def _plano(dir_: Path, estilo="aula-ccnp", **extra) -> dict:
    fonte = _fonte(dir_)
    plano = {
        "estilo": estilo,
        "fonte": str(fonte),
        "transcript": str(_transcript(dir_, fonte)),
        "slug": "teste",
        "projeto": "provas",
        "janelas": [[0.4, 5.0]],
        "saida": str(dir_ / "saida"),
    }
    plano.update(extra)
    return plano


def _cmds(seco) -> str:
    return "\n".join(" ".join(c) for c in seco.comandos)


def _arquivo(seco) -> tuple[Path, str]:
    """O plano resolvido que o helper lê, do primeiro passo que o escreve (a transcrição não escreve)."""
    return next(p.arquivo for p in seco.passos if p.arquivo)


def _voz(dir_: Path, dur=8) -> Path:
    """Um take de voz. O bruto `avatar` parte de áudio, não de imagem."""
    saida = dir_ / "take.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
                    str(saida)], check=True)
    return saida


def _plano_vsl(dir_: Path, **extra) -> dict:
    voz = _voz(dir_)
    plano = {
        "estilo": "vsl",
        "fonte": str(voz),
        "transcript": str(_transcript(dir_, voz)),
        "slug": "oferta",
        "projeto": "provas",
        "saida": str(dir_ / "saida"),
    }
    plano.update(extra)
    return plano


# ---- o bruto avatar ---------------------------------------------------------
#
# A VSL era uma cadeia chamada à mão, com a ordem escrita em prosa num LEIA-ME
# dentro de uma pasta de vídeo. O modo seco não cobria um passo dela — e foi
# gerando sem conferir que 83% dos créditos de uma sessão foram embora.


def test_avatar_corta_no_audio_e_nao_renderiza(tmp: Path):
    seco = fb.fabrica(_plano_vsl(tmp), seco=True)
    cmds = _cmds(seco)
    assert "trata_voz.py" in cmds, "a voz tem que ser tratada antes de gerar"
    assert "apara_pausas.py" in cmds, "o corte do avatar roda no áudio"
    assert cmds.index("ouvido.py confere") < cmds.index("pre_voo.py"), (
        "o ouvido reprova antes do portão: o whisper apaga o falso começo")
    assert "render.py" not in cmds, (
        "avatar não passa pelo render: não existe quadro para cortar quando o "
        "corte acontece"
    )


def test_avatar_sem_os_blocos_para_no_portao(tmp: Path):
    seco = fb.fabrica(_plano_vsl(tmp), seco=True)
    assert "pre_voo.py" in _cmds(seco), "o portão tem que estar na cadeia"
    assert seco.passos[-1].nome == "portão do HeyGen", (
        "sem os blocos gerados a cadeia PARA no portão — gerar custa crédito e a "
        f"fábrica não gera sozinha. Último passo: {seco.passos[-1].nome}"
    )


def test_avatar_com_blocos_emenda_pelo_junta(tmp: Path):
    blocos = [str(_fonte(tmp, f"b{i}.mp4", dur=2)) for i in (1, 2)]
    seco = fb.fabrica(_plano_vsl(tmp, gerado=blocos), seco=True)
    cmds = _cmds(seco)
    assert "junta.py" in cmds, "os blocos do HeyGen se emendam pelo junta.py"
    assert "-f concat" not in cmds, (
        "concat do ffmpeg mantém a taxa do primeiro arquivo sem reescrever o "
        "relógio: o HeyGen entrega a 25 fps e o projeto roda a 30"
    )


def test_a_afinacao_do_estilo_chega_no_apara_pausas(tmp: Path):
    seco = fb.fabrica(_plano_vsl(tmp), seco=True)
    apara = next(p for p in seco.passos if "apara_pausas.py" in " ".join(p.cmd))
    cmd = " ".join(apara.cmd)
    assert "--afinacao tight" in cmd, f"a afinação do estilo tem que mandar: {cmd}"
    assert "--sil-cut 0.04" in cmd, (
        "o ajuste do estilo tem que chegar no helper, senão o corte da VSL e o "
        f"que a fábrica calcula viram dois números com o mesmo nome: {cmd}"
    )


def test_o_estilo_escolhe_o_queimador_de_legenda(tmp: Path):
    """Dois jeitos de entregar a legenda: quem escolhe é o estilo, não o chamador."""
    (tmp / "v").mkdir(parents=True, exist_ok=True)
    (tmp / "l").mkdir(parents=True, exist_ok=True)
    viral = fb.fabrica(_plano(tmp / "v", estilo="reel-mono"), seco=True)
    assert "captions_viral.py" in _cmds(viral), "o padrão do recurso é a legenda com direção"

    liso = fb.fabrica(_plano(tmp / "l", estilo="reel-mono",
                             adaptadores={"legenda": "liso"}), seco=True)
    cmds = _cmds(liso)
    assert "legendar.py" in cmds, f"o plano pediu 'liso' e não veio: {cmds}"
    assert "captions_viral.py" not in cmds, "os dois queimadores entraram na mesma cadeia"


def test_adaptador_que_nao_existe_falha_listando(tmp: Path):
    erro = None
    try:
        fb.fabrica(_plano(tmp, estilo="reel-mono",
                          adaptadores={"legenda": "inventado"}), seco=True)
    except Exception as e:
        erro = e
    assert erro is not None, "adaptador inventado passou"
    assert "viral" in str(erro) and "liso" in str(erro), f"não lista os válidos: {erro}"


def test_legenda_pedida_sem_plano_gera_os_cards(tmp: Path):
    """O estilo pediu legenda e o plano não trouxe o plano de cards.

    Antes: `e.tem('legenda')` dava verdadeiro e nenhum comando entrava — o
    recurso sumia calado e o vídeo saía sem legenda nenhuma.
    """
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    cmds = _cmds(seco)
    assert "cards_da_fala.py" in cmds, f"ninguém gerou o plano de cards: {cmds}"
    assert "captions_viral.py" in cmds, "gerou o plano e não queimou"


def test_legenda_gerada_anda_no_tempo_do_corte(tmp: Path):
    """A transcrição está no tempo do bruto; a legenda queima no vídeo cortado.

    Antes: o `cards_da_fala` lia a transcrição crua, e cada silêncio que o corte
    tirava atrasava a legenda. No curto do kit de Lorcana (28/09) ela chegou
    2,4 s atrasada no fim, e as duas últimas falas caíram depois do vídeo.
    """
    plano = _plano(tmp, estilo="reel-camera", janelas=[[0.4, 1.8], [3.2, 5.0]])
    seco = fb.fabrica(plano, seco=True)
    passo = _passo(seco, "cards da fala")
    assert passo.arquivo, "a legenda não recebeu a transcrição no tempo do corte"
    caminho, texto = passo.arquivo
    assert str(caminho) in passo.cmd, f"o comando não lê a transcrição cortada: {passo.cmd}"

    bruto = json.loads(Path(plano["transcript"]).read_text(encoding="utf-8"))["words"]
    cortada = json.loads(texto)["words"]
    fica = [w for w in bruto
            if any(t["start"] <= (w["start"] + w["end"]) / 2 <= t["end"] for t in seco.edl)]
    assert len(cortada) == len(fica), \
        f"palavra que o corte tirou continua na legenda: {len(cortada)} de {len(fica)}"
    for orig, nova in zip(fica, cortada):
        assert nova["start"] == fb.tempo_de_saida(seco.edl, orig["start"]), \
            f"'{orig['text']}' fora do lugar: {nova['start']} (bruto {orig['start']})"
    total = sum(t["end"] - t["start"] for t in seco.edl)
    assert cortada[-1]["end"] <= total + 0.05, "a última fala passa do fim do vídeo"
    assert cortada[len([w for w in fica if w["start"] < 2])]["start"] < 3.2, \
        "a segunda janela não adiantou"


def test_por_bloco_num_bruto_so_trata_a_voz_pela_cadeia_do_microfone(tmp: Path):
    """`voz.por_bloco` declarado num plano sem blocos rodava o realce do render (afftdn), que abafa a voz.
    Agora o render sai sem ele e a fala passa por trata_voz, como no bloco."""
    seco = fb.fabrica(_plano(tmp, estilo="reel-camera", voz={"tratamento": "realce", "por_bloco": True}), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes.index("render") < nomes.index("trata a voz") < nomes.index("voz do vídeo"), nomes
    assert "--voice-enhance" not in _passo(seco, "render").cmd
    (tmp / "sem").mkdir()
    sem = fb.fabrica(_plano(tmp / "sem", estilo="reel-camera", voz={"tratamento": "realce", "por_bloco": False}), seco=True)
    assert "trata a voz" not in [p.nome for p in sem.passos] and "--voice-enhance" in _passo(sem, "render").cmd


def test_voz_isolada_entra_antes_do_render(tmp: Path):
    """Gravação em loja cheia: o realce não tira conversa de fundo, o isolador tira.

    Com `voz.tratamento = isola`, o render lê a fonte com a voz isolada — e SEM o
    realce por cima: o afftdn dele (piso -25 dB) toma a voz limpa por ruído. No
    episódio 1 do pré-release (29/09) o centro do som caiu de 1.117 para 679 Hz,
    o agudo acima de 8 kHz perdeu 10,7 dB, e o dono ouviu "um maluco falando".
    """
    seco = fb.fabrica(_plano(tmp, estilo="reel-camera", voz={"tratamento": "isola"}),
                      seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "isola a voz" in nomes, f"o isolamento não entrou: {nomes}"
    assert nomes.index("isola a voz") < nomes.index("render"), f"isolou depois: {nomes}"
    render = _passo(seco, "render")
    isolada = _passo(seco, "isola a voz").saida
    # o extra é JSON: no Windows o caminho vem com a barra invertida escapada
    assert isolada.as_posix() in render.extra.replace("\\\\", "/"), "o render continua lendo o bruto com barulho"
    assert isolada in render.entradas, "o cache do render não enxerga a fonte isolada"
    assert "--voice-enhance" not in render.cmd, "o realce por cima do isolador abafa a voz"

    (tmp / "comum").mkdir()
    comum = fb.fabrica(_plano(tmp / "comum", estilo="reel-camera"), seco=True)
    assert "isola a voz" not in [p.nome for p in comum.passos], \
        "isolou sem o estilo pedir: é crédito gasto à toa"


def test_bloco_sai_de_janelas_do_bruto(tmp: Path):
    """O curto de abertura de pacote: o conteúdo é a carta, não a fala.

    Cada bloco sai de janelas escolhidas do bruto — o corte por palavra jogaria
    fora o rasgo e a carta, que não têm fala. A voz é isolada UMA vez, e todo
    recorte lê a fonte limpa.
    """
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "kit.mp4", dur=8)
    plano = {"estilo": "lorcana-curto", "slug": "pacote-1", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "voz": {"tratamento": "isola"}, "faixa": "acustico-inspirador",
             "blocos": [{"nome": "abertura", "janelas": [[0.5, 2.0]]},
                        {"nome": "pacote", "janelas": [[3.0, 4.5], [5.0, 6.0]]}]}
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes.count("isola a voz") == 1, f"isolou mais de uma vez, ou nenhuma: {nomes}"
    assert nomes.index("isola a voz") < nomes.index("abertura: recorte"), nomes
    for b in ("abertura", "pacote"):
        for etapa in ("recorte", "legenda, peças e câmera", "som"):
            assert f"{b}: {etapa}" in nomes, f"falta '{b}: {etapa}': {nomes}"
    recorte = _passo(seco, "pacote: recorte")
    edl = json.loads(recorte.arquivo[1])
    assert [(r["start"], r["end"]) for r in edl["ranges"]] == [(3.0, 4.5), (5.0, 6.0)], edl
    assert list(edl["sources"].values()) == [str(fb._fonte_isolada(Path(seco.passos[0].saida).parent))], \
        f"o recorte não lê a fonte isolada: {edl['sources']}"
    assert abs(seco.duracao - 4.0) < 0.01, f"duração errada: {seco.duracao}"
    # O volume é do vídeo inteiro: bloco sem fala normalizado sozinho subia o
    # resto de conversa 26 dB e virava ruído (episódio 1 do pré-release, 29/09).
    assert "--no-loudnorm" in recorte.cmd, "o bloco se normalizou sozinho"
    assert "--voice-enhance" not in recorte.cmd, "o realce por cima do isolador abafa a voz"
    assert any("com trilha" in n for n in nomes), f"ninguém acertou o volume do episódio: {nomes}"
    mudo = fb.fabrica({**plano, "blocos": [{"nome": "rasgo", "janelas": [[0.5, 2.0]],
                                            "mudo": True}]}, seco=True)
    assert "--mudo" in _passo(mudo, "rasgo: recorte").cmd, "o bloco mudo saiu com som"
    assert "--mudo" not in recorte.cmd, "silenciou bloco que tem fala"
    assert seco.final.resolve() == (tmp / "saida" / "provas" / "pacote-1.mp4").resolve(), \
        seco.final


def test_bloco_com_voz_gravada_por_cima(tmp: Path):
    """Abertura e encerramento: ele grava só a voz; a imagem sai do bruto.

    O bloco dura o que a fala dura (mais uma folga), a imagem entra muda e a
    voz passa pela cadeia do microfone dele antes de assentar.
    """
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "kit.mp4", dur=8)
    voz = _voz(tmp, dur=2)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte), "faixa": "acustico-inspirador",
             "blocos": [{"nome": "abertura", "janelas": [[1.0, 1.0]], "voz": str(voz)}]}
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    ordem = ["abertura: trata a voz", "abertura: recorte", "abertura: voz do bloco",
             "abertura: legenda, peças e câmera"]
    assert all(n in nomes for n in ordem), f"falta passo: {nomes}"
    assert [nomes.index(n) for n in ordem] == sorted(nomes.index(n) for n in ordem), nomes
    recorte = _passo(seco, "abertura: recorte")
    assert "--mudo" in recorte.cmd, "a imagem do bruto entrou com o som da loja"
    janela = json.loads(recorte.arquivo[1])["ranges"][0]
    assert abs((janela["end"] - janela["start"]) - (2.0 + fb.FOLGA_VOZ)) < 0.01, janela
    assert abs(seco.duracao - (2.0 + fb.FOLGA_VOZ)) < 0.01, seco.duracao
    base = _passo(seco, "abertura: voz do bloco").saida
    assert str(base) in _passo(seco, "abertura: legenda, peças e câmera").cmd, \
        "as peças foram postas no vídeo sem a voz"


def test_bloco_com_voz_sintetica_nao_passa_pelo_microfone(tmp: Path):
    """Voz `cru` (a do Eleven v4) entra no bloco como chegou: rnnoise e EQ do OBS
    em cima dela tratariam o que não tem ruído."""
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "tela.mp4", dur=8)
    voz = _voz(tmp, dur=2)
    plano = {"estilo": "aula-narrada", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "blocos": [{"nome": "demo", "janelas": [[1.0, 1.0]], "voz": str(voz)}]}
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "demo: trata a voz" not in nomes, nomes
    assert str(voz) in _passo(seco, "demo: voz do bloco").cmd, "a voz do bloco não é a que chegou"


def test_curto_com_cama_sai_no_alvo_dele(tmp: Path):
    """A cama de trilha re-normaliza a mistura: sem alvo, o `mixa` entrega em -16
    LUFS (web), e o curto do Lorcana sairia 2 dB abaixo dos outliers medidos."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "kit.mp4", dur=4)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "recursos": ["trilha"], "adaptadores": {"trilha": "cama"},
             "faixa": "acustico-inspirador", "blocos": [{"nome": "b", "janelas": [[0, 2]]}]}
    cmd = _passo(fb.fabrica(plano, seco=True), "com trilha").cmd
    assert cmd[cmd.index("--alvo") + 1] == "-14.0", f"o curto não pediu -14: {cmd}"
    # Curto de mãos tem trecho inteiro sem fala: com a cama de aula (-31,5) a
    # trilha ficava 14 dB abaixo da voz e o bloco mudo soava vazio. Em -24 ela
    # cobria a moeda de cada carta (ele pediu a trilha mais baixa, 29/09).
    assert cmd[cmd.index("--cama") + 1] == "-27.0", f"a cama do curto mudou: {cmd}"
    vsl = _passo(fb.fabrica(_vsl_blocos(tmp), seco=True), "com trilha").cmd
    assert "--alvo" not in vsl, f"a VSL mudou de volume sem ninguém pedir: {vsl}"
    assert "--cama" not in vsl, f"a cama da VSL mudou sem ninguém pedir: {vsl}"


def test_efeito_nao_abaixa_a_trilha(tmp: Path):
    """No bloco mudo só soa efeito: a moeda de cada carta abaixava a cama como se
    fosse fala, e a trilha bombeava doze vezes por pacote (pré-release, 29/09).
    O `mixa` só abaixa a cama onde há voz, e só mede a voz ali."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "kit.mp4", dur=8)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte), "faixa": "acustico-inspirador",
             "blocos": [{"nome": "fala", "janelas": [[0, 2]]},
                        {"nome": "cartas", "janelas": [[3, 6]], "mudo": True},
                        {"nome": "fim", "janelas": [[6, 7.5]]}]}
    cmd = _passo(fb.fabrica(plano, seco=True), "com trilha").cmd
    assert cmd[cmd.index("--fala") + 1] == "0.00:2.00,5.00:6.50", f"voz no lugar errado: {cmd}"
    calado = {**plano, "blocos": [{**b, "mudo": True} for b in plano["blocos"]]}
    cmd = _passo(fb.fabrica(calado, seco=True), "com trilha").cmd
    assert cmd[cmd.index("--fala") + 1] == "", f"sem voz nenhuma, algo ainda abaixa a cama: {cmd}"
    vsl = _passo(fb.fabrica(_vsl_blocos(tmp), seco=True), "com trilha").cmd
    assert "--fala" not in vsl, f"a VSL, que fala o tempo todo, mudou de ducking: {vsl}"


def test_janela_congela_o_ultimo_quadro(tmp: Path):
    """Carta que passa rápido na mão (0,8 s) não dá tempo de ler o preço: a janela
    ganha um terceiro número, os segundos de quadro parado no fim dela. A que demora
    ganha um quarto, a velocidade — o que o congelado alonga, a demora devolve."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "lote.mp4", dur=8)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "blocos": [{"nome": "cartas", "janelas": [[1.0, 1.8, 0.6], [3.0, 4.0], [4.0, 6.0, 0, 2.0]],
                         "mudo": True}]}
    seco = fb.fabrica(plano, seco=True)
    edl = json.loads(_passo(seco, "cartas: recorte").arquivo[1])
    assert edl["ranges"][0].get("congela") == 0.6 and "congela" not in edl["ranges"][1], edl["ranges"]
    # o quarto número acelera: a demora dele com uma carta na mão passa em 2x
    assert edl["ranges"][2].get("velocidade") == 2.0 and "velocidade" not in edl["ranges"][1], edl["ranges"]
    assert abs(seco.duracao - 3.4) < 0.01, f"congelado ou acelerado fora da duração: {seco.duracao}"


def test_corte_congela_fim_segura_o_final(tmp: Path):
    """`corte.congela_fim`: o vídeo segura o fim em vez de acabar na última palavra. A última faixa estica
    primeiro até a cauda que o bruto tem (sem passar da janela do plano) e o resto vira quadro parado.
    Com 0, o padrão, o corte sai como sempre saiu."""
    plano = _plano(tmp, janelas=[])                      # o bruto inteiro
    bruto = ff.dur(Path(plano["fonte"]))
    base = fb.fabrica(plano, seco=True)
    fim = base.edl[-1]["end"]
    assert "congela" not in base.edl[-1] and fim < bruto - 1.0, base.edl[-1]

    zero = fb.fabrica({**plano, "corte": {"congela_fim": 0}}, seco=True)
    assert zero.edl == base.edl and zero.duracao == base.duracao, "com 0 o corte não pode mudar"

    # pede mais do que o bruto guarda depois do corte: estica até o fim dele e congela o resto
    ultimo = fb.fabrica({**plano, "corte": {"congela_fim": 4.0}}, seco=True)
    faixa = ultimo.edl[-1]
    assert abs(faixa["end"] - bruto) < 0.01, faixa
    assert abs(faixa["congela"] - (4.0 - (bruto - fim))) < 0.01, faixa
    assert abs(ultimo.duracao - base.duracao - 4.0) < 0.01, f"a duração do corte esquece o quadro parado: {ultimo.duracao}"

    # a janela do plano é o teto da cauda natural: o fim não devolve a fala que o editor tirou
    janela = fb.fabrica({**_plano(tmp), "corte": {"congela_fim": 2.0}}, seco=True)        # janela [0.4, 5.0]
    faixa = janela.edl[-1]
    assert faixa["end"] == 5.0 and faixa["congela"] == 2.0, faixa


def test_bloco_recorta_o_vertical_de_outro_bruto(tmp: Path):
    """O semanal vem em vários clipes deitados, e o curto é vertical: cada bloco diz de
    qual bruto sai e que faixa dele vira o quadro em pé."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    import render
    fonte, outro = _fonte(tmp, "r1.mp4", dur=4), _fonte(tmp, "pacote.mp4", dur=4)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "blocos": [{"nome": "r1", "janelas": [[0, 2]], "mudo": True},
                        {"nome": "pacote", "fonte": str(outro), "recorte": "crop=225:400:200:0",
                         "janelas": [[1, 3]], "mudo": True}]}
    seco = fb.fabrica(plano, seco=True)
    edl = json.loads(_passo(seco, "pacote: recorte").arquivo[1])
    assert edl["sources"]["bruto"] == str(outro), f"o bloco não saiu do bruto dele: {edl['sources']}"
    assert edl["ranges"][0]["recorte"] == "crop=225:400:200:0", edl["ranges"]
    assert "recorte" not in json.loads(_passo(seco, "r1: recorte").arquivo[1])["ranges"][0]
    saida = tmp / "em-pe.mp4"
    render.extract_segment(outro, 1.0, 1.0, "", saida, out_height=1920, fps=30,
                           recorte="crop=225:400:200:0")
    s = ff.probe(saida)
    assert (s.largura, s.altura) == (1080, 1920), f"o recorte não ficou em pé: {s.largura}x{s.altura}"
    # mais largo que 9:16 (menos zoom): cabe pela largura, com o fundo borrado, e a tela é a mesma
    largo = tmp / "menos-zoom.mp4"
    render.extract_segment(outro, 1.0, 1.0, "", largo, out_height=1920, fps=30,
                           recorte="crop=300:400:100:0")
    s = ff.probe(largo)
    assert (s.largura, s.altura) == (1080, 1920), f"o recorte largo saiu {s.largura}x{s.altura}"


def test_o_short_sai_em_pe_do_video_deitado(tmp: Path):
    """O Short do vídeo longo (módulo YouTube Completo): no reel do celular, o `imagem.recorte` é a faixa
    da fonte deitada que vira o 9:16, e entra em todo trecho do corte."""
    fonte = _fonte(tmp, "longo.mp4", dur=4)
    plano = {"estilo": "reel-camera", "slug": "short", "saida": str(tmp / "saida"), "fonte": str(fonte),
             "imagem": {"recorte": "crop=225:400:200:0"}}
    seco = fb.fabrica(plano, seco=True)
    assert seco.edl and all(r.get("recorte") == "crop=225:400:200:0" for r in seco.edl), seco.edl


def test_longo_nivela_a_fala_de_cada_bloco(tmp: Path):
    """No longo, o bloco com a fala dele passa pelo trata_voz como a voz gravada à parte:
    cada bloco veio de um microfone, e sem isso a cama passava por cima do mais baixo."""
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "casa.mp4", dur=6)
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "blocos": [{"nome": "fala", "janelas": [[0, 2]]},
                        {"nome": "jogo", "janelas": [[2, 4]], "mudo": True}]}
    seco = fb.fabrica(plano, seco=True)
    assert "--voice-enhance" not in _passo(seco, "fala: recorte").cmd, "o realce do render dobraria o tratamento"
    assert _passo(seco, "fala: trata a voz").cmd[2].endswith("trecho.mp4")
    assert _passo(seco, "fala: voz do bloco")
    assert not any(p.nome.startswith("jogo: trata") for p in seco.passos), "bloco mudo não tem fala pra nivelar"


def test_nivela_fala_no_plano_poe_um_passo_entre_a_emenda_e_a_trilha(tmp: Path):
    """`nivela_fala` (27/10, ep. 7: a fala ia de -12,8 a -31,7 dB de bloco pra bloco): a emenda vira `emendado.mp4` e o `nivela_fala.py` escreve o
    `juntado.mp4`, com a marca de mudo de cada bloco. A chave do plano manda; sem ela vale o do estilo (`lorcana-longo` traz o nivelador como padrão,
    28/10) e `null` desliga. Estilo sem o padrão (o `video-longo` do aluno) segue sem o passo."""
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "casa.mp4", dur=6)
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte), "nivela_fala": {"alvo": -20.0},
             "blocos": [{"nome": "fala", "janelas": [[0, 2]]},
                        {"nome": "jogo", "janelas": [[2, 4]], "mudo": True}]}
    seco = fb.fabrica(plano, seco=True)
    emenda, nivela = _passo(seco, "emenda dos blocos"), _passo(seco, "nivela a fala por bloco")
    assert emenda.saida.name == "emendado.mp4" and nivela.saida.name == "juntado.mp4", (emenda.saida, nivela.saida)
    assert nivela.cmd[nivela.cmd.index("--mudos") + 1] == "0,1" and nivela.cmd[nivela.cmd.index("--alvo") + 1] == "-20.0", nivela.cmd
    assert emenda.saida in nivela.entradas, "o nivelador lê a emenda"
    sem = {k: v for k, v in plano.items() if k != "nivela_fala"}
    nivela = _passo(fb.fabrica(sem, seco=True), "nivela a fala por bloco")
    assert nivela.cmd[nivela.cmd.index("--alvo") + 1] == "-22.0", "sem a chave vale o nivelador do estilo (alvo -22 dBFS)"
    desligado = fb.fabrica(dict(plano, nivela_fala=None), seco=True)
    assert _passo(desligado, "emenda dos blocos").saida.name == "juntado.mp4"
    assert not any(p.nome.startswith("nivela a fala") for p in desligado.passos), "null desliga"
    do_aluno = fb.fabrica(dict(sem, estilo="video-longo"), seco=True)
    assert not any(p.nome.startswith("nivela a fala") for p in do_aluno.passos), "o video-longo do aluno não leva o nivelador do canal"
    com_jl = dict(plano, blocos=[dict(plano["blocos"][0], jl=0.25), plano["blocos"][1]])
    for p_ in (com_jl, {k: v for k, v in com_jl.items() if k != "nivela_fala"}):   # com a chave ou pelo padrão do estilo
        try:
            fb.fabrica(p_, seco=True)
        except ValueError as e:
            assert "J/L-cut" in str(e) and "nivela_fala" in str(e), e
        else:
            raise AssertionError("o nivelador por bloco passou com J/L-cut")
    fb.fabrica(dict(com_jl, nivela_fala=None), seco=True)   # sem o nivelador o J/L-cut roda


def test_refaz_um_bloco_derruba_so_o_cache_dele(tmp: Path):
    """`--refaz <bloco>` (28/10): a correção de um bloco refaz esse bloco e o que lê a saída dele, não o longo inteiro. Apaga só a marca (`.impressao`) dos
    passos do bloco; o `--sem-cache` do CLI é o `sem_cache` da função."""
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "casa.mp4", dur=6)
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas", "saida": str(tmp / "saida"), "fonte": str(fonte),
             "blocos": [{"nome": "fala", "janelas": [[0, 2]]}, {"nome": "jogo", "janelas": [[2, 4]], "mudo": True}]}
    seco = fb.fabrica(plano, seco=True)
    de = {"fala": [p for p in seco.passos if p.nome.startswith("fala:")], "jogo": [p for p in seco.passos if p.nome.startswith("jogo:")]}
    assert de["fala"] and de["jogo"]
    for p in seco.passos:   # o cache cheio: uma saída plausível e a impressão certa ao lado
        p.saida.parent.mkdir(parents=True, exist_ok=True)
        p.saida.write_bytes(b"x" * 2048)
        fb.impressao.marca(p.saida, fb._digital(p))
    cheio = fb.fabrica(plano, seco=True)
    assert all(p.pulavel for p in cheio.passos if p.nome.split(":")[0] in de), [p.nome for p in cheio.passos if not p.pulavel]
    refeito = fb.fabrica(plano, seco=True, refaz=["jogo"])
    assert not any(p.pulavel for p in refeito.passos if p.nome.startswith("jogo:")), "o bloco pedido refaz"
    assert all(p.pulavel for p in refeito.passos if p.nome.startswith("fala:")), "o outro bloco segue no cache"
    # sem seco, apaga a marca dos passos do bloco (e só deles)
    fb._esquece_blocos(seco.passos, ["jogo"])
    assert all(not fb.impressao.pronto(p.saida, fb._digital(p)) for p in de["jogo"])
    assert all(fb.impressao.pronto(p.saida, fb._digital(p)) for p in de["fala"])
    try:
        fb.fabrica(plano, seco=True, refaz=["nao-existe"])
    except ValueError as e:
        assert "nao-existe" in str(e) and "fala" in str(e) and "jogo" in str(e), e
    else:
        raise AssertionError("--refaz de bloco que não existe passou")
    assert fb.fabrica(plano, seco=True, sem_cache=True).pulados == [], "--sem-cache não pula nada"
    ajuda = subprocess.run([sys.executable, str(Path(fb.__file__)), "--help"], capture_output=True, text=True, encoding="utf-8").stdout
    assert "--refaz" in ajuda and "--sem-cache" in ajuda, ajuda


def test_jl_do_bloco_vira_cortes_no_junta_e_zoom_motivo_vai_pro_edl(tmp: Path):
    """`jl` no bloco i = J/L-cut na emenda i→i+1 (--cortes do junta, um por emenda); `zoom_motivo` vai ao EDL."""
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "casa.mp4", dur=6)
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte), "nivela_fala": None,   # o nivelador por bloco não vale com J/L-cut
             "blocos": [{"nome": "a", "janelas": [[0, 2]], "jl": 0.25},
                        {"nome": "b", "janelas": [[2, 4]], "zoom_motivo": [[1.0, 0.1]]},
                        {"nome": "c", "janelas": [[4, 6]]}]}
    seco = fb.fabrica(plano, seco=True)
    junta = _passo(seco, "emenda dos blocos").cmd
    assert junta[junta.index("--cortes") + 1] == "0.25,0.0", junta
    sem = dict(plano, blocos=[{k: v for k, v in b.items() if k != "jl"} for b in plano["blocos"]])
    assert "--cortes" not in _passo(fb.fabrica(sem, seco=True), "emenda dos blocos").cmd


def test_plano_de_bloco_cai_na_fala_pela_ancora(tmp: Path):
    """`{âncora}` no plano é dado: a janela cai na fala do bruto, e a peça na fala do bloco já
    cortado. O plano continua JSON, e o modo seco mostra o segundo resolvido."""
    import ancora
    ancora._autoteste()          # a sintaxe: começo, fim, corte, n-ésima, desloca, alternativa, fim
    if not fb.V2.exists():
        return
    fonte = _fonte(tmp, "IMG_1.mp4", dur=8)
    (tmp / "transcripts").mkdir()
    fala = [("oi", 0.5, 0.8), ("pessoal", 0.9, 1.4), ("olha", 3.0, 3.3), ("essa", 3.4, 3.6), ("carta", 3.7, 4.2)]
    (tmp / "transcripts" / "IMG_1.json").write_text(json.dumps(
        {"words": [{"text": t, "start": a, "end": b} for t, a, b in fala]}), encoding="utf-8")
    (tmp / "b.json").write_text(json.dumps({"brolls": [
        {"peca": "el_rabisco", "q": {"tipo": "x", "alvo": "terco-dir"}, "t0": "{carta}", "t1": "{carta>+0.5}"}]}),
        encoding="utf-8")
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas", "saida": str(tmp / "saida"),
             "fonte": str(fonte), "transcricoes": "transcripts", "_dir": str(tmp),
             "blocos": [{"nome": "b", "janelas": [["{|oi}", "{pessoal>}"], ["{olha}", "{fim}"]],
                         "plano": "b.json"}]}
    try:
        fb.fabrica(plano, seco=True)
        raise AssertionError("'fim' sem fim passou")
    except ValueError as e:
        assert "bloco b" in str(e), e
    plano["blocos"][0]["janelas"][1][1] = "{carta>+0.2}"
    seco = fb.fabrica(plano, seco=True)
    edl = json.loads(_passo(seco, "b: recorte").arquivo[1])
    assert [(r["start"], r["end"]) for r in edl["ranges"]] == [(0.25, 1.4), (3.0, 4.4)], edl["ranges"]
    br = json.loads(_passo(seco, "b: legenda, peças e câmera").arquivo[1])["brolls"][0]
    # no bloco: 1,15 s da primeira janela, e a carta 0,7 s depois do começo da segunda
    assert (br["t0"], br["t1"]) == (1.85, 2.85), br


def test_vinheta_abre_o_bloco_e_a_cama_sai_da_frente(tmp: Path):
    """O jingle cantado da abertura e do fecho: soa no começo do bloco, e a cama
    abaixa enquanto ele canta — duas músicas juntas, em tons diferentes, embolam."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2, e sem ela o plano com `blocos` não roda
    fonte = _fonte(tmp, "kit.mp4", dur=8)
    vinheta = tmp / "agora-vai.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=500:duration=1.5", str(vinheta)], check=True)
    plano = {"estilo": "lorcana-curto", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte), "faixa": "acustico-inspirador",
             "blocos": [{"nome": "cartas", "janelas": [[0, 3]], "mudo": True},
                        {"nome": "fim", "janelas": [[3, 7]], "mudo": True, "vinheta": str(vinheta)}]}
    seco = fb.fabrica(plano, seco=True)
    cmd = _passo(seco, "com trilha").cmd
    assert cmd[cmd.index("--fala") + 1] == "3.00:4.50", f"a cama não saiu da frente da vinheta: {cmd}"
    sons = json.loads(_passo(seco, "fim: legenda").arquivo[1])["sons"]
    assert {"arquivo": str(vinheta), "t": 0.0, "ganho": 1.0} in sons, f"a vinheta não toca: {sons}"


def test_o_vsl_nao_promete_explicador(tmp: Path):
    """O que a VSL chama de card é a legenda com direção, não o cartão de aula."""
    e = fb.es.estilo("vsl")
    assert not e.tem("explicador"), (
        "o explicador da fábrica é o lesson_overlays e exige `overlays` no plano; "
        "a VSL desenha pelo cards_da_fala, que é legenda"
    )
    assert e.adaptador("legenda") == "viral"


def test_avatar_nao_grava_edl_morto(tmp: Path):
    """No avatar quem corta é o apara_pausas: um EDL em disco seria um segundo
    cálculo do mesmo corte, pronto para divergir."""
    plano = _plano_vsl(tmp)
    fb.fabrica(plano, seco=True)
    sobras = list((tmp / "saida").rglob("edl.json"))
    assert not sobras, f"gravou EDL que ninguém lê: {sobras}"


# ---- a VSL em blocos ---------------------------------------------------------
#
# O monta.sh da VSL do Hermes fazia isto à mão, bloco a bloco, com a direção
# copiada em 22 planos. Aqui o plano lista os blocos e o estilo traz a direção.


def _vsl_blocos(tmp: Path, **bloco_extra) -> dict:
    gerado = _fonte(tmp, "base_b1.mp4", dur=3)
    bp = tmp / "plano_b1.json"
    bp.write_text(json.dumps({"cards": [], "brolls": [], "camera": [], "sons": []}), encoding="utf-8")
    b1 = {"nome": "b1", "gerado": gerado.name, "plano": bp.name, **bloco_extra}
    b2 = {"nome": "b2", "pronto": _fonte(tmp, "b2.mp4", dur=2).name}
    return {"estilo": "vsl", "slug": "oferta", "projeto": "provas",
            "saida": str(tmp / "saida"), "_dir": str(tmp), "faixa": "acustico-inspirador",
            "blocos": [b1, b2]}


def _passo(seco, trecho: str):
    return next(p for p in seco.passos if trecho in p.nome)


def test_vsl_em_blocos_monta_cada_bloco_e_emenda(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    seco = fb.fabrica(_vsl_blocos(tmp), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "b1: legenda, peças e câmera" in nomes and "b1: som" in nomes, nomes
    assert not any(n.startswith("b2:") for n in nomes), "bloco pronto não se refaz"
    junta = _passo(seco, "emenda dos blocos")
    assert junta.cmd[junta.cmd.index("-o") - 1].endswith("b2.mp4"), "os cortes entram na ordem do plano"
    assert "mixa.py" in " ".join(seco.passos[-1].cmd), (
        "a VSL fecha com a cama da trilha (mixa), não com o fecho do reel")
    som = " ".join(_passo(seco, "b1: som").cmd)
    assert "--mestre -2.0" in som, f"o nível dos sons é do estilo: {som}"


def test_cor_por_trecho_entra_antes_das_pecas(tmp: Path):
    """A cor do vídeo num trecho é do vídeo, não da peça: o painel por cima fica sem graduação (19/10)."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp)
    bp = tmp / "plano_b1.json"
    bp.write_text(json.dumps({"cards": [], "brolls": [], "camera": [], "sons": [],
                              "cor": [{"t0": 1.0, "t1": 2.0, "filtro": "eq=brightness=0.1"}]}), encoding="utf-8")
    seco = fb.fabrica(plano, seco=True)
    cor, leg = _passo(seco, "b1: cor por trecho"), _passo(seco, "b1: legenda")
    assert str(cor.saida) in leg.cmd, "as peças vão por cima do vídeo já graduado"
    assert "between(t,1.0,2.0)" in " ".join(cor.cmd) and cor.toca == 1.0, cor.cmd


def test_o_estilo_preenche_a_direcao_do_bloco(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    seco = fb.fabrica(_vsl_blocos(tmp), seco=True)
    _, texto = _passo(seco, "b1: legenda").arquivo
    doc = json.loads(texto)
    assert doc["acento"] == "#0640fb", "o acento vem do núcleo, não de cada plano"
    assert doc["ritmo"] == {"entrada": 0.167, "stagger": 0.033}, doc.get("ritmo")


def test_vsl_nao_poe_texto_atras_da_pessoa(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp)
    bp = tmp / "plano_b1.json"
    bp.write_text(json.dumps({"cards": [{"t0": 1.0, "t1": 2.0, "atras": True, "words": []}]}), encoding="utf-8")
    erro = None
    try:
        fb.fabrica(plano, seco=True)
    except ValueError as e:
        erro = e
    assert erro and "atrás" in str(erro), f"card atrás da pessoa passou: {erro}"


def test_peca_pelo_nome_sai_no_tema_do_estilo(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp)
    (tmp / "plano_b1.json").write_text(json.dumps({"cards": [], "brolls": [
        {"peca": "t_frase", "q": {"l1": "Oi", "l2": "tudo"}, "t0": 0.5, "t1": 2.5, "alt": 1.0}]}), encoding="utf-8")
    seco = fb.fabrica(plano, seco=True)
    render = " ".join(_passo(seco, "peça t_frase").cmd)
    assert "v2.py render t_frase l1=Oi l2=tudo --tema claro" in render, render
    doc = json.loads(_passo(seco, "b1: legenda").arquivo[1])
    assert doc["brolls"][0]["arquivo"].endswith(".mov") and "peca" not in doc["brolls"][0], (
        "o plano do bloco tem que apontar pro render, não pro nome")


def test_peca_transparente_flutua_sobre_o_video(tmp: Path):
    """Peça que o catálogo marca como alfa entra COM a transparência dela.

    Antes o plano tinha que dizer `alfa` à mão; sem isso o captions_viral perdia
    o alpha e a peça cobria o vídeo com um retângulo preto (episódio 1, 29/09).
    """
    if not fb.V2.exists():
        return
    plano = _vsl_blocos(tmp)
    (tmp / "plano_b1.json").write_text(json.dumps({"cards": [], "brolls": [
        {"peca": "g_contador", "q": {"de": "1", "para": "2"}, "t0": 0.2, "t1": 2.0},
        {"peca": "t_frase", "q": {"l1": "Oi"}, "t0": 2.0, "t1": 2.8}]}), encoding="utf-8")
    doc = json.loads(_passo(fb.fabrica(plano, seco=True), "b1: legenda").arquivo[1])
    alfa, opaca = doc["brolls"]
    assert alfa.get("alfa") is True, f"a peça transparente entrou opaca: {alfa}"
    assert not opaca.get("alfa"), f"a peça opaca ganhou transparência: {opaca}"


def test_bloco_sem_geracao_para_no_portao_dele(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    voz = _voz(tmp)
    plano = _vsl_blocos(tmp)
    plano["blocos"].append({"nome": "b3", "fonte": voz.name,
                            "transcript": _transcript(tmp, voz).name})
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "b3: portão do HeyGen" in nomes, nomes
    assert "emenda dos blocos" not in nomes, "emendou com um bloco que nem foi gerado"
    assert "fecho com trilha" not in nomes, (
        "parou no portão e ainda mandou a trilha — sobre uma PASTA, que é o que sobra "
        "quando não existe imagem")


def test_receita_troca_a_imagem_e_o_som_vem_dela(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp, receitas=[{"id": "b1-tese", "receita": "tese", "de": 0.5,
                                        "ate": 1.5, "rosto": "rosto.webm"}])
    plano["placa"] = "placa.png"
    for n in ("rosto.webm", "placa.png"):
        (tmp / n).write_bytes(b"")
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "b1: receita b1-tese" in nomes and "b1: receitas na base" in nomes, nomes
    leg = _passo(seco, "b1: legenda")
    assert Path(leg.cmd[2]).as_posix().endswith("b1/base.mp4"), "a legenda tem que ir sobre a base com a receita"
    doc = json.loads(leg.arquivo[1])
    assert doc["cues_de"][0]["arquivo"].endswith("b1-tese.mp4"), "os sons da receita se perderam"


def test_portao_e_apara_nao_dividem_a_marca_de_cache(tmp: Path):
    """Com a mesma saída, um apagava a marca do outro: o apara refazia sempre e o
    ouvido, que é pago, rodava de novo a cada corrida."""
    seco = fb.fabrica(_plano_vsl(tmp), seco=True)
    saidas = [p.saida for p in seco.passos]
    assert len(saidas) == len(set(saidas)), f"dois passos com a mesma saída: {saidas}"


def test_peca_refaz_quando_o_desenho_muda(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp)
    (tmp / "plano_b1.json").write_text(json.dumps({"brolls": [
        {"peca": "t_frase", "q": {"l1": "Oi"}, "t0": 0.5, "t1": 2.5}]}), encoding="utf-8")
    peca = _passo(fb.fabrica(plano, seco=True), "peça t_frase")
    nomes = {x.name for x in peca.entradas}
    assert {"t_frase.html", "direcao-v2.css", "direcao-v2.js"} <= nomes, (
        f"mexer na peça ou no núcleo não refaria o render: {nomes}")


def test_receitas_sobrepostas_sao_recusadas(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    plano = _vsl_blocos(tmp, receitas=[
        {"id": "a", "receita": "tese", "de": 0.2, "ate": 1.4, "rosto": "rosto.webm"},
        {"id": "b", "receita": "tese", "de": 1.0, "ate": 2.0, "rosto": "rosto.webm"}])
    plano["placa"] = "placa.png"
    for n in ("rosto.webm", "placa.png"):
        (tmp / n).write_bytes(b"")
    erro = None
    try:
        fb.fabrica(plano, seco=True)
    except ValueError as e:
        erro = e
    assert erro and "sobrepostas" in str(erro), f"a emenda pularia a base: {erro}"


def test_nao_sobrescreve_final_que_nao_fez(tmp: Path):
    """Em 26/09 o slug de um plano novo era o nome da VSL que estava no ar."""
    plano = _plano(tmp, estilo="aula-ccnp")
    seco = fb.fabrica(plano, seco=True)
    seco.final.parent.mkdir(parents=True, exist_ok=True)
    seco.final.write_bytes(b"o video publicado")
    assert fb.fabrica(plano, seco=True).alheio, "o modo seco não avisou"
    erro = None
    try:
        fb.fabrica(plano)
    except FileExistsError as e:
        erro = e
    assert erro, "copiou por cima de um final que não era dela"
    assert seco.final.read_bytes() == b"o video publicado"


def test_sem_saida_o_final_vai_para_videos(tmp: Path):
    e = fb.es.estilo("vsl")
    final = fb._final({"slug": "x", "projeto": "p"}, e)
    assert final.parts[-3:] == ("videos", "p", "x.mp4"), final
    reel = fb._final({"slug": "r"}, fb.es.estilo("reel-mono"))
    assert reel.parts[-3:] == ("videos", "reels", "r.mp4"), reel


def test_a_legenda_da_fabrica_leva_a_direcao(tmp: Path):
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    cards = " ".join(_passo(seco, "cards da fala").cmd)
    assert "--acento #0640fb" in cards, f"a legenda saía sem a cor do núcleo: {cards}"


def test_o_preset_de_legenda_vem_do_estilo(tmp: Path):
    """`desenho.legenda` chega por nome ao cards_da_fala e ao criativo; sem ele, o comando é o
    de antes, letra por letra."""
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    antes = _passo(seco, "cards da fala").cmd
    assert "--legenda" not in antes, antes
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono", desenho={"legenda": "fita"}), seco=True)
    cmd = _passo(seco, "cards da fala").cmd
    assert cmd[cmd.index("--legenda") + 1] == "fita", cmd
    assert [x for x in cmd if x not in ("--legenda", "fita")] == antes, "o preset mexeu no resto"
    # o lugar da legenda (`desenho.legenda_layout`) também chega ao cards_da_fala: copiar a posição
    # de uma referência é um campo do eixo, não edição à mão do cards.json
    assert "--layout" not in antes, antes
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono", desenho={"legenda_layout": "topo"}), seco=True)
    cmd = _passo(seco, "cards da fala").cmd
    assert cmd[cmd.index("--layout") + 1] == "topo", cmd
    # e o teto de palavras por cartão (`desenho.legenda_palavras`)
    assert "--max" not in antes, antes
    seco = fb.fabrica(_plano(tmp, estilo="reel-mono", desenho={"legenda_palavras": 2}), seco=True)
    cmd = _passo(seco, "cards da fala").cmd
    assert cmd[cmd.index("--max") + 1] == "2", cmd
    if SEM_CRIATIVO:
        return
    doc = json.loads(_arquivo(fb.fabrica(_criativo(tmp / "cr", desenho={"legenda": "caixa-cor"}),
                                         seco=True))[1])
    assert doc["_estilo"]["legenda"] == "caixa-cor", doc["_estilo"]
    doc = json.loads(_arquivo(fb.fabrica(_criativo(tmp / "cr0"), seco=True))[1])
    assert "legenda" not in doc["_estilo"], "o criativo sem preset ganhou um"


def test_argumento_gigante_nao_derruba_a_impressao(tmp: Path):
    """Um `filter_complex` de b-roll tem milhares de caracteres, e a impressão
    pergunta a todo argumento se ele é arquivo. `Path(...).exists()` num texto
    desse tamanho estoura `OSError: File name too long` — e derrubava o plano
    inteiro, não só o cache. Era o único plano com b-roll que chegava aqui.
    """
    gigante = "[1:v]trim=0:2," + ("x" * 5000) + "[v]"
    passo = fb.Passo("b-roll", ["ffmpeg", "-filter_complex", gigante, "saida.mp4"],
                     tmp / "saida.mp4")
    fb._entradas(passo)   # não pode estourar
    fb._digital(passo)    # nem aqui


def test_recurso_que_nao_vai_entrar_e_anunciado(tmp: Path):
    """Camada pedida que não entra tem que DIZER, não sumir.

    O estilo `vsl` pedia `explicador`; a cadeia só monta explicador com
    `overlays` no plano, e uma VSL nunca traz. O vídeo saía sem a camada e nada
    acusava — nem no modo seco, que é onde se confere.
    """
    seco = fb.fabrica(_plano(tmp, estilo="aula-ccnp"), seco=True)  # sem overlays
    mudos = dict(seco.mudos)
    assert "explicador" in mudos, (
        f"o estilo pede explicador, o plano não traz overlays, e ninguém avisou: "
        f"{seco.mudos}"
    )
    assert mudos["explicador"] == "overlays", "o aviso não diz qual campo falta"


def test_legenda_sem_transcricao_nem_plano_e_anunciada(tmp: Path):
    """A legenda tem duas fontes possíveis — o plano de cards, ou a transcrição
    de onde gerá-lo. Sem nenhuma das duas ela não entra, e isso também precisa
    aparecer: achei este caso rodando um reel de câmera sem transcrição, e a
    camada sumia sem uma linha na tela."""
    plano = _plano(tmp, estilo="reel-camera")
    del plano["transcript"]
    seco = fb.fabrica(plano, seco=True)
    assert "legenda" in dict(seco.mudos), (
        f"legenda sem transcrição e sem plano some calada: {seco.mudos}"
    )


def test_recurso_atendido_nao_e_anunciado_como_mudo(tmp: Path):
    """O aviso só vale se ele calar quando está tudo certo."""
    cards = [{"scene": "term", "at": 1.0, "dur": 3.0,
              "term": "EDL", "def": "a lista de trechos"}]
    seco = fb.fabrica(_plano(tmp, estilo="aula-ccnp", overlays=cards), seco=True)
    assert "explicador" not in dict(seco.mudos), (
        f"avisou de camada que vai entrar: {seco.mudos}"
    )


def test_todo_adaptador_aponta_para_helper_que_existe(tmp: Path):
    aqui = Path(fb.__file__).resolve().parent
    for recurso, v in fb.es.RECURSOS.items():
        escolhas = v.get("adaptadores") or {}
        for apelido, arquivo in escolhas.items():
            assert (aqui / arquivo).exists(), (
                f"o adaptador '{apelido}' de '{recurso}' aponta para {arquivo}, "
                "que não existe"
            )
        if escolhas:
            assert v["padrao"] in escolhas, (
                f"o padrão de '{recurso}' não está entre os adaptadores dele"
            )


def test_o_portao_nao_entra_como_suspeito(tmp: Path):
    seco = fb.fabrica(_plano_vsl(tmp), seco=True)
    portao = next(p for p in seco.passos if p.nome == "portão do HeyGen")
    assert not portao.suspeito(seco.duracao), (
        "o portão muda 0s de propósito e custa quase nada. Marcá-lo de suspeito "
        "ensina a ignorar o marcador que existe para achar passo caro e bobo"
    )


# ---- a forma do beat de b-roll ----------------------------------------------
#
# Dois planos no repositório descreviam b-roll com palavras diferentes, e o de
# vocabulário velho estourava com KeyError no meio do render. A forma do beat
# passa a ser conferida na entrada, como eixo e adaptador já são.


def _beat(**extra):
    b = {"arquivo": "broll/x.mp4", "em": 1.0, "dur": 2.0}
    b.update(extra)
    return b


def test_beat_sem_campo_obrigatorio_diz_qual_beat(tmp: Path):
    ruim = _beat(); del ruim["arquivo"]
    erro = None
    try:
        fb.confere_beats([_beat(), ruim])
    except Exception as e:
        erro = e
    assert erro is not None, "beat sem arquivo passou"
    assert "arquivo" in str(erro), f"não diz o que falta: {erro}"
    assert "2" in str(erro) or "#2" in str(erro), f"não diz qual beat: {erro}"


def test_beat_com_chave_do_vocabulario_velho_ensina_a_traducao(tmp: Path):
    """`file`/`start` era o vocabulário de antes da fábrica. O erro tem que
    ensinar a tradução, não só recusar — quem escreveu não sabe que mudou."""
    erro = None
    try:
        fb.confere_beats([{"file": "broll/x.mp4", "start": 1.0, "dur": 2.0}])
    except Exception as e:
        erro = e
    assert erro is not None, "vocabulário velho passou"
    assert "file" in str(erro) and "arquivo" in str(erro), (
        f"o erro não ensina file -> arquivo: {erro}"
    )


def test_beat_com_chave_inventada_lista_as_validas(tmp: Path):
    erro = None
    try:
        fb.confere_beats([_beat(chave_que_nao_existe=1)])
    except Exception as e:
        erro = e
    assert erro is not None
    assert "largura" in str(erro) and "anim" in str(erro), f"não lista as válidas: {erro}"


def test_beat_valido_passa_inteiro(tmp: Path):
    entrada = [_beat(anim="left", largura=300, x=10, y=20)]
    assert fb.confere_beats(entrada) == entrada, "mexeu no beat que já estava certo"


# ---- o produtor de b-roll ---------------------------------------------------
#
# O recurso `broll` era consumido e ninguém o produzia: dois planos no repo
# inteiro, os dois escritos à mão. O get-brolls sabe O QUÊ e DE QUEM; a âncora
# na transcrição é que sabe QUANDO.


def _candidato(bid="c1", beat="abertura", caminho="brolls/c1.mp4", dur=3.0,
               estado="delivered", direitos="Pexels License"):
    return {
        "schema_version": 1, "id": bid, "provider": "pexels",
        "source_id": "123", "source_url": "https://pexels.com/v/123",
        "state": estado,
        "segment": {"beat": beat, "start": 2.0, "end": 2.0 + dur},
        "approval": {"decision": "approved", "by": "matheus"},
        "rights": {"license": direitos, "evidence": "condições reais da fonte"},
        "output": {}, "acquisition": {}, "preview": {}, "media": {},
        "delivery": {"path": caminho},
    }


def test_candidato_aprovado_vira_beat(tmp: Path):
    import brolls
    saida = brolls.beats_de([_candidato()], {"abertura": 4.5}, raiz=Path("/p"))
    assert len(saida) == 1, saida
    b = saida[0]
    assert b["dur"] == 3.0, "a duração sai do segmento aprovado"
    assert b["em"] == 4.5, "o 'em' sai da âncora nossa, não do get-brolls"
    assert Path(b["arquivo"]).as_posix().endswith("brolls/c1.mp4"), b["arquivo"]
    f = b["fonte"]
    assert f["licenca"] == "Pexels License", f"a licença tem que viajar junto: {b}"
    assert f["id"] == "c1" and f["aprovado_por"] == "matheus", (
        "sem id e sem quem aprovou não dá pra achar o candidato de volta no "
        f"get-brolls quando a reclamação chegar: {f}"
    )


def test_candidato_nao_aprovado_fica_de_fora(tmp: Path):
    import brolls
    reprovado = _candidato(bid="c2", estado="rejected")
    reprovado["approval"] = {"decision": "rejected", "by": "matheus"}
    assert brolls.beats_de([reprovado], {"abertura": 1.0}, raiz=Path("/p")) == []


def test_beat_sem_ancora_fica_de_fora_e_nao_chuta(tmp: Path):
    """Sem âncora não há quando. Chutar 0.0 põe o clipe em cima da primeira
    frase — errado e silencioso."""
    import brolls
    assert brolls.beats_de([_candidato(beat="fecho")], {"abertura": 1.0},
                           raiz=Path("/p")) == []


def test_o_que_sai_do_produtor_passa_na_guarda_do_beat(tmp: Path):
    """As duas pontas têm que falar a mesma língua — é o ponto de ter uma forma."""
    import brolls
    saida = brolls.beats_de([_candidato(), _candidato(bid="c2", beat="meio")],
                            {"abertura": 4.5, "meio": 12.0}, raiz=Path("/p"))
    assert fb.confere_beats(saida) == saida, "o produtor emite num formato que a guarda recusa"


# ---- procedência ------------------------------------------------------------
#
# Clipe de terceiro entra no final e o final não lembrava de onde veio. Para
# quem publica comercialmente, saber a origem depois de publicado é a resposta
# pronta quando alguém reclama.


def test_procedencia_lista_so_o_que_veio_de_fora(tmp: Path):
    plano = {"broll": [
        {"arquivo": "a.mp4", "em": 1, "dur": 2,
         "fonte": {"id": "c1", "licenca": "Pexels License", "url": "u"}},
        {"arquivo": "meu.mp4", "em": 4, "dur": 2},
    ]}
    p = fb.procedencia(plano)
    assert len(p) == 1, f"o clipe sem fonte é meu e não entra na lista: {p}"
    assert p[0]["arquivo"] == "a.mp4"
    assert p[0]["fonte"]["id"] == "c1", "a trilha de volta ao candidato tem que sobreviver"


def test_sem_material_de_terceiro_nao_ha_o_que_declarar(tmp: Path):
    assert fb.procedencia({"broll": [{"arquivo": "meu.mp4", "em": 1, "dur": 2}]}) == []
    assert fb.procedencia({}) == []


# ---- validação, antes do primeiro comando -----------------------------------


def test_plano_sem_campo_obrigatorio_falha_antes_de_tudo(tmp: Path):
    plano = _plano(tmp); del plano["fonte"]
    erro = None
    try:
        fb.fabrica(plano, seco=True)
    except Exception as e:
        erro = e
    assert erro is not None, "plano sem fonte passou"
    assert "fonte" in str(erro), f"o erro não diz o que faltou: {erro}"


def test_estilo_que_nao_existe_falha_listando(tmp: Path):
    erro = None
    try:
        fb.fabrica(_plano(tmp, estilo="aula-inventada"), seco=True)
    except Exception as e:
        erro = e
    assert erro is not None
    assert "aula-ccnp" in str(erro), f"o erro não lista os válidos: {erro}"


def test_bruto_incompativel_com_o_estilo_falha(tmp: Path):
    """Mandar uma live para um estilo de câmera é erro de entrada, não de render."""
    erro = None
    try:
        fb.fabrica(_plano(tmp, estilo="reel-camera", bruto="live"), seco=True)
    except Exception as e:
        erro = e
    assert erro is not None, "bruto incompatível passou"
    assert "camera" in str(erro)


def test_fonte_que_nao_existe_falha(tmp: Path):
    plano = _plano(tmp); plano["fonte"] = str(tmp / "fantasma.mp4")
    erro = None
    try:
        fb.fabrica(plano, seco=True)
    except Exception as e:
        erro = e
    assert erro is not None and "fantasma" in str(erro)


# ---- o modo seco não executa ------------------------------------------------


def test_modo_seco_nao_escreve_video(tmp: Path):
    seco = fb.fabrica(_plano(tmp), seco=True)
    assert seco.comandos, "o modo seco não montou comando nenhum"
    assert not list((tmp / "saida").glob("*.mp4")), "o modo seco renderizou"


def test_modo_seco_devolve_o_edl(tmp: Path):
    seco = fb.fabrica(_plano(tmp), seco=True)
    assert seco.edl, "o modo seco não devolveu o EDL"
    assert all("start" in t and "end" in t for t in seco.edl)


def test_modo_seco_devolve_o_estilo_resolvido(tmp: Path):
    seco = fb.fabrica(_plano(tmp), seco=True)
    assert seco.estilo.nome == "aula-ccnp"
    assert seco.estilo.eixos["imagem"]["canvas"] == "2560x1440"


def test_modo_seco_mostra_a_pilha_de_recursos(tmp: Path):
    seco = fb.fabrica(_plano(tmp), seco=True)
    assert seco.estilo.recursos == ["explicador", "emenda", "abertura"]


# ---- invariantes que já custaram um render ----------------------------------


def test_toda_entrada_em_laco_leva_limite_de_duracao(tmp: Path):
    """Sem -t, o render trava esperando uma máscara que não acaba."""
    for cmd in fb.fabrica(_plano(tmp), seco=True).comandos:
        if "-stream_loop" in cmd or "-loop" in cmd:
            assert "-t" in cmd, f"entrada em laço sem -t: {' '.join(cmd)}"


def test_saida_do_canal_sem_ninguem_pedir(tmp: Path):
    """1440p30 para de ser convenção lembrada: o plano não pede e sai assim."""
    plano = _plano(tmp)
    assert "imagem" not in plano, "o plano deste caso não pode falar de tamanho"
    render = next(c for c in fb.fabrica(plano, seco=True).comandos
                  if "render.py" in " ".join(c))
    assert render[render.index("--height") + 1] == str(ff.ALTURA)
    assert render[render.index("--fps") + 1] == str(ff.FPS)
    assert "--canvas" in render, "o canvas 16:9 da aula não chegou"


def test_glitch_entra_antes_do_embrulho_crt(tmp: Path):
    """Se o CRT vier primeiro, o tempo da emenda não bate mais com o EDL."""
    txt = _cmds(fb.fabrica(_plano(tmp), seco=True))
    i_gl, i_crt = txt.find("glitch_cuts"), txt.find("tv_effect")
    assert i_gl != -1 and i_crt != -1, "a aula saiu sem glitch ou sem CRT"
    assert i_gl < i_crt, "o CRT entrou antes do glitch"


# ---- a aula da Fábrica ------------------------------------------------------


def test_chapa_cobre_a_bolinha_e_cabe_no_quadro(tmp: Path):
    """A geometria da chapa com a câmera dentro do OBS: a tela inteira na janela, sem deformar,
    com papel em volta; o cartão cobre a bolinha que o OBS gravou (ela continua na tela embaixo)
    e salta da janela sem passar do quadro, sombra incluída."""
    g = fb.chapa_geo(2560, 1600, 1440, bolinha="crop=471:313:2089:1287")
    assert (g["W"], g["H"]) == (2560, 1440)
    jx, jy, jw, jh = g["jan"]
    assert jx > 0 and jy > 0 and jx + jw < 2560 and jy + jh < 1440, g
    assert abs(jw / jh - 1.6) < 0.002, f"a tela deformou: {jw}x{jh}"
    assert all(v % 2 == 0 for v in (jw, jh, *g["cam"][2:])), "o x264 recusa tamanho ímpar"
    cx, cy, cw, ch = g["cam"]
    bx0, by0, bx1, by1 = jx + 2089 * jw / 2560, jy + 1287 * jh / 1600, jx + jw, jy + jh
    assert cx <= bx0 + 1 and cy <= by0 and cx + cw >= bx1 and cy + ch >= by1, "sobrou bolinha velha à mostra"
    assert cx + cw > jx + jw and cy + ch > jy + jh, "o cartão não salta da janela"
    sombra = 12 * 1440 / 1080            # borda e sombra da peça, no pixel de saída
    assert cx + cw + sombra < 2560 and cy + ch + sombra < 1440, "o cartão passou do quadro"
    assert fb.chapa_geo(2560, 1600, 1440)["cam"] is None, "sem rosto, sem cartão"


def test_chapa_do_modo_2_nao_cobre_a_tela(tmp: Path):
    """No modo 2 a tela é limpa: o cartão do celular vai na faixa da direita, sem cobrir nada
    dela (quatro de quatro alunos reclamaram da câmera em cima do conteúdo), na proporção do
    celular e embaixo, na zona do rosto."""
    g = fb.chapa_geo(2560, 1600, 1440, celular=(2160, 3840))
    jx, jy, jw, jh = g["jan"]
    cx, cy, cw, ch = g["cam"]
    assert cx >= jx + jw + 10, f"o cartão encostou na tela: {g}"
    assert abs(cw / ch - 9 / 16) < 0.01 and cy + ch == jy + jh, g
    assert cx + cw + 12 * 1440 / 1080 < 2560 and abs(jw / jh - 1.6) < 0.002, g


# O explicador de aula (lesson_overlays) vem no módulo YouTube Completo: sem ele, o seco mostra o passo
# sem as peças, e o que confere as peças não tem o que conferir.
SEM_AULA = not (Path(fb.__file__).parent / "lesson_overlays.py").exists()


def _plano_fabrica(tmp: Path, **extra) -> dict:
    # a fonte de teste é 640x400: a bolinha cabe nela
    return _plano(tmp, **{"estilo": "aula-fabrica-live", "imagem": {"recorte": "crop=120:80:520:320"},
                          "overlays": [{"at": 1.0, "scene": "term", "dur": 2.0, "term": "VPS",
                                        "def": "o servidor"}], **extra})


def test_aula_fabrica_poe_a_chapa_antes_do_explicador(tmp: Path):
    """A peça que toma a tela cobre o papel também, e a que vai por cima mede a zona do rosto no
    quadro de saída: por isso a chapa vem antes do explicador. Sem CRT, sem glitch, sem as
    barras pretas do canvas."""
    if not fb.V2.exists() or SEM_AULA:
        return  # o kit não leva tools/v2; o principal da Fábrica não leva o explicador de aula
    seco = fb.fabrica(_plano_fabrica(tmp), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes[:5] == ["render", "peça h_chapa", "chapa", "peça h_termo", "explicador"], nomes
    txt = _cmds(seco)
    assert "tv_effect" not in txt and "glitch_cuts" not in txt, "o CRT e o glitch são do CCnP"
    assert "--canvas" not in " ".join(_passo(seco, "render").cmd), "a chapa faz o 16:9, não o canvas"
    chapa = " ".join(next(p for p in seco.passos if p.nome == "chapa").cmd)
    assert "crop=120:80:520:320" in chapa and "scale=640:400" in chapa, (
        "o recorte é medido no quadro da live: o vídeo volta às dimensões dela antes")
    assert "com_chapa.mp4" in " ".join(_passo(seco, "explicador").cmd)
    sem = _cmds(fb.fabrica(_plano_fabrica(tmp, imagem={"recorte": None}), seco=True))
    assert "split" not in sem and "h_chapa" in sem and "cam=" not in sem, "sem recorte é só a janela"


def test_o_seco_enxerga_as_pecas_do_explicador(tmp: Path):
    """As peças do explicador são passos da fábrica, como as do bloco: o seco mostra cada uma, elas
    vão no lote, e o explicador só as põe no lugar (o que foi cortado não ganha peça). Antes elas
    renderizavam dentro do lesson_overlays, longe do seco e do cache da fábrica."""
    if not fb.V2.exists() or SEM_AULA:
        return  # o kit não leva tools/v2; o principal da Fábrica não leva o explicador de aula
    ovs = [{"at": 1.0, "scene": "term", "dur": 2.0, "term": "VPS", "def": "o servidor"},
           {"at": 2.5, "scene": "stat", "dur": 2.0, "n": "20 dias", "sub": "esperando"},
           {"at": 999.0, "scene": "term", "dur": 2.0, "term": "fora", "def": "do vídeo"}]
    seco = fb.fabrica(_plano_fabrica(tmp, overlays=ovs), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes.count("peça h_termo") == 2 and "peça ve_dado" in nomes, nomes
    exp = _passo(seco, "explicador")
    assert "--pecas" in exp.cmd and exp.arquivo, exp.cmd
    colocadas = json.loads(exp.arquivo[1])
    import lesson_overlays as lo
    edl = {"ranges": seco.edl}
    assert [round(c["em"], 3) for c in colocadas] == [round(lo.out_time(edl, o["at"]) + lo.INTRO, 3) for o in ovs], colocadas
    assert [round(c["ate"] - c["em"], 3) for c in colocadas] == [2.0, 2.0, 2.0], colocadas
    pecas = {p.saida for p in seco.passos if p.nome in ("peça h_termo", "peça ve_dado")}
    assert {Path(c["arquivo"]) for c in colocadas} <= pecas and pecas <= set(exp.entradas), (colocadas, exp.entradas)
    dado = next(p for p in seco.passos if p.nome == "peça ve_dado")
    assert "--opaco" in dado.cmd and dado.saida.suffix == ".mp4", "a peça que toma a tela sai opaca, como antes"


def _celular(dir_: Path, dur=9) -> Path:
    saida = dir_ / "celular.mov"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=360x640:rate=30:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=500:duration={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(saida)], check=True)
    return saida


def test_modo_2_corta_o_celular_nos_trechos_da_tela(tmp: Path):
    """O bruto do jeito que ele grava: a tela no OBS e ele no celular. O celular é cortado nos
    MESMOS trechos, deslocados pela palma, já na altura do cartão; a voz é a do OBS, ou a do
    celular quando o plano pede. Sem o celular, a fábrica recusa antes de começar."""
    if not fb.V2.exists():
        return
    plano = _plano(tmp, estilo="aula-fabrica", celular=str(_celular(tmp)), offset=-0.5)
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes[:4] == ["render", "câmera", "peça h_chapa", "chapa"], nomes
    cam = _passo(seco, "câmera")
    tela = [(r["start"], r["end"]) for r in seco.edl]
    corte = [(r["start"], r["end"]) for r in json.loads(cam.arquivo[1])["ranges"]]
    assert corte == [(round(a + 0.5, 3), round(b + 0.5, 3)) for a, b in tela], (tela, corte)
    altura = cam.cmd[cam.cmd.index("--height") + 1]
    chapa = next(p for p in seco.passos if p.nome == "chapa").cmd
    assert f":{altura}:flags" in " ".join(chapa) and "--mudo" in cam.cmd, "o cartão reescalou à toa"
    assert chapa[chapa.index("-map", chapa.index("[v]")) + 1] == "0:a", "a voz é a do OBS"
    com = fb.fabrica({**plano, "microfone": "celular"}, seco=True)
    chapa = next(p for p in com.passos if p.nome == "chapa").cmd
    assert chapa[chapa.index("-map", chapa.index("[v]")) + 1] == "2:a" and "--voice-enhance" in _passo(
        com, "câmera").cmd, "a voz do celular não veio"
    for ruim, diz in (({"celular": None}, "celular"), ({"offset": -5.0}, "cai fora do celular")):
        try:
            fb.fabrica({**plano, **ruim}, seco=True)
            raise AssertionError(f"{ruim} passou")
        except (FileNotFoundError, ValueError) as err:
            assert diz in str(err), err


def test_abertura_e_fecho_por_peca(tmp: Path):
    """A marca abre e fecha: cada ponta é uma peça no tamanho do vídeo, com silêncio por baixo
    (o junta recusa parte sem áudio) e os cues dela por cima, emendada pelo junta.py."""
    if not fb.V2.exists():
        return
    seco = fb.fabrica(_plano_fabrica(tmp), seco=True)
    renders = [" ".join(p.cmd) for p in seco.passos if p.nome == "peça t_marca"]
    assert len(renders) == 2 and "sai=0" not in renders[0] and "sai=0" in renders[1], renders
    assert all("--ar 1920x1080" in r for r in renders), "a marca nasce em pé e esticou no 16:9"
    junta = _passo(seco, "abertura e fecho").cmd
    partes = [Path(c).name for c in junta[2:junta.index("-o")]]
    assert partes == ["abertura.mp4", "com_explicador.mp4", "fecho.mp4"], partes
    som = _passo(seco, "abertura: som")
    assert json.loads(som.arquivo[1])["brolls"][0]["arquivo"].endswith(".mov"), "os cues da peça não soam"
    assert "anullsrc" in " ".join(_passo(seco, "abertura").cmd) and "scale=2560:1440" in " ".join(
        _passo(seco, "abertura").cmd), "a ponta não saiu no tamanho do vídeo, com áudio"
    so = fb.fabrica(_plano_fabrica(tmp, efeito={"fecho": None, "som": False}), seco=True)
    nomes = [p.nome for p in so.passos]
    assert "fecho" not in nomes and "abertura: som" not in nomes and "abertura" in nomes, nomes
    assert "tv_effect" not in _cmds(so), "peça na abertura troca o CRT"


# ---- recursos ---------------------------------------------------------------


def test_desligar_recurso_some_com_os_comandos_dele(tmp: Path):
    com = _cmds(fb.fabrica(_plano(tmp), seco=True))
    sem = _cmds(fb.fabrica(_plano(tmp, recursos={"-": ["abertura"]}), seco=True))
    assert "tv_effect" in com
    assert "tv_effect" not in sem, "desligar a abertura não tirou o CRT"
    assert "glitch_cuts" in sem, "desligar a abertura derrubou a emenda junto"


def test_ligar_recurso_acrescenta_o_passo(tmp: Path):
    sem = _cmds(fb.fabrica(_plano(tmp, estilo="quadro"), seco=True))
    com = _cmds(fb.fabrica(_plano(tmp, estilo="quadro",
                                  recursos={"+": ["abertura"]}), seco=True))
    assert "tv_effect" not in sem and "tv_effect" in com


# ---- ponto de partida -------------------------------------------------------


def test_comecar_no_desenho_nao_corta_nem_renderiza(tmp: Path):
    txt = _cmds(fb.fabrica(_plano(tmp), seco=True, desde="desenho"))
    assert "render.py" not in txt, "começar no desenho ainda renderizou"


def test_desde_corta_a_cadeia_sem_mudar_o_caminho(tmp: Path):
    """Começar numa etapa roda o rabo da MESMA cadeia: cada passo que sobra é igual ao da cadeia
    inteira, e o explicador lê a saída da chapa (pronta no disco) e não o render cru."""
    if not fb.V2.exists():
        return  # a chapa é peça de tools/v2, que o kit não leva
    plano = _plano_fabrica(tmp)
    inteira = _cmds(fb.fabrica(plano, seco=True))
    for etapa in fb.ETAPAS[1:]:
        for cmd in fb.fabrica(plano, seco=True, desde=etapa).comandos:
            assert " ".join(cmd) in inteira, f"desde {etapa} montou um passo que a cadeia inteira não tem: {cmd[:4]}"
    composicao = fb.fabrica(plano, seco=True, desde="composicao")
    assert all(p.nome not in ("render", "chapa", "explicador") for p in composicao.passos)


def test_etapa_que_nao_existe_lista_as_validas(tmp: Path):
    erro = None
    try:
        fb.fabrica(_plano(tmp), seco=True, desde="pintura")
    except Exception as e:
        erro = e
    assert erro is not None and "corte" in str(erro)


# ---- uma fábrica, dois formatos ---------------------------------------------


def test_vertical_e_horizontal_pela_mesma_fabrica(tmp: Path):
    """O que derrubou as duas fábricas: os dois passam aqui e saem diferentes."""
    h = fb.fabrica(_plano(tmp), seco=True)
    v = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    assert h.estilo.orientacao == "16:9" and v.estilo.orientacao == "9:16"
    assert _cmds(h) != _cmds(v), "os dois formatos deram a mesma cadeia"
    assert h.comandos and v.comandos


def test_a_entrega_sai_onde_o_estilo_manda(tmp: Path):
    h = fb.fabrica(_plano(tmp), seco=True)
    v = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    assert h.final.parent.name == "provas", f"a aula não foi para o projeto: {h.final}"
    assert v.final.parent.name == "reels", f"o reel não foi para reels/: {v.final}"
    assert h.final.name == "teste.mp4", "o final não saiu por slug"


def test_o_corte_vem_do_estilo(tmp: Path):
    """Estilos com afinação diferente cortam diferente — o elo com a costura A."""
    aula = fb.fabrica(_plano(tmp), seco=True)
    reel = fb.fabrica(_plano(tmp, estilo="reel-mono"), seco=True)
    assert aula.edl != reel.edl, "aula e reel cortaram igual"


def test_sobrescrita_do_plano_chega_na_cadeia(tmp: Path):
    seco = fb.fabrica(_plano(tmp, imagem={"altura": 1080}), seco=True)
    assert "1080" in _cmds(seco), "a sobrescrita de altura não chegou no comando"


# ---- composição vertical ----------------------------------------------------


def test_recorte_volta_as_dimensoes_da_live_antes_de_cortar(tmp: Path):
    """O recorte é medido no quadro da live, e o render pode ter reescalado.
    Pular isso tira o rosto do lugar — foi o defeito que mais custou retrabalho."""
    plano = _plano(tmp, estilo="reel-mono",
                   imagem={"composicao": "pilha", "recorte": "crop=400:500:100:0"})
    cmd = next(c for c in fb.fabrica(plano, seco=True).comandos
               if "crop=400:500:100:0" in " ".join(c))
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.index("scale=640:400") < vf.index("crop=400:500"), \
        f"recortou antes de devolver às dimensões da live: {vf}"


def test_pilha_empilha_rosto_e_desenho(tmp: Path):
    desenho = _fonte(tmp, "desenho.mp4", dur=5)
    plano = _plano(tmp, estilo="reel-mono", camada=str(desenho),
                   imagem={"composicao": "pilha", "recorte": "crop=400:500:100:0"})
    txt = _cmds(fb.fabrica(plano, seco=True))
    assert "vstack=inputs=2" in txt, "a pilha não empilhou"


def test_sobreposicao_usa_chroma_em_vez_de_empilhar(tmp: Path):
    desenho = _fonte(tmp, "desenho.mp4", dur=5)
    plano = _plano(tmp, estilo="reel-mono", camada=str(desenho),
                   imagem={"composicao": "sobreposicao", "recorte": "crop=400:500:100:0"})
    txt = _cmds(fb.fabrica(plano, seco=True))
    assert "colorkey=0xff00ff" in txt and "vstack" not in txt


def test_sem_recorte_nao_ha_composicao(tmp: Path):
    """Quadro e reel de câmera usam o quadro inteiro — nada a montar."""
    txt = _cmds(fb.fabrica(_plano(tmp, estilo="reel-camera", bruto="camera"), seco=True))
    assert "vstack" not in txt and "colorkey" not in txt


def test_reel_de_camera_toca_os_sons(tmp: Path):
    """Aluno, 22/10: pediu efeito sonoro e o vídeo saiu sem. O reel de câmera sem blocos nunca
    chamava o som.py: nem o `sons` do plano, nem os golpes da legenda, nem os cues das peças."""
    sons = [{"tipo": "pop", "t": 1.0}]
    seco = fb.fabrica(_plano(tmp, estilo="reel-camera", bruto="camera", sons=sons), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "som" in nomes and nomes.index("som") > nomes.index("legenda"), nomes
    som = _passo(seco, "som")
    plan = json.loads(som.arquivo[1])
    assert plan["sons"] == sons, plan
    # a legenda grava os golpes dela ao lado do vídeo; o som.py lê de lá
    assert plan["cues_de"][0]["arquivo"] == str(_passo(seco, "legenda").saida), plan


def test_reel_de_camera_poe_as_pecas_da_fala_e_o_plano_desliga(tmp: Path):
    """O plano mínimo escolhe o reel-camera, e a fala escolhe as peças (recurso `pecas`, densidade do estilo): cada uma é um
    passo, e a legenda lê o plano que o `propoe.py --junta` monta. Quem tira o recurso, ou a densidade, fica sem."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    seco = fb.fabrica(_plano(tmp, estilo="reel-camera", bruto="camera"), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert "junta as peças da fala" in nomes, nomes
    junta = _passo(seco, "junta as peças da fala")
    assert nomes.index("junta as peças da fala") < nomes.index("legenda"), nomes
    pecas = json.loads(junta.arquivo[1])
    assert pecas and all(Path(b["arquivo"]).name for b in pecas) and {b["_peca"] for b in pecas} >= {"g_gancho"}, pecas
    assert junta.saida in _passo(seco, "legenda").entradas
    for plano in (_plano(tmp, estilo="reel-camera", bruto="camera", recursos={"-": ["pecas"]}),
                  _plano(tmp, estilo="reel-camera", bruto="camera", desenho={"densidade": None})):
        assert "junta as peças da fala" not in [p.nome for p in fb.fabrica(plano, seco=True).passos]


def test_ancora_da_live_vira_tempo_do_clipe(tmp: Path):
    """A âncora é medida assistindo a live; o card pousa no clipe já cortado."""
    trechos = [{"start": 10.0, "end": 12.0}, {"start": 20.0, "end": 23.0}]
    assert fb.tempo_de_saida(trechos, 10.0) == 0.0
    assert fb.tempo_de_saida(trechos, 11.5) == 1.5
    # o segundo trecho começa depois de 2s já mantidos, não aos 20s
    assert fb.tempo_de_saida(trechos, 20.0) == 2.0
    assert fb.tempo_de_saida(trechos, 22.0) == 4.0


def test_ancora_no_silencio_removido_cai_na_emenda(tmp: Path):
    """Fora de trecho mantido, o card entra na emenda — onde faz menos estrago."""
    trechos = [{"start": 10.0, "end": 12.0}, {"start": 20.0, "end": 23.0}]
    assert fb.tempo_de_saida(trechos, 15.0) == 2.0


# ---- o fecho com trilha -----------------------------------------------------


def _trilha(tmp: Path, **extra):
    faixa = _fonte(tmp, "musica.mp4", dur=4)
    plano = _plano(tmp, estilo="reel-mono", faixa=str(faixa),
                   recursos={"-": ["explicador", "legenda"]}, **extra)
    return next(c for c in fb.fabrica(plano, seco=True).comandos
                if "amix" in " ".join(c))


def test_a_faixa_entra_duas_vezes_e_cruza_consigo(tmp: Path):
    """É o que faz o laço não ter costura audível quando a música é curta."""
    cmd = _trilha(tmp)
    assert " ".join(cmd).count("musica.mp4") == 2, "a faixa não entrou duas vezes"
    assert "acrossfade" in cmd[cmd.index("-filter_complex") + 1]


def test_a_trilha_fica_no_piso_sem_fecho(tmp: Path):
    """Sem outro não há para onde subir: a trilha fica embaixo da fala inteira."""
    fc = _trilha(tmp)[_trilha(tmp).index("-filter_complex") + 1]
    assert "volume=0.03" in fc
    assert "clip(" not in fc, "subiu a trilha num reel que não tem fecho"


def test_com_fecho_a_trilha_sobe_em_rampa(tmp: Path):
    outro = _fonte(tmp, "outro.mp4", dur=5)
    cmd = _trilha(tmp, outro=str(outro))
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "clip(0.03" in fc, "a trilha não sobe no fecho"
    assert "concat=n=2" in fc, "o vídeo de fecho não foi concatenado"


def test_trilha_sem_fecho_copia_a_imagem(tmp: Path):
    """Sem fecho a trilha só mexe no áudio: a imagem passa por cópia, sem mais um encode. Com
    fecho o vídeo de saída é concatenado, e aí codifica."""
    cmd = _trilha(tmp)
    assert cmd[cmd.index("-c:v") + 1] == "copy", cmd
    outro = _fonte(tmp, "outro.mp4", dur=5)
    cmd = _trilha(tmp, outro=str(outro))
    assert cmd[cmd.index("-c:v") + 1] != "copy", "com fecho a imagem muda e tem que codificar"


def test_emenda_copia_a_imagem_quando_as_partes_sao_iguais(tmp: Path):
    """Blocos que saíram do mesmo passo emendam por cópia (a imagem não codifica de novo) e
    começam no zero do som; 25 com 30 continua recodificando. É o autoteste do junta."""
    import junta
    junta._autoteste()


def test_o_mix_nao_normaliza(tmp: Path):
    """Normalizar faria a trilha subir sozinha toda vez que a fala desse pausa."""
    fc = _trilha(tmp)[_trilha(tmp).index("-filter_complex") + 1]
    assert "normalize=0" in fc
    assert "alimiter" in fc, "sem limitador, o mix estoura no pico"


def test_sem_faixa_nao_ha_passo_de_trilha(tmp: Path):
    plano = _plano(tmp, estilo="reel-mono", recursos={"-": ["explicador", "legenda"]})
    assert not any("amix" in " ".join(c)
                   for c in fb.fabrica(plano, seco=True).comandos)


def test_desligar_o_recurso_tira_a_trilha(tmp: Path):
    faixa = _fonte(tmp, "musica.mp4", dur=4)
    plano = _plano(tmp, estilo="reel-mono", faixa=str(faixa),
                   recursos={"-": ["trilha"]})
    assert not any("amix" in " ".join(c)
                   for c in fb.fabrica(plano, seco=True).comandos)


def test_aula_que_virou_slide_reprova_antes_do_render(tmp: Path):
    """A régua: o defeito aparece aqui, não no gate de alunos depois do render."""
    plano = _plano(tmp, overlays=[{"scene": "rows", "itens": [{"tipo": "janela"}]},
                                  {"scene": "quote", "itens": []}])
    erro = None
    try:
        fb.fabrica(plano, seco=True)
    except Exception as e:
        erro = e
    assert erro is not None, "a aula só de texto passou"
    assert "régua" in str(erro)


def test_aula_com_desenho_passa_na_regua(tmp: Path):
    plano = _plano(tmp, overlays=[{"scene": "hub", "at": 1.0,
                                   "itens": [{"tipo": "rede"}, {"tipo": "robo"}]}])
    assert fb.fabrica(plano, seco=True).comandos


# ---- b-roll -----------------------------------------------------------------


def _broll(tmp: Path, beats):
    plano = _plano(tmp, estilo="reel-camera", bruto="camera", broll=beats)
    return next(c for c in fb.fabrica(plano, seco=True).comandos
                if "overlay" in " ".join(c))


def test_cada_corte_de_apoio_e_uma_entrada(tmp: Path):
    beats = [{"arquivo": "/b/um.mp4", "em": 3.7, "dur": 3.3},
             {"arquivo": "/b/dois.mp4", "em": 9.0, "dur": 2.0, "anim": "left"}]
    cmd = _broll(tmp, beats)
    linha = " ".join(cmd).replace("\\", "/")     # no Windows o caminho volta com \
    assert linha.count("/b/um.mp4") == 1, linha
    assert linha.count("/b/dois.mp4") == 1, linha


def test_o_deslize_mora_na_coordenada_e_nao_num_fade(tmp: Path):
    """O overlay só aceita uma posição por quadro: a rampa TEM que estar no x/y."""
    cmd = _broll(tmp, [{"arquivo": "/b/um.mp4", "em": 3.0, "dur": 2.0, "anim": "top"}])
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "clip((t-3.0)" in fc, "a entrada não é função do tempo"
    assert "overlay=x=" in fc and "y='" in fc


def test_o_apoio_so_existe_na_janela_dele(tmp: Path):
    cmd = _broll(tmp, [{"arquivo": "/b/um.mp4", "em": 3.0, "dur": 2.0}])
    assert "enable='between(t," in cmd[cmd.index("-filter_complex") + 1], \
        "sem enable o clipe é composto o vídeo inteiro"


def test_sem_broll_nao_ha_passo(tmp: Path):
    plano = _plano(tmp, estilo="reel-camera", bruto="camera")
    assert not any("overlay" in " ".join(c)
                   for c in fb.fabrica(plano, seco=True).comandos)


# ---- o cache por impressão --------------------------------------------------


def test_rodar_duas_vezes_nao_refaz_nada(tmp: Path):
    """19,5 s medidos para não mudar nada. É o que o cache existe para matar."""
    plano = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(plano)
    seco = fb.fabrica(plano, seco=True)
    feitos = [p for p in seco.passos if not fb.ja_feito(p)]
    assert not feitos, f"sobrou passo para refazer: {[p.nome for p in feitos]}"


def test_trocar_o_conteudo_do_card_nao_refaz_o_corte(tmp: Path):
    """O que dói é o décimo render, depois de ajustar uma legenda."""
    base = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(base)
    mexido = {**base, "overlays": [{"scene": "hub",
                                    "itens": [{"tipo": "rede"}, {"tipo": "robo"}]}]}
    seco = fb.fabrica(mexido, seco=True)
    render = next(p for p in seco.passos if p.nome == "render")
    assert fb.ja_feito(render), "trocar o card refez o render"


def test_trocar_a_janela_refaz_do_corte_em_diante(tmp: Path):
    base = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(base)
    seco = fb.fabrica({**base, "janelas": [[0.4, 3.0]]}, seco=True)
    render = next(p for p in seco.passos if p.nome == "render")
    assert not fb.ja_feito(render), "mudar a janela não refez o render"


def test_mexer_no_helper_invalida_o_que_ele_produziu(tmp: Path):
    """Corrigir uma heurística tem que refazer o que ela produziu."""
    plano = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(plano)
    render = next(p for p in fb.fabrica(plano, seco=True).passos if p.nome == "render")
    assert fb.ja_feito(render)

    alvo = Path(fb.AQUI / "render.py")
    original = alvo.read_bytes()
    try:
        alvo.write_bytes(original + b"\n# comentario novo\n")
        render2 = next(p for p in fb.fabrica(plano, seco=True).passos if p.nome == "render")
        assert not fb.ja_feito(render2), "mexer no helper não invalidou a saída dele"
    finally:
        alvo.write_bytes(original)


def test_saida_truncada_nao_conta_como_feita(tmp: Path):
    plano = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(plano)
    passo = next(p for p in fb.fabrica(plano, seco=True).passos if p.nome == "render")
    passo.saida.write_bytes(b"\x00" * 10)
    assert not fb.ja_feito(passo), "arquivo pela metade passou como pronto"


def test_o_cache_nao_muda_o_resultado(tmp: Path):
    """A única diferença entre com e sem cache tem que ser o tempo."""
    plano = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    a = fb.fabrica(plano)
    bruto_a = a.read_bytes()
    b = fb.fabrica(plano)
    assert b.read_bytes() == bruto_a, "a corrida com cache entregou outro arquivo"


def test_sem_cache_traz_todos_os_passos_de_volta(tmp: Path):
    """Quem desconfia precisa confirmar sem apagar pasta."""
    plano = _plano(tmp, recursos={"-": ["emenda", "abertura", "explicador"]})
    fb.fabrica(plano)
    seco = fb.fabrica(plano, seco=True, sem_cache=True)
    assert all(not p.pulavel for p in seco.passos), "sem_cache ainda pulou passo"


def test_trocar_o_card_refaz_o_explicador(tmp: Path):
    """O caso que o cache tem que pegar e quase deixou passar: o conteúdo do card
    muda, o comando fica igual (o caminho é o mesmo), e o vídeo sai com o card
    velho. Sem barulho nenhum."""
    def com(texto):
        return _plano(tmp, recursos={"-": ["emenda", "abertura"]},
                      overlays=[{"scene": "hub", "at": 1.0, "h": texto,
                                 "itens": [{"tipo": "rede"}, {"tipo": "robo"}]}])
    fb.fabrica(com("primeira versão"), seco=True)
    a = next(p for p in fb.fabrica(com("primeira versão"), seco=True).passos
             if p.nome == "explicador")
    b = next(p for p in fb.fabrica(com("OUTRO TEXTO"), seco=True).passos
             if p.nome == "explicador")
    assert fb._digital(a) != fb._digital(b), \
        "trocar o texto do card não mudou a impressão — o cache entregaria o velho"


def test_trocar_um_arquivo_de_entrada_refaz_o_passo(tmp: Path):
    """Trilha, camada, b-roll e legenda entram pelo comando. Se não entrarem na
    impressão, trocar o arquivo no mesmo caminho passa despercebido."""
    faixa = _fonte(tmp, "musica.mp4", dur=4)
    plano = _plano(tmp, estilo="reel-mono", faixa=str(faixa),
                   recursos={"-": ["explicador", "legenda"]})
    antes = next(p for p in fb.fabrica(plano, seco=True).passos
                 if p.nome == "fecho com trilha")
    d_antes = fb._digital(antes)
    _fonte(tmp, "musica.mp4", dur=6)          # outra faixa, mesmo caminho
    depois = next(p for p in fb.fabrica(plano, seco=True).passos
                  if p.nome == "fecho com trilha")
    assert d_antes != fb._digital(depois), "trocar a faixa não mudou a impressão"


# ---- o preço antes do render ------------------------------------------------


def test_o_modo_seco_estima_o_custo(tmp: Path):
    seco = fb.fabrica(_plano(tmp), seco=True)
    assert seco.custo_total() > 0, "o modo seco não estimou nada"
    assert all(p.custo(seco.duracao) > 0 for p in seco.passos)


def test_o_passo_que_toca_pouco_e_custa_muito_sai_marcado(tmp: Path):
    """A regra que achou os dois candidatos deste spec fica no código para achar
    o próximo."""
    seco = fb.fabrica(_plano(tmp), seco=True)
    suspeitos = [p.nome for p in seco.passos if p.suspeito(seco.duracao)]
    assert "glitch de emenda" in suspeitos, \
        f"o glitch toca 0,4s de 54s e não foi marcado: {suspeitos}"
    assert "render" not in suspeitos, "o render toca tudo — não é suspeito, é honesto"


def test_o_passo_que_toca_tudo_nao_e_suspeito(tmp: Path):
    render = next(p for p in fb.fabrica(_plano(tmp), seco=True).passos
                  if p.nome == "render")
    assert render.toca is None
    assert not render.suspeito(54.0)


# ---- o tempo medido, o seco curto e o progresso -----------------------------


import contextlib
import io
import os


@contextlib.contextmanager
def _cache_em(pasta: Path):
    """O cache de tempo e as vagas do usuário apontam para a pasta do teste: nada escreve em ~/.cache."""
    velho = os.environ.get(fb.vagas.CACHE)
    os.environ[fb.vagas.CACHE] = str(pasta)
    try:
        yield
    finally:
        os.environ.pop(fb.vagas.CACHE, None)
        if velho is not None:
            os.environ[fb.vagas.CACHE] = velho


def test_o_tempo_medido_guarda_as_cinco_ultimas_e_a_mediana_vale(tmp: Path):
    with _cache_em(tmp / "cache"):
        por_s = fb.Passo("bloco 1: recorte", ["x"], tmp / "a.mp4")       # custa o vídeo: guarda s por s
        fixo = fb.Passo("transcreve a.mp3", ["x"], tmp / "t.json", custo_fixo=60.0)
        for s in (10, 20, 30, 40, 50, 60, 70):                          # sete corridas de 100 s de vídeo
            fb.grava_tempo(por_s, 100.0, s)
            fb.grava_tempo(fixo, 100.0, s)
        medidos = fb.tempos_medidos()
        assert sorted(len(v) for v in medidos.values()) == [5, 5], medidos      # só as 5 últimas: 30 a 70
        assert por_s.estima(200.0, medidos) == (100.0, True), "0,5 s por s de vídeo, num vídeo de 200 s"
        assert fixo.estima(200.0, medidos) == (50.0, True), "passo fixo não escala com o vídeo"
        # a chave é o tipo do passo, sem o bloco nem o nome do arquivo
        assert replace_nome(por_s, "bloco 7: recorte").chave == por_s.chave
        assert replace_nome(fixo, "transcreve b.mp3").chave == fixo.chave
        assert replace_nome(por_s, "bloco 1: som").chave != por_s.chave
        # sem amostra, o número de fábrica, dito estimativa
        novo = fb.Passo("glitch de emenda", ["x"], tmp / "g.mp4", toca=0.4)
        assert novo.estima(54.0, medidos) == (novo.custo(54.0), False)
    # cache ilegível não derruba nada
    with _cache_em(tmp / "ruim"):
        (tmp / "ruim").mkdir()
        (tmp / "ruim" / "tempos.json").write_text("{não é json", encoding="utf-8")
        assert fb.tempos_medidos() == {}
        fb.grava_tempo(fixo, 10.0, 5.0)
        assert list(fb.tempos_medidos().values()) == [[5.0]]


def replace_nome(passo, nome):
    return fb.replace(passo, nome=nome)


def test_o_seco_sai_curto_e_o_detalhe_traz_o_comando(tmp: Path):
    with _cache_em(tmp / "cache"):
        seco = fb.fabrica(_plano(tmp), seco=True)

        def tela(**kw) -> str:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                seco.imprime(**kw)
            return buf.getvalue()
        curto, longo = tela(), tela(detalhe=True)
        linhas = [l for l in curto.splitlines() if re.match(r"\s*\d+ [ !=$] ", l)]
        assert len(linhas) == len(seco.passos), curto
        assert all("estimado" in l for l in linhas), "sem medida nenhuma, toda linha é estimativa de fábrica"
        assert not any(" ".join(p.cmd) in curto for p in seco.passos), "o curto não traz o comando"
        assert all(" ".join(p.cmd) in longo for p in seco.passos), "o detalhe traz todos"
        assert "muda " in longo and "muda " not in curto
        assert len(curto.splitlines()) < len(longo.splitlines())
        assert re.search(r"~\d+(\.\d)? min", curto.splitlines()[-1]), curto.splitlines()[-1]
        # medido nesta máquina: a linha do render troca de origem e o resto não
        render = next(p for p in seco.passos if p.nome == "render")
        fb.grava_tempo(render, seco.duracao, 12.0)
        depois = [l for l in tela().splitlines() if re.match(r"\s*\d+ [ !=$] ", l)]
        dele = [l for l in depois if re.match(r"\s*\d+ . render\s{2}", l)]
        assert len(dele) == 1 and "medido" in dele[0] and "estimado" not in dele[0], dele
        assert sum("medido" in l for l in depois) == 1


def test_main_so_mostra_o_comando_com_detalhe(tmp: Path):
    pj = tmp / "plano.json"
    pj.write_text(json.dumps(_plano(tmp)), encoding="utf-8")
    saidas = {}
    velho = sys.argv
    try:
        with _cache_em(tmp / "cache"):
            for flags in ([], ["--detalhe"]):
                sys.argv = ["fabrica.py", str(pj), "--seco", *flags]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    fb.main()
                saidas[bool(flags)] = buf.getvalue()
    finally:
        sys.argv = velho
    assert "muda tudo" not in saidas[False] and "muda tudo" in saidas[True], saidas


def test_storyboard_do_celular_sem_visual_json_para_na_linha_da_pauta(tmp: Path):
    """O primeiro vídeo do celular não ganha storyboard sem a pauta: falta o visual.json, a linha manda fazê-la.
    Só com `--pauta` (opt-in); com o arquivo ao lado, segue. Plano em blocos nunca lê a pauta."""
    plano = _plano(tmp, estilo="reel-camera")
    e = fb.es.estilo("reel-camera")
    fala = tmp / "fala_cortada.json"
    linha = fb._falta_pauta(plano, e, fala)
    assert linha and linha.startswith("pauta: falta o visual.json") and "pauta-visual.md" in linha, linha
    assert "fala_cortada.json" in linha and "sem --pauta" in linha and "visual.json" in linha, linha
    assert fb._falta_pauta({**plano, "blocos": [{"nome": "a"}]}, e, fala) is None
    (tmp / "visual.json").write_text("[]", encoding="utf-8")
    plano["_dir"] = str(tmp)
    assert fb._falta_pauta(plano, e, fala) is None
    assert "--pauta" in subprocess.run([sys.executable, str(Path(fb.__file__)), "-h"], capture_output=True,
                                           text=True, encoding="utf-8").stdout


def test_storyboard_sem_pauta_nao_faz_trabalho_pesado_antes_de_parar(tmp: Path):
    """Com `--pauta` e sem `visual.json` o `--storyboard` do celular faz só o que a pauta lê (corte, transcrição, a fala cortada) e para na
    linha `pauta:`: nem render nem legenda antes. Sem a flag (ou com o arquivo) a cadeia vem inteira, e sem a legenda."""
    plano = _plano(tmp, estilo="reel-camera", _dir=str(tmp))
    nomes = lambda **kw: [p.nome for p in fb.fabrica(plano, seco=True, storyboard=True, **kw).passos]  # noqa: E731
    assert nomes(pauta=True) == ["cards da fala"], nomes(pauta=True)
    inteira = nomes()
    assert "render" in inteira and "legenda" not in inteira, inteira
    # o render final continua queimando a legenda
    assert "legenda" in [p.nome for p in fb.fabrica(plano, seco=True).passos]


def test_executa_mostra_o_progresso_grava_o_tempo_e_so_pede_vaga_a_quem_custa(tmp: Path):
    pedidas = []

    @contextlib.contextmanager
    def ocupa(quantas):
        pedidas.append(quantas)
        yield

    def passo(nome, **kw):
        saida = tmp / f"{nome}.bin"
        return fb.Passo(nome, ["fake", *kw.pop("le", []), str(saida)], saida, **kw)

    def roda(cmd, **kw):
        if cmd[-1].endswith("quebra.bin"):
            raise RuntimeError("quebrou")
        Path(cmd[-1]).write_bytes(b"x" * fb.impressao.PISO_BYTES)

    a = passo("a", custo_fixo=30.0)
    b = passo("b", le=[str(tmp / "a.bin")])
    de_graca = passo("de graça", custo_fixo=0.0)
    quebra = passo("quebra", custo_fixo=5.0)
    velho_run, velho_ocupa = fb.ff.run, fb.vagas.ocupa
    fb.ff.run, fb.vagas.ocupa = roda, ocupa
    try:
        with _cache_em(tmp / "cache"):
            tela = io.StringIO()
            with contextlib.redirect_stdout(tela):
                fb._executa([a, b, de_graca], sem_cache=True, paralelo=3, duracao=50.0)
            linhas = [l for l in tela.getvalue().splitlines() if l.startswith("passo ")]
            assert len(linhas) == 3, tela.getvalue()
            assert all(re.fullmatch(r"passo \d/3 · .+ · \d+\.\d s · faltam ~\d+\.\d min", l) for l in linhas), linhas
            assert linhas[-1].startswith("passo 3/3") and linhas[-1].endswith("faltam ~0.0 min"), linhas
            assert pedidas == [3, 3], f"a vaga é só de quem custa (a e b, não o de graça): {pedidas}"
            medidos = fb.tempos_medidos()
            assert a.chave in medidos and b.chave in medidos, medidos
            assert all(len(v) == 1 for v in medidos.values())
            # passo que quebra não deixa amostra
            try:
                fb._executa([quebra], sem_cache=True, paralelo=1, duracao=50.0)
            except RuntimeError:
                pass
            else:
                raise AssertionError("o passo que quebrou não parou a cadeia")
            assert quebra.chave not in fb.tempos_medidos()
    finally:
        fb.ff.run, fb.vagas.ocupa = velho_run, velho_ocupa


# ---- paralelo ---------------------------------------------------------------


def test_os_trechos_saem_na_ordem_das_janelas(tmp: Path):
    """O paralelo não pode entregar por ordem de término. Costurar trecho fora de
    ordem é requisito antigo, e é o que o paralelo ameaça."""
    import render
    fonte = _fonte(tmp, dur=6)
    edl = {"version": 1, "sources": {fonte.stem: str(fonte)},
           "ranges": [{"source": fonte.stem, "start": 4.0, "end": 4.6},
                      {"source": fonte.stem, "start": 0.2, "end": 0.8},
                      {"source": fonte.stem, "start": 2.0, "end": 2.6}],
           "grade": "none", "overlays": [], "total_duration_s": 1.8}
    edit = tmp / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    partes = render.extract_all_segments(edl, edit, preview=False, draft=True,
                                         out_height=240, fps=25)
    assert len(partes) == 3
    assert [p.name for p in partes] == sorted(p.name for p in partes), \
        f"os trechos saíram fora da ordem pedida: {[p.name for p in partes]}"
    assert all(p.exists() for p in partes), "algum trecho não foi produzido"


def test_um_trecho_que_falha_diz_qual(tmp: Path):
    """O paralelo não pode transformar erro em mistério."""
    import render
    fonte = _fonte(tmp, dur=3)
    edl = {"version": 1, "sources": {fonte.stem: str(fonte)},
           "ranges": [{"source": fonte.stem, "start": 0.2, "end": 0.6},
                      {"source": "fantasma", "start": 0.2, "end": 0.6}],
           "grade": "none", "overlays": [], "total_duration_s": 0.8}
    edit = tmp / "edit2"
    edit.mkdir(parents=True, exist_ok=True)
    erro = None
    try:
        render.extract_all_segments(edl, edit, preview=False, draft=True,
                                    out_height=240, fps=25)
    except Exception as e:
        erro = e
    assert erro is not None, "trecho com fonte inexistente passou"


# ---- o reel de avatar ---------------------------------------------------------


def _reel_avatar(tmp: Path, slug: str, dur: float, tela_cheia: list) -> Path:
    voz = tmp / f"{slug}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=220:duration={dur}", str(voz)], check=True)
    caminho = tmp / f"{slug}.json"
    caminho.write_text(json.dumps({
        "estilo": "reel-avatar", "slug": slug, "projeto": "provas",
        "saida": str(tmp / "saida"),
        "blocos": [{"nome": "b1", "fonte": str(voz), "transcript": str(_transcript(tmp, voz)),
                    "tela_cheia": tela_cheia}]}), encoding="utf-8")
    return caminho


def test_voz_sintetica_pula_o_microfone(tmp: Path):
    """A voz do Eleven v4 já chega limpa e no nível: a cadeia do OBS em cima dela
    tira ruído que não existe. O apara, o ouvido e o portão continuam."""
    plano = json.loads(_reel_avatar(tmp, "seg", 4, []).read_text(encoding="utf-8"))
    cmds = _cmds(fb.fabrica(plano, seco=True))
    assert "trata_voz.py" not in cmds, f"a voz sintética passou pelo microfone: {cmds}"
    for helper in ("apara_pausas.py", "ouvido.py", "pre_voo.py"):
        assert helper in cmds, f"faltou {helper} depois de pular o tratamento"
    assert f"apara_pausas.py {tmp / 'seg.wav'}" in cmds, "o apara tem que ler a voz como veio"


def test_trechos_de_rosto_de_dois_reels_numa_geracao(tmp: Path):
    """Os reels da semana numa geração só: cada um manda só o rosto, e o mapa
    devolve cada pedaço ao reel e ao tempo de onde saiu."""
    if not (Path(fb.__file__).parent / "trechos_de_rosto.py").exists():
        return                          # vem no módulo Clone de IA; com ele instalado, roda aqui
    import trechos_de_rosto as tr
    seg = _reel_avatar(tmp, "seg", 8, [[2, 5]])
    qua = _reel_avatar(tmp, "qua", 6, [[0, 1], [4, 6]])
    try:
        tr.blocos_do_plano(seg)
        assert False, "montou a geração sem o áudio limpo do portão"
    except FileNotFoundError:
        pass
    for p in (seg, qua):
        # o áudio limpo que a fábrica deixa no portão
        apara = next(x for x in fb.fabrica({**json.loads(p.read_text(encoding="utf-8")), "_dir": str(tmp)},
                                           seco=True).passos if "apara_pausas.py" in x.cmd[1])
        apara.saida.parent.mkdir(parents=True, exist_ok=True)
        apara.saida.write_bytes((tmp / f"{p.stem}.wav").read_bytes())

    doc = tr.monta(tr.blocos_do_plano(seg) + tr.blocos_do_plano(qua), tmp / "semana")
    pedacos = [(t["reel"], t["fonte"]) for t in doc["trechos"]]
    assert pedacos == [("seg", [0.0, 2.25]), ("seg", [4.75, 8.0]), ("qua", [0.75, 4.25])], (
        f"tela cheia na borda não sobra rosto; no meio, 0,25 s pra dentro da peça: {pedacos}")
    assert doc["trechos"][2]["gerado"] == [6.1, 9.6], doc["trechos"][2]
    assert abs(ff.dur(tmp / "semana" / "geracao.wav") - 9.6) < 0.05, "o wav não bate com o mapa"

    gerado = tmp / "gerado.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=108x192:rate=25:duration=9.6", "-pix_fmt", "yuv420p",
                    str(gerado)], check=True)
    voltas = {b["reel"]: s for b, s in tr.devolve(tmp / "semana" / "geracao.json", gerado)}
    for reel, dur in (("seg", 8), ("qua", 6)):
        assert abs(ff.dur(voltas[reel]) - dur) < 0.1, (
            f"{reel} voltou com {ff.dur(voltas[reel]):.2f}s, e o áudio limpo tem {dur}s")


# ---- o reel editorial ---------------------------------------------------------


def _reel_editorial(tmp: Path, **extra) -> dict:
    """Um reel editorial mínimo: a voz, o transcript e o webm existem (o webm só de nome:
    o modo seco não o abre), e o resto é o plano."""
    voz = _voz(tmp, dur=3)
    (tmp / "transcripts").mkdir(exist_ok=True)
    (tmp / "transcripts" / f"{voz.stem}.json").write_text(json.dumps({"words": [
        {"text": "Oi.", "start": 0.2, "end": 0.6, "type": "word"}]}), encoding="utf-8")
    (tmp / "avatar").mkdir(exist_ok=True)
    (tmp / "avatar" / "rosto.webm").write_bytes(b"webm")
    # o fundo e a trilha do plano, gerados aqui: o estilo não tem fundo, e o pacote não leva música
    fundo, faixa = tmp / "fundo.png", tmp / "faixa.wav"
    if not fundo.exists():
        from PIL import Image
        Image.new("RGB", (1080, 1920), (40, 44, 52)).save(fundo)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                        str(faixa)], check=True)
    plano = {"estilo": "reel-editorial", "slug": "novo", "fonte": voz.name, "narracao": "Oi.",
             "saida": str(tmp / "saida"), "_dir": str(tmp), "trabalho": "_trabalho", "dur": 3.0,
             "imagem": {"fundo": str(fundo)},
             "avatar": {"arquivo": "avatar/rosto.webm", "cartao": {"s": 1.0, "x": 18, "y": 427},
                        "cheio": {"s": 1.2, "x": -6, "y": -378}},
             "base": [{"de": 0.0, "ate": 1.5, "avatar": 0.0, "quadro": "cartao"},
                      {"de": 1.5, "ate": 3.0, "avatar": 1.5, "quadro": "cheio"}],
             "r": {"dur": 3.0, "cenas": [[0, 1.5, "split", "tinta"], [1.5, 3.0, "rosto"]],
                   "vozes": [{"t": 2.0, "ate": 3.0, "chamada": ["comenta", "“OI”"]}]},
             "pecas": [{"nome": "gancho", "peca": "g_gancho", "em": 0, "ate": 1.5, "segura": True,
                        "caixa": [60, 440, 1020, 720], "q": {"l": "*OI"}}],
             "sons": [], "trilha": {"faixa": str(faixa)}}
    plano.update(extra)
    return plano


def test_reel_editorial_monta_pelo_helper(tmp: Path):
    """Três monta.py copiados faziam o reel do molde do Nick. Agora é estilo: a fábrica
    confere, põe o que é do estilo no plano e chama o helper passo a passo."""
    if not fb.V2.exists():
        return  # o kit não leva tools/v2
    seco = fb.fabrica(_reel_editorial(tmp), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes == ["transcreve take.wav", "take", "pessoa", "camadas", "pecas", "compor", "junta", "som",
                     "folha"], nomes
    assert seco.final.parent.name == "topo" and seco.final.name == "novo.mp4", seco.final
    doc = json.loads(_arquivo(seco)[1])["_estilo"]
    assert doc["fundo"] == str(tmp / "fundo.png"), f"o fundo atrás do rosto é o do plano: {doc['fundo']}"
    assert doc["mixa"] == ["--cama", "-21.0", "--duck-ratio", "3.0", "--fade-fim", "0.6"], doc["mixa"]
    assert "fecho com trilha" not in nomes, "a cama da fábrica por cima da trilha do reel"


def test_reel_editorial_nao_gasta_sozinho(tmp: Path):
    """A voz e o avatar custam dinheiro: faltando, viram passo que cobra, impresso, e a
    cadeia para ali — nem a execução chama a ElevenLabs."""
    if not fb.V2.exists():
        return
    plano = _reel_editorial(tmp)
    (tmp / "avatar" / "rosto.webm").unlink()
    seco = fb.fabrica(plano, seco=True)
    assert [(p.nome, p.cobra) for p in seco.passos] == [("transcreve take.wav", ""), ("heygen", ""),
                                                           ("avatar", "HeyGen")], seco.passos
    (tmp / plano["fonte"]).unlink()
    seco = fb.fabrica(plano, seco=True)
    assert [(p.nome, p.cobra) for p in seco.passos] == [("narração", "ElevenLabs")], seco.passos
    fb.fabrica(plano)
    assert not (tmp / plano["fonte"]).exists(), "a fábrica gerou a voz sozinha"


def test_reel_editorial_sem_rosto_nao_pede_heygen(tmp: Path):
    """O Reel da isca ROTEIRO é todo tela: o terminal e o roteiro, sem avatar (pedido do dono, 04/10).
    A fábrica lia o webm do plano e, sem ele, parava pedindo a HeyGen; o confere cobrava o fundo
    atrás de um rosto que não existe."""
    if not fb.V2.exists():
        return
    cena = tmp / "cena.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=3", "-pix_fmt", "yuv420p", cena)
    plano = _reel_editorial(tmp, base=[{"de": 0.0, "ate": 3.0, "cena": "cena.mp4"}],
                            r={"dur": 3.0, "cenas": [[0, 3.0, "rosto"]]}, imagem={})
    del plano["avatar"]
    (tmp / "avatar" / "rosto.webm").unlink()
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert not any(p.cobra for p in seco.passos), f"sem rosto, nada cobra: {[(p.nome, p.cobra) for p in seco.passos]}"
    assert nomes[:3] == ["transcreve take.wav", "take", "pessoa"] and "heygen" not in nomes, nomes
    # e o helper monta o take e a pessoa (transparente) sem o webm
    pj, texto = _arquivo(seco)
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(texto, encoding="utf-8")
    re_ = fb._reel()
    r = re_.Reel(pj.parent)
    assert re_.take(r).exists() and re_.pessoa(r).exists()


def test_reel_editorial_cobra_as_regras_do_dono(tmp: Path):
    """As decisões de 30/09 recusadas no modo seco, cada uma com o motivo."""
    if not fb.V2.exists():
        return
    base = _reel_editorial(tmp)
    r = base["r"]
    casos = {
        "cartão arredondado": {"base": [{"de": 0.0, "ate": 1.5, "painel": "tinta", "quadro": "cartao"},
                                        base["base"][1]]},
        "chamada": {"r": {**r, "vozes": [{"t": 0.2, "ate": 3.0, "chamada": ["comenta", "“OI”"]}]}},
        "legenda do Instagram": {"pecas": [{**base["pecas"][0], "caixa": [60, 1200, 1020, 1600]}]},
        "selo de IA": {"selo": {"texto": "feito com IA"}},
        # a voz acaba em 3,0 e o reel em 3,8: a cauda muda vira a maior pausa do geracao.wav
        "cauda do reel": {"dur": 3.8, "base": [base["base"][0], {**base["base"][1], "ate": 3.8}]},
        # o heygen-rosto pedia `tick`, que o banco não tem: o som.py pulava calado
        "o banco": {"sons": [{"tipo": "tick", "t": 0.35}]},
        "tela cheia": {"base": [base["base"][0], {"de": 1.5, "ate": 3.0, "painel": "tinta"}],
                       "r": {**r, "cenas": [[0, 1.5, "split", "tinta"], [1.5, 3.0, "tela", "tinta"]]}},
        "quadro 0": {"pecas": [{**base["pecas"][0], "em": 0.5}]},
        # o estilo não tem fundo: sem o do plano, o rosto ia sobre o escritório do dono
        "imagem.fundo": {"imagem": {}},
    }
    for motivo, troca in casos.items():
        erro = None
        try:
            fb.fabrica({**base, **troca}, seco=True)
        except ValueError as e:
            erro = str(e)
        assert erro and motivo in erro, f"{motivo}: passou ou reprovou por outro motivo: {erro}"


def test_reel_editorial_cabeca_e_rosto_do_mesmo_webm(tmp: Path):
    """Em 30/09 o webm foi trocado depois do take: o rosto no cartão ficou do velho e a
    cabeça, do novo. Os dois passos leem o webm, e trocá-lo refaz os dois."""
    if not fb.V2.exists():
        return
    seco = fb.fabrica(_reel_editorial(tmp), seco=True)
    webm = tmp / "avatar" / "rosto.webm"
    for nome in ("take", "pessoa"):
        # pelo nome inteiro: "transcreve take.wav" também tem "take"
        passo = next(p for p in seco.passos if p.nome == nome)
        assert webm in passo.entradas, f"o {nome} não enxerga o webm"


def test_reel_editorial_capa_ve_a_foto(tmp: Path):
    """A impressão da capa olhava só o bloco do plano: trocar a foto ou o logo mantendo o
    nome entregava a capa velha."""
    if not fb.V2.exists():
        return
    foto, logo = tmp / "foto.png", tmp / "logo.svg"
    foto.write_bytes(b"velha")
    logo.write_bytes(b"<svg/>")
    plano = _reel_editorial(tmp, capa={"foto": "foto.png", "logo": "@logo.svg", "lados": "mic,@logo.svg",
                                       "titulo": "a|b"})
    capa = lambda: fb._digital(_passo(fb.fabrica(plano, seco=True), "capa"))
    antes = capa()
    foto.write_bytes(b"a foto nova")
    depois = capa()
    assert depois != antes, "trocar a foto não refaz a capa"
    logo.write_bytes(b"<svg>outro</svg>")
    assert capa() != depois, "trocar o logo não refaz a capa"


def test_reel_editorial_peca_mostra_a_capa_que_a_cadeia_faz(tmp: Path):
    """Em 03/10 o --seco numa pasta nova reprovou o plano cujo r_capa mostra a capa: o
    `_trabalho/capa-nick.jpg` ainda não existe, e quem o faz é o passo `capa`, antes das peças."""
    if not fb.V2.exists():
        return
    mostra = {"nome": "capa", "peca": "r_capa", "em": 1.5, "ate": 3.0, "q": {"img": "@_trabalho/capa-nick.jpg"}}
    base = _reel_editorial(tmp)
    plano = {**base, "pecas": [*base["pecas"], mostra]}
    try:
        fb.fabrica(plano, seco=True)
        assert False, "sem `capa` no plano ninguém faz o arquivo, e o --seco deixou passar"
    except ValueError as e:
        assert "capa-nick.jpg" in str(e), e
    nomes = [p.nome for p in fb.fabrica({**plano, "capa": {"titulo": "a|b"}}, seco=True).passos]
    assert nomes.index("capa") < nomes.index("pecas"), nomes


def test_transcricao_abre_o_audio(tmp: Path):
    """Em 03/10 o pacote sem lock instalou o av 19, e o faster-whisper quebrou ao abrir o áudio
    (`open() got an unexpected keyword argument 'metadata_errors'`) no primeiro vídeo do aluno.
    A conferência passava: nada abria áudio por ele. Abre aqui, sem baixar modelo."""
    from faster_whisper import decode_audio
    audio = decode_audio(str(_voz(tmp, dur=1)))
    assert abs(len(audio) - 16000) < 400, len(audio)


def _reel_de_verdade(tmp: Path, **extra):
    """O helper e um Reel dele, com o reel.json que a fábrica deixaria na pasta de trabalho."""
    re_ = fb._reel()
    pj, texto = _arquivo(fb.fabrica(_reel_editorial(tmp, **extra), seco=True))
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(texto, encoding="utf-8")
    return re_, re_.Reel(pj.parent)


def _troca(mod, **novas):
    """Troca funções do módulo e devolve como desfazer."""
    velhas = {k: getattr(mod, k) for k in novas}
    for k, v in novas.items():
        setattr(mod, k, v)
    return lambda: [setattr(mod, k, v) for k, v in velhas.items()]


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def test_transcricao_refeita_quando_a_fonte_muda(tmp: Path):
    """Em 30/09 a frase do YouTube foi gerada de novo e o transcribe.py devolveu o que a voz
    VELHA disse: o cache olhava só o nome. O passo `transcreve` da fábrica tinha o mesmo furo."""
    import os
    import transcribe as tr
    voz = _voz(tmp, dur=1)
    velha = tmp / "transcripts" / f"{voz.stem}.json"
    velha.parent.mkdir()
    velha.write_text(json.dumps({"words": [{"text": "velha"}]}), encoding="utf-8")
    os.utime(velha, (1, 1))
    feitas = []
    desfaz = _troca(tr, _transcribe_audio=lambda *a, **k: feitas.append(1) or {"words": [{"text": "nova"}]})
    try:
        tr.transcribe_one(voz, tmp, verbose=False)
        assert feitas, "a voz refeita voltou com a transcrição da velha"
        tr.transcribe_one(voz, tmp, verbose=False)
        assert len(feitas) == 1, "transcreveu de novo sem a fonte mudar"
    finally:
        desfaz()


def test_transcricao_segue_a_voz(tmp: Path):
    """Em 01/10 a voz nova do criativo saiu cortada e legendada no tempo da velha: o passo
    `transcreve` só entrava quando transcripts/<voz>.json faltava. Agora ele está sempre na cadeia,
    e a impressão, que olha a voz, decide se refaz. O editorial e o avatar tinham o mesmo furo."""
    if SEM_CRIATIVO:
        return
    plano = _criativo(tmp)
    fala = tmp / "transcripts" / "take.json"
    # do tamanho de uma de verdade: abaixo de 1 KB a impressão não aceita a saída como feita
    fala.write_text(json.dumps({**json.loads(fala.read_text(encoding="utf-8")),
                                "text": "Oi gente tudo bem " * 60}), encoding="utf-8")

    def transcreve():
        return next(p for p in fb.fabrica(plano, seco=True).passos if p.nome == "transcreve take.wav")
    passo = transcreve()
    fb.impressao.marca(passo.saida, fb._digital(passo))       # a corrida anterior transcreveu
    assert transcreve().pulavel, "a voz não mudou e a transcrição seria refeita"
    _voz(tmp, dur=2)                                          # a voz gerada de novo, no mesmo nome
    assert not transcreve().pulavel, "voz nova, transcrição velha"
    # a transcrição em outro caminho é do usuário: a fábrica não escreve por cima
    (tmp / "minha.json").write_text(fala.read_text(encoding="utf-8"), encoding="utf-8")
    assert "transcribe.py" not in _cmds(fb.fabrica({**plano, "transcript": "minha.json"}, seco=True))
    # no avatar também: a de transcripts/ segue a voz, a do plano em outro lugar fica como está
    vsl = _plano_vsl(tmp)
    nomes = [p.nome for p in fb.fabrica({**vsl, "transcript": str(fala)}, seco=True).passos]
    assert nomes[0] == "transcreve take.wav", nomes
    assert "transcribe.py" not in _cmds(fb.fabrica(vsl, seco=True))


def test_caminho_do_plano_vale_de_qualquer_pasta(tmp: Path):
    """O reel do celular lia `fonte` e `transcript` da pasta de quem rodou o comando, não da do
    plano: de outra pasta, o --seco passava (o _confere procura nas duas) e o corte caía em
    FileNotFoundError. O editorial e o criativo já liam da pasta do plano; a regra é uma só."""
    video, outra = tmp / "video", tmp / "outra"
    video.mkdir()
    outra.mkdir()
    fonte = _fonte(video, "celular.mp4")
    _transcript(video, fonte)
    _fonte(video, "apoio.mp4", dur=2)
    planos = {"celular.json": {"estilo": "reel-camera", "slug": "celular", "fonte": "celular.mp4",
                               "transcript": "t.json", "saida": "saida",
                               "broll": [{"arquivo": "apoio.mp4", "em": 1.0, "dur": 1.0}]}}
    if not SEM_CRIATIVO:
        planos["criativo.json"] = {k: v for k, v in _criativo(video).items() if k != "_dir"}
    if fb.V2.exists():
        planos["editorial.json"] = {k: v for k, v in _reel_editorial(video).items() if k != "_dir"}
    for nome, plano in planos.items():
        pj = video / nome
        pj.write_text(json.dumps(plano, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, fb.__file__, str(pj), "--seco"], cwd=outra,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, f"{nome}: {r.stderr[-600:]}"
    seco = fb.fabrica({**planos["celular.json"], "_dir": str(video)}, seco=True)
    assert str(video / "apoio.mp4") in _cmds(seco), "o b-roll também sai da pasta do plano"


def test_reel_editorial_frase_do_youtube_confere_o_que_ouviu(tmp: Path):
    """A 1ª geração da frase do heygen-rosto disse "O link, o link tá na descrição" e passou
    verde. A que não diz a `fala` sai do caminho: com o fim-yt.wav no lugar, a fábrica montava com ela."""
    if not fb.V2.exists():
        return
    re_, r = _reel_de_verdade(tmp, youtube={"fala": "O link tá na descrição.", "chamada": ["o link tá", "NA DESCRIÇÃO"]})
    (tmp / "vozes").mkdir()
    gerada = _voz(tmp / "_trabalho", dur=1)
    desfaz = _troca(re_, _gera=lambda *a: gerada, _ultima_frase=lambda r: (1.0, 0.8, 2.0),
                    _ouve=lambda r, v: "O link, o link tá na descrição.")
    erro = ""
    try:
        re_.yt_voz(r)
    except SystemExit as e:
        erro = str(e)
    finally:
        desfaz()
    assert "não disse a fala" in erro and "o link" in erro, f"a repetição passou: {erro!r}"
    assert not r.fim_yt.exists() and list((tmp / "vozes").glob("*recusada.wav")), "a geração errada ficou no lugar"


def test_reel_editorial_ultima_frase_sem_ponto(tmp: Path):
    """O large-v3 pontuou a voz do heygen-rosto toda com vírgula, e o `yt` quebrava com
    IndexError. O tamanho da última frase sai da narração, que tem ponto."""
    if not fb.V2.exists():
        return
    re_, r = _reel_de_verdade(tmp, narracao="Oi, tudo bem. Comenta OI.")
    _ffmpeg("-f", "lavfi", "-i", "aevalsrc='0.5*sin(2*PI*220*t)*(between(t,0.2,1)+between(t,1.4,2.2)+between(t,2.6,3.4))'"
            ":s=48000:d=3.6", r.voz)
    ws = [("Oi,", 0.2, 0.5), ("tudo", 0.6, 1.0), ("bem,", 1.4, 2.2), ("Comenta", 2.6, 3.0), ("OI.", 3.0, 3.4)]
    r.transcript(r.voz).write_text(json.dumps({"words": [{"text": t, "start": a, "end": b} for t, a, b in ws]}), encoding="utf-8")
    ini, antes, fim = re_._ultima_frase(r)
    assert abs(ini - 2.6) < 0.05 and abs(antes - 2.2) < 0.05 and abs(fim - 3.4) < 0.05, (ini, antes, fim)


def _site(paginas: dict):
    """Um site local. /pendura nunca responde: é o analytics que não deixa a rede ficar ociosa."""
    import http.server
    import threading
    import time

    class Site(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/pendura":
                time.sleep(120)
                return
            tipo, corpo = paginas.get(self.path, ("text/plain", b""))
            self.send_response(200 if self.path in paginas else 404)
            self.send_header("Content-Type", tipo)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# a rolagem animada por script, como a da heygen.com: o scrollTo leva 1,5 s pra chegar
_PAGINA = b"""<html><head><style>html{scroll-behavior:smooth} body{margin:0;font:40px sans-serif}</style></head>
<body><header><a href="/"><img src="/_next/image?url=%2Flogo.png&w=256"></a></header>
<div style="height:9000px"></div><h2>Passo tres</h2><p>Escreva o roteiro e gere o video</p>
<div style="height:3000px"></div><script>fetch('/pendura');
const nat = window.scrollTo.bind(window);
window.scrollTo = (x, y) => { const de = scrollY, t0 = performance.now();
  const anda = t => { const u = Math.min(1, (t - t0) / 1500); nat(0, de + (y - de) * u); if (u < 1) requestAnimationFrame(anda); };
  requestAnimationFrame(anda); };</script></body></html>"""


def test_reel_editorial_captura_em_pagina_que_nao_para(tmp: Path):
    """Na heygen.com o `networkidle` nunca chega (estourava os 60 s), a rolagem é animada (o print
    saía no meio do caminho) e o logo do cabeçalho é um PNG, não o SVG que a captura procurava.
    E a captura que já existe não é refeita por cima."""
    if not fb.V2.exists():
        return
    import io
    from PIL import Image
    logo = Image.new("RGBA", (300, 80))
    logo.paste((20, 20, 20, 255), (10, 10, 290, 70))
    png = io.BytesIO()
    logo.save(png, "PNG")
    srv, url = _site({"/": ("text/html", _PAGINA), "/logo.png": ("image/png", png.getvalue())})
    try:
        re_, r = _reel_de_verdade(tmp, capturas={"logo": url + "/", "prints": {
            "passo": [url + "/", "Passo tres", 400, "Escreva o roteiro"], "velho": [url + "/", "x", 400, "x"]}})
        r.cap.mkdir(parents=True)
        (r.cap / "velho.png").write_bytes(b"feito antes")
        re_.captura(r)
    finally:
        srv.shutdown()
    foco = json.loads((r.cap / "focos.json").read_text(encoding="utf-8"))["passo"]
    assert 0 <= foco[1] <= 1 and foco[1] + foco[3] <= 1, f"o print saiu fora da frase (rolagem no meio): {foco}"
    branco = Image.open(r.cap / "logo_branco.png")
    assert branco.mode == "RGBA" and branco.getpixel((600, branco.height // 2)) == (255, 255, 255, 255), "o logo PNG não virou o logo branco"
    assert (r.cap / "velho.png").read_bytes() == b"feito antes", "a captura que existia foi refeita por cima"


def test_caminho_do_windows_nao_vira_deslocamento(tmp: Path):
    """No Windows o caminho da fala tem `D:`, e o cards_da_fala lia o resto como os segundos
    de deslocamento: todo primeiro vídeo quebrava no CI do Windows (12/10)."""
    import cards_da_fala as cf
    assert cf._spec(r"D:\a\fala.json") == (r"D:\a\fala.json", 0.0)
    assert cf._spec(r"D:\a\fala.json:12.5") == (r"D:\a\fala.json", 12.5)
    assert cf._spec("fala.json") == ("fala.json", 0.0)
    assert cf._spec("fala.json:3") == ("fala.json", 3.0)


def test_reel_editorial_converte_leva_o_que_o_plano_velho_tinha(tmp: Path):
    """O converte largava calado as `capturas` e o `corrige` do plano do heygen-rosto, e deixava
    o webm ainda não gerado com o caminho da raiz do repositório."""
    if not fb.V2.exists():
        return
    import contextlib
    import io
    import os
    re_ = fb._reel()
    webm = "videos/topo/nao-existe/avatar/rosto.webm"
    velho = {"dur": 3.0, "base": [{"de": 0, "ate": 3.0, "avatar": 0, "quadro": "cheio", "fundo": "xadrez"}],
             "avatar": {"arquivo": webm}, "trilha": {"faixa": "plantao-urgente", "pedacos": []}, "outra_coisa": 1,
             "capturas": {"_leia": "x", "gemeo": {"url": "https://a.b", "ancora": "A", "frase": "B"},
                          "vsl": {"arquivo": "v.mp4", "t": 1}},
             "corrige": {"Heijen": "HeyGen", "_leia": "x"}}
    plano = tmp / "velho" / "plano.json"
    plano.parent.mkdir()
    plano.write_text(json.dumps(velho), encoding="utf-8")
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        re_.converte(plano)
    novo, saida = json.loads(plano.with_name("reel.json").read_text(encoding="utf-8")), saida.getvalue()
    assert novo.get("capturas") == {"prints": {"gemeo": ["https://a.b", "A", 900, "B"]}}, novo.get("capturas")
    assert ["Heijen", "HeyGen"] in novo.get("junta", []), "o corrige sumiu"
    assert novo["base"][0]["fundo"] == "xadrez"
    try:
        esperado = os.path.relpath(re_.RAIZ / webm, plano.parent)
    except ValueError:      # Windows, outro disco: o converte grava o caminho inteiro
        esperado = str(re_.RAIZ / webm)
    assert novo["avatar"]["arquivo"] == esperado, novo["avatar"]["arquivo"]
    for dito in ("capturas.vsl", "outra_coisa", "corrige"):
        assert dito in saida, f"o converte não avisou de {dito}:\n{saida}"


def _mov(saida: Path, caixas: str, dur=2):
    """Uma peça com alfa: `caixas` são drawbox do ffmpeg sobre o transparente."""
    _ffmpeg("-f", "lavfi", "-i", f"color=c=black@0:s=1080x1920:r=30:d={dur},format=yuva444p,{caixas}",
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", saida)
    return saida


def test_reel_editorial_encaixe_mede_a_peca_inteira(tmp: Path):
    """O encaixe media o último quadro: o o_estados da ficha, com o último estado mais estreito,
    passava da borda; e a peça que sai não tinha caixa (TypeError em vez do nome da peça)."""
    if not fb.V2.exists():
        return
    re_, r = _reel_de_verdade(tmp)
    (r.trab / "pecas").mkdir(parents=True)
    larga_e_estreita = _mov(r.trab / "pecas" / "estados.mov",
                            "drawbox=x=140:y=900:w=800:h=100:color=white@1:t=fill:replace=1:enable='lt(t,1)',"
                            "drawbox=x=340:y=900:w=400:h=100:color=white@1:t=fill:replace=1:enable='gte(t,1)'")
    e, x, _ = re_.encaixe(r, {"nome": "estados", "caixa": [24, 800, 1056, 1200], "max": 3}, larga_e_estreita)
    assert x + 140 * e >= 24 - 2 and x + 940 * e <= 1056 + 2, f"o estado largo vaza da caixa: escala {e:.2f}, x {x}"
    vazia = _mov(r.trab / "pecas" / "sumiu.mov", "null")
    erro = ""
    try:
        re_.encaixe(r, {"nome": "sumiu", "caixa": [24, 800, 1056, 1200]}, vazia)
    except ValueError as ex:
        erro = str(ex)
    assert "sumiu" in erro, f"a peça sem desenho não disse o nome: {erro!r}"


def _webm_vazio(saida: Path):
    _ffmpeg("-f", "lavfi", "-i", "color=c=black@0:s=1080x1920:r=30:d=2,format=yuva420p",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", saida)


def test_reel_editorial_fundo_por_trecho(tmp: Path):
    """"Ele sai SEM FUNDO": o avatar recortado sobre o xadrez de transparência, não sobre o
    escritório. O estilo punha o escritório atrás de todo rosto e o plano não tinha como pedir."""
    if not fb.V2.exists():
        return
    base = [{"de": 0.0, "ate": 1.5, "avatar": 0.0, "quadro": "cartao"},
            {"de": 1.5, "ate": 3.0, "avatar": 1.5, "quadro": "cheio", "fundo": "xadrez"}]
    re_, r = _reel_de_verdade(tmp, base=base)
    _webm_vazio(tmp / "avatar" / "rosto.webm")
    mp4 = re_.trecho(r, r.p["base"][1], 1)
    png = tmp / "quadro.png"
    _ffmpeg("-i", mp4, "-frames:v", "1", png)
    from PIL import Image
    q = Image.open(png).convert("L")
    assert q.getpixel((30, 30)) > 240 and 190 < q.getpixel((90, 30)) < 220, (
        f"atrás do rosto não está o xadrez: {q.getpixel((30, 30))}, {q.getpixel((90, 30))}")


def test_reel_editorial_trechos_saem_iguais(tmp: Path):
    """O take é o concat por cópia dos trechos. Trecho de rosto saía com SAR indefinido e cor sem tag,
    trecho de cena com SAR 1:1 e bt709: no corte o ffmpeg reconfigura o grafo do compor, o
    setpts=PTS-STARTPTS da letra recomeça e a legenda fica 1,5 s adiantada da voz (site-vira-video,
    04/10). Todo trecho tem que sair com as mesmas propriedades de quadro."""
    if not fb.V2.exists():
        return
    cena = tmp / "cena.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2", "-vf", "setsar=1", "-color_range", "tv",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-pix_fmt", "yuv420p", cena)
    base = [{"de": 0.0, "ate": 1.5, "avatar": 0.0, "quadro": "cheio"},
            {"de": 1.5, "ate": 3.0, "cena": "cena.mp4"}]
    re_, r = _reel_de_verdade(tmp, base=base, r={"dur": 3.0, "cenas": [[0, 3.0, "rosto"]]})
    _webm_vazio(tmp / "avatar" / "rosto.webm")
    campos = "sample_aspect_ratio,color_range,color_space,color_primaries,color_transfer"
    props = [subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", f"stream={campos}",
                             "-of", "csv=p=0", str(re_.trecho(r, s, i))], capture_output=True, text=True,
                            encoding="utf-8").stdout.strip()
             for i, s in enumerate(r.p["base"])]
    assert len(set(props)) == 1, f"os trechos do take saem diferentes (rosto, cena): {props}"


def test_reel_editorial_alinha_o_webm_que_chegou_pronto(tmp: Path):
    """O aluno chega com a voz e o webm que ele mesmo gerou na HeyGen, sem o mapa do passo heygen
    (a prova QD3, 03/10: os dois agentes montaram a base com ffmpeg à mão). O webm tem uma pausa a
    mais e não tem a última frase: o `alinha` acha cada pedaço da voz no áudio dele, o take parte o
    rosto onde o webm salta, e a base que põe rosto na frase que o webm não tem é recusada."""
    if not fb.V2.exists():
        return
    import numpy as np
    sr, rng = 48000, np.random.default_rng(7)
    voz = np.zeros(3 * sr, np.float32)
    for a, b in ((0.2, 0.9), (1.1, 1.8), (2.0, 2.7)):      # três frases, cada uma um ruído diferente
        k = np.convolve(rng.standard_normal(round((b - a) * sr)), np.ones(12) / 12, "same")   # fala, não chiado
        voz[round(a * sr):round(a * sr) + len(k)] = 0.3 * k / np.abs(k).max()
    # o webm: até 1,0 s igual, 0,4 s de pausa a mais, a segunda frase, e a terceira a HeyGen não recebeu
    webm = np.concatenate([voz[:sr], np.zeros(round(0.4 * sr), np.float32), voz[sr:round(1.9 * sr)]])
    for nome, x in (("voz.raw", voz), ("webm.raw", webm)):
        (tmp / nome).write_bytes(x.tobytes())

    def material():      # o _reel_editorial escreve a voz e o webm de enfeite dele a cada chamada: os nossos vêm depois
        _ffmpeg("-f", "f32le", "-ar", sr, "-ac", 1, "-i", tmp / "voz.raw", tmp / "take.wav")
        _ffmpeg("-f", "lavfi", "-i", "color=c=black@0:s=108x192:r=30:d=2.3,format=yuva420p",
                "-f", "f32le", "-ar", sr, "-ac", 1, "-i", tmp / "webm.raw", "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p", "-c:a", "libopus", "-b:a", "128k", "-shortest", tmp / "avatar" / "rosto.webm")

    plano = _reel_editorial(tmp)
    material()
    avatar = {**plano["avatar"], "alinha": True}

    seco = fb.fabrica({**plano, "avatar": avatar}, seco=True)
    alinha = next(p for p in seco.passos if p.nome == "alinha")
    assert tmp / "avatar" / "rosto.webm" in alinha.entradas and tmp / "take.wav" in alinha.entradas, alinha.entradas
    assert alinha.saida in next(p for p in seco.passos if p.nome == "take").entradas, "o take não enxerga o mapa"

    re_, r = _reel_de_verdade(tmp, avatar=avatar)   # a base do exemplo põe rosto até 3,0 s
    material()
    try:
        re_.alinha(r)
        assert False, "a base pôs rosto na frase que o webm não tem e passou"
    except SystemExit as e:
        assert "onde o webm não tem" in str(e) and "1.9" in str(e) and "–3.00s" in str(e), e
    mapa = json.loads(Path(r.p["avatar"]["mapa"]).read_text(encoding="utf-8"))["trechos"]
    desvios = [round(m["gerado"][0] - m["fonte"][0], 2) for m in mapa]
    assert desvios == [0.0, 0.4], f"o webm está igual até 1,0 s e 0,4 s adiantado depois: {mapa}"
    assert abs(mapa[0]["fonte"][1] - 1.0) < 0.05 and abs(mapa[1]["fonte"][1] - 1.9) < 0.05, mapa

    base = [{"de": 0.0, "ate": 1.5, "avatar": 0.0, "quadro": "cartao"},
            {"de": 1.5, "ate": 1.85, "avatar": 0.0, "quadro": "cheio", "fundo": "xadrez"},
            {"de": 1.85, "ate": 3.0, "avatar": 0.0, "quadro": "cheio", "congela": True}]
    re_, r = _reel_de_verdade(tmp, avatar=avatar, base=base)
    material()
    re_.alinha(r)
    partes = [(p["de"], p["ate"]) for p in re_._partes(r)]
    assert partes[:2] == [(0.0, mapa[0]["fonte"][1]), (mapa[0]["fonte"][1], 1.5)], (
        f"o trecho que passa pela pausa a mais não se partiu: {partes}")
    assert abs(re_._no_webm(r, re_._partes(r)[1]) - (mapa[0]["fonte"][1] + 0.4)) < 0.05, "o rosto não pulou a pausa"


def test_reel_editorial_peca_sem_estilo_sai_no_claro(tmp: Path):
    """Quem monta o Reel por fora (videos/fabrica/monta.py) não passa o estilo: a costura da marca lia
    `r.est` e todo criativo com `pecas` caía em AttributeError (03/10). Sem estilo, o tema é o claro."""
    if not (Path(fb.__file__).parent / "reel_editorial.py").exists():
        return
    from types import SimpleNamespace
    import reel_editorial as re_
    assert re_._tema(SimpleNamespace()) == [], "sem `est`, a peça tem que sair no claro"
    assert re_._tema(SimpleNamespace(est={"tema": "claro"})) == []
    assert re_._tema(SimpleNamespace(est={"tema": "marca"})) == ["--tema", "marca"]


def test_reel_editorial_sem_trilha_quando_a_musica_e_do_app(tmp: Path):
    """O aluno que põe a música pelo app do Instagram (o caminho mais seguro no orgânico) não pode
    ser barrado pela trava da trilha: `trilha.faixa` "nenhuma" passa, e o som sai sem faixa."""
    if not fb.V2.exists():
        return
    plano = _reel_editorial(tmp, trilha={"faixa": "nenhuma"})
    som = next(p for p in fb.fabrica(plano, seco=True).passos if p.nome == "som")
    assert not [e for e in som.entradas if e.suffix in (".wav", ".m4a", ".mp3") and e.name != "take.wav"], som.entradas
    erro = None
    try:
        # sem clima também: com ele, a fábrica escolheria uma faixa do catálogo
        fb.fabrica(_reel_editorial(tmp, trilha={"clima": None}), seco=True)
    except ValueError as e:
        erro = str(e)
    assert erro and "nenhuma" in erro, f"sem faixa, a trava não diz como sair sem trilha: {erro}"


def test_reel_editorial_escolhe_a_trilha_pelo_clima(tmp: Path):
    """Em 03/10 doze planos da fábrica escreviam a mesma faixa à mão. Sem faixa, o estilo pede um
    clima e a fábrica escolhe no catálogo; o seco escolhe sem marcar a faixa como usada."""
    if not fb.V2.exists():
        return
    import mixa
    plano = _reel_editorial(tmp, trilha={})
    musica = tmp / "musica"
    musica.mkdir()
    (musica / "calma.wav").write_bytes((tmp / "faixa.wav").read_bytes())
    (musica / "catalogo.json").write_text(json.dumps({"faixas": [
        {"nome": "calma", "clima": "editorial", "arquivo": "calma.wav"}]}), encoding="utf-8")
    antes = mixa.MUSICA, mixa.USADAS
    mixa.MUSICA, mixa.USADAS = musica, musica / "usadas.json"
    try:
        seco = fb.fabrica(plano, seco=True)
    finally:
        mixa.MUSICA, mixa.USADAS = antes
    assert json.loads(_arquivo(seco)[1])["trilha"]["faixa"] == str(musica / "calma.wav")
    assert not (musica / "usadas.json").exists(), "o seco marcou a faixa como usada"


def _com_painel(tmp: Path, **extra) -> dict:
    """Um reel com tela cheia de 1,5 a 3,0 s e uma captura na largura toda."""
    return dict(base=[{"de": 0.0, "ate": 1.5, "avatar": 0.0, "quadro": "cartao"}, {"de": 1.5, "ate": 3.0, "painel": "tinta"}],
                r={"dur": 3.0, "cenas": [[0, 1.5, "split", "tinta"], [1.5, 3.0, "tela", "tinta"]],
                   "vozes": [{"t": 2.0, "ate": 3.0, "chamada": ["comenta", "“OI”"]}]},
                pecas=[{"nome": "gancho", "peca": "g_gancho", "em": 0, "ate": 1.5, "caixa": [60, 440, 1020, 720], "q": {}},
                       {"nome": "cap", "peca": "r_print", "em": 1.5, "ate": 3.0, "caixa": [24, 110, 1056, 1318], "q": {}}],
                **extra)


def test_reel_editorial_trava_mede_a_tela_vazia(tmp: Path):
    """A trava de 30/09 contava peça na largura toda e deixou passar os chips pequenos com a
    metade de baixo vazia (heygen-rosto, 11,5–13,5 s). Agora ela mede o render."""
    if not fb.V2.exists():
        return
    re_, r = _reel_de_verdade(tmp, **_com_painel(tmp))
    from PIL import Image
    Image.new("RGB", (1080, 1920), (11, 13, 18)).save(r.trab / "painel_tinta.png")
    vazio, cheio = tmp / "vazio.mp4", tmp / "cheio.mp4"
    for saida, vf in ((vazio, "null"), (cheio, "drawbox=x=24:y=110:w=1032:h=1208:color=white:t=fill")):
        _ffmpeg("-loop", "1", "-framerate", "30", "-t", "3", "-i", r.trab / "painel_tinta.png", "-vf", vf,
                "-pix_fmt", "yuv420p", saida)
    erros = re_.vazios(r, vazio)
    assert len(erros) == 1 and "1.50–3.00" in erros[0], erros
    assert re_.vazios(r, cheio) == [], "a captura na tela toda reprovou"


def test_reel_editorial_seco_avisa_a_tela_vazia(tmp: Path):
    """O seco não vê o render, mas vê as caixas: se nem cheias elas enchem a tela, ele avisa."""
    if not fb.V2.exists():
        return
    import contextlib
    import io
    plano = _reel_editorial(tmp, **_com_painel(tmp))
    plano["pecas"][1]["caixa"] = [24, 110, 1056, 600]
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        fb.fabrica(plano, seco=True)
    assert "aviso: tela cheia 1.50–3.00" in saida.getvalue(), saida.getvalue()


def test_reel_editorial_degraus_e_fechos(tmp: Path):
    """O bruto que vira editado: o mesmo take com 0, 1… N skills, montado nas trocas, e um final por
    fecho dito no mesmo áudio. No seco: o passo dos degraus entre a junta e o som, e o confere
    recusa skill que não existe e troca faltando."""
    if not fb.V2.exists():
        return
    hud = {"nome": "placar", "peca": "g_pedidos", "em": 0, "ate": 3.0, "q": {"pedidos": "oi|ritmo|0.1|0.5"}}
    extra = {"degraus": {"ordem": ["ritmo", "legendas"], "trocas": [0.5, "Oi"], "ate": 1.4, "hud": ["placar"]},
             "fechos": {"a": [2.0, 2.5], "b": [2.5, 3.0]}}
    plano = _reel_editorial(tmp, **extra)
    plano["pecas"].append(hud)
    plano["r"]["vozes"] = [{"t": 2.5, "ate": 3.0, "chamada": ["comenta", "“OI”"]}]
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes[nomes.index("junta") + 1:nomes.index("som")] == ["degraus"], nomes
    e = fb.es.estilo("reel-editorial")
    entregas = [d.name for _, d in fb._entregas(plano, e, seco.final, tmp / "_trabalho")]
    assert entregas == ["novo.mp4", "novo-a.mp4", "novo-b.mp4"], entregas
    for chave, valor, motivo in (("ordem", ["ritmo", "cor"], "as skills são"), ("trocas", [0.5], "uma troca por skill"),
                                 ("hud", ["nada"], "não está nas `pecas`"), ("ate", 2.5, "não tem rosto")):
        ruim = json.loads(json.dumps(plano))
        ruim["degraus"][chave] = valor
        if chave == "ate":
            ruim["base"][1] = {"de": 1.5, "ate": 3.0, "painel": "tinta"}
        try:
            fb.fabrica(ruim, seco=True)
            raise AssertionError(f"degraus.{chave}={valor} passou")
        except ValueError as ex:
            assert motivo in str(ex), ex


def test_degrau_desliga_o_que_a_skill_faz(tmp: Path):
    """Cada skill desligada tira do plano o que ela faz, e nada mais."""
    if not (Path(fb.__file__).parent / "reel_editorial.py").exists():
        return  # o kit de aulas não leva o reel editorial
    import reel_editorial as re_
    p = {"dur": 10.0, "degraus": {"hud": ["placar"]}, "fechos": {"a": [8, 9]}, "sons": [{"tipo": "pop", "t": 1}],
         "base": [{"de": 0.0, "ate": 4.0, "avatar": 0.0, "quadro": "cheio"},
                  {"de": 4.0, "ate": 10.0, "avatar": 4.0, "quadro": "cartao"}],
         "r": {"dur": 10.0, "cenas": [[0, 4, "rosto", "claro", 1.1], [4, 10, "split", "tinta"]],
               "graficos": [{"t": 4.5, "ate": 9, "g": "mascote"}], "vozes": [{"t": 1, "ate": 2, "rotulo": "x"}]},
         "pecas": [{"nome": "placar", "em": 0}, {"nome": "carimbo", "em": 5}, {"nome": "tarde", "em": 7}],
         "imagens": []}
    nada = re_.degrau(p, set(re_.SKILLS), 6.0, [0.0, 2.0, 4.5])
    assert nada["base"] == [{"de": 0.0, "ate": 6.0, "avatar": 0.0, "quadro": "cheio"}], nada["base"]
    assert nada["r"]["cenas"] == [[0.0, 6.0, "rosto"]] and nada["r"]["graficos"] == [], nada["r"]
    assert nada["_sem_fala"] and nada["r"]["vozes"] == [] and nada["pecas"] == [], nada
    assert "fechos" not in nada and "sons" not in nada and nada["dur"] == nada["r"]["dur"] == 6.0
    ritmo = re_.degrau(p, set(re_.SKILLS) - {"ritmo"}, 6.0, [0.0, 2.0, 4.5])
    assert ritmo["r"]["cenas"] == [[0.0, 2.0, "rosto"], [2.0, 4.5, "rosto", "claro", 1.12], [4.5, 6.0, "rosto"]], ritmo["r"]
    quase = re_.degrau(p, {"estilo"}, 6.0, [0.0])
    assert quase["r"]["cenas"] == [[0, 4, "rosto", "claro", 1.1], [4, 6.0, "split", "claro"]], quase["r"]["cenas"]
    assert [x["nome"] for x in quase["pecas"]] == ["carimbo"], "o placar é do hud, e a peça de 7 s fica fora"
    assert quase["base"][1] == {"de": 4.0, "ate": 6.0, "avatar": 4.0, "quadro": "cartao"}, quase["base"]
    assert "_sem_fala" not in quase and quase["r"]["vozes"] == [{"t": 1, "ate": 2, "rotulo": "x"}]
    # o cenário gerado atrás do rosto e a capa que congela: tirados, o rosto volta inteiro pro escritório
    p["base"] = [{"de": 0.0, "ate": 2.0, "avatar": 0.0, "quadro": "cheio"},
                 {"de": 2.0, "ate": 4.0, "avatar": 2.0, "quadro": "cheio", "fundo": "@fabrica.mp4"},
                 {"de": 4.0, "ate": 5.0, "avatar": 4.0, "quadro": "cheio", "congela": True},
                 {"de": 5.0, "ate": 10.0, "avatar": 5.0, "quadro": "cheio", "fundo": "xadrez"}]
    p["pecas"].append({"nome": "titulo", "em": 4.0, "camada": "capa"})
    cru = re_.degrau(p, {"cenarios", "capa"}, 6.0, [0.0])
    assert cru["base"] == [{"de": 0.0, "ate": 5.0, "avatar": 0.0, "quadro": "cheio"},
                           {"de": 5.0, "ate": 6.0, "avatar": 5.0, "quadro": "cheio", "fundo": "xadrez"}], cru["base"]
    assert "titulo" not in [x["nome"] for x in cru["pecas"]], "a peça da capa sai com a capa"
    assert re_.degrau(p, {"capa"}, 6.0, [0.0])["base"][1]["fundo"] == "@fabrica.mp4", "o cenário fica sem a capa"
    inicios = [0.1, 1.0, 2.0]
    assert re_._na_frase(inicios, 0.95, 2.5) == 1.0 and re_._na_frase(inicios, 0.7, 2.5) == 1.0, (
        "o fecho que começa no silêncio, ou no rabo da frase anterior, abre com ela na tela")
    assert re_._na_frase(inicios, 1.3, 2.5) == 1.0, "o fecho que começa no meio da primeira palavra volta pro começo dela"


def test_degrau_sem_capa_toca_o_buraco_do_mapa(tmp: Path):
    """O degrau sem capa tira o `congela` que cobria o buraco do mapa (a voz que a HeyGen não recebeu,
    12,52–12,7 s no Linha do Tempo) e junta o rosto num trecho só; o _partes corta nas bordas do mapa,
    e o pedaço do buraco não tinha onde tocar no webm: o degrau quebrava (04/10). No buraco o webm segue
    de onde o trecho anterior parou; depois dele, volta ao mapa."""
    if not (Path(fb.__file__).parent / "reel_editorial.py").exists():
        return
    from types import SimpleNamespace
    import reel_editorial as re_
    mapa = tmp / "mapa.json"
    mapa.write_text(json.dumps({"trechos": [{"fonte": [0.0, 2.5], "gerado": [0.0, 2.5]},
                                            {"fonte": [2.7, 5.0], "gerado": [2.6, 4.9]}]}), encoding="utf-8")
    p = {"dur": 5.0, "degraus": {}, "avatar": {"arquivo": "rosto.webm", "mapa": str(mapa)},
         "base": [{"de": 0.0, "ate": 2.3, "avatar": 0.0, "quadro": "cheio"},
                  {"de": 2.3, "ate": 2.9, "avatar": 2.3, "quadro": "cheio", "congela": True},
                  {"de": 2.9, "ate": 5.0, "avatar": 2.9, "quadro": "cheio"}],
         "r": {"dur": 5.0, "cenas": [[0, 5, "rosto"]]}, "pecas": [], "imagens": []}
    r = SimpleNamespace(p=re_.degrau(p, {"capa"}, 5.0, [0.0]), rel=Path)
    partes = re_._partes(r)
    assert [(x["de"], x["ate"]) for x in partes] == [(0.0, 2.5), (2.5, 2.7), (2.7, 5.0)], partes
    assert [round(re_._no_webm(r, x), 3) for x in partes] == [0.0, 2.5, 2.6], "o rosto no buraco não seguiu o webm"
    try:
        re_._no_webm(r, {"de": 5.2, "ate": 6.0})
        raise AssertionError("o rosto depois do fim do mapa passou")
    except ValueError:
        pass
    assert re_._na_frase([0.1], 1.5, 1.8) == 1.5, "sem começo de frase perto, fica"
    falas = [["Tira", 0.1, 0.3], ["as", 0.3, 0.4], ["pausas.", 0.4, 0.9], ["Põe", 1.0, 1.2], ["pausas", 2.0, 2.4]]
    assert re_.ancora("pausas", falas) == 0.9 and re_.ancora("pausas", falas, 0.9) == 2.4 and re_.ancora(3, falas) == 3.0
    assert re_.frases(falas) == [0.1, 1.0], re_.frases(falas)


# ---- corrida ----------------------------------------------------------------


# ---- o criativo ---------------------------------------------------------------

# O kit de aulas não leva o criativo nem o acabamento de filmagem achada; a Fábrica, só com o módulo Cenas de Cinema.
SEM_CRIATIVO = not (Path(fb.__file__).parent / "criativo.py").exists()


def _criativo(tmp: Path, **extra) -> dict:
    """Um criativo mínimo: um banco de duas cenas, a voz e a transcrição dela, e uma trilha.
    Nada aqui é do banco dos ninjas: o estilo serve a qualquer banco."""
    banco = tmp / "banco"
    (banco / "cenas").mkdir(parents=True, exist_ok=True)
    for nome in ("porta", "mesa"):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", "testsrc=size=360x640:rate=30:duration=2.5", "-pix_fmt", "yuv420p",
                        str(banco / "cenas" / f"{nome}.mp4")], check=True)
    (banco / "cenas.json").write_text(json.dumps([
        {"id": "porta", "arquivo": "cenas/porta.mp4", "acabamento": "cctv", "janela": [0.2, 2.0],
         "hora": "03:00:00", "cam": "03"},
        {"id": "mesa", "arquivo": "cenas/mesa.mp4", "acabamento": "celular", "janela": [0.3, 2.4],
         "hora": "09:15:00"}]), encoding="utf-8")
    voz = _voz(tmp, dur=3)
    (tmp / "transcripts").mkdir(exist_ok=True)
    (tmp / "transcripts" / f"{voz.stem}.json").write_text(json.dumps({"words": [
        {"text": t, "start": a, "end": b, "type": "word"}
        for t, a, b in (("Oi", 0.2, 0.5), ("gente", 0.5, 0.9), ("tudo", 1.5, 1.8), ("bem", 1.8, 2.2))]}), encoding="utf-8")
    faixa = tmp / "faixa.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                    str(faixa)], check=True)
    plano = {"estilo": "criativo", "slug": "porta", "projeto": "provas", "fonte": voz.name,
             "_dir": str(tmp), "saida": str(tmp / "saida"), "trabalho": "_trabalho", "banco": "banco",
             "locutor": {"id": "voz-de-teste", "ajustes": {"stability": 0.5}},
             "trechos": [["Oi, gente.", "porta"], ["Tudo bem?", "mesa"]],
             "trilha": {"faixa": str(faixa)}}
    plano.update(extra)
    return plano


def test_criativo_monta_pelo_helper(tmp: Path):
    """O criativo morou meses num monta_criativo.py fora da fábrica: sem modo seco, sem teste.
    Agora é estilo, e o seco lista a cadeia inteira."""
    if SEM_CRIATIVO:
        return
    seco = fb.fabrica(_criativo(tmp), seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes == ["transcreve take.wav", "base", "cards", "legenda", "fecho com trilha"], nomes
    assert seco.final == (tmp / "saida" / "provas" / "porta.mp4").resolve(), seco.final
    assert not seco.mudos, f"a legenda do criativo sai dos trechos, não da transcrição: {seco.mudos}"
    est = json.loads(_arquivo(seco)[1])["_estilo"]
    assert est["layout"] == "faixa_criativo" and est["ritmo"] == [0.167, 0.033], est
    if fb.V2.exists():
        assert est["acento"] == fb._v2().token("mk"), f"o destaque é o amarelo do marcador: {est['acento']}"
    mixa = seco.passos[-1].cmd
    assert mixa[-6:] == ["--cama", "-20.0", "--duck-ratio", "1.5", "--fade-fim", "0.3"], mixa
    reel = fb.fabrica(_criativo(tmp, estilo="criativo-reel"), seco=True)
    assert json.loads(_arquivo(reel)[1])["_estilo"]["layout"] == "faixa"
    assert reel.passos[-1].cmd[-1] == "1.2", "o Reels sai devagar no fim"
    # sem legenda, o criativo termina na base
    sem = fb.fabrica(_criativo(tmp, recursos={"-": ["legenda"]}), seco=True)
    assert [p.nome for p in sem.passos] == ["transcreve take.wav", "base", "fecho com trilha"], sem.passos
    # o --desde vale aqui também
    desenho = fb.fabrica(_criativo(tmp), seco=True, desde="desenho")
    # a transcrição não é etapa: é o material, e segue a voz em qualquer --desde
    assert [p.nome for p in desenho.passos] == ["transcreve take.wav", "cards", "legenda", "fecho com trilha"], \
        desenho.passos


def test_criativo_nao_gasta_sozinho(tmp: Path):
    """A voz custa caracteres na ElevenLabs: faltando, vira passo que cobra, impresso com `$`, e a
    cadeia para ali — nem a execução chama a API."""
    if SEM_CRIATIVO:
        return
    import contextlib
    import io
    plano = _criativo(tmp)
    (tmp / plano["fonte"]).unlink()
    seco = fb.fabrica(plano, seco=True)
    assert [(p.nome, p.cobra) for p in seco.passos] == [("narração", "ElevenLabs")], seco.passos
    tela = io.StringIO()
    with contextlib.redirect_stdout(tela):
        seco.imprime()
    assert " $ narração" in tela.getvalue() and "criativo.py voz" in tela.getvalue(), tela.getvalue()
    with contextlib.redirect_stdout(io.StringIO()):
        fb.fabrica(plano)
    assert not (tmp / plano["fonte"]).exists(), "a fábrica gerou a voz sozinha"
    # sem a voz e sem quem a leia, recusa na entrada
    sem_locutor = {k: v for k, v in plano.items() if k != "locutor"}
    try:
        fb.fabrica(sem_locutor, seco=True)
        raise AssertionError("criativo sem voz e sem locutor passou")
    except ValueError as erro:
        assert "locutor" in str(erro), erro


def test_criativo_recusa_cena_que_o_banco_nao_tem(tmp: Path):
    """Cena fora do banco ou com acabamento que não existe estourava no meio da montagem."""
    if SEM_CRIATIVO:
        return
    for trechos, dito in (([["Oi.", "porta"], ["Tchau.", "jardim"]], "cena fora do banco: jardim"),
                          ([["Oi.", "porta", "vhs"]], "acabamento 'vhs'"),
                          ([["Oi.", "porta", {"acabamento": "filmadora", "data": "27/09/2026"}]],
                           "data '27/09/2026'")):
        try:
            fb.fabrica(_criativo(tmp, trechos=trechos), seco=True)
            raise AssertionError(f"passou: {trechos}")
        except ValueError as erro:
            assert dito in str(erro), erro


def test_criativo_legenda_sai_do_roteiro(tmp: Path):
    """A voz lê o roteiro: o texto e a pontuação vêm dele, e do Whisper só a hora (era o
    _autoteste do monta_criativo)."""
    if SEM_CRIATIVO:
        return
    import criativo as cr
    ouv = [{"text": t, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, t in enumerate(
        "Enquanto você né assiste isso tem os carrocés e reclama do ar condicionado. Toca".split())]
    rot = [("Enquanto você assiste isso, tem os carrosséis", "a"), ("e reclama do ar-condicionado!", "b"),
           ("Toca aqui.", "c")]
    al = cr.palavras_do_roteiro(rot, ouv)
    assert [w["text"] for w in al] == " ".join(t for t, _ in rot).split(), [w["text"] for w in al]  # "né" some
    assert al[3]["text"] == "isso," and al[3]["start"] == 2.0                  # a pontuação vem do roteiro
    assert al[6]["text"] == "carrosséis" and al[6]["start"] == 3.5             # trocada, no tempo dela
    assert (al[10]["start"], al[10]["end"]) == (5.5, 6.4)                      # "ar" + "condicionado." viram uma
    assert (al[11]["start"], al[12]["start"], al[12]["end"]) == (6.5, 6.7, 6.9)  # "aqui." engolida: divide com "Toca"


def test_criativo_de_ponta_a_ponta(tmp: Path):
    """Banco, voz e trilha de mentira, o render de verdade: cada cena no trecho dela, a duração é
    a da voz mais a cauda, e a segunda corrida não refaz nada."""
    if SEM_CRIATIVO:
        return
    import contextlib
    import io
    import criativo as cr
    # ponytail: sem a legenda, que é o captions_viral e tem os testes dele; os cards entram no seco
    plano = _criativo(tmp, recursos={"-": ["legenda"]})
    with contextlib.redirect_stdout(io.StringIO()):
        final = fb.fabrica(plano)
    esperado = ff.dur(tmp / plano["fonte"]) + cr.CAUDA
    assert abs(ff.dur(final) - esperado) <= 1 / 30 + 0.03, (ff.dur(final), esperado)
    # o acabamento fica guardado no banco, com o aparelho, a hora e a câmera no nome (o fim é a impressão
    # do acabamento e da taxa: desde 04/10 a cena de 24 qps chega a 30 misturando quadros)
    acabadas = sorted(p.name for p in (tmp / "banco" / "acabadas").iterdir())
    assert [a.split("--")[:4] for a in acabadas] == [["mesa", "celular", "091500", "7d8155.mp4"],
                                                     ["porta", "cctv", "030000", "cam03"]], acabadas
    seco = fb.fabrica(plano, seco=True)
    # a transcrição de quatro palavras fica abaixo do piso da impressão (1 KB) e o passo roda de
    # novo, mas o transcribe.py devolve a do disco: a voz não é mais nova que ela
    assert all(p.pulavel for p in seco.passos if not p.nome.startswith("transcreve")), \
        [p.nome for p in seco.passos if not p.pulavel]
    # os cards do roteiro, com o layout do estilo e a vírgula do texto
    doc = json.loads(_arquivo(seco)[1])
    cr.cards({**doc, "punch": ["bem"]}, tmp / "_trabalho")
    legenda = json.loads((tmp / "_trabalho" / "legenda.json").read_text(encoding="utf-8"))
    palavras = [w["tx"] for c in legenda["cards"] for w in c["words"]]
    assert {c["layout"] for c in legenda["cards"]} == {"faixa_criativo"}, legenda["cards"]
    assert [p.strip(",.?").upper() for p in palavras] == ["OI", "GENTE", "TUDO", "BEM"], palavras


def test_filmadora_escreve_a_data_da_ficha(tmp: Path):
    """A filmadora escrevia "SET 27 2026", a data do dono, em toda cena. A data vem do trecho ou
    da ficha, sem ela é a de hoje, e a cena de outro dia é outra cena no banco."""
    if SEM_CRIATIVO:
        return
    from datetime import date
    import criativo as cr
    import filmagem_achada as fa
    assert fa.selo("2026-09-27") == "SET 27 2026" and fa.selo() == fa.selo(date.today().isoformat())
    feitas, velha = [], cr.acabar
    cr.acabar = lambda *a: feitas.append(a[-1])
    try:
        ficha = {"porta": {"arquivo": "cenas/porta.mp4", "data": "2026-09-27"}}
        nomes = [cr.cena("porta", ficha, tmp, acabamento="filmadora")[0].name,
                 cr.cena("porta", ficha, tmp, acabamento="filmadora", data="1987-05-02")[0].name,
                 cr.cena("porta", {"porta": {"arquivo": "cenas/porta.mp4"}}, tmp, acabamento="filmadora")[0].name,
                 cr.cena("porta", ficha, tmp, acabamento="cctv")[0].name]
    finally:
        cr.acabar = velha
    hoje = date.today().isoformat()
    assert feitas == ["2026-09-27", "1987-05-02", hoje, "2026-09-27"], feitas
    assert [n.split("--")[3] for n in nomes[:3]] == ["20260927", "19870502", hoje.replace("-", "")], nomes
    assert "2026" not in nomes[3], f"só a filmadora escreve a data: {nomes[3]}"


def test_selo_da_camera_sem_a_fonte_do_mac(tmp: Path):
    """Menlo e Arial Bold só existem no Mac: fora dele o selo cai na fonte livre e avisa, em vez
    de dar OSError na primeira cena."""
    if SEM_CRIATIVO:
        return
    import contextlib
    import io
    import filmagem_achada as fa
    velhas = fa.FONTE, fa.NEGRITO
    fa.FONTE, fa.NEGRITO = (("/nao/existe/Menlo.ttc",) + velhas[0][1:]), (("/nao/existe/Arial.ttf",) + velhas[1][1:])
    aviso = io.StringIO()
    try:
        with contextlib.redirect_stderr(aviso):
            for tipo in ("cctv", "telejornal"):
                (tmp / tipo).mkdir()
                fa.rotulo(tipo, "03:00:00", "02", 0.1, tmp / tipo)
                assert (tmp / tipo / "r_00000.png").exists(), tipo
    finally:
        fa.FONTE, fa.NEGRITO = velhas
    assert fa.FONTE[1].exists(), f"a mono livre não viajou junto: {fa.FONTE[1]}"
    assert "IBMPlexMono" in aviso.getvalue() and "Montserrat" in aviso.getvalue(), aviso.getvalue()


def test_blocos_correm_juntos_e_quem_le_espera(tmp: Path):
    """Dois blocos independentes rodam ao mesmo tempo; o passo que lê a saída de outro espera ele.
    No longo do semanal, um ajuste em dois blocos refazia um depois do outro.
    Cada passo anota quando começou e acabou, e o teste confere que o a e o c se sobrepõem. Um
    cronômetro no total (< 1,1 s) travou a conferência de dois alunos do Windows em 10/2026: lá
    abrir o Python demora mais, e o total passava sem nada estar errado."""
    def passo(nome, saida, le=None, dorme=0.0):
        cod = (f"import time,pathlib;t0=time.time();time.sleep({dorme});"
               + (f"t=pathlib.Path({str(le)!r}).read_text(encoding='utf-8')[:1];" if le else "t='';")
               # o cache recusa arquivo menor que o piso: render pela metade
               + f"pathlib.Path({str(saida)!r}).write_text(t+{nome!r}+' %r %r'%(t0,time.time())"
               + f"+' '*{fb.impressao.PISO_BYTES},encoding='utf-8')")
        return fb.Passo(nome, [fb.PY, "-c", cod, *([str(le)] if le else [])], saida)
    a, b, c = tmp / "a.txt", tmp / "b.txt", tmp / "c.txt"
    # na ordem da cadeia, o b (que lê o a) vem antes do c: o c não pode ficar na fila atrás dele
    cmds = [passo("a", a, dorme=1.0), passo("b", b, le=a), passo("c", c, dorme=1.0)]
    assert fb._dependencias(cmds) == [set(), {0}, set()], fb._dependencias(cmds)
    assert fb._executa(cmds, sem_cache=True, paralelo=2) == []
    (a0, a1), (c0, c1) = ([float(x) for x in p.read_text(encoding="utf-8").split()[1:3]] for p in (a, c))
    assert c0 < a1 and a0 < c1, f"os dois blocos não correram juntos: a {a0:.2f}–{a1:.2f}, c {c0:.2f}–{c1:.2f}"
    lido = b.read_text(encoding="utf-8")
    assert lido.startswith("ab"), f"o passo leu antes da entrada ficar pronta: {lido[:3]!r}"
    assert fb._executa(cmds, sem_cache=False, paralelo=2) == ["a", "b", "c"], "o cache não pulou"


def test_pecas_da_cadeia_vao_num_lote_so(tmp: Path):
    """As peças que faltam saem num `v2.py lote` só (um navegador pro vídeo inteiro, não um por
    peça); quem lê a peça espera o lote, e a peça pronta no cache fica de fora dele."""
    feitos = []
    velho = fb.ff.run

    def roda(cmd, **kw):
        feitos.append(cmd)
        if "lote" in cmd:
            for args in json.loads(Path(cmd[-1]).read_text(encoding="utf-8")):
                Path(args[args.index("--out") + 1]).write_bytes(b"x" * fb.impressao.PISO_BYTES)
        else:
            Path(cmd[-1]).write_bytes(Path(cmd[-2]).read_bytes() + b"y")

    def peca(nome):
        saida = tmp / "pecas" / f"{nome}.mov"        # a pasta ainda não existe, como no vídeo novo
        return fb.Passo(f"peça {nome}", [fb.PY, str(fb.V2 / "v2.py"), "render", "el_rabisco", f"tipo={nome}",
                                         "--out", str(saida)], saida)
    a, b = peca("a"), peca("b")
    le = fb.Passo("legenda", ["cat", str(a.saida), str(tmp / "leg.mp4")], tmp / "leg.mp4")
    fb.ff.run = roda
    try:
        assert fb._executa([a, b, le], sem_cache=False, paralelo=2) == []
        lotes = [c for c in feitos if "lote" in c]
        assert len(lotes) == 1 and not [c for c in feitos if "render" in c], feitos
        assert feitos[-1] is le.cmd, "a legenda rodou antes do lote"
        feitos.clear()
        b.saida.unlink()
        assert fb._executa([a, b, le], sem_cache=False, paralelo=2) == ["peça a", "legenda"]
        assert len(feitos) == 1 and "lote" in feitos[0], feitos
    finally:
        fb.ff.run = velho


def test_mexer_na_camera_refaz_a_legenda(tmp: Path):
    """A câmera e a análise de cena saíram do captions_viral pra módulos próprios: a impressão da
    legenda lê os dois, senão conserto na câmera não refazia legenda nenhuma."""
    passo = fb.Passo("legenda", [fb.PY, str(fb.AQUI / "captions_viral.py"), "x.mp4"], tmp / "l.mp4")
    nomes = {p.name for p in fb._helpers(passo)}
    assert {"captions_viral.py", "camera.py", "cena.py"} <= nomes, nomes


def test_proxy_uma_vez_por_bruto_e_o_recorte_fica_no_original(tmp: Path):
    """`imagem.proxy`: os blocos leem uma cópia do bruto na altura da saída, feita uma vez por
    bruto; o bloco com `recorte` (em pixel do bruto) continua no original."""
    if not fb.V2.exists() or not ff.tem_videotoolbox():
        return  # o kit não leva tools/v2; e sem o hardware do Mac não há proxy
    fonte = _fonte(tmp, "bruto.mp4", dur=4)
    plano = {"estilo": "lorcana-longo", "slug": "p", "projeto": "provas",
             "saida": str(tmp / "saida"), "fonte": str(fonte),
             "imagem": {"altura": 200, "proxy": True},
             "blocos": [{"nome": "a", "janelas": [[0, 1]], "mudo": True},
                        {"nome": "b", "janelas": [[2, 3]], "mudo": True},
                        {"nome": "c", "janelas": [[1, 2]], "mudo": True, "recorte": "crop=225:400:200:0"}]}
    seco = fb.fabrica(plano, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes.count("proxy de bruto.mp4") == 1, nomes
    proxy = _passo(seco, "proxy de").saida
    for b, fonte_dele in (("a", proxy), ("b", proxy), ("c", fonte)):
        edl = json.loads(_passo(seco, f"{b}: recorte").arquivo[1])
        assert edl["sources"]["bruto"] == str(fonte_dele), f"{b} leu {edl['sources']}"
    assert nomes.index("proxy de bruto.mp4") < nomes.index("a: recorte"), nomes
    sem = fb.fabrica({**plano, "imagem": {"altura": 400, "proxy": True}}, seco=True)
    assert not any("proxy" in p.nome for p in sem.passos), "fez proxy de bruto que já cabe na saída"


def test_codificador_de_hardware_refaz_o_cache(tmp: Path):
    """Trocar o `imagem.codificador` muda todo encode sem mudar comando nenhum: a escolha entra
    na impressão, senão o cache entregaria o vídeo do outro codificador."""
    import os
    p = fb.Passo("x", ["ffmpeg", "-i", "a.mp4", "b.mp4"], tmp / "b.mp4")
    try:
        os.environ[ff.HARDWARE] = "0"
        x264 = fb._digital(p)
        os.environ[ff.HARDWARE] = "1"
        hw = fb._digital(p)
        assert hw != x264, "o cache não vê o codificador"
        os.environ[ff.HARDWARE] = "auto"
        assert fb._digital(p) not in (x264, hw), "o cache não separa o auto"
    finally:
        os.environ[ff.HARDWARE] = "0"


def test_estilo_pede_o_codificador_auto_por_padrao(tmp: Path):
    """O estilo base pede `auto` (hardware só nos degraus intermediários) e a fábrica passa a
    escolha adiante tal como veio; `hardware` continua sendo `1`."""
    import os
    es = fb.es
    assert es.estilo("reel-camera").eixos["imagem"]["codificador"] == "auto"
    assert fb._modo_hardware("auto") == "auto"
    assert fb._modo_hardware("hardware") == "1"
    assert fb._modo_hardware("x264") == "0"


# ---- o plano mínimo e o bruto do celular ------------------------------------

def _iphone(dir_: Path, nome="meu vídeo ação.mov", hevc=True, vfr=True, giro=90, dur=2) -> Path:
    """Imita o iPhone: HEVC, taxa variável (quadros que faltam), giro nos metadados."""
    base = dir_ / "_base.mp4"
    filtro = ["-vf", "select='gt(abs(mod(n,5)-3),0)'", "-fps_mode", "vfr"] if vfr else []
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc=size=640x400:rate=30:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}", *filtro,
                    "-c:v", "libx265" if hevc else "libx264", "-tag:v", "hvc1" if hevc else "avc1",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(base)], check=True)
    saida = dir_ / nome
    subprocess.run(["ffmpeg", "-y", "-v", "error", *(["-display_rotation", str(giro)] if giro else []),
                    "-i", str(base), "-c", "copy", str(saida)], check=True)
    return saida


def test_plano_minimo_so_com_o_bruto(tmp: Path):
    fonte = _fonte(tmp, "meu vídeo.mp4")
    seco = fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True)
    assert seco.estilo.nome == "reel-camera", seco.estilo.nome
    nomes = [p.nome for p in seco.passos]
    assert any(n.startswith("transcreve") for n in nomes), nomes
    assert "render" in nomes and nomes.index("render") > [n.startswith("transcreve") for n in nomes].index(True)
    assert seco.final.stem == "meu-video", seco.final


def test_bruto_de_celular_ganha_o_passo_de_normalizar(tmp: Path):
    cel = _iphone(tmp)
    seco = fb.fabrica({"fonte": str(cel)}, seco=True)
    nomes = [p.nome for p in seco.passos]
    assert nomes[0].startswith("normaliza"), nomes
    assert nomes.index("render") > 0
    limpo = fb.fabrica({"fonte": str(_fonte(tmp, "limpo.mp4"))}, seco=True)
    assert not any(p.nome.startswith("normaliza") for p in limpo.passos), \
        [p.nome for p in limpo.passos]


def test_motivos_de_normalizar_pela_sonda(tmp: Path):
    S = ff.Sonda
    assert fb.motivos_de_normalizar(S(1920, 1080, 30, 5.0, True, "", "h264", False, 0)) == []
    assert fb.motivos_de_normalizar(S(1920, 1080, 30, 5.0, True, "", "hevc", False, 0)) == ["codec HEVC"]
    assert len(fb.motivos_de_normalizar(S(1080, 1920, 30, 5.0, True, "", "hevc", True, 90))) == 3


def test_normaliza_o_bruto_de_celular_de_verdade(tmp: Path):
    cel = _iphone(tmp)
    passo = fb.normaliza_bruto(cel, tmp / "trab")
    assert passo is not None and passo.saida.name == "bruto.mp4"
    fb._executa([passo], False, 1)
    antes, depois = ff.probe(cel), ff.probe(passo.saida)
    assert depois.codec == "h264" and not depois.vfr and depois.giro == 0, depois
    assert (depois.largura, depois.altura) == (antes.largura, antes.altura) == (400, 640), (antes, depois)
    assert depois.tem_audio and abs(depois.duracao - antes.duracao) < 0.3, depois


def test_main_com_bruto_que_nao_existe_fala_portugues(tmp: Path):
    import contextlib, io
    plano = tmp / "reel.json"
    plano.write_text(json.dumps({"fonte": "nao-gravei.mov"}), encoding="utf-8")
    err = io.StringIO()
    velho = sys.argv
    sys.argv = ["fabrica.py", str(plano), "--seco"]
    try:
        with contextlib.redirect_stderr(err):
            try:
                fb.main()
                codigo = 0
            except SystemExit as e:
                codigo = e.code
    finally:
        sys.argv = velho
    linhas = err.getvalue().strip().splitlines()
    assert codigo not in (0, None), codigo
    assert len(linhas) == 3, linhas
    assert "nao-gravei.mov" in linhas[0] and "conferencia.txt" in linhas[2], linhas
    assert "Traceback" not in err.getvalue()


def test_transcript_com_erro_de_digitacao_nao_corta_calado(tmp: Path):
    """Caminho de transcript que não existe: no run real é erro (antes o vídeo saía inteiro, sem
    corte, e ninguém via). No seco passa — a transcrição pode nascer na cadeia."""
    plano = _plano(tmp, transcript=str(tmp / "t-errado.json"))
    erro = None
    try:
        fb.fabrica(plano)
    except FileNotFoundError as e:
        erro = e
    assert erro is not None and "transcript" in str(erro), erro
    fb.fabrica(plano, seco=True)


def test_estilo_so_ganha_padrao_no_plano_minimo(tmp: Path):
    fonte = _fonte(tmp)
    erro = None
    try:
        fb.fabrica({"fonte": str(fonte), "slug": "x", "janelas": [[0, 1]]}, seco=True)
    except KeyError as e:
        erro = e
    assert erro is not None and "estilo" in str(erro), erro
    assert fb.fabrica({"fonte": str(fonte)}, seco=True).estilo.nome == "reel-camera"


def test_plano_minimo_usa_o_estilo_padrao_da_marca(tmp: Path):
    """O onboarding grava `_padrao` na marca do aluno: é o estilo de quem só traz o bruto. Nome que o
    catálogo não conhece cai no reel-camera; estilo escrito no plano ganha; plano com mais que o mínimo
    segue sem estilo (e erra, como sempre)."""
    es = fb.es
    marca = tmp / "marca"
    marca.mkdir()
    (marca / "estilos.json").write_text(json.dumps({
        "_padrao": "acme-celular", "acme-celular": {"herda": "reel-camera", "desenho": {"tema": "tinta"}}}),
        encoding="utf-8")
    fonte = _fonte(tmp, "bruto.mp4")
    velho_marca, velho = es.MARCA, dict(es.ESTILOS)
    try:
        es.MARCA = marca
        es.ESTILOS.update(es.da_marca(marca))
        seco = fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True)
        assert seco.estilo.nome == "acme-celular", seco.estilo.nome
        assert fb.fabrica({"fonte": str(fonte), "estilo": "reel-camera"}, seco=True).estilo.nome == "reel-camera"
        assert "estilo" not in fb._completa({"fonte": str(fonte), "slug": "x", "janelas": [[0, 1]]})
        (marca / "estilos.json").write_text(json.dumps({"_padrao": "nao-existe"}), encoding="utf-8")
        assert fb.fabrica({"fonte": str(fonte)}, seco=True).estilo.nome == "reel-camera"
    finally:
        es.MARCA = velho_marca
        es.ESTILOS.clear()
        es.ESTILOS.update(velho)


def _fala_pronta(dir_: Path, duracao: float) -> Path:
    palavras = [{"type": "word", "text": t, "start": round(0.5 + i * 0.5, 2), "end": round(0.8 + i * 0.5, 2)}
                for i, t in enumerate("essa aula mostra como cortar a live".split())]
    arq = dir_ / "fala.json"
    arq.write_text(json.dumps({"language": "por", "duration": duracao, "text": "essa aula",
                               "words": palavras}), encoding="utf-8")
    return arq


def test_plano_minimo_usa_a_fala_pronta_ao_lado_do_bruto(tmp: Path):
    """A demo do kit traz o Transcript (`fala.json`) ao lado do vídeo: com a mesma duração, a fábrica
    corta por ele e não transcreve. Duração diferente é outro vídeo, e aí transcreve como sempre."""
    fonte = _fonte(tmp, "meu-primeiro-video.mp4", dur=8)
    sem = fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True)
    assert any(p.nome.startswith("transcreve") for p in sem.passos), "sem fala.json a fábrica transcreve"
    fala = _fala_pronta(tmp, ff.dur(fonte))
    com = fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True)
    nomes = [p.nome for p in com.passos]
    assert not any(n.startswith("transcreve") for n in nomes), nomes
    assert len(com.edl) > 1, f"o corte não saiu da fala pronta: {com.edl}"
    assert com.final == sem.final
    _fala_pronta(tmp, ff.dur(fonte) + 3)
    outra = fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True)
    assert any(p.nome.startswith("transcreve") for p in outra.passos), "fala de outro vídeo foi usada"
    fala.write_text("{quebrado", encoding="utf-8")
    assert any(p.nome.startswith("transcreve") for p in
               fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida")}, seco=True).passos)


def test_plano_minimo_leva_a_trilha_do_kit_se_o_kit_tem(tmp: Path):
    """O kit traz três faixas CC0 em `exemplos/trilhas/`. O primeiro vídeo sai com a primeira por baixo
    da fala, sem o aluno pedir. Onde a pasta não existe (o tronco), nada muda e nada é avisado. O aluno
    que escolheu (faixa, recursos, música no estilo) não é desfeito."""
    fonte = _fonte(tmp, "v.mp4")
    faixa = tmp / "lofi-calma.m4a"
    faixa.write_bytes(b"x")
    velha = fb.FAIXA_DO_KIT

    def seco(**extra):
        return fb.fabrica({"fonte": str(fonte), "saida": str(tmp / "saida"), **extra}, seco=True)

    try:
        fb.FAIXA_DO_KIT = tmp / "nao-existe.m4a"
        s = seco()
        assert not any("trilha" in p.nome for p in s.passos) and not any("trilha" in m[0] for m in s.mudos), \
            [p.nome for p in s.passos]
        fb.FAIXA_DO_KIT = faixa
        s = seco()
        assert any(p.nome == "fecho com trilha" and str(faixa) in p.cmd for p in s.passos), \
            [p.nome for p in s.passos]
        assert not any(m[0] == "trilha" for m in s.mudos), s.mudos
        # quem já decidiu fica com o que decidiu
        proprio = tmp / "minha.mp3"
        proprio.write_bytes(b"y")
        s = seco(faixa=str(proprio), recursos={"+": ["trilha"]})
        assert any(p.nome == "fecho com trilha" and str(proprio) in p.cmd and str(faixa) not in p.cmd
                   for p in s.passos), [p.cmd for p in s.passos]
        s = seco(faixa=str(proprio))
        assert not any(str(faixa) in p.cmd for p in s.passos), "a faixa do kit passou por cima da dele"
        s = seco(recursos={"-": ["trilha"]})
        assert not any("trilha" in p.nome for p in s.passos), "o aluno tirou a música e ela voltou"
        s = seco(trilha={"faixa": str(proprio)})
        assert not any(str(faixa) in p.cmd for p in s.passos), "a faixa do kit passou por cima da dele"
        # plano com mais que o mínimo não ganha música que não pediu
        s = fb.fabrica({"fonte": str(fonte), "estilo": "reel-camera", "slug": "v", "janelas": [[0, 2]]},
                       seco=True)
        assert not any("trilha" in p.nome for p in s.passos)
    finally:
        fb.FAIXA_DO_KIT = velha


def test_knob_inofensivo_nao_desliga_a_transcricao(tmp: Path):
    fonte = _fonte(tmp)
    # o botão do corte automático (congela_fim) é por vídeo e não diz onde cortar: o plano segue mínimo
    for extra in ({"paralelo": 1}, {"faixa": "x.mp3"}, {"trilha": {"duck": 0.5}},
                  {"corte": {"congela_fim": 1.5}}):
        seco = fb.fabrica({"fonte": str(fonte), **extra}, seco=True)
        assert any(p.nome.startswith("transcreve") for p in seco.passos), extra


def test_camera_sem_transcricao_avisa_que_vai_inteiro(tmp: Path):
    import contextlib, io
    fonte = _fonte(tmp)

    def fala(plano):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            fb.fabrica(plano, seco=True)
        return out.getvalue()
    texto = fala({"fonte": str(fonte), "estilo": "reel-camera", "slug": "v", "janelas": [[0, 2]]})
    assert "sem corte" in texto and "transcript" in texto, texto
    assert "sem corte" not in fala({"fonte": str(fonte)})


def test_erro_de_transcricao_sai_com_conselho_de_internet(tmp: Path):
    e = RuntimeError("passo falhou (código 1): /py/python /x/transcribe.py /t/bruto.mp4 --model large-v3")
    assert "internet" in " ".join(fb.explica_erro(e))


def test_main_mostra_o_traceback_do_erro_desconhecido(tmp: Path):
    import contextlib, io
    plano = tmp / "p.json"
    plano.write_text(json.dumps({"fonte": "x.mov"}), encoding="utf-8")
    velho, velha_f = sys.argv, fb.fabrica
    def estoura(*a, **k):
        return 1 / 0
    fb.fabrica = estoura
    sys.argv = ["fabrica.py", str(plano)]
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            try:
                fb.main()
            except SystemExit:
                pass
    finally:
        sys.argv, fb.fabrica = velho, velha_f
    assert "Traceback" in err.getvalue() and "ZeroDivisionError" in err.getvalue(), err.getvalue()


def test_normaliza_com_taxa_padrao_e_nao_com_a_media_solta(tmp: Path):
    S, velho = ff.Sonda, ff.probe
    try:
        for sonda, quer in ((S(640, 400, 30, 5.0, True, "", "hevc", True, 0, 24), "fps=24"),
                            (S(640, 400, 30, 5.0, True, "", "hevc", True, 0, 19), "fps=24"),
                            (S(640, 400, 30, 5.0, True, "", "hevc", True, 0, 29), "fps=30"),
                            (S(640, 400, 60, 5.0, True, "", "hevc", False, 0, 60), "fps=60")):
            ff.probe = lambda _f, s=sonda: s
            passo = fb.normaliza_bruto(tmp / "a.mov", tmp / "t")
            assert quer in passo.cmd, (sonda, passo.cmd)
    finally:
        ff.probe = velho


def main() -> int:
    casos = [
        ("plano sem campo falha antes",     test_plano_sem_campo_obrigatorio_falha_antes_de_tudo),
        ("estilo errado lista válidos",     test_estilo_que_nao_existe_falha_listando),
        ("bruto incompatível falha",        test_bruto_incompativel_com_o_estilo_falha),
        ("fonte que não existe falha",      test_fonte_que_nao_existe_falha),
        ("modo seco não escreve vídeo",     test_modo_seco_nao_escreve_video),
        ("modo seco devolve o EDL",         test_modo_seco_devolve_o_edl),
        ("modo seco devolve o estilo",      test_modo_seco_devolve_o_estilo_resolvido),
        ("modo seco mostra os recursos",    test_modo_seco_mostra_a_pilha_de_recursos),
        ("entrada em laço leva -t",         test_toda_entrada_em_laco_leva_limite_de_duracao),
        ("saída do canal sem pedir",        test_saida_do_canal_sem_ninguem_pedir),
        ("glitch antes do CRT",             test_glitch_entra_antes_do_embrulho_crt),
        ("chapa cobre a bolinha",           test_chapa_cobre_a_bolinha_e_cabe_no_quadro),
        ("chapa do modo 2 ao lado",         test_chapa_do_modo_2_nao_cobre_a_tela),
        ("chapa antes do explicador",       test_aula_fabrica_poe_a_chapa_antes_do_explicador),
        ("modo 2 corta o celular",          test_modo_2_corta_o_celular_nos_trechos_da_tela),
        ("abertura e fecho por peça",       test_abertura_e_fecho_por_peca),
        ("desligar some com o passo",       test_desligar_recurso_some_com_os_comandos_dele),
        ("ligar acrescenta o passo",        test_ligar_recurso_acrescenta_o_passo),
        ("começar no desenho",              test_comecar_no_desenho_nao_corta_nem_renderiza),
        ("etapa errada lista as válidas",   test_etapa_que_nao_existe_lista_as_validas),
        ("desde corta sem mudar o caminho", test_desde_corta_a_cadeia_sem_mudar_o_caminho),
        ("os dois formatos, uma fábrica",   test_vertical_e_horizontal_pela_mesma_fabrica),
        ("entrega onde o estilo manda",     test_a_entrega_sai_onde_o_estilo_manda),
        ("o corte vem do estilo",           test_o_corte_vem_do_estilo),
        ("sobrescrita chega na cadeia",     test_sobrescrita_do_plano_chega_na_cadeia),
        ("recorte volta às dims da live",   test_recorte_volta_as_dimensoes_da_live_antes_de_cortar),
        ("pilha empilha rosto e desenho",   test_pilha_empilha_rosto_e_desenho),
        ("sobreposição usa chroma",         test_sobreposicao_usa_chroma_em_vez_de_empilhar),
        ("sem recorte não há composição",   test_sem_recorte_nao_ha_composicao),
        ("reel de câmera toca os sons",     test_reel_de_camera_toca_os_sons),
        ("reel de câmera põe as peças da fala", test_reel_de_camera_poe_as_pecas_da_fala_e_o_plano_desliga),
        ("âncora da live vira tempo do clipe", test_ancora_da_live_vira_tempo_do_clipe),
        ("âncora no silêncio cai na emenda", test_ancora_no_silencio_removido_cai_na_emenda),
        ("faixa entra 2x e cruza",          test_a_faixa_entra_duas_vezes_e_cruza_consigo),
        ("trilha no piso sem fecho",        test_a_trilha_fica_no_piso_sem_fecho),
        ("com fecho a trilha sobe",         test_com_fecho_a_trilha_sobe_em_rampa),
        ("trilha sem fecho copia a imagem", test_trilha_sem_fecho_copia_a_imagem),
        ("emenda copia partes iguais",      test_emenda_copia_a_imagem_quando_as_partes_sao_iguais),
        ("o mix não normaliza",             test_o_mix_nao_normaliza),
        ("sem faixa não há trilha",         test_sem_faixa_nao_ha_passo_de_trilha),
        ("desligar o recurso tira",         test_desligar_o_recurso_tira_a_trilha),
        ("slide de texto reprova",          test_aula_que_virou_slide_reprova_antes_do_render),
        ("aula com desenho passa",          test_aula_com_desenho_passa_na_regua),
        ("cada apoio é uma entrada",        test_cada_corte_de_apoio_e_uma_entrada),
        ("deslize mora na coordenada",      test_o_deslize_mora_na_coordenada_e_nao_num_fade),
        ("apoio só na janela dele",         test_o_apoio_so_existe_na_janela_dele),
        ("sem b-roll não há passo",         test_sem_broll_nao_ha_passo),
        ("rodar 2x não refaz nada",         test_rodar_duas_vezes_nao_refaz_nada),
        ("trocar card não refaz corte",     test_trocar_o_conteudo_do_card_nao_refaz_o_corte),
        ("trocar janela refaz o corte",     test_trocar_a_janela_refaz_do_corte_em_diante),
        ("helper alterado invalida",        test_mexer_no_helper_invalida_o_que_ele_produziu),
        ("truncado não conta como feito",   test_saida_truncada_nao_conta_como_feita),
        ("o cache não muda o resultado",    test_o_cache_nao_muda_o_resultado),
        ("sem cache traz tudo de volta",    test_sem_cache_traz_todos_os_passos_de_volta),
        ("trocar o card refaz explicador",  test_trocar_o_card_refaz_o_explicador),
        ("trocar entrada refaz o passo",    test_trocar_um_arquivo_de_entrada_refaz_o_passo),
        ("o seco estima o custo",           test_o_modo_seco_estima_o_custo),
        ("passo suspeito sai marcado",      test_o_passo_que_toca_pouco_e_custa_muito_sai_marcado),
        ("quem toca tudo não é suspeito",   test_o_passo_que_toca_tudo_nao_e_suspeito),
        ("trechos na ordem das janelas",    test_os_trechos_saem_na_ordem_das_janelas),
        ("trecho que falha diz qual",       test_um_trecho_que_falha_diz_qual),
        ("avatar corta no áudio",           test_avatar_corta_no_audio_e_nao_renderiza),
        ("avatar para no portão",           test_avatar_sem_os_blocos_para_no_portao),
        ("avatar emenda com junta",         test_avatar_com_blocos_emenda_pelo_junta),
        ("a afinação do estilo manda",      test_a_afinacao_do_estilo_chega_no_apara_pausas),
        ("o portão não é suspeito",         test_o_portao_nao_entra_como_suspeito),
        ("o estilo escolhe o queimador",    test_o_estilo_escolhe_o_queimador_de_legenda),
        ("adaptador inventado falha",       test_adaptador_que_nao_existe_falha_listando),
        ("legenda sem plano gera cards",    test_legenda_pedida_sem_plano_gera_os_cards),
        ("vsl não promete explicador",      test_o_vsl_nao_promete_explicador),
        ("avatar não grava EDL morto",      test_avatar_nao_grava_edl_morto),
        ("beat sem campo diz qual",         test_beat_sem_campo_obrigatorio_diz_qual_beat),
        ("beat velho ensina a tradução",    test_beat_com_chave_do_vocabulario_velho_ensina_a_traducao),
        ("beat inventado lista as válidas", test_beat_com_chave_inventada_lista_as_validas),
        ("beat válido passa inteiro",       test_beat_valido_passa_inteiro),
        ("aprovado vira beat",              test_candidato_aprovado_vira_beat),
        ("reprovado fica de fora",          test_candidato_nao_aprovado_fica_de_fora),
        ("sem âncora não chuta",            test_beat_sem_ancora_fica_de_fora_e_nao_chuta),
        ("produtor fala a língua da guarda", test_o_que_sai_do_produtor_passa_na_guarda_do_beat),
        ("procedência só do que é de fora", test_procedencia_lista_so_o_que_veio_de_fora),
        ("sem terceiro, nada a declarar",   test_sem_material_de_terceiro_nao_ha_o_que_declarar),
        ("argumento gigante não derruba",   test_argumento_gigante_nao_derruba_a_impressao),
        ("camada muda é anunciada",         test_recurso_que_nao_vai_entrar_e_anunciado),
        ("legenda sem fonte é anunciada",   test_legenda_sem_transcricao_nem_plano_e_anunciada),
        ("camada atendida não vira aviso",   test_recurso_atendido_nao_e_anunciado_como_mudo),
        ("adaptador aponta pra helper",     test_todo_adaptador_aponta_para_helper_que_existe),
        ("vsl em blocos monta e emenda",    test_vsl_em_blocos_monta_cada_bloco_e_emenda),
        ("cor por trecho antes das peças",  test_cor_por_trecho_entra_antes_das_pecas),
        ("o estilo preenche a direção",     test_o_estilo_preenche_a_direcao_do_bloco),
        ("vsl: nada atrás da pessoa",       test_vsl_nao_poe_texto_atras_da_pessoa),
        ("peça pelo nome, tema do estilo",  test_peca_pelo_nome_sai_no_tema_do_estilo),
        ("bloco não gerado para no portão", test_bloco_sem_geracao_para_no_portao_dele),
        ("receita troca imagem, traz som",  test_receita_troca_a_imagem_e_o_som_vem_dela),
        ("sem saida, final em videos/",     test_sem_saida_o_final_vai_para_videos),
        ("portão e apara: marcas próprias", test_portao_e_apara_nao_dividem_a_marca_de_cache),
        ("peça refaz se o desenho muda",    test_peca_refaz_quando_o_desenho_muda),
        ("receitas sobrepostas recusadas",  test_receitas_sobrepostas_sao_recusadas),
        ("não pisa em final alheio",        test_nao_sobrescreve_final_que_nao_fez),
        ("legenda da fábrica tem direção",  test_a_legenda_da_fabrica_leva_a_direcao),
        ("preset de legenda vem do estilo", test_o_preset_de_legenda_vem_do_estilo),
        ("legenda anda no tempo do corte",  test_legenda_gerada_anda_no_tempo_do_corte),
        ("por_bloco num bruto trata a voz",  test_por_bloco_num_bruto_so_trata_a_voz_pela_cadeia_do_microfone),
        ("voz isolada antes do render",     test_voz_isolada_entra_antes_do_render),
        ("bloco sai de janelas do bruto",   test_bloco_sai_de_janelas_do_bruto),
        ("curto com cama no alvo dele",     test_curto_com_cama_sai_no_alvo_dele),
        ("efeito não abaixa a trilha",      test_efeito_nao_abaixa_a_trilha),
        ("vinheta abre o bloco",            test_vinheta_abre_o_bloco_e_a_cama_sai_da_frente),
        ("janela congela e acelera",        test_janela_congela_o_ultimo_quadro),
        ("congela_fim segura o final",      test_corte_congela_fim_segura_o_final),
        ("bloco recorta o vertical",        test_bloco_recorta_o_vertical_de_outro_bruto),
        ("o Short sai em pé do vídeo deitado", test_o_short_sai_em_pe_do_video_deitado),
        ("longo nivela a fala por bloco",   test_longo_nivela_a_fala_de_cada_bloco),
        ("nivela_fala entra após a emenda", test_nivela_fala_no_plano_poe_um_passo_entre_a_emenda_e_a_trilha),
        ("--refaz derruba só o bloco",      test_refaz_um_bloco_derruba_so_o_cache_dele),
        ("plano de bloco cai na fala",      test_plano_de_bloco_cai_na_fala_pela_ancora),
        ("peça transparente flutua",        test_peca_transparente_flutua_sobre_o_video),
        ("bloco com voz gravada por cima",  test_bloco_com_voz_gravada_por_cima),
        ("voz sintética pula o microfone",  test_voz_sintetica_pula_o_microfone),
        ("bloco de voz sintética também",   test_bloco_com_voz_sintetica_nao_passa_pelo_microfone),
        ("dois reels numa geração só",      test_trechos_de_rosto_de_dois_reels_numa_geracao),
        ("reel editorial pelo helper",      test_reel_editorial_monta_pelo_helper),
        ("reel editorial não gasta",        test_reel_editorial_nao_gasta_sozinho),
        ("regras do dono no seco",          test_reel_editorial_cobra_as_regras_do_dono),
        ("cabeça e rosto do mesmo webm",    test_reel_editorial_cabeca_e_rosto_do_mesmo_webm),
        ("capa vê a foto",                  test_reel_editorial_capa_ve_a_foto),
        ("peça mostra a capa da cadeia",    test_reel_editorial_peca_mostra_a_capa_que_a_cadeia_faz),
        ("transcrição abre o áudio",        test_transcricao_abre_o_audio),
        ("fonte refeita, transcrição nova", test_transcricao_refeita_quando_a_fonte_muda),
        ("a transcrição segue a voz",      test_transcricao_segue_a_voz),
        ("caminho do plano, outra pasta",   test_caminho_do_plano_vale_de_qualquer_pasta),
        ("frase do yt confere o que ouviu", test_reel_editorial_frase_do_youtube_confere_o_que_ouviu),
        ("última frase sem ponto",          test_reel_editorial_ultima_frase_sem_ponto),
        ("captura em página que não para",  test_reel_editorial_captura_em_pagina_que_nao_para),
        ("converte leva o plano velho",     test_reel_editorial_converte_leva_o_que_o_plano_velho_tinha),
        ("caminho do Windows na fala",      test_caminho_do_windows_nao_vira_deslocamento),
        ("encaixe mede a peça inteira",     test_reel_editorial_encaixe_mede_a_peca_inteira),
        ("fundo por trecho",                test_reel_editorial_fundo_por_trecho),
        ("trechos do take saem iguais",     test_reel_editorial_trechos_saem_iguais),
        ("sem rosto não pede HeyGen",       test_reel_editorial_sem_rosto_nao_pede_heygen),
        ("alinha o webm que chegou pronto", test_reel_editorial_alinha_o_webm_que_chegou_pronto),
        ("sem trilha, a do app",            test_reel_editorial_sem_trilha_quando_a_musica_e_do_app),
        ("peça sem estilo sai no claro",    test_reel_editorial_peca_sem_estilo_sai_no_claro),
        ("trilha pelo clima",               test_reel_editorial_escolhe_a_trilha_pelo_clima),
        ("trava mede a tela vazia",         test_reel_editorial_trava_mede_a_tela_vazia),
        ("seco avisa a tela vazia",         test_reel_editorial_seco_avisa_a_tela_vazia),
        ("degraus e fechos no seco",        test_reel_editorial_degraus_e_fechos),
        ("degrau desliga a skill",          test_degrau_desliga_o_que_a_skill_faz),
        ("degrau toca o buraco do mapa",    test_degrau_sem_capa_toca_o_buraco_do_mapa),
        ("criativo pelo helper",            test_criativo_monta_pelo_helper),
        ("criativo não gasta",              test_criativo_nao_gasta_sozinho),
        ("criativo recusa cena fora",       test_criativo_recusa_cena_que_o_banco_nao_tem),
        ("legenda sai do roteiro",          test_criativo_legenda_sai_do_roteiro),
        ("criativo de ponta a ponta",       test_criativo_de_ponta_a_ponta),
        ("filmadora com a data da ficha",   test_filmadora_escreve_a_data_da_ficha),
        ("selo sem a fonte do Mac",         test_selo_da_camera_sem_a_fonte_do_mac),
        ("blocos correm juntos",            test_blocos_correm_juntos_e_quem_le_espera),
        ("peças num lote só",               test_pecas_da_cadeia_vao_num_lote_so),
        ("câmera refaz a legenda",          test_mexer_na_camera_refaz_a_legenda),
        ("seco enxerga o explicador",       test_o_seco_enxerga_as_pecas_do_explicador),
        ("proxy uma vez, recorte no 4K",    test_proxy_uma_vez_por_bruto_e_o_recorte_fica_no_original),
        ("codificador entra no cache",      test_codificador_de_hardware_refaz_o_cache),
        ("estilo pede o codificador auto",  test_estilo_pede_o_codificador_auto_por_padrao),
        ("plano minimo so com o bruto",     test_plano_minimo_so_com_o_bruto),
        ("celular ganha o passo normaliza", test_bruto_de_celular_ganha_o_passo_de_normalizar),
        ("motivos de normalizar",           test_motivos_de_normalizar_pela_sonda),
        ("normaliza o celular de verdade",  test_normaliza_o_bruto_de_celular_de_verdade),
        ("main com bruto ausente",          test_main_com_bruto_que_nao_existe_fala_portugues),
        ("transcript errado não corta calado", test_transcript_com_erro_de_digitacao_nao_corta_calado),
        ("estilo padrão só no mínimo",      test_estilo_so_ganha_padrao_no_plano_minimo),
        ("padrão da marca no mínimo",       test_plano_minimo_usa_o_estilo_padrao_da_marca),
        ("fala pronta ao lado do bruto",    test_plano_minimo_usa_a_fala_pronta_ao_lado_do_bruto),
        ("trilha do kit no mínimo",         test_plano_minimo_leva_a_trilha_do_kit_se_o_kit_tem),
        ("knob inofensivo mantém transcrição", test_knob_inofensivo_nao_desliga_a_transcricao),
        ("câmera sem corte avisa",          test_camera_sem_transcricao_avisa_que_vai_inteiro),
        ("erro de transcrição aconselha",   test_erro_de_transcricao_sai_com_conselho_de_internet),
        ("erro desconhecido mostra traceback", test_main_mostra_o_traceback_do_erro_desconhecido),
        ("normaliza com taxa padrão",       test_normaliza_com_taxa_padrao_e_nao_com_a_media_solta),
        ("tempo medido, mediana de 5",      test_o_tempo_medido_guarda_as_cinco_ultimas_e_a_mediana_vale),
        ("seco curto, detalhe com comando", test_o_seco_sai_curto_e_o_detalhe_traz_o_comando),
        ("main --detalhe",                  test_main_so_mostra_o_comando_com_detalhe),
        ("storyboard sem pauta para",     test_storyboard_do_celular_sem_visual_json_para_na_linha_da_pauta),
        ("sem pauta nada pesado",          test_storyboard_sem_pauta_nao_faz_trabalho_pesado_antes_de_parar),
        ("progresso, tempo e vaga",         test_executa_mostra_o_progresso_grava_o_tempo_e_so_pede_vaga_a_quem_custa),
    ]
    falhas = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # os casos que renderizam de verdade gravariam o tempo e pegariam as vagas do cache de quem roda o teste
        os.environ[fb.vagas.CACHE] = str(tmp / "_cache")
        for nome, caso in casos:
            sub = tmp / re.sub(r"[^\w-]+", "_", nome)
            sub.mkdir(parents=True, exist_ok=True)
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
