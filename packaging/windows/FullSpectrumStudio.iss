#define MyAppName "FullSpectrum Studio"
#ifndef MyAppVersion
#define MyAppVersion "0.4.14"
#endif
#define MyAppPublisher "FullSpectrum Studio contributors"
#define MyAppExeName "FullSpectrumStudio.exe"

[Setup]
AppId={{77153921-9101-4FD1-9DD3-C388973CB5AD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FullSpectrum Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\release
OutputBaseFilename=FullSpectrum-Studio-Windows-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\FullSpectrumStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
