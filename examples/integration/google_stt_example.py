"""Example: attach PhraseSet payload to Google Speech Adaptation."""
from __future__ import annotations

import json
from pathlib import Path

PHRASE_SET = Path("../basic/expected_output/phrase_set.json")


def load_phrase_set() -> dict:
    return json.loads(PHRASE_SET.read_text(encoding="utf-8"))


def main() -> None:
    payload = load_phrase_set()
    print("Send this payload to google.cloud.speech_v2 adaptation API:\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
