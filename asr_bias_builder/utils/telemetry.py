"""Lightweight telemetry emitters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def write_stats(path: Path, stats: Dict[str, object]) -> None:
    """Write stats as a JSON document."""
    path.write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")


def snapshot_environment(dest: Path, pip_freeze: str) -> None:
    """Persist environment metadata for auditing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(pip_freeze, encoding="utf-8")


__all__ = ["write_stats", "snapshot_environment"]
