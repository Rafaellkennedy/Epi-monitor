; =========================================================
; EPI Monitor - Script Inno Setup
; Gera o instalador Windows (Setup.exe) a partir do build do PyInstaller.
;
; Pré-requisitos:
;   1. Executar `pyinstaller epi_monitor.spec` primeiro (gera dist/EPIMonitor/)
;   2. Instalar o Inno Setup (https://jrsoftware.org/isinfo.php)
;   3. Compilar este script com o Inno Setup Compiler (ISCC.exe)
;
; Uso via linha de comando:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup_inno.iss
; =========================================================

#define MyAppName "EPI Monitor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Sua Empresa"
#define MyAppExeName "EPIMonitor.exe"

[Setup]
AppId={{B7E5A1F0-EPI4-M0N1-T0R0-000000000001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=EPIMonitor_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; Permite update silencioso "por cima" de uma instalação anterior
UsePreviousAppDir=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na área de trabalho"; GroupDescription: "Ícones adicionais:"

[Files]
; Copia TODO o conteúdo gerado pelo PyInstaller (dist/EPIMonitor/*)
Source: "dist\EPIMonitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

; NOTA IMPORTANTE (PostgreSQL):
; Este instalador NÃO inclui o PostgreSQL. Recomenda-se:
;   a) Instalar o PostgreSQL separadamente no servidor/computador central
;      (https://www.postgresql.org/download/windows/), OU
;   b) Adicionar aqui uma etapa [Run] para instalar um PostgreSQL portátil/
;      embutido silenciosamente, caso a empresa deseje um instalador 100%
;      autocontido.
