# Comparacao entre referencias e Komicove atual

`Sim` significa funcionalidade encontrada no codigo, nao apenas botao no mockup. `Parcial` indica formato, dados ou interface diferentes. `Nao comprovado` evita prometer comportamento nao verificado. As referencias sao mockups e nao demonstram backend real.

| Recurso | Referencia possui? | PC atual possui? | Android atual possui? | Acao |
| --- | --- | --- | --- | --- |
| Biblioteca por pasta com capas | Sim | Sim | Sim | Redesenhar UI; preservar importacao/arquivos |
| Busca de HQ | Sim | Sim | Sim | Busca fixa no topo PC; revisar mobile na Fase 5 |
| Filtros de estado e favoritos | Sim | Sim | Sim | Redesenhar chips e manter logica |
| Ordenacao | Sim | Sim | Sim | Preservar criterios atuais; UI da referencia |
| Continuar lendo e progresso | Sim | Sim | Sim | Dar destaque visual sem alterar armazenamento |
| Menu de HQ e edicao de metadados | Sim | Sim | Sim | Manter menu e comandos |
| Estado vazio da biblioteca | Sim | Sim, simples | Sim, simples | Redesenhar PC nesta fase; mobile na Fase 5 |
| Colecoes, pastas e series | Sim | Sim | Sim | Fases 2 e 5 |
| Downloads com andamento e erro | Sim | Sim | Sim | Fases 2 e 5; confirmar cancelamento real |
| Estatisticas pessoais basicas | Sim | Sim | Sim | Fases 2 e 5; graficos so com dados reais |
| Graficos historicos de leitura | Sim | Sim, historico local real | Nao comprovado | Levar o mesmo modelo ao Android nas Fases 5 e 6 |
| Descobrir e catalogo remoto | Sim | Sim | Sim | Fases 2 e 5, reutilizar API |
| Criadores em destaque | Sim | Nao comprovado | Nao comprovado | Implementar so com dados de API validos |
| Meus envios, status e remocao | Sim | Sim | Sim | Fases 2 e 5 |
| Notificacoes e contador | Sim | Sim | Sim | Fases 2 e 5; categorias dependem da API |
| Perfil, e-mail, senha e 2FA | Sim | Sim | Sim | Redesenhar nas Fases 3 e 6 |
| Dispositivos conectados | Sim | Sim, plataforma e datas reais | API compativel, UI pendente | Reutilizar endpoints na Fase 6 |
| Moderacao por papel | Sim | Sim | Sim | Preservar gate de permissao nas Fases 3 e 6 |
| Login, cadastro, convidado | Sim | Sim | Sim | Fases 3 e 6; sem convite |
| Leitor com modos, zoom e paginas | Sim | Sim | Sim | Fases 4 e 6 |
| Selecao visual de paginas | Sim | Parcial | Parcial | Melhorar nas Fases 4 e 6 |
| Marcadores por pagina | Sim | Sim | Sim | Redesenhar lista nas Fases 4 e 6 |
| Leitura guiada e editor manual | Sim | Sim | Sim | Preservar algoritmo e editor nas Fases 4 e 6 |
| Atalhos do leitor | Sim | Sim, espalhados | Nao se aplica | Dialog centralizado na Fase 4 |
| Navbar mobile unica | Sim | Nao se aplica | Sim, visual atual divergente | Reestilizar a implementacao compartilhada na Fase 5 |
| Idioma PT/EN e tema | Sim | Sim | Sim | Manter em cada nova tela |
| Backup, restauracao, atualizacoes e diagnostico | Sim | Sim | Sim, onde aplicavel | Reestilizar sem remover recurso |

## Evidencias de codigo

- Desktop: `komicove_app/library_views.py`, `library_widgets.py`, `reader_views.py`, `downloads.py`, `account_views.py`, `community_views.py`, `moderation_views.py`, `storage.py`.
- Android: `android/app/src/main/java/com/lucrazy/komicove/MainActivity.java`, `LibraryStore.java`, `ReaderActivity.java`, `PanelEditorView.java`, `ReaderPreferences.java`, `PanelApi.java`.
- API: `komicove_backend/api/routes/`.

Este mapa sera refinado antes de cada fase. Especialmente no Android, `Parcial` e `Nao comprovado` exigem teste em aparelho antes de fechar a implementacao.
