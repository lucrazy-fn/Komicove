#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ "$(uname -s)" == Linux ]] || { echo 'Compile no Linux ou WSL.'; exit 1; }
python_bin="${KOMICOVE_LINUX_PYTHON:-python3}"
version="$($python_bin -c 'from komicove_app.updater import CURRENT_VERSION; print(CURRENT_VERSION)')"
arch="$(uname -m)"
case "$arch" in
  x86_64) sevenzip_archive='7z2604-linux-x64.tar.xz'; sevenzip_sha='fc0327ba27e89bd086cf426dff17d77de582953cdbbc10a6576540a06853ffcd' ;;
  aarch64) sevenzip_archive='7z2604-linux-arm64.tar.xz'; sevenzip_sha='5b0ac3aa91c1e3499f011d6af69d7f6b4de3ef2f011d9e2ff44c58ebd04aa388' ;;
  *) echo "Arquitetura Linux sem 7-Zip verificado: $arch" >&2; exit 1 ;;
esac
sevenzip_dir="build/linux-tools/7zip-$arch"
if [[ ! -x "$sevenzip_dir/7zz" || ! -f "$sevenzip_dir/License.txt" ]]; then
  mkdir -p "$sevenzip_dir"
  archive_path="$sevenzip_dir/$sevenzip_archive"
  curl --fail --location --output "$archive_path" "https://www.7-zip.org/a/$sevenzip_archive"
  echo "$sevenzip_sha  $archive_path" | sha256sum --check --status
  tar -xJf "$archive_path" -C "$sevenzip_dir" 7zz License.txt
  chmod 755 "$sevenzip_dir/7zz"
fi
export KOMICOVE_BUNDLED_7ZIP_PATH="$PWD/$sevenzip_dir/7zz"
"$python_bin" -m PyInstaller --noconfirm --distpath build/linux-dist --workpath build/linux-work installer/Komicove.spec
mkdir -p dist
tar -C build/linux-dist -czf "dist/Komicove-Linux-${version}-${arch}.tar.gz" Komicove
echo "dist/Komicove-Linux-${version}-${arch}.tar.gz"
