# Aprendizados — Comentario DM Ratos

<!-- O Claude registra aqui erros, descobertas e regras aprendidas durante o uso.
     Formato:
     ### {DATA} — {titulo curto}
     **Regra:** {o que fazer sempre/nunca}
     **Contexto:** {o que aconteceu pra gerar esse aprendizado}
-->

### 2026-11-06 — Token EAA (login unificado) nao funciona no graph.instagram.com
**Regra:** Para a Uniqee, usar sempre graph.facebook.com com o token da PAGINA (PAGE_ACCESS_TOKEN do .env). Nunca graph.instagram.com.
**Contexto:** O painel "API do Instagram (login unificado)" do app claudecode-edy gera tokens EAA de System User, que o graph.instagram.com recusa ("Cannot parse access token"). Solucao: System User `dm-automacao` no portfolio Uniqee com ativos atribuidos (app, Instagram, Pagina) e token sem expiracao; dele sai o token da Pagina 653031451236536, usado no Worker.

### 2026-11-06 — Inscrever a Pagina no app exige pages_manage_metadata
**Regra:** O token do System User precisa de `pages_manage_metadata` para `POST /{PAGE_ID}/subscribed_apps`; sem isso o webhook de comentarios nao chega.
**Contexto:** Primeiro token do dm-automacao veio sem essa permissao e o subscribed_apps retornou erro #200.

### 2026-11-12 — Gatilho por número/regex
**Regra:** Para "comente o número", criar a automação com keyword `re:<regex>` (o Worker testa como expressão regular). Ex.: `re:(^|\D)[1-7](\D|$)` casa um número solto de 1 a 7 ("3", "quero o 2") e ignora "10" ou "100%".
**Contexto:** Reel do presépio dourado (opções 1 a 7). O Worker só aceitava palavra fixa; foi adicionado o modo `re:` no index.js e feito o deploy.
