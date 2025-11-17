#!/usr/bin/env python3
"""Generate per-run review markdown and summary CSV for bias artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..config import load_config
from .csv_export import append_summary_csv

CONFIG = load_config()
CLASS_ORDER = CONFIG.get("class_order", ["PERSON", "ORG", "PRODUCT", "TECH"])


def read_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_phrases(path: Path) -> int:
    data = read_json(path)
    if not data:
        return 0
    phrase_sets = data.get("phraseSets")
    if isinstance(phrase_sets, list) and phrase_sets:
        phrases = phrase_sets[0].get("phrases")
        if isinstance(phrases, list):
            return len(phrases)
    return 0


def top_terms_by_class(verified: List[Dict[str, object]], per_class: int = 5) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {cls: [] for cls in CLASS_ORDER}
    sorted_terms = sorted(verified, key=lambda item: item.get("score", 0), reverse=True)
    for item in sorted_terms:
        canonical = str(item.get("canonical", "")).strip()
        if not canonical:
            continue
        for cls in item.get("classes", []) or []:
            if cls not in buckets:
                buckets[cls] = []
            if len(buckets[cls]) < per_class:
                buckets[cls].append(canonical)
    return buckets


def write_review_markdown(
    deck_id: str,
    deck_name: str,
    output_dir: Path,
    metrics: Dict[str, object],
    mine_stats: Dict[str, object],
    verify_stats: Dict[str, object],
    top_terms: Dict[str, List[str]],
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Bias Review – {deck_name}",
        "",
        f"*Deck ID:* `{deck_id}`  |  *Generated:* {timestamp}",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Terms in prompt | {metrics['term_count']} |",
        f"| Phrases in PhraseSet | {metrics['phrase_count']} |",
        f"| Seed fallback triggered | {verify_stats.get('fallback', False)} |",
        f"| Seed terms kept | {verify_stats.get('seed_used', 0)} |",
        f"| LLM terms kept | {verify_stats.get('llm_used', 0)} |",
        "",
        "## Filter Stats",
        "",
        "| Filter | Count |",
        "| --- | --- |",
        f"| Stop words | {mine_stats.get('stop_words', 0)} |",
        f"| Numbers | {mine_stats.get('numbers', 0)} |",
        f"| Pattern rejects | {mine_stats.get('deny_patterns', 0)} |",
        f"| Length rejects | {mine_stats.get('length', 0)} |",
        f"| Section weighting hits | {mine_stats.get('section_weight_hits', 0)} |",
        f"| LLM priority drops | {verify_stats.get('llm_filtered_priority', 0)} |",
        "",
        "## Top Terms by Class",
        "",
    ]
    for cls in CLASS_ORDER:
        terms = top_terms.get(cls, [])
        if not terms:
            continue
        joined = ", ".join(terms)
        lines.append(f"- **{cls}:** {joined}")
    lines.append("")
    review_path = output_dir / "review.md"
    review_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate review artifacts for a deck run")
    parser.add_argument("--deck-id", required=True)
    parser.add_argument("--deck-name", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, required=True)
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    deck_terms = read_lines(output_dir / "deck_terms.txt")
    verified_raw = read_json(output_dir / "verified_terms.json")
    if isinstance(verified_raw, list):
        verified_terms = verified_raw
    else:
        verified_terms = []
    phrase_count = count_phrases(output_dir / "phrase_set.json")
    mine_stats = read_json(output_dir / "mine_terms_stats.json")
    verify_stats = read_json(output_dir / "verify_stats.json")
    metrics = {
        "term_count": len(deck_terms),
        "phrase_count": phrase_count,
    }
    write_review_markdown(
        args.deck_id,
        args.deck_name,
        output_dir,
        metrics,
        mine_stats,
        verify_stats,
        top_terms_by_class(verified_terms),
    )
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "deck_id": args.deck_id,
        "deck_name": args.deck_name,
        "term_count": len(deck_terms),
        "phrase_count": phrase_count,
        "seed_used": verify_stats.get("seed_used", 0),
        "seed_filtered": verify_stats.get("seed_filtered", 0),
        "llm_used": verify_stats.get("llm_used", 0),
        "llm_filtered": verify_stats.get("llm_filtered", 0),
        "llm_filtered_priority": verify_stats.get("llm_filtered_priority", 0),
        "fallback": verify_stats.get("fallback", False),
    }
    append_summary_csv(args.summary_csv, record)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
