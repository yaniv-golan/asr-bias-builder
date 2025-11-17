"""Normalization and section heuristics for deck text."""
from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

SECTION_HEADER_MAX_WORDS = 8


def normalize_text(text: str) -> str:
    """Normalize whitespace and Unicode composition."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r" *(\n+) *", "\n", text)
    return text.strip()


def detect_sections(text: str) -> List[Tuple[str, str]]:
    """Split normalized text into (header, body) tuples."""
    sections: List[Tuple[str, str]] = []
    current_header = "Document"
    current_lines: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        maybe_header = line.startswith("[Slide") or line.endswith(":") or len(line.split()) <= SECTION_HEADER_MAX_WORDS
        if maybe_header and any(ch.isupper() for ch in line[:SECTION_HEADER_MAX_WORDS]):
            if current_lines:
                sections.append((current_header, " ".join(current_lines)))
                current_lines = []
            current_header = line.strip("[]:")
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_header, " ".join(current_lines)))
    return sections


__all__ = ["normalize_text", "detect_sections"]
