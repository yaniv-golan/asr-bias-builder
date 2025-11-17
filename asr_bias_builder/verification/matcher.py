#!/usr/bin/env python3
"""Verify LLM terms against deterministic deck text and consolidate seeds."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..config import load_config
from .deduplicator import append_aliases_file, collect_alias_suggestions
from .scorer import TermRecord, assess_seed_quality

CONFIG = load_config()
STOP_WORDS = {w.lower() for w in CONFIG.get("stop_words", [])}
ALLOWED_CLASSES = set(CONFIG.get("high_value_classes", []))
MIN_TERM_LENGTH = int(CONFIG.get("min_term_length", 2))
MAX_TERM_LENGTH = int(CONFIG.get("max_term_length", 50))
DENY_EXACT = {s.lower() for s in CONFIG.get("deny_exact", [])}
ALIAS_MAP = {
    variant.lower(): canonical
    for canonical, variants in CONFIG.get("ocr_aliases", {}).items()
    for variant in variants
}
KNOWN_ALIAS_VARIANTS = set(ALIAS_MAP.keys())
USE_LLM_PRIORITY_THRESHOLD = bool(CONFIG.get("use_llm_priority_threshold", False))
LLM_PRIORITY_THRESHOLD = float(CONFIG.get("llm_priority_threshold", 0.75))


def sanitize_json_text(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        raw = "\n".join(lines).strip()
    # If Claude prepended prose, strip everything before the first JSON object/array
    match = re.search(r"([\[{].*)", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    return raw


def load_json(path: Optional[Path]) -> Optional[object]:
    if not path or not path.exists():
        return None
    raw = sanitize_json_text(path.read_text(encoding="utf-8"))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw)
        return obj


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def canonicalize(term: str) -> str:
    return ALIAS_MAP.get(term.lower(), term)


def is_allowed_term(term: str) -> bool:
    if len(term) < MIN_TERM_LENGTH or len(term) > MAX_TERM_LENGTH:
        return False
    if term.lower() in STOP_WORDS:
        return False
    if term.lower() in DENY_EXACT:
        return False
    return True


def classes_allowed(classes: List[str]) -> bool:
    if not classes:
        return True
    return bool(set(classes).intersection(ALLOWED_CLASSES))


def count_occurrences(text_lower: str, term: str) -> int:
    if not term:
        return 0
    pattern = re.escape(term.lower())
    return len(re.findall(pattern, text_lower))


def detect_presence(text_lower: str, canonical: str, variants: Iterable[str]) -> Tuple[bool, int, Optional[str]]:
    total_freq = count_occurrences(text_lower, canonical)
    if total_freq:
        return True, total_freq, canonical
    for variant in variants:
        freq = count_occurrences(text_lower, variant)
        if freq:
            return True, freq, variant
    return False, 0, None


def log_stats(message: str) -> None:
    print(f"[verify_terms] {message}", file=sys.stderr)


def consolidate(
    deck_text: str,
    seeds_data: Optional[List[Dict[str, object]]],
    llm_data: Optional[object],
    allow_llm_aliases: bool,
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    text_lower = deck_text.lower()
    records: Dict[str, TermRecord] = {}
    stats = {
        "seed_used": 0,
        "seed_filtered": 0,
        "llm_used": 0,
        "llm_filtered": 0,
        "llm_filtered_priority": 0,
        "fallback": False,
    }

    llm_terms: List[Dict[str, object]] = []
    if isinstance(llm_data, list):
        llm_terms = llm_data
    elif isinstance(llm_data, dict):
        terms = llm_data.get("terms")
        if isinstance(terms, list):
            llm_terms = terms

    use_llm_only, quality_stats = assess_seed_quality(seeds_data, llm_terms, canonicalize, normalize)
    stats["fallback"] = use_llm_only
    log_stats(
        "seed_quality ratio={ratio:.2f} overlap={overlap:.2%} fallback={fallback}".format(
            ratio=quality_stats.get("seed_llm_ratio", 0.0),
            overlap=quality_stats.get("overlap_ratio", 0.0),
            fallback=use_llm_only,
        )
    )

    if seeds_data and not use_llm_only:
        for entry in seeds_data:
            term = canonicalize(normalize(str(entry.get("term", ""))))
            if not term or not is_allowed_term(term):
                stats["seed_filtered"] += 1
                continue
            freq = int(entry.get("frequency", 1))
            record = records.setdefault(term.lower(), TermRecord(canonical=term, source="seed"))
            record.frequency = max(record.frequency, freq)
            record.present_in_deck = True
            record.priority = max(record.priority, 0.6)
            stats["seed_used"] += 1

    for entry in llm_terms:
        canonical = canonicalize(normalize(str(entry.get("canonical", ""))))
        if not canonical:
            stats["llm_filtered"] += 1
            continue
        if not is_allowed_term(canonical):
            stats["llm_filtered"] += 1
            continue
        variants = [canonicalize(normalize(v)) for v in entry.get("variants", []) if isinstance(v, str)]
        classes = [c for c in entry.get("classes", []) if isinstance(c, str)]
        if not classes_allowed(classes):
            stats["llm_filtered"] += 1
            continue
        priority = float(entry.get("priority", 0.5))
        present_flag = bool(entry.get("present_in_deck", False))

        if (
            USE_LLM_PRIORITY_THRESHOLD
            and priority < LLM_PRIORITY_THRESHOLD
            and not {"PERSON", "ORG"}.intersection(classes)
        ):
            stats["llm_filtered_priority"] += 1
            continue

        present, freq, matched_variant = detect_presence(text_lower, canonical, variants)
        if not present and not allow_llm_aliases:
            stats["llm_filtered"] += 1
            continue
        record = records.setdefault(canonical.lower(), TermRecord(canonical=canonical, source="llm"))
        record.source = "seed+llm" if record.source == "seed" else "llm"
        record.priority = max(record.priority, priority)
        record.classes = sorted(set(record.classes + classes))
        record.variants.extend([v for v in variants if v and v.lower() != canonical.lower()])
        record.present_in_deck = present or present_flag
        record.frequency = max(record.frequency, freq)
        if not present and allow_llm_aliases:
            record.notes = "Alias not found in deck"
        elif matched_variant and matched_variant.lower() != canonical.lower():
            record.notes = f"Matched variant: {matched_variant}"
        stats["llm_used"] += 1

    payloads = [rec.to_payload() for rec in records.values()]
    payloads.sort(key=lambda item: (item["score"], item["frequency"], item["canonical"]), reverse=True)
    log_stats(
        "usage seeds_used={seed_used} seeds_filtered={seed_filtered} "
        "llm_used={llm_used} llm_filtered={llm_filtered} "
        "llm_filtered_priority={llm_filtered_priority} fallback={fallback} output_terms={output}".format(
            seed_used=stats["seed_used"],
            seed_filtered=stats["seed_filtered"],
            llm_used=stats["llm_used"],
            llm_filtered=stats["llm_filtered"],
            llm_filtered_priority=stats["llm_filtered_priority"],
            fallback=stats["fallback"],
            output=len(payloads),
        )
    )
    return payloads, stats


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify LLM terms and merge with deterministic seeds")
    parser.add_argument("--deck-text", type=Path, required=True)
    parser.add_argument("--seeds", type=Path)
    parser.add_argument("--llm", type=Path)
    parser.add_argument("--allow-llm-aliases", action="store_true")
    parser.add_argument("--stats-file", type=Path)
    parser.add_argument("--learned-aliases", type=Path)
    args = parser.parse_args(argv)

    deck_text = args.deck_text.read_text(encoding="utf-8")
    seeds = load_json(args.seeds)
    llm = load_json(args.llm)
    payloads, stats = consolidate(deck_text, seeds, llm, allow_llm_aliases=args.allow_llm_aliases)
    if args.stats_file:
        report = stats.copy()
        report["output_terms"] = len(payloads)
        args.stats_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.learned_aliases:
        suggestions = collect_alias_suggestions(payloads, KNOWN_ALIAS_VARIANTS)
        append_aliases_file(args.learned_aliases, suggestions)
    json.dump(payloads, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
