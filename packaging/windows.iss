[Setup]
AppId=ChatFLOW.Studio.Windows
AppName=ChatFLOW 建站系统
AppVersion=2.1.6
DefaultDirName={localappdata}\Programs\ChatFLOW
DefaultGroupName=ChatFLOW
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ChatFLOW-Windows-x64-v2.1.6-Setup
Compression=lzma2/fast
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ChatFLOW.exe
WizardStyle=modern

[Files]
Source: "..\dist\ChatFLOW\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ChatFLOW"; Filename: "{app}\ChatFLOW.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ChatFLOW"; Filename: "{app}\ChatFLOW.exe"; WorkingDir: "{app}"
