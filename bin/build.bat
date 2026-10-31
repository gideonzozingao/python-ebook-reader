@echo off
rem  bin\build.bat                          PyInstaller + installer
rem  bin\build.bat -Compiler nuitka         native compile (Nuitka) + installer
rem  bin\build.bat -SkipInstaller           program folder only
rem  bin\build.bat -Console                 keep a console window (debugging)
rem  Double-clickable wrapper around build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
if errorlevel 1 pause
