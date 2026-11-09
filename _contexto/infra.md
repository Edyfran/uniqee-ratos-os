<!-- quem alimenta: o /setup semeia na entrevista; o /atualizar acrescenta quando algo passa a estar hospedado. Lido quando a sessão precisa saber onde algo está (mapa). -->
# Infra

> Onde as coisas estão hospedadas: site, domínio, servidor, banco, DNS, email, área de membros.
> É diferente de `integracoes.md` (o que você usa) e aponta pra onde cada coisa **mora**.
> Sem chave, sem senha. Aqui vai o nome do serviço, o endereço e quem tem acesso.

| o quê | onde mora (serviço) | endereço | quem acessa e como | observações |
|---|---|---|---|---|
| Loja da Uniqee | plataforma Brinderoz | uniqeepersonalizados.shop | Edyfran, pelo painel do Brinderoz | imagens servidas por bdz.brinderozerp.com.br |
| Domínio do PreçoArte | Hostinger (registro) | precoarte.com.br | Edyfran, conta Hostinger | DNS apontado pra Cloudflare |
| DNS e página do PreçoArte | Cloudflare (Worker "precoarte") | precoarte.com.br e www | Edyfran, conta Cloudflare | a internet de casa não alcança os IPs da zona; conferir pelo endereço workers.dev |
| Serviço de chaves do PreçoArte | Cloudflare Worker | rotas /ativar, /admin/nova, /admin/painel | Edyfran, pelo painel /admin com senha | recebe webhook da Kiwify e manda email pelo Resend |
| Checkout do PreçoArte | Kiwify | links em `precificacao-desktop/entrega-chaves/KIWIFY-PASSO-A-PASSO.md` | Edyfran, conta Kiwify | conta ainda pede documentos pra liberar saque |
| Código e instaladores do PreçoArte | GitHub | repositório privado (código) e público (instaladores) | Edyfran | download direto por releases/latest/download/PrecoArte-Setup.exe |
