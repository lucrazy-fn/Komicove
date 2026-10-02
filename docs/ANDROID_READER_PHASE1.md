# Android — Fase 1: arquivos grandes, RAM, cache e rotação

Escopo: somente a lógica do leitor Android. Layout, funcionalidades, versão
0.2.0/10720, package de produção `com.lucrazy.panel`, biblioteca e preferências
foram preservados. Base comparada: `53ecd9541e5e16e2cdf6b72b0630d7ba16b6c9cd`.

## Implementação

- TAR/CBT: indexação por cabeçalhos, com saltos no arquivo. Não percorre cada
  payload para listar páginas. GNU long names, PAX e ordenação natural continuam
  suportados. Arquivos sparse mantêm o caminho sequencial do parser.
- 7Z/CB7: lista metadados e extrai apenas a entrada solicitada.
- RAR4/CBR: lista cabeçalhos e extrai a entrada solicitada. Em arquivos sólidos,
  reconstrói o dicionário com as entradas anteriores, descartando os bytes delas.
- RAR5: lista cabeçalhos diretamente, verifica CRC, tamanhos, extras, links,
  criptografia e dicionário antes da alocação nativa. Evita a descompactação de
  todo um RAR sólido só para obter a lista de páginas. A extração continua usando
  libarchive, com validação nativa do conteúdo.
- Decode em streams com buffer fixo: removida a cópia da página comprimida em
  dois arrays grandes. RGB565, amostragem, limite de 8 Mi pixels e limites de
  dimensões evitam alocações desnecessárias.
- `ReaderSession` retém preparação, fonte e bitmaps na mudança de configuração,
  sem guardar Activity/View. Página, modo, zoom, posição e controles recolhidos
  são restaurados; preferências e progresso continuam no storage existente.
- Cache de bitmaps: até `min(24 MiB, heap máximo / 8)`, mantém páginas próximas,
  evita dois decodes simultâneos da mesma página, é esvaziado sob pressão de
  memória e no fechamento definitivo. Não recicla um bitmap ainda exibido.
- Prefetch cancelável em executor separado e de prioridade baixa; thumbnails
  possuem fila limitada, vínculo fraco e cancelamento ao reciclar/desanexar a view.
  Navegação cancela trabalhos obsoletos e ignora resultados de gerações antigas.
- Locks de ciclo de vida e por página substituem a serialização de toda leitura.
  PDF continua serializado apenas no renderer, que exige esse cuidado.
- Cache de arquivos em `cache/reader-pages-v1`: identidade por caminho, tamanho
  e mtime; gravação `.part` e publicação após sucesso. Índice reutilizado no
  processo; páginas preparadas reutilizadas na reabertura. Limpeza apenas de
  arquivos reconhecidos nesse namespace, sem seguir symlinks; leases protegem
  entradas em uso. Pendências interrompidas são removidas antes da reutilização.

## Limites e compatibilidade

Mantidos: 10.000 páginas, 48 MiB por página e 1,5 GiB descompactados; o limite
de cópia/importação SAF de 768 MiB não foi ampliado. Acrescentados: 20.000
entradas, dicionário de até 64 MiB, cabeçalho RAR5 de até 2 MiB e nome de até
64 KiB. O limite total também considera os bytes realmente gravados no cache.
Links não são materializados como caminhos de saída. Nomes externos são
convertidos em arquivos numéricos internos, não usados como destinos.

Cache inativo: orçamento de 256 MiB, até quatro entradas e expiração de 30
minutos, aplicados ao adquirir/liberar/limpar; entradas ativas não são apagadas.
Um livro ativo pode usar mais de 256 MiB, até seu limite seguro de 1,5 GiB.

Não há migração de dados de usuário, dependência nova, reset ou mudança de
formato de biblioteca. O namespace novo contém apenas cache regenerável.
Temporários legados de versões antigas não são apagados por uma busca ampla.
As mensagens existentes continuam em PT/EN.

## Medição antes/depois no aparelho

Samsung SM-A266M via USB. Sete arquivos sintéticos, 16 BMPs de 1280×2048,
aproximadamente 120 MiB por arquivo. RAR4 armazenado; RAR5 e 7Z comprimidos,
incluindo versões sólidas. Nenhuma HQ pessoal foi usada.

Cada benchmark cria uma cópia com identidade nova, fora da janela medida,
para evitar cache de páginas já extraídas. A implementação anterior é compilada
somente no APK de instrumentação, não no APK do aplicativo. Ambas as versões
leem o mesmo arquivo; alvo de decode 1600. Tempo contado da abertura até o
bitmap decodificado (não inclui importação SAF, animação ou primeiro frame GPU).
Heap Java e heap nativo amostrados a cada 2 ms, até a primeira página. São
estimativas de alocação, não medições de RSS/PSS total do processo.

Rodada final comparativa, em ms:

| Arquivo | Preparação antes → depois | Primeira página antes → depois | Pico Java antes → depois, MiB |
|---|---:|---:|---:|
| TAR/CBT | 488,50 → 33,64 | 530,04 → 105,89 | 25,10 → 0,43 |
| 7Z/CB7 | 542,92 → 14,04 | 565,19 → 68,99 | 38,19 → 7,27 |
| RAR4/CBR | 838,31 → 9,32 | 862,04 → 63,87 | 39,95 → 12,56 |
| RAR5 | 235,86 → 11,93 | 259,40 → 42,54 | 23,75 → 0,60 |
| 7Z sólido | 512,47 → 11,61 | 538,74 → 54,52 | 30,04 → 7,23 |
| RAR5 sólido | 1627,00 → 11,09 | 1646,88 → 132,02 | 23,70 → 0,60 |
| CBZ/ZIP | 1,98 → 1,87 | 23,87 → 17,33 | 23,60 → 0,23 |

Nos seis formatos com extração, apenas 7.864.374 bytes (uma página, ~7,5 MiB)
estavam preparados na primeira página, em vez dos ~120 MiB anteriores.
Primeira/última/página anterior/revisita passaram em todos os arquivos.
O heap nativo permanece em ~5,1 MiB por primeira imagem; RAR5 sólido precisa
de ~64,3 MiB por seu dicionário, praticamente igual ao anterior. A redução é
principalmente nos arrays Java e na quantidade de imagens/payloads retidos.

Os números variam com temperatura, coleta de lixo e I/O. Em uma rodada anterior,
CBZ mediu 29,33 → 76,83 ms: streaming privilegia memória e não garante redução
de latência em toda execução. Não se trata de promessa universal de velocidade.

No teste local de TAR de 96 MiB: primeira página 853,91 → 367,79 ms;
reabertura 376,74 → 35,55 ms; extração 96 → 3 MiB. Robolectric não substitui
a medição nativa; serve como regressão reproduzível.

## Testes e reprodução

- `ArchivePerformanceTest`: TAR grande, indexação/extracão lazy, cache e
  reabertura, 7Z, nomes GNU/PAX, operações concorrentes, cancelamento de escrita,
  limpeza segura, orçamento real, limites de páginas/tamanho e dicionário RAR5,
  indexação RAR5/CRC. RAR4 sólido comprimido usa fixture opt-in.
- `ReaderSessionTest`: decode concorrente compartilha bitmap, descarte de páginas
  distantes, limite de cache e cache vazio após close.
- `ReaderPhase1Instrumentation`: arquivos grandes, navegação fora de ordem,
  rotação real da Activity (mesma fonte/sessão, zoom preservado), sequência rápida
  de sete saltos, progresso na reabertura e liberação de bitmaps no fechamento.
- Regressões existentes de importação, EPUB, biblioteca, coleções, favoritos,
  progresso, leitura guiada e editor são executadas junto da suíte Android.

Gerar fixtures em uma pasta nova e ignorada pelo Git:

```text
python tools/reader_phase1_fixtures.py android/build/phase1-fixtures-NOVA
```

O gerador usa WinRAR/7-Zip já instalados no Windows, não instala ferramentas.
Para a fixture pequena de RAR4 sólido comprimido, fonte oficial:
[RARaddin 48×48](https://www.rarlab.com/themes/RARaddin_48x48.theme.rar).
Esse arquivo é somente teste opt-in local: não foi adicionado ao app ou ao Git.
Definir `PANEL_TEST_RAR4` com seu caminho e `PANEL_TEST_CBZ` com a HQ sintética
para executar também as regressões opt-in de RAR4 e detecção de quadros.

```text
gradle --offline :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease
gradle --offline -PreaderBenchmark=true :app:assembleDebug :app:assembleDebugAndroidTest
```

O flag de benchmark modifica apenas o debug para `com.lucrazy.panel.phase1test`.
Isso permitiu testar sem desinstalar o app original, cuja assinatura difere da
debug local. O release e o debug normal mantêm o ID original e a versão 0.2.0.
O release compila sem assinatura oficial; nenhum keystore foi acessado.

No pacote isolado, copiar fixtures para um diretório pertencente ao UID do app
(`run-as`); copiar por ADB só para armazenamento externo pode produzir arquivos
que o processo do app não consegue abrir. Executar:

```text
adb shell am instrument -w -e fixtures CAMINHO_PRIVADO_DAS_FIXTURES -e rar4Solid CAMINHO_PRIVADO_RAR4 com.lucrazy.panel.phase1test.test/com.lucrazy.komicove.ReaderPhase1Instrumentation
```

`-e baseline true` exige uma cópia da classe BookSource do commit base renomeada
para `BaselineBookSource`, em `app/build/generated/phase1Baseline/com/lucrazy/komicove/`.
O sourceSet dessa pasta é exclusivo de androidTest. O runner recusa sobrescrever
sua entrada de biblioteca sintética e remove somente essa entrada ao terminar.

### Resultado final

- 39 testes Android: aprovados, zero falhas e zero skips, com as duas fixtures
  opt-in configuradas. Inclui o RAR4 sólido comprimido e a detecção de quadros
  nas 16 páginas da HQ grande.
- USB: sete arquivos grandes aprovados, RAR4 sólido comprimido aprovado,
  rotação/zoom/saltos rápidos/reabertura/liberação de cache aprovados.
- Suíte Python existente: 71 aprovados, um skip preexistente por exigir sessão
  gráfica Tk; sem falhas. Avisos de depreciação das dependências e de permissão
  no cache do pytest não impediram os testes.
- Builds Android debug e release: compilados; lint vital de release aprovado.
  APKs inspecionados: Komicove, `com.lucrazy.panel`, 0.2.0/10720. Nenhuma classe
  de baseline ou instrumentação dentro do APK normal. Release não assinado.
- `git diff --check`: aprovado. Desktop/backend não foram modificados.
- As três cópias dos arquivos sintéticos de USB (~2,5 GiB) foram removidas por
  nomes exatos dos diretórios de teste verificados. Não houve desinstalação do
  app original nem remoção de biblioteca pessoal; fixtures locais e gerador
  permitem repetir os testes.

## Arquivos alterados

```text
android/app/build.gradle
android/app/src/main/java/com/lucrazy/komicove/BookSource.java
android/app/src/main/java/com/lucrazy/komicove/Rar5Reader.java
android/app/src/main/java/com/lucrazy/komicove/ArchivePageCache.java
android/app/src/main/java/com/lucrazy/komicove/ReaderSession.java
android/app/src/main/java/com/lucrazy/komicove/ReaderActivity.java
android/app/src/main/java/com/lucrazy/komicove/LibraryStore.java
android/app/src/test/java/com/lucrazy/komicove/ArchivePerformanceTest.java
android/app/src/test/java/com/lucrazy/komicove/ReaderSessionTest.java
android/app/src/androidTest/java/com/lucrazy/komicove/ReaderPhase1Instrumentation.java
tools/reader_phase1_fixtures.py
docs/ANDROID_READER_PHASE1.md
```

## Critérios e exceções técnicas

- Arquivos grandes CBR/RAR/7Z/TAR, primeira página antes da extração completa,
  cache reutilizado, rotação sem nova preparação, descarte de bitmaps, cancelamento,
  prefetch separado, limpeza segura e limites: implementados e testados.
- ZIP/CBZ, EPUB e demais recursos anteriores não foram removidos.
- **Sólidos:** acessar uma página ainda não extraída pode exigir reconstruir
  dicionário desde entradas anteriores. Isso usa CPU/I/O, não salva as páginas
  anteriores em RAM ou extrai o livro inteiro. A primeira página na ordem natural
  também pode precisar dessa reconstrução se estiver no fim físico do arquivo.
- **Cancelamento nativo:** cooperativo entre cabeçalhos, buffers e decodes.
  Uma chamada interna de libarchive/BitmapFactory já em execução não pode ser
  interrompida instantaneamente; seu resultado obsoleto é descartado. Prefetch
  não ocupa a fila da página atual, embora ainda dispute CPU/I/O brevemente.
- **SAF não seekable:** é necessário copiar o arquivo comprimido para armazenamento
  privado antes de acessar formatos que precisam de seeks. A rotação preserva
  essa cópia durante a sessão. Não é uma extração completa de páginas.
- **Processo encerrado:** retenção em RAM vale para rotação no mesmo processo;
  após morte do processo, cabeçalhos são reindexados e páginas em disco podem ser
  reutilizadas quando a identidade do arquivo continua igual. Não há migração.
- **Arquivos acima dos limites:** rejeitados de forma segura, não promessa de
  suporte a qualquer tamanho/dicionário. Somente um modelo de celular foi testado.
