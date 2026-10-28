@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem  Digitally signs ONE file using the method set in sign_config.bat.
rem  Usage:  sign_file.bat "path\to\file.exe"
rem  If signing is not configured the file is left unsigned and the build continues.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
if exist "sign_config.bat" call "sign_config.bat"
if "%~1"=="" (
    echo Usage: sign_file.bat "file"
    exit /b 2
)
if not defined SIGN_METHOD (
    echo [sign] Not configured - "%~nx1" stays unsigned. See BUILD.md, section Digital signature.
    exit /b 0
)
if not defined SIGN_TIMESTAMP set "SIGN_TIMESTAMP=http://timestamp.digicert.com"

rem ---- find signtool.exe (Windows SDK) unless SIGNTOOL points to it ----
set "ST=%SIGNTOOL%"
set "KITS=%ProgramFiles(x86)%\Windows Kits\10\bin"
if not defined ST (
    for /f "delims=" %%F in ('dir /b /s "%KITS%\signtool.exe" 2^>nul ^| findstr /i "\\x64\\"') do set "ST=%%F"
)
if not defined ST (
    echo [sign] signtool.exe was not found. Install the Windows SDK:
    echo        winget install Microsoft.WindowsSDK.10.0.22621
    echo        or set SIGNTOOL=full path of signtool.exe in sign_config.bat
    exit /b 1
)

echo [sign] Signing "%~nx1" with method "%SIGN_METHOD%" ...
if /i "%SIGN_METHOD%"=="thumbprint" (
    "%ST%" sign /fd SHA256 /sha1 "%SIGN_THUMBPRINT%" /tr "%SIGN_TIMESTAMP%" /td SHA256 /d "Book Reader" "%~1"
) else if /i "%SIGN_METHOD%"=="subject" (
    "%ST%" sign /fd SHA256 /n "%SIGN_SUBJECT%" /tr "%SIGN_TIMESTAMP%" /td SHA256 /d "Book Reader" "%~1"
) else if /i "%SIGN_METHOD%"=="pfx" (
    "%ST%" sign /fd SHA256 /f "%SIGN_PFX%" /p "%SIGN_PASSWORD%" /tr "%SIGN_TIMESTAMP%" /td SHA256 /d "Book Reader" "%~1"
) else if /i "%SIGN_METHOD%"=="azure" (
    "%ST%" sign /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 /dlib "%SIGN_AZURE_DLIB%" /dmdf "%SIGN_AZURE_JSON%" "%~1"
) else if /i "%SIGN_METHOD%"=="custom" (
    call %SIGN_COMMAND% "%~1"
) else (
    echo [sign] Unknown SIGN_METHOD "%SIGN_METHOD%". Use thumbprint, subject, pfx, azure or custom.
    exit /b 2
)
if errorlevel 1 (
    echo [sign] SIGNING FAILED for "%~nx1".
    exit /b 1
)

"%ST%" verify /pa "%~1" >nul 2>&1 && ( echo [sign] OK - signed and trusted by this PC. ) || ( echo [sign] Signed. This PC does not trust the certificate yet, which is normal for a self-signed test certificate. )
exit /b 0
