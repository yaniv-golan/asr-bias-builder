"""End-to-end pipeline orchestration."""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.resources import as_file, files
from pathlib import Path
from typing import Iterable, List, Optional

from .artifacts.google_stt import build_phrase_set
from .artifacts.whisper import build_prompt
from .config import load_config
from .extraction import extract_text
from .llm.claude import run_claude
from .mining import mine
from .reporting.csv_export import append_summary_csv
from .reporting.summary import top_terms_by_class, write_review_markdown
from .utils import configure_logging, ensure_file, snapshot_environment, write_stats
from .verification import matcher
from .verification.deduplicator import append_aliases_file, collect_alias_suggestions

logger = logging.getLogger(__name__)
_SCHEMA_RESOURCE = files("asr_bias_builder.llm.prompts") / "schema.md"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@contextlib.contextmanager
def _resolved_schema_path(schema_file: Optional[Path]):
    if schema_file:
        yield schema_file
    else:
        with as_file(_SCHEMA_RESOURCE) as tmp_path:
            yield Path(tmp_path)


def run_pipeline(
    deck_path: Path,
    output_dir: Path,
    summary_csv: Path,
    config_path: Optional[Path] = None,
    llm_output: Optional[Path] = None,
    schema_file: Optional[Path] = None,
    model: str = "sonnet",
    permission_flags: Optional[List[str]] = None,
    enable_ocr: bool = False,
    chunk_size: int = 50_000,
    stream_threshold: int = 80_000,
    allow_llm_aliases: bool = False,
) -> None:
    """Run the ASR bias builder pipeline."""
    configure_logging()
    logger.info("Starting pipeline for deck %s", deck_path.name)
    logger.info("Writing artifacts to %s", output_dir)
    logger.info("Summary CSV will be stored at %s", summary_csv)
    cfg = load_config(str(config_path) if config_path else None)
    output_dir.mkdir(parents=True, exist_ok=True)
    deck_text_path = output_dir / "deck_text.txt"
    seeds_path = output_dir / "seeds.json"
    mine_stats_path = output_dir / "mine_terms_stats.json"
    verify_stats_path = output_dir / "verify_stats.json"
    llm_candidates_path = llm_output or (output_dir / "llm_candidates.json")
    verified_terms_path = output_dir / "verified_terms.json"
    prompt_list_path = output_dir / "deck_terms.txt"
    phrase_set_path = output_dir / "phrase_set.json"
    review_path = output_dir / "review.md"
    aliases_path = output_dir / "aliases_learned.yaml"

    logger.info("Stage 1/6: extracting deck text%s", " with OCR fallback enabled" if enable_ocr else "")
    text = extract_text(deck_path, enable_ocr=enable_ocr, config=cfg)
    deck_text_path.write_text(text, encoding="utf-8")
    logger.info("Stage 1 complete (%d characters)", len(text))

    logger.info("Stage 2/6: mining deterministic seeds")
    seeds, seed_stats = mine(text)
    _write_json(seeds_path, seeds)
    stats_payload = asdict(seed_stats)
    stats_payload["output_terms"] = len(seeds)
    write_stats(mine_stats_path, stats_payload)
    logger.info("Stage 2 complete (%d seeds)", len(seeds))

    llm_payload = None
    if llm_output is None or not llm_output.exists():
        logger.info("Stage 3/6: running LLM extraction (model=%s)", model)
        with _resolved_schema_path(schema_file) as resolved_schema:
            result = run_claude(
                deck_text=deck_text_path,
                schema_file=resolved_schema,
                output_path=llm_candidates_path,
                model=model,
                permission_flags=permission_flags,
                chunk_size=chunk_size,
                stream_threshold_bytes=stream_threshold,
            )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr.strip()}")
        llm_payload = matcher.load_json(llm_candidates_path)
        logger.info("Stage 3 complete (LLM candidates captured)")
    elif llm_candidates_path.exists():
        logger.info("Stage 3 skipped: using existing LLM candidates at %s", llm_candidates_path)
        llm_payload = matcher.load_json(llm_candidates_path)

    logger.info("Stage 4/6: verifying and consolidating terms")
    verified_terms, verify_stats = matcher.consolidate(
        deck_text=text,
        seeds_data=seeds,
        llm_data=llm_payload,
        allow_llm_aliases=allow_llm_aliases,
    )
    _write_json(verified_terms_path, verified_terms)
    verify_stats["output_terms"] = len(verified_terms)
    write_stats(verify_stats_path, verify_stats)
    logger.info("Stage 4 complete (%d verified terms)", len(verified_terms))

    logger.info("Stage 5/6: building ASR artifacts")
    prompt_terms = build_prompt(
        verified_terms,
        max_terms=int(cfg.get("max_prompt_terms", 120)),
        max_tokens=int(cfg.get("max_prompt_tokens", 200)),
        include_aliases=bool(cfg.get("include_aliases_in_prompt", False)),
    )
    prompt_list_path.write_text("\n".join(prompt_terms), encoding="utf-8")

    phrase_payload = build_phrase_set(
        verified_terms,
        default_boost=float(cfg.get("google_phrase_boost", 8.0)),
        include_aliases=bool(cfg.get("include_aliases_in_phrase_set", False)),
        max_phrases=int(cfg.get("phrase_set_max", 300)),
    )
    _write_json(phrase_set_path, phrase_payload)
    logger.info("Stage 5 complete (prompt terms=%d, phrase count=%d)", len(prompt_terms), len(phrase_payload["phraseSets"][0]["phrases"]))

    logger.info("Stage 6/6: generating reports and summaries")
    deck_id = str(cfg.get("deck_id", deck_path.stem))
    timestamp = datetime.now(timezone.utc).isoformat()
    write_review_markdown(
        deck_id=deck_id,
        deck_name=deck_path.name,
        output_dir=output_dir,
        metrics={"term_count": len(prompt_terms), "phrase_count": len(phrase_payload["phraseSets"][0]["phrases"])},
        mine_stats=stats_payload,
        verify_stats=verify_stats,
        top_terms=top_terms_by_class(verified_terms),
    )
    append_summary_csv(
        summary_csv,
        {
            "timestamp": timestamp,
            "deck_id": deck_id,
            "deck_name": deck_path.name,
            "term_count": len(prompt_terms),
            "phrase_count": len(phrase_payload["phraseSets"][0]["phrases"]),
            "seed_used": verify_stats.get("seed_used", 0),
            "seed_filtered": verify_stats.get("seed_filtered", 0),
            "llm_used": verify_stats.get("llm_used", 0),
            "llm_filtered": verify_stats.get("llm_filtered", 0),
            "llm_filtered_priority": verify_stats.get("llm_filtered_priority", 0),
            "fallback": verify_stats.get("fallback", False),
        },
    )

    suggestions = collect_alias_suggestions(verified_terms, matcher.KNOWN_ALIAS_VARIANTS)
    append_aliases_file(aliases_path, suggestions)

    freeze = subprocess.run(["pip", "freeze"], capture_output=True, text=True, check=False)
    snapshot_environment(output_dir / "pip-freeze.txt", freeze.stdout)
    logger.info("Pipeline finished for %s. Artifacts stored at %s", deck_path.name, output_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ASR bias builder pipeline")
    parser.add_argument("deck", type=Path, help="Input deck path (.pdf or .pptx)")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--summary-csv", type=Path)
    parser.add_argument("--config", type=Path, help="Optional config override")
    parser.add_argument("--llm-output", type=Path, help="Existing LLM candidates JSON")
    parser.add_argument("--schema-file", type=Path, help="System prompt schema for Claude CLI")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--permission-flag", action="append", dest="permission_flags")
    parser.add_argument("--enable-ocr", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=50_000)
    parser.add_argument("--stream-threshold", type=int, default=80_000)
    parser.add_argument("--allow-llm-aliases", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    deck_path = ensure_file(args.deck)
    run_pipeline(
        deck_path=deck_path,
        output_dir=args.output_dir or Path.cwd() / "asr-bias-output" / deck_path.stem,
        summary_csv=args.summary_csv or Path.cwd() / "asr-bias-summary.csv",
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
    return 0


__all__ = ["run_pipeline", "main"]
