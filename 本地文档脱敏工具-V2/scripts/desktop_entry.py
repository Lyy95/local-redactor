# ruff: noqa: E402, I001
from __future__ import annotations

import os
import sys
from pathlib import Path


_dll_directory_handles: list[object] = []


def _prepare_frozen_dll_search_path() -> None:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if not bundled_root or not hasattr(os, "add_dll_directory"):
        return
    root = Path(bundled_root)
    candidates = (root, root / "PySide6", root / "shiboken6")
    os.environ["PATH"] = os.pathsep.join(
        [*(str(path) for path in candidates if path.is_dir()), os.environ.get("PATH", "")]
    )
    for path in candidates:
        if path.is_dir():
            _dll_directory_handles.append(os.add_dll_directory(str(path)))


_prepare_frozen_dll_search_path()

from local_redactor_v2.app import main

if __name__ == "__main__":
    raise SystemExit(main())
