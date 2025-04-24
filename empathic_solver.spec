# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['empathic_solver.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['typer', 'rich.console', 'rich.table', 'rich.markdown', 'rich.panel', 
                  'rich.progress', 'pandas', 'numpy', 'sqlite3', 'datetime', 'pathlib',
                  'requests', 'keyring', 'getpass', 'json', 'textwrap'],
    hookspath=[],
    hooksconfig={},
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='empathic-solver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)