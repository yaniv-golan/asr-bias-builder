from __future__ import annotations

from asr_bias_builder.artifacts.google_stt import build_phrase_set
from asr_bias_builder.artifacts.whisper import build_prompt


def test_build_prompt_limited(verified_terms: list[dict[str, object]]) -> None:
    prompt = build_prompt(verified_terms, max_terms=10, max_tokens=40, include_aliases=False)
    assert 0 < len(prompt) <= 10


def test_build_phrase_set_structure(verified_terms: list[dict[str, object]]) -> None:
    payload = build_phrase_set(verified_terms, default_boost=8.0, include_aliases=False, max_phrases=20)
    assert "phraseSets" in payload
    assert payload["phraseSets"][0]["phrases"]
