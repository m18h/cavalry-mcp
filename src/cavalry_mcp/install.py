"""Copy the bundled bridge.js into Cavalry's Scripts folder."""

from __future__ import annotations

import os
import platform
import shutil
from importlib.resources import files
from pathlib import Path

BRIDGE_FILENAME = "cavalry-mcp-bridge.js"


def scripts_folder() -> Path:
    """Cavalry's per-user Scripts folder (same location Stallion uses)."""
    if platform.system() == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Cavalry"
            / "Scripts"
        )
    if platform.system() == "Windows":
        roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return roaming / "Cavalry" / "Scripts"
    # Linux: Cavalry is not officially supported, but keep a sensible guess.
    return Path.home() / ".local" / "share" / "Cavalry" / "Scripts"


def bundled_bridge_path() -> Path:
    return Path(str(files("cavalry_mcp").joinpath(f"js/{BRIDGE_FILENAME}")))


def install_bridge(target_dir: Path | None = None) -> Path:
    folder = target_dir or scripts_folder()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / BRIDGE_FILENAME
    shutil.copyfile(bundled_bridge_path(), target)
    return target
