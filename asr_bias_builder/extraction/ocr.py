"""OCR normalization helpers."""
from __future__ import annotations

import re
from typing import Dict


def apply_ocr_normalization(text: str, config: Dict[str, object]) -> str:
    """Apply regex and alias-based OCR cleanup."""
    normalizations = config.get("ocr_normalizations", [])
    for rule in normalizations or []:
        pattern = rule.get("pattern")
        replacement = rule.get("replacement", "")
        if not pattern:
            continue
        text = re.sub(pattern, replacement, text)

    alias_map = config.get("ocr_aliases", {})
    for canonical, variants in (alias_map or {}).items():
        for variant in variants:
            pattern = rf"\b{re.escape(variant)}\b"
            text = re.sub(pattern, str(canonical), text, flags=re.IGNORECASE)
    return text


__all__ = ["apply_ocr_normalization"]
