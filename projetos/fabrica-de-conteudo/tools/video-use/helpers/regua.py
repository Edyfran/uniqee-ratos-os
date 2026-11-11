"""A régua de desenho, do lado da aula.

Importada do `checa_board.mjs` do vídeo de quadro, que já a tinha resolvida. É o
movimento 4 do `tools/quadro/UNIFICACAO.md`, e o combinado lá está inteiro aqui,
com as duas correções que o fio acertou:

**Bloco de código e captura NÃO contam como desenho.** Sem essa exclusão um board
marcou 29% de "desenho" que era quase só janela, e o dono voltou dizendo que
estava tudo texto. Do lado da aula é pior: um `rows` de comandos passaria como
100% desenho — a forma mais textual do catálogo virando a mais bem avaliada.

**A régua vale por AULA, não por card.** Três das sete formas são texto por
natureza: `quote` é uma frase, `term` é palavra mais definição, `rows` é lista.
Elas existem porque a fala às vezes não tem o que desenhar. Reprovar card a card
mataria as três; reprovar a aula pega o que interessa — a aula que virou slide.

O teto de dois textos por cena vale por card, e sem discussão: é regra do dono,
cobrada três vezes.
"""
from __future__ import annotations

from dataclasses import dataclass

# Proporção mínima de desenho numa aula. Abaixo disto ela virou slide.
MIN_DESENHO = 0.25
# Por cena: rótulo e frase. `janela` fica de fora da conta pelo mesmo motivo que
# não conta como desenho — ela é texto num quadro escuro.
MAX_TEXTOS = 2

# As formas que são texto por natureza. Não ganham isenção — a régua por aula já
# as protege. Estão nomeadas para o relatório poder explicar o número.
FORMAS_DE_TEXTO = {"quote", "term", "rows"}

# O que parece desenho e não é.
SO_TEXTO = {"janela", "codigo", "img", "shot", "captura"}


@dataclass(frozen=True)
class Veredito:
    passou: bool
    proporcao: float
    desenhos: int
    total: int
    reclamacoes: list[str]

    def __str__(self) -> str:
        cabeca = (f"desenho: {self.desenhos}/{self.total} "
                  f"({self.proporcao:.0%}, mínimo {MIN_DESENHO:.0%})")
        return cabeca + ("" if self.passou else "\n  " + "\n  ".join(self.reclamacoes))


def _itens(card: dict) -> list[dict]:
    """O que aparece na tela deste card, achatado."""
    saida = []
    for chave in ("itens", "items", "elementos", "beats"):
        for it in card.get(chave) or []:
            saida.append(it if isinstance(it, dict) else {"tipo": str(it)})
    return saida


def _e_desenho(item: dict) -> bool:
    tipo = str(item.get("tipo") or item.get("el") or item.get("marca") or "").lower()
    if not tipo:
        return False
    return tipo not in SO_TEXTO


def _textos(card: dict) -> int:
    return sum(1 for c in ("rotulo", "frase", "cap_ch", "h", "cap", "sub", "q")
               if card.get(c))


def confere(cards: list[dict]) -> Veredito:
    """A aula inteira passa na régua?

    `cards` é a lista de explicadores de uma aula — o que o plano chama de
    `overlays`.
    """
    desenhos = total = 0
    reclamacoes = []

    for i, card in enumerate(cards):
        itens = _itens(card)
        total += len(itens)
        desenhos += sum(1 for it in itens if _e_desenho(it))

        n = _textos(card)
        if n > MAX_TEXTOS:
            forma = card.get("scene", f"card {i}")
            reclamacoes.append(
                f"{forma}: {n} textos numa cena só (teto {MAX_TEXTOS}) — "
                f"o card virou parágrafo"
            )

    proporcao = (desenhos / total) if total else 0.0
    if total and proporcao < MIN_DESENHO:
        so_texto = sum(1 for c in cards if c.get("scene") in FORMAS_DE_TEXTO)
        reclamacoes.insert(0, (
            f"a aula tem {proporcao:.0%} de desenho, abaixo de {MIN_DESENHO:.0%}"
            + (f" — {so_texto} dos {len(cards)} cards são forma de texto "
               f"({', '.join(sorted(FORMAS_DE_TEXTO))}); alterne com forma que desenha"
               if so_texto else "")
        ))

    return Veredito(not reclamacoes, proporcao, desenhos, total, reclamacoes)
