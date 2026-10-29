[![Release](https://github.com/gideonzozingao/python-ebook-reader/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/gideonzozingao/python-ebook-reader/actions/workflows/release.yml)

# Book Reader

A desktop reader for **EPUB**, **PDF** and **Markdown** books, with notes, a reading
clock and daily reading goals. Built with Python and Qt (PySide6), and available for
Windows, Linux and macOS.

<!-- Add a screenshot: save it as docs/screenshot.png and uncomment the line below.
![Book Reader](docs/screenshot.png)
-->

## Features

- **Read EPUB, PDF and Markdown** (`.epub`, `.pdf`, `.md`, `.markdown`) in one app, with a
  library that shows your books with their covers.
- **Take notes while you read**, sorted by topic: _General_, _Key idea_, _Quote_,
  _Question_, _Action item_, _To look up_ and _Vocabulary_.
- **Review your notes** grouped by book section, by topic or by date.
- **Reading clock and daily goal.** Tracks how long you read (pausing automatically after
  5 minutes without activity) against a daily goal, 20 minutes by default.
- **Voice dictation** for notes (optional, see [below](#optional-voice-dictation)).
- **"Open with" integration.** Book Reader is offered for EPUB, PDF and Markdown files
  without changing your default apps.
- **Automatic updates on Windows.** The app checks GitHub for new releases and can install
  them for you.
- **Your data stays local.** Books, notes and settings are stored on your own computer,
  never uploaded.

## Download and install

Get the latest version from the
[**Releases page**](https://github.com/gideonzozingao/python-ebook-reader/releases/latest).

### Windows

Download `BookReader-Setup-<version>.exe` and run it. No administrator rights are needed:
it installs for your user account, or for all users if you choose that in the installer.
New versions are offered inside the app.

> If Windows SmartScreen says it _protected your PC_, click **More info → Run anyway**.
> This appears for installers that are not code-signed.

### Linux (x86_64)

```bash
tar -xzf BookReader-<version>-linux-x86_64.tar.gz
cd BookReader-<version>-linux-x86_64
./install.sh
```

This installs into `~/.local/share/BookReader` (no root needed), adds a menu entry and a
`book-reader` command. To remove it: `~/.local/share/BookReader/uninstall.sh`.

If the app does not start, install Qt's cursor library:
`sudo apt install libxcb-cursor0` (Debian/Ubuntu).

### macOS (Apple Silicon)

Open `BookReader-<version>-macos-arm64.dmg` and drag **BookReader** to **Applications**.

The app is not notarized by Apple yet, so the first time, **right-click the app → Open**
and confirm. Alternatively run:

```bash
xattr -dr com.apple.quarantine /Applications/BookReader.app
```

On Linux and macOS, update by downloading the new release (automatic updates are
Windows-only for now).

## Where your data lives

Your library, notes and settings are kept in **`~/.epub_reader`**
(`C:\Users\<you>\.epub_reader` on Windows). Updating or uninstalling the app never touches
this folder, and the installed app and the Python version (below) share it.

To keep the data somewhere else, set the environment variable `EPUB_READER_HOME` to a
folder of your choice.

## Run from source

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/gideonzozingao/python-ebook-reader.git
cd python-ebook-reader
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
python epub_reader2.py
```

Main dependencies: [PySide6](https://doc.qt.io/qtforpython/) (user interface),
[PyMuPDF](https://pymupdf.readthedocs.io/) (PDF), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
(EPUB/HTML) and [Python-Markdown](https://python-markdown.github.io/).

### Optional: voice dictation

```bash
pip install SpeechRecognition pyaudio
```

The app works without these; dictation is simply unavailable.

### Self-test

```bash
python epub_reader2.py --self-test
```

checks that all components (Qt, PDF, EPUB and Markdown support, updater) load correctly.
The build scripts run the same check on every packaged program.

## Building

Two build tools are supported:

| Tool                      | What it does                                              | Build time                         |
| ------------------------- | --------------------------------------------------------- | ---------------------------------- |
| **PyInstaller** (default) | Bundles Python, the app and its libraries                 | 1–2 minutes                        |
| **Nuitka**                | Compiles the app's Python code to C, then to machine code | 10–30+ minutes, needs a C compiler |

Both produce the same layout, so packaging works the same either way.

### Windows

Needs [Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer
(`winget install JRSoftware.InnoSetup`).

```bat
build_exe.bat                   :: program only   -> dist\BookReader\BookReader.exe
build_installer.bat             :: program + installer -> installer\BookReader-Setup-<version>.exe
build_installer.bat /nuitka     :: same, compiled with Nuitka
```

Other options for `build_exe.bat`: `/console` (keep a console window for debugging),
`/voice` (bundle voice dictation), `/onefile` (single .exe, PyInstaller only).

For Nuitka on Windows, install **Visual Studio Build Tools** with the
_Desktop development with C++_ workload (including a Windows SDK). The build script loads
the compiler automatically.

### Linux and macOS

```bash
bash build_exe.sh                          # PyInstaller
BUILDER=nuitka bash build_exe.sh           # Nuitka
bash tools/package_linux.sh <version>      # Linux  -> installer/BookReader-<version>-linux-<arch>.tar.gz
bash tools/package_macos.sh <version>      # macOS  -> installer/BookReader-<version>-macos-<arch>.dmg
```

Linux builds need Qt's system libraries for the self-test
(`libegl1 libgl1 libxkbcommon0 libxcb-cursor0 libfontconfig1`). macOS builds need the Xcode
command line tools (`xcode-select --install`).

## Releasing

Releases are built and published by GitHub Actions
([`.github/workflows/release.yml`](.github/workflows/release.yml)) for all three platforms.

1. Set the new version in `book_reader/__init__.py`, e.g. `__version__ = "1.2.0"`.
2. Commit and push, then tag that commit:

   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```

The workflow checks that the tag matches `__version__`, builds and tests the Windows
installer, the Linux package and the macOS disk image, and publishes them to a GitHub
Release together with checksums and the `latest.json` file the Windows updater reads.

To test the builds without publishing, use **Actions → Release → Run workflow**; the
results are kept as downloadable artifacts. There you can also choose PyInstaller or
Nuitka (for tag releases, set the repository variable `BUILDER` to `nuitka`).

Optional Windows code signing: add the repository secrets `WINDOWS_CERT_PFX_BASE64` and
`WINDOWS_CERT_PASSWORD`. See [BUILD.md](BUILD.md) for details.

## Project layout

```
epub_reader2.py          entry point
book_reader/             the application package (core, services, ui, assets)
BookReader.spec          PyInstaller recipe (Windows, Linux, macOS)
installer.iss            Windows installer (Inno Setup)
build_exe.bat / .sh      build the program (PyInstaller or Nuitka)
build_installer.bat      build the Windows installer
tools/                   Nuitka build, Linux/macOS packaging, version and update manifest helpers
packaging/linux/         Linux install script and menu entry
.github/workflows/       automated release builds
```

## Contributing

Bug reports and suggestions are welcome in
[Issues](https://github.com/gideonzozingao/python-ebook-reader/issues). For code changes,
please open an issue first to discuss the idea, then send a pull request; run
`python epub_reader2.py --self-test` before submitting.

## License

<!-- Choose a license (e.g. MIT) and add a LICENSE file, then name it here. -->

No license has been chosen yet. Until one is added, all rights are reserved.
