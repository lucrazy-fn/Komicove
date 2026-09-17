<p align="center"><img src="panellogo.png" width="160" alt="Logo PANEL"></p>

# PANEL · Comic Book Reader

Sua biblioteca de quadrinhos, do seu jeito. Leitor para Windows com capas, coleções, progresso salvo e recursos de comunidade opcionais.

**1.5.0 · Windows 10/11 · Android 8+ · Python 3.10+ · MIT**

[Releases](https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases) · [Reportar problema](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues)

> Em desenvolvimento. Os recursos descritos aqui correspondem ao código desta versão; releases antigas podem não incluí-los.

## Comece por aqui

Se houver um instalador disponível em Releases, baixe e execute o arquivo de instalação. O pacote gerado por este projeto inclui Python e as bibliotecas do leitor: o usuário não precisa instalar Python.

1. Abra o PANEL e use o modo convidado para leitura local.
2. Clique em **Pasta** e escolha onde estão seus quadrinhos.
3. Abra uma capa para começar. O progresso fica salvo no computador.

O instalador cria um atalho no menu Iniciar e oferece um atalho opcional na área de trabalho. A instalação é por usuário, sem exigir administrador. Os dados em `%APPDATA%\Panel` são preservados na desinstalação.

## O que tem no app

- **Biblioteca:** capas, busca, favoritos, filtros e progresso de leitura.
- **Coleções:** organização por pastas e agrupamento de séries.
- **Leitor:** zoom, miniaturas, marcadores, tela cheia, página dupla, modo mangá e leitura vertical.
- **Personalização:** temas, traduções e animações de interação.
- **Backup:** exportação e restauração dos dados de leitura.
- **Android 1.4.0:** leitor nativo para Android 8+, com biblioteca, coleções, progresso, favoritos, backup, atualizações e diagnóstico seguro.

Publique somente conteúdo próprio ou que você tenha autorização para distribuir.

## Versão Android

O PANEL também possui uma edição mobile nativa em Java, com a mesma conta e API do desktop. A versão Android 1.3.2 inclui importação pelo seletor de arquivos, leitor com gestos e zoom, página dupla, modo mangá, leitura vertical, marcadores, backup e suporte a CBZ, ZIP, PDF, 7Z, CB7, TAR, CBT e CBR/RAR conforme a compatibilidade da biblioteca.

Para compilar, abra a pasta `android` no Android Studio usando JDK 17. O APK de teste é gerado em `android/app/build/outputs/apk/debug/app-debug.apk`. Consulte [`android/README.md`](android/README.md) para os requisitos e instruções completas.

## Formatos de leitura local

| Arquivos | Dependência |
| --- | --- |
| CBZ / ZIP | Suporte nativo |
| PDF | PyMuPDF, incluído no pacote do leitor |
| CBR / RAR | 7-Zip ou ferramenta compatível com rarfile, como UnRAR |
| 7Z / CB7 / TAR / CBT | 7-Zip instalado separadamente |

Os arquivos compactados precisam conter páginas de imagem. Arquivos protegidos por senha não são suportados nesta integração.

O app procura `7z`/`7zz` no PATH e o 7-Zip nas pastas padrão do Windows. Para uma instalação diferente, defina `PANEL_7ZIP_PATH` com o caminho completo de `7z.exe` antes de iniciar o app. O instalador do PANEL não redistribui o 7-Zip.

Os uploads da comunidade continuam limitados a CBZ, ZIP, CBR, RAR e PDF; suporte local não significa suporte para publicação.


## Contas e servidor

 O leitor local funciona sem servidor. Login somente se quiser utilizar a comunidade!

## Problemas comuns

- **Login sem conexão:** será corrigido na versão 1.6.
- **CBR/7Z não abre:** confira a instalação do 7-Zip, a integridade do arquivo e se ele possui senha.
- **Capas ou ícones ausentes no pacote:** mantenha a pasta gerada inteira; não mova somente o EXE.

Ao abrir uma issue, informe versão, mensagem de erro e passos para reproduzir. Não anexe senhas, tokens ou obras sem autorização.

## Licença

O código do PANEL usa a [licença MIT](LICENSE). Dependências e ferramentas externas mantêm suas próprias licenças; revise suas condições antes de redistribuir o pacote.
