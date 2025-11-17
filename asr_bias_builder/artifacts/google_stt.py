#!/usr/bin/env python3
"""Build Google STT v2 Speech Adaptation PhraseSet from verified terms."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from ..config import load_config

CONFIG = load_config()
ALLOWED_CLASSES = set(CONFIG.get("high_value_classes", []))
STOP_WORDS = {w.lower() for w in CONFIG.get("stop_words", [])}
MIN_TERM_LENGTH = int(CONFIG.get("min_term_length", 2))
MAX_TERM_LENGTH = int(CONFIG.get("max_term_length", 50))
DENY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CONFIG.get("deny_patterns", [])]
DENY_EXACT = {s.lower() for s in CONFIG.get("deny_exact", [])}
PHRASE_MAX = int(CONFIG.get("phrase_set_max", 300))
SCORE_BOOSTS = sorted(CONFIG.get("score_boosts", []), key=lambda x: x.get("threshold", 0), reverse=True)
USE_TITLECASE_FILTER = bool(CONFIG.get("use_titlecase_filter", False))
ACRONYM_MIN_LENGTH = int(CONFIG.get("acronym_min_length", 2))
CLASS_BOOST_FLOORS = {k: float(v) for k, v in CONFIG.get("class_boost_floors", {}).items()}
POS_FILTER_ENABLED = bool(CONFIG.get("pos_filter", False))
POS_MODEL = str(CONFIG.get("pos_model", "en_core_web_sm"))
POS_VALID_TAGS = set(CONFIG.get("pos_valid_tags", ["PROPN", "NOUN", "X"]))
_POS_PIPE = None
_POS_READY = None


def load_terms(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("verified_terms.json must contain a list")
    return data


def is_titlecase_term(term: str) -> bool:
    if not USE_TITLECASE_FILTER:
        return True
    tokens = [tok for tok in re.split(r"[^A-Za-z0-9#]+", term) if tok]
    for token in tokens:
        sanitized = token.replace("#", "")
        if not sanitized:
            continue
        if len(sanitized) >= ACRONYM_MIN_LENGTH and sanitized.isupper():
            return True
        if token[0].isupper() and any(ch.islower() for ch in token[1:]):
            return True
        if token[0].isupper() and any(ch.isupper() for ch in token[1:]) and any(ch.islower() for ch in token[1:]):
            return True
    return False


def passes_pos_filter(term: str) -> bool:
    global _POS_PIPE, _POS_READY, POS_FILTER_ENABLED
    if not POS_FILTER_ENABLED:
        return True
    if _POS_READY is False:
        return True
    if _POS_PIPE is None:
        try:
            import spacy  # type: ignore

            _POS_PIPE = spacy.load(POS_MODEL)
            _POS_READY = True
        except Exception as exc:  # pragma: no cover
            print(f"[build_phrase_set] POS filter disabled: {exc}", file=sys.stderr)
            _POS_READY = False
            POS_FILTER_ENABLED = False
            return True
    doc = _POS_PIPE(term)
    return any(token.pos_ in POS_VALID_TAGS for token in doc)


def is_high_value_phrase(item: dict, include_aliases: bool) -> bool:
    canonical = str(item.get("canonical", "")).strip()
    if not canonical:
        return False
    if len(canonical) < MIN_TERM_LENGTH or len(canonical) > MAX_TERM_LENGTH:
        return False
    if canonical.lower() in STOP_WORDS:
        return False
    if canonical.lower() in DENY_EXACT:
        return False
    if any(pattern.search(canonical) for pattern in DENY_PATTERNS):
        return False
    if not item.get("present_in_deck", False) and not include_aliases:
        return False
    classes = item.get("classes", []) or []
    if not classes:
        return False
    if not set(classes).intersection(ALLOWED_CLASSES):
        return False
    return True


def score_to_boost(score: float, default_boost: float) -> float:
    for rule in SCORE_BOOSTS:
        threshold = rule.get("threshold")
        boost = rule.get("boost")
        if threshold is None or boost is None:
            continue
        if score >= float(threshold):
            return float(boost)
    return default_boost


def apply_class_boost_floor(boost: float, classes: List[str]) -> float:
    adjusted = boost
    for cls in classes:
        floor = CLASS_BOOST_FLOORS.get(cls)
        if floor:
            adjusted = max(adjusted, floor)
    return min(adjusted, 20.0)


def build_phrase_set(terms: List[dict], default_boost: float, include_aliases: bool, max_phrases: Optional[int] = None) -> dict:
    if not (0 < default_boost <= 20):
        raise ValueError("boost must be within (0, 20]")
    phrases = []
    dropped = 0
    dropped_titlecase = 0
    limit = min(max_phrases or PHRASE_MAX, PHRASE_MAX)
    for item in sorted(terms, key=lambda t: t.get("score", 0), reverse=True):
        if len(phrases) >= limit:
            break
        canonical = str(item.get("canonical", "")).strip()
        if USE_TITLECASE_FILTER and not is_titlecase_term(canonical):
            dropped_titlecase += 1
            continue
        if POS_FILTER_ENABLED and not passes_pos_filter(canonical):
            dropped += 1
            continue
        if not is_high_value_phrase(item, include_aliases):
            dropped += 1
            continue
        canonical = str(item["canonical"]).strip()
        boost = score_to_boost(float(item.get("score", 0)), default_boost)
        boost = apply_class_boost_floor(boost, item.get("classes", []) or [])
        if boost <= 0:
            continue
        phrases.append({"value": canonical, "boost": boost})
    print(
        f"[build_phrase_set] stats kept={len(phrases)} dropped={dropped} titlecase_dropped={dropped_titlecase} max={limit}",
        file=sys.stderr,
    )
    return {"phraseSets": [{"phrases": phrases}]}


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build Google STT v2 phrase_set.json")
    parser.add_argument("verified_terms", type=Path)
    parser.add_argument("--boost", type=float, default=8.0)
    parser.add_argument("--max-phrases", type=int, default=500)
    parser.add_argument("--include-aliases", action="store_true")
    args = parser.parse_args(argv)

    terms = load_terms(args.verified_terms)
    payload = build_phrase_set(terms, args.boost, args.include_aliases, args.max_phrases)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
