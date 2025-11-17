# CLI Reference

```
asr-bias-builder <command> [options]
```

Commands:
- `extract` – `asr-bias-builder extract deck.pdf --enable-ocr --output out/deck_text.txt`
- `mine` – `asr-bias-builder mine out/deck_text.txt --output out/seeds.json --stats out/mine_stats.json`
- `verify` – `asr-bias-builder verify --deck-text out/deck_text.txt --seeds out/seeds.json --llm out/lmm_candidates.json`
- `prompt` – `asr-bias-builder prompt out/verified_terms.json --output out/deck_terms.txt`
- `phraseset` – `asr-bias-builder phraseset out/verified_terms.json --output out/phrase_set.json`
- `pipeline` – Runs the entire flow end-to-end (wraps the commands above plus review generation). Uses the packaged schema by default; pass `--schema-file` only when you need a custom one.

Environment variables honored by scripts:
- `BIAS_CONFIG_FILE` – Custom YAML config path
- `BIAS_DECK_ID` – Deck identifier for overrides
- `MODEL`, `PERMISSION_FLAGS`, `STREAM_THRESHOLD_BYTES` – pass-through to Claude CLI helpers
