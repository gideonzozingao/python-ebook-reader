# Building Book Reader into a Windows program

1. Extract the whole zip into your project folder (replace everything, including `book_reader`).
2. Double-click **build_exe.bat** (or run it from PowerShell in this folder).
   - It reuses/creates `C:\venv\epub`, installs the requirements and PyInstaller, builds, then
     runs a self-test on the finished program.
   - Result: `dist\BookReader\BookReader.exe` (keep the whole `BookReader` folder together).
3. Optional switches: `build_exe.bat /onefile` (single .exe, starts slower), `/console`
   (shows a console for debugging), `/voice` (bundle voice dictation packages).
4. One-file installer (recommended for sharing):
   - Install Inno Setup once:  `winget install JRSoftware.InnoSetup`
   - Double-click **build_installer.bat** (or `build_installer.bat 1.2.0` to set the version).
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

1. Get a certificate (see the table below) or make a test one with `make_test_cert.ps1`.
2. Copy `sign_config.example.bat` to `sign_config.bat` and enable ONE method in it.
3. Run `build_exe.bat` / `build_installer.bat` as usual. They now sign `BookReader.exe`, the
   installer and the uninstaller automatically. Without `sign_config.bat` they build unsigned.
4. Check: `Get-AuthenticodeSignature .\dist\BookReader\BookReader.exe | Format-List`
   (Status should be `Valid`, and the timestamp is part of the signature).

| Situation | Use |
|---|---|
| Public release, Windows users you do not know | An **OV code-signing certificate** from a public CA (DigiCert, Sectigo, SSL.com, Certum ...). Since June 2023 the private key must stay on a hardware token or CA cloud signer, so you cannot export a .pfx; use method A (thumbprint/subject) or D (the CA's signing tool). Certificates last at most about 15 months. |
| US/Canada individual or US/Canada/EU/UK organisation | **Azure Artifact Signing** (formerly Trusted Signing), about US$10/month, method C. |
| Only your own PCs or an organisation you control | A **self-signed or internal-CA certificate** (`make_test_cert.ps1`, method B), trusted on those PCs through Group Policy (Trusted Publishers + Trusted Root). Free, but other PCs will still warn. |

Keep keys and passwords out of the project folder and out of version control (`.gitignore`
already excludes `sign_config.bat` and `*.pfx`). Sign after building, never before.
