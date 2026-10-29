# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe for Book Reader, for Windows, Linux and macOS.
#     Windows:        build_exe.bat
#     Linux / macOS:  bash build_exe.sh
#     or directly:    pyinstaller --noconfirm --clean BookReader.spec
#
# Result:  Windows -> dist/BookReader/BookReader.exe   Linux -> dist/BookReader/BookReader
#          macOS   -> dist/BookReader.app
# Environment switches:  BR_ONEFILE=1 (single file, Windows/Linux only)
#                        BR_CONSOLE=1 (show a console window)
import os
import re
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# Windows uses the .ico as is. On macOS PyInstaller converts it to .icns (needs Pillow in the
# build environment; build_exe.sh installs it). Linux programs have no embedded icon: the menu
# icon comes from tools/package_linux.sh.
ICON = "book_reader/assets/book_reader.ico"

# A macOS .app is always a folder build; a single-file program inside an .app starts slowly and
# PyInstaller discourages it, so BR_ONEFILE is ignored there.
onefile = os.environ.get("BR_ONEFILE") == "1" and not IS_MAC
console = os.environ.get("BR_CONSOLE") == "1"

with open("book_reader/__init__.py", encoding="utf-8") as f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
# macOS bundle versions must be plain numbers: 1.2.3-beta.4 -> 1.2.3
NUM_VERSION = VERSION.split("-", 1)[0]

datas = [("book_reader/assets", "book_reader/assets")]
binaries, hiddenimports = [], ["PySide6.QtSvg", "bs4", "html.parser"]

# Packages that load parts of themselves by name at run time (extensions, binary libraries).
for pkg in ("pymupdf", "markdown", "speech_recognition", "pyaudio"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue                      # optional package that is not installed
    datas += d
    binaries += b
    hiddenimports += h
try:
    hiddenimports += collect_submodules("fitz")   # older PyMuPDF name
except Exception:
    pass

a = Analysis(
    ["epub_reader2.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
              # large packages the app never uses (they only get in if they are installed)
              "numpy", "scipy", "pandas", "matplotlib", "PIL", "IPython", "pytest"],
    noarchive=False,
)
# Qt's translation files (7 MB) only matter for non-English Qt dialogs.
a.datas = [d for d in a.datas if "Qt/translations" not in d[0].replace("\\", "/")]
pyz = PYZ(a.pure)

# macOS: books opened from Finder ("Open with", double-click) arrive as an Apple event, not as a
# command-line argument; argv_emulation turns the one sent at start-up into sys.argv.
mac_options = {"argv_emulation": True} if IS_MAC else {}

if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="BookReader", console=console,
              icon=ICON, upx=False, runtime_tmpdir=None, **mac_options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="BookReader", console=console,
              icon=ICON, upx=False, **mac_options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="BookReader")

if IS_MAC:
    def _doc_type(name, uti):
        # 'Alternate': Book Reader appears under "Open With", your default apps stay the same.
        return {"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate", "LSItemContentTypes": [uti]}

    app = BUNDLE(
        coll,
        name="BookReader.app",
        icon=ICON,
        bundle_identifier="io.github.gideonzozingao.bookreader",
        version=NUM_VERSION,
        info_plist={
            "CFBundleDisplayName": "Book Reader",
            "CFBundleShortVersionString": NUM_VERSION,
            "CFBundleVersion": NUM_VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.books",
            "CFBundleDocumentTypes": [
                _doc_type("EPUB book", "org.idpf.epub-container"),
                _doc_type("PDF document", "com.adobe.pdf"),
                _doc_type("Markdown document", "net.daringfireball.markdown"),
            ],
        },
    )
