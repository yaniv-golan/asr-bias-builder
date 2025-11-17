"""CSV export helpers for pipeline summaries."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict


def append_summary_csv(summary_csv: Path, record: Dict[str, object]) -> None:
    """Append a single run's metrics to the shared CSV file."""
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "deck_id",
        "deck_name",
        "term_count",
        "phrase_count",
        "seed_used",
        "seed_filtered",
        "llm_used",
        "llm_filtered",
        "llm_filtered_priority",
        "fallback",
    ]
    needs_header = not summary_csv.exists()
    with summary_csv.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if needs_header:
            writer.writeheader()
        writer.writerow(record)


__all__ = ["append_summary_csv"]
