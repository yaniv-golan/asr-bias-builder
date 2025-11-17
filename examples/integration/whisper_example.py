"""Example: apply deck terms to a Whisper API request."""
from __future__ import annotations

from pathlib import Path

PROMPT_FILE = Path("../basic/expected_output/deck_terms.txt")


def build_initial_prompt() -> str:
    terms = [line.strip() for line in PROMPT_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return ", ".join(terms[:75])


def main() -> None:
    prompt = build_initial_prompt()
    print("Pass this prompt to your Whisper transcription request:\n")
    print(prompt)


if __name__ == "__main__":
    main()
