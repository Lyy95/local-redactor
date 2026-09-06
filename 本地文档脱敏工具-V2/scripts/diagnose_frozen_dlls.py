from __future__ import annotations

import argparse
import os
from collections import deque
from pathlib import Path

import pefile


def imports_for(path: Path) -> list[str]:
    image = pefile.PE(str(path), fast_load=True)
    image.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
    )
    entries = getattr(image, "DIRECTORY_ENTRY_IMPORT", ())
    return [entry.dll.decode("ascii", errors="replace") for entry in entries]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_dir", type=Path)
    args = parser.parse_args()
    internal = args.app_dir.resolve() / "_internal"
    search_roots = (
        internal,
        internal / "PySide6",
        internal / "shiboken6",
        Path(os.environ["WINDIR"]) / "System32",
    )
    available: dict[str, Path] = {}
    for root in search_roots:
        if root.is_dir():
            for path in root.glob("*"):
                if path.is_file():
                    available.setdefault(path.name.casefold(), path)

    start = internal / "PySide6" / "QtCore.pyd"
    queue = deque([start])
    visited: set[Path] = set()
    missing: dict[str, set[str]] = {}
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        try:
            dependencies = imports_for(current)
        except (OSError, pefile.PEFormatError):
            continue
        for dependency in dependencies:
            key = dependency.casefold()
            if key.startswith(("api-ms-", "ext-ms-")):
                continue
            resolved = available.get(key)
            if resolved is None:
                missing.setdefault(dependency, set()).add(current.name)
            elif resolved.suffix.casefold() in {".dll", ".pyd", ".exe"}:
                queue.append(resolved)

    for dependency, parents in sorted(missing.items()):
        print(f"MISSING {dependency} <- {', '.join(sorted(parents))}")
    print(f"checked={len(visited)} missing={len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
