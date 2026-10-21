@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ---------------------------------------------------------------------------
echo  Builds the Zuqongsoft E-Book Reader installer:
echo    installer\Zuqongsoft-EBook-Reader-Setup.exe
echo.
echo    build_installer.bat              build the app, then the installer
echo    build_installer.bat /skipbuild   reuse the existing dist\Zuqongsoft-EBook-Reader folder
echo ---------------------------------------------------------------------------
set "APPVER=1.0"
set "SETUP=installer\Zuqongsoft-EBook-Reader-Setup.exe"
set "APPEXE=dist\Zuqongsoft-EBook-Reader\Zuqongsoft-EBook-Reader.exe"
set "SKIPBUILD=0"
for %%A in (%*) do (
    if /i "%%A"=="/skipbuild" set "SKIPBUILD=1"
)

if not exist "installer.iss" (
    echo installer.iss was not found in this folder.
    goto fail
)

if "%SKIPBUILD%"=="1" goto findiscc
echo.
echo Step 1 of 2: building the program ...
call build_exe.bat /nopause
if errorlevel 1 goto fail

:findiscc
if not exist "%APPEXE%" (
    echo %APPEXE% is missing. Run without /skipbuild.
    goto fail
)

echo.
echo Step 2 of 2: looking for Inno Setup ...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"

if not defined ISCC (
    echo.
    echo Inno Setup 6 was not found. Install it, then run this file again:
    echo    winget install --id JRSoftware.InnoSetup -e
    echo or download it from https://jrsoftware.org/isdl.php
    goto fail
)
echo Using: %ISCC%

if exist "%SETUP%" del /q "%SETUP%"
"%ISCC%" /Qp /DAppVersion=%APPVER% "installer.iss"
if errorlevel 1 (
    echo.
    echo INSTALLER BUILD FAILED. Scroll up for the Inno Setup message.
    goto fail
)
if not exist "%SETUP%" (
    echo The installer file was not created.
    goto fail
)

echo.
echo Done:  %CD%\%SETUP%
echo Give this single file to anyone. It installs the fast folder version.
explorer "installer"
pause
exit /b 0

:fail
echo.
echo Installer was not built.
pause
exit /b 1