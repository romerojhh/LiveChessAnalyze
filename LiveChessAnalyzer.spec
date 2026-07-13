# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('gui', 'gui'), ('vision', 'vision'), ('engine', 'engine')],
    hiddenimports=['numpy._core._exceptions'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LiveChessAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LiveChessAnalyzer',
)
app = BUNDLE(
    coll,
    name='LiveChessAnalyzer.app',
    icon=None,
    bundle_identifier='com.livechessanalyzer.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSScreenCaptureUsageDescription': 'Live Chess Analyzer needs to capture your screen to analyze the chess board in real-time.',
    },
)
