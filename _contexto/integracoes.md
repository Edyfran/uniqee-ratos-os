<!-- quem alimenta: o /setup semeia na entrevista; o /atualizar acrescenta integração nova, acesso novo ou "não alcanço"; a /faxina confere e pergunta. Lido antes de dizer "não consigo" e ao criar skill. -->
# Integrações

> O que o negócio usa e como o agente alcança cada coisa. **"não ligada" é resposta válida:** é assim
> que o agente sabe que aquilo existe e dá pra ligar, em vez de achar que é impossível.
> Chave nunca fica aqui. Chave mora no `.env` (fora do git) ou no gerenciador de senha; aqui vai só o
> nome da variável. O cardápio do que dá pra ligar está em `sistema/templates/integracoes/catalogo.md`.

| integração | pra quê | como o agente alcança | estado | última checagem |
|---|---|---|---|---|
| Brinderoz ERP | loja, pedidos, tarefa e prazo, agenda, financeiro, ficha do cliente | só você, na mão (sem conector) | não ligada | 2026-11-08 |
| WhatsApp | atendimento e orçamento com cliente | só você, na mão (dá pra ligar via WhatsApp Cloud API ou Z-API) | não ligada | 2026-11-08 |
| Canva | artes e posts da Uniqee (tem brand kit da Uniqee) | MCP (conector do claude.ai) | ligada | 2026-11-08 |
| Metricool | métricas e agendamento de posts | MCP (conector do claude.ai) | ligada, mas sem o Instagram conectado | 2026-11-08 |
| Instagram | divulgação da Uniqee e do PreçoArte | via Metricool, quando conectar | não ligada | 2026-11-08 |
| ManyChat | resposta automática no Instagram ("comente PREÇO") | só você, na mão | não ligada | 2026-11-08 |
| Kiwify | checkout do PreçoArte | webhook pro serviço de chaves na Cloudflare; o agente não alcança direto | não ligada | 2026-11-08 |
| Mercado Pago | link de pagamento pra venda manual no WhatsApp | só você, na mão | não ligada | 2026-11-08 |
| Cloudflare | página e serviço de chaves do PreçoArte | CLI (`npx wrangler`, com Node instalado) | não ligada | 2026-11-08 |
| Resend | email de entrega de código do PreçoArte | API, configurada dentro do serviço de chaves | não ligada | 2026-11-08 |
| GitHub | código e versões do PreçoArte | git instalado; `gh` CLI não instalado | não ligada | 2026-11-08 |
| Gmail | email | MCP (conector do claude.ai) | ligada, uso no negócio não confirmado | 2026-11-08 |
| Google Calendar | agenda | MCP (conector do claude.ai) | ligada, uso no negócio não confirmado | 2026-11-08 |
| ChatGPT | gerar a arte das peças | só você, na mão | não ligada | 2026-11-08 |
| Corel | imprimir a arte (espelha na impressão) | só você, na mão | não ligada | 2026-11-08 |
| Kittl | ampliar imagem pequena antes de imprimir (upscale; pode custar crédito). Não tem mockup de azulejo | MCP (conector do claude.ai) | ligada | 2026-11-09 |
| Gemini (Veo e imagem) | vídeos e mockups de divulgação | só você, na mão | não ligada | 2026-11-09 |
| Python + Pillow | script da /ajustar-arte | CLI (`python`) | ligada | 2026-11-08 |
| Fábrica de Conteúdo com IA | editar os Reels (corte, legenda, peças, trilha, capa), de graça | CLI (`uv run` dentro de `projetos/fabrica-de-conteudo/`) | ligada, transcrição local (sem chave da ElevenLabs) | 2026-11-11 |

## Os sete assuntos que todo negócio tem

| assunto | o que usa |
|---|---|
| Mensagem com cliente | WhatsApp |
| Tarefa e prazo | Brinderoz ERP |
| Email | não informado |
| Agenda | Brinderoz ERP |
| Dinheiro entrando e saindo | Brinderoz ERP |
| Ficha do cliente | Brinderoz ERP |
| Reunião | não informado |
