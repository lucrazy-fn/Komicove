# Fase 5: identidade e sincronização PC/Android

`item_key` v1 é o SHA-256 hexadecimal minúsculo dos bytes originais da HQ. Caminho, URI, nome e extensão não participam do hash. Cópias idênticas compartilham a identidade; recomprimir ou editar o arquivo produz outra identidade.

## Migrações automáticas

- Desktop: `content_index.json` mantém o formato anterior. O índice é carregado uma vez por processo e salvo uma vez por lote. Os hashes já validados pelo índice de pastas são reutilizados quando tamanho e mtime ainda correspondem.
- Desktop: `library_sync_state.json` acrescenta timestamps de favoritos, inclusive remoções, e um registro atômico do merge. Progresso inteiro, progresso com campos extras e listas antigas de favoritos continuam legíveis. Os arquivos anteriores continuam presentes. O registro permite recuperar um merge interrompido entre a gravação de progresso e favoritos. Backups continuam exportando progresso e favoritos no contrato existente.
- Android: `item_key`, `legacy_item_key` e `sync_updated_at` são acrescentados ao JSON existente, sem trocar `Book.id`, nomes de arquivos, capas, marcadores, coleções ou quadros manuais. Estado antigo com leitura/favorito usa o timestamp existente; itens sem leitura começam com timestamp de sync zero, evitando que uma importação recente apague leitura remota. O índice `content_identity/index` é gravado em SharedPreferences em lote.
- Backend: `init_db()` cria, via `Base.metadata.create_all`, a tabela adicional `library_state_aliases`, com alias exclusivo por conta. Não há recriação de banco nem mudança em `library_states`. A migração de `uri-<sha256 da URI>` para o hash dos bytes ocorre transacionalmente na primeira requisição com `legacy_keys`. Respostas incluem as chaves canônicas e os aliases, permitindo que clientes antigos continuem lendo e gravando. A associação antiga permanece ligada ao conteúdo original se a URI passar a apontar para outros bytes.

Atualize o backend antes dos clientes para habilitar a migração de aliases. Não é necessário configurar novos endpoints, variáveis, dependências ou chaves de assinatura. Não execute migração contra a biblioteca ou conta pessoal para validar: use os testes isolados.

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

Instrumentação e instalação em aparelho Android físico não foram executadas nesta validação: a depuração USB está indisponível. A verificação Android usa Robolectric e o build debug com o modelo local normal.

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
