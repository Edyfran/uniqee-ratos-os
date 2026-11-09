# Ratos OS 🐀

O sistema operacional do seu negócio, feito pelo [Ratos de IA](https://ratosdeia.com.br) pra alunos do curso **Ratos OS** (o Claude Code OS).

---

## Como instalar

O kit funciona no **Claude Code** e no **Codex** (Windows, Mac ou Linux). Você baixou um zip na
plataforma do curso; instalar é abrir a pasta e chamar o setup.

**1. Descompacte o zip** onde você guarda seus projetos. Essa pasta vai ser a casa do seu negócio
(pode renomear pra o nome dele, se quiser).

**2. Abra a pasta no seu agente:** no aplicativo do **Claude Code** (ou no VS Code com a
extensão), use "Abrir pasta" e escolha a pasta que você descompactou. No **Codex**, mesma coisa.

**3. Chame o setup:**
- No Claude Code: digite `/setup`
- No Codex (primeira vez): peça `leia e siga o arquivo .claude/skills/setup/SKILL.md`

> Prefere o terminal? Entrar na pasta e rodar `claude` (ou `codex`) dá no mesmo.

O agente vai te fazer algumas perguntas e configurar o sistema pro seu negócio. Em 5 minutos você tem tudo pronto, funcionando nos dois.

---

## O que vem no kit

**Skills prontas pra usar:**
- `/setup`: configura o sistema pro seu negócio (comece por aqui)
- `/iniciar`: abre a sessão: carrega o contexto, anuncia recados e diz onde você parou
- `/atualizar`: fecha a sessão: escreve o diário do dia, o "onde paramos", as decisões e o contexto, e diz o que escreveu onde
- `/syncar` (opcional): guarda uma cópia no GitHub e diz o que subiu. Quem não liga nunca ouve falar dele
- `/novo-projeto`: cria pasta de projeto ou cliente com contexto próprio
- `/mapear`: entrevista você sobre o dia a dia e cria skills personalizadas
- `/compartilhar`: prepara uma pasta de projeto pra sair daqui como repositório próprio (cliente, sócio)
- `/faxina`: varredura mensal: o que envelheceu, o que estourou o teto, o que está fora do lugar. Só relata
- `/carrossel` `/proposta-comercial` `/slide` `/publicar-site` `/analisar-dados` `/roteiro-post` `/email-profissional`: modelos prontos que o `/mapear` instala com a sua identidade

**A casa, depois do `/setup`:**

```
seu-negocio/
├── AGENTS.md        as regras, o boot, o mapa e a tabela de destinos (o cérebro, com teto de 180 linhas)
├── CLAUDE.md        uma linha: @AGENTS.md
├── _contexto/       o que o sistema sabe do negócio: empresa, preferências, foco, integrações, infra, marca/
├── _memoria/        o que aconteceu e por quê: diario/ (um arquivo por dia), decisoes.md, recados/
├── sistema/         o motor do kit: scripts e modelos. Você não precisa abrir
├── .claude/         as skills
└── clientes/ propostas/ conteudo/ ...   as pastas de trabalho, conforme o seu perfil
```

Dois comandos que você vai confundir no começo: `/iniciar` lê, `/atualizar` escreve.

**Se você já tinha a versão anterior do kit** (a que tinha `dados/` e `marca/` na raiz): não precisa
mudar nada se o seu sistema te atende. Quando quiser atualizar: descompacte este kit **ao lado** da
sua pasta, abra o agente dentro da sua pasta e peça pra ele ler `sistema/changelog/COMO-ATUALIZAR.md`
do kit novo. Ele mostra o que mudou, aplica no máximo três coisas por vez, e você decide cada uma.

---

## Ficou travado?

Assiste a **Aula 1.3** do curso (instalação do Claude Code).

Dúvidas: [ratosdeia.com.br](https://ratosdeia.com.br)
