# -*- mode: python ; coding: utf-8 -*-
#
# Build:        pyinstaller --noconfirm BladesPlayground.spec        (output: dist/BladesPlayground[.exe])
# Smoke build:  BP_CONSOLE=1 pyinstaller --noconfirm BladesPlayground.spec
#               keeps a console window so stdin "terminal control" works (used to test the build).
#
# Notes
#  * Only assets/ is bundled.  data/ is deliberately NOT: saves live in the per-user data folder
#    (see utils/paths.py), and shipping the developer's own scores would be wrong.
#  * pygame._sdl2.* are imported lazily (gamepad, GPU presenter) so PyInstaller can't see them.
import os
from pathlib import Path

CONSOLE = os.environ.get("BP_CONSOLE") == "1"
ICON = Path("assets/logo.ico")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['pygame._sdl2.controller', 'pygame._sdl2.video'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
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
    name='BladesPlayground',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ICON)] if ICON.exists() else None,
)
