[Setup]
AppName=MoneyFlow
AppVersion=1.0
DefaultDirName={autopf}\MoneyFlow
DefaultGroupName=MoneyFlow
UninstallDisplayIcon={app}\MoneyFlow.exe
Compression=lzma2
SolidCompression=yes
; Icono del instalador
SetupIconFile=src\assets\icono.ico
; Carpeta donde se guardará el instalador final
OutputDir=.\OutputInstaller
OutputBaseFilename=MoneyFlow_Setup
WizardStyle=modern

[Files]
; Copia TODO lo generado por PyInstaller (incluye el .exe, _internal, etc.)
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Si quieres incluir un .env, descomenta la siguiente línea y asegúrate de que el archivo exista en dist\
; Source: "dist\.env"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MoneyFlow"; Filename: "{app}\MoneyFlow.exe"
Name: "{autodesktop}\MoneyFlow"; Filename: "{app}\MoneyFlow.exe"

[Run]
Filename: "{app}\MoneyFlow.exe"; Description: "Lanzar MoneyFlow ahora mismo"; Flags: nowait postinstall skipifsilent