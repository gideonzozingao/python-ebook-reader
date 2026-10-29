"""Puts a release's update manifest into the update feed.

The feed is a GitHub release named "update-feed" holding one file per channel:
    stable.json   read by stable installs
    beta.json     read by beta installs
Each file is a copy of the latest.json that tools/make_manifest.py writes for a release, so the
app reads the same format as before. A stable release also updates beta.json unless that
already points at a newer beta, so beta testers are offered the final release too.

    python tools/update_feed.py --manifest installer/latest.json --version 1.2.0 \
        --channel stable --feed feed
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")
PRE_RANK = {"alpha": 0, "beta": 1, "rc": 2}


def order(version: str) -> tuple:
    m = VERSION.match(version or "")
    if not m:
        return (-1,)
    x, y, z, pre, n = m.groups()
    # a final release sorts after its own betas: 1.2.0-beta.3 < 1.2.0
    return (int(x), int(y), int(z), 0 if pre else 1, PRE_RANK.get(pre, 3), int(n or 0))


def version_in(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("version") if isinstance(data, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--version", required=True)
    ap.add_argument("--channel", required=True, choices=["stable", "beta"])
    ap.add_argument("--feed", required=True, type=Path)
    a = ap.parse_args()

    a.feed.mkdir(parents=True, exist_ok=True)
    targets = [a.channel]
    if a.channel == "stable":
        current_beta = version_in(a.feed / "beta.json")
        if current_beta is None or order(current_beta) <= order(a.version):
            targets.append("beta")
        else:
            print(f"beta.json kept at {current_beta} (newer than {a.version})")
    for channel in targets:
        shutil.copyfile(a.manifest, a.feed / f"{channel}.json")
        print(f"{channel}.json -> {a.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
