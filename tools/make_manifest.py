"""Write the update manifest for a release.

    python tools/make_manifest.py installer/BookReader-Setup-1.2.0.exe ^
        --url https://example.com/downloads/BookReader-Setup-1.2.0.exe ^
        --notes "Faster start-up. Fixed a crash when opening large PDFs." ^
        --page https://example.com/book-reader

Creates next to the installer:
    latest.json                          upload this to the address in UPDATE_URL
    BookReader-Setup-1.2.0.exe.sha256    optional (GitHub Releases: attach it to the release)
--notes may also be @notes.md to read the text from a file.
Using GitHub Releases instead? You do not need latest.json at all; see BUILD.md.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def app_version() -> str:
    text = (ROOT / "book_reader" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("installer", help="path to BookReader-Setup-<version>.exe")
    ap.add_argument("--url", required=True, help="public HTTPS address the installer will be uploaded to")
    ap.add_argument("--notes", default="", help='release notes, or @file.md')
    ap.add_argument("--page", default="", help="web page shown to people who cannot update in place")
    args = ap.parse_args()

    exe = Path(args.installer)
    if not exe.is_file():
        print(f"Not found: {exe}")
        return 1
    m = re.search(r"Setup-(\d+(?:\.\d+){0,3})\.exe$", exe.name, re.I)
    if not m:
        print("The installer must be named like BookReader-Setup-1.2.0.exe")
        return 1
    version = m.group(1)
    if version != app_version():
        print(f"Version mismatch: the installer is {version} but book_reader/__init__.py says "
              f"{app_version()}.\nBump __version__, rebuild the installer, then run this again.")
        return 1
    if not args.url.lower().startswith("https://"):
        print("--url must start with https://")
        return 1

    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    notes = args.notes
    if notes.startswith("@"):
        notes = Path(notes[1:]).read_text(encoding="utf-8")
    manifest = {"version": version, "url": args.url, "sha256": sha, "size": exe.stat().st_size,
                "notes": notes, "page": args.page}
    (exe.parent / "latest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (exe.parent / (exe.name + ".sha256")).write_text(f"{sha}  {exe.name}\n", encoding="utf-8")
    print(f"Wrote {exe.parent / 'latest.json'}  (version {version}, sha256 {sha[:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
