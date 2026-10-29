#!/usr/bin/env bash
# Builds Book Reader with PyInstaller on Linux or macOS (on Windows use build_exe.bat).
#
#   bash build_exe.sh
#
# Result:  Linux -> dist/BookReader/BookReader        macOS -> dist/BookReader.app
# Uses the virtual environment in $VENV (default: .venv next to this file), creating it if needed.
set -euo pipefail
cd "$(dirname "$0")"

VENV="${VENV:-.venv}"
PY="${PYTHON:-python3}"

echo "Step 1/2: building the program ..."
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating the build environment in $VENV ..."
  "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"

echo "Installing build requirements ..."
"$VPY" -m pip install --upgrade pip
# Pillow lets PyInstaller turn book_reader.ico into the macOS .icns icon, and package_linux.sh
# uses it to make the Linux menu icon.
"$VPY" -m pip install -r requirements.txt pyinstaller pillow

echo "Building. This takes a few minutes ..."
"$VPY" -m PyInstaller --noconfirm --clean BookReader.spec

case "$(uname -s)" in
  Darwin) APP_EXE="dist/BookReader.app/Contents/MacOS/BookReader" ;;
  *)      APP_EXE="dist/BookReader/BookReader" ;;
esac
if [ ! -x "$APP_EXE" ]; then
  echo "BUILD FAILED: $APP_EXE was not produced. Scroll up for the reason."
  exit 1
fi

echo "Step 2/2: checking the packaged program (self-test) ..."
TEST_HOME="$(mktemp -d)"
set +e
# offscreen = no screen needed, so this also works on build servers
EPUB_READER_HOME="$TEST_HOME" QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" "$APP_EXE" --self-test
rc=$?
set -e
cat "$TEST_HOME/selftest.txt" 2>/dev/null || true
rm -rf "$TEST_HOME"
if [ "$rc" -ne 0 ]; then
  echo "SELF-TEST FAILED (exit code $rc)."
  exit 1
fi

echo "Done: $APP_EXE"