---
name: ajustar-arte
description: >
  Ajusta a arte de uma peça da Uniqee (normalmente gerada no ChatGPT) pro tamanho exato de
  impressão: PNG em 300 dpi pra caneca (21 x 9,8 cm), azulejo 15 (15,7 x 15,7 cm), azulejo 20
  (20,7 x 20,7 cm) ou outra medida, preenchendo ou encaixando a imagem e avisando quando a
  resolução não dá pra imprimir bem. Use sempre que o Edyfran chamar /ajustar-arte ou disser
  "ajusta essa arte pra caneca", "deixa no tamanho do azulejo", "prepara pra imprimir", "coloca no
  tamanho da peça", "a arte ficou pequena", ou mandar uma imagem dizendo em que peça ela vai.
---

# Ajustar arte pra peça

A arte nasce no ChatGPT e quase nunca vem no tamanho nem na proporção da peça. Esta skill entrega o
PNG pronto pra abrir no Corel. O Corel espelha na hora da impressão, então **aqui nunca se espelha**.

## Antes de começar

Ler `_contexto/preferencias.md` (como falar com o Edyfran).

## Medidas das peças

Já com a sobra, são o tamanho final do arquivo:

| peça | `--peca` | tamanho |
|---|---|---|
| Caneca | `caneca` | 21 x 9,8 cm |
| Azulejo 15x15 | `azulejo15` | 15,7 x 15,7 cm |
| Azulejo 20x20 | `azulejo20` | 20,7 x 20,7 cm |

Peça fora da lista (camiseta, almofada, squeeze): pedir a medida ao Edyfran e usar `--largura` e
`--altura` em cm. Ao final, perguntar se quer guardar essa medida na lista acima (e no script, no
dicionário `PECAS`).

## Passo a passo

1. **Receber a imagem e a peça.** Se a imagem veio colada na conversa e não existe como arquivo,
   pedir que ele salve na pasta `pedidos/artes/` e diga o nome.
2. **Olhar a imagem** antes de decidir o encaixe: a proporção e o que é importante nela (rosto, frase).
3. **Escolher o encaixe com ele**, sugerindo o que parece melhor:
   - `preencher`: ocupa a peça toda e corta a sobra. Bom pra fundo contínuo e padrão. Com `--foco`
     (`centro`, `topo`, `base`, `esquerda`, `direita`) escolhe-se o que preservar no corte. Antes,
     conferir se o corte não pega rosto nem frase.
   - `caber`: a imagem inteira aparece, e o que sobra vira fundo na cor `--fundo` (#RRGGBB; branco
     por padrão). Bom quando nada da arte pode sumir. Sugerir uma cor tirada da própria arte pra o
     fundo não ficar aparente.
4. **Rodar o script** (fica em `scripts/` dentro desta skill):
   ```bash
   python .claude/skills/ajustar-arte/scripts/ajustar.py "<imagem>" --peca caneca --modo preencher --saida "pedidos/artes/<arquivo>.png"
   ```
   Nome do arquivo: `AAAA-MM-DD-<cliente-ou-tema>-<peca>.png`, minúsculas e sem acento
   (ex.: `2026-11-08-maria-caneca.png`). Se ele não disser o cliente, usar o tema da arte.
5. **Conferir o resultado:** abrir o PNG gerado e olhar se ficou certo (nada importante cortado,
   fundo combinando).
6. **Ler o aviso de qualidade** que o script imprime (resolução real no impresso):
   - **boa** (220 dpi ou mais): pode imprimir.
   - **aceitável** (150 a 219): avisar que pode perder um pouco de nitidez.
   - **baixa** (abaixo de 150): avisar que vai sair borrada e sugerir ampliar a imagem antes
     (o Kittl, conectado na conta, faz isso com o upscale; pode custar crédito, então perguntar
     antes) ou gerar de novo no ChatGPT em resolução maior. Depois, rodar o ajuste com a imagem nova.
7. **Entregar** em uma ou duas linhas: onde salvou, o tamanho e a qualidade.

## Cuidados

- A pasta `pedidos/` fica fora do git, porque a arte costuma ter foto de cliente. Não copiar essas
  artes pra outro lugar nem usar em post sem o Edyfran pedir.
- Nunca sobrescrever a imagem original: a saída é sempre um arquivo novo.
- O script precisa do Pillow (instalado em 2026-11-08). Se der erro de módulo faltando, instalar com
  `python -m pip install --user pillow`, avisando antes.
