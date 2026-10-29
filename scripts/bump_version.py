"""Bumps __version__ in book_reader/__init__.py and prints the new version.

    python scripts/bump_version.py patch stable     1.1.1 -> 1.1.2        1.2.0-beta.3 -> 1.2.0
    python scripts/bump_version.py minor stable     1.1.1 -> 1.2.0        1.2.0-beta.3 -> 1.3.0
    python scripts/bump_version.py patch beta       1.1.1 -> 1.1.2-beta.1 1.1.2-beta.1 -> 1.1.2-beta.2
    python scripts/bump_version.py minor beta       1.1.1 -> 1.2.0-beta.1 1.2.0-beta.3 -> 1.3.0-beta.1
    python scripts/bump_version.py --show           prints the current version, changes nothing
    python scripts/bump_version.py --set 1.1.1      sets the version (used to undo a failed release)

Rule of thumb: from a beta, "patch stable" publishes that beta's version as the final release,
and "patch beta" makes the next beta of the same version.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "book_reader" / "__init__.py"
ASSIGN = re.compile(r'(__version__\s*=\s*")([^"]+)(")')
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")


def parse(text: str) -> tuple[int, int, int, str | None, int]:
    m = VERSION.match(text)
    if not m:
        sys.exit(f'__version__ "{text}" is not like 1.2.3 or 1.2.3-beta.4')
    x, y, z, pre, n = m.groups()
    return int(x), int(y), int(z), pre, int(n or 0)


def next_version(current: str, bump: str, channel: str) -> str:
    x, y, z, pre, n = parse(current)

    def bumped() -> tuple[int, int, int]:
        if bump == "major":
            return x + 1, 0, 0
        if bump == "minor":
            return x, y + 1, 0
        return x, y, z + 1

    if channel == "stable":
        if pre and bump == "patch":
            return f"{x}.{y}.{z}"                      # finish the beta as the final release
        return "{}.{}.{}".format(*bumped())
    if pre == "beta" and bump == "patch":
        return f"{x}.{y}.{z}-beta.{n + 1}"            # next beta of the same version
    if pre and bump == "patch":
        return f"{x}.{y}.{z}-beta.1"
    return "{}.{}.{}-beta.1".format(*bumped())


def main() -> int:
    text = INIT.read_text(encoding="utf-8")
    m = ASSIGN.search(text)
    if not m:
        sys.exit(f"No __version__ = \"...\" line found in {INIT}")
    current = m.group(2)
    args = sys.argv[1:]
    if args == ["--show"]:
        parse(current)
        print(current)
        return 0
    if len(args) == 2 and args[0] == "--set":
        parse(args[1])
        INIT.write_text(text[:m.start(2)] + args[1] + text[m.end(2):], encoding="utf-8")
        print(args[1])
        return 0
    if len(args) != 2 or args[0] not in ("patch", "minor", "major") or args[1] not in ("stable", "beta"):
        sys.exit("usage: bump_version.py patch|minor|major stable|beta   (or --show, or --set X.Y.Z)")
    new = next_version(current, args[0], args[1])
    INIT.write_text(text[:m.start(2)] + new + text[m.end(2):], encoding="utf-8")
    print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())