# Android 0.2.0 — distribuição e preparação para Google Play

## Build

- Nome: Komicove; applicationId: `com.lucrazy.panel`.
- versionName: `0.2.0`; versionCode: `10720` (preservados).
- compileSdk/targetSdk: 36; minSdk: 26; AGP: 8.10.1; Gradle: 8.11.1; Java: 17.
- Debug padrão também se chama Komicove. Sufixos/nomes de testes são somente
  opt-in via `readerBenchmark`/`phase2Test`; não entram no release.
- APK é para instalação direta; AAB é para envio ao Play Console, não para
  instalação direta no aparelho.

A assinatura release usa exclusivamente as variáveis de ambiente
`KOMICOVE_KEYSTORE`, `KOMICOVE_STORE_PASSWORD`, `KOMICOVE_KEY_ALIAS` e
`KOMICOVE_KEY_PASSWORD`. Não inserir senha, chave ou arquivo privado no Git.
Informar todas as quatro, ou nenhuma; configuração incompleta falha antes do
build. Sem essas variáveis, o release fica **sem assinatura** e não deve ser
distribuído como se estivesse instalável. Builds assinados executam:

```
gradle :app:testDebugUnitTest :app:lintVitalRelease :app:assembleRelease :app:bundleRelease --no-daemon --no-configuration-cache
```

Guardar a chave permanente fora do repositório, com backup privado. Não gerar
outra chave para atualizar uma instalação existente. Conferir certificados
SHA-256 do APK instalado e do novo APK antes de atualizar; nunca desinstalar ou
limpar dados para contornar uma divergência de assinatura.

Verificações do artefato:

- `apksigner verify --print-certs`: assinatura APK;
- `jarsigner -verify`: assinatura AAB (certificado autoassinado é normal);
- `aapt dump badging`: pacote, versão, SDK, nome e ausência de debuggable;
- `python tools/verify_android_native.py arquivo.apk arquivo.aab`: integridade
  ZIP, alinhamento ELF de bibliotecas 64-bit e alinhamento ZIP do APK a 16 KiB;
- checksum SHA-256 local e no celular após transferência.

Os testes gráficos do detector continuam explicitamente no Android 15/API 35
(baseline anterior): Robolectric 4.14.1 não suporta execução API 36. Os demais
testes possuem SDK explícito. Compilar com target 36 não equivale a testar a
execução em Android 16; aceitação em Android 16 e dispositivo 16 KiB permanece
necessária antes de afirmar compatibilidade de runtime nessas configurações.

## Resultado desta execução (02/10/2026)

- APK e AAB release assinados com a chave permanente indicada: build e
  lintVitalRelease passaram; ambos possuem bibliotecas 64-bit alinhadas a 16 KiB.
- Android: 50 testes passaram; 2 opcionais ignorados por ausência de fixtures.
  O teste do detector inicialmente tentou usar API 36 por herdar o novo target;
  corrigida a seleção do SDK para manter o baseline API 35, sem remover testes.
- Python: suíte completa 91 passou; repetição das regressões de pastas/interface
  19 passou. PyInstaller Windows e Inno Setup 0.2.0 compilaram.
- APK/AAB copiados para `/sdcard/Download/Komicove-0.2.0/`; SHA-256 local e
  no aparelho idênticos. Nenhuma instalação pessoal foi limpa/desinstalada.
- A instalação existente tem certificado diferente da nova chave permanente.
  Foi encontrada a antiga chave de testes local com certificado correspondente;
  por autorização do usuário, foi gerado `Komicove-0.2.0-compativel.apk` a partir
  do mesmo release (DEBUG=false), para atualização direta com a assinatura antiga.
  Este APK **não é o artefato destinado à Play Store**; o AAB mantém a chave
  permanente. Certificado do APK compatível e alinhamento foram verificados.
- Não foi executada instalação limpa/atualização do release pessoal nesta
  execução: apenas geração, verificações e transferência. Testes USB da Fase 2
  anteriores utilizaram pacote isolado; ver pendências em `PHASE2_FOLDERS.md`.
- O usuário instalou Debian 13 no WSL2 sem remover o Ubuntu antigo. A suíte
  Linux passou: 91 testes, com um aviso de dependência; PyInstaller compilou
  e o binário confirmou `Komicove assets OK`. A interface foi aberta com
  dados isolados no WSLg e aprovada pelo usuário.
- Gerados `Komicove-Linux-0.2.0-x86_64.tar.gz` e
  `Komicove-Linux-0.2.0-x86_64.flatpak` na pasta de entrega. O Flatpak foi
  exportado, instalado no Debian e abriu; imports, Tk 9.0.2, versão e assets
  foram verificados dentro do sandbox. A limpeza de cache do flatpak-builder
  retornou `fchmod: Operation not permitted` após exportar os commits; o bundle
  foi finalizado separadamente a partir desse repositório exportado.
- O portátil foi compilado em Debian 13/glibc 2.41: não afirmar suporte a
  distribuições com glibc anterior sem teste. O Flatpak usa o runtime
  org.freedesktop.Sdk 25.08. Teste WSL2 não equivale a teste em Debian nativo.
- SHA-256 tar.gz: `40cc759e387daeaf33afae47108cca860cc366db07c2b02d49610ac573428262`.
- SHA-256 Flatpak: `94d0dffa313df1d4893b239a39f3b2c2a4389763fd8421fba5282a0ec81614df`.
- Nenhum pagamento ou publicação na Play Store foi realizado. O commit/push
  posterior de menção ao Debian incluiu somente `docs/index.html`; as alterações
  funcionais locais não foram enviadas junto com essa atualização do site.

## Google Play: pendências antes de publicar

Este build não equivale a aprovação da loja. Nenhuma publicação, conta ou
pagamento foi realizado. O usuário ainda não possui conta Play Console e
optou por adiar o custo; pode instalar/distribuir o APK por link enquanto isso.

1. Criar/verificar conta de desenvolvedor quando possível. A taxa é US$25,
   paga uma vez. Conta pessoal nova exige verificação e teste fechado com pelo
   menos 12 participantes inscritos continuamente por 14 dias antes de pedir
   acesso à produção.
2. Criar o app, configurar Play App Signing e enviar o AAB inicialmente para
   teste interno; revisar impacto da chave da Play Store nas instalações APK
   existentes antes de escolher a chave de assinatura.
3. Publicar política de privacidade acessível e preencher Segurança dos dados
   com base nos fluxos reais de conta, perfil, sincronização e comunidade.
   Não declarar "nenhum dado coletado" sem auditoria desses fluxos.
4. Como existe criação de conta, fornecer exclusão de conta/dados pelo app e
   recurso externo acessível por URL. A inspeção atual não encontrou um fluxo
   completo Android/backend de exclusão de conta; isso é uma pendência real,
   não foi adicionada uma funcionalidade grande fora da Fase 2.
5. Revisar comunidade/UGC: termos aceitos antes de envio, denúncia de conteúdo
   e usuários, bloqueio quando exigido e moderação efetiva. Há denúncia de obra
   e moderação, mas não foi identificado fluxo completo de termos/bloqueio.
   Auditar também direitos de distribuição dos arquivos enviados.
6. Preencher classificação indicativa, público-alvo, anúncios (conforme uso
   real), acesso do revisor às partes com login e contato de suporte. Preparar
   ícone, screenshots reais e imagem de destaque próprios, sem dados pessoais.
7. Executar aceitação do release em instalação limpa/atualização, Android 16,
   aparelho 16 KiB e relatório de pré-lançamento do Play Console.

Fontes oficiais verificadas em 02/10/2026:

- [API alvo exigida](https://developer.android.com/google/play/requirements/target-sdk)
- [Mudanças Android 16](https://developer.android.com/about/versions/16/behavior-changes-16)
- [AGP 8.10 e API 36](https://developer.android.com/build/releases/agp-8-10-0-release-notes)
- [Compatibilidade 16 KiB](https://developer.android.com/guide/practices/page-sizes)
- [App Bundles](https://developer.android.com/guide/app-bundle)
- [Cadastro Play Console](https://support.google.com/googleplay/android-developer/answer/6112435?hl=pt-BR)
- [Testes de contas pessoais novas](https://support.google.com/googleplay/android-developer/answer/14151465?hl=pt-BR)
- [Privacidade e dados](https://support.google.com/googleplay/android-developer/answer/10144311?hl=pt-BR)
- [Exclusão de conta](https://support.google.com/googleplay/android-developer/answer/13327111?hl=pt-BR)
- [Conteúdo gerado por usuários](https://support.google.com/googleplay/android-developer/answer/9876937?hl=pt-BR)
