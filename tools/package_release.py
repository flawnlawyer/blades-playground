#!/usr/bin/env python3
"""
package_release.py — zip a PyInstaller build for a GitHub release.

    python tools/package_release.py            # -> dist/BladesPlayground-<version>-<os>.zip

Contains the game binary plus README, LICENSE, CONSOLE.md and CHANGELOG.md.
"""
import sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from game import __version__

OS_NAME = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def build_zip(dist: Path = ROOT / "dist") -> Path:
    exe = next((p for p in (dist / "BladesPlayground.exe", dist / "BladesPlayground") if p.exists()), None)
    if exe is None:
        raise SystemExit(f"no build found in {dist} — run pyinstaller first")
    out = dist / f"BladesPlayground-{__version__}-{OS_NAME}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo.from_file(exe, exe.name)
        info.external_attr = 0o755 << 16                        # keep the executable bit on macOS/Linux
        with open(exe, "rb") as fh:
            z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
        for doc in ("README.md", "LICENSE", "CONSOLE.md", "CHANGELOG.md"):
            if (ROOT / doc).exists():
                z.write(ROOT / doc, doc)
    return out


if __name__ == "__main__":
    print(build_zip())
