"""Rewrites the release statistics in README.md (between the stats markers) from the GitHub API.

Run by the release workflow after each published release:
    GH_TOKEN=... GH_REPO=owner/repo python3 tools/update_readme_stats.py README.md

Counts only real downloads (installers and packages), not the update-feed files that installed
apps poll, and ignores the "update-feed" release itself.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

START = "<!-- stats:start -->"
END = "<!-- stats:end -->"
WORKFLOW = "release.yml"
FEED_TAG = "update-feed"


def api(path: str) -> dict | list:
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def all_releases(repo: str) -> list[dict]:
    out, page = [], 1
    while True:
        batch = api(f"repos/{repo}/releases?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def run_count(repo: str, status: str) -> tuple[int, dict | None]:
    data = api(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?status={status}&per_page=1")
    runs = data.get("workflow_runs") or []
    return data.get("total_count", 0), (runs[0] if runs else None)


def day(stamp: str | None) -> str:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).strftime("%Y-%m-%d") if stamp else "-"


def platform(name: str) -> str | None:
    if name.endswith(".exe"):
        return "Windows"
    if name.endswith(".tar.gz"):
        return "Linux"
    if name.endswith(".dmg"):
        return "macOS"
    return None


def build_table(repo: str) -> str:
    releases = [r for r in all_releases(repo) if not r.get("draft") and r.get("tag_name") != FEED_TAG]
    releases.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    stable = next((r for r in releases if not r.get("prerelease")), None)
    beta = next((r for r in releases if r.get("prerelease")), None)

    downloads = {"Windows": 0, "Linux": 0, "macOS": 0}
    for r in releases:
        for asset in r.get("assets", []):
            p = platform(asset.get("name", ""))
            if p:
                downloads[p] += asset.get("download_count", 0)

    ok, last_ok = run_count(repo, "success")
    failed, _ = run_count(repo, "failure")
    finished = ok + failed
    rate = f"{ok * 100 // finished}%" if finished else "-"

    def rel(r: dict | None) -> str:
        if not r:
            return "-"
        return f"[{r['tag_name']}]({r['html_url']}) ({day(r.get('published_at'))})"

    last_run = f"[{day(last_ok.get('updated_at'))}]({last_ok['html_url']})" if last_ok else "-"
    total = sum(downloads.values())
    lines = [
        "| | |",
        "|---|---|",
        f"| **Latest stable** | {rel(stable)} |",
        f"| **Latest beta** | {rel(beta)} |",
        f"| **Releases published** | {len(releases)} |",
        f"| **Successful release runs** | {ok} of {finished} finished ({rate} success) |",
        f"| **Last successful run** | {last_run} |",
        f"| **Downloads** | {total:,} in total: Windows {downloads['Windows']:,}, "
        f"Linux {downloads['Linux']:,}, macOS {downloads['macOS']:,} |",
        "",
        f"<sub>Updated automatically after each release ({datetime.utcnow():%Y-%m-%d %H:%M} UTC).</sub>",
    ]
    return "\n".join(lines)


def main() -> int:
    readme = Path(sys.argv[1] if len(sys.argv) > 1 else "README.md")
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print(f"No {START} ... {END} block in {readme}; nothing to update.")
        return 0
    block = f"{START}\n{build_table(os.environ['GH_REPO'])}\n{END}"
    new = pattern.sub(lambda _: block, text, count=1)
    if new != text:
        readme.write_text(new, encoding="utf-8")
        print("README stats updated")
    else:
        print("README stats unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())