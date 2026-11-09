---
name: compartilhar
description: >
  Prepara uma pasta de projeto pra sair daqui e ser aberta por outra pessoa (cliente, sócio,
  parceiro): completa o que ela herdava da raiz, leva as decisões dela, confere segredo,
  vira repositório git próprio e guia o convite no GitHub. Compartilhar é git, sem zip.
  Use quando o usuário chamar /compartilhar, disser "vou compartilhar essa pasta", "mandar
  a pasta do X pro cliente", "o sócio vai trabalhar nessa pasta", "dar acesso a essa pasta".
---

# /compartilhar · a pasta vira uma casa que se vira sozinha

Dentro do sistema, a pasta de projeto herda tudo da raiz por gatilho (`../../marca`,
`../../AGENTS.md`). Fora do sistema, esses caminhos quebram. Esta skill copia pra dentro o que a
pasta alcançava por fora, e faz dela um repositório próprio. **A raiz não viaja**; só a pasta.

## Passo 1 · qual pasta, pra quem, com que acesso

Confirmar a pasta (tem que ter `AGENTS.md`; se não tem, rodar antes o `/novo-projeto link`).
Perguntar pra quem vai e o que a pessoa vai fazer: só ler, ou trabalhar junto. Isso muda o final.

## Passo 2 · segredo não viaja

```bash
find <pasta> -name '.env*' -o -name '*.json' -o -name '*.yaml' | head
grep -rIl 'sk-\|ghp_\|AKIA\|-----BEGIN\|password=\|token=\|api_key' <pasta> 2>/dev/null
```

Achou chave, token ou senha: **parar**, mostrar onde, e resolver antes de seguir (mover pro `.env`
da raiz, que não viaja; a pasta só declara qual integração usa, não como autenticar). Sem o
usuário resolver, não seguir.

## Passo 3 · completar a pasta

Mostrar a lista do que vai entrar e aplicar depois do sim:

1. **Marca.** Se a pasta não tem `marca/` própria, criar `marca/design-guide.md` com um resumo do
   guia da raiz (cores, fontes, logo copiado pra dentro, tom com o cliente). Resumo, não cópia
   cega: o que a pasta usa.
2. **`AGENTS.md` da pasta.** Trocar os gatilhos `../../` pelos locais (`marca/`, a tabela curta
   abaixo). Primeira linha vira: **"Quem recebe esta pasta, abre esta pasta. Não a raiz de
   ninguém."** Acrescentar uma tabela de destinos mínima: trabalho → aqui · onde está e pendências
   → `andamento.md` · decisão → `decisoes.md` desta pasta · o que a pasta sabe do projeto →
   `contexto.md`. E uma linha de fim de sessão: "sessão que rendeu trabalho: atualize o
   `andamento.md` antes de salvar".
3. **Decisões do projeto.** Extrair de `_memoria/decisoes.md` da raiz as entradas marcadas com o
   nome deste projeto (`[acme]`) pra um `decisoes.md` dentro da pasta, mesmo formato. As da raiz
   ficam onde estão.
4. **Habilidades.** As que moram em `<pasta>/.claude/skills/` já viajam. Se a pasta depende de uma
   skill da raiz ou global, perguntar: copiar pra dentro (viaja) ou tirar a dependência. Skill
   global não vai junto, e prometer capacidade que não existe é pior que não ter.
5. **`CLAUDE.md`** com `@AGENTS.md` (já existe). **`.gitignore` fail-closed** da pasta: copiar o da
   raiz (é o mesmo modelo: nega tudo, libera texto, config, script, imagem, PDF; bloqueia `.env`).
6. **`contexto.md` e `andamento.md`** frescos: reler e apagar o que só faz sentido de dentro do
   sistema ("ver `_contexto/pessoas/...`" vira o conteúdo em si).

## Passo 4 · virar repositório próprio

De dentro da pasta:

```bash
git init && git branch -M main
git add -A && git commit -m "início (<origem>): pasta preparada pra compartilhar"
```

Na raiz do sistema, **a pasta passa a ser ignorada**: acrescentar `<pasta>/` no `.gitignore` da
raiz (repositório dentro de repositório vira um fantasma que quebra clone; a pasta continua no
lugar, só o git da raiz não olha mais pra ela). Atualizar a linha dela no mapa de pastas da raiz:
``· repositório próprio, compartilhada com [quem]``.

## Passo 5 · o convite

> "Agora crie um repositório **privado** em github.com/new (nome sugerido: `acme`), sem README,
> e me passa o link."

Com o link: `git remote add origin <link>` e `git push -u origin main`. Depois:

> "Subiu. Pra dar acesso: no GitHub, Settings → Collaborators → Add people, com o email ou usuário
> de [quem]. A pessoa abre a pasta no Claude Code ou no Codex e o sistema dela já lê o `AGENTS.md`
> daqui. Se vocês dois forem trabalhar nela, cada um sincroniza com o `/syncar` normal: ele puxa
> antes de mandar e assina com a origem de cada máquina."

## Regras

- Segredo dentro da pasta: parar e resolver antes de qualquer outra coisa.
- Nunca mover nem apagar nada na raiz; só a linha no `.gitignore` e no mapa.
- Não copiar a raiz inteira pra dentro: a pasta leva o que usa, resumido.
- Sem zip. O caminho de compartilhar é git, sempre.
