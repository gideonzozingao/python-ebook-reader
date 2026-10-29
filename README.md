[![Release workflow](https://github.com/gideonzozingao/python-ebook-reader/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/gideonzozingao/python-ebook-reader/actions/workflows/release.yml)
[![Latest stable](https://img.shields.io/github/v/release/gideonzozingao/python-ebook-reader?sort=semver&label=stable&color=2ea44f)](https://github.com/gideonzozingao/python-ebook-reader/releases/latest)
[![Latest beta](https://img.shields.io/github/v/release/gideonzozingao/python-ebook-reader?include_prereleases&sort=semver&filter=*beta*&label=beta&color=orange)](https://github.com/gideonzozingao/python-ebook-reader/releases)
[![Release date](https://img.shields.io/github/release-date/gideonzozingao/python-ebook-reader?label=released)](https://github.com/gideonzozingao/python-ebook-reader/releases/latest)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-blue)](#download-and-install)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](#run-from-source)

# Book Reader

A desktop reader for **EPUB**, **PDF** and **Markdown** books, with notes, a reading
clock and daily reading goals. Built with Python and Qt (PySide6), and available for
Windows, Linux and macOS.

<!-- Add a screenshot: save it as docs/screenshot.png and uncomment the line below.
![Book Reader](docs/screenshot.png)
-->

## Release stats

<!-- stats:start -->
| | |
|---|---|
| **Latest stable** | [v2.0.0](https://github.com/gideonzozingao/python-ebook-reader/releases/tag/v2.0.0) (2026-10-29) |
| **Latest beta** | [v1.0.0](https://github.com/gideonzozingao/python-ebook-reader/releases/tag/v1.0.0) (2026-10-21) |
| **Releases published** | 2 |
| **Successful release runs** | 0 of 0 finished (- success) |
| **Last successful run** | - |
| **Downloads** | 14 in total: Windows 14, Linux 0, macOS 0 |

<sub>Updated automatically after each release (2026-10-29 07:40 UTC).</sub>
<!-- stats:end -->

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

```powershell
.\build.ps1                       # PyInstaller + installer -> installer\BookReader-Setup-<version>.exe
.\build.ps1 -Compiler nuitka      # compile to native code with Nuitka, then the installer
.\build.ps1 -SkipInstaller        # only the program folder dist\BookReader
.\build.ps1 -Console              # keep a console window (shows errors while testing)
.\build.ps1 -Voice                # also bundle voice dictation
.\build.ps1 -Python "py -3.12"    # Python used to create the build venv (.venv-build)
```

Or double-click `build.bat` (same options, e.g. `build.bat -Compiler nuitka`). Each build runs
the program's self-test and writes a `.sha256` next to the installer.

For Nuitka, install **Visual Studio Build Tools** with the _Desktop development with C++_
workload (including a Windows SDK); `build.ps1` loads the compiler automatically.

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

Build requirements are listed in `requirements-build.txt` (PyInstaller) and
`requirements-build-nuitka.txt` (Nuitka).

## Releasing

Releases are built and published by GitHub Actions
([`.github/workflows/release.yml`](.github/workflows/release.yml)) for Windows, Linux and macOS.
There are two channels: **stable** (`1.2.0`) and **beta** (`1.2.0-beta.3`).

1. **From the Actions tab:** _Release → Run workflow_, choose the version bump
   (patch/minor/major), the channel and the compiler. The workflow bumps `__version__`, commits
   and tags it, builds, tests and publishes.
2. **By pushing a tag** whose version is already in `book_reader/__init__.py`:
   `git tag v1.2.0 && git push origin v1.2.0`.
3. **Rolling beta:** every push to `main` publishes the next beta automatically. Set the
   repository variable `AUTO_BETA` to `false` to turn this off.

Version bumps work like this: from `1.1.1`, _patch / beta_ gives `1.1.2-beta.1`; another
_patch / beta_ gives `1.1.2-beta.2`; _patch / stable_ then releases `1.1.2`.

Installed Windows copies check the update feed of their channel
(`releases/download/update-feed/stable.json` or `beta.json`) and offer new versions. The
`update-feed` release is maintained by the workflow; do not delete it. A release needs the
Windows build to pass; Linux and macOS packages are attached when their builds pass too.

Because the workflow commits version bumps to `main`, **run `git pull` before you start working**.

Choose the compiler for automatic releases with the repository variable `BUILDER`
(`pyinstaller` or `nuitka`). Optional Windows code signing: add the repository secrets
`WINDOWS_CERT_PFX_BASE64` and `WINDOWS_CERT_PASSWORD`.

## Git workflow

The release workflow commits version bumps to `main` itself (`Release vX.Y.Z [skip ci]`), so
GitHub's `main` regularly moves ahead of your copy. Pulling **before** you work, and pulling
with rebase, keeps your history clean and avoids "rejected (non-fast-forward)" pushes.

### One-time setup

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git config --global pull.rebase true          # replay your commits on top of GitHub's
git config --global rebase.autoStash true     # also works with uncommitted changes
git config --global core.editor "code --wait" # optional: VS Code instead of Vim for messages
```

### Everyday flow (small changes straight to `main`)

```bash
git pull                              # 1. get the latest bump commits first
# ... edit, build, test (python epub_reader2.py --self-test) ...
git status                            # 2. see what changed
git add -A                            # 3. stage everything (or name files)
git commit -m "Add night mode to the reader"
git pull                              # 4. catch anything that landed meanwhile
git push                              # 5. publishes the next beta automatically
```

Every push to `main` that changes code builds and publishes a **beta**. Changes that only
touch `*.md` or `docs/` do not.

### Bigger changes (branch + pull request)

Work on a branch so unfinished work does not produce betas:

```bash
git pull
git switch -c feature/night-mode      # new branch
# ... commit as often as you like ...
git push -u origin feature/night-mode
```

Open a pull request on GitHub; merging it into `main` publishes one beta with all the changes.
Afterwards:

```bash
git switch main
git pull
git branch -d feature/night-mode
```

### Releasing a stable version

Actions → **Release** → **Run workflow** → bump `patch`, channel `stable`. Then bring the bump
commit to your copy:

```bash
git pull
```

### If a push is rejected

```bash
git pull          # rebases your commits on top of GitHub's
git push
```

If `git pull` stops with a conflict, `git status` lists the files. Fix them (remove the
`<<<<<<<`, `=======`, `>>>>>>>` markers), then `git add <file>` and `git rebase --continue`.
To give up and go back to how things were: `git rebase --abort`.

Avoid `git commit --amend` and `git push --force` on commits that are already on GitHub.

## Project layout

```
epub_reader2.py          entry point
book_reader/             the application package (core, services, ui, assets)
BookReader.spec          PyInstaller recipe (Windows, Linux, macOS)
installer.iss            Windows installer (Inno Setup)
build.ps1 / build.bat    Windows build: program + installer (PyInstaller or Nuitka)
build_exe.sh             Linux/macOS build (PyInstaller or Nuitka)
requirements-build*.txt  build requirements
scripts/bump_version.py  version bumps used by the release workflow
tools/                   Nuitka build, Linux/macOS packaging, update manifest, feed and README stats
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
