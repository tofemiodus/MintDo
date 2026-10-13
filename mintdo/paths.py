"""Cross-platform data locations for MintDo.

Linux:   $XDG_DATA_HOME/mintdo/mintdo.db   (usually ~/.local/share/mintdo/)
Windows: %LOCALAPPDATA%\\MintDo\\mintdo.db
"""
from __future__ import annotations

import os
import sys


def data_dir() -> str:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            os.path.join("~", "AppData", "Local"))
        return os.path.join(root, "MintDo")
    root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        os.path.join("~", ".local", "share"))
    return os.path.join(root, "mintdo")


def db_path() -> str:
    return os.path.join(data_dir(), "mintdo.db")
