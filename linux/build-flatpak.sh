#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ "$(uname -s)" == Linux ]] || { echo 'Compile no Linux ou WSL.'; exit 1; }
python_bin="${KOMICOVE_LINUX_PYTHON:-python3}"
version="$("$python_bin" -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
build_dir="${KOMICOVE_FLATPAK_BUILD_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-build}"
state_dir="${KOMICOVE_FLATPAK_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-builder}"
repo_dir="${KOMICOVE_FLATPAK_REPO_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-repo}"
flatpak-builder --user --force-clean --state-dir="$state_dir" --repo="$repo_dir" "$build_dir" flatpak/io.github.lucrazy_fn.Komicove.yml
mkdir -p dist
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo "$repo_dir" "dist/Komicove-Linux-${version}-$(uname -m).flatpak" io.github.lucrazy_fn.Komicove
echo "dist/Komicove-Linux-${version}-$(uname -m).flatpak"
