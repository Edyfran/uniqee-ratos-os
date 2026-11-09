# Atualizar o seu RatosOS

**Pra você (humano):** baixe o kit novo na plataforma, descompacte **ao lado** da pasta do seu
sistema (nunca por cima), abra o seu agente (Claude Code ou Codex) **dentro da pasta do seu
sistema** e diga:

> leia `../<pasta-do-kit-novo>/sistema/changelog/COMO-ATUALIZAR.md` e faz o que está escrito

Se o seu sistema te atende como está, **não precisa atualizar.** Nada abaixo é obrigatório.

---

<!-- Daqui pra baixo é instrução pro agente. -->

## Como você (agente) se comporta aqui

**A casa do usuário manda.** O kit novo é sugestão; a instalação dele é a verdade. Você compara,
propõe, nunca sobrescreve, e adapta tudo aos nomes que ele usa (se a memória dele se chama
`cerebro/`, é `cerebro/` no papel também).

0. **Você não aplica nada sem um sim explícito.** Este arquivo tem pontos marcados **PARE**: neles
   você termina a mensagem e espera a resposta. Não encadeie fases, não "adiante" mudanças, não
   presuma que ele quer tudo. "Faz tudo, decide tu" vale só pro grupo de 3 mudanças em curso.
1. **A primeira mensagem da conversa é só esta, e nada mais:** "Se o seu sistema te atende como
   está, não precisa atualizar. Quer ver o que a versão nova traz, e escolher o que entra?"
   **PARE.**
2. **Cópia de segurança antes de qualquer mudança, sempre a pasta inteira:** `cp -R` da pasta
   pra `<pasta>-antes-da-<versão>-<data>` (ao lado, fora dela), conferindo a contagem de arquivos
   dos dois lados. Commit de git **não substitui** essa cópia: o `.gitignore` da 1.0 esconde as
   pastas de trabalho, então um commit "antes" não guarda o que mais importa. Se a pasta tem git,
   fazer o commit também (`git add -A && git commit -m "antes de atualizar pra <versão>"`), como
   segundo colete. Dizer onde a cópia está.
3. **No máximo 3 mudanças por rodada.** Terminou as três, pergunta se segue. "Faz tudo, decide tu"
   vale pra aplicar; não vale pra apagar nada nem pra mexer em arquivo que ele escreveu.
4. **Antes/depois na tela** de todo arquivo que muda, antes de mudar.
5. **Nunca apagar.** Arquivo absorvido por outro só sai depois de conferir que o conteúdo chegou
   inteiro; na dúvida, renomear pra `<nome>-antigo.md` e avisar.
6. **Fale como gente.** Sem "merge", "rebase", "diff", "commit" na tela: "cópia de segurança",
   "salvar", "juntar os dois textos".
7. **Escreva na voz dele:** ler o `preferencias.md` dele antes de escrever qualquer texto novo.
8. **A atualização mexe só dentro da pasta dele.** Nada de criar repositório no GitHub, instalar
   conector (MCP), mexer em configuração do agente ou da máquina, abrir programa. Isso não é
   atualização; se ele quiser, é outra conversa, com o comando certo (`/syncar`, `/setup`).
   "Faz tudo, decide tu" não cobre nada disso.

## O procedimento

### 1. Descobrir de onde ele parte

```bash
cat .ratosos 2>/dev/null || echo "sem .ratosos"
ls sistema/changelog/ 2>/dev/null || echo "sem changelog"
ls ../<kit-novo>/sistema/changelog/
```

- Sem `.ratosos` e sem `sistema/changelog/`: é a **1.0**. Tudo do `2.0.md` (e dos seguintes)
  está por aplicar.
- Com changelog: o que existe no kit novo e **falta** na instalação é o que falta aplicar, em
  ordem de versão. Funciona pra quem pulou versões.
- Dentro de uma versão, o que já foi aplicado ou recusado está registrado no `decisoes.md` dele
  (entradas com `[atualizacao]`). Ler antes de propor: não oferecer de novo o que ele recusou,
  a não ser que ele peça.

### 2. Reconhecer a casa, sem presumir nome

`ls -a`, `find . -maxdepth 2 -type d`, `ls .claude/skills/`, `wc -l AGENTS.md` (ou `CLAUDE.md`,
se a instalação for anterior ao `AGENTS.md`). Descobrir qual pasta cumpre qual papel **pelo
conteúdo**: memória do negócio (tem `empresa.md`), marca (tem `design-guide.md`), scripts e
modelos, material cru. Anotar o mapa dele; toda mudança abaixo é escrita com os nomes dele.

### 3. Ler o(s) arquivo(s) de versão que faltam

Cada mudança tem cinco campos: **o que é · por quê · te afeta se (o check) · como aplicar · como
testar**. Rodar o check de cada uma na instalação dele. As que o check diz "não te afeta" somem
da lista. As que sobram, apresentar **rankeadas como estão no arquivo** (valor primeiro), em
linguagem de gente, e propor as 3 primeiras.

Apresentadas as 3, **PARE** e espere ele dizer quais entram.

### 4. Aplicar, uma por vez

Pra cada mudança aceita: mostrar o antes/depois de cada arquivo que muda e **PARE** → com o sim,
aplicar → rodar o "como testar" → uma linha no
`decisoes.md` dele: `- **AAAA-MM-DD** (agente) [atualizacao]: aplicada "<nome da mudança>" da
versão X. Por quê: <motivo dele, se disse>`. Recusada: mesma linha com "recusada".

Terminou o grupo de 3: dizer o que mudou, listar o que ainda falta, perguntar se segue. **PARE.**

### 5. Fechar a rodada

Quando todas as mudanças da versão estiverem aplicadas ou recusadas: escrever a versão no
`.ratosos` (uma linha) e copiar a pasta `sistema/changelog/` do kit novo pra dentro da instalação
(é assim que a próxima versão sabe de onde ele parte). Se sobrou mudança pra próxima rodada,
`.ratosos` fica como estava e a rodada seguinte continua daqui.

Se a seção 8 do `AGENTS.md` dele diz que o sistema está no GitHub: oferecer sincronizar. Depois, dizer em três linhas o
que mudou e o que ficou de fora.
