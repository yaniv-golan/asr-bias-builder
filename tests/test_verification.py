from __future__ import annotations

import json

from asr_bias_builder.verification import matcher


def test_consolidate_handles_aliases(sample_text: str) -> None:
    seeds = [{"term": "Dyson Sphere AI", "frequency": 2, "contexts": []}]
    llm_data = {
        "terms": [
            {"canonical": "Dyson Sphere AI", "classes": ["ORG"], "priority": 0.9, "present_in_deck": True}
        ]
    }
    payloads, stats = matcher.consolidate(sample_text, seeds, llm_data, allow_llm_aliases=False)
    assert payloads
    assert stats["llm_used"] >= 1
