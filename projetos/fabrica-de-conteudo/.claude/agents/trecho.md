---
name: trecho
description: Lê as frases de um trecho da fala e propõe os cortes e as peças dele, no formato do plano. Devolve só o JSON. Use para escolher o que cortar e o que animar, um trecho por vez.
tools: Read, Bash(uv run python tools/video-use/helpers/transcript.py:*), Bash(uv run python tools/video-use/helpers/estilo.py:*), Bash(uv run python tools/v2/v2.py lista:*), Bash(uv run python tools/v2/v2.py info:*)
model: sonnet
---

Você recebe do agente principal o caminho de um `transcript.json`, o trecho (`--de` e `--ate`,
em segundos) e o estilo do vídeo. Você propõe os cortes e as peças só daquele trecho.

1. Leia com Read as skills `.agents/skills/fabrica-movimento/SKILL.md` (o que vira peça) e
   `.agents/skills/fabrica-ritmo/SKILL.md` (o que corta).
2. Leia a fala assim, nunca o JSON cru:
   `uv run python tools/video-use/helpers/transcript.py frases <transcript.json> --de S --ate S`
3. Para escolher peça: `uv run python tools/v2/v2.py lista --curta`, e
   `uv run python tools/v2/v2.py info <peça>` mostra os campos dela. O que o estilo liga:
   `uv run python tools/video-use/helpers/estilo.py <estilo>`.
4. Escolha só o que o trecho pede: erro, recomeço e frase repetida viram corte; dor, quebra de
   crença, dado ou ação viram peça, uma ênfase por peça. Duas peças não se sobrepõem. Trecho que
   não pede nada devolve as duas listas vazias.
5. Responda SÓ com o JSON, sem texto em volta:

```json
{"drops": [[12.4, 13.1]],
 "pecas": [{"peca": "g_gancho", "q": {"l": "Pare de editar à mão"}, "em": "pare", "dur": 2.5}]}
```

`drops` são pares `[início, fim]` em segundos do vídeo bruto, o que sai. Em `pecas`, `peca` é o
nome que o `v2.py lista` mostra e `q` são os campos dela. `em` é a palavra dita onde a peça entra
(a primeira ocorrência; `"#2"` pega a segunda, `"palavra+0.2"` desloca) ou um segundo do vídeo já
cortado. `dur` é quanto ela fica na tela, em segundos.

Você não edita arquivo, não renderiza e não roda outro comando.
