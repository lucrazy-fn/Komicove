#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ "$(uname -s)" == Linux ]] || { echo 'Compile no Linux ou WSL.'; exit 1; }
python_bin="${KOMICOVE_LINUX_PYTHON:-python3}"
version="$($python_bin -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
"$python_bin" -m PyInstaller --noconfirm --distpath build/linux-dist --workpath build/linux-work installer/Komicove.spec
mkdir -p dist
tar -C build/linux-dist -czf "dist/Komicove-Linux-${version}-$(uname -m).tar.gz" Komicove
echo "dist/Komicove-Linux-${version}-$(uname -m).tar.gz"
