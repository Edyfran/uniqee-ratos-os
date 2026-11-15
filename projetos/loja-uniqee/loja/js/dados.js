// Dados da loja. Preços e textos vindos da loja atual (Brinderoz), lidos em 2026-11-15.
// Na versão final isto sai do banco, cadastrado pelo painel; aqui é a vitrine de teste.
window.UNIQEE = (function () {
  const CONFIG = {
    zap: '5583991020063',
    zapVisivel: '(83) 99102-0063',
    instagram: 'uniqeepersonalizados',
    prazoProducao: 5,           // dias úteis
    parcelasSemJuros: 2,
    parcelaMinima: 20,          // reais por parcela
    cepSousa: [58800000, 58815999],
  };

  // momentos: natal, avos, maes, aniversario, amor, professores, fe
  // provador: 'caneca' | 'camiseta' | 'azulejo' quando dá pra montar a peça no site
  // pede: o que o cliente informa na compra quando não usa o provador
  const PRODUTOS = [
    { id: 'caneca-personalizada', nome: 'Caneca personalizada com foto', img: 'caneca-personalizada.webp', preco: 23.00, cat: 'canecas',
      momentos: ['maes', 'aniversario', 'amor', 'natal'], etiqueta: 'Mais pedida', provador: 'caneca', peso: 0.45,
      desc: 'Caneca branca de porcelana com a sua foto e o nome de quem vai receber.\n\nNo provador você envia a foto, escreve a frase, escolhe a cor do fundo e gira a caneca pra ver como fica antes de pedir.' },
    { id: 'azulejo-15', nome: 'Azulejo personalizado 15x15', img: 'azulejo-15.webp', preco: 30.00, cat: 'azulejos',
      momentos: ['aniversario', 'amor', 'maes', 'avos', 'natal'], provador: 'azulejo', peso: 0.6,
      desc: 'Azulejo 15x15 com a foto, a frase ou a arte que você quiser.\n\nMonte no provador e veja como ele fica antes de pedir.' },
    { id: 'camisa-poliester', nome: 'Camisa personalizada 100% poliéster', img: 'camisa-poliester.jpeg', preco: 45.00, cat: 'camisetas',
      momentos: ['aniversario'], provador: 'camiseta', peso: 0.25,
      opcoes: [{ nome: 'Tamanho', valores: ['P', 'M', 'G', 'GG'] }],
      desc: 'Camisa em poliéster com a sua estampa na frente, em várias cores. Boa pra aniversário, evento, time e família.' },
    { id: 'azulejo-natal', nome: 'Azulejo perolado de Natal 15x15', img: 'azulejo-natal.webp', preco: 59.55, cat: 'azulejos',
      momentos: ['natal', 'fe'], colecao: 'fe', etiqueta: 'Natal', peso: 0.7,
      desc: 'Azulejo perolado com a Sagrada Família em tons dourados. Um presente pra deixar o Natal à vista o ano inteiro.' },
    { id: 'azulejo-relogio', nome: 'Azulejo relógio 20x20 com suporte', img: 'azulejo-relogio.jpg', preco: 50.00, cat: 'azulejos',
      momentos: ['aniversario', 'avos', 'maes'], peso: 1.0,
      pede: { texto: 'Frase ou nome no relógio (opcional)', fotos: 1 },
      desc: 'Relógio de azulejo 20x20 com a imagem que você escolher. Um presente que marca as horas e a lembrança.' },
    { id: 'caneca-liturgia', nome: 'Caneca Orai sem Cessar com QR Code da liturgia do dia', img: 'caneca-liturgia.webp', preco: 39.90, cat: 'canecas',
      momentos: ['fe', 'natal'], colecao: 'fe', peso: 0.45,
      desc: 'Caneca com QR Code que abre a liturgia do dia em texto e áudio. Pra começar a manhã com a Palavra.' },
    { id: 'caneca-professores', nome: 'Caneca Dia dos Professores, corujinha', img: 'caneca-professores.jpg', preco: 25.00, cat: 'canecas',
      momentos: ['professores'], peso: 0.45,
      pede: { texto: 'Nome do professor ou da professora (opcional)' },
      desc: 'Caneca com a corujinha "Meu professor é o melhor". Presente carinhoso pra homenagear quem ensina.' },
    { id: 'caneca-album', nome: 'Caneca Meu Álbum Mágico com QR Code', img: 'caneca-album.webp', preco: 30.00, cat: 'canecas',
      momentos: ['aniversario', 'amor'], peso: 0.45,
      pede: { texto: 'Nome de quem vai receber', fotos: 10 },
      desc: 'A pessoa escaneia o QR Code da caneca e abre um álbum de figurinhas digital com as fotos de vocês.' },
    { id: 'squeeze', nome: 'Squeeze de alumínio com foto', img: 'squeeze.webp', preco: 50.00, cat: 'squeezes',
      momentos: ['aniversario', 'professores'], peso: 0.3,
      pede: { texto: 'Nome ou frase (opcional)', fotos: 1 },
      desc: 'Squeeze de alumínio personalizado com a sua foto. Não é térmico.' },
    { id: 'kit-avos-caixa', nome: 'Kit Dia dos Avós na caixa', img: 'kit-avos-caixa.webp', preco: 57.90, cat: 'kits',
      momentos: ['avos'], etiqueta: 'Kit', peso: 1.2,
      pede: { texto: 'Como os netos chamam os avós (ex.: Vovó e Vovô)', fotos: 2 },
      desc: 'Caixa de presente com almofada e azulejo personalizados com a foto dos avós.' },
    { id: 'kit-avos-almofada', nome: 'Kit Dia dos Avós, almofada e caneca', img: 'kit-avos-almofada.webp', preco: 52.67, cat: 'kits',
      momentos: ['avos'], etiqueta: 'Kit', peso: 1.0,
      pede: { texto: 'Como os netos chamam os avós (ex.: Vovó e Vovô)', fotos: 2 },
      desc: 'Almofada e caneca com a foto da família, prontas pra presentear vovó e vovô.' },
    { id: 'kit-canecas-avos', nome: 'Kit canecas Vovó e Vovô', img: 'kit-canecas-avos.webp', preco: 38.90, cat: 'kits',
      momentos: ['avos'], etiqueta: 'Kit', peso: 1.0,
      pede: { texto: 'Nomes nas canecas (ex.: Vovó Maria e Vovô José)', fotos: 2 },
      desc: 'Duas canecas personalizadas com foto, embaladas com laço e cartão.' },
    { id: 'kit-mulheres', nome: 'Kit caneca e azulejo decorativo', img: 'kit-mulheres.webp', preco: 50.00, cat: 'kits',
      momentos: ['maes', 'amor'], etiqueta: 'Kit', peso: 1.1,
      pede: { texto: 'Nome de quem vai receber', fotos: 1 },
      desc: 'Caneca e azulejo decorativo personalizados, combinando entre si.' },
    { id: 'kit-caneca-azulejo', nome: 'Kit caneca e azulejo 15x15 personalizados', img: 'kit-caneca-azulejo.png', preco: 42.50, cat: 'kits',
      momentos: ['natal', 'aniversario', 'maes', 'avos'], etiqueta: 'Kit', peso: 1.1,
      pede: { texto: 'Nome ou frase', fotos: 1 },
      desc: 'Caneca e azulejo 15x15 com a mesma foto ou arte. Um presente completo.' },
    { id: 'kit-tradicao', nome: 'Kit Tradição, 212 anos do Milagre Eucarístico de Sousa', img: 'kit-tradicao.webp', preco: 120.00, cat: 'kits',
      momentos: ['fe'], colecao: 'fe', etiqueta: 'Sousa', peso: 1.3,
      desc: 'Dois azulejos 15x15 em homenagem aos 212 anos do Milagre Eucarístico da cidade de Sousa-PB.' },
  ];
  // Não entram na vitrine (personagem, marca ou pessoa famosa): Armaduras do Cosmos, Dança dos Dragões,
  // Doutor Destino, Luan Santana. Ficam fora também os insumos pra sublimação (azulejo 4,5 com ímã).

  const MOMENTOS = [
    { id: 'natal', nome: 'Natal', dica: '', icone: '<path d="M12 3l3 5h-2l3 5h-2l3 5H7l3-5H8l3-5H9z"/><path d="M12 18v3"/>' },
    { id: 'avos', nome: 'Avós', dica: 'Pra quem cuidou de todo mundo', icone: '<circle cx="8" cy="8" r="3"/><circle cx="16" cy="8" r="3"/><path d="M3 20c0-3 2.5-5 5-5s5 2 5 5M11 20c0-3 2.5-5 5-5s5 2 5 5"/>' },
    { id: 'maes', nome: 'Mães e mulheres', dica: 'Carinho que fica na estante', icone: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>' },
    { id: 'aniversario', nome: 'Aniversário', dica: 'Um presente com a cara da pessoa', icone: '<path d="M4 21h16v-8H4zM12 13V8M12 8c-1.5 0-2-1.5-1-3l1-2 1 2c1 1.5.5 3-1 3z"/><path d="M4 17c2 1 4-1 4-1s2 2 4 0 4 0 4 0 2 1 4-1"/>' },
    { id: 'amor', nome: 'Pro amor', dica: 'Namoro, casamento, bodas', icone: '<path d="M9 18s-5-3.1-5-7a3 3 0 0 1 5-2 3 3 0 0 1 5 2c0 3.9-5 7-5 7z"/><path d="M15 15s4-2.4 4-5.6a2.4 2.4 0 0 0-4-1.6"/>' },
    { id: 'professores', nome: 'Professores', dica: 'Pra quem ensina com carinho', icone: '<path d="M3 8l9-4 9 4-9 4z"/><path d="M7 10v5c0 1.5 2.5 3 5 3s5-1.5 5-3v-5"/>' },
    { id: 'fe', nome: 'Fé', dica: 'Pra oração de cada dia', icone: '<path d="M12 3v18M7 8h10"/>' },
  ];

  const CATEGORIAS = [['todos', 'Todos'], ['canecas', 'Canecas'], ['azulejos', 'Azulejos'], ['kits', 'Kits'], ['camisetas', 'Camisetas'], ['squeezes', 'Squeezes']];

  const COLECOES = {
    fe: 'Fé e devoção',
  };

  return { CONFIG, PRODUTOS, MOMENTOS, CATEGORIAS, COLECOES };
})();
