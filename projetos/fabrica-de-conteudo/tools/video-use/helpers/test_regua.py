"""Auto-teste da régua de desenho. Um comando, nada renderiza.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_regua.py

Os dois casos que decidem o desenho da régua vêm do fio de unificação: um board
marcou 29% de desenho que era quase só janela, e três das sete formas da aula são
texto por natureza.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import regua as rg


def card(scene="hub", itens=(), **extra):
    return {"scene": scene, "itens": [{"tipo": t} for t in itens], **extra}


def test_aula_com_desenho_passa():
    aula = [card("hub", ["rede", "robo", "nuvem"]), card("stepper", ["barra", "seta"])]
    assert rg.confere(aula).passou


def test_aula_so_de_texto_reprova():
    """O defeito que a régua existe para pegar: a aula virou slide."""
    aula = [card("rows", ["janela", "janela"]), card("quote", ["janela"])]
    v = rg.confere(aula)
    assert not v.passou
    assert "abaixo de 25%" in str(v)


def test_janela_nao_conta_como_desenho():
    """Um board marcou 29% de desenho que era quase só janela, e o dono voltou
    dizendo que estava tudo texto."""
    so_janela = rg.confere([card("rows", ["janela"] * 10)])
    assert not so_janela.passou
    assert so_janela.desenhos == 0, "a janela foi contada como desenho"


def test_um_rows_de_comandos_nao_passa_como_100_por_cento():
    """A forma mais textual do catálogo não pode virar a mais bem avaliada."""
    v = rg.confere([card("rows", ["codigo", "codigo", "codigo"])])
    assert v.proporcao == 0.0


def test_a_regua_vale_por_aula_e_nao_por_card():
    """`quote` é uma frase e nada mais. Reprovar card a card mataria três das
    sete formas; reprovar a aula pega o que interessa."""
    aula = [card("hub", ["rede", "robo", "nuvem", "leque"]),
            card("quote", [])]                      # sem desenho nenhum, e tudo bem
    assert rg.confere(aula).passou, "a régua matou um quote legítimo"


def test_uma_forma_de_texto_sozinha_ainda_reprova():
    v = rg.confere([card("quote", ["janela"])])
    assert not v.passou
    assert "forma de texto" in str(v), "o erro não explica de onde vem o número"


def test_teto_de_dois_textos_por_cena():
    v = rg.confere([card("hub", ["rede", "robo"],
                         cap_ch="Bloco 3", h="um endpoint", cap="mil apps")])
    assert not v.passou
    assert "virou parágrafo" in str(v)


def test_dois_textos_passam():
    v = rg.confere([card("hub", ["rede", "robo"], cap_ch="Bloco 3", h="um endpoint")])
    assert v.passou


def test_o_teto_de_texto_vale_por_card_mesmo_numa_aula_boa():
    """A régua de proporção é por aula; o teto de texto não — é regra do dono."""
    aula = [card("hub", ["rede", "robo", "nuvem", "leque", "seta"]),
            card("stat", [], cap_ch="a", h="b", cap="c", sub="d")]
    assert not rg.confere(aula).passou


def test_aula_vazia_nao_estoura():
    assert rg.confere([]).passou


def test_o_relatorio_diz_o_numero():
    v = rg.confere([card("hub", ["rede", "robo", "janela", "janela"])])
    assert "2/4" in str(v), f"o relatório não mostra a conta: {v}"


def main() -> int:
    casos = [
        ("aula com desenho passa",         test_aula_com_desenho_passa),
        ("aula só de texto reprova",       test_aula_so_de_texto_reprova),
        ("janela não conta",               test_janela_nao_conta_como_desenho),
        ("rows de comandos não é 100%",    test_um_rows_de_comandos_nao_passa_como_100_por_cento),
        ("régua vale por aula",            test_a_regua_vale_por_aula_e_nao_por_card),
        ("forma de texto sozinha reprova", test_uma_forma_de_texto_sozinha_ainda_reprova),
        ("teto de dois textos",            test_teto_de_dois_textos_por_cena),
        ("dois textos passam",             test_dois_textos_passam),
        ("teto vale por card",             test_o_teto_de_texto_vale_por_card_mesmo_numa_aula_boa),
        ("aula vazia não estoura",         test_aula_vazia_nao_estoura),
        ("o relatório diz o número",       test_o_relatorio_diz_o_numero),
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
