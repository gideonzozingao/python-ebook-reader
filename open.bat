@echo off
setlocal EnableExtensions

rem ================== SETTINGS ==================
set "APP_DIR=C:\Users\gzozingao\Documents\Learning\epub-reader"
set "VENV=C:\venv\epub"
set "APP=epub_reader2.py"
set "PACKAGES=PySide6-Essentials beautifulsoup4 pymupdf markdown"
rem ===============================================

cd /d "%APP_DIR%" || (
    echo Folder not found: %APP_DIR%
    pause
    exit /b 1
)

if not exist "%APP%" (
    echo %APP% was not found in %APP_DIR%
    pause
    exit /b 1
)
if not exist "book_reader\__init__.py" (
    echo The book_reader folder must sit next to %APP%.
    echo Unzip book_reader_app.zip into %APP_DIR%
    pause
    exit /b 1
)

rem ---- 1. Make sure the virtual environment exists ----
if not exist "%VENV%\Scripts\python.exe" (
    set "PY="
    where py >nul 2>&1 && set "PY=py -3"
    if not defined PY where python >nul 2>&1 && set "PY=python"
    if not defined PY (
        echo Python was not found. Install Python 3.10 or newer from python.org
        echo and tick "Add python.exe to PATH" in the installer.
        pause
        exit /b 1
    )
    echo Creating virtual environment in %VENV% ...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

rem ---- 2. Install packages only when something is missing (or on /update) ----
set "NEED_INSTALL="
if /i "%~1"=="/update" set "NEED_INSTALL=1"
if not defined NEED_INSTALL (
    "%VENV%\Scripts\python.exe" -c "import importlib.util as u,sys; sys.exit(0 if all(u.find_spec(m) for m in ('PySide6','bs4','markdown','pymupdf')) else 1)" >nul 2>&1
    if errorlevel 1 set "NEED_INSTALL=1"
)

if defined NEED_INSTALL (
    echo.
    echo Installing packages. This only happens on the first run
    echo and can take a few minutes. Please wait ...
    echo.
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
    if exist "requirements.txt" (
        "%VENV%\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
    ) else (
        "%VENV%\Scripts\python.exe" -m pip install --upgrade %PACKAGES%
    )
    if errorlevel 1 (
        echo.
        echo Package installation failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

rem ---- 3. Start the app ----
if /i "%~1"=="/debug" (
    rem Console mode: shows error messages if the app crashes
    "%VENV%\Scripts\python.exe" "%APP%"
    pause
    exit /b 0
)

start "" "%VENV%\Scripts\pythonw.exe" "%APP%" %*
exit /b 0