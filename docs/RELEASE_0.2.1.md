# Komicove v0.2.1

Pacotes completos para Android, Windows e Linux.

- Novo cargo **Contribuidor**, obtido com token seguro de uso único e resgatável no perfil do desktop ou Android.
- Painel de moderadores com geração, cópia, revogação e histórico dos tokens, incluindo quem resgatou e quando.
- Mensagens de atualização nos dois apps, com título, versão, changelog, data e botão **Baixar**.
- Criação manual com Markdown e preview, ou importação de Releases oficiais existentes.
- Destino **GitHub** gerado automaticamente pela versão, ou **site oficial do Komicove**. Não há campo para inserir links personalizados.
- Verificação de atualizações nos repositórios `PANEL-ComicBookReader` e `Komicove`, com comparação de versões e deduplicação.
- Validação de permissões no backend, preservando contas, sessões, biblioteca, progresso e favoritos existentes.
- IA local de leitura guiada incluída nos três pacotes, preservando os recursos existentes do leitor.
- APK universal com ARM64, ARM de 32 bits, x86 e x86_64, mantendo o identificador e a assinatura para atualização.

As mensagens são publicadas dentro do Komicove. Importar uma Release ou escolher o destino Baixar não cria nem modifica Releases no GitHub.

Para disponibilizar os novos recursos, a API precisa executar esta versão e suas dependências de servidor. As duas tabelas novas são criadas automaticamente na inicialização, sem recriar o banco existente.
