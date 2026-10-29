@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PAUSE=pause"

rem ---------------------------------------------------------------------------
rem  Builds Book Reader into a Windows program.
rem    build_exe.bat            folder build   -> dist\BookReader\BookReader.exe  (recommended)
rem    build_exe.bat /nuitka    compile with Nuitka (Python -> C -> machine code) instead of
rem                             PyInstaller. Same result folder; the build takes much longer
rem                             (often 10-30 minutes) and needs a C compiler: Visual Studio
rem                             Build Tools if installed, otherwise Nuitka offers to download one.
rem    build_exe.bat /onefile   single file    -> dist\BookReader.exe  (slower to start;
rem                             PyInstaller only)
rem    build_exe.bat /console   keeps a console window (shows errors while testing)
rem    build_exe.bat /voice     also bundles voice dictation (SpeechRecognition + pyaudio)
rem    build_exe.bat /nopause   do not wait for a key at the end (used by build_installer.bat)
rem  The build tool can also be chosen with the environment variable BUILDER=pyinstaller|nuitka
rem  (the GitHub workflow does this); /nuitka or /pyinstaller on the command line wins.
rem ---------------------------------------------------------------------------
set "VENV=C:\venv\epub"
set "BR_ONEFILE=0"
set "BR_CONSOLE=0"
set "VOICE=0"
if not defined BUILDER set "BUILDER=pyinstaller"
for %%A in (%*) do (
    if /i "%%A"=="/onefile" set "BR_ONEFILE=1"
    if /i "%%A"=="/console" set "BR_CONSOLE=1"
    if /i "%%A"=="/voice" set "VOICE=1"
    if /i "%%A"=="/nopause" set "PAUSE=echo."
    if /i "%%A"=="/nuitka" set "BUILDER=nuitka"
    if /i "%%A"=="/pyinstaller" set "BUILDER=pyinstaller"
)
if /i not "%BUILDER%"=="pyinstaller" if /i not "%BUILDER%"=="nuitka" (
    echo BUILDER must be pyinstaller or nuitka, got: %BUILDER%
    %PAUSE% & exit /b 1
)
if /i "%BUILDER%"=="nuitka" if "%BR_ONEFILE%"=="1" (
    echo Note: /onefile is a PyInstaller option; the Nuitka build makes the folder version.
    set "BR_ONEFILE=0"
)

if not exist "epub_reader2.py" (
    echo Run this from the folder that contains epub_reader2.py and BookReader.spec
    %PAUSE% & exit /b 1
)
if not exist "book_reader\assets\book_reader.ico" (
    echo The icon is missing. Re-extract the whole zip into this folder.
    %PAUSE% & exit /b 1
)

rem  Create the build environment if needed. Plain lines with goto instead of one ( ... ) block:
rem  inside a block, %PY% would be read before "set PY=" runs and come out empty.
if exist "%VENV%\Scripts\python.exe" goto :have_venv
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :make_venv
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :make_venv
echo Python 3.10 or newer was not found. Install it from python.org first.
%PAUSE%
exit /b 1

:make_venv
echo Creating virtual environment in %VENV% with: %PY%
%PY% -m venv "%VENV%"
if errorlevel 1 ( echo Could not create the environment. & %PAUSE% & exit /b 1 )

:have_venv
set "PYX=%VENV%\Scripts\python.exe"

echo.
echo Installing build requirements (build tool: %BUILDER%) ...
"%PYX%" -m pip install --upgrade pip
"%PYX%" -m pip install --upgrade -r requirements.txt %BUILDER% || ( echo Install failed. & %PAUSE% & exit /b 1 )
if "%VOICE%"=="1" "%PYX%" -m pip install --upgrade SpeechRecognition pyaudio

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.
if /i "%BUILDER%"=="nuitka" goto :build_nuitka

echo Building with PyInstaller. This takes a few minutes ...
"%PYX%" -m PyInstaller --noconfirm --clean BookReader.spec
if errorlevel 1 ( echo. & echo BUILD FAILED. Scroll up for the reason. & %PAUSE% & exit /b 1 )
goto :built

:build_nuitka
rem  Load the Visual Studio C compiler environment (compiler + Windows SDK paths), the same as
rem  opening a "Developer PowerShell", so Nuitka uses MSVC instead of falling back to MinGW.
rem  Skipped if the compiler is already set up (developer shell, GitHub runner).
where cl >nul 2>&1 && goto :nuitka_compile
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto :nuitka_compile
set "VSDIR="
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%I"
if not defined VSDIR goto :nuitka_compile
if not exist "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" goto :nuitka_compile
echo Using the Visual Studio C compiler from "%VSDIR%"
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul

:nuitka_compile
echo Compiling with Nuitka. This takes a while (often 10-30 minutes) ...
"%PYX%" tools\build_nuitka.py
if errorlevel 1 ( echo. & echo BUILD FAILED. Scroll up for the reason. & %PAUSE% & exit /b 1 )

:built
if "%BR_ONEFILE%"=="1" ( set "EXE=dist\BookReader.exe" ) else ( set "EXE=dist\BookReader\BookReader.exe" )
if not exist "%EXE%" ( echo. & echo BUILD FAILED: %EXE% was not produced. & %PAUSE% & exit /b 1 )
echo.
call sign_file.bat "%EXE%"
if errorlevel 1 ( echo. & echo SIGNING FAILED. & %PAUSE% & exit /b 1 )
echo.
echo Checking the packaged program (self-test) ...
"%EXE%" --self-test
if errorlevel 1 (
    echo.
    echo SELF-TEST FAILED: a dependency is missing from the build. Send me the lines above.
    %PAUSE% & exit /b 1
)
echo.
echo Done:  %CD%\%EXE%   (built with %BUILDER%)
echo Your books and notes stay in %USERPROFILE%\.epub_reader and are shared with the Python version.
if /i not "%PAUSE%"=="echo." explorer "dist"
%PAUSE%
exit /b 0