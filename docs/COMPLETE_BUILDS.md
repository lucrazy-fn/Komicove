# Builds completos / Complete builds

PT-BR: O build desktop padrao inclui a IA local existente, seu runtime e o
modelo verificado em `local_models/inkwell.onnx`. Instale o extra `ai` antes
de compilar. Os pesos permanecem fora do Git; obtenha-os da origem e revisao
documentadas em `installer/inkwell/NOTICE.txt` (arquivo original `best.onnx`,
renomeado localmente para `inkwell.onnx`). O build recusa pesos ausentes
ou diferentes. `KOMICOVE_BUILD_WITH_AI=0` permite explicitamente um pacote
sem IA; nao e o pacote completo. `--check-ai` verifica inferencia real no
executavel empacotado. `--check-assets` verifica seus recursos visuais.

EN: The default desktop build includes the existing local AI, its runtime
and the verified `local_models/inkwell.onnx` model. Install the `ai` extra
before building. Weights remain outside Git; obtain them from the source
and revision in `installer/inkwell/NOTICE.txt` (original `best.onnx`, renamed
locally to `inkwell.onnx`). Missing or different weights
fail the build. `KOMICOVE_BUILD_WITH_AI=0` explicitly produces a package
without AI, which is not the complete package. `--check-ai` runs actual
inference in the packaged executable; `--check-assets` verifies its assets.

PT-BR: Android padrao e universal: nao passe filtros de ABI ou
`-PguidedAiModel=none`. Preserve `com.lucrazy.panel` e use a assinatura
existente para atualizar sem remover dados. Linux e Windows desktop sao
x86_64; o pacote Linux depende da glibc da distribuicao de build e nao e
um instalador universal de todas as distribuicoes.

EN: The default Android build is universal: omit ABI filters and
`-PguidedAiModel=none`. Keep `com.lucrazy.panel` and the existing signature
to update without removing data. Linux and Windows desktop are x86_64;
the Linux package depends on the build distribution's glibc and is not
a universal installer for all distributions.

PT-BR: O Flatpak experimental tambem inclui o modelo verificado, suas licencas,
ONNX Runtime, NumPy e 7-Zip. Use `bash linux/build-flatpak.sh` com o SDK
Freedesktop 25.08 instalado. `KOMICOVE_LINUX_PYTHON` seleciona o Python que
consulta a versao; os overrides `KOMICOVE_FLATPAK_BUILD_DIR`,
`KOMICOVE_FLATPAK_STATE_DIR` e `KOMICOVE_FLATPAK_REPO_DIR` permitem builds
isolados. O bundle informa o repositorio Flathub para obter o runtime.
O identificador `io.github.lucrazy_fn.Komicove`, a branch e os dados existentes
sao preservados. Pesos ausentes ou com checksum diferente impedem o build.

EN: The experimental Flatpak also includes the verified model, its licenses,
ONNX Runtime, NumPy and 7-Zip. Run `bash linux/build-flatpak.sh` with the
Freedesktop 25.08 SDK installed. `KOMICOVE_LINUX_PYTHON` selects the Python
used to read the version; `KOMICOVE_FLATPAK_BUILD_DIR`,
`KOMICOVE_FLATPAK_STATE_DIR` and `KOMICOVE_FLATPAK_REPO_DIR` overrides allow
isolated builds. The bundle provides the Flathub repository for its runtime.
The `io.github.lucrazy_fn.Komicove` identifier, branch and existing data are
preserved. Missing weights or a different checksum prevent building.
