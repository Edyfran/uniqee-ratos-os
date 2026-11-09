---
name: atualizar
description: >
  Fecha a sessão guardando o que aconteceu no lugar certo: diário do dia, onde paramos,
  decisões e os arquivos de contexto, roteando pela tabela de destinos do AGENTS.md.
  Trabalha com o que está na conversa; não varre o sistema (isso é a /faxina).
  Use quando o usuário chamar /atualizar, disser "salva o que a gente fez", "fecha a
  sessão", "atualiza o contexto", "guarda isso", ou quando você ofereceu e ele aceitou.
  Não manda pro GitHub (isso é /syncar).
---

# /atualizar · guardar a sessão no lugar certo

Esta skill **decide onde cada informação mora e escreve**. Leve por contrato: a fonte é a
conversa que acabou de acontecer; o roteamento é a tabela de destinos do `AGENTS.md` (já
carregada); ela lê **só os destinos que vai tocar**. Nada de varrer o sistema atrás de coisa
velha: varredura é `/faxina`.

Robô, rotina e agente autônomo **não rodam esta skill**: eles escrevem direto no próprio diário
e em recados (o contrato do robô, `sistema/contrato-robo.md`).

## Passo 0 · silencioso

1. A ponte do Codex, idempotente, sem comentar: rodar o script da ponte que mora na pasta de
   scripts do sistema (linha "modelos e scripts" do mapa; numa instalação nova é
   `bash sistema/scripts/sync-ponte.sh` no Mac/Linux e
   `powershell -ExecutionPolicy Bypass -File sistema\scripts\sync-ponte.ps1` no Windows, inclusive
   dentro do Git Bash).
2. A origem deste computador: `cat .origem`. Se o arquivo não existe, perguntar antes de escrever
   qualquer coisa: *"Este é o seu computador principal? Se sim, eu escrevo o diário sem
   sufixo. Se é outro computador ou outra pessoa, me diz um nome curto pra ele (ex: notebook,
   socio, escritorio)."* Criar `.origem` com `dono` ou com o nome (minúsculas, sem espaço). O arquivo fica
   fora do git.

## Passo 1 · separar o que tem valor depois que a sessão terminar

Olhar a conversa inteira e listar, em rascunho, cada item que vale guardar. O que costuma aparecer:

- o que foi feito (entregável criado, arquivo salvo, tarefa concluída)
- decisão (escolheu um caminho, descartou outro, mudou de ideia, fechou preço, definiu regra)
- fato novo do negócio (cliente, serviço, equipe, preço, mercado)
- mudança de rumo, foco ou meta
- correção do jeito de trabalhar ("não faça mais isso", "prefiro assim"), inclusive as que você
  respondeu "anotado, salvo no fim"
- ferramenta nova, acesso novo, ou algo que você tentou e não alcançou
- onde alguma coisa passou a estar hospedada
- pendência que ficou em aberto, e pendência que foi resolvida
- pessoa ou empresa que apareceu de novo (não cliente, não time)
- recado que foi tratado nesta sessão
- material bruto que chegou (transcrição, PDF, email) e ainda não foi destilado

**Não entra:** pergunta solta, teste, conversa sem ação, tarefa trivial. Guardar demais é tão ruim
quanto guardar de menos: em três meses ninguém acha nada.

Sessão inteira trivial: dizer *"nada desta sessão precisa ser guardado; seu sistema já está em dia"*
e parar.

## Passo 2 · rotear pela tabela de destinos

Pra cada item, achar a linha da tabela "aconteceu X, escreve em Y" do `AGENTS.md`. **A tabela de
lá vence o que está escrito aqui**: é o que faz o sistema seguir funcionando quando o usuário
renomeia uma pasta.

- Cabe claro numa linha: vai pra lá.
- Cabe em duas: a mais específica, e dizer qual escolheu. Nunca a mesma informação em dois
  arquivos (duplicata é o que faz os dois envelhecerem torto).
- Não cabe em nenhuma: **perguntar**. Nunca inventar gaveta nem destino em silêncio. Se o usuário
  topar criar um lugar novo, criar **e** acrescentar a linha na tabela do `AGENTS.md` junto.

Se a sessão trabalhou dentro de uma pasta de projeto, o `andamento.md` dela entra na lista.

## Passo 3 · ler só os destinos que vai tocar

Dois a quatro arquivos pequenos, direcionados. Ler antes de escrever, sempre: é assim que se evita
duplicar linha e contradizer o que já está lá.

## Passo 4 · mostrar o plano, uma vez

Uma mensagem só, no formato "arquivo → o que vai entrar" (as linhas de verdade, não um resumo):

> Vou guardar assim:
> - `_memoria/diario/2026-09-08.md` → 3 linhas: proposta da Acme enviada; ...
> - `_contexto/agora.md` → onde paramos: ... · pendência "orçamento gráfica" **sai** (feito)
> - `_memoria/decisoes.md` → "2026-09-08 (você) [acme]: proposta em 3 parcelas. Por quê: ..."
> - `_contexto/integracoes.md` → linha nova: Canva, ligada por MCP
>
> Aplico?

Esperar o sim. Se o usuário quiser mudar algo, ajustar e aplicar.

## Passo 5 · escrever, nesta ordem

1. **Diário** (`_memoria/diario/AAAA-MM-DD.md` se a origem é `dono`; `AAAA-MM-DD-<origem>.md` se
   não). Criar a pasta se faltar. **Acrescentar no fim**, nunca reescrever. Um bloco por sessão:

   ```markdown
   ## HH:MM · [origem]
   - o que foi feito, cru, em poucas linhas
   - recado tratado: "assunto" (de quem)
   ```

2. **`_contexto/agora.md`**: reescreve (é destilado). "Onde paramos" é a última coisa em
   andamento. Pendência resolvida **sai com motivo dito na resposta** (feito / virou projeto /
   mandaram soltar), nunca some em silêncio. "Quente agora" é o que está ativo esta semana. O que
   passou de ~30 dias sai. Decisão não vai aqui.

3. **`andamento.md` da pasta de projeto** em que a sessão trabalhou: reescrever a seção "onde
   está" com a data de hoje; pendências do projeto seguem a mesma regra do `agora.md`.

4. **`_memoria/decisoes.md`**: acrescentar no fim, no formato do próprio arquivo (data, quem, projeto
   se houver, a decisão, o porquê). Quando muda uma decisão anterior, `Substitui: <data>`; a antiga
   fica onde está. Nunca editar linha velha.

5. **`_contexto/`** (`empresa.md`, `estrategia.md`, `preferencias.md`, `integracoes.md`,
   `infra.md`, `marca/`, `pessoas/<nome>.md`): acrescentar a linha na seção certa, sem reformatar o
   arquivo. Antes de cada linha, o **checklist das 4 doenças**:
   - **duplicata:** já existe linha dizendo isso? Então não escreve.
   - **contradição:** a linha nova contradiz uma antiga? Então a antiga sai e você diz isso na resposta.
   - **vencido:** tem linha com prazo que já passou? Marcar como vencida e perguntar se sai.
   - **data relativa:** "semana que vem", "mês passado" viram data absoluta (AAAA-MM-DD).
   Em `integracoes.md`, atualizar a coluna "última checagem" do que foi usado hoje.
   `pessoas/<nome>.md` nasce quando a mesma pessoa ou empresa apareceu em mais de uma sessão
   (conferir no diário); a pasta nasce no primeiro arquivo.
   Arquivo de boot que passou do teto declarado no topo: escrever mesmo assim e avisar em uma linha.

6. **Recados tratados:** apagar o arquivo em `_memoria/recados/` (o registro do que foi feito já
   está no diário).

## Passo 6 · fechar

Dizer o que escreveu onde, em poucas linhas:

> Guardado: diário (3 linhas), agora.md (onde paramos + 1 pendência resolvida), 1 decisão,
> integracoes.md (+Canva).

Só ofereça o `/syncar` se a seção 8 do `AGENTS.md` diz que este sistema está no GitHub (o `/syncar`
escreve essa linha quando liga). Aí, na mesma mensagem: *"Quer mandar pro GitHub? É só dizer
'synca'."* Sem a linha, não falar de GitHub.

## Regras

- Não mexe no GitHub. Não varre o sistema. Não relê o que não vai tocar.
- Nunca reformatar arquivo inteiro. Nunca reescrever arquivo cujo modo é acrescentar (diário,
  decisões). Nunca apagar linha sem dizer.
- Não inventar informação que não apareceu na conversa.
- Em dúvida sobre o destino, pergunta. Em dúvida se vale guardar, não guarda.
- Tom direto, sem diagnóstico inflado: sistema recém-configurado costuma estar em dia.
