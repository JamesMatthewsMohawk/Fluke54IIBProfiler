# -*- mode: python ; coding: utf-8 -*-

# Internal tool only -- issues license keys for SuperbaTunnelProfiler.
# Never attach this build to a customer-facing release.

EXCLUDES = [
    'PIL',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQuick3D',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtSensors',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebSockets',
    'PySide6.QtWebChannel',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtSql',
    'PySide6.QtHelp',
    'PySide6.QtDesigner',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtStateMachine',
    'PySide6.QtSpatialAudio',
    'PySide6.QtTextToSpeech',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DExtras',
    'pyqtgraph',
    'numpy',
    'openpyxl',
    'pypdf',
    'serial',
]

a = Analysis(
    ['tools\\license_key_gui.py'],
    pathex=['.', 'tools'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Onefile: this tool is launched rarely, so the onefile per-launch
# extraction cost doesn't matter, and shipping a single .exe is simpler
# to hand off than a folder.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LicenseKeyMaker',
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
    icon=['icon.ico'],
)
