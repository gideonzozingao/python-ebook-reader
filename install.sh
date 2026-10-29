#!/usr/bin/env bash
# Book Reader for Linux: installs for the current user, no root needed.
#
#   ./install.sh                  install into ~/.local/share/BookReader, add a menu entry and
#                                 the "book-reader" command, and offer Book Reader in "Open with"
#                                 for EPUB, PDF and Markdown (your default apps are not changed)
#   ./install.sh --uninstall      remove it again
#   PREFIX=/opt ./install.sh      install into /opt/BookReader instead (needs write access there)
#
# Your books, notes and settings live in ~/.epub_reader and are never touched by this script.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="${PREFIX:-$DATA}/BookReader"
BIN_DIR="$HOME/.local/bin"
DESKTOP="$DATA/applications/book-reader.desktop"
ICON="$DATA/icons/hicolor/256x256/apps/book-reader.png"

refresh_menus() {
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$DATA/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

MODE="install"
if [ "$(basename "$0")" = "uninstall.sh" ]; then
  MODE="uninstall"
  APP_DIR="$HERE"          # the copy inside the installed folder removes that folder
elif [ "${1:-}" = "--uninstall" ]; then
  MODE="uninstall"
fi

case "$APP_DIR" in
  */BookReader) ;;
  *) echo "Refusing to continue: unexpected install folder $APP_DIR" >&2; exit 1 ;;
esac

if [ "$MODE" = "uninstall" ]; then
  rm -rf "$APP_DIR"
  rm -f "$DESKTOP" "$ICON" "$BIN_DIR/book-reader"
  refresh_menus
  echo "Book Reader was removed. Your library in ~/.epub_reader was kept."
  exit 0
fi

if [ ! -x "$HERE/BookReader/BookReader" ]; then
  echo "Run this script from the unpacked Book Reader folder (BookReader/BookReader is missing)." >&2
  exit 1
fi

mkdir -p "$(dirname "$APP_DIR")" "$BIN_DIR" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
rm -rf "$APP_DIR"
cp -a "$HERE/BookReader" "$APP_DIR"
cp "$HERE/install.sh" "$APP_DIR/uninstall.sh"
chmod +x "$APP_DIR/uninstall.sh"

cp "$HERE/book-reader.png" "$ICON"
sed "s|@APP_DIR@|$APP_DIR|g" "$HERE/book-reader.desktop" > "$DESKTOP"
chmod 644 "$DESKTOP"
ln -sf "$APP_DIR/BookReader" "$BIN_DIR/book-reader"
refresh_menus

echo "Book Reader is installed in $APP_DIR"
echo "Start it from your applications menu, or run: book-reader"
echo "To remove it later: $APP_DIR/uninstall.sh"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "(Note: $BIN_DIR is not on your PATH, so the book-reader command needs a new login first.)" ;;
esac
