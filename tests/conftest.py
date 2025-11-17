from __future__ import annotations

import json
from pathlib import Path

import pytest

from asr_bias_builder.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_text() -> str:
    return (FIXTURES / "sample_deck.txt").read_text(encoding="utf-8")


@pytest.fixture()
def verified_terms() -> list[dict[str, object]]:
    return json.loads((FIXTURES / "expected_output.json").read_text(encoding="utf-8"))


@pytest.fixture()
def config_dict() -> dict:
    return load_config(str(FIXTURES / "config_test.yml"))
