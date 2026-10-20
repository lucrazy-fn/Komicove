# Validacao desktop da traducao - 2026-10-17

## Escopo

Validacao pratica no Windows com a interface normal do leitor, processamento local e inspecao visual de paginas originais e derivadas. Nenhum celular foi usado. Nao havia chave de API configurada, portanto provedores remotos foram cobertos apenas por testes automatizados com respostas simuladas.

## Obras e amostras

| HQ | Paginas | Direcao | Tempo | Regioes / incertas | Resultado |
| --- | ---: | --- | ---: | ---: | --- |
| Invincible 001 (2003) | 27 de 27 | ingles para portugues brasileiro | 755,08 s | 157 / 32 | 27 concluidas, 0 falhas |
| Ben 10 #1 (2026) | 31 de 31 | portugues brasileiro para ingles | 2.666,38 s | 475 / 100 | 31 concluidas, 0 falhas; falsos textos em capa e anuncios |
| Homem-Aranha Azul 01 | 25 de 25 | portugues brasileiro para ingles | 588,80 s | 70 / 38 | 25 concluidas, 0 falhas; muitos dialogos nao detectados |
| Mail v01 | 50 de 190, inicio, meio e fim | ingles para portugues brasileiro | 3.036,66 s | 199 / 102 | 50 concluidas, 0 falhas; manga e lettering irregular |
| Shura Yukihime Gaiden | 50 de 185, inicio, meio e fim | ingles para portugues brasileiro | 2.823,77 s | 150 / 55 | 50 concluidas, 0 falhas; preto e branco, paginas mudas e texto vertical japones |

Total: 183 paginas processadas, 1.051 regioes detectadas, 1.014 candidatas traduzidas e 327 regioes incertas. As evidencias visuais permanecem somente na pasta temporaria local e nao fazem parte do repositorio.

## Casos repetidos depois das correcoes

- Mail pagina 7: a caixa que atravessava dois baloes passou a permanecer original para revisao.
- Mail pagina 96: quatro regioes traduzidas, sem marcador sobre a arte e sem deslocamento visivel.
- Homem-Aranha Azul pagina 13: deteccao subiu de uma para cinco regioes ao aceitar papel acinzentado e combinar OCR portugues e ingles. Ainda ficaram dialogos ausentes.
- Barra da leitura guiada em 800 x 600: os seis controles passaram a ocupar tres linhas e o teste isolado passou.

## Metricas operacionais

- Tempo total medido das cinco amostras: 9.870,69 s.
- Media global: 53,94 s por pagina.
- Paginas sem regioes: Invincible 2, Ben 10 0, Homem-Aranha Azul 5, Mail 10, Shura 20. Parte delas e realmente muda; outras representam falha de deteccao.
- Segunda passagem: Invincible 27/27, Ben 10 31/31 e Homem-Aranha Azul 25/25 reutilizadas sem reprocessamento.
- Cancelamento durante OCR: 0,416 s ate encerrar a operacao.
- Pico aproximado do processo filho de OCR: 142,5 MiB.
- Chamadas reais de API: 0.
- Falhas por pagina: 0. Timeouts e travamentos: 0.

## Problemas e correcoes

- Arte era confundida com texto. Fragmentos incoerentes agora sao removidos e regioes de baixa confianca ficam para revisao.
- Uma linha longa podia unir baloes. Caixas excessivamente largas e longas agora sao classificadas como incertas.
- Baloes em papel envelhecido nao eram propostos porque o limiar exigia branco quase puro. O detector agora aceita cinza claro de baixa cromaticidade.
- OCR portugues isolado perdeu lettering latino estilizado. Quando ambos estao instalados, o passe usa `por+eng`.
- Marcadores de revisao eram desenhados sobre capas, efeitos e arte. A pagina agora permanece intacta; a pendencia aparece na lista de revisao.
- Falha de encaixe podia limpar o original antes de descobrir que a traducao nao cabia. O encaixe agora e validado antes da limpeza.
- O empacotamento nao confirmava dependencias de traducao local. O build agora verifica o conjunto `translation`.
- A barra guiada excedia a janela em 800 x 600. O layout compacto foi reorganizado.

## Limitacoes comprovadas

- O OCR local ainda perde baloes e legendas em scans granulados, fontes desenhadas, verticais, curvas e texto sobre arte.
- O tradutor Argos recebe cada regiao separadamente. Ele nao resolve de forma confiavel pronomes, piadas, voz e continuidade entre paginas.
- Algumas traducoes sao literais, incorretas ou misturam trechos de OCR corrompido.
- A reconstrucao e segura em fundo uniforme. Fundo complexo permanece original para revisao, sem inpainting avancado.
- Nao ha classificacao robusta de dialogo, narracao e efeito sonoro, nem escolha automatica de familias tipograficas por classe.
- As cinco combinacoes de idioma solicitadas nao puderam ser executadas. O catalogo Argos desta instalacao nao oferece espanhol, frances ou japones para portugues, e nao havia chave de API.
- API real, Webtoon real, pouco espaco em disco e retomada apos encerramento forcado nao foram aprovados.
- Android e Linux nao foram executados nesta rodada.

## Continuacao de 2026-10-18

### Conjunto de referencia

Foi criado um manifesto local, mantido fora do Git, com 31 regioes revisadas em cinco paginas dificeis: Homem-Aranha Azul 01 pagina 13, Mail v01 pagina 7, Ben 10 #1 pagina 16, capa japonesa de Shura Yukihime Gaiden e uma pagina muda da mesma obra. O avaliador reproduzivel esta em `tools/evaluate_translation_reference.py`.

| Medida | Antes | Depois |
| --- | ---: | ---: |
| Regioes localizadas | 10 de 31 (32,3%) | 28 de 31 (90,3%) |
| Falsos positivos considerados confiaveis | 12 | 0 |
| Homem-Aranha Azul 01 pagina 13 | 6 regioes uteis, com baloes unidos | 9 de 9 regioes localizadas, sem uniao |
| Mail v01 pagina 7 | baloes podiam ser unidos | 11 de 11 regioes localizadas, sem falso positivo |
| Ben 10 #1 pagina 16 | bloco superior unido | 8 de 9 regioes localizadas; `EI!` estilizado ainda ausente |
| Pagina muda de Shura | arte reconhecida como texto | nenhum texto retornado |

A meta de 95% nao foi atingida. O OCR ainda erra parte do conteudo reconhecido, portanto localizacao nao significa aprovacao semantica.

### Comparacao de mecanismos

- Tesseract com passes esparsos, recortes de baloes, escala, contraste, PSM alternativos e segunda leitura em cinza permaneceu como mecanismo distribuido. A saida TSV deixou de depender do arquivo opcional `configs/tsv`, permitindo modelos gerenciados contendo apenas `traineddata`.
- EasyOCR 1.7.2 com CRAFT foi testado somente no ambiente descartavel. Em paginas reais produziu 25 candidatos na pagina 13 de Homem-Aranha Azul, 62 em Mail 7, 18 em Ben 10 pagina 16 e 6 na capa de Shura, com predominio de arte, numeros e fragmentos. Os modelos e bibliotecas acrescentariam mais de 130 MiB. Nao foi integrado.
- Manga OCR teve a instalacao comparativa interrompida porque a resolucao das dependencias nao terminou em tempo razoavel. Nenhuma dependencia do produto foi alterada.
- `jpn` e `jpn_vert` oficiais do Tesseract foram avaliados na capa de Shura. Os dois produziram fragmentos incorretos e nao reconheceram o titulo vertical. O caso permanece para revisao e nao e aprovado automaticamente.

### Traducoes locais

O catalogo Argos disponivel foi reavaliado. O Komicove agora aceita internamente uma rota de ate dois pacotes quando nao ha par direto. Foram executados com sucesso: ingles para portugues brasileiro, portugues brasileiro para ingles, espanhol para portugues brasileiro, frances para portugues brasileiro e japones para portugues brasileiro. Os tres ultimos usaram ingles como idioma intermediario. A frase japonesa curta perdeu informacao na rota indireta, confirmando que disponibilidade tecnica nao equivale a qualidade contextual aprovada.

O modelo ONNX da leitura guiada detecta quadros e nao possui capacidade de OCR ou traducao. Nao foi usado de forma enganosa como tradutor. Argos continua offline e basico, sem contexto narrativo suficiente. Traducao contextual local exige um modelo de linguagem adicional compativel e ainda nao esta atendida.

### Reconstrucao

A limpeza de baloes uniformes passou a remover componentes das letras com mascara dilatada e cor amostrada, sem preencher toda a caixa do OCR. Regioes complexas ou incertas continuam preservadas para revisao. Nao foi incluido inpainting neural e nenhuma pagina com fundo complexo foi declarada completamente correta.

### Validacao restante

Nenhuma pagina do conjunto dificil atende simultaneamente OCR correto, traducao contextual correta, reconstrucao aprovada e equivalencia tipografica. API real segue pendente por ausencia de chave. Android e Linux nao foram usados nesta continuacao.

### Testes desta continuacao

- Avaliador do conjunto de referencia: 28 de 31 regioes, 90,3% de localizacao e 0 falsos positivos confiaveis em 224,41 s.
- Pagina 13 de Homem-Aranha Azul apos calibracao: 9 regioes, 4 enviadas obrigatoriamente para revisao e 5 consideradas confiaveis pelo OCR. Ainda ha erros lexicos nas cinco e a pagina nao foi aprovada.
- Testes de traducao: 59 aprovados sem o teste de credencial.
- Cofre de Credenciais do Windows: 1 aprovado fora do sandbox com chave ficticia removida ao final.
- Regressao de traducao, leitor e leitura guiada: 166 testes aprovados.
- A suite integral de 357 testes ficou presa no primeiro teste de seguranca de conta no ambiente desta execucao e foi interrompida. A suite integral anterior a esta continuacao tinha 351 aprovados; o travamento atual nao foi apresentado como aprovacao.
- Build PyInstaller Windows concluido. `--check-assets` terminou com codigo 0. A abertura visual do executavel nao foi observavel pelo controlador de janelas desta execucao, portanto a validacao visual do binario permanece pendente.

## Otimizacao e fila de HQ inteira em 2026-10-19

### Gargalo medido e solucao

O perfil mostrou que mais de 96% do tempo de uma pagina dificil era gasto em processos repetidos do Tesseract. A pagina 13 de Homem-Aranha iniciou 80 processos; a pagina muda de Shura iniciou 172. Paralelizar processos piorou o tempo por disputa de CPU, e reduzir tentativas perdeu uma regiao do conjunto de referencia. Essas alternativas foram descartadas.

Os recortes que usam a mesma configuracao passaram a ser enviados como paginas independentes de um TIFF em memoria. O Tesseract continua separando cada recorte por `page_num`; as cinco estrategias adicionais continuam limitadas as regioes incertas. Na pagina 13, os processos cairam de 80 para 38 e o pico observado do processo filho caiu de 142,5 MiB para 83,8 MiB.

| Medida | Antes | Depois |
| --- | ---: | ---: |
| Media historica das 183 paginas | 53,94 s/pagina | 25,81 s/pagina nas 3 paginas dificeis latinas |
| Mesmas 3 paginas latinas | 117,51 s | 77,42 s |
| Homem-Aranha Azul 01 pagina 13 | 33,34 s | 25,52 s |
| Mail v01 pagina 7 | 45,48 s | 29,17 s |
| Ben 10 #1 pagina 16 | 38,69 s | 22,73 s |
| Cache OCR, mediana | nao medido | 93,4 ms |
| Cache final, mediana | nao medido | 115 ms no modo local |

A queda contra a media historica foi de 52,1%. A comparacao estrita das mesmas tres paginas foi de 34,1%, portanto a meta de 50% no mesmo conjunto permanece como excecao comprovada. O resultado de qualidade permaneceu em 28 de 31 regioes e zero falso positivo confiavel. Os modelos japoneses `jpn` e `jpn_vert` nao estavam instalados nesta rodada final; as paginas japonesas foram excluidas da comparacao de velocidade e continuam pendentes.

### HQ inteira, estimativa e retomada

- A tela possui a acao real `Traduzir HQ inteira`, com uma confirmacao unica contendo obra, total, concluidas, pendentes, idiomas, modo, intervalo inicial e aviso de possivel custo de API.
- A fila prioriza a pagina aberta, continua depois de erro recuperavel, registra paginas concluidas e erros, e nao repete OCR ou traducao encontrada nos caches separados.
- Progresso mostra pagina, total, estado, percentual, tempo decorrido, segundos por pagina e tempo restante. A estimativa usa mediana e media recente, ignora cache e so mostra tempo restante depois de duas amostras.
- Pausa ocorre entre paginas; cancelamento encerra o subprocesso ativo e preserva paginas concluidas. O trabalho persistido reaparece como `Continuar traducao` apos reabrir.
- A assinatura de retomada inclui obra, idiomas, provedor, modelo, endereco, OCR, visao, glossario, modo manga e rotacao. Mudancas incompativeis nao reutilizam silenciosamente o estado antigo.

### Regressao e build

- 363 testes da suite completa aprovados. O travamento anterior foi isolado ao canal interno do loop assincrono bloqueado pelo sandbox; fora desse isolamento, o teste de seguranca concluiu em 2,32 s sem alteracao funcional.
- O unico defeito observado na primeira execucao completa foi uma corrida visual ao entrar em tela cheia no modo Webtoon. A barra agora e ocultada no mesmo ciclo e o caso passou isoladamente e na suite completa.
- Build PyInstaller Windows concluido e `Komicove.exe --check-assets` retornou codigo 0.
- A tentativa de abrir a janela do executavel pelo controlador visual expirou aguardando aprovacao do ambiente. A interface do binario nao foi declarada visualmente aprovada nesta rodada.
