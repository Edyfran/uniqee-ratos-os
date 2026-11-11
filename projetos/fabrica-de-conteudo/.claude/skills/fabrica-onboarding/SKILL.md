---
name: fabrica-onboarding
description: Use quando o usuário pedir onboarding, começar, "configurar minha fábrica", primeiros passos, ou digitar /onboarding. Sobe uma página no computador dele, onde ele escolhe sozinho, uma escolha por tela, o estilo, as cores, as letras, o logo e a legenda vendo o resultado (e, com os módulos, conecta as ferramentas pagas e vê o checklist do clone). A página grava tudo na hora em onboarding/escolhas.json e não depende de você: você sobe, avisa e fica livre. Quando ele voltar dizendo que terminou, você lê o arquivo e aplica as escolhas na fábrica. O onboarding só define preferências: não pede vídeo, e a edição vem depois, na conversa.
---

# Onboarding

O aluno escolhe numa página, no computador dele, e **a página se basta**: cada escolha vai para
`onboarding/escolhas.json` na hora (as chaves, para o `.env.local`), sem você no meio. Você sobe a
página, diz o que fazer e fica livre. Quando ele voltar à conversa, você lê o arquivo e aplica.

A página só escuta em 127.0.0.1. Não pede vídeo: as prévias de estilo e de legenda tocam num clipe de
exemplo que vem no kit (`tools/onboarding/previa/`, domínio público). Nada pago roda no onboarding. O
botão "Gera pra mim" (paleta, letras, logo) é do servidor: ele chama o `claude -p` ou o `codex exec`
do próprio aluno, sem ferramenta nenhuma, e a página mostra o que volta. Não é trabalho seu.

Rode tudo da raiz desta pasta. Fale com o aluno sempre em português do Brasil.

## 1. A máquina

Sem `.fabrica-ok` na raiz, faça antes a "Primeira vez nesta máquina" do `INSTALAR.md`,
inteira, e volte para cá. Diga numa linha que está preparando o computador.

## 2. Suba a página e fique livre

```bash
uv run python tools/onboarding/onboarding.py --fundo
```

O `--fundo` solta a página do terminal (ela fica no ar até o `para`), abre o navegador e imprime o
endereço; o log fica em `onboarding.log`. Agente sem tela: `--sem-navegador`. Se o navegador não
abriu, mande o endereço inteiro, com o `?t=` do fim: sem ele a página não grava nada.

Diga ao aluno, em poucas linhas: a página abriu no navegador; são uns 10 minutos, uma escolha por
tela, e tudo fica salvo na hora; quando chegar na última tela, ele volta aqui e diz "terminei o
onboarding". **Não rode o `espera` e não fique esperando.** Pode atender outra coisa que ele pedir.

Se ele disser que terminou (ou colar a frase da última tela), vá para a seção 3. Se ainda não houver
`onboarding/escolhas.json` com `"pronto": true`, diga que ele ainda não chegou na última tela.

### Só com o módulo Clone de IA: a lista dos looks da HeyGen

A tela da HeyGen tem o botão "Listar os meus looks", que precisa do seu MCP. Só nesse caso rode, uma
vez, `uv run python tools/onboarding/onboarding.py espera` (até 9 min). Se vier `faz: gerar` com
`o` = `looks`, chame `list_avatar_looks` com `ownership: "private"` e devolva
`uv run python tools/onboarding/onboarding.py entrega looks onboarding/gerados/looks.json`, com
`{"opcoes": [{"id", "nome", "tipo"}]}`. Sem as ferramentas ou sem look, entregue
`{"opcoes": [], "msg": "<o que falta, em uma frase>"}` e explique no chat como ligar (skill
`fabrica-clone`). O aluno também pode colar o ID do look na tela, sem esperar por você.

## 3. Aplicar as escolhas

Leia `onboarding/escolhas.json`:

| Campo | O que é |
|---|---|
| `marca.nome`, `sobre`, `jeito` | o nome ou @, o que ele vende e pra quem, o jeito de falar |
| `marca.estilo` | um dos estilos de `docs/guia-de-estilos.md` |
| `marca.cores` | `pp`, `ink`, `ac`, `mk`, já no papel de cada uma (chão, letra, bloco, marcador) |
| `marca.fontes` | `null`: as do tema do estilo. Senão `fd` (títulos) e `fm` (apoio), cada uma `{arq, peso}`, arquivos de `tools/video-use/assets/fontes/` |
| `marca.logo` | `onboarding/logo.*`, se ele mandou um ou escolheu um dos gerados |
| `legenda` | o preset da legenda viral (`captions_viral.py`, `PRESETS`) |
| `ferramentas`, `clone` | o que ele conectou e se já tem o avatar (só com os módulos); as chaves já estão no `.env.local` |

1. **A marca:** siga a seção "A marca feita aqui" da skill `fabrica-estilo`, com as respostas do
   arquivo no lugar das perguntas. O slug é o `marca.nome` em minúsculas, sem `@` nem espaço
   (`minha-marca` sem nome). O `tema.css` é o do estilo, com as quatro cores como vieram. As letras
   saem de `tools/video-use/assets/fontes/`, copiadas para `marca/fontes/` com a licença: as do tema,
   ou, com `marca.fontes`, a face `'Marca'` com o `fd` e a `'MarcaApoio'` com o `fm`, cada uma com o
   `font-weight` do `peso`. O logo vai para `marca/` com o nome `logo` e a extensão que veio. Campo
   que ele não preencheu sai do `MARCA.md`.
2. **A legenda:** `desenho.legenda` = `legenda` em todo estilo da marca que queima a legenda viral
   (o `-celular`, o `-anuncio`, o `-avatar`). Com legenda escolhida, tire o `desenho.fonte` desses
   estilos: o preset traz as letras dele, e a fonte da marca passaria por cima.
3. **O tipo padrão:** o do Reel do celular. O estilo `<slug>-celular` vai em `"_padrao"` no topo do
   `marca/estilos.json`, e o pedido do Reel do celular (do `GUIA-DE-PEDIDOS.md`) abre o
   `marca/PEDIDOS.md`. Com o módulo do Clone, crie também `<slug>-avatar`, herdando de `reel-avatar`,
   com `desenho.tema` `marca` e a legenda.
4. **Confira:** `uv run python marca/instala.py --sem-voz --amostra` (com a chave da ElevenLabs e o
   `VOZ_ID` no `.env.local`, sem o `--sem-voz`) e `uv run python tools/video-use/helpers/estilo.py`.
5. **A biblioteca:** as animações dele, na marca nova, numa página na raiz:
   `uv run python tools/v2/v2.py biblioteca --abrir`.

Diga ao aluno em até quatro linhas: o que entrou na fábrica (`marca/`); que o próximo passo é mandar o
vídeo e o pedido aqui na conversa (o caminho entra arrastando o arquivo pra janela); e que o
`biblioteca.html` mostra as animações, cada uma com a frase pra colar. Se a página ainda estiver
aberta, `uv run python tools/onboarding/onboarding.py para` a desliga.

## Regras

- **Chave:** nunca abra, imprima nem cole o `.env.local`; nada de `grep`, `cat` nem `Read` nele. Para
  ver o que está preenchido, só `uv run python tools/video-use/helpers/confere_env.py`. Quem grava é a
  página. O `HEYGEN_LOOK` não é chave: lê e grava só pelo
  `uv run python tools/onboarding/onboarding.py id HEYGEN_LOOK [<id>]`.
- **Nada pago:** nem narração, nem avatar, nem cena, nem imagem, mesmo com a chave conectada. O
  primeiro vídeo pago sai de um pedido dele, depois do onboarding, com o `--seco` e o custo antes
  (`fabrica-de-conteudo`, regras 1 e 2).
- **Se travar:** depois de três consertos na mesma falha, pare. Diga qual passo, o sistema
  (`uname -sm`) e as linhas exatas do erro, sem nenhuma chave, pra ele mandar ao suporte.
