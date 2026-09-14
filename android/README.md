# PANEL Android — leitor nativo

Aplicativo Android em Java, separado da interface Tkinter do Windows. Android 8.0 ou superior (API 26). Versão 1.3.1, com leitor completo e integração com a API do PANEL.

## Biblioteca e leitura

- Importação de vários arquivos ou de uma pasta pelo seletor de documentos do Android.
- Cópias privadas das HQs, sem acesso amplo ao armazenamento. Desinstalar o app remove essas cópias; os originais selecionados permanecem no local de origem.
- Identificação SHA-256 para evitar duplicatas, capas, busca, favoritos, coleções e renomeação.
- Mantenha a capa pressionada para organizar, publicar ou remover uma HQ.
- Leitor com pinça, arrasto, duplo toque para zoom, gestos de página, botões e teclas de volume.
- Toque no centro para esconder/exibir controles. Miniaturas, marcadores, progresso e restauração de zoom.
- Página única, modo mangá, dupla inteligente (capa isolada, páginas horizontais sem par) e leitura vertical.
- Backup JSON de progresso, favoritos, coleções e marcadores. Reimporte as HQs antes de restaurar em outro celular. Não inclui os quadrinhos nem importa o JSON de backup do desktop.

## Formatos

CBZ/ZIP e PDF; TAR/CBT e 7Z/CB7 por bibliotecas embarcadas. CBR/RAR por Junrar, com limitações de compatibilidade (RAR5 não é suportado). Não precisa do programa 7-Zip do Windows. Arquivos com senha não são suportados. Até 768 MB por importação, 48 MB por página codificada e 1,5 GB de conteúdo descompactado. Imagens grandes são reduzidas para limitar o uso de memória. GIF é exibido como imagem estática.

## Comunidade

Configure a URL HTTPS do backend em **Ajustes**. A leitura local não precisa de conta ou servidor. `localhost` no telefone é o próprio telefone, não o PC. Esta versão não presume nenhum servidor público.

Inclui login/cadastro, código 2FA no login, perfil, troca de senha, notificações, sincronização manual de progresso e favoritos com os mesmos identificadores SHA-256 do desktop, Descobrir, downloads, publicação autorizada, Meus envios, remoção, denúncia de obras e fila de moderação conforme o cargo.

O token persistido é cifrado com uma chave do Android Keystore. Não há senha salva. Redirecionamentos HTTP são desativados para impedir envio do token a outro destino.

Pausar/continuar downloads funciona durante a sessão, não como retomada HTTP após matar o processo. Os concluídos ficam na biblioteca. Mantenha o app aberto durante transferências; não há serviço Android de download em segundo plano. A gestão avançada de usuários e tokens continua no painel web `/moderators`.

## Compilar

Abra esta pasta `android` no Android Studio, instale SDK 35 e Build Tools 35.0.0 e use JDK 17. Gradle 8.11.1 e Android Gradle Plugin 8.9.2 estão fixados no projeto. O Android Studio cria `local.properties` com o caminho do SDK; esse arquivo não deve ir para o Git.

No Windows:

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest
```

Ou execute `powershell -ExecutionPolicy Bypass -File .\build-apk.ps1`.

Saída: `app/build/outputs/apk/debug/app-debug.apk`. Esse APK é assinado com uma chave de desenvolvimento para testes. Para uma release, use **Build → Generate Signed App Bundle / APK** no Android Studio e guarde a chave permanente fora do repositório. Atualizações precisam usar a mesma chave e um `versionCode` maior em `app/build.gradle`.

Para instalar em um aparelho conectado com depuração USB: `adb install -r app/build/outputs/apk/debug/app-debug.apk`. Ou transfira o APK ao telefone e abra pelo gerenciador de arquivos, autorizando a instalação para esse aplicativo.

## Organização

- `MainActivity`: biblioteca, coleções, conta e comunidade.
- `ReaderActivity` e `ZoomPage`: leitura nativa e gestos.
- `BookSource`: PDF, arquivos compactados e limites de descompactação; não extrai nomes arbitrários para o sistema de arquivos.
- `LibraryStore`: importação, capas, progresso e backup.
- `PanelApi`: cliente HTTPS e sessão cifrada.
- `Ui`: cores e componentes compartilhados.
- Logo real em `app/src/main/res/drawable/panel_logo.png`.

## Antes de divulgar

Teste em um celular Android: importar pelo gerenciador de arquivos, girar a tela, voltar ao leitor, ler uma HQ grande, alternar modos, restaurar backup, testar offline e conectar à API. Os testes automatizados não substituem esses testes de toque e memória no aparelho.

Código sob a licença do projeto. Android SDK, OkHttp, Commons Compress, XZ e Junrar mantêm suas respectivas licenças. Consulte também `THIRD_PARTY.md`.
