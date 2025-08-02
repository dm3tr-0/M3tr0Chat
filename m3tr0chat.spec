# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['m3tr0chat.py'],
    pathex=[],
    binaries=[],
    datas=[('app.manifest', '.')],
    hiddenimports=['stem', 'flask', 'colorama', 'requests', 'pysocks', 'urllib3.contrib.socks', 'requests.packages.urllib3.contrib.socks', 'waitress'],
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
    name='m3tr0chat',
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
    version='version_info.txt',
    icon=['icon.ico'],
)
