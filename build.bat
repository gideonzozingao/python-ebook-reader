@echo off
rem  build.bat                          PyInstaller + installer
rem  build.bat -Compiler nuitka         native compile (Nuitka) + installer
rem  build.bat -SkipInstaller           program folder only
rem  build.bat -Console                 keep a console window (debugging)
rem  Double-clickable wrapper around build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
if errorlevel 1 pause
