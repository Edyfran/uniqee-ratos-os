---
name: fabrica-composicao
description: Use ao decidir onde fica cada coisa no quadro 9:16 de um vídeo da Fábrica de Conteúdo com IA — tela dividida, rosto no cartão ou cheio, cena embaixo, tela cheia sem rosto, o fundo atrás do rosto, peça por cima. Também quando o usuário pedir para trocar ou recortar o fundo, ou reclamar de tela vazia, de rosto que some ou de cena mal enquadrada.
---

# Composição

Entre parênteses, onde a regra mora nesta pasta: o código que cobra ou o arquivo que a
define. *direção* marca a regra de direção de arte que nenhum código cobra: confira no
quadro.

## Tela dividida (reel editorial)

- No **vídeo do celular**, a tela dividida vem do `visual.json` (`dividida`, `cheia`, `rosto` por batida: veja `pauta-visual.md` na skill `fabrica-de-conteudo`). Nela a legenda termina acima do cabelo (y 1040 de 1920), nunca no rosto ou no peito; em `cheia` e `rosto` ela segue o estilo.

- Painel em cima, o rosto num cartão de cantos redondos embaixo (do y 1240 até o pé), com a
  cabeça passando da borda de cima do cartão (`e_editorial.html`; `reel_editorial.py`,
  `CARTAO`).
- **O cartão arredondado é só para rosto falando.** Ele existe para a cabeça sair da borda.
  Trecho `"quadro": "cartao"` sem `avatar` é recusado (`reel_editorial.py`, `confere`).
- A cabeça fora da borda e o rosto dentro do cartão saem do mesmo quadro do avatar
  (`reel_editorial.py`, topo).
- O rosto alterna entre o cartão e o quadro cheio (`"quadro": "cheio"`); a troca é corte seco
  (`e_editorial.html`, parâmetro `cenas`).

## Cena embaixo: 40/60

- Com cena (b-roll) embaixo, nada de cartão: a tela divide reta, painel 40 em cima e cena 60
  embaixo (`divide` na `base`), ou a cena entra grande, por cima do painel
  (`reel_editorial.py`, `confere`).
- Sem corte seco na costura: a cena sobe por cima do painel num degradê de 120 px, na linha
  dos 768 (`estilo.py`, `imagem.costura`).
- O assunto da cena fica no meio dos 60% de baixo, não no meio do quadro original: acerte o
  `foco` do trecho (`reel_editorial.py`, topo, campo `divide`).
- B-roll só quando o assunto pede. Reel sobre uma ferramenta é rosto, motion e captura; cena
  solta, sem ligação com a fala, deixa o vídeo sem pé nem cabeça (*direção*).

## O fundo atrás do rosto

- No cartão e no rosto cheio, atrás do avatar vai a placa do look do usuário na HeyGen
  (`imagem.fundo` no plano): o lugar como ele é, nítido, sem desfoque, na escala e na posição
  do avatar, para o corpo cair no lugar. Plano sem `imagem.fundo` é recusado, e placa que não
  cobre o quadro também (`reel_editorial.py`, `confere` e `cobre`). Sem placa, vale a do
  exemplo e o banco cobre cada trecho (`fabrica-de-conteudo`, regra 4).
- **Recorte de fundo**, trecho a trecho: `"fundo": "xadrez" | "painel:claro" |
  "painel:tinta" | "@<imagem ou vídeo>"` põe o rosto recortado sobre outra coisa. Só em
  trecho com rosto (`reel_editorial.py`, topo e `confere`). Pede o rosto em webm com alfa: o
  avatar gerado com fundo removível, ou o vídeo do celular exportado sem fundo.
- **Com banco de cenas, o fundo troca na fala.** Cada trecho de rosto leva o `fundo` de uma
  cena do banco (`"@../banco-de-cenas/<arquivo>"`, da pasta do vídeo): onde a voz nomeia um
  lugar ou uma coisa, a cena cujo `ilustra` casa com ela, trocando na palavra; no resto, a
  cena marcada "cenário atrás do rosto". Uma cena só atrás do vídeo inteiro desperdiça o
  banco, e a voz que diz "troca o fundo" sobre o mesmo fundo se contradiz (*direção*). A cena
  em vídeo dá a volta sozinha, e o corte do rosto não a reinicia (`reel_editorial.py`, `chao`
  e `_partes`).
- O vídeo do celular com o fundo dele não troca de fundo. O que dá é a palavra passar atrás
  da pessoa (`fabrica-legendas`).

## Tela cheia sem rosto

- Sem o rosto, a tela se enche. Precisa de pelo menos uma peça na largura toda (90% ou mais)
  (`reel_editorial.py`, `confere`). A captura vai grande, quase na largura toda, com zoom
  lento e grifo, e ganha camadas (etiqueta, número, seta, sticker) até não sobrar fundo
  (*direção*).
- O render mede: faixa vazia de mais de 300 px acima da legenda do Instagram, por mais de
  0,5 s, reprova. O `--seco` já avisa o que dá para prever (`reel_editorial.py`, `VAZIO_MAX`
  e `preve_vazios`).
- O que é pequeno demais para encher a tela vira tela dividida com o rosto (*direção*).

## Por cima, no sentido literal

- **Nada passa atrás da pessoa.** Ênfase vem de peso, cor e escala na camada de cima, nunca
  de profundidade. Só o estilo libera (`desenho.atras`), e a fábrica recusa peça em camadas
  ou card atrás nos outros (`estilo.py`; `fabrica.py`, `_peca` e `_direcao`).
- Três jeitos de pôr a informação, e eles se alternam (*direção*):
  - **painel**, quando o argumento depende de composição: fluxo, tabela, linha do tempo
    (no reel editorial, o cartão com o painel em cima);
  - **tela cheia**, na virada, quando o gráfico é a informação (`painel` na `base`);
  - **peça flutuante** sobre o rosto inteiro, para lista e número solto (peça com alfa sobre
    o `"quadro": "cheio"`).
- Dois painéis seguidos leem como apresentação de slides, e o rosto some tempo demais. Mas
  qual entra continua saindo do que aquele momento faz (*direção*).
- Painel que mostra terminal, código ou nome de arquivo interno é ruído para quem assiste
  (*direção*).

## Criativo

- Voz em off sobre cenas do banco, cada cena cobrindo o trecho da fala que ilustra. A
  legenda vai numa faixa: `faixa_criativo` no anúncio, `faixa` no `criativo-reel`
  (`estilo.py`; `criativo.py`, topo).
- Toda imagem funciona parada, como print. O assunto se lê em meio segundo: o elemento
  grande e visível, nunca o detalhe no canto (`docs/linguagem-do-criativo.md`, no módulo Cenas de Cinema).

## Antes de renderizar

```bash
uv run python tools/video-use/helpers/fabrica.py <plano.json> --seco
```

O `--seco` roda o `confere`: cartão sem rosto, fundo faltando, tela cheia sem peça, letra na
legenda do Instagram. Depois do render, olhe a folha de quadros (`folha-1fps.png`, na pasta
de trabalho do vídeo).
