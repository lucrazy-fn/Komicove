#ifndef AppSource
  #define AppSource "..\dist\Komicove"
#endif

[Setup]
AppId={{45B7906A-4DE9-4C45-90C0-6E43D8A48A40}
AppVerName=Komicove 0.2.0
AppPublisher=lucrazy-fn
AppPublisherURL=https://github.com/lucrazy-fn/PANEL-ComicBookReader
PrivilegesRequired=lowest
SetupIconFile=..\Komicove.ico
UninstallDisplayIcon={app}\Komicove.exe
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
AppName=Komicove
AppVersion=0.2.0
DefaultDirName={localappdata}\Programs\Komicove
DefaultGroupName=Komicove
OutputBaseFilename=Komicove-Setup-0.2.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\PANEL.exe"
Type: files; Name: "{autoprograms}\PANEL Comic Reader.lnk"
Type: files; Name: "{autodesktop}\PANEL Comic Reader.lnk"

[Icons]
Name: "{autoprograms}\Komicove"; Filename: "{app}\Komicove.exe"
Name: "{autodesktop}\Komicove"; Filename: "{app}\Komicove.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Run]
Filename: "{app}\Komicove.exe"; Description: "Abrir Komicove"; Flags: nowait postinstall skipifsilent
