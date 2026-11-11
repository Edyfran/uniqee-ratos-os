# As fontes que viajam no kit

Toda letra que um preset ou sistema de legenda do `captions_viral` usa mora aqui, e o kit leva a
pasta inteira (`empacota_kit.py`, `ASSETS`). Nenhum preset lê o `~/Library/Fonts` do dono nem fonte
do sistema do Mac: na máquina do aluno elas não existem, e a legenda caía na Montserrat sem ninguém
ver. O autoteste do `captions_viral` reprova preset que aponte pra fonte fora desta pasta.

Todas são SIL Open Font License 1.1: uso comercial livre, inclusive em vídeo vendido, e podem viajar
junto do programa desde que o texto da licença vá ao lado (`<Família>-OFL.txt`).

| arquivo | nome no registro | família | quem fez | origem |
|---|---|---|---|---|
| `Montserrat[wght].ttf` | `montserrat`, `montserrat-media`, `montserrat-semi` | Montserrat | Julieta Ulanovsky | github.com/JulietaUla/Montserrat |
| `IBMPlexMono-Regular.ttf` | `mono` | IBM Plex Mono | IBM | github.com/IBM/plex |
| `CreatoDisplay-Black.otf` | `creato` (o padrão) | Creato Display Black | Anugrah Pasau | licença OFL embutida na fonte |
| `BebasNeue-Regular.otf` | `bebas` | Bebas Neue | Dharma Type | github.com/dharmatype/Bebas-Neue |
| `DMSans-Variable.ttf` | `dm` | DM Sans | Colophon | github.com/googlefonts/dm-fonts |
| `Nunito-Variable.ttf` | `redonda` | Nunito | Vernon Adams | github.com/googlefonts/nunito |
| `TikTokSans-Variable.ttf` | `tiktok` | TikTok Sans | TikTok | github.com/tiktok/TikTokSans |
| `Excalifont-Regular.ttf` | `excali` | Excalifont | Excalidraw | github.com/excalidraw/excalidraw (fonts/Excalifont) |
| `PlayfairDisplay-Variable.ttf` | `serifa` | Playfair Display | Claus Eggers Sørensen | github.com/clauseggers/Playfair-Display |
| `PlayfairDisplay-Italic-Variable.ttf` | `serifa-italica` | Playfair Display Italic | Claus Eggers Sørensen | idem |
| `Inter-opsz-wght.ttf` | `inter`, `inter-regular` | Inter | Rasmus Andersson | github.com/rsms/inter |
| `InstrumentSerif-Italic.ttf` | `instrument` | Instrument Serif Italic | Instrument | github.com/Instrument/instrument-serif |
| `Jost-Variable.ttf` | `jost` | Jost | indestructible type* | github.com/google/fonts (ofl/jost) |
| `Fraunces-Variable.ttf` | `fraunces` | Fraunces | Undercase Type | github.com/google/fonts (ofl/fraunces) |
| `ArchivoBlack-Regular.ttf` | `archivo` | Archivo Black | Omnibus-Type | github.com/google/fonts (ofl/archivoblack) |

Os temas do guia de estilos (`docs/guia-de-estilos/<estilo>.css`) também só usam letra desta pasta: o
agente copia o arquivo pra `marca/fontes/` com a licença. Estas entraram só pra eles (05/10/2026), sem
nome no registro da legenda:

| arquivo | estilo | família | quem fez | origem |
|---|---|---|---|---|
| `SpaceGrotesk-Variable.ttf` | neobrutalista | Space Grotesk | Florian Karsten | github.com/google/fonts (ofl/spacegrotesk) |
| `PixelifySans-Variable.ttf` | pixel | Pixelify Sans | Stefie Justprince | github.com/google/fonts (ofl/pixelifysans) |
| `Bangers-Regular.ttf` | quadrinhos | Bangers | Vernon Adams | github.com/google/fonts (ofl/bangers) |
| `ChakraPetch-SemiBold.ttf` | cyberpunk | Chakra Petch | Cadson Demak | github.com/google/fonts (ofl/chakrapetch) |
| `IBMPlexMono-SemiBold.ttf` | o apoio de vários | IBM Plex Mono SemiBold | IBM | github.com/google/fonts (ofl/ibmplexmono); a licença é a `IBMPlexMono-OFL.txt` |

## As que saíram (comerciais) e quem entrou no lugar

Em 05/10/2026 três presets usavam letra que não se pode distribuir:

| era | licença | preset | entrou |
|---|---|---|---|
| Cooper Black (`cooper`, do pack) | URW/Monotype, comercial | `gigante`, `comedia` | Fraunces Black com suavidade 100 (`fraunces`): a serifa gorda e redonda do Cooper |
| Futura Condensed ExtraBold (`futura`, do Mac) | Neufville/Apple, comercial | `fita`, `comedia` | Jost ExtraBold (`jost`), a geométrica livre feita a partir da Futura |
| Arial Black (`black`, do Mac) | Monotype, comercial | `karaoke-ciclo` | Archivo Black (`archivo`) |

Os nomes antigos continuam no registro pra plano escrito à mão na máquina do dono; preset nenhum aponta
pra eles. As `capviral-*` do pack pago também ficam fora daqui, salvo as duas que são OFL de verdade
(Bebas Neue e Creato Display, conferido na tabela `name` de cada arquivo).
