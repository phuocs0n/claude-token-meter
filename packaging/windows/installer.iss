; Inno Setup 6 script for the Windows installer.
; Built by: python packaging/build.py --installer
; Installs for the current user by default (no admin rights needed).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\ClaudeTokenMeter"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{8D3F5C2A-6B1E-4F7A-9C0D-2E4B6A8F1C35}
AppName=Claude Token Meter
AppVersion={#AppVersion}
AppVerName=Claude Token Meter {#AppVersion}
AppPublisher=Claude Token Meter contributors
AppPublisherURL=https://github.com/phuocs0n/claude-token-meter
AppSupportURL=https://github.com/phuocs0n/claude-token-meter/issues
AppUpdatesURL=https://github.com/phuocs0n/claude-token-meter/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Claude Token Meter
DefaultGroupName=Claude Token Meter
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=ClaudeTokenMeter-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\ClaudeTokenMeter.exe
UninstallDisplayName=Claude Token Meter
LicenseFile=..\..\LICENSE
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of an older version that the new one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Claude Token Meter"; Filename: "{app}\ClaudeTokenMeter.exe"
Name: "{autodesktop}\Claude Token Meter"; Filename: "{app}\ClaudeTokenMeter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ClaudeTokenMeter.exe"; Description: "{cm:LaunchProgram,Claude Token Meter}"; Flags: nowait postinstall skipifsilent
