#ifndef AppVersion
  #define AppVersion "1.0"
#endif

[Setup]
AppId={{7C3B5E52-4A1D-4F0E-9B6A-2D8E1F4C9A37}
AppName=Zuqongsoft E-Book Reader
AppVersion={#AppVersion}
AppPublisher=Zuqongsoft
DefaultDirName={autopf}\Zuqongsoft E-Book Reader
DefaultGroupName=Zuqongsoft E-Book Reader
DisableProgramGroupPage=yes
OutputBaseFilename=Zuqongsoft-EBook-Reader-Setup
OutputDir=installer
SetupIconFile=book_reader\assets\book_reader.ico
UninstallDisplayIcon={app}\Zuqongsoft-EBook-Reader.exe
UninstallDisplayName=Zuqongsoft E-Book Reader
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\Zuqongsoft-EBook-Reader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Zuqongsoft E-Book Reader"; Filename: "{app}\Zuqongsoft-EBook-Reader.exe"
Name: "{group}\Uninstall Zuqongsoft E-Book Reader"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Zuqongsoft E-Book Reader"; Filename: "{app}\Zuqongsoft-EBook-Reader.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\Zuqongsoft-EBook-Reader.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Zuqongsoft E-Book Reader"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\Zuqongsoft-EBook-Reader.exe\shell\open\command"; ValueType: string; ValueData: """{app}\Zuqongsoft-EBook-Reader.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.epub\OpenWithList\Zuqongsoft-EBook-Reader.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithList\Zuqongsoft-EBook-Reader.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.md\OpenWithList\Zuqongsoft-EBook-Reader.exe"; ValueType: none; Flags: uninsdeletekey

[Run]
Filename: "{app}\Zuqongsoft-EBook-Reader.exe"; Description: "Start Zuqongsoft E-Book Reader"; Flags: nowait postinstall skipifsilent