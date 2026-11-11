# Contexto · Fábrica de Conteúdo com IA

**Tipo:** interno (ferramenta) · **Versão instalada:** 2026.11.08 (ver `VERSAO`)

## O que é
Kit da Academy (Ratos de IA) que transforma vídeo gravado no celular em Reels editado: corte,
legenda, peças animadas, trilha e capa, a partir de um plano em JSON renderizado pelo `fabrica.py`.
Roda de graça aqui na VPS; só os módulos (voz clonada, avatar, cenas com IA, postagem) cobram.

## Pra que serve na Uniqee
Editar os Reels do Instagram da Uniqee e do PreçoArte sem ferramenta paga.

## Como funciona
- O pacote tem regras próprias: `AGENTS.md` desta pasta (não editar: a atualização troca).
  Antes de qualquer vídeo, a skill `.agents/skills/fabrica-de-conteudo/SKILL.md`.
- Pedidos prontos: `GUIA-DE-PEDIDOS.md`. Tudo o que anima: `biblioteca.html`.
- Gravações e vídeos prontos: `videos/`.
- Chaves dos módulos: `.env.local` (fora do git; nunca abrir, conferir só com `confere_env.py`).
- Atualização: ZIP novo da aula + `/atualizar` com a conversa aberta nesta pasta
  (aberta na raiz, `/atualizar` é o do RatosOS).

## Instalação (2026-11-11)
- Fonte: `fabrica-de-conteudo-com-ia.zip`, anexado no chat em 2026-11-11.
- `uv` instalado em `~/.local/bin`; ffmpeg 6.1.1 do sistema.
- Playwright alinhado com o navegador da Ratoeira (1.64.1, `/opt/ratoeira/ms-playwright`)
  em vez de baixar outro Chromium. Depois de atualizar a Fábrica, se o navegador não abrir:
  `uv lock --upgrade-package 'playwright==<versão do sistema>' && uv sync`.
- Conferência rápida passou (99 testes); `.fabrica-ok` gravado.
- Sem chave da ElevenLabs: transcrição local, com modelo de ~3 GB.
- Render de vídeo pesa na VPS (que é compartilhada): seguir a skill `video-pesado-ratoeira`.
