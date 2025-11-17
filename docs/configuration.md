# Configuration Guide

Configuration is loaded from `config/default.yml` and optionally overridden via `BIAS_CONFIG_FILE` or `--config`.

Key sections:

- `stop_words`, `deny_patterns`, `deny_exact` – deterministic filters applied during mining/verification.
- `ocr_aliases`, `ocr_normalizations` – map OCR mistakes to canonical tokens.
- `high_value_classes`, `class_order`, `class_boost_floors` – control scoring/ordering in artifacts.
- `phrase_set_max`, `score_boosts`, `google_phrase_boost` – Google STT bias tuning.
- `use_titlecase_filter`, `pos_filter`, `pos_model` – heuristics to drop generic terms.
- `deck_overrides.<deck_id>` – per-deck deny lists and feature toggles.
- `section_keyword_weights` – heuristics for weighing high-value slides during mining.

Validate config structure against `config/schema.json`. Example overrides live in `config/examples/`.
