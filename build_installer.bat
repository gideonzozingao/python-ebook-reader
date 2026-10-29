@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PAUSE=pause"

rem ---------------------------------------------------------------------------
rem  Builds BookReader-Setup-<version>.exe  (one installer file you can hand out).
rem    build_installer.bat                 version from book_reader\__init__.py
rem    build_installer.bat 1.2.0           choose the version number
rem    build_installer.bat 1.2.0 /nuitka   compile the program with Nuitka (machine code)
rem                                        instead of PyInstaller; takes much longer
rem    build_installer.bat 1.2.0 /skipbuild   reuse the existing dist\BookReader folder
rem    build_installer.bat 1.2.0 /nopause     do not wait for a key or open Explorer (used by the GitHub workflow)
rem  The build tool can also come from the environment variable BUILDER=pyinstaller|nuitka.
rem  Needs Inno Setup 6 (free):  winget install JRSoftware.InnoSetup
rem ---------------------------------------------------------------------------
set "VER=1.0.0"
rem  The default version is the one in book_reader\__init__.py (so the app and installer agree).
for /f "tokens=3 delims= " %%V in ('findstr /B /C:"__version__" "book_reader\__init__.py"') do set "VER=%%~V"
set "SKIP=0"
set "BUILDOPT="
for %%A in (%*) do (
    if /i "%%A"=="/skipbuild" (
        set "SKIP=1"
    ) else if /i "%%A"=="/nopause" (
        set "PAUSE=echo."
    ) else if /i "%%A"=="/nuitka" (
        set "BUILDOPT=/nuitka"
    ) else if /i "%%A"=="/pyinstaller" (
        set "BUILDOPT=/pyinstaller"
    ) else (
        set "VER=%%A"
    )
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup 6 was not found.
    echo Install it with:   winget install JRSoftware.InnoSetup
    echo or download it from https://jrsoftware.org/isdl.php  then run this file again.
    %PAUSE%
    exit /b 1
)

if "%SKIP%"=="0" (
    echo Step 1/2: building the program ...
    call build_exe.bat /nopause %BUILDOPT%
    if errorlevel 1 ( echo The program build failed. & %PAUSE% & exit /b 1 )
)
if not exist "dist\BookReader\BookReader.exe" (
    echo dist\BookReader\BookReader.exe is missing. Run build_exe.bat first.
    %PAUSE%
    exit /b 1
)

echo.
echo Step 2/2: creating the installer (version %VER%) ...
set "SIGNARGS="
if exist "sign_config.bat" call "sign_config.bat"
if defined SIGN_METHOD (
    echo Signing is configured: the installer and uninstaller will be signed too.
    set SIGNARGS=/DSign=1 "/Sbookreader=$q%CD%\sign_file.bat$q $f"
)
"%ISCC%" /Qp /DAppVersion=%VER% %SIGNARGS% installer.iss
if errorlevel 1 ( echo. & echo INSTALLER BUILD FAILED. Scroll up for the reason. & %PAUSE% & exit /b 1 )

echo.
echo Done:  %CD%\installer\BookReader-Setup-%VER%.exe
if /i not "%PAUSE%"=="echo." explorer "installer"
%PAUSE%
exit /b 0