#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ "$(uname -s)" == Linux ]] || { echo 'Compile no Linux ou WSL.'; exit 1; }
version="$(python3 -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
build_dir="${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-build"
state_dir="${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-builder"
repo_dir="${XDG_CACHE_HOME:-$HOME/.cache}/komicove-flatpak-repo"
flatpak-builder --user --force-clean --state-dir="$state_dir" --repo="$repo_dir" "$build_dir" flatpak/io.github.lucrazy_fn.Komicove.yml
mkdir -p dist
flatpak build-bundle "$repo_dir" "dist/Komicove-Linux-${version}-$(uname -m).flatpak" io.github.lucrazy_fn.Komicove
echo "dist/Komicove-Linux-${version}-$(uname -m).flatpak"
