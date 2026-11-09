---
name: faxina
description: >
  Varredura periódica do sistema: arquiva o que envelheceu, avisa o que estourou o teto,
  procura segredo fora do lugar, arquivo órfão, ferramenta e skill fora da lista, decisões
  que se contradizem, "onde paramos" descolado do diário, e coisa no diário que nunca foi
  promovida pro contexto. Só relata; não apaga nem adiciona sozinha.
  Use quando o usuário chamar /faxina, disser "faz uma faxina", "o que está apodrecendo",
  "audita o sistema", "o que ficou velho", ou uma vez por mês.
---

# /faxina · o que envelheceu, em frases

O `/atualizar` guarda a sessão e não olha o resto. A faxina olha o resto. Rodada pelo usuário,
mensal ou quando quiser; **escopo limitado por rodada**; fecha com um relatório curto em frases,
não em tabela de auditoria. **Nunca apaga, nunca adiciona sozinha:** arquiva com etiqueta, avisa,
pergunta.

## Passo 0 · escopo da rodada

Perguntar em uma linha: *"faxina completa, ou só a memória (diário, decisões, recados), só o
contexto (`_contexto/`), ou só uma pasta de projeto?"*. Padrão, se ele disser "tanto faz":
memória + contexto. Pasta de projeto entra sempre que a rodada é completa.

Ler o `AGENTS.md` da raiz inteiro (mapa, tabela, mapa de pastas): é a régua de tudo abaixo.

## Os checks

Rodar os que couberem no escopo. Cada um vira no máximo duas frases no relatório, e só aparece se
achou algo. "Nada encontrado" some.

1. **Arquivar o que passou de 90 dias.** Diário: `_memoria/diario/AAAA-MM-DD*.md` com data
   anterior a hoje menos 90 dias vai pra `_memoria/arquivo/AAAA/` (mover, `git mv` se houver git).
   Decisões: entrada com mais de 90 dias **que já foi substituída** (alguma entrada mais nova diz
   `Substitui: <data dela>`) vai pra `_memoria/arquivo/AAAA/decisoes-substituidas.md`; decisão
   ativa fica, por mais velha que seja. Recado com mais de 30 dias sem tratar: avisar, não mover.
   Mostrar a lista e mover só com o sim.
2. **Teto dos arquivos que carregam toda sessão.** `AGENTS.md` (teto na primeira linha) e os três
   do boot (teto no comentário do topo). Estourou: dizer quanto e propor o corte (o que virar
   ponteiro pra arquivo próprio). Não cortar sozinho.
3. **Segredo fora do lugar.** `grep -rIl` por `sk-`, `ghp_`, `AKIA`, `-----BEGIN`, `password=`,
   `token=`, `api_key`, e CPF (`\d{3}\.\d{3}\.\d{3}-\d{2}`) em tudo que não é `.env`. Avisar arquivo
   e linha. Nunca apagar.
4. **O diário rende?** Contar os arquivos de diário dos últimos 30 dias e, no mesmo período, o que
   mudou em `_contexto/`, `decisoes.md` e nos `andamento.md` (`git log --since=30.days --name-only`
   ou data de modificação). Diário crescendo e nada mais se movendo (na casa de 3:1) é sinal de
   fabricar registro que ninguém promove. Dizer isso em uma frase, como heurística.
5. **Órfãos.** Arquivo em `_contexto/`, `_memoria/` ou na raiz que nenhuma linha do `AGENTS.md`
   (mapa, tabela, gatilhos, mapa de pastas) cita, e pasta de trabalho que não está no mapa de
   pastas. Perguntar: entra no mapa ou vai pro arquivo?
6. **Skills fora da lista.** Toda `SKILL.md` em `.claude/skills/` (raiz e pastas de projeto) tem
   `name` e `description`? Skill de pasta de projeto está citada no `AGENTS.md` daquela pasta?
7. **Integração fora do `integracoes.md`.** Cruzar `claude mcp list` (se houver), `.mcp.json` e
   os nomes de variável do `.env` (só o nome, nunca o valor) com as linhas de
   `_contexto/integracoes.md`. O que está ligado e não está na tabela: **perguntar** se adiciona.
   Linha com "última checagem" há mais de 90 dias: perguntar se ainda usa.
8. **Decisões que se contradizem.** Ler `_memoria/decisoes.md` inteiro e apontar pares que dizem
   coisas opostas sem `Substitui:`. Sugerir a entrada nova que resolve ("substitui: <data>").
9. **`agora.md` × diário recente.** O "onde paramos" bate com as últimas 3 entradas do diário?
   Pendência do `agora.md` que o diário diz que foi feita? Apontar, propor a correção.
10. **Frescor.** Pra cada arquivo com regra de leitura/escrita (os de `_contexto/`, `marca/`,
    `decisoes.md`, e `contexto.md`/`andamento.md` de cada pasta de projeto), a data da última
    modificação contra a data do último diário. Muito longe (mais de 60 dias, com sessões
    acontecendo) é candidato a apodrecido: perguntar se ainda vale.
11. **Memória → contexto.** Coisa que aparece repetida no diário ou nas decisões (mesmo cliente,
    mesma ferramenta, mesma pessoa, 3 vezes ou mais) e não está no `_contexto/` nem no
    `contexto.md` do projeto certo. Propor a promoção (a linha pronta), aplicar só com o sim.
12b. **Automações × sinais de vida.** Cruzar `_contexto/automacoes.md` (se existir) com os
    rastros reais: recados e diários assinados pela origem de cada rotina nos últimos 30 dias.
    Rotina registrada sem nenhum sinal no período: avisar ("pode ter quebrado em silêncio; a
    coluna 'como saber se quebrou' diz onde conferir"). Sinal chegando de origem que NÃO está
    no registro: avisar ("automação fantasma; registrar ou desligar"). Só relata.
12. **Memória do agente → sistema.** Ler a auto-memória do Claude Code deste projeto
    (`~/.claude/projects/<pasta-codificada>/memory/`) e a do Codex, se existirem. O que for **fato
    de negócio** (cliente, preço, preferência de trabalho) mora no sistema, não no agente: sugerir
    trazer, com a linha e o destino pela tabela. Nunca trazer sozinha. O que for só jeito da
    máquina fica lá.

## O relatório

Frases, agrupadas por "o que fiz" / "o que precisa de você" / "o que só avisei". Exemplo:

> Faxina de setembro, escopo memória + contexto.
>
> **Fiz:** arquivei 14 diários de antes de junho em `_memoria/arquivo/2026/`.
> **Precisa de você:** o `agora.md` diz que a proposta da Acme está pendente, mas o diário de
> terça diz que foi enviada; corrijo? · o Canva aparece ligado e não está no `integracoes.md`;
> adiciono? · duas decisões sobre parcelamento se contradizem (12/06 e 03/08); a de agosto
> substitui a de junho?
> **Avisei:** o `empresa.md` está com 71 linhas, teto 60. Dá pra tirar a lista de clientes dali
> e deixar um ponteiro pra `clientes/`.

Tudo o que precisa de sim é aplicado só depois do sim, um item por vez ou "aplica tudo".

## Regras

- Nunca apagar. Arquivar é mover pra `_memoria/arquivo/AAAA/` com a lista mostrada antes.
- Nunca adicionar ferramenta, linha de contexto ou promoção sem o sim.
- Escopo limitado: uma rodada não precisa rodar os 12 checks. Melhor 5 bem feitos.
- Relatório curto. Sistema em dia rende um relatório de três linhas, e é isso.
