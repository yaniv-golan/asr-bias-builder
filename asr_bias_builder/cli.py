"""Command-line interface for asr-bias-builder."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
import re
from pathlib import Path
from typing import Iterable, Optional

from . import __version__
from .artifacts.google_stt import build_phrase_set
from .artifacts.whisper import build_prompt
from .config import load_config
from .extraction import extract_text
from .mining import mine
from .pipeline import run_pipeline
from .verification import matcher


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def handle_extract(args: argparse.Namespace) -> None:
    cfg = load_config()
    text = extract_text(args.deck, enable_ocr=args.enable_ocr, config=cfg)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


def handle_mine(args: argparse.Namespace) -> None:
    text = args.deck_text.read_text(encoding="utf-8")
    seeds, stats = mine(text, min_freq=args.min_freq, max_terms=args.max_terms)
    _write_json(args.output, seeds)
    if args.stats:
        stats_dict = asdict(stats)
        stats_dict["output_terms"] = len(seeds)
        _write_json(args.stats, stats_dict)


def handle_verify(args: argparse.Namespace) -> None:
    deck_text = args.deck_text.read_text(encoding="utf-8")
    seeds = matcher.load_json(args.seeds)
    llm_data = matcher.load_json(args.llm)
    payloads, stats = matcher.consolidate(deck_text, seeds, llm_data, allow_llm_aliases=args.allow_llm_aliases)
    _write_json(args.output, payloads)
    if args.stats:
        stats["output_terms"] = len(payloads)
        _write_json(args.stats, stats)


def handle_prompt(args: argparse.Namespace) -> None:
    terms = json.loads(args.verified_terms.read_text(encoding="utf-8"))
    prompt_terms = build_prompt(
        terms,
        max_terms=args.max_terms,
        max_tokens=args.max_tokens,
        include_aliases=args.include_aliases,
    )
    args.output.write_text("\n".join(prompt_terms), encoding="utf-8")


def handle_phrase(args: argparse.Namespace) -> None:
    terms = json.loads(args.verified_terms.read_text(encoding="utf-8"))
    payload = build_phrase_set(
        terms,
        default_boost=args.boost,
        include_aliases=args.include_aliases,
        max_phrases=args.max_phrases,
    )
    _write_json(args.output, payload)


def _default_output_dir(deck: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", deck.stem).strip("_") or "deck"
    return Path.cwd() / "asr-bias-output" / safe


def handle_pipeline(args: argparse.Namespace) -> None:
    deck_path = args.deck
    output_dir = args.output_dir or _default_output_dir(deck_path)
    summary_csv = args.summary_csv or Path.cwd() / "asr-bias-summary.csv"
    run_pipeline(
        deck_path=deck_path,
        output_dir=output_dir,
        summary_csv=summary_csv,
        config_path=args.config,
        llm_output=args.llm_output,
        schema_file=args.schema_file,
        model=args.model,
        permission_flags=args.permission_flags,
        enable_ocr=args.enable_ocr,
        chunk_size=args.chunk_size,
        stream_threshold=args.stream_threshold,
        allow_llm_aliases=args.allow_llm_aliases,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asr-bias-builder",
        description="ASR Bias Builder CLI – extract deck text, run LLM verification, and emit ASR bias artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_p = subparsers.add_parser(
        "extract",
        help="Extract normalized deck text",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    extract_p.add_argument("deck", type=Path, help="PDF/PPTX source to extract text from")
    extract_p.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Allow OCR fallback when the deck has no text layer",
    )
    extract_p.add_argument("--output", type=Path, help="Where to write deck_text.txt (defaults to stdout)")
    extract_p.set_defaults(func=handle_extract)

    mine_p = subparsers.add_parser(
        "mine",
        help="Mine deterministic seed terms",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    mine_p.add_argument("deck_text", type=Path, help="Path to deck_text.txt from extraction step")
    mine_p.add_argument("--min-freq", type=int, default=1, help="Minimum term frequency to keep")
    mine_p.add_argument("--max-terms", type=int, default=500, help="Maximum number of seeds to emit")
    mine_p.add_argument("--output", type=Path, default=Path("seeds.json"), help="Where to write seeds.json")
    mine_p.add_argument("--stats", type=Path, help="Optional JSON stats file for filter counters")
    mine_p.set_defaults(func=handle_mine)

    verify_p = subparsers.add_parser(
        "verify",
        help="Verify LLM output against deck text",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    verify_p.add_argument("--deck-text", type=Path, required=True, help="deck_text.txt emitted by extraction")
    verify_p.add_argument("--seeds", type=Path, help="Optional deterministic seeds JSON (seeds.json)")
    verify_p.add_argument("--llm", type=Path, help="LLM candidates JSON (llm_candidates.json)")
    verify_p.add_argument(
        "--allow-llm-aliases",
        action="store_true",
        help="Keep LLM terms even when no exact deck match exists (trust alias variants)",
    )
    verify_p.add_argument("--output", type=Path, default=Path("verified_terms.json"), help="Where to write verified_terms.json")
    verify_p.add_argument("--stats", type=Path, help="Optional JSON stats file for verification counters")
    verify_p.set_defaults(func=handle_verify)

    prompt_p = subparsers.add_parser(
        "prompt",
        help="Build Whisper prompt list",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    prompt_p.add_argument("verified_terms", type=Path, help="verified_terms.json emitted by verify step")
    prompt_p.add_argument("--max-terms", type=int, default=120, help="Maximum number of terms to include")
    prompt_p.add_argument("--max-tokens", type=int, default=200, help="Approximate token budget for Whisper")
    prompt_p.add_argument(
        "--include-aliases",
        action="store_true",
        help="Allow alias-only entries (not present in deck) into the prompt list",
    )
    prompt_p.add_argument("--output", type=Path, default=Path("deck_terms.txt"), help="Text file for Whisper prompt terms")
    prompt_p.set_defaults(func=handle_prompt)

    phrase_p = subparsers.add_parser(
        "phraseset",
        help="Build Google STT phrase set",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    phrase_p.add_argument("verified_terms", type=Path, help="verified_terms.json emitted by verify step")
    phrase_p.add_argument("--boost", type=float, default=8.0, help="Default boost to apply to phrases")
    phrase_p.add_argument("--max-phrases", type=int, default=300, help="Maximum phrases to include")
    phrase_p.add_argument(
        "--include-aliases",
        action="store_true",
        help="Allow alias-only entries into the PhraseSet",
    )
    phrase_p.add_argument("--output", type=Path, default=Path("phrase_set.json"), help="Destination JSON file for PhraseSet")
    phrase_p.set_defaults(func=handle_phrase)

    pipe_p = subparsers.add_parser(
        "pipeline",
        help="Run the full deterministic + LLM pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    pipe_p.add_argument("deck", type=Path, help="PDF/PPTX deck to process")
    pipe_p.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for artifacts (defaults to ./asr-bias-output/<deck-stem>)",
    )
    pipe_p.add_argument(
        "--summary-csv",
        type=Path,
        help="CSV path to append run summaries (defaults to ./asr-bias-summary.csv)",
    )
    pipe_p.add_argument("--config", type=Path, help="Optional YAML config override")
    pipe_p.add_argument(
        "--llm-output",
        type=Path,
        help="Reuse an existing llm_candidates.json instead of calling Claude",
    )
    pipe_p.add_argument(
        "--schema-file",
        type=Path,
        help="Custom system prompt/schema for Claude (omit to use the packaged default)",
    )
    pipe_p.add_argument("--model", default="sonnet", help="Claude model alias/name (sonnet, opus, etc.)")
    pipe_p.add_argument(
        "--permission-flag",
        dest="permission_flags",
        action="append",
        help="Additional flags to pass to the Claude CLI (repeat as needed)",
    )
    pipe_p.add_argument("--enable-ocr", action="store_true", help="Allow OCR fallback for image-only PDFs")
    pipe_p.add_argument("--chunk-size", type=int, default=50_000, help="Chunk size for streaming inputs (bytes)")
    pipe_p.add_argument(
        "--stream-threshold",
        type=int,
        default=80_000,
        help="Switch to streaming mode when deck_text exceeds this many bytes",
    )
    pipe_p.add_argument(
        "--allow-llm-aliases",
        action="store_true",
        help="Keep LLM entries even if no exact match in deck (trust alias heuristics)",
    )
    pipe_p.set_defaults(func=handle_pipeline)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


__all__ = ["main", "build_parser"]
