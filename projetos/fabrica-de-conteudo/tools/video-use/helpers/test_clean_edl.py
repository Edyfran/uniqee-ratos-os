"""Auto-teste da costura A (clean_edl). Sem framework — assert direto, um comando.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_clean_edl.py

Só um caso gera um áudio sintético curto (ffmpeg, via ff). Cada frase aqui saiu de uma live de verdade, e cada caso
existe porque o corte errado foi visto assistindo. Corte errado novo entra aqui
como uma linha, senão ele volta no ajuste seguinte.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import clean_edl as ce


# ---- montagem de fala -------------------------------------------------------


def fala(texto: str, inicio: float = 10.0, dur: float = 0.30, respiro: float = 0.05):
    """Palavras em sequência, cada uma com a mesma duração e o mesmo respiro."""
    palavras, t = [], inicio
    for tok in texto.split():
        palavras.append({"text": tok, "start": round(t, 3), "end": round(t + dur, 3),
                         "type": "word"})
        t += dur + respiro
    return palavras


def p(texto, inicio, fim):
    return {"text": texto, "start": inicio, "end": fim, "type": "word"}


def ditas(trechos) -> str:
    """O que sobrou, em texto, para o assert ler como frase."""
    return " ".join(t.get("_texto", "") for t in trechos).strip()


def cobre(trechos, palavra: dict) -> bool:
    """A palavra sobreviveu ao corte? (algum trecho mantido a contém)"""
    meio = (float(palavra["start"]) + float(palavra["end"])) / 2
    return any(t["start"] <= meio <= t["end"] for t in trechos)


def sobreviveram(trechos, palavras) -> list[str]:
    return [w["text"] for w in palavras if cobre(trechos, w)]


# ---- gaguejada vs lista vs anáfora ------------------------------------------


def test_gaguejada_de_duas_palavras_sai():
    """'meu projeto meu projeto' — repetição imediata, uma some."""
    ws = fala("eu abri o meu projeto meu projeto ontem")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert sobreviveram(t, ws).count("projeto") == 1, \
        f"a gaguejada sobreviveu: {sobreviveram(t, ws)}"


def test_lista_de_dois_itens_fica():
    """'pode criar carrossel, pode criar post' — lista, não gaguejada."""
    ws = fala("pode criar carrossel, pode criar post")
    t = ce.cortar(ws, afinacao=ce.AULA)
    vivas = sobreviveram(t, ws)
    assert vivas.count("pode") == 2, f"comeu um item da lista: {vivas}"
    assert "carrossel," in vivas and "post" in vivas


def test_anafora_de_tres_fica():
    """'vai poder X, vai poder Y, vai poder Z' — ênfase deliberada, intacta."""
    ws = fala("vai poder cortar, vai poder legendar, vai poder publicar")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert sobreviveram(t, ws).count("vai") == 3, \
        f"a anáfora foi cortada: {sobreviveram(t, ws)}"


def test_recomeco_de_quatro_e_cinco_palavras_sai():
    """Frase inteira dita de novo, colada. Só olhava 2 e 3 palavras: estas
    passavam intactas."""
    for frase, palavra in (("eu vou te mostrar como eu vou te mostrar como funciona", "mostrar"),
                           ("você abre o terminal aqui você abre o terminal aqui e digita", "terminal")):
        ws = fala(frase)
        t = ce.cortar(ws, afinacao=ce.AULA)
        assert sobreviveram(t, ws).count(palavra) == 1, \
            f"o recomeço sobreviveu: {sobreviveram(t, ws)}"


def test_recomeco_longo_com_pausa_longa_fica():
    """Quatro palavras repetidas depois de uma pausa longa são retomada."""
    ws = fala("isso é muito importante", inicio=10.0) + fala("isso é muito importante", inicio=13.0)
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert sobreviveram(t, ws).count("importante") == 2, "cortou uma retomada distante"


def test_repeticao_que_abre_frase_nova_fica():
    """Saíram de lives: a segunda vez começa outra frase, de propósito."""
    for frase in ("isso aqui não é a primeira camada do projeto. A primeira camada do projeto são os arquivos",
                  "o que a gente vai usar? A gente vai usar o plugin",
                  "não é isso que a gente vai fazer A gente vai fazer outra coisa"):
        ws = fala(frase)
        t = ce.cortar(ws, afinacao=ce.AULA)
        assert sobreviveram(t, ws) == [w["text"] for w in ws], \
            f"cortou repetição de propósito: {sobreviveram(t, ws)}"


def test_repeticao_de_uma_palavra_sai():
    ws = fala("então então vamos ver")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert sobreviveram(t, ws).count("então") == 1


def test_repeticao_lenta_nao_e_gaguejada():
    """Duas frases iguais separadas por pausa longa são retomada, não gagueira."""
    ws = [p("a", 10.0, 10.3), p("meta", 10.4, 10.9),
          p("a", 14.0, 14.3), p("meta", 14.4, 14.9)]
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert sobreviveram(t, ws).count("meta") == 2, "cortou uma retomada distante"


# ---- "tá" verbo vs tique ----------------------------------------------------


def test_ta_verbo_fica():
    for frase in ("o servidor tá rodando agora", "ele tá no ar", "tudo tá certo"):
        ws = fala(frase)
        t = ce.cortar(ws, afinacao=ce.AULA)
        assert "tá" in sobreviveram(t, ws), f"apagou o verbo em: {frase}"


def test_ta_tique_sai():
    ws = fala("isso resolve o problema tá? vamos seguir")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "tá?" not in sobreviveram(t, ws), "o tique 'tá?' ficou"


# ---- "é" verbo vs hesitação -------------------------------------------------


def test_e_verbo_fica():
    for frase in ("isso é o que importa", "é um problema comum", "é gratuito"):
        ws = fala(frase)
        t = ce.cortar(ws, afinacao=ce.AULA)
        assert "é" in sobreviveram(t, ws), f"apagou o verbo em: {frase}"


def test_e_verbo_antes_de_infinitivo_fica():
    """'é ver o vídeo' — o infinitivo curto já derrubou o verbo uma vez."""
    ws = fala("o jeito é ver o vídeo")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "é" in sobreviveram(t, ws)


def test_e_hesitacao_com_virgula_sai():
    """Vírgula depois do 'é' é hesitação: o verbo pede complemento, não fecha oração."""
    ws = fala("então é, vamos fazer assim")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "é," not in sobreviveram(t, ws), "a hesitação 'é,' ficou"


def test_e_depois_de_que_nao_e_hesitacao():
    """'não sei o que é, mas funciona' — depois de 'que', a vírgula é legítima."""
    ws = fala("não sei o que é, mas funciona")
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "é," in sobreviveram(t, ws)


def test_e_arrastado_sai():
    """'ééé' longo é hesitação, qualquer que seja o resto."""
    ws = [p("então", 10.0, 10.4), p("ééé", 10.5, 11.1), p("vamos", 11.2, 11.6)]
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "ééé" not in sobreviveram(t, ws)


# ---- filler -----------------------------------------------------------------


def test_filler_com_pausa_do_lado_sai():
    ws = [p("isso", 10.0, 10.4), p("né", 10.9, 11.1), p("funciona", 11.6, 12.2)]
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "né" not in sobreviveram(t, ws)


def test_filler_colado_na_fala_fica():
    """Sem pausa de um dos lados, cortar deixa a emenda audível — melhor manter."""
    ws = [p("isso", 10.0, 10.4), p("né", 10.42, 10.6), p("funciona", 10.62, 11.2)]
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert "né" in sobreviveram(t, ws)


# ---- fôlego e cauda ---------------------------------------------------------


def test_folego_na_emenda_de_ar_morto():
    """Virada de tópico tem que continuar respirando: a emenda guarda parte da pausa."""
    ws = [p("primeiro", 10.0, 10.6), p("ponto", 10.7, 11.2),
          p("segundo", 15.0, 15.6), p("ponto", 15.7, 16.2)]
    com = ce.cortar(ws, afinacao=ce.AULA)
    sem = ce.cortar(ws, afinacao=ce.afinacao("aula", pause_keep=0.0))
    assert len(com) == 2, f"a pausa de 3.8s não virou corte: {com}"
    # O fôlego devolve silêncio para DENTRO dos trechos mantidos: o lado de cada
    # emenda cresce, e o que é jogado fora encolhe.
    respiro_com = (com[0]["end"] - 11.2) + (15.0 - com[1]["start"])
    respiro_sem = (sem[0]["end"] - 11.2) + (15.0 - sem[1]["start"])
    assert respiro_com > respiro_sem, \
        f"o fôlego não sobrou na emenda: {respiro_com:.2f}s contra {respiro_sem:.2f}s"
    assert com[1]["start"] - com[0]["end"] < 15.0 - 11.2, "nada foi cortado da pausa"


def test_cauda_de_consoante_surda_nao_e_clipada():
    """O whisper marca o fim na vogal; 'dashboard' e 'vps' arrastam depois disso."""
    ws = [p("abre", 10.0, 10.4), p("o", 10.5, 10.6), p("dashboard", 10.7, 11.3)]
    t = ce.cortar(ws, afinacao=ce.AULA)
    assert t[-1]["end"] >= 11.3 + 0.2, \
        f"cortou a cauda: fim em {t[-1]['end']}, palavra acaba em 11.3"


def test_voz_no_ar_estica_a_borda():
    """Preço da VSL, 22/09/2026: o whisper fechou '41,06' cedo e o tight comeu
    'e seis centavos'. Com a voz medida, a borda anda até o silêncio."""
    ws = [p("doze", 10.0, 10.3), p("vezes", 10.3, 10.6), p("41,06.", 10.6, 11.0),
          p("Esse", 13.0, 13.3)]
    voz = [(10.0, 11.9), (13.0, 13.3)]
    t = ce.cortar(ws, afinacao=ce.TIGHT, voz=voz)
    assert t[0]["end"] >= 11.9, f"cortou com voz no ar: fim em {t[0]['end']}, voz até 11.9"
    sem = ce.cortar(ws, afinacao=ce.TIGHT)
    assert sem[0]["end"] < 11.1, "sem voz o comportamento antigo não mudou"


def test_voz_nao_sobrepoe_trechos():
    """Dois trechos separados por um vão curto dentro da mesma voz: um estica a
    saída, o outro a entrada, e não podem se cruzar."""
    ws = [p("um", 10.0, 10.3), p("dois", 10.3, 10.6), p("três", 10.7, 11.0), p("quatro", 11.0, 11.3)]
    t = ce.cortar(ws, afinacao=ce.TIGHT, voz=[(9.9, 11.4)])
    for a, b in zip(t, t[1:]):
        assert b["start"] > a["end"], f"sobrepôs: {a} e {b}"


def test_voz_nao_devolve_palavra_removida():
    """Esticar pela voz para na palavra vizinha: o filler cortado não volta."""
    ws = [p("isso", 10.0, 10.3), p("né", 10.3, 10.5), p("funciona", 10.9, 11.4)]
    voz = [(10.0, 11.4)]
    t = ce.cortar(ws, afinacao=ce.TIGHT, voz=voz)
    sem = ce.cortar(ws, afinacao=ce.TIGHT)
    assert t[0]["end"] == sem[0]["end"], f"a saída cresceu por cima do 'né': {t[0]['end']}"
    assert t[1]["start"] >= 10.5, f"a entrada voltou por cima do 'né': {t[1]['start']}"


def test_palavra_esticada_vira_suspeita():
    """'olha esses cri- olha esses criativos' chega do whisper como um 'criativos'
    de 1.04s. Não dá para cortar pelo texto; tem que apontar."""
    ws = fala("aí ele faz o que eu aprovei e confere se entrou", dur=0.14, respiro=0.0)
    ws += [p("olha", 11.6, 11.8), p("esses", 11.8, 11.95), p("criativos", 11.95, 13.0),
           p("aqui", 13.0, 13.2), p("preparou.", 13.2, 13.6)]
    sus = [s["text"] for s in ce.suspeitas(ws)]
    assert sus == ["criativos"], sus


# ---- drops e janelas --------------------------------------------------------


def test_drop_a_mao_remove_o_trecho():
    ws = fala("um dois três quatro cinco", inicio=10.0)
    alvo = ws[2]
    t = ce.cortar(ws, drops=[(alvo["start"] - 0.01, alvo["end"] + 0.01)], afinacao=ce.AULA)
    assert "três" not in sobreviveram(t, ws)


def test_janelas_fora_de_ordem_saem_na_ordem_pedida():
    """Costurar trechos espalhados: a saída segue a ordem das janelas, não a do relógio."""
    ws = fala("alfa bravo", inicio=10.0) + fala("charlie delta", inicio=50.0)
    t = ce.cortar(ws, janelas=[(49.0, 52.0), (9.0, 12.0)], afinacao=ce.AULA)
    assert t[0]["start"] > t[-1]["start"], \
        f"as janelas saíram na ordem do relógio, não na pedida: {t}"


def test_pad_nao_escapa_da_janela():
    """A janela é o que o editor escolheu. O pad não pode buscar áudio de fora dela."""
    ws = fala("alfa bravo charlie", inicio=10.0)
    t = ce.cortar(ws, janelas=[(10.0, 11.05)], afinacao=ce.AULA)
    assert t[0]["start"] >= 10.0, f"o pad de entrada saiu da janela: {t[0]['start']}"
    assert t[-1]["end"] <= 11.05, f"o pad de saída saiu da janela: {t[-1]['end']}"


def test_janela_recorta_o_que_entra():
    ws = fala("alfa bravo", inicio=10.0) + fala("charlie delta", inicio=50.0)
    t = ce.cortar(ws, janelas=[(9.0, 12.0)], afinacao=ce.AULA)
    assert all(x["end"] < 20 for x in t), f"vazou fala de fora da janela: {t}"


# ---- afinações --------------------------------------------------------------


def test_aula_e_tight_no_mesmo_processo():
    """O teste que prova que o estado global saiu: as duas rodam sem se contaminar."""
    ws = [p("um", 10.0, 10.4), p("dois", 11.0, 11.4)]
    aula1 = ce.cortar(ws, afinacao=ce.AULA)
    tight = ce.cortar(ws, afinacao=ce.TIGHT)
    aula2 = ce.cortar(ws, afinacao=ce.AULA)
    assert aula1 != tight, "aula e tight deram a mesma saída"
    assert aula1 == aula2, "rodar tight no meio mudou o resultado do modo aula"


def test_tight_corta_a_pausa_que_a_aula_mantem():
    ws = [p("um", 10.0, 10.4), p("dois", 11.0, 11.4)]
    assert len(ce.cortar(ws, afinacao=ce.AULA)) == 1, "a aula não deveria cortar 0.6s"
    assert len(ce.cortar(ws, afinacao=ce.TIGHT)) == 2, "o tight deveria cortar 0.6s"


def test_afinacao_por_nome():
    assert ce.afinacao("aula") == ce.AULA
    assert ce.afinacao("tight") == ce.TIGHT


def test_afinacao_desconhecida_lista_as_validas():
    erro = None
    try:
        ce.afinacao("apertado")
    except Exception as e:
        erro = e
    assert erro is not None, "afinação inexistente passou calada"
    assert "aula" in str(erro) and "tight" in str(erro), f"o erro não lista as válidas: {erro}"


def test_afinacao_com_sobrescrita():
    a = ce.afinacao("aula", sil_cut=0.5)
    assert a.sil_cut == 0.5
    assert a.pad_out == ce.AULA.pad_out, "a sobrescrita vazou para outro botão"
    assert ce.AULA.sil_cut != 0.5, "a sobrescrita mexeu na afinação nomeada"


def test_afinacao_com_botao_que_nao_existe():
    erro = None
    try:
        ce.afinacao("aula", velocidade=2)
    except Exception as e:
        erro = e
    assert erro is not None, "botão inexistente passou calado"


# ---- corte por energia (silence_edl absorvido) ------------------------------


def test_trechos_de_fala_viram_corte():
    """Detecção por energia entra pela mesma função: os trechos falados são as 'palavras'."""
    fala_detectada = [(10.0, 12.0), (14.0, 16.0)]
    t = ce.cortar(ce.palavras_de_trechos(fala_detectada), afinacao=ce.SILENCIO)
    assert len(t) == 2, f"os dois trechos de fala deviam virar dois cortes: {t}"
    assert t[0]["start"] < 10.0, "faltou pad na entrada"
    assert t[0]["end"] > 12.0, "faltou pad na saída"


def test_energia_nao_tenta_ler_texto():
    """Sem texto, as regras de filler/tá/é/gaguejada não têm o que morder."""
    t = ce.cortar(ce.palavras_de_trechos([(10.0, 10.5), (10.6, 11.0)]), afinacao=ce.SILENCIO)
    assert t, "o corte por energia devolveu vazio"


def test_silencio_junta_trechos_colados():
    t = ce.cortar(ce.palavras_de_trechos([(10.0, 12.0), (12.01, 14.0)]), afinacao=ce.SILENCIO)
    assert len(t) == 1, f"trechos colados deviam virar um só: {t}"


def test_silencio_com_gagueira_tira_so_a_repeticao():
    """O corte do reel da câmera: por energia, sem ler o texto, mas a repetição colada sai.
    Nada além dela: 'é', 'tá' e a lista de dois itens ficam como foram ditos."""
    ws = fala("eu abri o meu projeto meu projeto é tá pode criar carrossel pode criar post ontem",
              respiro=0.02)
    af = ce.afinacao("silencio-gagueira")
    assert af.usa_texto is False and af.disfluencia is True, af
    vistas = sobreviveram(ce.cortar(ws, afinacao=af), ws)
    esperado = "eu abri o meu projeto é tá pode criar carrossel pode criar post ontem".split()
    assert vistas == esperado, f"só a repetição devia sair: {vistas}"
    # o corte puro por energia segue como era: nada de ler o texto
    assert sobreviveram(ce.cortar(ws, afinacao=ce.SILENCIO), ws).count("projeto") == 2


def test_silencio_com_gagueira_deixa_a_anafora_inteira():
    ws = fala("vai poder criar, vai poder editar, vai poder postar", respiro=0.02)
    vistas = sobreviveram(ce.cortar(ws, afinacao=ce.afinacao("silencio-gagueira")), ws)
    assert vistas == [w["text"] for w in ws], f"cortou a anáfora de três: {vistas}"


def test_silencio_nao_come_palavra_curta_entre_vaos_finos():
    """Medido na demo do kit (Scribe, 23/10): "corta as pausas" tinha vão de 0.04 e 0.06 s em volta do
    "as" (0.1 s), e "ou pro Codex e pede" o mesmo em volta do "e" (0.06 s). A ilha ficava abaixo do
    `min_seg` e saía do vídeo: "corta pausas", "codex pede"."""
    ws = [p("Corta", 24.58, 24.74), p("as", 24.78, 24.88), p("pausas,", 24.94, 25.30),
          p("pro", 25.40, 25.55), p("Codex", 25.60, 26.10), p("e", 26.16, 26.22), p("pede", 26.28, 26.60)]
    for nome in ("silencio", "silencio-gagueira"):
        vistas = sobreviveram(ce.cortar(ws, afinacao=ce.afinacao(nome)), ws)
        assert vistas == [w["text"] for w in ws], f"{nome}: palavra curta saiu: {vistas}"
    # o estalo sem texto (corte por energia) continua varrido pelo `min_seg`
    assert ce.cortar(ce.palavras_de_trechos([(10.0, 10.05), (14.0, 15.0)]), afinacao=ce.SILENCIO)[0]["start"] > 13.0
    # o corte pelo texto (aula, tight) segue com o `min_seg` de antes: a aula mostra esse corte
    ilha = [p("antes", 10.0, 10.5), p("x", 11.0, 11.01), p("depois", 12.0, 12.5)]
    assert "x" not in sobreviveram(ce.cortar(ilha, afinacao=ce.TIGHT), ilha)


def test_corte_do_tight_nao_deixa_voz_no_vao():
    """O `end` do whisper fecha antes do som. Com a voz medida no áudio (como o fabrica.py
    passa), o vão descartado fica em silêncio; sem ela, o tight come o fim da palavra.
    Áudio sintético: três rajadas de seno com 0.3 s de silêncio entre elas."""
    import re, subprocess, tempfile
    import ff
    rajadas = [(0.0, 1.0), (1.3, 2.5), (2.8, 4.0)]
    expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in rajadas)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "fala.wav"
        ff.run(["ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i",
                f"aevalsrc=0.5*sin(2*PI*200*t)*({expr}):s=16000:d=4.2", str(wav)], quiet=True)

        def pico(a, b):
            if b - a < 0.005:
                return -99.0
            err = ff.run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i",
                          str(wav), "-af", "volumedetect", "-f", "null", "-"],
                         quiet=True, check=False).stderr
            return float(re.search(r"max_volume: (-?[\d.]+)", err).group(1))

        # o whisper marca começo e fim 0.15 s antes do som
        ws = [p("a", 0.0, 0.85), p("b", 1.15, 2.35), p("c", 2.65, 3.85)]
        for voz in (None, ce.fala_do_audio(wav)):
            t = ce.cortar(ws, afinacao=ce.TIGHT, voz=voz)
            piores = [(pico(a["end"], b["start"]), pico(a["end"], min(b["start"], a["end"] + 0.1)))
                      for a, b in zip(t, t[1:])]
            ok = all(v <= -35 and c <= -35 for v, c in piores)
            assert ok == (voz is not None), f"voz={'sim' if voz else 'não'}: vãos {piores}"


def test_silencio_gagueira_nao_come_cauda_de_voz_continua():
    """O estilo do celular (silencio-gagueira) também mede a voz: o vão de 0.2 s no meio de voz
    contínua não vira corte, e a pausa real de 0.6 s continua saindo."""
    import tempfile
    import ff
    expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in [(0.0, 3.0), (3.6, 5.0)])
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "fala.wav"
        ff.run(["ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i",
                f"aevalsrc=0.5*sin(2*PI*200*t)*({expr}):s=16000:d=5.2", str(wav)], quiet=True)
        voz = ce.fala_do_audio(wav)
    # o whisper fecha cada palavra cedo; "b" e "c" têm 0.2 s de vão dentro da voz contínua
    ws = [p("a", 0.0, 1.0), p("b", 1.2, 1.9), p("c", 2.1, 2.6), p("d", 3.7, 4.8)]
    antes = ce.cortar(ws, afinacao=ce.SILENCIO_GAGUEIRA)
    t = ce.cortar(ws, afinacao=ce.SILENCIO_GAGUEIRA, voz=voz)
    assert len(antes) > len(t) == 2, (antes, t)           # sem a voz o vão cortava; com ela, só a pausa
    assert t[0]["end"] >= 3.0 and 3.0 < t[0]["end"] < t[1]["start"] < 3.6 + 0.01, t
    for a, b in zip(t, t[1:]):
        assert not any(x < a["end"] + 0.1 and y > a["end"] for x, y in voz), (a, b)


# ---- corrida ----------------------------------------------------------------


def main() -> int:
    casos = [
        ("voz no ar estica a borda",          test_voz_no_ar_estica_a_borda),
        ("tight não deixa voz no vão",       test_corte_do_tight_nao_deixa_voz_no_vao),
        ("celular não come cauda de voz",    test_silencio_gagueira_nao_come_cauda_de_voz_continua),
        ("voz não sobrepõe trechos",          test_voz_nao_sobrepoe_trechos),
        ("voz não devolve palavra removida",  test_voz_nao_devolve_palavra_removida),
        ("palavra esticada vira suspeita",    test_palavra_esticada_vira_suspeita),
        ("gaguejada de duas palavras sai",   test_gaguejada_de_duas_palavras_sai),
        ("lista de dois itens fica",         test_lista_de_dois_itens_fica),
        ("anáfora de três fica",             test_anafora_de_tres_fica),
        ("repetição de uma palavra sai",     test_repeticao_de_uma_palavra_sai),
        ("repetição lenta não é gaguejada",  test_repeticao_lenta_nao_e_gaguejada),
        ("tá verbo fica",                    test_ta_verbo_fica),
        ("tá? tique sai",                    test_ta_tique_sai),
        ("é verbo fica",                     test_e_verbo_fica),
        ("é antes de infinitivo fica",       test_e_verbo_antes_de_infinitivo_fica),
        ("é, hesitação sai",                 test_e_hesitacao_com_virgula_sai),
        ("é, depois de 'que' fica",          test_e_depois_de_que_nao_e_hesitacao),
        ("é arrastado sai",                  test_e_arrastado_sai),
        ("filler com pausa sai",             test_filler_com_pausa_do_lado_sai),
        ("filler colado fica",               test_filler_colado_na_fala_fica),
        ("fôlego na emenda",                 test_folego_na_emenda_de_ar_morto),
        ("cauda de consoante não clipa",     test_cauda_de_consoante_surda_nao_e_clipada),
        ("drop à mão remove",                test_drop_a_mao_remove_o_trecho),
        ("janelas fora de ordem",            test_janelas_fora_de_ordem_saem_na_ordem_pedida),
        ("pad não escapa da janela",         test_pad_nao_escapa_da_janela),
        ("janela recorta",                   test_janela_recorta_o_que_entra),
        ("aula e tight no mesmo processo",   test_aula_e_tight_no_mesmo_processo),
        ("tight corta o que a aula mantém",  test_tight_corta_a_pausa_que_a_aula_mantem),
        ("afinação por nome",                test_afinacao_por_nome),
        ("recomeço de 4 e 5 palavras sai",   test_recomeco_de_quatro_e_cinco_palavras_sai),
        ("recomeço longo com pausa fica",    test_recomeco_longo_com_pausa_longa_fica),
        ("repetição que abre frase fica",    test_repeticao_que_abre_frase_nova_fica),
        ("afinação errada lista válidas",    test_afinacao_desconhecida_lista_as_validas),
        ("afinação com sobrescrita",         test_afinacao_com_sobrescrita),
        ("botão que não existe estoura",     test_afinacao_com_botao_que_nao_existe),
        ("trechos de fala viram corte",      test_trechos_de_fala_viram_corte),
        ("energia não lê texto",             test_energia_nao_tenta_ler_texto),
        ("silêncio junta trechos colados",   test_silencio_junta_trechos_colados),
        ("silêncio com gagueira: só a repetição", test_silencio_com_gagueira_tira_so_a_repeticao),
        ("silêncio com gagueira: anáfora fica",   test_silencio_com_gagueira_deixa_a_anafora_inteira),
        ("silêncio não come palavra curta",       test_silencio_nao_come_palavra_curta_entre_vaos_finos),
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


if __name__ == "__main__":
    sys.exit(main())
