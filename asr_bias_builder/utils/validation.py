"""Input validation helpers."""
from __future__ import annotations

from pathlib import Path


def ensure_file(path: Path) -> Path:
    """Ensure the file exists, raising a friendly error otherwise."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    return path


__all__ = ["ensure_file"]
