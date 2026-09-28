# Mapa de assets e referências do REDESIGN

Fonte: `C:/Users/Luanz/OneDrive/Desktop/Imagens REDESIGN/PT2/`.
O `README.txt` explica o papel de cada pasta. O `manifest.csv` relaciona os 41 arquivos renomeados com seus nomes anteriores e hashes. As imagens originais permanecem intactas.

## Referências da Fase 1

| Arquivo | Tipo | Uso correto |
| --- | --- | --- |
| `references/desktop/desktop_library.png` | tela desktop completa | Composição da Biblioteca com HQs, hero e grid |
| `references/desktop/desktop_library_empty.png` | tela desktop completa | Composição da Biblioteca vazia |
| `references/mobile/mobile_library_empty.png` | tela mobile completa | Guia visual futuro para Android, não copiar como UI |
| `references/empty_states/empty_library_panel.png` | painel com texto e botão | Guia de composição para um painel vazio, não é asset isolado |
| `assets/backgrounds/background_red_moon_city_desktop.png` | fundo decorativo | Hero da Biblioteca com HQs, não o estado vazio |
| `assets/backgrounds/background_red_moon_city_mobile.png` | fundo decorativo | Referência para telas mobile futuras, não o estado vazio |

As telas e o painel contêm controles, textos e outros elementos embutidos. Não são usados como fundo do aplicativo.

## Assets realmente usados na cópia

| Destino | Origem | Finalidade |
| --- | --- | --- |
| `assets_redesign/banners/library_noir.png` | `assets/backgrounds/background_red_moon_city_desktop.png` | Arte decorativa do hero quando há HQs |
| `assets_redesign/backgrounds/auth_noir.png` | `assets/backgrounds/background_red_moon_city_mobile.png` | Reservado para autenticação futura |
| `assets_redesign/empty_states/library_desktop.png` | arte isolada a partir de `references/desktop/desktop_library_empty.png` | Ilustração transparente da Biblioteca vazia, sem textos ou botões |
| `assets_redesign/empty_states/collections_desktop.png` | arte isolada a partir de `references/desktop/desktop_collections_empty.png` | Ilustração transparente de Coleções vazias, sem textos ou botões |
| `assets_redesign/empty_states/downloads_desktop.png` | arte isolada a partir de `references/desktop/desktop_downloads_empty.png` | Ilustração transparente de Downloads vazios, sem textos ou botões |
| `assets_redesign/empty_states/notifications_illustration.png` | arte isolada a partir de `references/empty_states/empty_notifications_panel.png` | Ilustração transparente de Notificações vazias, sem textos ou botões |
| `assets_redesign/placeholders/comic_cover.png` | `assets/placeholders/comic_cover_placeholder.png` | Reservado para outras telas; Downloads não usa capa genérica |
| `assets_redesign/icons/*.svg` | pacote oficial Lucide | Fontes vetoriais locais para a linguagem de ícones desktop e Android |
| `assets_redesign/icons/generated/` | SVGs Lucide rasterizados pelo build | PNGs em variantes normal, hover, ativo e branco; nenhum download acontece durante o uso do app |

As quatro ilustrações foram separadas das referências com a ferramenta de geração de imagens, em modo de edição e com fundo transparente. Títulos, descrições, busca, filtros e botões permanecem controles Tkinter reais. Nenhuma tela completa é usada como interface.

Para Notificações, o prompt de edição pediu para preservar sino metálico, cidade noir, lua vermelha, cartões e retícula, removendo borda do painel, texto, botão e fundo plano, com transparência real. O painel original em `references/empty_states/empty_notifications_panel.png` não foi modificado. `installer/Komicove.spec` e o manifesto Flatpak incluem `assets_redesign/` para que a arte acompanhe o executável.

Ainda não há arte mobile isolada no pacote. O Android será tratado na Fase 5 a partir de `references/mobile/mobile_library_empty.png`, que tem composição diferente da desktop.

## Pipeline de ícones

Os SVGs oficiais ficam preservados como fonte e os PNGs são gerados por `tools/build_lucide_icons.py`. CairoSVG é usado somente pelo utilitário de desenvolvimento. O aplicativo distribuído continua dependendo apenas de Pillow para carregar os PNGs locais. As variantes ativas recebem um halo vermelho leve, e a interface escolhe automaticamente cores claras ou escuras conforme o tema.
