"""Builds Book Reader with Nuitka: Python -> C -> machine code.

The result goes where PyInstaller puts it, so the packaging steps work unchanged:
    Linux / Windows -> dist/BookReader/  (BookReader or BookReader.exe inside)
    macOS           -> dist/BookReader.app

Usage (from the build environment's Python, with nuitka installed):
    python tools/build_nuitka.py
Environment switch: BR_CONSOLE=1 keeps a console window (Windows) for debugging.
A C compiler is needed: gcc on Linux, clang (Xcode command line tools) on macOS,
MSVC or MinGW on Windows (Nuitka offers to download MinGW).
"""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_ICO = ROOT / "book_reader" / "assets" / "book_reader.ico"
OUT = ROOT / "build" / "nuitka"
DIST = ROOT / "dist"

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

BUNDLE_ID = "io.github.gideonzozingao.bookreader"

# Packages the app never uses; PyMuPDF can pull some of them in (the PyInstaller spec excludes
# the same list).
NOT_NEEDED = ["numpy", "onnxruntime", "scipy", "pandas", "matplotlib", "PIL", "IPython",
              "pytest", "tkinter", "networkx", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
              "PySide6.QtQml"]


def read_version() -> str:
    text = (ROOT / "book_reader" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"(\d+(?:\.\d+){1,3})"', text)
    if not m:
        sys.exit('Could not read a plain numeric __version__ from book_reader/__init__.py')
    return m.group(1)


def make_icns(work: Path) -> Path:
    """macOS app icon: the largest picture in the .ico, turned into .icns with iconutil."""
    from PIL import Image  # build-time only; build_exe.sh installs Pillow

    im = Image.open(ICON_ICO)
    sizes = im.info.get("sizes") or {im.size}
    im.size = max(sizes)
    im.load()
    src = im.convert("RGBA")
    iconset = work / "BookReader.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for px in (16, 32, 128, 256, 512):
        src.resize((px, px), Image.LANCZOS).save(iconset / f"icon_{px}x{px}.png")
        src.resize((px * 2, px * 2), Image.LANCZOS).save(iconset / f"icon_{px}x{px}@2x.png")
    icns = work / "BookReader.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    return icns


def finish_mac_bundle(app: Path, version: str) -> None:
    """Adds what Nuitka does not write itself: "Open With" entries and display name."""
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as f:
        info = plistlib.load(f)

    def doc(name: str, uti: str) -> dict:
        # 'Alternate': listed under "Open With", the user's default apps stay the same.
        return {"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate", "LSItemContentTypes": [uti]}

    info.update({
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": "BookReader",
        "CFBundleDisplayName": "Book Reader",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.books",
        "CFBundleDocumentTypes": [
            doc("EPUB book", "org.idpf.epub-container"),
            doc("PDF document", "com.adobe.pdf"),
            doc("Markdown document", "net.daringfireball.markdown"),
        ],
    })
    with plist_path.open("wb") as f:
        plistlib.dump(info, f)
    # Changing Info.plist breaks the existing signature; Apple Silicon will not start an app with
    # a broken one, so sign it again (ad-hoc; package_macos.sh does the same before the .dmg).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)


def main() -> int:
    os.chdir(ROOT)
    version = read_version()
    console = os.environ.get("BR_CONSOLE") == "1"
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)

    cmd = [
        sys.executable, "-m", "nuitka", "epub_reader2.py",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=platforms,svg",
        "--noinclude-qt-translations",
        "--include-package=book_reader",
        "--include-data-dir=book_reader/assets=book_reader/assets",
        # loaded by name at run time, so Nuitka cannot see them being imported
        "--include-package=markdown.extensions",
        "--include-package=pymupdf",
        "--include-package-data=pymupdf",
        "--nofollow-import-to=" + ",".join(NOT_NEEDED),
        "--output-filename=BookReader",
        f"--output-dir={OUT}",
        "--assume-yes-for-downloads",
        "--show-progress" if os.environ.get("CI") else "--quiet",
    ]
    if IS_WIN:
        cmd += [
            f"--windows-console-mode={'force' if console else 'disable'}",
            f"--windows-icon-from-ico={ICON_ICO}",
            "--company-name=Book Reader",
            "--product-name=Book Reader",
            f"--file-version={version}",
            f"--product-version={version}",
            "--file-description=Book Reader",
        ]
    if IS_MAC:
        work = Path(tempfile.mkdtemp())
        cmd += [
            "--macos-create-app-bundle",
            "--macos-app-mode=gui",
            "--macos-app-name=Book Reader",
            f"--macos-app-version={version}",
            f"--macos-signed-app-name={BUNDLE_ID}",
            f"--macos-app-icon={make_icns(work)}",
        ]

    print("Nuitka build of Book Reader", version)
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

    DIST.mkdir(exist_ok=True)
    if IS_MAC:
        built = OUT / "epub_reader2.app"
        target = DIST / "BookReader.app"
    else:
        built = OUT / "epub_reader2.dist"
        target = DIST / "BookReader"
    if not built.exists():
        sys.exit(f"Nuitka finished but {built} is missing")
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(built), str(target))
    if IS_MAC:
        finish_mac_bundle(target, version)

    print("Nuitka build done:", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
