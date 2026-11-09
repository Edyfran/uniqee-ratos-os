---
name: iniciar
description: >
  Abre a sessão de trabalho: puxa o que mudou no GitHub, carrega o contexto do negócio,
  anuncia recados deixados por robôs ou por outras pessoas, resume o que outra origem
  escreveu hoje e diz onde você parou. Só lê, nunca escreve.
  Use no começo de cada sessão, quando o usuário chamar /iniciar, ou disser "bora",
  "onde a gente parou", "o que tem pra hoje", "começar".
---

# /iniciar · abrir a sessão

**Esta skill só lê.** Quem escreve é o `/atualizar`, no fim. Quem manda pro GitHub é o `/syncar`.
O `AGENTS.md` já fez o boot (os três arquivos); aqui é o ritual completo por cima dele.

Tudo abaixo roda em silêncio. O usuário vê só o resumo do fim.

## 1. Puxar o que mudou fora daqui

Se a pasta tem git com remoto (`git remote get-url origin` responde), trazer o que está lá antes
de ler qualquer memória, senão você lê uma versão velha:

```bash
git pull --ff-only 2>&1
```

- Deu certo ou "already up to date": segue.
- Falhou porque este computador e o GitHub divergiram: **não resolver aqui**. Seguir com o que está
  no disco e avisar no resumo, em uma linha: *"seu sistema mudou em outro lugar também; quando
  quiser, rodo o `/syncar` pra juntar as duas versões com segurança."*
- Sem internet: seguir com o disco, avisar em uma linha.
- Sem git ou sem remoto: nada a fazer, não comentar.

## 2. Conferir que o sistema foi configurado

Se `_contexto/empresa.md`, `_contexto/preferencias.md` ou `_contexto/agora.md` tiver
`<!-- NOT CONFIGURED -->` (ou não existir), parar aqui:

> "O sistema ainda não foi configurado. Rode `/setup` pra eu aprender sobre o seu negócio, leva
> uns 5 minutos. Depois disso o `/iniciar` funciona completo."

## 3. Ler o que o resumo precisa

Os três do boot (`empresa.md`, `preferencias.md`, `agora.md`) e mais `_contexto/estrategia.md`
(só pra linha do foco). Nada além disso: o resto do sistema se lê quando a sessão pedir, pelo
mapa do `AGENTS.md`.

## 4. Recados

Listar `_memoria/recados/*.md`. Pra cada um, ler as três primeiras linhas (`de:`, `quando:`,
`precisa de ação:`) e o assunto. Não apagar, não responder, não tratar: só anunciar. Quem trata é
o usuário na sessão; o `/atualizar` apaga o que foi tratado.

## 5. Diário de hoje escrito por outra origem

```bash
cat .origem 2>/dev/null
ls _memoria/diario/$(date +%Y-%m-%d)-*.md 2>/dev/null
```

Todo arquivo de hoje com sufixo diferente da origem deste computador (ou qualquer sufixo, se a
origem daqui é `dono`) foi escrito por outra máquina, outra pessoa ou um robô. Ler e resumir cada
um **em uma frase**. O diário de ontem não entra: o `agora.md` já cobre o "onde paramos".

## 6. Idade do "onde paramos"

```bash
git log -1 --format=%cs -- _contexto/agora.md 2>/dev/null || stat -f %Sm -t %Y-%m-%d _contexto/agora.md
```

Se faz mais de 7 dias, uma linha no resumo: *"faz N dias que não atualizamos o onde-paramos; o que
está ali pode estar velho."* Sem drama, sem repetir na mesma sessão.

## 7. Última decisão recente

Se a última entrada de `_memoria/decisoes.md` tem menos de 7 dias, citar em uma linha. É o que
evita refazer uma discussão que já aconteceu.

## 8. O resumo

Até 8 linhas, direto, sem "Olá! Fico feliz em ajudar!". Não listar os arquivos lidos.

```
Contexto carregado.

**Negócio:** [nome e o que faz, em uma linha]
**Foco agora:** [prioridade principal de estrategia.md; omitir se vazio]
**Onde paramos:** [de agora.md]
**Pendências:** [até 3 itens de agora.md; omitir se não houver]
**Recados:** [N recados: "de X, sobre Y (precisa de ação)"; omitir se zero]
**Hoje, por outra origem:** [uma frase por arquivo; omitir se nenhum]
**Lembretes:** [uma preferência importante, ex: "sem travessão", "tratar por tu"]
[aviso de idade do agora.md, ou de divergência com o GitHub, se houver]

O que você quer fazer hoje? Quando terminarmos, eu ofereço o /atualizar pra guardar o que rolou.
```

Depois do resumo, esperar o usuário.

## Regras

- Só lê. Nada de criar, apagar ou editar arquivo nesta skill.
- Tom direto. Sem jargão de git na tela ("fast-forward", "rebase"); falar "juntar as versões".
- Recado se anuncia inteiro em uma linha; o conteúdo completo só se o usuário pedir.
- Sistema recém-configurado: o resumo é curto e é isso. Não inventar pendência pra parecer útil.
