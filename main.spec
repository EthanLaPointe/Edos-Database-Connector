# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/Main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/style.qss', '.')],
    hiddenimports=[
        'app',
        'pages',
        'pages.login_page',
        'pages.home_page',
        'pages.report_page',
        'pages.alias_page',
        'pages.sidebar',
        'pages.report_flag_dialog',
        'pages.protocols',
        'db_connection',
        'data_cache',
        'file_handler',
        'report',
        'PySide6',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name='Edos Database Connector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
