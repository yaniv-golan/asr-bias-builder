"""Validation helpers for generated artifacts."""
from __future__ import annotations

from typing import Iterable, List, Mapping


def validate_prompt_terms(terms: Iterable[str], max_terms: int = 300) -> None:
    """Ensure the Whisper prompt list is within size constraints."""
    term_list = list(terms)
    if len(term_list) > max_terms:
        raise ValueError(f"prompt list too large ({len(term_list)} > {max_terms})")
    if any(len(term.strip()) == 0 for term in term_list):
        raise ValueError("prompt list contains blank entries")


def validate_phrase_set(payload: Mapping[str, object]) -> None:
    """Validate Google Speech Adaptation payload structure."""
    if "phraseSets" not in payload:
        raise ValueError("phraseSets missing from payload")
    phrase_sets = payload["phraseSets"]
    if not isinstance(phrase_sets, list) or not phrase_sets:
        raise ValueError("phraseSets must be a non-empty list")
    phrases = phrase_sets[0].get("phrases")
    if not isinstance(phrases, list):
        raise ValueError("phrases must be a list")
    for phrase in phrases:
        if "value" not in phrase or "boost" not in phrase:
            raise ValueError("phrase entries must include value and boost fields")


__all__ = ["validate_prompt_terms", "validate_phrase_set"]
