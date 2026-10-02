# Fase 2 — pastas monitoradas (Komicove 0.2.0)

## Escopo

Pastas persistentes, atualização automática/manual, duplicatas silenciosas,
identidade por SHA-256 do **arquivo completo**, indisponibilidade e movimentação
sem apagar progresso. Nenhum endpoint ou versão foi alterado.

As referências `Fase 02 - Pastas Monitoradas PC.png` e
`Fase 02 - Pastas Monitoradas Android.png` foram abertas e comparadas.
No desktop, o usuário preferiu restaurar o visual compacto anterior; a lógica
nova e a atualização incremental foram mantidas. Android mantém o header,
bottom navigation, safe area e os componentes existentes, com cards da fase.
Capas são reais ou placeholders locais; não foram adicionados dados fictícios
ao aplicativo de produção.

## Funcionamento

- PC: rescan em thread a cada 10 segundos; arquivos pendentes são revistos
  após aproximadamente 3 segundos. A verificação de arquivos conhecidos usa
  caminho, tamanho e mtime, sem reabrir/hash/decomprimir cada HQ. Links e
  junctions não são seguidos. Pastas sobrepostas preservam ambas as associações.
- Android: árvores SAF persistidas, rescan em executor separado a cada 15
  segundos enquanto a biblioteca está em primeiro plano, e na retomada do app.
  Pendências são verificadas após 3,5 segundos. Ao sair, tarefas são canceladas.
  A preparação do leitor não compete no mesmo executor com a varredura.
- As ações Atualizar pasta/Atualizar todas fazem uma reconciliação conjunta das
  raízes ativas: isso permite reconhecer movimentos entre pastas cadastradas.
- A importação de uma pasta produz somente um resumo ao terminar o lote.
  Duplicatas não geram um aviso por arquivo. Imports avulsos Android também
  produzem um resumo por lote.
- Antes de importar: duas observações estáveis, validade do arquivo, limites
  do leitor e nova verificação dos metadados depois de ler/hash. No SAF,
  `FLAG_PARTIAL` bloqueia a importação. Falhas temporárias de acesso são
  tentadas novamente; arquivos inválidos conhecidos não são reabertos sem
  mudança nos metadados.
- Temporários Android são exclusivos em `cacheDir` e removidos em `finally`;
  arquivos de origem nunca são alterados pelo monitoramento.
- Arquivos removidos permanecem na biblioteca como indisponíveis. Renomeação
  ou movimento com conteúdo idêntico recupera a mesma identidade. Arquivos
  com imagens internas de nomes iguais não compartilham a identidade/cache.
- Pausar/remover o cadastro de uma pasta não exclui arquivos ou progresso.
  Ativar/desativar está disponível diretamente em cada linha/card (botão
  desktop, switch Android), além do menu. A preferência é persistida; uma
  pasta desativada não importa HQs novas até ser reativada e suas HQs ficam
  ocultas na biblioteca/Continuar lendo/agrupamentos. Nada é apagado do índice.
  Uma HQ associada também a outra pasta ativa continua visível; cópias locais
  independentes Android não são ocultadas. Reativar restaura as HQs e progresso.
- Android: **Mostrar mais** amplia a grade no mesmo ScrollView e preserva a
  posição; não reconstrói a página inteira nem volta ao topo.
- Desktop possui ação **Voltar à biblioteca**. Android tem o botão **Pastas**
  também com a biblioteca vazia; ele abre o cadastro e a ação **Adicionar
  pasta** usa o seletor SAF real. Corrigida a largura zero desse botão.
- Atualizações desktop de contador, data, estado e resumo não recriam a tela:
  busca, widgets, menus e rolagem permanecem estáveis durante as verificações.
  Callbacks de resumo são associados ao frame que os criou e descartados
  quando a tela é destruída. Isso evita `can't delete Tcl command` e
  atualizações de labels destruídos ao navegar/reabrir a tela.
  A tabela usa a altura real do conteúdo; linhas têm altura mínima, mas
  podem crescer com fontes/escala de tela. Isso evita cortar a última pasta
  e seu botão Ativar/Desativar (regressão verificada em três escalas Tk).

## Compatibilidade e migração

PC: novo `monitored_folders.json`, versão 1, na pasta de dados do aplicativo.
Na primeira criação, a pasta legada é cadastrada automaticamente. O arquivo
antigo de configuração é preservado, inclusive campos desconhecidos. O índice
é salvo por arquivo temporário + substituição atômica. Fontes antigas indexadas
apenas por caminho continuam sendo lidas e são normalizadas após confirmação.
`folder_covers/` contém somente thumbnails derivadas e pode ser regenerado.

Movimentos PC copiam as chaves de progresso, marcadores, favoritos, status e
metadados para o novo caminho, sem apagar as chaves antigas ou sobrescrever
dados existentes no destino. Estatísticas mantêm a identidade por conteúdo.

Android: a preferência legada `library_folders/uris` é migrada para `registry`
sem reset. Os campos novos dos livros (`available`, `fingerprint`, `sources`)
têm defaults compatíveis. IDs antigos são preservados quando a origem antiga
é reconhecida. Progresso, favoritos, coleções, marcas e preferências permanecem
nos registros existentes; gravações do leitor não desfazem indisponibilidade
ou localização atualizada pelo monitor. Nenhuma migração destrutiva é usada.

Não há dependência nova. Os limites de profundidade, quantidade de entradas,
tamanho e expansão dos arquivos continuam ativos.

## Verificação

- Suíte Python completa: **91 passaram**, sem skips; dois avisos de
  depreciação preexistentes. Inclui as regressões de atualização incremental
  da tela e preservação da rolagem.
- Suíte Android/Robolectric completa: **50 passaram, 2 ignorados**, sem
  falhas. Os dois testes opcionais dependem de fixtures externas
  `PANEL_TEST_RAR4` e `PANEL_TEST_CBZ`, não fornecidas nesta execução.
- Compilação Windows/PyInstaller e APK Android debug normal **0.2.0**
  concluídas. O pacote normal permanece `com.lucrazy.panel`; não foi
  instalado sobre o aplicativo pessoal do aparelho.
- Testes Python: pasta com 300 HQs, nova HQ, duplicata, remoção, movimento,
  reabertura do índice, raízes sobrepostas, arquivo incompleto/inválido,
  reutilização de metadados, watcher e isolamento de `001.jpg`/`002.jpg`.
- Testes Tk: 50 atualizações sem recriar widgets ou deslocar a rolagem;
  atualização/remoção do resumo sem recriar a tabela; navegação/reabertura
  após destruição dos controles ou reconstrução da sidebar; ativação
  persistente e ação de voltar à biblioteca.
- Android/Robolectric: 300 HQs, metadados sem releitura, duplicatas, novas,
  removidas/renomeadas, permissão revogada, FLAG_PARTIAL, remoção manual,
  gravação obsoleta do leitor, renomeação com mesmo document ID e título
  personalizado preservado.
  Inclui switch visível com persistência, pausa/retomada sem perder progresso
  e o botão Pastas com largura real na biblioteca vazia, abrindo a tela e
  o seletor `ACTION_OPEN_DOCUMENT_TREE` através de Adicionar pasta.
- Aceitação USB: pacote `.phase2test` separado, provedor SAF de fixtures
  sintéticas registrado **somente no APK de testes**. A suíte se recusa a
  sobrescrever uma biblioteca existente e nunca limpa o pacote original.
  Passaram importação de 302 HQs, duplicatas, registro/permissões SAF,
  arquivo novo/removido, movimento entre pastas, progresso/favoritos,
  isolamento das imagens internas e abertura da tela nativa.
  A última validação automática com a tela em primeiro plano permanece
  pendente: o aparelho bloqueou e pausou a atividade durante a execução.
  O APK de teste mantém a tela acesa durante essa verificação, mas exige
  desbloqueio pelo usuário antes de começar.
- Prévia desktop usa pasta de dados temporária e HQs sintéticas, sem abrir
  sessão, biblioteca ou pastas pessoais.

## Limitações objetivas

- SAF não oferece watcher universal para provedores arbitrários. Detecção
  automática ocorre com a biblioteca aberta ou na próxima retomada; não foi
  criado serviço permanente quando o app está fechado.
- Sem cooperação do produtor, não é possível provar que um arquivo válido e
  parado por vários segundos não será modificado depois. São usados estabilidade,
  validação e rechecagem. A garantia absoluta exige publicação por rename
  atômico/arquivo temporário ou um provedor que sinalize `FLAG_PARTIAL`.
- Metadados inconsistentes/ausentes de provedores SAF reduzem a confiabilidade
  de detecção de mudanças. Movimentos fora das raízes cadastradas ficam
  indisponíveis até que a nova pasta seja adicionada.
- O rescan portátil PC funciona com o app aberto. Não há daemon do sistema.
- Linux validado posteriormente no Debian 13/WSL2 instalado pelo usuário:
  91 testes passaram, PyInstaller compilou, assets do binário passaram e
  o usuário aprovou a interface aberta no WSLg. Flatpak gerado/instalado,
  com imports, versão, assets e inicialização Tk verificados. O Ubuntu antigo
  com disco ausente não foi apagado/reinstalado. Debian nativo e outras
  distribuições não foram testados nesta execução.

## Arquivos desta fase

- Desktop: `komicove_app/monitored_folders.py`, `folder_views.py`,
  `library_views.py`, `library_widgets.py`, `runtime.py`, `storage.py`.
- Android: `MonitoredFolders.java`, `MonitoredFoldersView.java`,
  `MainActivity.java`, `LibraryStore.java`, `I18n.java` em
  `android/app/src/main/java/com/lucrazy/komicove/`; `android/app/build.gradle`;
  drawables `lucide_refresh.xml`, `lucide_x.xml`, `lucide_more_horizontal.xml`.
- Testes: `tests/test_monitored_folders.py`, `tests/test_folder_views.py`,
  `MonitoredFoldersTest.java`; manifesto de `androidTest` e
  `FolderPhase2Instrumentation.java`, `FolderFixtureProvider.java`,
  `FolderFixtureControlProvider.java` (fixtures apenas no pacote isolado).
- Prévia isolada: `tools/phase2_desktop_preview.py`.
- Documentação: `docs/PHASE2_FOLDERS.md`.

Os demais arquivos já alterados pela Fase 1 não foram revertidos. Nenhum
commit/push funcional, alteração de versão ou limpeza de dados pessoais foi
realizado. A publicação posterior de `docs/index.html` alterou somente o site
para registrar a validação no Debian 13 via WSL2.
