# API Reference

## `asr_bias_builder.extraction`
- `extract_text(path, enable_ocr=False, config=None)` – Normalize PDF/PPTX decks.

## `asr_bias_builder.mining`
- `mine(text, min_freq=1, max_terms=500)` – Return candidate seeds and filter stats.

## `asr_bias_builder.llm`
- `run_claude(...)` – Invoke the Claude CLI (stdin vs. streaming automatically).
- `write_stream_file(deck_text, output_jsonl)` – Emit streaming JSONL payloads.

## `asr_bias_builder.verification`
- `consolidate(deck_text, seeds_data, llm_data, allow_llm_aliases)` – Merge deterministic + LLM terms.
- `TermRecord` – Intermediate scoring model.

## `asr_bias_builder.artifacts`
- `build_prompt(terms, max_terms, max_tokens, include_aliases)` – Whisper list.
- `build_phrase_set(terms, default_boost, include_aliases, max_phrases)` – Google STT payload.

## `asr_bias_builder.reporting`
- `write_review_markdown(...)` – Markdown summary per deck.
- `append_summary_csv(path, record)` – Cross-deck metrics.

See inline docstrings for detailed parameters and return types.
