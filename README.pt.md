<p align="center">
  <img src="komicovelogo.png" width="300" alt="Komicove">
</p>

# Komicove · Comic Book Reader

**Português** · [English](README.md)

Leitor de quadrinhos gratuito e de código aberto para Windows, Linux e Android. Organize sua coleção, acompanhe seu progresso e leia seus arquivos locais sem conta ou internet.

**Windows 0.2.1.1 · Android 0.2.1.1 · Linux 0.2.1.1 · Licença MIT**

[Site](https://lucrazy-fn.github.io/PANEL-ComicBookReader/) · [Downloads](https://github.com/lucrazy-fn/PANEL-ComicBookReader/releases) · [Issues](https://github.com/lucrazy-fn/PANEL-ComicBookReader/issues)

> Projeto em desenvolvimento. Os recursos descritos correspondem ao código atual; versões antigas podem não incluí-los.

## Versão mais recente: 0.2.1.1

Esta revisão melhora o controle de brilho durante a leitura no Windows, Linux e Android.

### Novidades

- Escolha **Usar brilho das preferências** para aplicar o nível configurado no Komicove.
- Escolha **Usar brilho do sistema** para respeitar a configuração do dispositivo ou sistema operacional.
- O modo selecionado e o nível manual de brilho são salvos e restaurados ao abrir o aplicativo.
- O controle manual fica claramente desativado enquanto o brilho do sistema está selecionado.
- A troca do modo de brilho preserva todas as outras preferências do leitor.
- No Android, cancelar a prévia das preferências restaura a configuração de brilho salva.
- O atualizador agora reconhece versões com quatro números, como `0.2.1.1`.

A versão 0.2.1.1 está disponível como instalador e pacote portátil para Windows, pacotes `tar.gz` e Flatpak para Linux e APK universal para Android.

## Conheça a interface

Estas são apenas algumas imagens do Komicove. O aplicativo possui outras telas e recursos além dos mostrados aqui.

### Desktop

Biblioteca com busca, filtros, progresso e acesso às suas próximas leituras.

<p align="center">
  <img src="docs/screenshots/desktop-biblioteca.png" width="1100" alt="Biblioteca do Komicove no desktop, com capas, filtros e a seção Continuar lendo">
</p>

<details>
<summary>Ver o leitor e as pastas monitoradas no desktop</summary>

#### Leitor

<img src="docs/screenshots/desktop-leitor.png" width="1100" alt="Leitor desktop com uma HQ aberta, barra superior e controles inferiores">

#### Pastas monitoradas

<img src="docs/screenshots/desktop-pastas.png" width="1100" alt="Pastas monitoradas no desktop, com contadores, status, atualização e opção de desativar">

</details>

### Android

Biblioteca, leitor e gerenciamento de pastas na interface nativa mobile.

<table>
  <tr><th>Biblioteca</th><th>Leitor</th><th>Pastas monitoradas</th></tr>
  <tr>
    <td><img src="docs/screenshots/android-biblioteca.jpg" width="240" alt="Biblioteca Android com filtros, capas, progresso e navegação inferior"></td>
    <td><img src="docs/screenshots/android-leitor.jpg" width="240" alt="Leitor Android com uma página aberta, progresso e controles de leitura"></td>
    <td><img src="docs/screenshots/android-pastas.jpg" width="240" alt="Pastas monitoradas Android com botão de adicionar, atualização e controle de ativação"></td>
  </tr>
</table>

As capturas mostram o aplicativo em uso. As HQs exibidas pertencem aos respectivos titulares e não acompanham o Komicove.

## 📢 PANEL agora é Komicove

**Desde a versão 0.1.0, o PANEL se chama Komicove.**

Quando comecei o projeto, escolhi o nome **PANEL** sem saber que já existia outro leitor de quadrinhos com um nome muito parecido. Eu não conhecia esse aplicativo antes de criar e publicar o PANEL.

Agora que descobri essa semelhança e o projeto está crescendo, decidi mudar o nome para dar a ele uma identidade mais própria e evitar possíveis confusões no futuro.

Komicove continua sendo o mesmo projeto open-source, com o mesmo desenvolvimento e objetivos. Os dados e contas existentes continuam acessíveis; as versões anteriores permanecem disponíveis com o nome PANEL.

Obrigado a todo mundo que vem acompanhando, testando e apoiando o projeto até agora! ❤️

**PANEL → Komicove**

## Para começar

- **Windows 10/11:** baixe o instalador na página de Releases. Não precisa instalar Python para usar o aplicativo.
- **Linux x86_64:** há pacotes portátil (`.tar.gz`) e Flatpak experimental. Confira a disponibilidade na página de Releases. A compatibilidade pode variar entre distribuições.
- **Android 8 ou superior:** baixe o APK na mesma página.

Também testado no **Debian 13**, em ambiente WSL2. O pacote portátil Linux desta atualização foi compilado com glibc 2.41; a compatibilidade com distribuições mais antigas pode variar.

Faça um backup antes de atualizar. No Android, o APK precisa ter uma assinatura compatível com a instalação existente; não desinstale o aplicativo para contornar incompatibilidades sem antes proteger seus dados.

No Windows, entre no modo convidado e selecione a pasta dos seus quadrinhos. No Android, adicione arquivos ou uma pasta pelo seletor do dispositivo. Os arquivos da pasta ficam no local original; o app usa uma cópia temporária enquanto a HQ está aberta. As HQs já importadas em versões anteriores continuam na biblioteca.

Na primeira abertura da nova versão para desktop, os dados locais da antiga pasta `Panel` são copiados para `Komicove`. A pasta antiga permanece como cópia de segurança e não é apagada automaticamente.

## Recursos

- Biblioteca com capas, busca, favoritos, progresso salvo e ordem alfanumérica no Android.
- Coleções para organizar seu acervo, com seleção de várias HQs no Android.
- Leitor com zoom, marcadores, página dupla, modo mangá e leitura vertical.
- Preferências de modo de brilho, persistência do zoom e encaixe automático.
- Leitura guiada experimental no Windows e no Android.
- Botões de navegação e retorno à biblioteca com área de clique ampliada.
- Pastas monitoradas com atualização manual e opção de ativar ou desativar.

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
