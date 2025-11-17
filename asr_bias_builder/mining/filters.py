"""Reusable filters for mining candidate terms."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, List

from ..config import load_config

CONFIG = load_config()
STOP_WORDS = {w.lower() for w in CONFIG.get("stop_words", [])}
MIN_TERM_LENGTH = int(CONFIG.get("min_term_length", 2))
MAX_TERM_LENGTH = int(CONFIG.get("max_term_length", 50))
DENY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CONFIG.get("deny_patterns", [])]
DENY_EXACT = {s.lower() for s in CONFIG.get("deny_exact", [])}
SECTION_KEYWORD_WEIGHTS = {
    key.lower(): float(value)
    for key, value in CONFIG.get("section_keyword_weights", {}).items()
}
DEFAULT_SECTION_WEIGHT = float(CONFIG.get("default_section_weight", 1.0))
USE_SECTION_WEIGHTING = bool(CONFIG.get("use_section_weighting", False))

PROPER_CASE_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
ALL_CAPS_RE = re.compile(r"\b[A-Z0-9&/\-]{2,}\b")
MIXED_TOKEN_RE = re.compile(r"\b[A-Za-z]+(?:[-/][A-Za-z0-9]+)+\b")
CAMEL_RE = re.compile(r"\b[A-Z][a-z]+[A-Z][\w]+\b")
NUMBER_RE = re.compile(r"^\d{1,4}(?:[./-]\d{1,4})?$")
SECTION_HEADER_MAX_WORDS = 8


@dataclass
class FilterStats:
    """Counters for how often each filter fired."""

    stop_words: int = 0
    numbers: int = 0
    deny_patterns: int = 0
    length: int = 0
    total_filtered: int = 0
    section_weight_hits: int = 0

    def log(self, output_count: float) -> None:
        from sys import stderr

        msg = (
            f"[mine_terms] filter_stats "
            f"stop_words={self.stop_words} numbers={self.numbers} "
            f"patterns={self.deny_patterns} length={self.length} "
            f"filtered_total={self.total_filtered} section_weight_hits={self.section_weight_hits} "
            f"output_terms={int(output_count)}"
        )
        print(msg, file=stderr)


def extract_candidates_from_line(text: str) -> List[str]:
    """Return candidate entity spans from a line of deck text."""
    candidates: List[str] = []
    for regex in (PROPER_CASE_RE, ALL_CAPS_RE, MIXED_TOKEN_RE, CAMEL_RE):
        candidates.extend(regex.findall(text))
    return candidates


def normalize_term(term: str) -> str:
    term = term.strip()
    term = re.sub(r"\s+", " ", term)
    return term


def is_stop_word(term: str) -> bool:
    return term.lower() in STOP_WORDS


def is_number_like(term: str) -> bool:
    clean = term.replace(",", "")
    if NUMBER_RE.fullmatch(clean):
        return True
    if clean.endswith("%") and clean[:-1].isdigit():
        return True
    return False


def matches_deny_pattern(term: str) -> bool:
    return any(pattern.search(term) for pattern in DENY_PATTERNS)


def detect_section_weight(line: str, current_weight: float, stats: FilterStats) -> float:
    """Adjust weighting when a new section header is encountered."""
    stripped = line.strip()
    if not stripped:
        return current_weight
    normalized = re.sub(r"[^a-z0-9 ]+", " ", stripped.lower()).strip()
    maybe_header = stripped.endswith(":") or stripped.isupper() or len(stripped.split()) <= SECTION_HEADER_MAX_WORDS
    matched_key = None
    for keyword, weight in SECTION_KEYWORD_WEIGHTS.items():
        if keyword in normalized:
            matched_key = keyword
            break
    if matched_key:
        stats.section_weight_hits += 1
        return float(SECTION_KEYWORD_WEIGHTS.get(matched_key, DEFAULT_SECTION_WEIGHT))
    if maybe_header:
        return DEFAULT_SECTION_WEIGHT
    return current_weight


__all__ = [
    "FilterStats",
    "DEFAULT_SECTION_WEIGHT",
    "USE_SECTION_WEIGHTING",
    "DENY_EXACT",
    "MIN_TERM_LENGTH",
    "MAX_TERM_LENGTH",
    "extract_candidates_from_line",
    "normalize_term",
    "is_stop_word",
    "is_number_like",
    "matches_deny_pattern",
    "detect_section_weight",
]
