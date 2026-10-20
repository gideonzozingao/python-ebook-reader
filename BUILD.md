# Building Book Reader into a Windows program

1. Extract the whole zip into your project folder (replace everything, including `book_reader`).
2. Double-click **build_exe.bat** (or run it from PowerShell in this folder).
   - It reuses/creates `C:\venv\epub`, installs the requirements and PyInstaller, builds, then
     runs a self-test on the finished program.
   - Result: `dist\BookReader\BookReader.exe` (keep the whole `BookReader` folder together).
3. Optional switches: `build_exe.bat /onefile` (single .exe, starts slower), `/console`
   (shows a console for debugging), `/voice` (bundle voice dictation packages).
4. Optional installer: install Inno Setup, open `installer.iss`, press Compile
   -> `installer\BookReader-Setup.exe`.

Your library, notes and settings are not inside the program. They stay in
`%USERPROFILE%\.epub_reader` (and the registry for settings), so updating or reinstalling
never loses them, and the Python version and the .exe share the same library.

Check a build at any time with `BookReader.exe --self-test` (writes selftest.txt in the
library folder). If a line says FAIL, send it to me.

Windows SmartScreen / antivirus may warn about an unsigned program the first time. The folder
build triggers this less than /onefile. A code-signing certificate removes the warning.
