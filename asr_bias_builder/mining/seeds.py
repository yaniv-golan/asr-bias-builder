#!/usr/bin/env python3
"""Mine candidate seed terms from deterministic deck text."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .filters import (
    DEFAULT_SECTION_WEIGHT,
    DENY_EXACT,
    FilterStats,
    MAX_TERM_LENGTH,
    MIN_TERM_LENGTH,
    USE_SECTION_WEIGHTING,
    detect_section_weight,
    extract_candidates_from_line,
    is_number_like,
    is_stop_word,
    matches_deny_pattern,
    normalize_term,
)

MAX_CONTEXT_CHARS = 80


def build_contexts(text: str, terms: Iterable[str]) -> Dict[str, List[str]]:
    contexts: Dict[str, List[str]] = defaultdict(list)
    lowered = text.lower()
    for term in terms:
        term_clean = term.strip()
        if not term_clean:
            continue
        idx = lowered.find(term_clean.lower())
        if idx == -1:
            continue
        start = max(0, idx - MAX_CONTEXT_CHARS // 2)
        end = min(len(text), idx + len(term_clean) + MAX_CONTEXT_CHARS // 2)
        snippet = text[start:end].replace("\n", " ")
        contexts[term_clean].append(snippet.strip())
    return contexts


def mine(text: str, min_freq: int = 1, max_terms: int = 500) -> (List[Dict[str, object]], FilterStats):
    stats = FilterStats()
    counter: Counter[str] = Counter()
    current_weight = DEFAULT_SECTION_WEIGHT
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        current_weight = detect_section_weight(line, current_weight, stats)
        weight = current_weight if USE_SECTION_WEIGHTING else DEFAULT_SECTION_WEIGHT
        for token in extract_candidates_from_line(line):
            term = normalize_term(token)
            if not term:
                continue
            if len(term) < MIN_TERM_LENGTH or len(term) > MAX_TERM_LENGTH:
                stats.length += 1
                stats.total_filtered += 1
                continue
            if is_stop_word(term):
                stats.stop_words += 1
                stats.total_filtered += 1
                continue
            if term.lower() in DENY_EXACT:
                stats.deny_patterns += 1
                stats.total_filtered += 1
                continue
            if is_number_like(term):
                stats.numbers += 1
                stats.total_filtered += 1
                continue
            if matches_deny_pattern(term):
                stats.deny_patterns += 1
                stats.total_filtered += 1
                continue
            counter[term] += weight

    filtered = [t for t, c in counter.most_common() if c >= min_freq]
    contexts = build_contexts(text, filtered)
    seeds: List[Dict[str, object]] = []
    for term in filtered[:max_terms]:
        seeds.append(
            {
                "term": term,
                "frequency": counter[term],
                "contexts": contexts.get(term, [])[:3],
            }
        )
    stats.log(len(seeds))
    return seeds, stats


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mine deterministic seed terms from deck text")
    parser.add_argument("deck_text", type=Path, help="Path to deck_text.txt")
    parser.add_argument("--min-freq", type=int, default=1)
    parser.add_argument("--max-terms", type=int, default=500)
    parser.add_argument("--stats-file", type=Path)
    args = parser.parse_args(argv)

    text = args.deck_text.read_text(encoding="utf-8")
    seeds, stats = mine(text, min_freq=args.min_freq, max_terms=args.max_terms)
    if args.stats_file:
        report = stats.__dict__.copy()
        report["output_terms"] = len(seeds)
        args.stats_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    json.dump(seeds, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
