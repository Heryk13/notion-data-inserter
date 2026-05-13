# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# Coleta tudo (binaries, data files, e hidden imports) dos pacotes que carregam dinamicamente
keyring_datas, keyring_binaries, keyring_hidden = collect_all('keyring')
quest_datas, quest_binaries, quest_hidden = collect_all('questionary')
pt_datas, pt_binaries, pt_hidden = collect_all('prompt_toolkit')


a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=keyring_binaries + quest_binaries + pt_binaries,
    datas=keyring_datas + quest_datas + pt_datas + [
        ('src/data/japan_regions.json', 'data'),
    ],
    hiddenimports=keyring_hidden + quest_hidden + pt_hidden + [
        'openpyxl',
        'openpyxl.cell._writer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)