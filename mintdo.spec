r"""Build a single-file standalone Windows executable for MintDo.

Usage (on Windows, from the project root):

    build_windows.bat

...or manually:

    pip install -r requirements.txt pyinstaller
    pyinstaller --noconfirm --clean mintdo.spec

Output:  dist\MintDo.exe     (ONE file - copy it anywhere and double-click;
                              no Python needed, everything is bundled inside)

Notes
-----
* One-file mode: the exe unpacks itself to a temp folder on each launch, so the
  first start is a second or two slower. It is the simplest thing to hand to a
  non-technical user (just MintDo.exe).
* If you'd rather have a folder you can move (faster startup), see the note in
  README about one-folder builds.
* Data is stored per-user in %LOCALAPPDATA%\MintDo\mintdo.db, so every copy of
  the exe shares the same to-do list.
"""
import os

block_cipher = None

# PyInstaller does NOT define __file__ inside a spec; SPECPATH is the folder
# that holds this .spec file (set by PyInstaller at build time).
ROOT = os.path.abspath(SPECPATH)
ICON = os.path.join(ROOT, "assets", "icon.ico")

# Only pass an icon if it exists; a .ico is expected on Windows.
icon = ICON if os.path.exists(ICON) else None

# Everything PySide6/Qt needs at runtime that PyInstaller's hooks might miss.
hiddenimports = [
    "mintdo.qt",
    "mintdo.qt_app",
]

a = Analysis(
    [os.path.join(ROOT, "mintdo", "qt_app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim unused Qt modules to keep the exe small.
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtMultimedia", "PySide6.QtNetwork",
              "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONE-FILE mode: bundle binaries + data straight into the exe (no COLLECT).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MintDo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

