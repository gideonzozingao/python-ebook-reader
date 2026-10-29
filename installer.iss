; Book Reader installer (Inno Setup 6).  Build it with build_installer.bat, or open this file in
; the Inno Setup Compiler and press F9 (run build_exe.bat first so dist\BookReader exists).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Book Reader"
#define AppExe "BookReader.exe"

[Setup]
; Keep this GUID the same in every version: it lets a new installer upgrade the old one.
AppId={{8B7F2C54-3D9A-4E61-A2B8-5C1E9F0D7A33}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=BookReader-Setup-{#AppVersion}
SetupIconFile=book_reader\assets\book_reader.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Installs for the current user (no administrator prompt). Choose "Install for all users"
; in the dialog, or change this to admin, if you want it in C:\Program Files.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no
#ifdef Sign
; Digitally sign the installer and the uninstaller (the "bookreader" tool is passed to ISCC by
; build_installer.bat, which calls sign_file.bat).
SignTool=bookreader
SignedUninstaller=yes
SignToolRetryCount=3
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\BookReader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Adds Book Reader to the "Open with" list for books (your default apps are not changed).
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.epub\OpenWithList\{#AppExe}"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithList\{#AppExe}"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.md\OpenWithList\{#AppExe}"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.markdown\OpenWithList\{#AppExe}"; ValueType: none; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
; Silent upgrade started by the app's own updater (it passes /RELAUNCH=1): start the new version.
; Other silent installs (e.g. rolled out by IT) do not start the app.
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifnotsilent runasoriginaluser; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;

// Your library (books, notes, settings) lives in your user folder, not here, so
// uninstalling or upgrading never deletes it.
