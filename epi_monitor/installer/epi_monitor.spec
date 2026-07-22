# -*- mode: python ; coding: utf-8 -*-
"""
epi_monitor.spec
-----------------
Especificação do PyInstaller para gerar o executável Windows (.exe) do
EPI Monitor. Gera um único diretório com o executável e dependências
(mais estável para apps grandes com PyTorch/Ultralytics do que --onefile,
que descompacta tudo em uma pasta temporária a cada início, deixando o
app lento para abrir).

Uso:
    cd installer
    pyinstaller epi_monitor.spec

Saída: installer/dist/EPIMonitor/EPIMonitor.exe
"""

import sys
from pathlib import Path

block_cipher = None
PROJECT_ROOT = Path(__file__).resolve().parent.parent

a = Analysis(
    [str(PROJECT_ROOT / "app" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "resources"), "resources"),
        (str(PROJECT_ROOT / ".env.example"), "."),
    ],
    hiddenimports=[
        "PySide6.QtMultimedia",
        "ultralytics",
        "cv2",
        "psycopg2",
        "onvif",
        "wsdiscovery",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EPIMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # False = sem janela de terminal (app gráfico)
    icon=str(PROJECT_ROOT / "resources" / "icons" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EPIMonitor",
)
