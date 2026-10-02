#!/usr/bin/env bash
# Scoped Linux release build, with an explicit source allowlist (no personal data).
set -euo pipefail
mode="${1:?prepare, native or flatpak}"
repo_root="$(realpath "${2:?repository directory}")"
work_root="$(realpath "${3:?new dedicated build directory}")"
delivery="$(realpath "${4:?delivery directory}")"
[[ "$(uname -s)" == Linux ]] || { echo 'Linux is required.'; exit 1; }
[[ "$work_root" == /home/*/komicove-release-* && "$work_root" != "$repo_root" ]] || {
  echo 'Refusing an unexpected build directory.'; exit 1;
}
source_root="$work_root/source"
python_bin="$work_root/venv/bin/python"

case "$mode" in
  prepare)
    [[ ! -e "$source_root" ]] || { echo 'Source staging already exists.'; exit 1; }
    mkdir "$source_root"
    tar -C "$repo_root" --exclude='__pycache__' --exclude='*.pyc' --exclude='*.db' \
      --exclude='*.sqlite*' --exclude='.env*' -cf - \
      komicove_app komicove_client komicove_backend panel_backend.py \
      pyproject.toml README.md LICENSE Icons assets_redesign komicovelogo.png \
      Komicove.ico installer flatpak tests linux | tar -C "$source_root" -xf -
    python3 -m venv "$work_root/venv"
    "$python_bin" -m pip install --disable-pip-version-check -e "$source_root[build,test,server]"
    ;;
  native)
    cd "$work_root"
    # Repository-policy tests intentionally inspect Android sources and .git.
    # Run the real suite in place; do not copy Git/secrets into the build source.
    xvfb-run -a "$python_bin" -m pytest -o addopts= -p no:cacheprovider -q -ra \
      "$repo_root/tests" --basetemp "$work_root/pytest-native"
    cd "$source_root"
    "$python_bin" -m PyInstaller --noconfirm --distpath "$work_root/native-dist" \
      --workpath "$work_root/native-work" installer/Komicove.spec
    xvfb-run -a env KOMICOVE_APPDATA_DIR="$work_root/native-smoke" \
      "$work_root/native-dist/Komicove/Komicove" --check-assets
    version="$("$python_bin" -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
    output="$delivery/Komicove-Linux-$version-$(uname -m).tar.gz"
    [[ ! -e "$output" ]] || { echo 'Refusing to overwrite an existing release.'; exit 1; }
    tar -C "$work_root/native-dist" -czf "$output" Komicove
    tar -tzf "$output" >/dev/null
    sha256sum "$output"
    ;;
  flatpak)
    flatpak --user remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    flatpak --user install -y --noninteractive flathub org.freedesktop.Sdk//25.08
    [[ ! -e "$work_root/flatpak-tree" ]] || { echo 'Flatpak staging already exists.'; exit 1; }
    flatpak-builder --user --disable-rofiles-fuse --state-dir="$work_root/flatpak-state" \
      --repo="$work_root/flatpak-repo" "$work_root/flatpak-tree" \
      "$source_root/flatpak/io.github.lucrazy_fn.Komicove.yml"
    version="$(cd "$source_root"; "$python_bin" -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
    output="$delivery/Komicove-Linux-$version-$(uname -m).flatpak"
    [[ ! -e "$output" ]] || { echo 'Refusing to overwrite an existing release.'; exit 1; }
    flatpak build-bundle "$work_root/flatpak-repo" "$output" io.github.lucrazy_fn.Komicove
    sha256sum "$output"
    ;;
  *) echo 'Unknown build mode.'; exit 1 ;;
esac
