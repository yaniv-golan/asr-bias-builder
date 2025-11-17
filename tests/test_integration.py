from __future__ import annotations

import json
from pathlib import Path

from asr_bias_builder.pipeline import run_pipeline


def test_run_pipeline_without_llm(tmp_path, sample_text):
    deck = tmp_path / "deck.txt"
    deck.write_text(sample_text, encoding="utf-8")
    out_dir = tmp_path / "out"
    summary = tmp_path / "summary.csv"
    # Create an empty LLM output file to skip the LLM stage
    llm_output = tmp_path / "llm_candidates.json"
    llm_output.write_text(json.dumps({"terms": []}), encoding="utf-8")
    run_pipeline(
        deck_path=deck,
        output_dir=out_dir,
        summary_csv=summary,
        config_path=Path("config/default.yml"),
        schema_file=None,
        llm_output=llm_output,
    )
    assert (out_dir / "deck_terms.txt").exists()
    assert summary.exists()
