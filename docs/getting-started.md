# Getting Started

1. Install Python 3.11+ and the dependencies listed in `requirements.txt`.
2. Install the Claude Code CLI (`claude`) and log in once interactively.
3. Clone this repo and run `pip install -e .`.
4. Execute the pipeline:

```bash
asr-bias-builder pipeline decks/sample.pdf
```

Artifacts appear in `./asr-bias-output/<deck-name>/`:
- `deck_text.txt` – normalized extraction
- `seeds.json` – deterministic candidates
- `llm_candidates.json` – Claude output (optional)
- `verified_terms.json` – merged + scored list
- `deck_terms.txt` – Whisper prompt
- `phrase_set.json` – Google Speech Adaptation payload
- `review.md` – human-readable summary
