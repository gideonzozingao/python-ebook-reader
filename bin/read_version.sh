#!/usr/bin/env bash
# Prints the app version from book_reader/__init__.py. In a GitHub tag build it also checks that
# the tag matches (v1.2.0 <-> "1.2.0") and writes version=... to $GITHUB_OUTPUT.
#   Usage: bash bin/read_version.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ver="$(sed -nE 's/^__version__[[:space:]]*=[[:space:]]*"([0-9]+(\.[0-9]+){1,3})".*/\1/p' book_reader/__init__.py | head -n 1)"
if [ -z "$ver" ]; then
  echo 'Could not read a plain numeric __version__ (like "1.2.0") from book_reader/__init__.py' >&2
  exit 1
fi
if [ "${GITHUB_REF_TYPE:-}" = "tag" ] && [ "${GITHUB_REF_NAME:-}" != "v$ver" ]; then
  echo "The tag ${GITHUB_REF_NAME} does not match __version__ $ver. Bump book_reader/__init__.py, or tag v$ver." >&2
  exit 1
fi
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "version=$ver" >> "$GITHUB_OUTPUT"
fi
echo "$ver"
