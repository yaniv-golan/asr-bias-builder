# ASR Bias Artifacts – Phase 2 Enhancements
**Date:** 2025‑11‑17  
**Goal:** Lift output quality from ⭐⭐⭐⭐ → ⭐⭐⭐⭐⭐ by implementing the highest‑impact follow‑ups identified during multi-deck testing.

---
## Summary of Findings
| Deck Alpha | 48 | Remaining noise: UI artifacts and Slack detritus |
| Deck Beta | 41 | Clean, but people/ORG ordering suboptimal |
| Deck Gamma | 95 | Accurate but generic nouns (“fuel cost”) still present |
| Deck Delta | 67 | Good coverage; ordering could improve |
| Deck Epsilon | 56 | Includes generic business phrases (“seed stage”) |
| Deck Zeta | 63 | People names not prioritized; industry jargon mixed with fluff |

Evidence: `pipeline_results/*/deck_terms.txt` shows residual lower-case phrases, while `phrase_set.json` reveals PERSON entries with boosts of 6.0/8.0 instead of 10.0.

---
## Phase 2 Workstreams

### 1. Class-Specific Boost Floors & Ordering
_Status: Completed – build_prompt_list.py and build_phrase_set.py enforce class ordering + boost floors (2025-11-17)._ 
**Rationale:** People names (founders, investors, customers) must always be recognized. Current boost mapping can drop to 6.0 if their computed score <0.85. Whisper also benefits when names lead the prompt.  
**Tasks:**
1. In `build_phrase_set.py`, enforce `if "PERSON" in classes → boost = max(boost, 10.0)`; `ORG → ≥8.0`.  
2. In `build_prompt_list.py`, sort verified terms by class priority: PERSON > ORG > PRODUCT > TECH, preserving score order within each bucket.  
3. Update telemetry to log how many terms were elevated.  
**Evidence:** `pipeline_results/deck_zeta.../phrase_set.json` lines 80+ show people at boost 6.0; `deck_terms.txt` has people scattered near mid-section.

### 2. Title-Case / POS Filtering (config-gated)
_Status: Completed – title-case heuristics plus optional spaCy POS filtering wired into build_prompt_list.py/build_phrase_set.py._
**Rationale:** Lower-case generics (“traffic management”, “fuel cost”, “logistics providers”) persist because they pass class filtering. Title-case (or POS PROPN) is a strong proxy for entities without heavy NLP dependencies.  
**Tasks:**
1. Add a config flag `use_titlecase_filter`. When true, retain terms if they contain ≥1 title-case token or uppercase acronym.  
2. Optional: integrate spaCy POS tagging behind `pos_filter=true`. Keep PROPN, X; optionally whitelist domain nouns via config (e.g., “Fleet Management”).  
3. Log filtered counts to telemetry.  
**Evidence:** `pipeline_results/deck_gamma/deck_terms.txt` lines 1‑20 highlight lower-case phrases despite being low-value for ASR.

### 3. Deck-Specific Overrides (deny lists)
_Status: Completed – config.yml contains per-deck overrides merged via BIAS_DECK_ID in config.py._
**Rationale:** Some decks mention domain-specific fluff (e.g., “seed stage” in Deck Zeta, “Slack” in Deck Alpha). A per-deck deny list lets ops clean output without code changes.  
**Tasks:**
1. Extend `config.yml` with `deck_overrides.<deck_id>.deny_exact/deny_patterns`.  
2. Identify deck ID by sanitized file name (e.g., `deck_zeta`). Pass to `load_config` for merging.  
3. Apply overrides in `mine_terms.py` + `verify_terms.py`, logging counts.  
**Evidence:** `pipeline_results/deck_zeta.../deck_terms.txt` lines 40‑63 include “seed stage”, “unicorn”, “Series D” – high-frequency but low-value words.

### 4. Section-Aware Weighting
_Status: Completed – mine_terms.py now adjusts weights via detect_section_weight heuristics._
**Rationale:** Slide context matters: “Team” and “Benchmarks” should outweigh “Footer”. Without weighting, footer text can dominate due to frequency.  
**Tasks:**
1. During extraction, capture section tags via heuristics (Title-case lines with colon, large-font detection if feasible).  
2. Assign multipliers (Team=2.0, Product=1.5, Solution=1.3, Footer=0.3).  
3. Feed weights into `mine_terms.py` (frequency × weight).  
4. Log section weighting stats.  
**Evidence:** In each deck’s `deck_terms.txt`, footer-derived items (e.g., “deckzeta.com”) appear near top due to repeated mention, despite lower semantic value.

### 5. LLM Priority Thresholding
_Status: Completed – verify_terms.py enforces configurable threshold + telemetry._
**Rationale:** Claude sometimes emits mid-priority jargon; filtering by `priority` >0.75 (unless PERSON/ORG) keeps the list crisp.  
**Tasks:**
1. In `verify_terms.py`, discard LLM entries with `priority < threshold` unless class is PERSON/ORG.  
2. Make threshold configurable (default 0.75).  
3. Emit telemetry for dropped LLM entries.  
**Evidence:** Some LLM terms in `pipeline_results/deck_gamma/verified_terms.json` have priority 0.55 (e.g., generic phrases) but still appear because they meet frequency criteria.

### 6. Review Mode & Summary Reports
_Status: Completed – generate_review.py produces review.md and appends pipeline_results/summary.csv per run._
**Rationale:** Ops need a quick sanity check. A markdown summary reduces friction and prevents bad outputs from shipping.  
**Tasks:**
1. After each run, generate `out/review.md` summarizing: term counts, filtered stats, fallback triggered?, top 10 per class.  
2. Build a `pipeline_results/summary.csv` aggregator for all decks (counts, durations, fallback).  
3. Optionally auto-open review file when running interactively.  
**Evidence:** Manual inspection was required to catch the remaining noise; automated summaries would speed validation.

### 7. Alias Enrichment Loop
_Status: Completed – verify_terms.py writes out/aliases_learned.yaml and scripts/merge_aliases.py merges them._
**Rationale:** LLM often surfaces high-quality variants (“Secured-MCP”, “Transportation Language Model”). Feeding those back into config prevents duplicates in future decks.  
**Tasks:**
1. After verification, append novel alias pairs to a `aliases_learned.yaml` (human review before merging).  
2. Provide a CLI flag to merge learned aliases into config.  
**Evidence:** Repeated variants still appear as separate canonical entries (e.g., `Transportation Language Model` vs. `TLM`).

---
## Timeline & Dependencies
| Phase | Items | Est. Effort |
| --- | --- | --- |
| 2A | Boost floors, ordering, title-case filter, LLM threshold | ~3 hrs |
| 2B | Deck overrides, section weighting (heuristic), review summaries | ~5 hrs |
| 2C | POS tagging (optional), alias enrichment loop | ~4 hrs |

Dependencies: section weighting requires extraction updates; POS tagging depends on spaCy install (optional). All other items are config/code changes within existing modules.

---
## Success Metrics
- `deck_terms.txt` ≤50 entries per deck, PERSONs at top.  
- `phrase_set.json`: all PERSON entries boost=10.0; no lower-case generics.  
- Telemetry logs: counts for title-case/POS filters, LLM drops, section weights.  
- `review.md` produced for each run; `summary.csv` aggregates across decks.  
- Deck-specific overrides documented in config.  
- Regression tests (manual or scripted) confirm:  
  1. Every PERSON term has boost ≥10.0.  
  2. Prompt ordering respects class priority.  
  3. `deck_terms.txt` contains zero lowercase-only entries.  
  4. LLM entries with priority < threshold are filtered (unless PERSON/ORG).

---
## Next Steps
1. Implement Phase 2A items (boost floors, ordering, title-case filter, LLM priority threshold).  
2. Add deck override plumbing and review summaries (Phase 2B).  
3. Evaluate POS tagging feasibility; if adopted, gate behind config.  
4. Define edge-case handling for short uppercase tokens (e.g., `AI`, `CI`, `C#`) and document default behavior in config (keep uppercase acronyms ≥2 chars; drop lowercase two-character tokens).  
5. Add feature toggles in `config.yml` (`use_titlecase_filter`, `use_llm_priority_threshold`) so changes can be rolled back quickly if a deck requires relaxed filtering.  
6. Re-run all decks, compare summary metrics, and update docs with any new best practices.
