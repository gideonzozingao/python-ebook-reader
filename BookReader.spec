# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe for Book Reader.   Build with build_exe.bat (Windows) or:
#     pyinstaller --noconfirm --clean BookReader.spec
# Environment switches:  BR_ONEFILE=1 (single .exe)   BR_CONSOLE=1 (show a console window)
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ICON = "book_reader/assets/book_reader.ico"
onefile = os.environ.get("BR_ONEFILE") == "1"
console = os.environ.get("BR_CONSOLE") == "1"

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

if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="BookReader", console=console,
              icon=ICON, upx=False, runtime_tmpdir=None)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="BookReader", console=console,
              icon=ICON, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="BookReader")
