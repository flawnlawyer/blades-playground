"""
paths.py — Where the game finds its assets and keeps its save data.

Running from source:   saves go in  <project>/data   (unchanged from before).
Packaged build:        saves go in the per-user data folder, because a one-file build
                       unpacks to a temporary directory that is DELETED on exit — saving
                       next to the code would silently lose every score on every launch.

    Windows  %APPDATA%\\BladesPlayground
    macOS    ~/Library/Application Support/BladesPlayground
    Linux    $XDG_DATA_HOME/BladesPlayground  (default ~/.local/share/BladesPlayground)

BLADES_DATA_DIR overrides everything (useful for tests, portable installs, debugging).
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

APP_NAME = "BladesPlayground"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True inside a PyInstaller or Nuitka build."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def resource_path(rel: str) -> Path:
    """Path to a bundled read-only file (e.g. 'assets/logo.png')."""
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))        # _MEIPASS = PyInstaller's unpack dir
    return base / rel


def user_data_dir() -> Path:
    override = os.environ.get("BLADES_DATA_DIR")
    if override:
        return Path(override)
    if not is_frozen():
        return PROJECT_ROOT / "data"
    home = Path.home()
    if sys.platform.startswith("win"):
        root = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = home / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    return root / APP_NAME
