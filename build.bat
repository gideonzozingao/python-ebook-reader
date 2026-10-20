@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem  Builds Book Reader into a Windows program with PyInstaller.
rem    build_exe.bat            folder build   -> dist\BookReader\BookReader.exe  (recommended)
rem    build_exe.bat /onefile   single file    -> dist\BookReader.exe  (slower to start)
rem    build_exe.bat /console   keeps a console window (shows errors while testing)
rem    build_exe.bat /voice     also bundles voice dictation (SpeechRecognition + pyaudio)
rem ---------------------------------------------------------------------------
set "VENV=C:\venv\epub"
set "BR_ONEFILE=0"
set "BR_CONSOLE=0"
set "VOICE=0"
for %%A in (%*) do (
    if /i "%%A"=="/onefile" set "BR_ONEFILE=1"
    if /i "%%A"=="/console" set "BR_CONSOLE=1"
    if /i "%%A"=="/voice" set "VOICE=1"
)

if not exist "epub_reader2.py" (
    echo Run this from the folder that contains epub_reader2.py and BookReader.spec
    pause & exit /b 1
)
if not exist "book_reader\assets\book_reader.ico" (
    echo The icon is missing. Re-extract the whole zip into this folder.
    pause & exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    set "PY="
    where py >nul 2>&1 && set "PY=py -3"
    if not defined PY where python >nul 2>&1 && set "PY=python"
    if not defined PY (
        echo Python 3.10 or newer was not found. Install it from python.org first.
        pause & exit /b 1
    )
    echo Creating virtual environment in %VENV% ...
    %PY% -m venv "%VENV%" || ( echo Could not create the environment. & pause & exit /b 1 )
)
set "PYX=%VENV%\Scripts\python.exe"

echo.
echo Installing build requirements ...
"%PYX%" -m pip install --upgrade pip
"%PYX%" -m pip install --upgrade -r requirements.txt pyinstaller || ( echo Install failed. & pause & exit /b 1 )
if "%VOICE%"=="1" "%PYX%" -m pip install --upgrade SpeechRecognition pyaudio

echo.
echo Building. This takes a few minutes ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PYX%" -m PyInstaller --noconfirm --clean BookReader.spec
if errorlevel 1 ( echo. & echo BUILD FAILED. Scroll up for the reason. & pause & exit /b 1 )

if "%BR_ONEFILE%"=="1" ( set "EXE=dist\BookReader.exe" ) else ( set "EXE=dist\BookReader\BookReader.exe" )
echo.
echo Checking the packaged program (self-test) ...
"%EXE%" --self-test
if errorlevel 1 (
    echo.
    echo SELF-TEST FAILED: a dependency is missing from the build. Send me the lines above.
    pause & exit /b 1
)
echo.
echo Done:  %CD%\%EXE%
echo Your books and notes stay in %USERPROFILE%\.epub_reader and are shared with the Python version.
explorer "dist"
pause
