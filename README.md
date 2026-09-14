<p align="center"><img src="panellogo.png" width="160" alt="Logo PANEL"></p>

# PANEL · Comic Book Reader

Sua biblioteca de quadrinhos, do seu jeito. Leitor para Windows com capas, coleções, progresso salvo e recursos de comunidade opcionais.

**1.4.1 · Windows 10/11 · Android 8+ · Python 3.10+ · MIT**

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
- **Com uma API disponível:** conta, perfil, notificações, sincronização, Descobrir, downloads, publicação e remoção dos próprios envios.
- **Equipe:** revisão de publicações, denúncias e painel administrativo em `/moderators`, conforme o cargo da conta.
- **Cargos por token:** o dono pode ativar sua conta com o token mestre no perfil; moderadores podem usar tokens limitados para se tornarem administradores.
- **Android 1.3.1:** leitor nativo para Android 8+, com biblioteca, coleções, progresso, favoritos, backup, formatos compactados e integração com a comunidade.

Publique somente conteúdo próprio ou que você tenha autorização para distribuir.

## Versão Android

O PANEL também possui uma edição mobile nativa em Java, com a mesma conta e API do desktop. A versão Android 1.3 inclui importação pelo seletor de arquivos, leitor com gestos e zoom, página dupla, modo mangá, leitura vertical, marcadores, backup e suporte a CBZ, ZIP, PDF, 7Z, CB7, TAR, CBT e CBR/RAR conforme a compatibilidade da biblioteca.

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

## Rodar pelo código

No PowerShell, dentro da pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[server,test]"
.\.venv\Scripts\python.exe -m panel_app
```

Também é possível usar `startapp.bat`. Use uma instalação do Python com Tkinter funcionando.

## Contas e servidor

 O leitor local funciona sem servidor. Login, sincronização e comunidade exigem a API; o instalador desktop **não inclui nem inicia o backend**.

Para desenvolvimento, execute em outro terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn panel_backend.api.app:app --host 127.0.0.1 --port 8000
```

A entrada pelo código também tenta iniciar uma API local automaticamente quando necessário. Para conectar a outra API, configure antes de iniciar o app:

```powershell
$env:PANEL_API_BASE_URL = "https://seu-servidor.example"
```

Esse endereço é apenas um exemplo, não um servidor público do PANEL. Sem API configurada, use o modo convidado. Um servidor local em cada computador não cria uma comunidade compartilhada.

Consulte `.env.example` e `startserver.bat` para a configuração de desenvolvimento. Nunca distribua `.env`, tokens, `panel.db` ou a pasta `panel_storage`. Não exponha o servidor de desenvolvimento diretamente à internet.

## Gerar executável e instalador

Ferramentas: Python com Tkinter, PyInstaller e **Inno Setup 6**. Compile no Windows usando a arquitetura que deseja distribuir.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

O script procura o compilador `ISCC.exe` no PATH e na pasta padrão do Inno Setup 6. Se não o encontrar, o executável permanece disponível, mas o instalador não será gerado.

Saídas:

- `dist\PANEL\PANEL.exe`: leitor empacotado. Para distribuir sem instalador, envie **toda a pasta PANEL**, não apenas o EXE.
- `dist\installer\PANEL-Setup-1.4.1.exe`: instalador, quando o Inno Setup estiver disponível.

Para gerar somente o executável:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1 -ExecutableOnly
```

O pacote inclui apenas recursos explicitamente selecionados e dependências do leitor, sem os dados locais do servidor. O executável não tem assinatura digital configurada; o Windows pode mostrar um aviso de reputação.

### Antes de publicar uma release

1. Execute os testes: `.\.venv\Scripts\python.exe -m pytest`.
2. Gere o instalador e teste instalação, abertura, capas, PDF, 7-Zip e desinstalação em um Windows sem Python.
3. Verifique o modo convidado e, separadamente, a conexão com a API.
4. Atualize as versões em `pyproject.toml`, `installer/Panel.iss` e no nome de saída do script.
5. Crie uma release no GitHub e anexe o instalador. Não envie banco, uploads ou segredos.

O script não publica nada automaticamente e não implementa atualização automática.

## Estrutura

```text
panel_app/       Interface, leitor, biblioteca e dados locais
panel_client/    Cliente HTTP para a API
panel_backend/   Contas, catálogo, moderação e API
installer/       Entrada de empacotamento, PyInstaller e Inno Setup
tests/           Testes automatizados
Icons/           Recursos visuais
```

`python -m panel_app` é a entrada principal. `ComicReader.py` mantém compatibilidade com a organização antiga.

## Problemas comuns

- **Login sem conexão:** confira a API e `PANEL_API_BASE_URL`; leitura local continua disponível como convidado.
- **CBR/7Z não abre:** confira a instalação do 7-Zip, a integridade do arquivo e se ele possui senha.
- **Capas ou ícones ausentes no pacote:** mantenha a pasta gerada inteira; não mova somente o EXE.
- **Erro de Tkinter ao compilar:** verifique o Python usado para criar a `.venv` antes de gerar o pacote.

Ao abrir uma issue, informe versão, mensagem de erro e passos para reproduzir. Não anexe senhas, tokens ou obras sem autorização.

## Licença

O código do PANEL usa a [licença MIT](LICENSE). Dependências e ferramentas externas mantêm suas próprias licenças; revise suas condições antes de redistribuir o pacote.
