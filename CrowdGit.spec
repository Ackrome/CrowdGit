# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['github_sync.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=['aiohttp', 'sv_ttk', 'github', 'certifi', 'requests', 'PIL', 'tkinterdnd2', 'urllib3', 'sqlite3', 'asyncio', 'tkinter', 'tkinter.ttk', 'base64', 'json', 'traceback', 'os', 're', 'logging', 'threading', 'hashlib', 'atexit', 'binascii', 'platform', 'urllib.request', 'http.client', 'requests.exceptions', 'urllib3.exceptions', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ImageTk', 'tkinter.filedialog', 'tkinter.messagebox'],
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
    name='CrowdGit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icons\\CrowdGit.ico'],
)
