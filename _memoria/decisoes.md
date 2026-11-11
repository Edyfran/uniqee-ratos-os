<!-- quem alimenta: o /atualizar acrescenta no fim; robô nunca escreve aqui (propõe por recado). Lido quando perguntam "por quê" ou antes de mudar algo já decidido. -->
# Decisões

Uma entrada por decisão, sempre acrescentada no fim, nunca reescrita. É o arquivo mais barato do
sistema e o que mais evita retrabalho: daqui a três meses, quando alguém (inclusive você) perguntar
"por que a gente faz assim?", a resposta está aqui.

O que entra: escolheu um caminho e descartou outro, mudou de ideia, fechou um preço, definiu uma
regra de trabalho. O que não entra: tarefa feita (isso é o diário).

**Formato de cada entrada:**

```
- **AAAA-MM-DD** (quem decidiu: o nome da pessoa, ou a origem se foi um robô) [projeto, se for de projeto]: a decisão em uma frase. Por quê: o motivo em outra. Substitui: AAAA-MM-DD (só quando muda uma decisão anterior; a antiga fica onde está)
```

---

<!-- as decisões entram abaixo, a mais nova por último -->
- **2026-11-08** (Edyfran): pedidos e artes de cliente ficam em `pedidos/`, fora do git. Por quê: têm nome, telefone e foto de cliente.
- **2026-11-08** (Edyfran) [PreçoArte]: divulgação com 3 posts por semana no perfil da Uniqee, por uma skill própria (/divulgar-precoarte). Por quê: o foco é vender o PreçoArte, e o público (sublimador) é outro, diferente do de quem compra presente.
- **2026-11-08** (Edyfran): melhorar a skill marketing-digital-uniqee em vez de criar uma /divulgar-uniqee nova. Por quê: ela já existia e vale em qualquer lugar da conta, inclusive no celular.
- **2026-11-09** (Edyfran): vídeos de divulgação podem ser feitos por IA, com pessoas fictícias, rótulo de IA no Instagram e "Vídeo ilustrativo" na legenda. Por quê: dispensa autorização de cliente e mantém o rosto dele fora da marca.
- **2026-11-11** (Edyfran) [Fábrica de Conteúdo]: a Fábrica fica em `projetos/fabrica-de-conteudo/`, com AGENTS.md próprio, e não na raiz. Por quê: o pacote traz AGENTS.md, CLAUDE.md e .claude/ que sobrescreveriam os do RatosOS.
