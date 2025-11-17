"""Helpers for deduplicating variants and writing alias suggestions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


def collect_alias_suggestions(
    payloads: List[Dict[str, object]],
    known_alias_variants: Set[str],
) -> Dict[str, List[str]]:
    """Build an alias suggestion map from verified payloads."""
    suggestions: Dict[str, set] = {}
    for item in payloads:
        canonical = str(item.get("canonical", "")).strip()
        variants = item.get("variants", []) or []
        for variant in variants:
            if not isinstance(variant, str):
                continue
            normalized = variant.strip()
            if (
                not normalized
                or normalized.lower() == canonical.lower()
                or normalized.lower() in known_alias_variants
            ):
                continue
            suggestions.setdefault(canonical, set()).add(normalized)
    return {canonical: sorted(values) for canonical, values in suggestions.items() if values}


def append_aliases_file(alias_path: Path, suggestions: Dict[str, List[str]]) -> None:
    """Append learned aliases to a YAML/JSON file."""
    if not suggestions:
        return
    existing: Dict[str, List[str]] = {}
    if alias_path.exists():
        raw = alias_path.read_text(encoding="utf-8")
        if raw.strip():
            if yaml is not None:
                loaded = yaml.safe_load(raw) or {}
            else:
                loaded = json.loads(raw)
            if isinstance(loaded, dict):
                existing = {k: list(v or []) for k, v in loaded.items()}
    for canonical, variants in suggestions.items():
        current = set(existing.get(canonical, []))
        current.update(variants)
        existing[canonical] = sorted(current)
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        alias_path.write_text(yaml.safe_dump(existing, sort_keys=True), encoding="utf-8")
    else:
        alias_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


__all__ = ["collect_alias_suggestions", "append_aliases_file"]
