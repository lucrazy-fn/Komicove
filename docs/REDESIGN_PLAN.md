# Redesign do Komicove

## Isolamento

- Origem: `../PANEL-ComicBookReader` (somente leitura neste trabalho).
- Trabalho: `PANEL-ComicBookReader-REDESIGN` (copia irma, sem `.git`).
- Referencias: `C:/Users/Luanz/OneDrive/Desktop/Imagens REDESIGN/PT2/` (somente leitura). Consultar `README.txt` e `manifest.csv` antes de reutilizar imagens.
- A copia preserva codigo, dados locais e builds presentes na origem. Os 25 links de caches/builds que nao puderam ser lidos nao sao codigo-fonte. O repositorio original nao recebeu edicoes.
- A copia nao compartilha a configuracao Git da origem. Nao executar `git push` a partir dela sem criar e conferir um remoto apropriado.
- A copia tambem contem dados e configuracoes locais da origem, inclusive arquivos ignorados pelo Git. Nao publicar a pasta inteira como ZIP nem inicializar Git com `git add .` sem revisar esses arquivos.
- Testes de interface devem usar `KOMICOVE_APPDATA_DIR` temporario para nao alterar dados reais.
- `startredesign-test.bat` inicia a copia com perfil separado em `build/redesign-profile`, sem usar o AppData habitual. Para verificar progresso antigo, sera preciso abrir o app normal da copia conscientemente; o teste isolado comeca vazio.

## Arquitetura encontrada

| Camada | Implementacao | Reuso |
| --- | --- | --- |
| Desktop | Python, Tkinter, Pillow | `komicove_app` |
| Android | Java nativo, Gradle | `android/app/src/main/java/com/lucrazy/komicove` |
| API | FastAPI e SQLAlchemy | `komicove_backend` |
| Cliente remoto | Python | `komicove_client` |
| Dados locais | JSON em AppData, caches de capa, biblioteca por pasta | manter formatos atuais |

## Direcao visual

`references/desktop/desktop_library.png` e `references/desktop/desktop_library_empty.png` guiam a Fase 1. `references/empty_states/empty_library_panel.png` mostra outra composicao vazia, com arte e controles embutidos, portanto nao e usado como fundo. Os fundos `assets/backgrounds/background_red_moon_city_*.png` sao decorativos. Tela com preto profundo e grafite; vermelho vivo apenas em acentos; bordas finas; tipografia clara; sidebar fixa; busca horizontal no topo; filtros e ordenacao em chips; faixa de progresso; grade de capas compacta; estado vazio com arte e acao. A UI e composta de controles Tkinter reais, nao de screenshots. O tema claro continua suportado.

## Fases

1. **Nesta entrega:** copia segura, inventario, mapa de assets, gap de recursos, tokens visuais reutilizaveis, shell desktop e Biblioteca desktop. Preservar busca, filtros, ordenacao, capas, progresso, favoritos, menu da HQ, abrir pasta e tema.
2. Colecoes, Descobrir, Downloads, Estatisticas, Meus envios e Notificacoes desktop.
3. Perfil, Login, Cadastro, Moderacao e Ajustes desktop.
4. Leitor desktop, preferencias, paginas, marcadores, editor e atalhos.
5. Sistema visual Android, navegacao inferior unica, Biblioteca, Colecoes, Comunidade e Ajustes.
6. Login/Cadastro e leitor Android, incluindo seus dialogos e editor.
7. Lacunas funcionais reais, integracao, desempenho, testes e builds.

## Regras de implementacao

- Nao remover funcoes existentes para acomodar o novo visual.
- Usar `ui(pt, en)` em todo texto novo mostrado ao usuario.
- Componentes e tokens ficam em `komicove_app/design` e sao usados pela shell e biblioteca nesta fase.
- Nao ler todas as paginas nem capas em resolucao maxima para montar a grade; manter `CoverLoader` e cache existentes.
- Formatos persistidos so podem crescer com defaults compativeis. O historico de estatisticas usa `version: 2`, preserva os campos antigos e continua incluido no backup existente.
- Nao tocar em `android/` nesta fase.

## Validacao da Fase 1

- Executar testes Python existentes na copia.
- Verificar importacao/compilacao dos arquivos Tkinter alterados.
- Iniciar o desktop com AppData temporario, navegar, alternar idioma/tema, selecionar pasta de teste e abrir HQ quando houver ambiente grafico disponivel.
- Confirmar que o projeto original continua com os mesmos hashes nos arquivos alterados na copia.

### Resultado desta entrega

- Suite Python na copia: 41 passaram, 1 ignorado.
- Compilacao sintatica e importacao dos modulos desktop alterados: passou.
- Assets escolhidos: hash SHA-256 igual aos arquivos de referencia renomeados.
- Origem Git: sem mudancas; destino: sem `.git`.
- Revisao visual posterior: a previa desktop com perfil temporario abriu em Windows. As capturas da Biblioteca vazia e com oito HQs de teste estao em `docs/redesign-review/`. O smoke pode ser repetido por `tools/redesign_visual_preview.py` (adicionar `--populated` para a grade). A composicao foi comparada com `desktop_library_empty.png` e `desktop_library.png`. O Android nao foi modificado nesta fase.
- Diferencas restantes: a referencia usa textura de parede e reticulas ao fundo da ilustracao vazia, brilho mais intenso nos botoes e icones customizados. A previa convidada tambem oculta naturalmente as secoes de conta e moderacao. Estes elementos nao foram simulados com dados falsos.

### Continuidade visual e inicio da Fase 2

- Botoes e filtros desktop passaram a usar retangulos de cantos arredondados moderados, no lugar de pilulas. Busca com borda arredondada e atalho Ctrl+K funcional.
- Colecoes recebeu cabecalho, busca funcional por nome, filtros, ordenacao, cartoes maiores com progresso e renomeacao, e estado vazio com ilustracao separada da referencia.
- Capturas adicionais em `docs/redesign-review/desktop-collections-empty.jpg` e `desktop-collections-populated.jpg`. A captura populada usa arquivos CBZ temporarios com capa de teste, sem tocar na biblioteca real.
- Downloads recebeu busca por titulo, filtros de status no mesmo componente visual da Biblioteca e Colecoes, cartoes com bordas mais arredondadas, progresso real e controles de pausar, continuar, cancelar e abrir pasta somente quando a acao e possivel. O titulo deixou de usar largura fixa e nao e cortado. As capas sao miniaturas reais da publicacao, obtidas em segundo plano e guardadas em cache por tarefa; a primeira pagina do arquivo concluido e usada quando a capa online nao estiver disponivel. Se nenhuma fonte funcionar, a tela informa isso em vez de mostrar uma capa generica. O estado vazio usa uma ilustracao separada da referencia e o botao real para Descobrir. Os filtros nao alteram o historico salvo.
- Capturas de Downloads vazio e com tarefas temporarias em `docs/redesign-review/desktop-downloads-empty.jpg` e `desktop-downloads-populated.jpg`. Nao representam downloads verdadeiros do usuario.
- Validacao apos as mudancas: 45 testes aprovados, 1 ignorado; compilacao sintatica passou; projeto original sem modificacoes. A previa Windows confirmou titulo completo, filtro de concluidos e bordas continuas no painel vazio. As capas online foram verificadas com resposta simulada; nao houve download real da API nesta validacao.
- Estatisticas desktop usa cartoes arredondados, contadores locais reais, grafico circular, leituras recentes e graficos reais por dia e semana. O armazenamento passou a registrar paginas unicas por data, duracao e quantidade de sessoes, sem apagar os totais antigos. Metadados reais da HQ alimentam a distribuicao de generos quando estiverem disponiveis. Sem historico, os graficos mostram um estado vazio. Testar com dados descartaveis: `tools/redesign_visual_preview.py --statistics-sample`.
- Descobrir e Meus envios usam cartoes arredondados, capas retornadas pela API, busca funcional e, nos envios, filtros pelos estados reais da publicacao. O botao Novo envio abre o fluxo de publicacao existente, sem duplicar regras de upload. As capas baixadas ficam em cache na tela para a busca nao solicitar a mesma imagem novamente. Dados de exemplo aparecem somente na previa descartavel (`--discover-sample` e `--submissions-sample`).
- Notificacoes preserva a API e o contador reais, acrescenta busca, filtros de lidas, nao lidas, envios e sistema, e exige um clique explicito para marcar como lida. Antes, apenas abrir a tela marcava todas automaticamente. Os cartoes nao mostram capas ficticias, porque as notificacoes da API atual nao incluem imagem. Previa descartavel: `--notifications-sample`.
- A Fase 2 desktop esta implementada. Permanecem diferencas visuais: as referencias mostram categorias de notificacao e graficos historicos que o backend ou armazenamento atual nao oferecem. A Fase 3 desktop comecou pelo Perfil; as fases Android ainda nao foram iniciadas.
- Previa Windows inspecionada visualmente nas telas Estatisticas, Descobrir, Meus envios e Notificacoes. Capturas em `docs/redesign-review/desktop-statistics-populated.jpg`, `desktop-discover-populated.jpg`, `desktop-submissions-populated.jpg`, `desktop-notifications-populated.jpg` e `desktop-notifications-empty.jpg`. O estado vazio agora usa painel amplo e a ilustracao de notificacoes isolada do painel de referencia; texto e botao para Descobrir continuam controles reais. Busca, filtro de nao lidas e marcacao explicita como lida foram testados na previa descartavel. A suite Python completa passou com 1 teste ignorado; compilacao sintatica passou; a pasta original continua sem mudancas no Git.

### Inicio da Fase 3 desktop

- A busca da Biblioteca agora usa a largura real disponivel e acompanha o redimensionamento da janela, evitando a largura curta na primeira exibicao em portugues. O mesmo componente continua funcionando em ingles.
- O Perfil recebeu titulo, cabecalho de conta mais destacado, e-mail visivel e cargos traduzidos como Dono, Admin, Moderador e Usuario. Os fluxos existentes de editar perfil, confirmar e-mail, trocar senha e 2FA foram preservados.
- Perfil agora possui bio real no banco, avatar local persistente, confirmacao da nova senha e lista de sessoes conectadas. O servidor guarda apenas um nome generico de plataforma, datas da sessao e atividade, sem inventar localizacao. Sessoes remotas podem ser encerradas; a sessao atual e protegida.
- Login e Cadastro foram reconstruidos em tela ampla com fundo noir, campos reais, recuperacao de senha, modo convidado secundario e 2FA exibido somente quando o servidor exigir. O cadastro passou a enviar nome de exibicao e confirmar a senha antes da requisicao.
- Moderacao ganhou busca por titulo/autor, filtros reais por status, contadores derivados da fila, banner de revisao e cartoes de acao mais proximos da referencia. A permissao continua sendo validada antes de mostrar a navegacao.
- Preferencias de idioma, tema, pasta, backup, restauracao, atualizacoes e diagnostico permanecem operacionais na sidebar da referencia. Nenhum toggle decorativo foi criado.
- Validacao desta etapa: 60 testes aprovados, 1 ignorado. Inclui testes do historico temporal e de listar/encerrar sessoes reais. A pasta original permanece sem alteracoes.

### Revisao visual transversal

- O design system agora possui radius pequeno, medio, grande e extragrande, alem da escala fixa de espacamento de 4 a 40 px. Botoes, campos, cards e navegacao deixam de escolher cantos arbitrarios.
- Botoes primarios receberam glow vermelho discreto por camadas leves de Canvas, com hover, pressionado, desabilitado, secundario e ghost coerentes.
- Sidebar, busca, filtros, acoes principais, estatisticas e controles centrais do leitor passaram a usar assets Lucide locais com estados normal, hover, ativo e branco. Os SVGs oficiais sao rasterizados durante o desenvolvimento, nunca baixados em runtime.
- A captura `docs/redesign-review/desktop-library-lucide.png` registra a Biblioteca populada depois da revisao e pode ser comparada com `references/desktop/desktop_library.png`.
- Android compartilha a mesma paleta, os mesmos tres radius principais e icones Lucide locais na navegacao inferior. Os botoes e inputs nativos agora usam superficies, bordas e estados consistentes, sem substituir a implementacao Java.
- Validacao: suite Python com 60 testes aprovados e 1 ignorado; compilacao Java Android concluida com sucesso usando JDK 21.

### Fechamento visual da Fase 3 e Fase 4 desktop

- Perfil, Login, Cadastro, Moderacao e os controles da sidebar receberam a ultima revisao visual da Fase 3. Cards, botoes, campos, selecao ativa e dispositivos de sessao usam radius centralizados, glow vermelho discreto e icones Lucide locais. O fundo reconstruido de autenticacao continua sendo usado nos fluxos de Login e Cadastro, sem transformar a imagem de referencia inteira em interface.
- O leitor desktop foi reconstruido mantendo a logica existente. A nova barra superior inclui voltar, favorito, tema, editor, preferencias, encaixe, Webtoon e tela cheia. O painel inferior concentra navegacao, pagina atual, zoom, brilho, modo manga, leitura guiada, rotacao, pagina dupla, marcadores e selecao de paginas.
- Zoom e brilho usam sliders reais desenhados no Canvas. Preferencias usam switches reais, salvam as configuracoes existentes e respeitam os conflitos entre pagina dupla e leitura guiada.
- A selecao de paginas carrega miniaturas reduzidas em segundo plano por uma fila segura para Tkinter. A pagina atual recebe borda e glow vermelhos, e clicar em qualquer miniatura navega para ela.
- Marcadores exibem somente paginas realmente salvas e permitem navegar ou remover. Sem marcadores, a janela usa o estado vazio correspondente.
- O editor manual preserva criar, selecionar, mover, redimensionar, excluir, reordenar, redetectar e salvar. A nova composicao possui trilho de paginas, Canvas central, caixas numeradas, handles, caminho de leitura, painel de propriedades e barra inferior de ferramentas.
- O dialogo de atalhos lista somente comandos funcionais. Foram ligados F1, Home, End, Ctrl+G, Ctrl+E, Ctrl+, e Espaco, alem dos atalhos do leitor que ja existiam.
- Leitura guiada, animacoes e transicoes existentes foram preservadas. O estado do botao guiado acompanha o modo real, sem controle decorativo.
- Capturas validadas: `docs/redesign-review/desktop-reader-phase4-final.png`, `desktop-reader-preferences-phase4-final.png`, `desktop-reader-pages-phase4-final.png`, `desktop-reader-bookmarks-phase4.png`, `desktop-reader-shortcuts-phase4-v2.png` e `desktop-panel-editor-phase4-final.png`.
- Validacao final desta etapa: compilacao sintatica passou; 65 testes aprovados e 1 ignorado. Os testes usaram `KOMICOVE_APPDATA_DIR` temporario.
- Diferencas visuais restantes: o Tkinter apresenta pequenas diferencas de antialiasing e tipografia em relacao aos mockups; a janela nativa e a barra de tarefas continuam controladas pelo Windows; o fundo do leitor nao possui a mesma textura isolada da referencia. A composicao, os controles e os dados continuam reais.

## Pendencias assumidas

As referencias sao tratadas como objetivo visual e funcional. Cada controle novo precisa usar dados e operacoes reais; quando ainda nao houver dados, a tela mostra um estado vazio. Nenhum dado ficticio sera usado em producao.
