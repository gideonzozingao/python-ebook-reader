; Optional: turns the folder build into a normal Windows installer.
; 1) Run build_exe.bat   2) Install Inno Setup (jrsoftware.org)   3) Open this file and press Compile.
[Setup]
AppName=Book Reader
AppVersion=1.0
AppPublisher=Book Reader
DefaultDirName={autopf}\Book Reader
DefaultGroupName=Book Reader
OutputBaseFilename=BookReader-Setup
OutputDir=installer
SetupIconFile=book_reader\assets\book_reader.ico
UninstallDisplayIcon={app}\BookReader.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\BookReader\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Book Reader"; Filename: "{app}\BookReader.exe"
Name: "{autodesktop}\Book Reader"; Filename: "{app}\BookReader.exe"; Tasks: desktopicon

[Registry]
; Adds Book Reader to the "Open with" list for books (does not change your default apps).
Root: HKCU; Subkey: "Software\Classes\Applications\BookReader.exe\shell\open\command"; ValueType: string; ValueData: """{app}\BookReader.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.epub\OpenWithList\BookReader.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithList\BookReader.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.md\OpenWithList\BookReader.exe"; ValueType: none; Flags: uninsdeletekey

[Run]
Filename: "{app}\BookReader.exe"; Description: "Start Book Reader"; Flags: nowait postinstall skipifsilent
