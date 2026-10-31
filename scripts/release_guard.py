"""Checks that a version can be released, before anything is built (used by release.yml).

    python scripts/release_guard.py 2.2.0 releases.json

releases.json is the output of
    gh release list --limit 1000 --json tagName,isDraft,isPrerelease

The run stops (exit code 1, with a GitHub ::error:: line) when
  - the version is not like 1.2.3 or 1.2.3-beta.4,
  - a published release already uses the tag v<version>, or
  - the version is not higher than the latest release of its channel:
      stable (1.2.3)      must be higher than the latest stable release
      beta (1.2.3-beta.4) must be higher than every published release, stable or beta,
                          because beta installs are offered both
    using semantic-version order: 2.2.0-beta.3 < 2.2.0 < 2.2.1-beta.1 < 2.2.1.

A leftover draft of the same tag (from a run that failed) is fine: the publish step fills it
and publishes it. Tags that are not versions (such as "update-feed") are ignored.
"""
from __future__ import annotations

import json
import re
import sys

VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")
PRE_RANK = {"alpha": 0, "beta": 1, "rc": 2}


def parse(text: str):
    """Sort key for a version (None if it isn't one). Pre-releases sort before their release."""
    m = VERSION.match(text or "")
    if not m:
        return None
    x, y, z, pre, n = m.groups()
    tail = (0, PRE_RANK[pre], int(n)) if pre else (1, 0, 0)
    return int(x), int(y), int(z), *tail


def is_prerelease(text: str) -> bool:
    return "-" in text


def check(version: str, releases: list) -> tuple[bool, list, str]:
    """(ok, messages, highest version it was compared with)."""
    key = parse(version)
    if key is None:
        return False, [f'"{version}" is not a version like 1.2.3 or 1.2.3-beta.4 '
                       f"(tags must look like v1.2.3)"], ""
    tag = f"v{version.lstrip('v')}"
    msgs = []
    for r in releases:
        if r.get("tagName") == tag:
            if r.get("isDraft"):
                msgs.append(f"A draft release {tag} is left over from an earlier run; "
                            f"it will be filled and published.")
            else:
                return False, [f"Release {tag} already exists. Release a higher version, "
                               f"or delete that release first if it was a mistake."], ""
    published = [r["tagName"] for r in releases
                 if not r.get("isDraft") and parse(r.get("tagName", "")) is not None]
    if not is_prerelease(version):
        published = [t for t in published if not is_prerelease(t)]   # compare stable with stable
    if not published:
        return True, msgs + ["No earlier release to compare with."], ""
    highest = max(published, key=parse)
    if key <= parse(highest):
        what = "the latest stable release" if not is_prerelease(version) else "the latest release"
        return False, [f"{tag} is not higher than {what}, {highest}. "
                       f"Use a higher version number."], highest
    return True, msgs + [f"{tag} is higher than {highest}: OK."], highest


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: release_guard.py <version> <releases.json>")
    version, path = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as f:
        releases = json.load(f)
    ok, msgs, _ = check(version, releases)
    for m in msgs:
        print(m if ok else f"::error::{m}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
