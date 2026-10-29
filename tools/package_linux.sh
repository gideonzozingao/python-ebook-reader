#!/usr/bin/env bash
# Packs dist/BookReader (from build_exe.sh) into
#     installer/BookReader-<version>-linux-<arch>.tar.gz
# together with a menu entry, an icon and install.sh.
#   Usage: bash tools/package_linux.sh 1.2.0
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:?usage: bash tools/package_linux.sh <version>}"
ARCH="$(uname -m)"
NAME="BookReader-$VERSION-linux-$ARCH"
WORK="build/linux-package"
STAGE="$WORK/$NAME"
VPY="${VENV:-.venv}/bin/python"

if [ ! -x dist/BookReader/BookReader ]; then
  echo "dist/BookReader/BookReader is missing: run build_exe.sh first." >&2
  exit 1
fi

rm -rf "$WORK"
mkdir -p "$STAGE" installer
cp -a dist/BookReader "$STAGE/BookReader"
cp packaging/linux/book-reader.desktop packaging/linux/install.sh "$STAGE/"
chmod +x "$STAGE/install.sh" "$STAGE/BookReader/BookReader"

# Menu icon: the largest picture inside the Windows .ico, as a 256x256 PNG.
"$VPY" - "$STAGE/book-reader.png" <<'EOF'
import sys
from PIL import Image
im = Image.open("book_reader/assets/book_reader.ico")
sizes = im.info.get("sizes") or {im.size}
im.size = max(sizes)          # the ICO reader loads the size chosen here
im.load()
im.convert("RGBA").resize((256, 256), Image.LANCZOS).save(sys.argv[1])
EOF

tar -C "$WORK" -czf "installer/$NAME.tar.gz" "$NAME"
ls -lh "installer/$NAME.tar.gz"
echo "Done: installer/$NAME.tar.gz"
