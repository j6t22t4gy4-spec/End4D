"""Build a simple macOS app bundle for launching End4D in Terminal."""
from __future__ import annotations

import plistlib
import shutil
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "End4D Launcher"
APP_DIR = ROOT / f"{APP_NAME}.app"
CONTENTS_DIR = APP_DIR / "Contents"
MACOS_DIR = CONTENTS_DIR / "MacOS"


def _write_info_plist(path: Path) -> None:
    info = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": "com.end4d.launcher",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    with path.open("wb") as f:
        plistlib.dump(info, f)


def _write_launcher(path: Path) -> None:
    script = f"""#!/bin/zsh
set -euo pipefail

ROOT_DIR="{ROOT}"
COMMAND_PATH="$ROOT_DIR/Launch_End4D.command"

if [ ! -f "$COMMAND_PATH" ]; then
  osascript -e 'display alert "End4D Launcher" message "Launch_End4D.command was not found." as critical'
  exit 1
fi

open -a Terminal "$COMMAND_PATH"
"""
    path.write_text(script, encoding="utf-8")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    MACOS_DIR.mkdir(parents=True, exist_ok=True)
    _write_info_plist(CONTENTS_DIR / "Info.plist")
    _write_launcher(MACOS_DIR / APP_NAME)

    print(f"Built macOS app bundle: {APP_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
