# Contrato do robô (rotina, cron, agente autônomo, subagente, outra pessoa ou computador)

Quem chega aqui pelo `AGENTS.md` (seção 6) vai escrever no sistema sem ser o dono numa conversa.
Estas regras existem pra duas coisas: a memória do dono não se bagunça sozinha, e dois escritores
nunca brigam pelo mesmo arquivo.

**Rotina lê muito e escreve pouco: o que ela escreve fica no diário e nos recados dela; criar arquivo
novo pode, reescrever o que existe não. Quem promove pra memória durável é o dono, pelo `/atualizar`.**

- Cada origem escreve só no próprio diário (`_memoria/diario/AAAA-MM-DD-<origem>.md`), assinado com o
  id dela. Duas origens nunca tocam o mesmo arquivo; conflito de sincronização fica impossível por desenho.
- O nome da origem desta máquina está em `.origem` (o `/setup` cria; fica fora do git). Sem esse
  arquivo, perguntar antes de escrever no diário. O dono escreve limpo, sem sufixo.
- Mudança em `_contexto/`, em `decisoes.md` ou em arquivo de trabalho alheio vira **recado**, não
  edição. Recado é um arquivo `_memoria/recados/AAAA-MM-DD-<origem>-<assunto>.md` que começa com
  `de:`, `quando:` e `precisa de ação: sim/não`. Tratou, apaga (ou leva pro diário se vale registro).
- Entregável ou rascunho novo a rotina cria direto, de preferência na pasta do projeto dela, e avisa
  por recado. Arquivo que ela mesma criou e mantém, ela reescreve à vontade.
- Toda rotina ligada tem uma linha em `_contexto/automacoes.md` (é o inventário do que roda
  sozinho). Rotina que não está lá não deveria estar rodando.
- Sessão sem gente na frente não gera memória durável sozinha.
