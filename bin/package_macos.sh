#!/usr/bin/env bash
# Wraps dist/BookReader.app (from bin/build_exe.sh) in a drag-to-Applications disk image:
#     installer/BookReader-<version>-macos-<arch>.dmg
#   Usage: bash bin/package_macos.sh 1.2.0
#
# The app gets an "ad-hoc" signature, which Apple Silicon needs to run it at all. It is NOT an
# Apple Developer ID signature, so on first launch users must right-click the app -> Open
# (or run: xattr -dr com.apple.quarantine /Applications/BookReader.app).
set -euo pipefail
cd "$(dirname "$0")/.."   # the project folder (this script is in bin)

VERSION="${1:?usage: bash bin/package_macos.sh <version>}"
ARCH="$(uname -m)"            # arm64 on Apple Silicon, x86_64 on Intel
APP="dist/BookReader.app"
DMG="installer/BookReader-$VERSION-macos-$ARCH.dmg"
STAGE="build/dmg"

if [ ! -d "$APP" ]; then
  echo "$APP is missing: run bin/build_exe.sh first." >&2
  exit 1
fi

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

rm -rf "$STAGE"
mkdir -p "$STAGE" installer
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"

# hdiutil sometimes fails with "Resource busy" on build machines, so try a few times.
for attempt in 1 2 3; do
  if hdiutil create -volname "Book Reader $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"; then
    break
  fi
  if [ "$attempt" -eq 3 ]; then
    echo "hdiutil could not create $DMG" >&2
    exit 1
  fi
  sleep 5
done

ls -lh "$DMG"
echo "Done: $DMG"
