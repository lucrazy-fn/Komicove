# Fase 5: identidade e sincronização PC/Android

`item_key` v2 identifica as páginas de imagem na ordem de leitura: SHA-256 de `komicove:pages:v2\0`, quantidade de páginas em 4 bytes big-endian e SHA-256 dos bytes de cada página. Caminho, URI, nome de entrada, compactação, comentário do arquivo e `ComicInfo.xml` não participam da identidade. Alterar uma imagem ou a ordem das páginas produz outra identidade. PDF e arquivos cujo decoder não está disponível preservam a identidade por bytes v1; não há comparação de imagens renderizadas nem tentativa de adivinhar identidade pelo título.

O SHA-256 original continua em `content_id`, nos IDs locais, caches do leitor e aliases v1. A correção responde a um caso reproduzido em aparelho: a mesma edição tinha páginas idênticas e 136 bytes de diferença no contêiner; os hashes v1 separavam seu progresso. A comparação de páginas corrigiu a correspondência, sem trocar IDs locais ou recriar estado.

## Migrações automáticas

- Desktop: `content_index.json` mantém `sha256`, tamanho e mtime e acrescenta `item_key` e `identity_version=2`. O índice é carregado uma vez por processo e salvo uma vez por lote. Hashes de arquivo já validados pelas pastas são reutilizados sem apagar o cache de páginas. A identificação de páginas ocorre uma vez na migração ou quando a assinatura do arquivo muda, sempre em worker, sem decodificar imagens.
- Desktop: `library_sync_state.json` acrescenta timestamps de favoritos, inclusive remoções, e um registro atômico do merge. Progresso inteiro, progresso com campos extras e listas antigas de favoritos continuam legíveis. Os arquivos anteriores continuam presentes. O registro permite recuperar um merge interrompido entre a gravação de progresso e favoritos. Backups continuam exportando progresso e favoritos no contrato existente.
- Android: `item_key`, `legacy_item_key` e `sync_updated_at` são acrescentados ao JSON existente, sem trocar `Book.id`, nomes de arquivos, capas, marcadores, coleções ou quadros manuais. Estado antigo com leitura/favorito usa o timestamp existente; itens sem leitura começam com timestamp de sync zero, evitando que uma importação recente apague leitura remota. O índice `content_identity/index` é gravado em SharedPreferences em lote.
- Backend: `init_db()` cria, via `Base.metadata.create_all`, a tabela adicional `library_state_aliases`, com alias exclusivo por conta. Não há recriação de banco nem mudança em `library_states`. `legacy_keys` aceita hashes v1 dos bytes e `uri-<sha256 da URI>`. A primeira requisição v2 migra transacionalmente esses registros e redireciona aliases URI previamente ligados ao hash v1, preservando o maior timestamp. Respostas incluem as chaves canônicas e os aliases, permitindo que clientes antigos continuem lendo e gravando. Um alias já ligado a outro conteúdo permanece protegido contra reassociação ambígua.

Atualize o backend antes dos clientes para habilitar a migração de aliases. Não é necessário configurar novos endpoints, variáveis, dependências ou chaves de assinatura. Não execute migração contra a biblioteca ou conta pessoal para validar: use os testes isolados.

O desktop atualiza a biblioteca visível após receber mudanças remotas, preservando a rolagem quando suportada pelo renderer. Respostas idênticas não regravam o estado nem provocam refresh. Outras telas e leitores abertos não são interrompidos.

## Conflitos, offline e lotes

`client_updated_at` usa segundos Unix, sem valores negativos, NaN ou infinito. Ganha o maior timestamp, mesmo se a página escolhida for anterior à atual. Empates com timestamp positivo preservam o estado já persistido no servidor. Empates zero são bootstrap legado: preservam favorito e a maior página não nula. Página nula significa ausência de leitura nesse aparelho e não apaga progresso. Clientes sem timestamp continuam aceitos, com timestamp atribuído pelo servidor.

Progresso e favorito formam o registro sincronizado desta fase. Edições locais recebem timestamp maior que o último estado conhecido. Depois da rede, o merge compara novamente o estado local, protegendo alterações feitas durante a requisição. As transações por conta são serializadas no backend. Aliases nunca atravessam contas.

Os clientes enviam lotes de até 5.000 registros, sem requisições por HQ. No Android, a resposta usa um índice em memória e uma única gravação da biblioteca. Hashing pesado e HTTP executam em workers. O desktop entrega o resultado pela fila à thread Tk; o Android não segura o monitor da biblioteca enquanto lê bytes.

Sync automático usa debounce de 1.500 ms e consulta/retry a cada 30 segundos enquanto o aplicativo está ativo. O Android retoma ao voltar à Activity principal. Falhas offline mantêm estado local, timestamps e remoções de favoritos para a próxima tentativa; não existe daemon com o aplicativo fechado.

URIs são abertas pelo ContentResolver, sem tentar convertê-las em caminhos. O cache compara tamanho e última modificação e reaproveita hashes das pastas já validados. Uma URI antiga ainda sem hash precisa estar acessível pelo menos uma vez; se estiver indisponível, permanece local, sem publicar a URI como identidade portátil. Provedores SAF que omitem metadados não permitem detectar alterações que mantenham a mesma assinatura; o digest conhecido é reutilizado até a assinatura mudar. Cópias privadas importadas já têm hash e são imutáveis pelos fluxos do app.

## Limites de escopo e verificação

Os merges alteram somente progresso, favorito e timestamps de leitura. Coleções, marcadores, quadros manuais e campos desconhecidos permanecem no armazenamento local e nos backups existentes. A identidade é independente desses domínios para extensões posteriores; nenhum payload ou recurso futuro foi ativado, e nenhuma tela foi criada.

`tests/test_sync_phase5.py` verifica o contrato comum, PC para Android e Android para PC, conflitos, timestamps inválidos, aliases de contas existentes, migração incremental idempotente, cache, debounce e recuperação offline/atômica. `LibrarySyncTest` verifica URIs reais em ContentResolver de teste, IDs legados, os dois sentidos, conflito durante a rede, persistência offline, invalidação de hash, lotes maiores que 5.000 e debounce automático. Ambos usam `android/app/src/test/resources/portable_identity_v1.json` como vetor compartilhado de identidade.

Comandos: `python -m pytest`; em `android/`, `gradlew.bat :app:testDebugUnitTest :app:assembleDebug`; build Windows: `build_installer.ps1 -ExecutableOnly`. Preserve o modelo local verificado nas variantes normais. Build Linux exige ambiente Linux/WSL; PostgreSQL exige serviço de teste próprio.

A validação inicial usou Robolectric porque a depuração USB estava indisponível. Em 05/10/2026, após a autorização USB, a instrumentação física passou no Galaxy A26 (SM-A266M), Android 16, ARM64. O APK instalado coincidiu por SHA-256 com o APK ARM64 entregue e abriu normalmente. Dez cenários passaram com ContentResolver real, backend local e conta descartável: identidade PC/URI, PC para Android, Android para PC, alias legado de conta existente, cache sem re-hash, edição durante a rede, conflitos/empates, falha de conexão e retry, lotes de 5.000/1, debounce de 1.500 ms e leitura/salvamento por URI. Um segundo processo confirmou persistência da identidade, progresso, favoritos e campos locais após force-stop.

O teste físico usa o pacote exclusivo `com.lucrazy.panel.phase5test`, não acessa a biblioteca da instalação principal e permite HTTP local somente nessa variante. O schema da API publicada também anunciou `legacy_keys` e `client_updated_at`; a sincronização autenticada da conta pessoal no servidor público não foi exercitada.

Resultados: suíte Python completa com 189 aprovados e 8 opcionais ignorados; verificação direcionada final no Windows com 27 aprovados; verificação direcionada no Linux/Debian WSL com 38 aprovados; Android com 99 testes, zero falhas e 3 opcionais ignorados, incluindo 9 testes desta fase. Builds Windows (PyInstaller), Linux (Python 3.13/Debian WSL) e Android debug com modelo local concluíram com sucesso. PostgreSQL não foi executado nesta validação; migração incremental e transações foram testadas em SQLite. O diff dos arquivos alterados passou em `git diff --check`.

O conteúdo isolado do commit da Fase 5 também foi validado sobre a base já versionada, sem depender das alterações locais anteriores: 106 testes Python aprovados, Android com 61 testes, zero falhas e 2 opcionais ignorados, e build Android debug aprovado. O teste que exige `.git` foi reexecutado após inicializar o repositório descartável de validação. A verificação direcionada final de sync e sessão nessa cópia teve 21 aprovados. O APK entregue da pasta principal preserva as funcionalidades locais já existentes.

## Arquivos desta fase

| Área | Arquivos |
| --- | --- |
| Desktop/cliente | `komicove_app/sync.py`, `komicove_app/storage.py`, `komicove_app/library_views.py`, `komicove_client/api_client.py` |
| Backend | `komicove_backend/accounts/models.py`, `komicove_backend/api/routes/account.py`, `komicove_backend/api/schemas.py` |
| Android | `android/app/src/main/java/com/lucrazy/komicove/ContentIdentity.java`, `LibrarySync.java`, `LibraryStore.java`, `MainActivity.java`, `I18n.java` (mesmo diretório) |
| Testes | `tests/test_sync_phase5.py`, `tests/conftest.py`, `android/app/src/test/java/com/lucrazy/komicove/LibrarySyncTest.java`, `android/app/src/test/resources/portable_identity_v1.json` |
| Documentação | `docs/PHASE5_SYNC.md` |
| Validação física | `tools/phase5_device_server.py`, `tools/phase5-device.gradle`, `android/app/src/androidTest/AndroidManifest-phase5.xml`, `AndroidManifest-phase5-target.xml` (mesmo diretório), `android/app/src/androidTest/java/com/lucrazy/komicove/LibraryPhase5Instrumentation.java`, `LibraryPhase5FixtureProvider.java` (mesmo diretório) |

## Repetir a validação física

1. Na raiz, execute `python tools/phase5_device_server.py --data-dir build/phase5-device-NOVO --port 18565`. Use um diretório novo: a ferramenta recusa reutilizar dados existentes e cria somente fixtures. O servidor escuta apenas em `127.0.0.1`.
2. Em `android/`, compile `gradlew.bat -I ../tools/phase5-device.gradle :app:assembleDebug :app:assembleDebugAndroidTest -PguidedAiAbis=arm64-v8a`. A opção de arquitetura deve corresponder ao aparelho.
3. Com ADB autorizado, faça `adb reverse tcp:18565 tcp:18565` e instale os APKs de teste gerados em `app/build/outputs/apk/debug/app-debug.apk` e `app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk`. Confira que o primeiro usa `com.lucrazy.panel.phase5test` antes de instalar.
4. Execute `adb shell am instrument -w -r -e base http://127.0.0.1:18565 com.lucrazy.panel.phase5test.test/com.lucrazy.komicove.LibraryPhase5Instrumentation`.
5. Execute `adb shell am force-stop com.lucrazy.panel.phase5test` e repita a instrumentação acrescentando `-e verifyOnly true` para verificar um processo novo.
6. Remova somente `com.lucrazy.panel.phase5test.test` e `com.lucrazy.panel.phase5test`, remova o reverse da porta 18565 e encerre o servidor. Compile novamente sem o init script para restaurar os artefatos de produção. Nenhuma credencial ou conta pessoal é necessária.
