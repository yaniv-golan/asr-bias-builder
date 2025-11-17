# ASR Bias Artifacts – Quality Improvement Plan

## Implementation Status
- [x] Phase 1 – deterministic filtering, OCR normalization, telemetry
- [ ] Phase 2 – robustness & fallbacks
- [ ] Phase 3 – advanced enhancements

## Phase 1 – Deterministic Filtering & Telemetry (ASAP)
1. **OCR normalization in extraction**
   - Add context-aware fixups (e.g., AI→Al, Liam Nguyn→Liam Nguyen, Dyson Spher→Dyson Sphere) directly in `extract_deck_text.py` before emitting `deck_text.txt`.
2. **Stop word & number filtering**
   - Introduce English stop-word list and standalone-number rejection to `mine_terms.py`.
3. **Regex-based reject rules**
   - Drop Slack artifacts, timestamps, file paths, code tokens, and IDs via configurable regex patterns during seed mining.
4. **Config-driven alias map & deny list**
   - Extend `config.yml` with `ocr_aliases`, `stop_words`, and `deny_patterns`; load them in `verify_terms.py`/`mine_terms.py`.
5. **Class gating & length checks**
   - Ensure only PERSON/ORG/PRODUCT/TECH survive into artifacts; reject tokens shorter than 2 chars or longer than 50.
6. **Confidence-based Google boosts + caps**
   - Map term score→boost (10/8/6) and cap PhraseSet to ≤300 entries.
7. **Quality telemetry**
   - Log counts of filtered stop words, numbers, OCR fixes, reject-pattern hits, and final term totals to `run.log`.

## Phase 2 – Robustness & Fallbacks
1. **LLM-only mode when seeds fail**
   - Detect low overlap/high noise (e.g., seed/LLM ratio >20:1 or overlap <20%) and emit LLM terms only.
2. **Slide/section weighting (keyword heuristic)**
   - Tag high-value sections (team, benchmarks, product) and apply weights when counting term frequency.
3. **Fuzzy deduplication & alias merging**
   - Use configurable alias map plus `SequenceMatcher` to collapse near-duplicate canonical forms.
4. **Optional POS filter**
   - Behind config flag, keep only PROPN/NOUN tokens (spaCy/stanza) for decks that still show residual noise.

## Phase 3 – Advanced Enhancements
1. **Layout-aware section detection**
   - Use PDF layout cues (font size, position) to refine importance weights per slide.
2. **Embeddings-based semantic filtering**
   - Cluster similar terms and drop outliers that are semantically distant from deck topics.
3. **Hebrew/Multilingual expansion**
   - Add bilingual stop words, alias maps, and POS models for future mixed-language decks.
