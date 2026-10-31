#!/usr/bin/env bash
# Builds Book Reader with PyInstaller on Linux or macOS (on Windows use bin\build.ps1).
#
#   bash bin/build_exe.sh            (from any folder: it builds in the project folder)
#
# Result:  Linux -> dist/BookReader/BookReader        macOS -> dist/BookReader.app
# Uses the virtual environment in $VENV (default: .venv in the project folder), creating it if needed.
#
# Choose the build tool with BUILDER:
#   BUILDER=pyinstaller  (default) bundles Python bytecode; builds in a minute or two
#   BUILDER=nuitka       compiles the code to C and then to machine code; builds take much longer
#                        and need a C compiler (gcc on Linux, Xcode command line tools on macOS)
set -euo pipefail
cd "$(dirname "$0")/.."   # the project folder (this script is in bin)

VENV="${VENV:-.venv}"
PY="${PYTHON:-python3}"
BUILDER="${BUILDER:-pyinstaller}"
case "$BUILDER" in
  pyinstaller|nuitka) ;;
  *) echo "BUILDER must be pyinstaller or nuitka, got: $BUILDER" >&2; exit 1 ;;
esac

echo "Step 1/2: building the program with $BUILDER ..."
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating the build environment in $VENV ..."
  "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"

echo "Installing build requirements ..."
"$VPY" -m pip install --upgrade pip
# Same requirement files as bin/build.ps1 on Windows (they add Pillow for the icons, and Nuitka's
# patchelf on Linux).
if [ "$BUILDER" = "nuitka" ]; then REQS=requirements-build-nuitka.txt; else REQS=requirements-build.txt; fi
"$VPY" -m pip install -r "$REQS"
if [ "$BUILDER" = "nuitka" ]; then
  echo "Compiling with Nuitka. This takes a while (often 10-30 minutes) ..."
  rm -rf dist/BookReader dist/BookReader.app
  # the venv's bin folder on PATH, so Nuitka finds the pip-installed patchelf
  PATH="$(cd "$VENV/bin" && pwd):$PATH" "$VPY" tools/build_nuitka.py
else
  echo "Building with PyInstaller. This takes a few minutes ..."
  "$VPY" -m PyInstaller --noconfirm --clean BookReader.spec
fi

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
