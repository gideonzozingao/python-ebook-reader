@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ---------------------------------------------------------------------------
echo  Builds Zuqongsoft E-Book Reader into a Windows program with PyInstaller.
echo    build_exe.bat            folder build   -^> dist\Zuqongsoft-EBook-Reader\Zuqongsoft-EBook-Reader.exe  (recommended)
echo    build_exe.bat /onefile   single file    -^> dist\Zuqongsoft-EBook-Reader.exe  (slower to start)
echo    build_exe.bat /console   keeps a console window (shows errors while testing)
echo    build_exe.bat /voice     also bundles voice dictation (SpeechRecognition + pyaudio)
echo    build_exe.bat /nopause   no pause or Explorer at the end (used by build_installer.bat)
echo ---------------------------------------------------------------------------
set "VENV=C:\venv\epub"
set "BR_ONEFILE=0"
set "BR_CONSOLE=0"
set "VOICE=0"
set "NOPAUSE=0"
set "PAUSE_CMD=pause"
for %%A in (%*) do (
    if /i "%%A"=="/onefile" set "BR_ONEFILE=1"
    if /i "%%A"=="/console" set "BR_CONSOLE=1"
    if /i "%%A"=="/voice" set "VOICE=1"
    if /i "%%A"=="/nopause" set "NOPAUSE=1"
)
if "%NOPAUSE%"=="1" set "PAUSE_CMD=echo."

if not exist "epub_reader2.py" (
    echo Run this from the folder that contains epub_reader2.py and BookReader.spec
    %PAUSE_CMD%
    exit /b 1
)
if not exist "BookReader.spec" (
    echo BookReader.spec was not found in this folder.
    %PAUSE_CMD%
    exit /b 1
)
if not exist "book_reader\assets\book_reader.ico" (
    echo The icon is missing. Re-extract the whole zip into this folder.
    %PAUSE_CMD%
    exit /b 1
)

if exist "%VENV%\Scripts\python.exe" goto havevenv
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto nopython
echo Creating virtual environment in %VENV% ...
%PY% -m venv "%VENV%"
if errorlevel 1 goto venvfail
:havevenv
set "PYX=%VENV%\Scripts\python.exe"

echo.
echo Installing build requirements ...
"%PYX%" -m pip install --upgrade pip
"%PYX%" -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Install failed.
    %PAUSE_CMD%
    exit /b 1
)
if "%VOICE%"=="1" "%PYX%" -m pip install --upgrade SpeechRecognition pyaudio

echo.
echo Building. This takes a few minutes ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PYX%" -m PyInstaller --noconfirm --clean BookReader.spec
if errorlevel 1 (
    echo.
    echo BUILD FAILED. Scroll up for the reason.
    %PAUSE_CMD%
    exit /b 1
)

if "%BR_ONEFILE%"=="1" ( set "EXE=dist\Zuqongsoft-EBook-Reader.exe" ) else ( set "EXE=dist\Zuqongsoft-EBook-Reader\Zuqongsoft-EBook-Reader.exe" )
echo.
echo Checking the packaged program - self-test ...
"%EXE%" --self-test
if errorlevel 1 (
    echo.
    echo SELF-TEST FAILED: a dependency is missing from the build. Send me the lines above.
    %PAUSE_CMD%
    exit /b 1
)
echo.
echo Done:  %CD%\%EXE%
echo Your books and notes stay in %USERPROFILE%\.epub_reader and are shared with the Python version.
if "%NOPAUSE%"=="1" exit /b 0
explorer "dist"
pause
exit /b 0

:nopython
echo Python 3.10 or newer was not found. Install it from python.org first.
%PAUSE_CMD%
exit /b 1

:venvfail
echo Could not create the environment.
%PAUSE_CMD%
exit /b 1