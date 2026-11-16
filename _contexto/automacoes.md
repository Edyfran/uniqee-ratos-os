<!-- quem alimenta: o /atualizar, quando uma automação é ligada, desligada ou mudada. -->
# Automações

| automação | o que faz | onde roda | quando | onde deixa o resultado | como saber se quebrou |
|---|---|---|---|---|---|
| Publicador do Instagram (app Conteúdo) | publica no @uniqeepersonalizados o que está na fila do app; pedido com horário espera a hora | Ratoeira, adaptador `instagram-publicador-uniqee` do app Conteúdo | a cada minuto | post no Instagram; resposta em `fila/feito/<id>.json` e estado da publicação no app | resposta "erro" em `fila/feito/` ou publicação parada em "na_fila" depois do horário |
