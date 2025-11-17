#!/usr/bin/env python3
"""Configuration loader for ASR bias pipeline."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_FILE = PACKAGE_ROOT / "config" / "default.yml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "stop_words": [
        "all",
        "also",
        "the",
        "this",
        "that",
        "these",
        "those",
        "see",
        "reply",
        "add",
        "today",
        "last",
        "just",
        "it",
        "on",
        "no",
        "end",
        "check",
        "prepare",
        "preparing",
        "message",
        "messages",
        "thread",
        "linked",
        "slide",
    ],
    "deny_patterns": [
        r"^demo[0-9_-]",
        r"^u/",
        r"^t0",
        r"/[A-Z0-9]{6,}",
        r"#[A-Za-z0-9_-]+",
        r"\.py$",
        r"\.js$",
        r"\.ts$",
        r"\.java$",
        r"\.rb$",
        r"\(\)",
        r"/[^\s]{4,}",
        r"^[0-9]{1,2}:[0-9]{2}$",
    ],
    "ocr_aliases": {
        "Dyson Sphere": ["Dyson Spher", "Dyson Sphere Al"],
        "Liam Nguyen": ["Liam Nguyn"],
        "AI": ["Al"],
    },
    "ocr_normalizations": [
        {"pattern": r"\b([A-Z][a-z]+)\s+Al\b", "replacement": r"\1 AI"},
        {"pattern": r"\bAl\s+([A-Z])", "replacement": r"AI \1"},
    ],
    "min_term_length": 2,
    "max_term_length": 50,
    "high_value_classes": ["PERSON", "ORG", "PRODUCT", "TECH"],
    "phrase_set_max": 300,
    "score_boosts": [
        {"threshold": 0.95, "boost": 10.0},
        {"threshold": 0.85, "boost": 8.0},
        {"threshold": 0.70, "boost": 6.0},
    ],
    "pos_filter": False,
    "auto_ocr": True,
    "use_titlecase_filter": True,
    "acronym_min_length": 2,
    "use_llm_priority_threshold": True,
    "llm_priority_threshold": 0.75,
    "deny_exact": [],
    "class_boost_floors": {
        "PERSON": 10.0,
        "ORG": 8.0,
        "PRODUCT": 6.0,
        "TECH": 6.0,
    },
    "class_order": ["PERSON", "ORG", "PRODUCT", "TECH"],
    "deck_overrides": {},
    "use_section_weighting": True,
    "section_keyword_weights": {
        "team": 2.0,
        "founder": 2.0,
        "leadership": 2.0,
        "product": 1.5,
        "solution": 1.3,
        "benchmark": 1.3,
        "customer": 1.3,
        "partner": 1.2,
        "confidential": 0.3,
        "copyright": 0.1,
        "footer": 0.3,
    },
    "default_section_weight": 1.0,
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Load configuration from YAML file or fall back to defaults."""
    cfg = dict(DEFAULT_CONFIG)
    config_path = path or os.getenv("BIAS_CONFIG_FILE")
    candidates = [Path(p) for p in [config_path, DEFAULT_CONFIG_FILE] if p]
    for file in candidates:
        if file.exists() and yaml is not None:
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        else:
            continue
        if isinstance(data, dict):
            cfg = _deep_merge(cfg, data)
    deck_id = os.getenv("BIAS_DECK_ID")
    if deck_id:
        overrides = cfg.get("deck_overrides", {}).get(deck_id)
        if isinstance(overrides, dict):
            cfg = _deep_merge(cfg, overrides)
    return cfg
