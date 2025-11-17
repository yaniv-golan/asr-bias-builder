#!/usr/bin/env python3
"""Merge learned aliases back into config.yml."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required for bin/merge_aliases.py") from exc


def load_yaml(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def normalize_alias_dict(data: Dict[str, object]) -> Dict[str, List[str]]:
    normalized: Dict[str, List[str]] = {}
    for canonical, variants in data.items():
        if not isinstance(variants, list):
            continue
        normalized[str(canonical)] = [str(v) for v in variants if isinstance(v, str)]
    return normalized


def merge_aliases(learned_path: Path, config_path: Path) -> None:
    learned_raw = load_yaml(learned_path)
    learned = normalize_alias_dict(learned_raw)
    if not learned:
        print("No aliases to merge")
        return
    config = load_yaml(config_path)
    existing_raw = config.get("ocr_aliases", {}) if isinstance(config, dict) else {}
    existing = normalize_alias_dict(existing_raw if isinstance(existing_raw, dict) else {})
    for canonical, variants in learned.items():
        bucket = set(existing.get(canonical, []))
        for variant in variants:
            if variant and variant.lower() != canonical.lower():
                bucket.add(variant)
        existing[canonical] = sorted(bucket)
    config["ocr_aliases"] = existing
    config_path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")
    print(f"Merged {len(learned)} canonical entries into {config_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge learned aliases into config.yml")
    parser.add_argument("learned_aliases", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/default.yml"))
    args = parser.parse_args()

    merge_aliases(args.learned_aliases, args.config)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
