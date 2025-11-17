#!/usr/bin/env python3
"""Process multiple decks sequentially using the Python pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path

from asr_bias_builder.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch process multiple decks")
    parser.add_argument("decks", nargs="+", type=Path)
    parser.add_argument("--schema-file", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--summary-csv", type=Path, default=Path("pipeline_results/summary.csv"))
    parser.add_argument("--output-root", type=Path, default=Path("out"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for deck in args.decks:
        deck_output = args.output_root / deck.stem
        run_pipeline(
            deck_path=deck,
            output_dir=deck_output,
            summary_csv=args.summary_csv,
            config_path=args.config,
            schema_file=args.schema_file,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
