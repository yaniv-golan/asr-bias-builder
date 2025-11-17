from __future__ import annotations

from pathlib import Path

from asr_bias_builder.extraction import normalize_text


def test_normalize_text(sample_text: str) -> None:
    normalized = normalize_text(sample_text)
    assert "\n" not in normalized.strip().split(" ")[0]
    assert len(normalized) > 10
