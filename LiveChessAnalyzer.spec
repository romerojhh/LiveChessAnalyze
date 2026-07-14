# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtPdf',
        'PySide6.QtQmlModels',
        'PySide6.QtQuickTemplates2',
        'PySide6.QtVirtualKeyboard',
    ],
    noarchive=False,
    optimize=0,
)

# Unused/redundant binary files to exclude to reduce executable size
excluded_binaries = {
    'opencv_videoio_ffmpeg500_64.dll',  # Unused video IO / FFmpeg support
    'Qt6Quick.dll',                     # Unused QML Quick engine
    'Qt6Qml.dll',                       # Unused QML scripting engine
    'Qt6Pdf.dll',                       # Unused PDF viewer engine
    'Qt6QmlModels.dll',                 # Unused QML model engine
    'Qt6QuickTemplates2.dll',           # Unused Quick templates
    'Qt6VirtualKeyboard.dll',           # Unused Virtual Keyboard
}

a.binaries = [x for x in a.binaries if x[0].split('\\')[-1].split('/')[-1] not in excluded_binaries]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LiveChessAnalyzer',
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
)
