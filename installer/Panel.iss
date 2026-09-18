[Setup]
AppId={{45B7906A-4DE9-4C45-90C0-6E43D8A48A40}
AppVerName=PANEL 1.6.1
AppPublisher=lucrazy-fn
AppPublisherURL=https://github.com/lucrazy-fn/PANEL-ComicBookReader
PrivilegesRequired=lowest
SetupIconFile=..\panel.ico
UninstallDisplayIcon={app}\PANEL.exe
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
AppName=PANEL Comic Reader
AppVersion=1.6.1
DefaultDirName={localappdata}\Programs\PANEL
DefaultGroupName=PANEL Comic Reader
OutputBaseFilename=PANEL-Setup-1.6.1
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\PANEL\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PANEL Comic Reader"; Filename: "{app}\PANEL.exe"
Name: "{autodesktop}\PANEL Comic Reader"; Filename: "{app}\PANEL.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Run]
Filename: "{app}\PANEL.exe"; Description: "Abrir PANEL"; Flags: nowait postinstall skipifsilent
