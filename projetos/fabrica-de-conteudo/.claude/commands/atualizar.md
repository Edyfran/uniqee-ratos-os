---
description: Atualizar a fábrica com o ZIP novo da aula, sem tocar na sua marca, nas suas chaves nem nos seus vídeos
---

Atualize esta Fábrica com o ZIP novo, da raiz desta pasta. Responda em português simples, sem jargão.

1. Rode `uv run python tools/video-use/helpers/atualiza.py --seco`. Se o aluno mandou o ZIP na conversa,
   ponha o caminho dele no fim do comando; sem caminho, o `atualiza.py` procura em Downloads e ao lado
   desta pasta, e escolhe o ZIP de versão mais nova. `--seco` só mostra o que mudaria e não escreve nada.
   - Não achou ZIP: diga ao aluno, em uma frase, que baixe o ZIP novo na aula da Fábrica, na Academy, e pare.
   - Disse "já está na versão ...": diga isso ao aluno e pare. Nada mudou.
2. Diga ao aluno, em uma frase, de que versão para qual a Fábrica vai e que a marca, as chaves
   e os vídeos dele não são tocados.
3. Rode o mesmo comando sem `--seco`. Ele guarda a cópia do que troca e do que sai em `.fabrica/copia/`.
4. Siga o que o comando mandar no fim: se pediu `uv sync`, rode. Rode
   `uv run python tools/v2/v2.py biblioteca` e depois `uv run python tools/video-use/helpers/confere.py`,
   e conserte o que a conferência acusar antes de devolver ao aluno.
5. Diga ao aluno a versão nova e, em uma frase, o que mudou (quantos arquivos). Diga que a cópia do que foi
   trocado fica em `.fabrica/copia/`. Se a conferência acusou defeito do pacote, diga isso e mande o
   `conferencia.txt` num Chamado da Academy.
