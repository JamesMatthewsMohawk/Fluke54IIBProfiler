"""Locate bundled resource files (icons, etc.), both from source and as a frozen exe."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Resolve a path to a bundled resource.

    Under PyInstaller, bundled data files are extracted to a temp dir at
    sys._MEIPASS, not next to the .exe (that's sys.executable's parent --
    see database._default_db_path for the writable-data-dir case, which is
    a different location for a different reason).
    """
    if getattr(sys, "frozen", False):
        base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir.joinpath(*parts)
