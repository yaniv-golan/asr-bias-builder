from __future__ import annotations

from asr_bias_builder.mining import mine


def test_mine_returns_seeds(sample_text: str) -> None:
    seeds, stats = mine(sample_text, min_freq=1, max_terms=20)
    assert len(seeds) > 0
    assert hasattr(stats, "stop_words")
