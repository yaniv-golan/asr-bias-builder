#!/usr/bin/env python3
"""Measure deterministic pipeline timings."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from asr_bias_builder.extraction import extract_text
from asr_bias_builder.mining import mine
from asr_bias_builder.config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark extraction + mining stages")
    parser.add_argument("deck", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    start = time.perf_counter()
    text = extract_text(args.deck, config=cfg)
    mid = time.perf_counter()
    mine(text)
    end = time.perf_counter()
    print(f"extract={mid-start:.2f}s mine={end-mid:.2f}s total={end-start:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
