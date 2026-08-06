# -*- mode: python ; coding: utf-8 -*-


# The app only uses QtWidgets/QtCore/QtGui/QtPrintSupport -- trim the
# unused PySide6 submodules to keep the onedir folder smaller. PIL/Pillow
# is a dev-only tool (used once, by hand, to build icon.ico) -- the app
# itself never imports it.
EXCLUDES = [
    'PIL',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQuick3D',
    # NOTE: PySide6.QtOpenGL/QtOpenGLWidgets are NOT excluded, even though
    # this app doesn't use OpenGL -- pyqtgraph's own import chain
    # (pyqtgraph/Qt/OpenGLHelpers.py) does `import PySide6.QtOpenGL`
    # unconditionally just to probe for it, so excluding it crashes
    # pyqtgraph's import at startup with ModuleNotFoundError.
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
]

a = Analysis(
    ['app\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('icon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SuperbaTunnelProfiler',
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

# onedir mode: the .exe loads its libraries directly from this folder
# instead of unpacking a bundled archive to a fresh temp dir on every
# launch (the onefile behavior) -- avoids that per-launch antivirus
# re-scan cost, at the cost of shipping a folder instead of one file.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SuperbaTunnelProfiler',
)
