<p align="center">
  <img src="transition.png" width="850" alt="PANEL está se tornando Komicove">
</p>

# Komicove · Comic Book Reader

Leitor de quadrinhos gratuito e de código aberto para Windows, Linux e Android. Organize sua coleção, acompanhe seu progresso e leia seus arquivos locais sem conta ou internet.

**Windows 0.1.0 · Android 0.1.0 · Linux em preparação · Licença MIT**

[Site](https://lucrazy-fn.github.io/PANEL-ComicBookReader/) · [Downloads](https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases) · [Issues](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues)

> Projeto em desenvolvimento. Os recursos descritos correspondem ao código atual; versões antigas podem não incluí-los.

## 📢 PANEL agora é Komicove

**A partir da versão 0.1.0, o PANEL passa a se chamar Komicove.**

Quando comecei o projeto, escolhi o nome **PANEL** sem saber que já existia outro leitor de quadrinhos com um nome muito parecido. Eu não conhecia esse aplicativo antes de criar e publicar o PANEL.

Agora que descobri essa semelhança e o projeto está crescendo, decidi mudar o nome para dar a ele uma identidade mais própria e evitar possíveis confusões no futuro.

Komicove continua sendo o mesmo projeto open-source, com o mesmo desenvolvimento e objetivos. Os dados e contas existentes continuam acessíveis; as versões anteriores permanecem disponíveis com o nome PANEL.

Obrigado a todo mundo que vem acompanhando, testando e apoiando o projeto até agora! ❤️

**PANEL → Komicove**

## Para começar

- **Windows 10/11:** baixe o instalador na página de Releases. Não precisa instalar Python para usar o aplicativo.
- **Linux x86_64:** o código desktop é compartilhado com Windows, mas o pacote Komicove 0.1.0 para Linux ainda precisa ser gerado e validado.
- **Android 8 ou superior:** baixe o APK na mesma página.

No Windows, entre no modo convidado e selecione a pasta dos seus quadrinhos. No Android, adicione arquivos ou uma pasta pelo seletor do dispositivo. Os arquivos da pasta ficam no local original; o app usa uma cópia temporária enquanto a HQ está aberta. As HQs já importadas em versões anteriores continuam na biblioteca.

## Recursos

- Biblioteca com capas, busca, favoritos, progresso salvo e ordem alfanumérica no Android.
- Coleções para organizar seu acervo, com seleção de várias HQs no Android.
- Leitor com zoom, marcadores, página dupla, modo mangá e leitura vertical.
- Preferências de persistência do zoom e encaixe automático.
- Leitura guiada experimental no Windows e no Android.
- Botões de navegação e retorno à biblioteca com área de clique ampliada.

### Leitura guiada experimental

Ative em **Preferências do leitor**. As setas percorrem os quadros detectados. No Windows, pressione **L** para ativar ou desativar o recurso.

Quando a detecção não reconhece as divisões da página, o leitor usa trechos aproximados com sobreposição, identificados como **Trecho**. Páginas com quadros diagonais, sobrepostos ou bordas coloridas podem não ser reconhecidas corretamente.

## Formatos

| Formato | Windows/Linux | Android |
| --- | --- | --- |
| CBZ / ZIP | Suporte incluído | Suporte incluído |
| EPUB de imagens | Suporte experimental | Suporte experimental |
| PDF | Suporte incluído | Suporte incluído |
| CBR / RAR | 7-Zip ou ferramenta compatível | Suporte incluído |
| 7Z / CB7 / TAR / CBT | Requer 7-Zip instalado separadamente | Suporte incluído |

Arquivos compactados devem conter páginas de imagem, inclusive dentro de pastas. O Android inclui suporte a RAR5. Arquivos com senha não são suportados.

## Colaborar com o Komicove

Sugestões, relatos de bugs, melhorias de acessibilidade, traduções e contribuições de código são bem-vindos.

1. Confira as Issues existentes antes de abrir uma nova.
2. Para mudanças maiores, descreva a proposta em uma Issue antes de implementar.
3. Crie um fork e uma branch para sua alteração.
4. Faça uma mudança focada e teste o comportamento afetado.
5. Abra um pull request explicando o problema, a solução e como você testou. Para alterações visuais, inclua capturas de tela.

## Encontrou um problema?

Abra uma [Issue](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues) com a versão do Komicove, seu sistema operacional, os passos para reproduzir e o resultado esperado. Se possível, inclua a mensagem de erro ou uma captura de tela.

Para falhas na leitura guiada, informe a página e se o contador mostrava **Quadro** ou **Trecho**. Não compartilhe senhas, tokens ou arquivos de quadrinhos sem autorização.

## Licença

O Komicove usa a [licença MIT](LICENSE). As dependências mantêm suas próprias licenças.
