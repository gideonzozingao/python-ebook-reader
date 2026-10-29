<#
  Build Book Reader -> installer\BookReader-Setup-<version>.exe

  .\build.ps1                       full build (PyInstaller + Inno Setup)
  .\build.ps1 -Compiler nuitka      compile to native code with Nuitka (harder to reverse engineer)
  .\build.ps1 -SkipInstaller        only the program folder dist\BookReader, no installer
  .\build.ps1 -Python "py -3.12"    choose the Python used for the build venv (.venv-build)
  .\build.ps1 -Console              keep a console window in the program (shows errors)
  .\build.ps1 -Voice                also bundle voice dictation (SpeechRecognition + pyaudio)

  Both compilers produce the same dist\BookReader folder, so the installer step is identical.
  Nuitka needs a C compiler: Visual Studio Build Tools ("Desktop development with C++",
  including a Windows SDK) are loaded automatically when installed; otherwise Nuitka offers to
  download MinGW (allowed automatically here).
  Optional signing: sign_config.bat (see sign_config.example.bat) or SIGN_* environment variables.
#>
param(
    [ValidateSet("pyinstaller", "nuitka")]
    [string]$Compiler = $(if ($env:BUILDER) { $env:BUILDER } else { "pyinstaller" }),
    [switch]$SkipInstaller,
    [string]$Python = "",
    [switch]$Console,
    [switch]$Voice
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

# Runs a .bat/.cmd file and copies the environment variables it sets into this session
# (used for Visual Studio's vcvars64.bat and for sign_config.bat).
function Import-BatchEnvironment([string]$BatchFile, [string]$Arguments = "") {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) "bookreader-env-$PID.cmd"
    Set-Content -Path $tmp -Encoding ascii -Value "@call `"$BatchFile`" $Arguments >nul 2>&1`r`n@if errorlevel 1 exit /b 1`r`n@set"
    try {
        $lines = & cmd.exe /d /c $tmp
        if ($LASTEXITCODE -ne 0) { throw "$BatchFile reported an error" }
        foreach ($line in $lines) {
            if ($line -match '^([^=]+)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2] }
        }
    }
    finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

# Makes Visual Studio's C compiler (with the Windows SDK) available to Nuitka, like opening a
# "Developer PowerShell". Skipped when cl.exe is already set up (developer shell, GitHub runner).
function Use-VisualStudioCompiler {
    if (Get-Command cl.exe -ErrorAction SilentlyContinue) { return }
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { return }
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { return }
    $vcvars = Join-Path $vs "VC\Auxiliary\Build\vcvars64.bat"
    if (-not (Test-Path $vcvars)) { return }
    Write-Host "    using the Visual Studio C compiler from $vs"
    try { Import-BatchEnvironment $vcvars } catch { Write-Warning "Could not load the Visual Studio environment: $_" }
}

# ---------------------------------------------------------------------------- checks
if (-not (Test-Path "epub_reader2.py")) { throw "Run this from the folder that contains epub_reader2.py" }
if (-not (Test-Path "book_reader\assets\book_reader.ico")) { throw "book_reader\assets\book_reader.ico is missing" }

$initText = Get-Content -Raw "book_reader\__init__.py"
$m = [regex]::Match($initText, '__version__\s*=\s*"(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?)"')
if (-not $m.Success) { throw '__version__ in book_reader\__init__.py must look like "1.2.3" or "1.2.3-beta.4"' }
$version = $m.Groups[1].Value
$numVersion = ($version -split '-')[0]            # 1.2.3-beta.4 -> 1.2.3 (Windows file versions are numbers only)
Step "Book Reader $version   compiler: $Compiler"

# ---------------------------------------------------------------------------- build venv
$venv = ".venv-build"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    if (-not $Python) { $Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } else { "python" } }
    Step "Creating the build venv ($venv) with: $Python"
    # @(...) keeps this an array even for a single word like "python"; without it PowerShell
    # unwraps the one result into a plain string and $parts[0] would be its first letter, "p".
    $parts = @($Python.Split(" ", [StringSplitOptions]::RemoveEmptyEntries))
    $exeName = $parts[0]
    $extra = @($parts | Select-Object -Skip 1)
    & $exeName @extra -m venv $venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) { throw "Could not create $venv with '$Python'. Install Python 3.10+ from python.org." }
}

$reqs = if ($Compiler -eq "nuitka") { "requirements-build-nuitka.txt" } else { "requirements-build.txt" }
Step "Installing build requirements ($reqs)"
& $py -m pip install --upgrade pip --quiet --disable-pip-version-check
& $py -m pip install -r $reqs --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
if ($Voice) {
    & $py -m pip install SpeechRecognition pyaudio --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "Installing voice dictation failed" }
}

# ---------------------------------------------------------------------------- build
$env:BR_CONSOLE = if ($Console) { "1" } else { "0" }
$env:BR_ONEFILE = "0"
if (Test-Path "dist\BookReader") { Remove-Item "dist\BookReader" -Recurse -Force }

if ($Compiler -eq "nuitka") {
    Step "Nuitka (compiling to native code; this takes a while)"
    Use-VisualStudioCompiler
    & $py tools\build_nuitka.py
    if ($LASTEXITCODE -ne 0) { throw "Nuitka build failed. Scroll up for the reason." }
}
else {
    Step "PyInstaller"
    if (Test-Path build) { Remove-Item build -Recurse -Force }
    & $py -m PyInstaller BookReader.spec --noconfirm --clean --distpath dist --workpath build
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed. Scroll up for the reason." }
}

$exe = "dist\BookReader\BookReader.exe"
if (-not (Test-Path $exe)) { throw "Expected $exe was not produced" }
Write-Host "    built $exe" -ForegroundColor Green

# ---------------------------------------------------------------------------- signing (optional)
if (Test-Path "sign_config.bat") { Import-BatchEnvironment (Resolve-Path "sign_config.bat").Path }
if (Test-Path "sign_file.bat") {
    & cmd.exe /d /c sign_file.bat $exe
    if ($LASTEXITCODE -ne 0) { throw "Signing $exe failed" }
}

# ---------------------------------------------------------------------------- self-test
Step "Self-test of the packaged program"
$testHome = Join-Path ([IO.Path]::GetTempPath()) "bookreader-selftest-$PID"
$oldHome = $env:EPUB_READER_HOME
$env:EPUB_READER_HOME = $testHome
try {
    $t = Start-Process -FilePath (Resolve-Path $exe).Path -ArgumentList "--self-test" -Wait -PassThru
    Get-Content (Join-Path $testHome "selftest.txt") -ErrorAction SilentlyContinue | Write-Host
    if ($t.ExitCode -ne 0) { throw "SELF-TEST FAILED (exit code $($t.ExitCode)): a part is missing from the build." }
}
finally {
    $env:EPUB_READER_HOME = $oldHome
    Remove-Item $testHome -Recurse -Force -ErrorAction SilentlyContinue
}

if ($SkipInstaller) {
    Write-Host "==> Done: $exe   (no installer, -SkipInstaller)" -ForegroundColor Green
    return
}

# ---------------------------------------------------------------------------- installer
Step "Inno Setup"
$candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source }
if (-not $iscc) {
    Write-Warning "Inno Setup 6 not found. Install it with:  winget install JRSoftware.InnoSetup"
    Write-Warning "The program itself is ready in dist\BookReader\ (you can run BookReader.exe directly)."
    exit 1
}

$isccArgs = @("/Qp", "/DAppVersion=$version", "/DAppNumVersion=$numVersion")
if ($env:SIGN_METHOD) {
    Write-Host "    signing the installer and uninstaller too"
    $isccArgs += "/DSign=1"
    $isccArgs += ('/Sbookreader=$q' + (Join-Path $PWD "sign_file.bat") + '$q $f')
}
& $iscc @isccArgs installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed. Scroll up for the reason." }

$setup = "installer\BookReader-Setup-$version.exe"
if (-not (Test-Path $setup)) { throw "Expected $setup was not produced" }
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $setup -Leaf)" | Set-Content "$setup.sha256" -Encoding ascii -NoNewline
Write-Host "==> Done: $setup" -ForegroundColor Green
Write-Host "    sha256 $hash"