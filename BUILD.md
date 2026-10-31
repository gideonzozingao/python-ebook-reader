# Building Book Reader into a Windows program

All build scripts live in the **`bin`** folder. They can be started from anywhere (double-click,
or `bin\build_exe.bat` from the project folder): each one switches to the project folder first.

1. Extract the whole zip into your project folder (replace everything, including `book_reader`).
2. Double-click **bin\build_exe.bat** (or run `bin\build_exe.bat` from the project folder).
   - It reuses/creates `C:\venv\epub`, installs the requirements and PyInstaller, builds, then
     runs a self-test on the finished program.
   - Result: `dist\BookReader\BookReader.exe` (keep the whole `BookReader` folder together).
3. Optional switches: `bin\build_exe.bat /onefile` (single .exe, starts slower), `/console`
   (shows a console for debugging), `/voice` (bundle voice dictation packages).
4. One-file installer (recommended for sharing):
   - Install Inno Setup once:  `winget install JRSoftware.InnoSetup`
   - Double-click **bin\build_installer.bat** (or `bin\build_installer.bat 1.2.0` to set the version).
   - Result: `installer\BookReader-Setup-1.0.0.exe`. It installs the fast folder build, adds a
     Start-menu entry (and an optional desktop icon), an uninstaller, and "Open with" entries
     for .epub, .pdf and .md. Running a newer installer upgrades in place.
   - Add `/skipbuild` to reuse the existing `dist\BookReader` folder.

Your library, notes and settings are not inside the program. They stay in
`%USERPROFILE%\.epub_reader` (and the registry for settings), so updating or reinstalling
never loses them, and the Python version and the .exe share the same library.

Check a build at any time with `BookReader.exe --self-test` (writes selftest.txt in the
library folder). If a line says FAIL, send it to me.

Windows SmartScreen / antivirus may warn about an unsigned program the first time. The folder
build triggers this less than /onefile. A code-signing certificate removes the warning.

## Digital signature (code signing)

Signing proves who published the program and that it was not changed after you built it. It is
optional: unsigned builds work, but Windows SmartScreen and antivirus warn more often.

1. Get a certificate (see the table below) or make a test one with `bin\make_test_cert.ps1`.
2. Copy `bin\sign_config.example.bat` to `bin\sign_config.bat` and enable ONE method in it.
   (A `sign_config.bat` in the project folder, where it used to go, still works.)
3. Run `bin\build_exe.bat` / `bin\build_installer.bat` (or `bin\build.ps1`) as usual. They now sign `BookReader.exe`, the
   installer and the uninstaller automatically. Without `sign_config.bat` they build unsigned.
4. Check: `Get-AuthenticodeSignature .\dist\BookReader\BookReader.exe | Format-List`
   (Status should be `Valid`, and the timestamp is part of the signature).

| Situation | Use |
|---|---|
| Public release, Windows users you do not know | An **OV code-signing certificate** from a public CA (DigiCert, Sectigo, SSL.com, Certum ...). Since June 2023 the private key must stay on a hardware token or CA cloud signer, so you cannot export a .pfx; use method A (thumbprint/subject) or D (the CA's signing tool). Certificates last at most about 15 months. |
| US/Canada individual or US/Canada/EU/UK organisation | **Azure Artifact Signing** (formerly Trusted Signing), about US$10/month, method C. |
| Only your own PCs or an organisation you control | A **self-signed or internal-CA certificate** (`bin\make_test_cert.ps1`, method B), trusted on those PCs through Group Policy (Trusted Publishers + Trusted Root). Free, but other PCs will still warn. |

Keep keys and passwords out of the project folder and out of version control (`.gitignore`
already excludes `sign_config.bat` and `*.pfx`). Sign after building, never before.

## Publishing updates (auto-update)

Book Reader checks for a newer version about 5 seconds after start-up (at most once a day, and
only if "Check for updates automatically" is ticked in the library's **⋯** menu), or when you pick
**⋯ → Check for updates…**. If one exists, a dialog shows what is new. **Install and restart**
downloads the installer, verifies its SHA-256 checksum, closes the app and runs the installer
silently; the installer upgrades in place and starts the new version. Your library is untouched.
It only updates the *installed* Windows program; a run from source just opens the download page.

**One-time setup.** Set `UPDATE_URL` in `book_reader/constants.py` (empty = feature off) to one of:

* **A manifest** you host anywhere over HTTPS, e.g. `https://example.com/book-reader/latest.json`.
* **GitHub Releases:** `https://api.github.com/repos/<owner>/<repo>/releases/latest`.

**Every release.**

1. Bump `__version__` in `book_reader/__init__.py` (e.g. `"1.2.0"`).
2. Run `bin\build_installer.bat` (it takes the version from that file) → `installer\BookReader-Setup-1.2.0.exe`.
3. Publish it:
   * *Manifest:* `python tools\make_manifest.py installer\BookReader-Setup-1.2.0.exe --url https://example.com/book-reader/BookReader-Setup-1.2.0.exe --notes "What is new"`,
     then upload the installer **and** `installer\latest.json` to your server (upload `latest.json` last).
   * *GitHub:* create a release tagged `v1.2.0`, attach the installer. Its checksum is read
     from GitHub's asset digest, or attach the `.sha256` file that `make_manifest.py` also writes.
     Mark it as a normal release (drafts and pre-releases are ignored).

Notes: only HTTPS addresses are accepted; an installer whose checksum does not match is deleted
and never run; releases tagged like `1.3.0-beta1` are ignored. Signing the installer
(see "Digital signature" below) is still recommended so Windows SmartScreen trusts it.

## Automated releases (GitHub Actions)

`.github/workflows/release.yml` builds and publishes a release for you, using the same scripts
as above (`bin\build.ps1` on Windows, `bin/build_exe.sh` + `bin/package_*.sh` on Linux and macOS).

**To release with a tag:** set `__version__` in `book_reader/__init__.py`, commit it to `main`,
tag that commit and push both:

    git commit -am "Release v1.2.0"
    git tag v1.2.0
    git push origin main v1.2.0

Or use Actions -> *Release* -> *Run workflow* from the branch `main`, which bumps the version,
commits and tags for you.

Before anything is built, the workflow checks (and stops with a clear message otherwise) that:

* the tag points at a commit that is on `main`, and equals `v` + `__version__`;
* no published release uses that tag yet (a leftover draft from a failed run is fine);
* the version is higher than the latest release of its channel, in semantic-version order
  (`2.2.0-beta.3` < `2.2.0` < `2.2.1-beta.1`): a stable version must be higher than the
  latest stable release, a beta higher than every release. See `scripts/release_guard.py`.

Pushing the release commit to `main` does not make a rolling beta: a push that sets a new
stable `__version__` without its tag, or pushes an already tagged commit, is left alone.

**To try a build without releasing:** Actions tab -> *Release* -> *Run workflow*. The installer is
kept for 30 days under the run's *Artifacts*; nothing is published.

What it does, in order:

1. Checks the tag against `__version__`.
2. Points the app's `UPDATE_URL` at this repository's latest release (in the build only, nothing is
   committed). Using other hosting? Set a repository **variable** named `UPDATE_URL`
   (Settings -> Secrets and variables -> Actions -> Variables) to your `latest.json` address.
3. Builds with Python 3.12, signs if a certificate is configured (below), runs the program's
   `--self-test`, and builds the installer.
4. Smoke-tests the installer: silent install, then the installed program's `--self-test`; then a
   silent upgrade with the updater's switches to check that the app relaunches.
5. (Separate job, the only one with write access.) Writes the release notes from your commits and
   pull requests, the `.sha256` checksum and `latest.json`, and publishes the release.

The installed app then finds new versions at
`https://github.com/<owner>/<repo>/releases/latest/download/latest.json`.
This works for **public** repositories. A private repository's releases cannot be read without a
login, so the build leaves updates off and warns you; host `latest.json` somewhere public and set
the `UPDATE_URL` variable instead.

**Code signing (optional).** Add two repository secrets and the build signs `BookReader.exe`, the
installer and the uninstaller through your existing `bin\sign_file.bat` (`SIGN_METHOD=pfx`):

* `WINDOWS_CERT_PFX_BASE64` - the .pfx file as text: in PowerShell run
  `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cert.pfx")) | Set-Clipboard`
* `WINDOWS_CERT_PASSWORD` - its password

Without them the build is unsigned (as it is on your PC without `sign_config.bat`). Note that public
certificate authorities no longer issue exportable .pfx files, so this path is for self-signed or
internal-CA certificates, which Windows SmartScreen does not trust. For public trust use a cloud
signing service (e.g. Azure Artifact Signing, `SIGN_METHOD=azure`), which needs extra steps in the
workflow.

The action versions in the workflow (`actions/checkout@v7`, ...) are current major versions. Enable
Dependabot for "github-actions" to be told when new ones are out.
