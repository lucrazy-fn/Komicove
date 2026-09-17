<p align="center"><img src="panellogo.png" width="160" alt="Logo PANEL"></p>

# PANEL · Comic Book Reader

Leitor de quadrinhos gratuito e de código aberto para Windows e Android. Organize sua coleção, acompanhe seu progresso e leia seus arquivos locais sem conta ou internet.

**Windows 1.6.0 · Android 1.5.0 · Licença MIT**

[Site](https://lucrazy-fn.github.io/PANEL-ComicBookReader/) · [Downloads](https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases) · [Issues](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues)

> Projeto em desenvolvimento. Os recursos descritos correspondem ao código atual; versões antigas podem não incluí-los.

## Para começar

- **Windows 10/11:** baixe o instalador na página de Releases. Não precisa instalar Python para usar o aplicativo.
- **Android 8 ou superior:** baixe o APK na mesma página.

No Windows, entre no modo convidado e selecione a pasta dos seus quadrinhos. No Android, importe os arquivos pelo seletor do dispositivo. Escolha uma HQ na biblioteca para começar.

## Recursos

- Biblioteca com capas, busca, favoritos e progresso salvo.
- Coleções para organizar seu acervo.
- Leitor com zoom, marcadores, página dupla, modo mangá e leitura vertical.
- Preferências de persistência do zoom e encaixe automático.
- Leitura guiada experimental no Windows e no Android.
- Botões de navegação e retorno à biblioteca com área de clique ampliada.

### Leitura guiada experimental

Ative em **Preferências do leitor**. As setas percorrem os quadros detectados. No Windows, pressione **L** para ativar ou desativar o recurso.

Quando a detecção não reconhece as divisões da página, o leitor usa trechos aproximados com sobreposição, identificados como **Trecho**. Páginas com quadros diagonais, sobrepostos ou bordas coloridas podem não ser reconhecidas corretamente.

## Formatos

| Formato | Windows | Android |
| --- | --- | --- |
| CBZ / ZIP | Suporte incluído | Suporte incluído |
| PDF | Suporte incluído | Suporte incluído |
| CBR / RAR | 7-Zip ou ferramenta compatível | Conforme a compatibilidade da biblioteca Junrar |
| 7Z / CB7 / TAR / CBT | Requer 7-Zip instalado separadamente | Suporte incluído |

Arquivos compactados devem conter páginas de imagem. Arquivos com senha não são suportados; RAR5 pode não abrir no Android.

## Colaborar com o PANEL

Sugestões, relatos de bugs, melhorias de acessibilidade, traduções e contribuições de código são bem-vindos.

1. Confira as Issues existentes antes de abrir uma nova.
2. Para mudanças maiores, descreva a proposta em uma Issue antes de implementar.
3. Crie um fork e uma branch para sua alteração.
4. Faça uma mudança focada e teste o comportamento afetado.
5. Abra um pull request explicando o problema, a solução e como você testou. Para alterações visuais, inclua capturas de tela.

## Encontrou um problema?

Abra uma [Issue](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues) com a versão do PANEL, seu sistema operacional, os passos para reproduzir e o resultado esperado. Se possível, inclua a mensagem de erro ou uma captura de tela.

Para falhas na leitura guiada, informe a página e se o contador mostrava **Quadro** ou **Trecho**. Não compartilhe senhas, tokens ou arquivos de quadrinhos sem autorização.

## Licença

O PANEL usa a [licença MIT](LICENSE). As dependências mantêm suas próprias licenças.
