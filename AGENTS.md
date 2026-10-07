# AGENTS.md: Komicove

Este documento contém versões equivalentes em Português do Brasil e Inglês. Caso exista qualquer diferença entre elas, a versão em português é a fonte de verdade. Ao atualizar estas instruções, mantenha as duas versões com exatamente o mesmo significado.

This document contains equivalent Brazilian Portuguese and English versions. If there is any difference between them, the Portuguese version is the source of truth. When updating these instructions, keep both versions identical in meaning.

## Português do Brasil (PT-BR)

### 1. Contexto, escopo e regra global de texto

- Komicove é um leitor gratuito e de código aberto, sob licença MIT, para organizar e ler quadrinhos locais no Windows, Linux e Android. A leitura local e o modo convidado funcionam sem conta ou internet. Conta, sincronização, comunidade, publicações e moderação usam a API opcional.
- Estas instruções abrangem este repositório Git, cuja raiz contém `pyproject.toml`, `komicove_app/`, `komicove_backend/` e `android/`. Não confunda a raiz com a pasta superior que contém backups, releases e outros checkouts.
- O código atual, inclusive alterações locais relevantes, é a fonte de verdade. Documentos de fases anteriores podem descrever planos ou estados antigos. Verifique a implementação antes de afirmar que um recurso existe ou está ausente.
- Nunca use o caractere Unicode U+2014 (travessão) em nenhum texto produzido pelo agente, incluindo código, comentários, documentação, mensagens, respostas, commits, logs ou arquivos gerados. Sempre substitua por vírgulas, dois pontos, parênteses ou hífens.
- Se algo já estiver implementado corretamente, não refaça. Não explique código óbvio. Faça as alterações diretamente e, no final, dê apenas um resumo curto, os arquivos alterados e os testes realizados.

### 2. Arquitetura e responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| `komicove_app/` | Desktop em Python 3.10+, Tkinter e Pillow; leitura, biblioteca, armazenamento local e telas. PyMuPDF renderiza PDF; rarfile e ferramentas externas atendem arquivos RAR. |
| `komicove_app/launcher.py`, `__main__.py` | Inicialização do desktop; o launcher pode iniciar uma API local quando o cliente está configurado para localhost e o app não está empacotado. |
| `komicove_app/runtime.py` | Integração compartilhada das telas, recursos, tema, idioma, componentes e carregamento de capas/páginas. Há definições históricas e reexportações: confira qual implementação é efetivamente usada. |
| `komicove_app/design/`, `components.py`, `library_widgets.py` | Tokens de cores, fontes, espaçamento, estilos, ícones e componentes reutilizados pela interface. |
| `komicove_app/archive.py`, `epub.py` | Formatos, listagem de páginas, extração de capas e carregamento incremental. |
| `komicove_app/library_views.py`, `library.py`, `collections.py`, `folder_views.py`, `monitored_folders.py`, `book_metadata.py` | Biblioteca, coleções, pastas monitoradas, metadados, busca e organização. |
| `komicove_app/reader_views.py`, `reader.py`, `guided.py`, `guided_ai.py`, `panel_editor.py` | Leitor, estado persistido, leitura guiada, IA local opcional e editor de quadros. |
| `komicove_app/storage.py`, `sync.py` | Dados locais em JSON, progresso, favoritos, marcadores, preferências, estatísticas, backup e identificação por conteúdo para sincronização. |
| `komicove_app/*_views.py`, `downloads.py`, `updater.py` | Telas de conta, autenticação, comunidade, publicações, moderação, notificações e estatísticas; downloads e verificação de atualização. |
| `komicove_client/` | Cliente HTTP Python baseado em requests e persistência da sessão desktop. |
| `komicove_backend/` | API FastAPI, schemas Pydantic, SQLAlchemy, contas, catálogo, assets, moderação e backup do servidor. `api/routes/` expõe os fluxos; `accounts/`, `catalog/` e `moderation/` concentram as regras. |
| `komicove_backend/web/` | Interface web da administração de moderadores. |
| `android/` | Aplicativo Android nativo em Java, Gradle e Android Gradle Plugin; implementação separada do desktop. |
| `android/app/src/main/java/com/lucrazy/komicove/` | Activities, biblioteca, cliente OkHttp, fontes de páginas, sessão do leitor, detector/editor de quadros, traduções e componentes nativos. |
| `android/app/src/main/res/` | Recursos visuais, temas, dimensões e ícones Android. |
| `tests/`, `android/app/src/test/`, `android/app/src/androidTest/` | Testes Python com pytest, testes Android com JUnit/Robolectric e instrumentação Android. |
| `tools/` | Validações, previews isolados, geração de ícones, fixtures, avaliação de IA e verificações de artefatos. |
| `installer/`, `build_installer.ps1` | Empacotamento desktop com PyInstaller e instalador Windows com Inno Setup. |
| `linux/`, `flatpak/` | Build portátil Linux e Flatpak experimental, manifesto, integração desktop e metadados. |
| `assets_redesign/`, `Icons/`, arquivos de logo/ícone na raiz | Assets locais distribuídos com o aplicativo, incluindo arte noir, estados vazios e ícones Lucide. |
| `docs/` | Documentação técnica, notas de release, capturas e site estático em HTML/CSS/JavaScript, sem etapa de build. |
| `.github/workflows/` | Workflow existente para manter a API ativa; não é uma pipeline de testes ou releases. |
| `ComicReader.py`, `panel_backend.py` | Entradas de compatibilidade com o projeto anterior PANEL. |

### 3. Formatos e comportamento de leitura

- Formatos locais reconhecidos: `.cbz`, `.zip`, `.cbr`, `.rar`, `.pdf`, `.7z`, `.cb7`, `.tar`, `.cbt` e `.epub`. As páginas de arquivos compactados podem estar em subpastas; imagens reconhecidas incluem JPG/JPEG, PNG, WebP, GIF e BMP. Preserve a ordenação natural das páginas. No Android, GIF é uma imagem estática.
- Desktop: ZIP/CBZ usam zipfile; PDF usa PyMuPDF; RAR/CBR usa 7-Zip quando disponível ou rarfile com ferramenta compatível; 7Z/CB7 e TAR/CBT requerem 7-Zip. Preserve a descoberta de `7z`/`7zz`, `KOMICOVE_7ZIP_PATH` e o fallback `PANEL_7ZIP_PATH`.
- Android: ZIP, PDF com PdfRenderer, 7Z/TAR com Commons Compress e XZ, RAR com Junrar e RAR5 com libarchive. Não dependa de executáveis desktop no Android.
- EPUB é experimental e voltado a quadrinhos com páginas em imagem, seguindo o spine. Não prometa suporte a EPUB de texto, DRM, recursos externos ou conteúdo complexo. Preserve as validações XML, de caminhos e de tamanho em `epub.py` e `EpubPages.java`.
- Arquivos protegidos por senha não são um formato de leitura suportado. Preserve mensagens claras para arquivo inválido, vazio, indisponível ou sem ferramenta de extração.
- Preserve página única, página dupla, modo mangá, leitura vertical/Webtoon, zoom, encaixe, rotação onde disponível, brilho, tela cheia, miniaturas, marcadores e retomada do progresso. As opções e os gestos variam por plataforma: confira o código antes de prometer paridade.
- Os formatos aceitos para publicação online são mais restritos que os formatos de leitura local. Consulte `komicove_backend/catalog/assets.py` antes de alterar upload ou divulgar suporte.

### 4. Preservação, arquitetura e refactors

- Inspecione `git status` antes de editar. Preserve alterações locais, arquivos não rastreados relevantes e trabalho fora do escopo; não restaure nem sobrescreva mudanças alheias.
- Faça a menor alteração que resolva a tarefa. Reutilize componentes e fluxos existentes. Não reescreva recursos funcionais para acomodar uma mudança visual.
- Não crie camadas, frameworks, dependências, abstrações genéricas ou refactors sem necessidade concreta para a tarefa. Não reorganize arquivos nem reformate módulos inteiros incidentalmente.
- Mudanças arquiteturais devem responder a uma necessidade explícita do escopo, identificar os consumidores afetados e preservar contratos, entradas, persistência e comportamento. Para mudanças maiores, siga a orientação do README de descrever a proposta em uma Issue antes de implementar.
- Preserve `ComicReader.py`, `panel_backend.py`, o comando `panel-reader`, fallbacks `PANEL_*` existentes e migrações de dados antigos enquanto houver consumidores compatíveis. Uma troca de nome visual não justifica removê-los.
- Não altere versões, identificadores de pacote, assinatura, endpoints públicos, esquema ou formato de backup como efeito colateral. Não execute scripts de commit, publicação, migração ou restauração incidentalmente.
- Quando o usuário pedir commit ou envio ao GitHub sem indicar o remoto, use sempre `public` (`https://github.com/lucrazy-fn/PANEL-ComicBookReader.git`). Só envie para `origin` quando o usuário pedir explicitamente o repositório privado.

### 5. UI/UX e identidade visual

- Preserve a identidade noir do Komicove: preto/grafite, acentos vermelhos, bordas finas, cantos arredondados, brilho discreto, tipografia legível e destaque para capas e conteúdo. Mantenha os temas claro e escuro e sua persistência.
- Use os tokens de `komicove_app/design/`, os helpers de `runtime.py` e os componentes existentes no desktop. No Android, reutilize `Ui.java` e os recursos nativos. Não espalhe novas cores, fontes ou medidas arbitrárias.
- Reutilize os ícones Lucide locais e suas variantes. SVGs são a fonte de geração, PNGs atendem o runtime desktop; CairoSVG pertence ao utilitário de desenvolvimento, não é requisito para abrir o app.
- Construa telas com controles reais. Não use screenshots de referências como interface, não embuta novos textos de interface em imagens e não substitua ações por controles decorativos.
- Use dados reais e estados vazios, de carregamento e de erro coerentes. Dados de demonstração ficam em previews/fixtures isolados, nunca na experiência de produção.
- Preserve busca, filtros, ordenação, foco, navegação por teclado, atalhos funcionais, rolagem, áreas de toque/clique e acesso de volta à biblioteca. Teste layouts pequenos e textos nos dois idiomas.
- Carregamento de capas, páginas, arquivos, rede e detecção não deve bloquear a interface. Preserve miniaturas reduzidas, caches limitados e entrega de resultados à thread da UI.

### 6. Internacionalização

- Os idiomas de interface são Português do Brasil (PT-BR) e Inglês (EN). Desktop e Android usam os valores persistidos `pt` e `en`; o site usa `pt-BR` e `en`. Não renomeie esses valores sem tratar compatibilidade.
- Todo texto visível ao usuário deve ser traduzível. Toda funcionalidade nova com texto visível deve incluir PT-BR e EN na mesma alteração. Nenhuma tela pode ficar parcialmente traduzida.
- Inclua títulos, botões, menus, diálogos, tooltips, estados vazios, erros, validações, notificações e descrições de acessibilidade. Não use strings de interface diretamente no código quando houver um sistema de i18n disponível.
- Desktop: use `komicove_app.translations.ui(portuguese, english)` para novos textos; preserve os catálogos existentes em `translations.py`, `themes.py` e `runtime.py`, conforme o consumidor. Não confie na substituição parcial de frases para traduzir uma nova mensagem completa.
- Android: adicione pares ao catálogo de `I18n.java` e use `I18n.t(context, texto)` ou componentes que já passam por ele, como `Ui`, `PanelDialog`, `AlertDialog` e `Toast`. Traduza também `setText`, hints e content descriptions fora desses helpers. Preserve o fallback de idioma das preferências `panel_ui`.
- Site: mantenha as mesmas chaves nos dois dicionários de `docs/translations.js`; use os atributos `data-i18n*` e `t(key)` de `docs/app.js`. Preserve o HTML estático em inglês, o seletor de idioma, metadados, textos alternativos, labels acessíveis e preferência persistida.
- Mensagens vindas da API precisam passar pelo tratamento/tradução da interface antes de serem apresentadas. Não traduza identificadores de protocolo nem conteúdo escrito pelo usuário como se fossem labels.
- Ao mudar idioma, confirme atualização consistente da tela e persistência após reabrir. Execute os testes de traduções e, quando aplicável, a validação do site.

### 7. Compatibilidade entre plataformas

- Windows e Linux compartilham o desktop Python/Tkinter; Android usa Java nativo. Não porte uma tela introduzindo dependências desktop no Android nem trate as duas implementações como código compartilhado.
- Windows: preserve descoberta de ferramentas, caminhos com espaços, `resource_path`, ícone da janela e execução sem console quando empacotada. O instalador usa PyInstaller e Inno Setup; preserve inclusão de assets e compatibilidade de atualização.
- Linux: preserve alternativas de fontes, maximização e grabs de Tk, eventos de roda, abertura com `xdg-open` e caminhos portáveis. Builds Linux devem rodar em Linux ou WSL. Não presuma que um binário portátil serve para qualquer glibc/distribuição.
- Flatpak: preserve recursos em `/app`, Tcl/Tk empacotado, integração desktop, permissões e diretório de dados definidos pelo manifesto. Mudanças em assets/dependências devem considerar também o pacote Flatpak experimental.
- Android: o mínimo atual é API 26 (Android 8); build usa Java 17 e SDKs definidos em `android/app/build.gradle`. Preserve `applicationId 'com.lucrazy.panel'`, apesar do namespace Java `com.lucrazy.komicove`, para manter atualizações e dados existentes.
- Preserve seletor de documentos/Storage Access Framework, URIs e permissões persistidas. Arquivos importados individualmente usam cópias privadas; arquivos de pastas ficam vinculados ao original, com cópia temporária para leitura. Não exclua os originais ao remover itens ou liberar cache.
- Preserve ciclo de vida, rotação, retomada, controles minimizáveis, gestos e teclas de volume do Android. `ReaderSession` sobrevive a mudanças de configuração sem guardar Activity/View; cancelamento, geração de callbacks e fechamento evitam resultados obsoletos e vazamentos.
- Preserve limites de importação, página, conteúdo descompactado, decodificação e cache presentes em `LibraryStore`, `BookSource` e `ArchivePageCache`. Não extraia ou decodifique o acervo inteiro para acelerar uma tela.
- Builds release Android usam as quatro variáveis de assinatura `KOMICOVE_KEYSTORE`, `KOMICOVE_STORE_PASSWORD`, `KOMICOVE_KEY_ALIAS` e `KOMICOVE_KEY_PASSWORD` quando configuradas. Sem elas, não trate o artefato como assinado para atualização. Não use uma nova chave nem desinstale o app para contornar incompatibilidade.
- Mudanças em bibliotecas nativas/empacotamento exigem verificar ABIs e alinhamento com `tools/verify_android_native.py`; alterações de compactação também têm `tools/verify_compact_apk.py`.

### 8. Dados locais, banco de dados e backups

- Desktop persiste JSON sob `APPDATA_DIR`, configurável por `KOMICOVE_APPDATA_DIR` e fallback `PANEL_APPDATA_DIR`. A migração `Panel` para `Komicove` copia dados sem substituir o destino nem apagar a origem; preserve esse comportamento.
- Preserve progresso antigo em inteiro e progresso com página/timestamp, favoritos, marcadores, status manual, metadados, preferências, estatísticas, estado do leitor, quadros manuais e identificação de conteúdo. Acrescente campos com defaults compatíveis, sem apagar dados desconhecidos incidentalmente.
- Preserve gravação pendente/flush do progresso, notificações de mudança e histórico que conta páginas reais sem inflar estatísticas por repaint.
- Android usa SharedPreferences e JSON para biblioteca/estado, além de arquivos privados e caches. Preserve identificação de conteúdo e dados de leitura ao atualizar fontes/pastas.
- Backups desktop, Android e servidor têm escopos e formatos diferentes. O backup Android não contém as HQs e não importa o JSON desktop; preserve reconhecimento do formato legado `panel-android`. Não prometa restauração cruzada sem implementação e testes.
- O backend usa SQLAlchemy, SQLite por padrão, preservando `panel.db` quando existente; há configuração de PostgreSQL via URL e dependência psycopg. Preserve `KOMICOVE_DATABASE_URL` e o fallback legado pelo helper `config_env.setting`.
- Migrações atuais estão em `komicove_backend/db.py`, com criação de tabelas e alterações incrementais. Não recrie nem limpe bancos existentes; mudanças de schema precisam de migração compatível, validação de dados antigos e atenção aos dialetos utilizados.
- Preserve sessões transacionais, commit, rollback e fechamento. Testes e previews devem usar bancos/dados descartáveis, nunca a biblioteca, o banco ou o storage reais.
- Não inclua `.env`, credenciais, sessões, bancos, storage privado, caches, modelos ou quadrinhos pessoais em commits ou artefatos públicos. Confira `.gitignore` e os scripts de empacotamento/backup antes de gerar entregas.

### 9. Biblioteca e pastas monitoradas

- Preserve biblioteca, capas, busca, filtros, favoritos, coleções, metadados, ordenação e continuação de séries. Use os algoritmos existentes de identificação e ordem natural; não invente a próxima edição quando os metadados forem ambíguos.
- Pastas monitoradas funcionam enquanto o app está ativo ou retoma a biblioteca, com atualização manual. Não prometa monitoramento permanente com o app fechado.
- Preserve deduplicação por conteúdo, estabilização/validação de arquivos, exclusões e resumo de importação. Uma nova varredura não deve reinserir silenciosamente um item explicitamente removido.
- Desativar pasta oculta seus itens sem apagar progresso. Arquivos removidos ficam indisponíveis preservando leitura; movimentos/renomeações devem reutilizar os dados quando identificáveis.
- Preserve `CoverLoader`, caches, filas e descarte de resultados de telas destruídas. Navegar, usar Mostrar mais ou voltar do leitor deve manter o estado relevante da biblioteca e sua rolagem.

### 10. Leitor e ciclo de vida

- O leitor desktop principal e o Webtoon ficam na janela existente, por `EmbeddedReader` e `EmbeddedWebtoon`; `ReaderWindow` e `WebtoonViewer` continuam disponíveis para hosts e ferramentas independentes. Reutilize `ReaderContent` e `WebtoonContent`.
- Preserve salvar ao trocar de HQ, voltar ou fechar; estado de página/zoom; opções de persistir zoom e encaixar; tratamento de capa e páginas horizontais na dupla; ordem de mangá; conflito entre dupla e guiada.
- Preserve retorno à tela anterior com busca, filtros, ordenação, coleção e rolagem. Remova bindings, timers e callbacks do leitor ao sair e restaure estado da janela.
- Mantenha preparação, extração, thumbnails e detecção em segundo plano. Atualizações Tk/objetos Tcl devem ocorrer na thread da UI; callbacks atrasados não podem acessar widgets destruídos nem substituir outra tela.
- Cancele resultados obsoletos ao abrir outra HQ ou sair e libere loaders, documentos PDF, imagens, caches, executores e recursos nativos segundo o ciclo de vida existente.

### 11. Guided reading e editor de quadros

- Leitura guiada é experimental. Preserve prioridade dos quadros manuais, regiões normalizadas, ordem comum/mangá, recorte/foco, transições, visão geral, retomada do quadro e preferências.
- Mantenha a distinção entre quadros detectados e trechos aproximados de fallback, incluindo status/confiança quando apresentados. Não anuncie precisão garantida.
- Redetectar não deve apagar nem sobrescrever quadros manuais automaticamente. Preserve o fluxo explícito do editor para criar, mover, redimensionar, excluir, reordenar e salvar.
- Preserve cache de detecção, versionamento, limites, cancelamento e validação de regiões. Uma detecção atrasada não pode mover o leitor para outra página.
- Desktop: `guided.py` fornece detecção/fallback e `guided_ai.py` usa ONNX Runtime/NumPy opcionais do extra `ai`. Preserve fallback quando o modelo ou runtime não estiver disponível, falhar ou estiver desativado por `KOMICOVE_GUIDED_AI=0`.
- Android: `PanelDetector`, `AiPanelDetector` e `OnnxPanelDetector` usam inferência local e fallback. O build normal procura `local_models/inkwell.onnx`, valida tamanho/hash e gera assets; `-PguidedAiModel=none` permite build sem pesos. Não baixe pesos automaticamente nem envie páginas à rede.
- Pesos ficam fora do Git e têm licença própria. Preserve checksum, pré-processamento, formato de entrada/saída e limites existentes; não altere o modelo ou seus parâmetros incidentalmente. Não inclua modelos na distribuição sem conferir suas condições de licença.

### 12. Autenticação, conta e segurança

- Preserve modo convidado e leitura offline quando a API falhar. Sessão inválida/expirada deve limpar o estado de autenticação necessário e permitir nova entrada, sem apagar a biblioteca local.
- Preserve hashing PBKDF2, comparação segura, tokens, restrições de conta, verificação de e-mail, recuperação de senha, TOTP/2FA, códigos de recuperação, sessões e auditoria. Mudanças nesses fluxos exigem testes de sucesso e rejeição.
- Permissões de usuário, moderador, admin e owner são verificadas pelo backend; esconder um botão não substitui autorização. Preserve autoria/propriedade e restrições de ações sensíveis.
- Desktop usa `komicove_client/session_store.py`; preserve gravação temporária e substituição do arquivo. Android cifra a sessão com Android Keystore/AES-GCM em `PanelApi`; preserve compatibilidade dos aliases/preferências existentes.
- Não exponha senha, token, segredo TOTP, códigos ou chaves em logs, UI, diagnóstico, fixtures públicas ou documentação. Preserve HTTPS, timeouts, tratamento de erros e restrições de redirects conforme o cliente existente.

### 13. Comunidade, publicações, moderação e rede

- Reutilize schemas, rotas e serviços atuais para catálogo, upload, downloads, capas, notificações, denúncias e moderação. Preserve contratos usados pelos clientes desktop e Android.
- Preserve validação de extensão/tamanho/conteúdo, caminhos seguros, armazenamento local/remoto e remontagem de assets em partes. Não amplie formatos de upload só porque o leitor local os aceita.
- Preserve decisões e estados de moderação, overrides manuais, permissões, propriedade da publicação e histórico. A IA de moderação do backend é distinta da detecção local de quadros do leitor.
- Downloads devem manter pausa, retomada e cancelamento onde implementados, progresso real, cache de capas e abertura somente de arquivos disponíveis. Falhas de rede não devem bloquear a leitura local.
- Preserve marcação explícita de notificações como lidas e sincronização por identificador de conteúdo/timestamp. Não use caminhos absolutos de um dispositivo como identidade universal de uma HQ.
- Atualizações e diagnóstico devem reutilizar `updater.py`, o cliente Android e os links/validações existentes. Não publique releases nem mude o servidor público como parte incidental de uma tarefa.

### 14. Comandos existentes

Execute os comandos na raiz deste repositório, salvo indicação. Use o Python do ambiente virtual escolhido (`python3` no Linux quando aplicável). Instalação/build podem precisar de ferramentas locais e rede; a presença do script não garante que estejam disponíveis.

| Objetivo | Comando e requisito |
| --- | --- |
| Dependências para build, testes e API | `python -m pip install -e ".[build,test,server]"`; extras definidos em `pyproject.toml`. Tkinter/Tcl/Tk também precisa estar disponível. |
| IA opcional desktop | `python -m pip install -e ".[ai]"`; pesos verificados são separados. |
| Iniciar desktop | `python -m komicove_app`; no Windows também existe `startapp.bat`. Entradas instaladas: `komicove` e `panel-reader`. |
| API local de desenvolvimento | `python -m uvicorn komicove_backend.api.app:app --host 127.0.0.1 --port 8000`; configure banco/storage de desenvolvimento antes de iniciar. |
| Suíte Python | `python -m pytest`; `pyproject.toml` aponta para `tests/` e desativa cacheprovider. |
| Teste Python específico | `python -m pytest tests/test_translations.py`; substitua pelo teste relevante existente. |
| Smoke da interface desktop | `python tools/redesign_smoke.py`; usa dados temporários e requer ambiente gráfico. |
| Executável Windows | `.\build_installer.ps1 -ExecutableOnly`; exige `.venv\Scripts\python.exe` e dependências do extra `build`. |
| Instalador Windows | `.\build_installer.ps1`; também exige Inno Setup/ISCC. |
| Portátil Linux | `bash linux/build.sh`; executar no Linux/WSL com PyInstaller e Tcl/Tk. |
| Flatpak experimental | `bash linux/build-flatpak.sh`; executar no Linux/WSL com flatpak-builder e SDK/runtime do manifesto. |
| APK debug Windows | `.\android\build-apk.ps1`; exige JDK 17, SDK Android e modelo padrão verificado. |
| APK release Windows | `.\android\build-apk.ps1 -Release`; confira assinatura e requisitos do modelo. |
| Testes unitários Android | Em `android/`: `.\gradlew.bat :app:testDebugUnitTest` no Windows ou `./gradlew :app:testDebugUnitTest` no Linux; requer toolchain e modelo padrão. Sem pesos, acrescente `-PguidedAiModel=none` e valide essa variante como tal. |
| Build Android sem modelo | Em `android/`: `.\gradlew.bat :app:assembleDebug -PguidedAiModel=none` ou `./gradlew :app:assembleDebug -PguidedAiModel=none`. |
| Verificação de bibliotecas nativas | `python tools/verify_android_native.py CAMINHO_DO_APK_OU_AAB`; substitua o argumento por artefato existente. |
| Preview do site | `node tools/preview-site.cjs`; requer Node.js, serve em `http://127.0.0.1:4173`. |
| Verificação estática do site | `node tools/verify-site.cjs`; verifica traduções, estrutura, assets e sintaxe JavaScript. |

### 15. Testes e validação

- Selecione testes conforme o risco: formatos/EPUB, pastas/deduplicação, migração/backup, leitor/retorno/transições, guided reading/IA, traduções, contas/sessões/permissões, publicações/capas/storage e telas afetadas. Amplie para a suíte pertinente quando a mudança atravessar componentes.
- Preserve isolamento de `tests/conftest.py`, que usa AppData temporário e desativa IA local por padrão para fixtures determinísticas. Defina dados temporários antes de importar módulos que criam diretórios/bancos. Limpe overrides e recursos usados nos testes.
- Testes Android locais usam JUnit/Robolectric; instrumentação em `src/androidTest` valida leitor e pastas com runners/variantes próprios. Consulte os arquivos e a documentação Android antes de instalar uma variante de teste.
- O usuário autoriza o uso do próprio PC para testar o Komicove e da depuração USB para testar no celular conectado, quando necessário. O agente pode executar esses testes sem pedir novamente essa autorização, preservando os dados e as instalações existentes.
- Para UI, teste PT-BR/EN, claro/escuro, tamanhos relevantes, foco, navegação, reabertura, persistência e resultados reais. Use previews isolados em `tools/`; não use conta ou acervo pessoal para fixtures.
- Quando não houver display, toolchain, modelo, aparelho ou plataforma, registre o que não foi validado. Não declare sucesso de build, teste visual, IA ou compatibilidade entre plataformas sem execução correspondente.
- Ajustes de empacotamento exigem conferir assets/ícones, dependências opcionais, inicialização do artefato e plataforma afetada; validar fonte não substitui validar o pacote.
- Corrija problemas causados pela alteração e repita os testes afetados. Não enfraqueça testes nem modifique comportamento não relacionado para esconder falhas. Mudanças exclusivamente documentais pedem revisão e validação do documento, sem builds que produzam artefatos desnecessários.

### 16. Processo recomendado

1. Inspecionar a raiz, instruções aplicáveis, estado Git, arquivos, consumidores e testes antes de alterar.
2. Entender o fluxo existente, dados persistidos, idiomas, ciclo de vida e diferenças entre plataformas.
3. Fazer somente as alterações necessárias, reutilizando a implementação correta e mantendo traduções juntas.
4. Testar o comportamento afetado com dados isolados e executar as validações pertinentes.
5. Corrigir problemas introduzidos, repetir verificações necessárias e conferir o diff final.
6. Resumir o resultado de forma curta, com arquivos alterados e testes/limitações de validação.

### 17. Critérios de conclusão

- O pedido foi atendido no escopo combinado, sem refactors ou mudanças incidentais.
- Funcionalidades existentes, dados antigos, contratos e compatibilidade das plataformas afetadas foram preservados ou a mudança necessária foi explicitamente tratada e validada.
- Textos novos estão completos e coerentes em PT-BR e EN, sem telas parcialmente traduzidas.
- Testes e verificações relevantes foram executados; falhas introduzidas foram resolvidas; validações não executadas estão identificadas.
- O diff contém somente arquivos necessários, preserva mudanças prévias e não inclui dados pessoais, segredos ou artefatos gerados incidentalmente.
- Textos produzidos não contêm U+2014. Alterações deste documento mantêm equivalência entre PT-BR e EN.
- A resposta final contém somente resumo curto, arquivos alterados e testes/validações realizados.

### 18. Referências visuais do redesign

- No repositório: `docs/REDESIGN_ASSETS.md` mapeia referências e assets; `docs/REDESIGN_PLAN.md` e `docs/REDESIGN_FEATURE_GAP.md` guardam contexto histórico. Não transforme restrições de fases antigas em proibições permanentes nem trate planos como implementação atual.
- Assets em uso: `assets_redesign/backgrounds/`, `banners/`, `empty_states/`, `placeholders/` e `icons/`; no Android, `android/app/src/main/res/drawable/` e `drawable-xxhdpi/`. Capturas atuais de divulgação ficam em `docs/screenshots/`.
- As referências originais ainda existem fora do Git deste repositório, em `C:/Users/Luanz/OneDrive/Desktop/Imagens REDESIGN/PT2/`. Consulte `README.txt` e `manifest.csv`; telas ficam em `references/desktop/`, `references/mobile/` e `references/empty_states/`, com arte em `assets/` e exemplos em `samples/`.
- Esse caminho externo é uma referência local, não uma dependência de build. Em outro ambiente, confira sua disponibilidade; não invente caminhos alternativos ou copie telas inteiras para a UI. Preserve os originais e escolha a referência da plataforma correta.

## English (EN)

### 1. Context, scope and global text rule

- Komicove is a free, MIT-licensed open-source reader for organizing and reading local comics on Windows, Linux and Android. Local reading and guest mode work without an account or internet. Accounts, synchronization, community, publications and moderation use the optional API.
- These instructions cover this Git repository, whose root contains `pyproject.toml`, `komicove_app/`, `komicove_backend/` and `android/`. Do not confuse the root with the parent directory containing backups, releases and other checkouts.
- Current code, including relevant local changes, is the source of truth. Documents from earlier phases may describe plans or old states. Check the implementation before claiming that a feature exists or is missing.
- Never use the Unicode U+2014 character (em dash) in any text produced by the agent, including code, comments, documentation, messages, responses, commits, logs or generated files. Always replace it with commas, colons, parentheses or hyphens.
- If something is already implemented correctly, do not redo it. Do not explain obvious code. Make the changes directly and, at the end, provide only a short summary, the changed files, and the tests performed.

### 2. Architecture and responsibilities

| Path | Responsibility |
| --- | --- |
| `komicove_app/` | Python 3.10+, Tkinter and Pillow desktop; reading, library, local storage and screens. PyMuPDF renders PDF; rarfile and external tools handle RAR archives. |
| `komicove_app/launcher.py`, `__main__.py` | Desktop startup; the launcher can start a local API when the client is configured for localhost and the app is not packaged. |
| `komicove_app/runtime.py` | Shared screen integration, resources, theme, language, components and cover/page loading. Historical definitions and reexports exist: check which implementation is actually used. |
| `komicove_app/design/`, `components.py`, `library_widgets.py` | Color, font, spacing, style and icon tokens, and components reused by the interface. |
| `komicove_app/archive.py`, `epub.py` | Formats, page listing, cover extraction and incremental loading. |
| `komicove_app/library_views.py`, `library.py`, `collections.py`, `folder_views.py`, `monitored_folders.py`, `book_metadata.py` | Library, collections, monitored folders, metadata, search and organization. |
| `komicove_app/reader_views.py`, `reader.py`, `guided.py`, `guided_ai.py`, `panel_editor.py` | Reader, persisted state, guided reading, optional local AI and panel editor. |
| `komicove_app/storage.py`, `sync.py` | Local JSON data, progress, favorites, bookmarks, preferences, statistics, backup and content identification for synchronization. |
| `komicove_app/*_views.py`, `downloads.py`, `updater.py` | Account, authentication, community, publication, moderation, notification and statistics screens; downloads and update checking. |
| `komicove_client/` | requests-based Python HTTP client and desktop session persistence. |
| `komicove_backend/` | FastAPI API, Pydantic schemas, SQLAlchemy, accounts, catalog, assets, moderation and server backup. `api/routes/` exposes the flows; `accounts/`, `catalog/` and `moderation/` hold the rules. |
| `komicove_backend/web/` | Web interface for moderator administration. |
| `android/` | Native Java Android app, Gradle and Android Gradle Plugin; separate implementation from desktop. |
| `android/app/src/main/java/com/lucrazy/komicove/` | Activities, library, OkHttp client, page sources, reader session, panel detector/editor, translations and native components. |
| `android/app/src/main/res/` | Android visual resources, themes, dimensions and icons. |
| `tests/`, `android/app/src/test/`, `android/app/src/androidTest/` | Python tests with pytest, Android tests with JUnit/Robolectric and Android instrumentation. |
| `tools/` | Validation, isolated previews, icon generation, fixtures, AI evaluation and artifact checks. |
| `installer/`, `build_installer.ps1` | Desktop packaging with PyInstaller and Windows installer with Inno Setup. |
| `linux/`, `flatpak/` | Portable Linux and experimental Flatpak builds, manifest, desktop integration and metadata. |
| `assets_redesign/`, `Icons/`, root logo/icon files | Local assets distributed with the app, including noir artwork, empty states and Lucide icons. |
| `docs/` | Technical documentation, release notes, screenshots and static HTML/CSS/JavaScript website with no build step. |
| `.github/workflows/` | Existing workflow to keep the API awake; it is not a test or release pipeline. |
| `ComicReader.py`, `panel_backend.py` | Compatibility entry points for the former PANEL project. |

### 3. Formats and reading behavior

- Recognized local formats: `.cbz`, `.zip`, `.cbr`, `.rar`, `.pdf`, `.7z`, `.cb7`, `.tar`, `.cbt` and `.epub`. Archive pages may be in subdirectories; recognized images include JPG/JPEG, PNG, WebP, GIF and BMP. Preserve natural page ordering. On Android, GIF is a static image.
- Desktop: ZIP/CBZ use zipfile; PDF uses PyMuPDF; RAR/CBR uses 7-Zip when available or rarfile with a compatible tool; 7Z/CB7 and TAR/CBT require 7-Zip. Preserve discovery of `7z`/`7zz`, `KOMICOVE_7ZIP_PATH` and the `PANEL_7ZIP_PATH` fallback.
- Android: ZIP, PDF with PdfRenderer, 7Z/TAR with Commons Compress and XZ, RAR with Junrar and RAR5 with libarchive. Do not depend on desktop executables on Android.
- EPUB is experimental and targets comics with image pages, following the spine. Do not promise support for text EPUB, DRM, external resources or complex content. Preserve XML, path and size validation in `epub.py` and `EpubPages.java`.
- Password-protected archives are not a supported reading format. Preserve clear messages for invalid, empty or unavailable files and missing extraction tools.
- Preserve single page, double page, manga mode, vertical/Webtoon reading, zoom, fit, rotation where available, brightness, fullscreen, thumbnails, bookmarks and progress resumption. Options and gestures vary by platform: check the code before promising parity.
- Formats accepted for online publication are more restricted than local reading formats. Consult `komicove_backend/catalog/assets.py` before changing upload or advertising support.

### 4. Preservation, architecture and refactors

- Inspect `git status` before editing. Preserve local changes, relevant untracked files and work outside scope; do not restore or overwrite others' changes.
- Make the smallest change that solves the task. Reuse existing components and flows. Do not rewrite working features to accommodate a visual change.
- Do not introduce layers, frameworks, dependencies, generic abstractions or refactors without a concrete task need. Do not incidentally reorganize files or reformat entire modules.
- Architectural changes must address an explicit need within scope, identify affected consumers and preserve contracts, entry points, persistence and behavior. For larger changes, follow the README guidance to describe the proposal in an Issue before implementing.
- Preserve `ComicReader.py`, `panel_backend.py`, the `panel-reader` command, existing `PANEL_*` fallbacks and legacy data migrations while compatible consumers remain. A visual rename does not justify removing them.
- Do not change versions, package identifiers, signing, public endpoints, schema or backup format as a side effect. Do not incidentally run commit, publishing, migration or restore scripts.
- When the user requests a commit or GitHub push without naming a remote, always use `public` (`https://github.com/lucrazy-fn/PANEL-ComicBookReader.git`). Only push to `origin` when the user explicitly requests the private repository.

### 5. UI/UX and visual identity

- Preserve Komicove's noir identity: black/graphite, red accents, thin borders, rounded corners, subtle glow, readable typography and emphasis on covers and content. Maintain light and dark themes and their persistence.
- Use `komicove_app/design/` tokens, `runtime.py` helpers and existing desktop components. On Android, reuse `Ui.java` and native resources. Do not scatter arbitrary new colors, fonts or dimensions.
- Reuse local Lucide icons and their variants. SVGs are the generation source, PNGs serve the desktop runtime; CairoSVG belongs to the development utility and is not required to open the app.
- Build screens with real controls. Do not use reference screenshots as the interface, embed new interface text in images or replace actions with decorative controls.
- Use real data and consistent empty, loading and error states. Demo data belongs in isolated previews/fixtures, never in the production experience.
- Preserve search, filters, sorting, focus, keyboard navigation, working shortcuts, scrolling, touch/click areas and access back to the library. Test small layouts and text in both languages.
- Loading covers, pages, files, network data and detection must not block the interface. Preserve reduced thumbnails, bounded caches and delivery of results to the UI thread.

### 6. Internationalization

- Interface languages are Brazilian Portuguese (PT-BR) and English (EN). Desktop and Android use persisted values `pt` and `en`; the website uses `pt-BR` and `en`. Do not rename these values without handling compatibility.
- All user-visible text must be translatable. Every new feature with visible text must include PT-BR and EN in the same change. No screen may remain partially translated.
- Include titles, buttons, menus, dialogs, tooltips, empty states, errors, validation, notifications and accessibility descriptions. Do not use interface strings directly in code when an i18n system is available.
- Desktop: use `komicove_app.translations.ui(portuguese, english)` for new text; preserve existing catalogs in `translations.py`, `themes.py` and `runtime.py` according to the consumer. Do not rely on partial phrase replacement to translate a new complete message.
- Android: add pairs to the `I18n.java` catalog and use `I18n.t(context, text)` or components already using it, such as `Ui`, `PanelDialog`, `AlertDialog` and `Toast`. Also translate `setText`, hints and content descriptions outside those helpers. Preserve the language fallback from `panel_ui` preferences.
- Website: maintain the same keys in both `docs/translations.js` dictionaries; use `data-i18n*` attributes and `t(key)` from `docs/app.js`. Preserve static English HTML, the language selector, metadata, alternative text, accessible labels and persisted preference.
- API messages must pass through the interface's handling/translation before being presented. Do not translate protocol identifiers or user-written content as interface labels.
- When changing language, confirm consistent screen updates and persistence after reopening. Run translation tests and, when applicable, website validation.

### 7. Cross-platform compatibility

- Windows and Linux share the Python/Tkinter desktop; Android uses native Java. Do not port a screen by introducing desktop dependencies on Android or treat the two implementations as shared code.
- Windows: preserve tool discovery, paths with spaces, `resource_path`, window icon and execution without a console when packaged. The installer uses PyInstaller and Inno Setup; preserve asset inclusion and update compatibility.
- Linux: preserve font alternatives, Tk maximization and grabs, wheel events, opening with `xdg-open` and portable paths. Linux builds must run on Linux or WSL. Do not assume a portable binary works with every glibc/distribution.
- Flatpak: preserve resources in `/app`, packaged Tcl/Tk, desktop integration, permissions and data directory defined by the manifest. Asset/dependency changes must also consider the experimental Flatpak package.
- Android: the current minimum is API 26 (Android 8); builds use Java 17 and SDKs defined in `android/app/build.gradle`. Preserve `applicationId 'com.lucrazy.panel'`, despite the Java namespace `com.lucrazy.komicove`, to maintain updates and existing data.
- Preserve the document picker/Storage Access Framework, URIs and persisted permissions. Individually imported files use private copies; folder files remain linked to originals, with a temporary reading copy. Do not delete originals when removing items or releasing cache.
- Preserve Android lifecycle, rotation, resumption, collapsible controls, gestures and volume keys. `ReaderSession` survives configuration changes without retaining Activity/View; cancellation, callback generation and closing prevent stale results and leaks.
- Preserve import, page, uncompressed content, decoding and cache limits in `LibraryStore`, `BookSource` and `ArchivePageCache`. Do not extract or decode the entire collection to speed up a screen.
- Android release builds use all four signing variables `KOMICOVE_KEYSTORE`, `KOMICOVE_STORE_PASSWORD`, `KOMICOVE_KEY_ALIAS` and `KOMICOVE_KEY_PASSWORD` when configured. Without them, do not treat the artifact as signed for updates. Do not use a new key or uninstall the app to bypass incompatibility.
- Native library/packaging changes require checking ABIs and alignment with `tools/verify_android_native.py`; compression changes also have `tools/verify_compact_apk.py`.

### 8. Local data, database and backups

- Desktop persists JSON under `APPDATA_DIR`, configurable through `KOMICOVE_APPDATA_DIR` and the `PANEL_APPDATA_DIR` fallback. The `Panel` to `Komicove` migration copies data without replacing the destination or deleting the source; preserve this behavior.
- Preserve legacy integer progress and progress with page/timestamp, favorites, bookmarks, manual status, metadata, preferences, statistics, reader state, manual panels and content identification. Add fields with compatible defaults without incidentally deleting unknown data.
- Preserve pending progress writes/flush, change notifications and history that counts real pages without inflating statistics through repaints.
- Android uses SharedPreferences and JSON for library/state, plus private files and caches. Preserve content identification and reading data when updating sources/folders.
- Desktop, Android and server backups have different scopes and formats. Android backup does not contain comics and does not import desktop JSON; preserve recognition of legacy `panel-android` format. Do not promise cross-restoration without implementation and tests.
- The backend uses SQLAlchemy, SQLite by default, preserving `panel.db` when present; PostgreSQL configuration through a URL and the psycopg dependency exist. Preserve `KOMICOVE_DATABASE_URL` and the legacy fallback through `config_env.setting`.
- Current migrations are in `komicove_backend/db.py`, with table creation and incremental changes. Do not recreate or clear existing databases; schema changes need compatible migration, validation of old data and attention to the dialects used.
- Preserve transactional sessions, commit, rollback and closing. Tests and previews must use disposable databases/data, never the real library, database or storage.
- Do not include `.env`, credentials, sessions, databases, private storage, caches, models or personal comics in commits or public artifacts. Check `.gitignore` and packaging/backup scripts before generating deliveries.

### 9. Library and monitored folders

- Preserve library, covers, search, filters, favorites, collections, metadata, sorting and series continuation. Use existing identification and natural ordering algorithms; do not invent the next issue when metadata is ambiguous.
- Monitored folders work while the app is active or resumes the library, with manual refresh. Do not promise permanent monitoring with the app closed.
- Preserve content deduplication, file stabilization/validation, exclusions and import summary. A new scan must not silently reinsert an explicitly removed item.
- Disabling a folder hides its items without deleting progress. Removed files become unavailable while preserving reading data; moves/renames must reuse data when identifiable.
- Preserve `CoverLoader`, caches, queues and rejection of results for destroyed screens. Navigating, using Show more or returning from the reader must maintain relevant library state and scrolling.

### 10. Reader and lifecycle

- The main desktop reader and Webtoon use the existing window through `EmbeddedReader` and `EmbeddedWebtoon`; `ReaderWindow` and `WebtoonViewer` remain available for standalone hosts and tools. Reuse `ReaderContent` and `WebtoonContent`.
- Preserve saving when changing comics, returning or closing; page/zoom state; persist zoom and fit options; cover and landscape page handling in double page; manga ordering; conflict between double page and guided reading.
- Preserve return to the previous screen with search, filters, sorting, collection and scrolling. Remove reader bindings, timers and callbacks when leaving and restore window state.
- Keep preparation, extraction, thumbnails and detection in the background. Tk/Tcl object updates must happen on the UI thread; delayed callbacks must not access destroyed widgets or replace another screen.
- Cancel stale results when opening another comic or leaving, and release loaders, PDF documents, images, caches, executors and native resources according to the existing lifecycle.

### 11. Guided reading and panel editor

- Guided reading is experimental. Preserve manual panel priority, normalized regions, standard/manga ordering, cropping/focus, transitions, overview, panel resumption and preferences.
- Maintain the distinction between detected panels and approximate fallback regions, including status/confidence when shown. Do not advertise guaranteed accuracy.
- Redetection must not automatically delete or overwrite manual panels. Preserve the explicit editor flow for creating, moving, resizing, deleting, reordering and saving.
- Preserve detection cache, versioning, limits, cancellation and region validation. Delayed detection must not move the reader to another page.
- Desktop: `guided.py` provides detection/fallback and `guided_ai.py` uses optional ONNX Runtime/NumPy from the `ai` extra. Preserve fallback when the model or runtime is unavailable, fails or is disabled by `KOMICOVE_GUIDED_AI=0`.
- Android: `PanelDetector`, `AiPanelDetector` and `OnnxPanelDetector` use local inference and fallback. The normal build looks for `local_models/inkwell.onnx`, validates size/hash and generates assets; `-PguidedAiModel=none` allows building without weights. Do not automatically download weights or send pages over the network.
- Weights remain outside Git and have their own license. Preserve existing checksum, preprocessing, input/output format and limits; do not incidentally change the model or its parameters. Do not include models in distribution without checking their license conditions.

### 12. Authentication, accounts and security

- Preserve guest mode and offline reading when the API fails. Invalid/expired sessions must clear the necessary authentication state and allow signing in again without deleting the local library.
- Preserve PBKDF2 hashing, secure comparison, tokens, account restrictions, email verification, password recovery, TOTP/2FA, recovery codes, sessions and auditing. Changes to these flows require success and rejection tests.
- User, moderator, admin and owner permissions are checked by the backend; hiding a button does not replace authorization. Preserve authorship/ownership and restrictions on sensitive actions.
- Desktop uses `komicove_client/session_store.py`; preserve temporary writes and file replacement. Android encrypts the session with Android Keystore/AES-GCM in `PanelApi`; preserve compatibility of existing aliases/preferences.
- Do not expose passwords, tokens, TOTP secrets, codes or keys in logs, UI, diagnostics, public fixtures or documentation. Preserve HTTPS, timeouts, error handling and redirect restrictions according to the existing client.

### 13. Community, publications, moderation and networking

- Reuse current schemas, routes and services for catalog, upload, downloads, covers, notifications, reports and moderation. Preserve contracts used by desktop and Android clients.
- Preserve extension/size/content validation, safe paths, local/remote storage and multipart asset reassembly. Do not expand upload formats just because the local reader accepts them.
- Preserve moderation decisions and states, manual overrides, permissions, publication ownership and history. Backend moderation AI is separate from the reader's local panel detection.
- Downloads must maintain pause, resume and cancellation where implemented, real progress, cover cache and opening only available files. Network failures must not block local reading.
- Preserve explicit marking of notifications as read and synchronization by content identifier/timestamp. Do not use absolute paths from one device as a comic's universal identity.
- Updates and diagnostics must reuse `updater.py`, the Android client and existing links/validation. Do not publish releases or change the public server incidentally as part of a task.

### 14. Existing commands

Run commands from this repository's root unless indicated otherwise. Use Python from the chosen virtual environment (`python3` on Linux when applicable). Installation/build may require local tools and networking; a script's presence does not guarantee their availability.

| Purpose | Command and requirement |
| --- | --- |
| Build, test and API dependencies | `python -m pip install -e ".[build,test,server]"`; extras defined in `pyproject.toml`. Tkinter/Tcl/Tk must also be available. |
| Optional desktop AI | `python -m pip install -e ".[ai]"`; verified weights are separate. |
| Start desktop | `python -m komicove_app`; Windows also has `startapp.bat`. Installed entry points: `komicove` and `panel-reader`. |
| Local development API | `python -m uvicorn komicove_backend.api.app:app --host 127.0.0.1 --port 8000`; configure development database/storage before starting. |
| Python suite | `python -m pytest`; `pyproject.toml` targets `tests/` and disables cacheprovider. |
| Specific Python test | `python -m pytest tests/test_translations.py`; replace with the relevant existing test. |
| Desktop interface smoke | `python tools/redesign_smoke.py`; uses temporary data and requires a graphical environment. |
| Windows executable | `.\build_installer.ps1 -ExecutableOnly`; requires `.venv\Scripts\python.exe` and `build` extra dependencies. |
| Windows installer | `.\build_installer.ps1`; also requires Inno Setup/ISCC. |
| Portable Linux | `bash linux/build.sh`; run on Linux/WSL with PyInstaller and Tcl/Tk. |
| Experimental Flatpak | `bash linux/build-flatpak.sh`; run on Linux/WSL with flatpak-builder and the manifest's SDK/runtime. |
| Windows debug APK | `.\android\build-apk.ps1`; requires JDK 17, Android SDK and the verified default model. |
| Windows release APK | `.\android\build-apk.ps1 -Release`; check signing and model requirements. |
| Android unit tests | In `android/`: `.\gradlew.bat :app:testDebugUnitTest` on Windows or `./gradlew :app:testDebugUnitTest` on Linux; requires toolchain and default model. Without weights, add `-PguidedAiModel=none` and validate that variant as such. |
| Android build without model | In `android/`: `.\gradlew.bat :app:assembleDebug -PguidedAiModel=none` or `./gradlew :app:assembleDebug -PguidedAiModel=none`. |
| Native library verification | `python tools/verify_android_native.py PATH_TO_APK_OR_AAB`; replace the argument with an existing artifact. |
| Website preview | `node tools/preview-site.cjs`; requires Node.js, serves at `http://127.0.0.1:4173`. |
| Static website verification | `node tools/verify-site.cjs`; checks translations, structure, assets and JavaScript syntax. |

### 15. Tests and validation

- Select tests according to risk: formats/EPUB, folders/deduplication, migration/backup, reader/return/transitions, guided reading/AI, translations, accounts/sessions/permissions, publications/covers/storage and affected screens. Expand to the relevant suite when the change crosses components.
- Preserve isolation in `tests/conftest.py`, which uses temporary AppData and disables local AI by default for deterministic fixtures. Set temporary data before importing modules that create directories/databases. Clean up overrides and resources used in tests.
- Local Android tests use JUnit/Robolectric; instrumentation in `src/androidTest` validates the reader and folders with dedicated runners/variants. Consult the files and Android documentation before installing a test variant.
- The user authorizes use of their PC to test Komicove and USB debugging to test on the connected phone when necessary. The agent may run these tests without requesting this authorization again, preserving existing data and installations.
- For UI, test PT-BR/EN, light/dark, relevant sizes, focus, navigation, reopening, persistence and real results. Use isolated previews in `tools/`; do not use personal accounts or collections for fixtures.
- When a display, toolchain, model, device or platform is unavailable, record what was not validated. Do not claim successful build, visual testing, AI or cross-platform compatibility without corresponding execution.
- Packaging changes require checking assets/icons, optional dependencies, artifact startup and the affected platform; validating source does not replace validating the package.
- Fix problems caused by the change and rerun affected tests. Do not weaken tests or modify unrelated behavior to hide failures. Documentation-only changes require document review and validation, without builds producing unnecessary artifacts.

### 16. Recommended process

1. Inspect the root, applicable instructions, Git state, files, consumers and tests before changing anything.
2. Understand the existing flow, persisted data, languages, lifecycle and platform differences.
3. Make only necessary changes, reusing correct implementation and keeping translations together.
4. Test affected behavior with isolated data and run relevant validation.
5. Fix introduced problems, repeat necessary checks and inspect the final diff.
6. Summarize the result briefly, with changed files and tests/validation limitations.

### 17. Completion criteria

- The request is fulfilled within the agreed scope, without refactors or incidental changes.
- Existing functionality, old data, contracts and affected platform compatibility are preserved, or the necessary change is explicitly handled and validated.
- New text is complete and consistent in PT-BR and EN, with no partially translated screens.
- Relevant tests and checks were run; introduced failures were resolved; unperformed validation is identified.
- The diff contains only necessary files, preserves prior changes and does not include personal data, secrets or incidentally generated artifacts.
- Produced text contains no U+2014. Changes to this document maintain PT-BR/EN equivalence.
- The final response contains only a short summary, changed files and tests/validation performed.

### 18. Redesign visual references

- In the repository: `docs/REDESIGN_ASSETS.md` maps references and assets; `docs/REDESIGN_PLAN.md` and `docs/REDESIGN_FEATURE_GAP.md` retain historical context. Do not turn old phase restrictions into permanent prohibitions or treat plans as current implementation.
- Assets in use: `assets_redesign/backgrounds/`, `banners/`, `empty_states/`, `placeholders/` and `icons/`; on Android, `android/app/src/main/res/drawable/` and `drawable-xxhdpi/`. Current promotional screenshots are in `docs/screenshots/`.
- Original references still exist outside this repository's Git, at `C:/Users/Luanz/OneDrive/Desktop/Imagens REDESIGN/PT2/`. Consult `README.txt` and `manifest.csv`; screens are in `references/desktop/`, `references/mobile/` and `references/empty_states/`, with artwork in `assets/` and examples in `samples/`.
- This external path is a local reference, not a build dependency. In another environment, check availability; do not invent alternative paths or copy entire screens into the UI. Preserve originals and choose the correct platform reference.
