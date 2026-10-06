# Komicove 0.2.1 📚

A 0.2.1 continua o trabalho da versão anterior, com melhorias na sincronização entre PC e Android, no leitor e no carregamento da biblioteca. Esta versão também traz o cargo Contribuidor e um sistema de mensagens de atualização integrado aos aplicativos.

## Novidades em relação à 0.2.0

### Sincronização entre PC e Android

- A mesma HQ passa a ser reconhecida entre os aparelhos, mesmo com caminhos diferentes no PC e URIs no Android.
- Progresso e favoritos são sincronizados automaticamente enquanto o aplicativo está em uso, com envio em lote.
- Alterações feitas offline ficam salvas para a próxima tentativa de sincronização.
- Conflitos seguem a data da alteração mais recente; empates preservam o estado já salvo no servidor.
- Migração dos identificadores antigos preservando progresso, favoritos e contas existentes.
- Reutilização de hashes e processamento em segundo plano para reduzir o trabalho repetido com arquivos grandes.

As HQs precisam estar disponíveis nos dois aparelhos. A sincronização compartilha progresso e favoritos; ela não transfere os arquivos da biblioteca.

### Leitor e leitura guiada

- No desktop, o leitor normal e o modo Webtoon abrem dentro da janela principal.
- Ao voltar à biblioteca, são preservados a busca, os filtros e a posição de rolagem.
- Detecção de quadros com IA local no desktop e no Android, com modelo incluído nos pacotes completos.
- Ajustes no foco, zoom, navegação e transições da leitura guiada.
- Indicação de detecção automática, quadros manuais e modo aproximado.
- Preferências separadas para manter o nível de zoom e a posição ao trocar de página.
- Melhorias na tela cheia do Android e no retorno aos controles.

A IA funciona localmente, sem enviar páginas para análise. A detecção continua experimental, com alternativa aproximada e prioridade para os quadros editados manualmente.

### Biblioteca e desempenho

- Carregamento da biblioteca desktop em segundo plano e criação dos cartões conforme a área visível.
- Melhor aproveitamento do cache de capas e cancelamento de tarefas que deixaram de ser necessárias.
- Reutilização de arquivos abertos durante a leitura de ZIP/CBZ.
- Ajustes nas pastas monitoradas e na escolha da origem disponível de uma HQ.

### Cargo Contribuidor

- Novo cargo obtido ao resgatar um token no perfil do desktop ou Android.
- Tokens seguros de uso único, gerados pela equipe no painel de moderadores.
- Administração dos tokens com revogação e histórico de resgate.
- Validação pelo servidor, sem conceder permissões de moderação ao Contribuidor.

### Atualizações dentro do Komicove

- Mensagens da equipe disponíveis no desktop e no Android, com título, versão, changelog e data.
- Criação manual com Markdown e preview, ou importação de uma Release oficial existente.
- Botão **Baixar** direcionado à Release da versão no GitHub ou à página oficial de downloads, conforme a escolha da equipe.
- Verificação de novas versões nos repositórios `PANEL-ComicBookReader` e `Komicove`, com comparação de versões e tratamento de duplicatas.
- Histórico de publicação e verificações de permissão no backend.

Importar uma Release apenas copia suas informações para o Komicove. Isso não cria nem modifica Releases no GitHub.

## Downloads

- **Windows 10/11:** `Komicove-Setup-0.2.1.exe`
- **Windows portátil:** `Komicove-Windows-0.2.1-portable.zip`
- **Linux x86_64:** `Komicove-Linux-0.2.1-x86_64.tar.gz` ou `Komicove-Linux-0.2.1-x86_64.flatpak`
- **Android 8 ou superior:** `Komicove-Android-0.2.1.apk`

O APK é universal, com suporte a ARM64, ARM de 32 bits, x86 e x86_64. Os pacotes completos incluem o modelo e o runtime da IA local.

O pacote Linux portátil foi compilado no Debian 13 com glibc 2.41. O Flatpak continua experimental e usa o runtime Freedesktop 25.08.

## Antes de atualizar

Faça um backup dos seus dados. No Android, o APK mantém a assinatura conferida com a instalação existente; atualizações de outras instalações também dependem de uma assinatura compatível.

A leitura local e o modo convidado continuam disponíveis sem internet. Conta, comunidade, mensagens de atualização e sincronização dependem da API.

Obrigado a todo mundo que está testando e ajudando o Komicove! ❤️

Encontrou um problema? Reporte nas [Issues do GitHub](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues).

Android version 0.2.1
