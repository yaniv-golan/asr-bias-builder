#!/usr/bin/env python3
"""Build Whisper prompt/hotword list from verified terms."""
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
USE_TITLECASE_FILTER = bool(CONFIG.get("use_titlecase_filter", False))
ACRONYM_MIN_LENGTH = int(CONFIG.get("acronym_min_length", 2))
CLASS_ORDER = CONFIG.get("class_order", ["PERSON", "ORG", "PRODUCT", "TECH"])
CLASS_PRIORITY = {label: idx for idx, label in enumerate(CLASS_ORDER)}
POS_FILTER_ENABLED = bool(CONFIG.get("pos_filter", False))
POS_MODEL = str(CONFIG.get("pos_model", "en_core_web_sm"))
POS_VALID_TAGS = set(CONFIG.get("pos_valid_tags", ["PROPN", "NOUN", "X"]))
_POS_PIPE = None
_POS_READY = None


def estimate_tokens(term: str) -> int:
    return max(1, len(term.split()))


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
            print(f"[build_prompt_list] POS filter disabled: {exc}", file=sys.stderr)
            _POS_READY = False
            POS_FILTER_ENABLED = False
            return True
    doc = _POS_PIPE(term)
    return any(token.pos_ in POS_VALID_TAGS for token in doc)


def is_high_value_term(item: dict, include_aliases: bool) -> bool:
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


def get_class_priority(classes: List[str]) -> int:
    for label in CLASS_ORDER:
        if label in classes:
            return CLASS_PRIORITY[label]
    return len(CLASS_ORDER)


def build_prompt(terms: List[dict], max_terms: int, max_tokens: int, include_aliases: bool) -> List[str]:
    eligible = []
    dropped = 0
    dropped_titlecase = 0
    dropped_pos = 0
    for item in terms:
        canonical = str(item.get("canonical", "")).strip()
        if not canonical:
            dropped += 1
            continue
        if USE_TITLECASE_FILTER and not is_titlecase_term(canonical):
            dropped_titlecase += 1
            continue
        if POS_FILTER_ENABLED and not passes_pos_filter(canonical):
            dropped_pos += 1
            dropped += 1
            continue
        if not is_high_value_term(item, include_aliases):
            dropped += 1
            continue
        eligible.append(item)

    eligible.sort(
        key=lambda item: (
            get_class_priority(item.get("classes", []) or []),
            -float(item.get("score", 0)),
            str(item.get("canonical", "")).lower(),
        )
    )

    chosen: List[str] = []
    token_budget = 0
    for item in eligible:
        if len(chosen) >= max_terms:
            break
        canonical = str(item["canonical"]).strip()
        tokens = estimate_tokens(canonical)
        if token_budget + tokens > max_tokens:
            continue
        chosen.append(canonical)
        token_budget += tokens
    print(
        "[build_prompt_list] stats kept={kept} dropped={dropped} titlecase_dropped={titlecase} pos_dropped={pos} token_budget={tokens}".format(
            kept=len(chosen), dropped=dropped, titlecase=dropped_titlecase, pos=dropped_pos, tokens=token_budget
        ),
        file=sys.stderr,
    )
    return chosen


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build Whisper prompt/hotword list")
    parser.add_argument("verified_terms", type=Path)
    parser.add_argument("--max-terms", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--include-aliases", action="store_true", help="Allow alias-only terms (not present in deck)")
    args = parser.parse_args(argv)

    terms = load_terms(args.verified_terms)
    prompt_terms = build_prompt(terms, args.max_terms, args.max_tokens, args.include_aliases)
    print("\n".join(prompt_terms))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
