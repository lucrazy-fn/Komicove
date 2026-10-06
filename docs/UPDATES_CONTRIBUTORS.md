# Atualizações e Contribuidores

## Uso

No painel `/moderators`, Moderador, Administrador e Dono podem gerar tokens de
Contribuidor, copiar o segredo exibido na criação, consultar o histórico e
revogar tokens ainda não utilizados. Cada token tem 256 bits aleatórios e
validade configurável de 1 a 8760 horas, com padrão de 120 horas. O banco guarda
somente SHA-256 do segredo. O segredo não pode ser recuperado pelo histórico.

No perfil desktop ou Android, uma conta com cargo Usuário pode escolher
**Resgatar token de Contribuidor**. O backend promove a conta e consome o token
na mesma transação. Tentativas simultâneas, tokens inválidos, expirados ou
revogados não deixam uma promoção parcial. Contas com outros cargos não são
rebaixadas e não consomem tokens. A sessão atual permanece válida. Contribuidor
não recebe permissões de moderação. Revogar um convite não altera o cargo de
uma conta que já o resgatou; convites utilizados permanecem no histórico.

Na aba Atualizações, a equipe pode escrever título, versão e changelog Markdown,
com preview, ou escolher uma Release de um dos dois repositórios oficiais.
O backend consulta novamente a Release por ID ao importar e guarda uma cópia do
conteúdo, repositório e link de origem. Não há upload de assets ou operações de
escrita na API do GitHub.

O destino Baixar é separado da origem do texto. GitHub usa automaticamente
`https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases/tag/vVERSAO`,
com a versão informada ou importada e um único prefixo `v`. O painel não aceita
links editáveis, e o backend rejeita tentativas de enviar um URL personalizado.
Site do Komicove usa `https://lucrazy-fn.github.io/Komicove/#downloads`.
A escolha fica salva na mensagem interna e não publica conteúdo nesses sites.
O histórico registra autor, data UTC, título, versão, texto, origem e destino.
Markdown não executa HTML, JavaScript ou imagens externas.

## Seleção de atualizações nos apps

As verificações existentes, no início do app e no botão Atualizações, consultam:

- `lucrazy-fn/PANEL-ComicBookReader`, preservando a fonte antiga;
- `lucrazy-fn/Komicove`;
- `/updates` da API Komicove, também disponível para convidados.

Versões são comparadas numericamente por major, minor e patch, com pré-release
abaixo da versão final. Prefixo `v`, patch omitido e metadados `+build` não
duplicam uma versão. A versão mais alta é apresentada primeiro; datas não
fazem uma versão inferior superar outra. Para versões iguais, a mensagem do
painel tem prioridade e preserva o destino escolhido pelo moderador. Entre
mensagens da mesma versão, vale a data mais recente. Em empate das Releases,
a fonte PANEL tem prioridade. Os dois nomes podem redirecionar para o mesmo
repositório e continuam sendo consultados sem gerar duas notificações.

Mantém-se a proteção existente contra tags antigas PANEL 1.x quando o app está
na série Komicove 0.x. No Android, mantém-se o marcador `Android version` no
changelog para selecionar a versão específica da plataforma. Releases draft ou
marcadas prerelease não entram na consulta automática ao GitHub.

Mensagens internas inéditas podem aparecer mesmo na versão instalada. Seus IDs
são registrados localmente ao exibir, inclusive na consulta manual, com limite
de 100. O changelog do autor permanece no idioma original. Uma fonte fora do
ar não impede o uso das demais. Se todas falharem, a consulta manual informa
a falha e a consulta automática permanece silenciosa, sem alterar leitura ou
sessão. O override desktop `KOMICOVE_UPDATE_MANIFEST_URL` ou o nome legado
`PANEL_UPDATE_MANIFEST_URL` continua substituindo apenas a primeira fonte.

## Migração e implantação

Instalar as dependências atuais do extra `server`, incluindo
`markdown-it-py>=3,<5`, e reiniciar a API com acesso de criação de tabelas no
banco já configurado. `init_db()` cria automaticamente `contributor_invites` e
`app_updates` e seus índices. O cargo é armazenado no campo `users.role`
existente; não há renomeação de IDs ou alteração de contas, sessões, biblioteca
ou convites administrativos antigos. A inicialização repetida é idempotente.

Não é necessária chave do GitHub: importações usam GETs públicos. A nova versão
da API deve ser implantada antes de distribuir os apps e painel com os novos
controles. Apps antigos continuam usando os endpoints existentes; apps novos
continuam consultando Releases mesmo se a API antiga responder 404 ao feed.
Publicar a API, distribuir os binários e enviar mensagens reais são operações
separadas da implementação local.

## Arquivos e validação

Backend: `accounts/models.py`, `accounts/contributor_invites.py`,
`api/schemas.py`, `api/app.py`, `api/routes/moderators.py`,
`api/routes/contributor_tokens.py`, `api/routes/updates.py`, `updates.py` e
`pyproject.toml`. Painel: `web/moderators.html`, `web/moderators-i18n.js` e
`web/moderators-features.js`, dentro de `komicove_backend/`.

Compartilhado: `komicove_client/releases.py` e `api_client.py`.
Desktop: `komicove_app/updater.py`, `account_views.py`, `auth.py`,
`library_views.py` e `translations.py`.
Android: `AppUpdates.java`, `PanelApi.java`, `MainActivity.java` e `I18n.java`
em `android/app/src/main/java/com/lucrazy/komicove/`.
Versão 0.2.1: `pyproject.toml`, `android/app/build.gradle`,
`installer/Komicove.iss` e a indicação do arquivo em `build_installer.ps1`.
`docs/RELEASE_0.2.1.md` contém a descrição pronta para a versão.

O APK usa `applicationId com.lucrazy.panel`, versão 0.2.1 e versionCode 10721,
acima da versão pública 0.2.0 (10720). O parâmetro opcional
`-PkomicoveAbis=arm64-v8a` compila o APK para aparelhos ARM64, incluindo Galaxy
A26; sem esse parâmetro, o build mantém as arquiteturas originais. A atualização
de uma instalação existente também exige a mesma assinatura do APK anterior.

Testes: `tests/test_contributors_updates.py`, `tests/test_update_sources.py`,
`tests/test_updates_ui.py`, `android/app/src/test/java/com/lucrazy/komicove/AppUpdatesTest.java`,
`android/app/src/test/resources/update_versions.json` e `tools/verify_moderators.py`.
Os testes usam contas e bancos isolados, sem promover usuários ou publicar
mensagens em produção. Cobrem concorrência, uso único, expiração, revogação,
permissões, preservação da migração, importação somente leitura, Markdown seguro,
duas fontes, deduplicação, comparação de versões, falhas parciais, PT/EN,
resgate no app e funcionamento dos botões de download.

Validação do checkout preparado para publicação: 136 testes Python aprovados;
68 testes Android, sem falhas, com 2 ignorados por fixtures externas. Builds
Windows, Linux e APK Android ARM64 0.2.1 executados. As alterações locais de
outros trabalhos foram preservadas e não fazem parte do commit desta entrega.
