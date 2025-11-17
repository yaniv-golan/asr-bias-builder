Below is a **technical spec** for a deck/PDF processing module that builds **ASR bias artifacts** (for Whisper `initial_prompt`/hotwords and Google STT v2 PhraseSets) using a **deterministic extractor + an LLM pass via Claude Code CLI (headless mode)**.

---

## Quick Reference

**What it does:** Extracts names, products, acronyms from PDF/PPTX decks → produces bias lists for ASR systems

**Key outputs:**
- `deck_terms.txt` — Whisper initial_prompt/hotwords (50-120 terms)
- `phrase_set.json` — Google STT v2 Speech Adaptation PhraseSet

**Pipeline:** Extract text → Mine seeds → LLM (stdin or streaming JSON) → Verify (exact match) → Build artifacts

**Key features:**
- ✅ Streaming JSON input/output plus stdin fallback for small decks
- ✅ Multi-turn via `--resume` for very large decks (>200KB)
- ✅ Hallucination guard (exact verification vs. source)
- ✅ English decks; **optional** Hebrew aliases (`allow_llm_aliases=true`)
- ✅ Configurable via `config.yml`
- ✅ Requires Python 3.11+ (preflight enforced)
- ✅ Optional Read tool mode with `--allowedTools "Read" --add-dir out`

**Quick start (CLI):**
```bash
asr-bias-builder pipeline deck.pdf
# → artifacts land in ./asr-bias-output/<deck>/ and summary appends to ./asr-bias-summary.csv
```

> **Note:** The sections below refer to files under `out/` for clarity. When running those commands, pass `--output-dir out --summary-csv pipeline_results/summary.csv` if you want the same layout; otherwise the CLI keeps writing to `./asr-bias-output/<deck>` and `./asr-bias-summary.csv`.

---

## 1) Objective & Scope

**Goal.** From a deck (`.pdf`/`.pptx`) produce:

* `deck_terms.txt` — compact, high‑value terms for **Whisper** `initial_prompt`/hotwords
* `phrase_set.json` — **Google STT v2 Speech Adaptation** PhraseSet (and optional CustomClasses)
* `lmm_candidates.json` — structured, ranked terms from an **LLM pass** (Claude Code)
* `deck_text.txt` — normalized raw text extracted from the deck (for verification & audit)

**Non‑goals.** Audio transcription, diarization enforcement, or A/B evaluation (handled by other modules).

---

## 2) System Overview

```
deck2bias/
  bin/
    make_bias.sh                # one-shot entrypoint (deterministic + LLM + verify)
    claudecode_llm_pass.sh      # headless Claude Code run (LLM pass)
  src/
    extract_deck_text.py        # PDF/PPTX text extraction (deterministic)
    mine_terms.py               # heuristics + optional NER to propose seeds
    verify_terms.py             # Exact multi-pattern verification on deck_text.txt
    build_phrase_set.py         # Google v2 Speech Adaptation PhraseSet builder
    build_prompt_list.py        # compact prompt/hotwords list for Whisper
  prompts/
    deck_terms_schema.md        # JSON schema & guidance for Claude outputs
  data/
    deck.pdf|deck.pptx          # input deck
  out/
    deck_text.txt               # deterministic extraction
    seeds.json                  # mined seed terms (deterministic)
    lmm_candidates.json         # Claude output (JSON)
    verified_terms.json         # LLM terms intersecting deck_text / heuristics
    deck_terms.txt              # final list for Whisper prompt/hotwords
    phrase_set.json             # final Google Speech Adaptation PhraseSet
    claude_raw.json             # normalized Claude output (JSON + metadata)
    claude_stream.jsonl         # streaming events (when --output-format stream-json is used)
    pip-freeze.txt              # dependency snapshot for audit
    run.log                     # pipeline log (timestamps, versions)
```

---

## 3) Dependencies

* **Python 3.11+ (required)** — entire toolchain, helper scripts, and virtual envs must run under CPython ≥3.11 for consistent typing support, structural pattern matching, and modern language features. Reject lower versions during preflight.
* **Claude Code CLI v1.0.54+** (headless) — `claude` binary (latest: 2.0.27 as of Oct 2025); requires ≥v1.0.54 for `--system-prompt-file` support, ≥v1.0.55 for `--append-system-prompt`. Supports non‑interactive `-p/--print`, JSON/streaming I/O, tool whitelisting, and plan/permission modes. ([Claude Code][1], [System Prompt Flags][7])
* **Python libs**: `pdfminer.six` and/or `PyMuPDF` for PDF; `python-pptx` for PPTX; `flashtext` or `pyahocorasick` for fast exact/approx matching; `regex`; `unicodedata`; `pyyaml` (for config file parsing – optional, see §9).
* **(Optional)** `tesseract-ocr` for image-only PDFs.
* **Shell utilities**: `jq` for JSON parsing; `stat` (both BSD/macOS and GNU/Linux formats supported).

**Install & login (Claude Code):**

```bash
curl -fsSL https://claude.ai/install.sh | bash   # macOS/Linux
claude                                          # first run triggers login
```

(Install & first-run login flow per overview docs.) ([Claude Code][2])

---

## 4) Processing Pipeline

### Step 1 — Deterministic extraction (`extract_deck_text.py`)

* **Input:** PDF/PPTX path
* **PDF:** if text layer exists → extract via `pdfminer.six` or `PyMuPDF`; if not → OCR (tesseract).
* **PPTX:** `python-pptx` to walk slides, shapes, tables.
* Normalize whitespace, linebreaks; write to `out/deck_text.txt`.

### Step 2 — Seed term mining (`mine_terms.py`)

* Use patterns for **Proper-Case multiwords**, **ALLCAPS tokens** with digits/hyphens, **acronyms**, **tech/product** strings. Deck inputs are assumed to be English, so deterministic seed mining focuses on English tokens; Hebrew spellings/aliases arrive later via the LLM path when needed for ASR biasing.
* Output `out/seeds.json` with `{term, freq, context_snippets}`.

### Step 3 — **LLM pass via Claude Code** (headless)

* Use **non‑interactive mode** (`-p/--print`) with **JSON output** (`--output-format json` or `--output-format stream-json`) so the result can be parsed deterministically. ([Claude Code][1])
* **Permissions:** pick the mode that matches your risk tolerance. For unattended automation, use `--dangerously-skip-permissions` (bypass prompts entirely). For interactive runs that should still auto-approve edits/tool calls, use `--permission-mode acceptEdits`. For read-only reviews, use `--permission-mode plan` (no auto-approval). Document the choice in `run.log`. ([Claude Code][2])
* **Input strategies (supported):**
  1. **Stdin (single chunk).** Pipe the entire deck text when it is ≤ ~80KB.
  2. **Streaming JSON input.** When the text is larger, switch to `--input-format stream-json --output-format stream-json` and send a JSONL sequence of user messages (each line: `{"type":"user","message":{"role":"user","content":[{"type":"text","text":"…"}]}}`). This keeps everything in one CLI invocation while chunking deterministically. ([Claude Code][1])
  3. **Read tool (optional).** Allow Claude to read files via `--allowedTools "Read"` (repeat flag per tool, e.g., `--allowedTools "Read" "Grep"`) plus `--add-dir out` (or the directory containing `deck_text.txt`). This still consumes tokens; it does **not** bypass context limits, but it lets Claude fetch only the portions it needs. Combine with an auto-approval mode to avoid permission prompts. ([Claude Code][3])
* **System prompt:** enforce the JSON schema via `--system-prompt-file asr_bias_builder/llm/prompts/schema.md` for file-based prompts (clean & version-controlled), or `--append-system-prompt "$(cat asr_bias_builder/llm/prompts/schema.md)"` if you need to preserve Claude Code's defaults. ([System Prompt Flags][7])
* **Model flag:** `--model sonnet|opus|haiku` uses aliases; pin a fully qualified model name (e.g., `claude-sonnet-4-5-20250929`) when you need reproducible runs. ([Claude Code][3])

**Example headless run (stdin, single-shot, auto-approve):**

```bash
DECK_TEXT=$(cat out/deck_text.txt)

claude --print \
  --model sonnet \
  --system-prompt-file asr_bias_builder/llm/prompts/schema.md \
  --output-format json \
  --dangerously-skip-permissions \
  <<< "$DECK_TEXT" \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example headless run (streaming JSON input for large decks):**

```bash
python3 -m asr_bias_builder.llm.claude out/deck_text.txt > out/deck_stream.jsonl

cat out/deck_stream.jsonl | claude --print \
  --model sonnet \
  --system-prompt-file asr_bias_builder/llm/prompts/schema.md \
  --input-format stream-json \
  --output-format stream-json \
  --include-partial-messages \
  --dangerously-skip-permissions \
  | tee out/claude_stream.jsonl >/dev/null

python3 -m asr_bias_builder.llm.parser out/claude_stream.jsonl \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example headless run (Read tool, file-driven):**

```bash
PROMPT="Use the Read tool to open out/deck_text.txt. Extract ASR bias terms. Return only the JSON schema."

printf '%s\n' "$PROMPT" | claude --print \
  --model sonnet \
  --system-prompt-file asr_bias_builder/llm/prompts/schema.md \
  --allowedTools "Read" \
  --add-dir out \
  --output-format json \
  --permission-mode acceptEdits \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

(All three flows are documented in the Claude Code headless reference.) When you need multi-turn refinement, capture the `session_id` from the JSON output and pass `--resume <id>` for follow-up turns. ([Claude Code][1])

**Model selection (optional):**

```bash
claude --model sonnet -p ...   # set model alias; see CLI --model flag
```

(Per CLI reference.) ([Claude Code][4])

### Step 4 — Verification & consolidation (`verify_terms.py`)

* Load `deck_text.txt` and `lmm_candidates.json`.
* **De-duplicate & verify** each candidate via **exact multi-pattern matching** (FlashText or Aho-Corasick) against the deterministic text; drop candidates that never appear (to avoid hallucinations). High-value aliases not in deck are **only kept** if `allow_llm_aliases=true`.
* Merge with `seeds.json`; rank by: (LLM priority/score, frequency, section emphasis).
* Output `out/verified_terms.json` with fields:

  ```json
  [{"canonical":"Dr. Liam Nguyen","variants":["Liam Nguyen"],"classes":["PERSON"],"present_in_deck":true,"score":0.94}, ...]
  ```

### Step 5 — Final artifacts

* **Whisper prompt/hotwords**: `build_prompt_list.py` → `out/deck_terms.txt`

  * Keep **50–120** tokens; prioritize proper nouns & jargon (Whisper only effectively uses a limited tail in `initial_prompt`).
  * Hard-cap the prompt to ≤200 tokens (~224 Whisper limit) to avoid wasting context. ([OpenAI Whisper Prompting Guide][5])
* **Google v2 PhraseSet**: `build_phrase_set.py` → `out/phrase_set.json`

  * Example:

    ```json
    {"phraseSets":[{"phrases":[
      {"value":"Dyson Sphere AI","boost":10.0},
      {"value":"AI Compute","boost":8.5},
      {"value":"Solar Collectors","boost":8.0}
    ]}]}
    ```
  * Validate every phrase (`value` non-empty UTF-8, `0 < boost ≤ 20`) before emitting to match the v2 `PhraseSet` contract. ([Google STT PhraseSet][6])

---

## 5) JSON Schema for Claude (LLM pass)

**System prompt (excerpt):**

```
You are building an ASR bias list. Read the deck text and output ONLY valid JSON with the schema:

{
  "terms": [
    {
      "canonical": "Forcepoint",
      "variants": ["Force Point", "פורספוינט"],
      "classes": ["ORG","PRODUCT"],    // PERSON|ORG|PRODUCT|ACRONYM|TECH
      "priority": 0-1,                 // importance to recognition
      "notes": "why it matters (optional)"
    }
  ]
}

Rules:
- Include English canonical spellings and, when helpful for downstream Hebrew audio, transliterations/aliases even if they are not present verbatim in the deck (flag via `present_in_deck` or notes).
- Prefer short canonical forms.
- No commentary. No markdown. JSON only.
```

**CLI flags to enforce structured output:** `--output-format json` plus either `--system-prompt-file asr_bias_builder/llm/prompts/schema.md` (print mode only, file-based) or `--append-system-prompt "$(cat asr_bias_builder/llm/prompts/schema.md)"` (appends to defaults). Stdin input by default. ([Claude Code][1], [System Prompt Flags][7])

---

## 6) CLI Details (headless mode)

* **Non-interactive** run: `claude --print …` plus `--output-format json` (or `--output-format stream-json`). Pipe stdin or feed streaming JSON input as needed. ([Claude Code][1])
* **System prompts:** prefer `--system-prompt-file asr_bias_builder/llm/prompts/schema.md` for file-based prompts (print mode only, clean & version-controlled); `--append-system-prompt` adds to defaults when you want to preserve Claude Code's built-in capabilities. ([System Prompt Flags][7])
* **Input modes:**
  * **Stdin** for compact decks. Keep prompts ≤ ~80KB.
  * **Streaming JSON** for larger decks: pair `--input-format stream-json` with `--output-format stream-json` and send JSONL user messages (`{"type":"user","message":{"role":"user","content":[{"type":"text","text":"…"}]}}`). ([CLI Reference][4])
  * **Read tool** when you want Claude to fetch files lazily: add `--allowedTools "Read" --add-dir out` (or whichever directories contain documents). Remember it still consumes tokens, so chunking/streaming may still be required for extremely large decks. ([CLI Reference][4])
* **Permission modes:**
  * `--dangerously-skip-permissions` → auto-approve all actions (fast CI path).
  * `--permission-mode acceptEdits` → auto-approve edits/tool runs, may still prompt for unknown actions.
  * `--permission-mode plan` → read-only planning, no actions (not auto-approve).
  Choose the mode explicitly per run and log it. ([Claude Code][2])
* **Streaming output & progress:** `--output-format stream-json --include-partial-messages` exposes event streams; capture them in `out/claude_stream.jsonl` and parse the final `{ "type": "result" }` record.
* **Resume multi-turn:** capture `session_id` from the JSON output and pass `--resume <session-id>` for follow-up turns when you need incremental refinement. ([Claude Code][1])

---

## 7) `scripts/make_bias.sh` (one‑shot pipeline)

```bash
#!/usr/bin/env bash
set -euo pipefail

DECK="${1:?Usage: make_bias.sh <deck.(pdf|pptx)>}"
CONFIG_FILE="${CONFIG_FILE:-config.yml}"

# Preflight checks
preflight_check() {
  command -v claude >/dev/null || { echo "ERROR: claude CLI not found"; exit 1; }
  python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("ERROR: Python 3.11+ required (found: %s)" % sys.version)
PY
}

preflight_check

mkdir -p out
RUN_LOG="out/run.log"
log(){ printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$RUN_LOG"; }

run_step(){
  local step=$1; shift
  local cmd="$*"
  local start=$(date +%s)
  log "step=$step status=start"
  if eval "$cmd"; then
    local end=$(date +%s)
    log "step=$step status=success duration=$((end-start))s"
  else
    local code=$?
    local end=$(date +%s)
    log "step=$step status=fail code=$code duration=$((end-start))s"
    exit $code
  fi
}

log "python_version=$(python3 --version)"
log "python_path=$(command -v python3)"
log "claude_cli_version=$(claude --version 2>/dev/null || echo 'unknown')"
log "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo 'n/a')"

if [[ -f "$CONFIG_FILE" ]]; then
  log "loading config from $CONFIG_FILE"
  eval "$(python3 - \"$CONFIG_FILE\" <<'PY'
import shlex, sys
try:
    import yaml
except ImportError:
    sys.exit(0)
cfg = yaml.safe_load(open(sys.argv[1])) or {}
mapping = {
    "google_phrase_boost": "GOOGLE_BOOST",
    "max_prompt_terms": "MAX_PROMPT_TERMS",
    "min_freq_in_deck": "MIN_FREQ_IN_DECK",
    "allow_llm_aliases": "ALLOW_LLM_ALIASES",
    "model": "CLAUDE_MODEL",
}
for key, env in mapping.items():
    if key in cfg:
        print(f"{env}={shlex.quote(str(cfg[key]))}")
PY
)"
else
  log "config=$CONFIG_FILE (not found, using defaults)"
fi

GOOGLE_BOOST="${GOOGLE_BOOST:-8.0}"
MAX_PROMPT_TERMS="${MAX_PROMPT_TERMS:-100}"
MIN_FREQ_IN_DECK="${MIN_FREQ_IN_DECK:-1}"
ALLOW_LLM_ALIASES="${ALLOW_LLM_ALIASES:-false}"
CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"

log "effective_config model=$CLAUDE_MODEL boost=$GOOGLE_BOOST max_terms=$MAX_PROMPT_TERMS min_freq=$MIN_FREQ_IN_DECK allow_aliases=$ALLOW_LLM_ALIASES"
python3 -m pip freeze > out/pip-freeze.txt
log "pip_freeze_file=out/pip-freeze.txt"

run_step extract_text "python3 -m asr_bias_builder.extraction \"$DECK\" > out/deck_text.txt"
run_step mine_seeds "python3 -m asr_bias_builder.mining.seeds out/deck_text.txt > out/seeds.json"

# LLM pass (headless, stdin-based)
run_step claude_pass "MODEL=\"$CLAUDE_MODEL\" bash scripts/claudecode_llm_pass.sh asr_bias_builder/llm/prompts/schema.md out/deck_text.txt out/claude_raw.json > out/lmm_candidates.json"

# Verify & consolidate
run_step verify_terms "python3 -m asr_bias_builder.verification.matcher --deck-text out/deck_text.txt --seeds out/seeds.json --llm out/lmm_candidates.json --min-freq \"$MIN_FREQ_IN_DECK\" --allow-llm-aliases \"$ALLOW_LLM_ALIASES\" > out/verified_terms.json"

# Emit artifacts
run_step build_prompt "python3 -m asr_bias_builder.artifacts.whisper --max-terms \"$MAX_PROMPT_TERMS\" out/verified_terms.json > out/deck_terms.txt"
run_step build_phrase_set "python3 -m asr_bias_builder.artifacts.google_stt --boost \"$GOOGLE_BOOST\" out/verified_terms.json > out/phrase_set.json"

log "Done. Artifacts in ./out"
```

**`scripts/claudecode_llm_pass.sh`** (auto-detect stdin vs. streaming):

```bash
#!/usr/bin/env bash
set -euo pipefail

SCHEMA_FILE="${1:?schema.md path missing}"
DECK_TEXT_FILE="${2:?deck_text.txt path missing}"
OUTPUT_JSON="${3:-out/claude_raw.json}"
MODEL="${MODEL:-sonnet}"
PERMISSION_FLAGS=(${PERMISSION_FLAGS:---dangerously-skip-permissions})

mkdir -p "$(dirname "$OUTPUT_JSON")"

TEXT_BYTES=$(stat -f%z "$DECK_TEXT_FILE" 2>/dev/null || stat -c%s "$DECK_TEXT_FILE")
STREAM_INPUT_JSONL="${STREAM_INPUT_JSONL:-out/deck_stream.jsonl}"
STREAM_EVENTS_JSONL="${STREAM_EVENTS_JSONL:-out/claude_stream.jsonl}"

if (( TEXT_BYTES > 80000 )); then
  # Streaming JSON input/output
  python3 -m asr_bias_builder.llm.claude "$DECK_TEXT_FILE" > "$STREAM_INPUT_JSONL"
  cat "$STREAM_INPUT_JSONL" | claude --print \
    --model "$MODEL" \
    --system-prompt-file "$SCHEMA_FILE" \
    --input-format stream-json \
    --output-format stream-json \
    --include-partial-messages \
    "${PERMISSION_FLAGS[@]}" \
    | tee "$STREAM_EVENTS_JSONL" >/dev/null
  python3 -m asr_bias_builder.llm.parser "$STREAM_EVENTS_JSONL" \
    | tee "$OUTPUT_JSON" \
    | jq -r '.result'
else
  # Simple stdin path
  claude --print \
    --model "$MODEL" \
    --system-prompt-file "$SCHEMA_FILE" \
    --output-format json \
    "${PERMISSION_FLAGS[@]}" \
    <<< "$(cat "$DECK_TEXT_FILE")" \
    | tee "$OUTPUT_JSON" \
    | jq -r '.result'
fi
```

(Headless usage, flags, and JSON parsing per docs.) ([Claude Code][1])

---

## 8) Quality Controls & Limits

* **Prompt length**: keep `deck_terms.txt` concise (≈ 50–120 terms) to avoid diminishing returns in Whisper's prompt/hotwords.
  * Whisper only consumes roughly the last ~224 tokens of `initial_prompt`, so enforce an upper bound (≤200 tokens) when building the list. ([OpenAI Whisper Prompting Guide][5])
* **Hallucination guard**: only keep `present_in_deck = true` by default; LLM-suggested terms not present in deck are **dropped unless** `--allow-llm-aliases=true`.
* **Hebrew alias handling**: Deterministic extraction stays English-only. LLM may suggest Hebrew spellings/transliterations, but they are **only included** if `allow_llm_aliases=true` (default: `false`). Hebrew aliases not present in deck text will be filtered out by default verification.
* **Determinism**: deterministic extraction & verification ensure reproducibility; **Claude** augments recall but does not gate correctness.
* **Token efficiency**: For very large decks, consider summarizing per-slide rather than sending all text; this trades some recall for faster/cheaper LLM calls.

---

## 9) Configurability

**`config.yml` (optional):**

```yaml
# ASR Bias Artifact Configuration
google_phrase_boost: 8.0       # boost value for Google Speech Adaptation (valid: 0-20)
max_prompt_terms: 100           # max terms in Whisper prompt (enforce ≤200 tokens)
min_freq_in_deck: 1             # minimum term frequency to include
allow_llm_aliases: false        # include LLM-suggested terms NOT in deck (Hebrew aliases, etc.)
model: "sonnet"                 # Claude model: sonnet, opus, haiku
use_read_tool: false            # set true to add --allowedTools "Read" --add-dir out during LLM pass
```

* All settings have sensible defaults; config file is optional
* Override any setting via environment variables (e.g., `export CLAUDE_MODEL=opus`)
* Config is loaded via PyYAML; if the module is missing the pipeline logs a warning and keeps defaults

---

## 10) Telemetry & Audit

* `out/run.log`: per-step `start/success/fail` entries with timestamps, duration, git commit, Python/Claude versions, and effective config.
* `out/claude_raw.json`: normalized Claude payload (result + metadata + cost/session_id). When streaming is enabled, the raw JSONL events are also saved at `out/claude_stream.jsonl` for deep audits.
* `out/pip-freeze.txt`: snapshot of the Python environment used for the run (consumed downstream for provenance checks).
* For production deployments, consider instrumenting with:
  * Exit codes on each step (extraction, mining, LLM, verification)
  * Term counts at each stage in `run.log`
  * Token usage & latency from Claude output JSON
  * Alerting if verification rate drops below threshold (e.g., <70% of LLM candidates verified)

---

## 11) Testing & Acceptance

* **Unit tests**:

  * Extraction works for text‑PDF, image‑PDF (with OCR), PPTX.
  * `verify_terms.py` drops non‑present LLM terms.
  * PhraseSet JSON passes JSON schema validation.
  * Stdin + streaming JSON flows both emit valid `out/claude_raw.json` payloads.
  * Read tool path works when `use_read_tool=true` (with `--add-dir out`).
  * Multi-turn resume works for very large decks.

* **Integration tests**:

  * Small deck (<50KB): stdin auto-approve path produces valid output
  * Large deck (>80KB): streaming JSON path produces valid output (single invocation)
  * Read tool mode (if enabled) produces identical `lmm_candidates.json`
  * Config file values override defaults correctly
  * Both macOS and Linux environments work

* **Acceptance criteria**:

  * On a known deck, ≥90% of intended names/products present in `deck_terms.txt`.
  * `phrase_set.json` loads in a dry‑run to Google v2 adapter (or JSON schema check).
  * End‑to‑end runtime < 60s on a 20‑slide deck (no OCR).
  * Zero hallucinated terms in `deck_terms.txt` when `allow_llm_aliases=false`.

---

## 12) Error Handling & Recovery

* **Extraction failures**: Log error and exit with code 1; preserve partial output for debugging
* **Claude API errors**: 
  * Network failures: retry up to 3 times with exponential backoff
  * Rate limits: respect retry-after headers, log wait time
  * Invalid JSON: save raw output to `out/claude_error.txt` and exit with code 2
* **Verification drops all terms**: If <10% of LLM candidates verify, emit warning but continue (may indicate deck text extraction issue)
* **Missing dependencies**: Check for `claude`, `jq`, required Python packages in a `preflight_check()` function
* **Idempotency**: All steps write to `out/` with predictable names; re-running is safe

**Example preflight check:**

```bash
preflight_check() {
  local missing=()
  command -v claude >/dev/null || missing+=("claude")
  command -v jq >/dev/null || missing+=("jq")
  
  # Check Python version
  if ! python3 - <<'PY' 2>/dev/null
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    echo "ERROR: Python 3.11+ required (found: $(python3 --version 2>&1 || echo 'not found'))" >&2
    exit 1
  fi
  
  # Warn if PyYAML not available (optional)
  if ! python3 -c "import yaml" 2>/dev/null; then
    echo "WARN: PyYAML not installed; config.yml support disabled" >&2
  fi
  
  if (( ${#missing[@]} > 0 )); then
    echo "ERROR: missing dependencies: ${missing[*]}" >&2
    exit 1
  fi
}
```

---

## 13) Security & Permissions

* **Permission strategy:**
  * **CI / unattended:** `--dangerously-skip-permissions` so the run never stalls.
  * **Interactive edits allowed:** `--permission-mode acceptEdits` (auto-approves edits/tool actions, may prompt for unknown operations).
  * **Read-only review:** `--permission-mode plan` (no actions executed). Document the chosen mode in `run.log`. ([Claude Code][2])
* **Tool allowlist:** only enable the tools you need (typically `Read` and/or `Grep`) and scope filesystem access via `--add-dir out` (or similar). Keep `dangerously-skip` usage restricted to trusted CI environments.
* **Remote decks:** if you must access cloud drives, configure an MCP connector via `--mcp-config` and still pair it with the appropriate permission mode. ([Claude Code][4])

---

## 14) Integration Points

* **Whisper arm**: pass `out/deck_terms.txt` as `initial_prompt` (or hotwords) when transcribing per STJSON window.
* **Google STT v2 arm**: attach `out/phrase_set.json` to **Speech Adaptation** in `RecognitionConfig` (then snap text to STJSON windows downstream).

**Example: Whisper integration**

```python
# Load bias terms
with open("out/deck_terms.txt") as f:
    initial_prompt = f.read().strip()

# Use in transcription
result = whisper.transcribe(
    audio_path,
    initial_prompt=initial_prompt,
    language="en"  # or "he" for Hebrew
)
```

**Example: Google STT v2 integration**

```python
import json
from google.cloud import speech_v2

# Load phrase set
with open("out/phrase_set.json") as f:
    phrase_set_config = json.load(f)

# Build adaptation config
adaptation = speech_v2.SpeechAdaptation(
    phrase_sets=[
        speech_v2.PhraseSet(phrases=[
            speech_v2.PhraseSet.Phrase(value=p["value"], boost=p["boost"])
            for p in phrase_set_config["phraseSets"][0]["phrases"]
        ])
    ]
)

# Use in recognition config
config = speech_v2.RecognitionConfig(
    adaptation=adaptation,
    # ... other config
)
```

---

### Notes on Claude Code Headless

* **Headless mode** lets you run programmatically and capture structured JSON (cost, duration, `session_id`, output). Use `--output-format json` for machine‑readable parsing. ([Claude Code][1])
* You can **resume** sessions for multi‑turn refinement (`--resume <id>`), or use **streaming JSON input** for chunked ingestion. ([Claude Code][1])
* Full CLI flags (e.g., `--append-system-prompt`, `--model`, `--max-turns`) are documented in the **CLI reference**. ([Claude Code][4])

---

## Appendix A: Version Compatibility

### Tested Versions

This specification has been verified with the following versions:

| Component | Minimum | Recommended | Latest (Nov 2025) | Notes |
|-----------|---------|-------------|-------------------|-------|
| Python | 3.11 | 3.11+ | 3.13 | 3.11+ required (fast path) |
| Claude Code CLI | 1.0.54 | 2.0.27 | 2.0.27 | v1.0.54+ for `--system-prompt-file`, v1.0.55+ for `--append-system-prompt` ([ref][7]) |
| Claude Models | - | sonnet | opus-4.5, sonnet-4.5 | Sonnet good balance of speed/quality |
| pdfminer.six | 20220524 | latest | - | For text-based PDFs |
| PyMuPDF | 1.20.0 | latest | - | Alternative PDF library |
| python-pptx | 0.6.21 | latest | - | For PowerPoint files |
| PyYAML | 5.4 | 6.0+ | - | Optional, for config.yml |
| jq | 1.6 | 1.7+ | 1.7 | JSON parsing in shell |

### Breaking Changes

**Claude Code CLI version history:**
- v1.0.54: `--system-prompt-file` added (load prompts from files in print mode)
- v1.0.55: `--append-system-prompt` added (append to default prompt)
- v2.0.0+: Headless mode (`-p/--print`) stabilized
- v2.0.14: `--system-prompt` added (replace entire prompt)
- All versions support `--output-format json`, `--output-format stream-json`, and `--input-format stream-json`
- `--permission-mode plan` available for read-only operations
- See [System Prompt Flags documentation][7] for complete flag reference

**Python Version Notes:**
- **3.11+**: Required minimum (structural pattern matching, better error messages, faster runtime)
- **3.13**: Latest stable, full compatibility expected

### Upgrade Path

If upgrading from older versions:

1. **Claude Code CLI**: `curl -fsSL https://claude.ai/install.sh | bash` (overwrites safely)
2. **Python**: Use pyenv/conda for version management; 3.11+ required
3. **Python packages**: `pip install --upgrade pdfminer.six python-pptx pyyaml`

---

## Appendix B: Troubleshooting

### Common Issues

**Issue: "command not found: claude"**
- Solution: Install Claude Code CLI: `curl -fsSL https://claude.ai/install.sh | bash` and restart shell
- Verify: `which claude` should show the binary path

**Issue: Claude returns empty JSON or errors**
- Check `out/claude_raw.json` for full error details
- Verify deck_text.txt is not empty: `wc -l out/deck_text.txt`
- Try with a smaller test file first
- Check API quota/rate limits in Claude dashboard

**Issue: Very few terms verified (<10%)**
- Likely cause: deck_text extraction failed or is incomplete
- Check: `head -100 out/deck_text.txt` for readable content
- For image PDFs, ensure tesseract is installed
- Try a different PDF library (switch between pdfminer.six and PyMuPDF)

**Issue: stat command fails on Linux**
- The script auto-detects; if it still fails, set: `export STAT_SIZE_FMT="-c%s"`

**Issue: Pipeline is slow (>2 minutes for small deck)**
- Check if OCR is running unnecessarily (text-based PDFs shouldn't need it)
- Consider using faster model: `model: "haiku"` in config.yml
- Large decks: chunking adds overhead; single-shot is faster when possible

**Issue: Hebrew variants missing from artifacts**
- Confirm the deck actually mentions the concept in English so the LLM has context to suggest aliases
- Ensure `allow_llm_aliases=true` (or provide manual variants) when you expect transliterations not present in the deck
- Inspect `out/lmm_candidates.json` to verify the LLM emitted the Hebrew spellings before verification filters

---

## Appendix C: Python Helper Script Skeletons (Optional/Reference)

**Note:** These scripts power the streaming JSON mode described in §4/§6. Use them whenever `deck_text.txt` exceeds the stdin threshold or when you prefer deterministic chunking over the Read tool.

### `asr_bias_builder/llm/claude.py` (streaming input builder)

```python
#!/usr/bin/env python3
"""Split deck text into JSONL chunks for Claude streaming input."""
import json
import sys

CHUNK_SIZE = 50_000  # characters per chunk

def main(deck_text_path: str) -> None:
    with open(deck_text_path, encoding="utf-8") as f:
        full_text = f.read()

    chunks = [
        full_text[i : i + CHUNK_SIZE]
        for i in range(0, len(full_text), CHUNK_SIZE)
    ]

    total = len(chunks) or 1
    for idx, chunk in enumerate(chunks or [""], start=1):
        print(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"[Chunk {idx}/{total}]\n\n{chunk}",
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            )
        )

if __name__ == "__main__":
    main(sys.argv[1])
```

### `asr_bias_builder/llm/parser.py` (streaming output parser)

```python
#!/usr/bin/env python3
"""Extract final result + metadata from Claude streaming JSONL output."""
import json
import sys
from typing import Any, Dict, List, Optional


def main(stream_jsonl_path: str) -> None:
    """Parse Claude streaming output and emit normalized JSON with result + metadata."""
    events: List[Dict[str, Any]] = []
    final_result: Optional[Any] = None
    metadata: Dict[str, Any] = {}

    with open(stream_jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            events.append(obj)
            
            # Look for result in various message formats
            if obj.get("type") == "result":
                final_result = obj.get("result")
                # Extract metadata if present
                for key in ("session_id", "usage", "cost", "model"):
                    if key in obj:
                        metadata[key] = obj[key]
            elif "result" in obj and final_result is None:
                final_result = obj["result"]

    if final_result is None:
        raise SystemExit("ERROR: no result found in stream")

    # If result is a JSON string, parse it
    if isinstance(final_result, str):
        try:
            final_result = json.loads(final_result)
        except json.JSONDecodeError:
            pass  # Keep as string if not valid JSON

    # Build normalized output
    payload: Dict[str, Any] = {
        "result": final_result,
        "event_count": len(events)
    }
    if metadata:
        payload["metadata"] = metadata

    # Output normalized JSON
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
    main(path)
```

### Notes on implementation

* **`make_jsonl_chunks.py`**: 
  - Adjust `CHUNK_SIZE` based on model context window; 50K chars ≈ 12K tokens
  - Uses structured message format with `type: "user"` and nested `message` object matching Claude API message structure
  - Each line is a complete JSON object with `ensure_ascii=False` for Hebrew support
* **`extract_claude_result.py`**: 
  - Handles both `{"type": "result", "result": {...}}` and message-based formats from Claude Code CLI
  - Returns normalized JSON with `result` field and optional `metadata` (session_id, usage, cost)
  - The shell script extracts just `.result` via `jq` for downstream processing
* Both scripts should handle UTF-8 (Hebrew/English) correctly with `ensure_ascii=False`
* **Type hints**: Python 3.11+ compatible; uses `typing.Dict`, `typing.List`, `typing.Optional`

---

## Appendix D: Performance Benchmarks

Expected performance on typical hardware (4-core CPU, 16GB RAM):

| Deck Size | Slides | Text Size | Mode | Time | Notes |
|-----------|--------|-----------|------|------|-------|
| Small | 10-15 | 20-40 KB | Single | 8-15s | Fastest path |
| Medium | 20-30 | 50-70 KB | Single | 15-25s | Still single-shot |
| Large | 40-60 | 100-150 KB | Chunked | 35-50s | Streaming overhead |
| Very Large | 100+ | 300+ KB | Chunked | 60-120s | Multiple chunks |

**Bottlenecks:**
- Claude API latency: ~3-8s per call (depends on model and input size)
- OCR (if needed): +20-60s depending on page count and image quality
- Network: affects Claude calls; local processing is fast (<1s total)

**Optimization tips:**
- Use `haiku` model for speed (60-80% faster than `sonnet`)
- Skip OCR on text-based PDFs (check extraction first)
- For batch processing, parallelize multiple decks (not pipeline steps)

---

## Appendix E: Example Run

```bash
# Create a test deck copy
cd deck2bias
mkdir -p data out
cp examples/basic/sample_deck.pdf data/sample_deck.pdf

# Run the pipeline
bash scripts/make_bias.sh data/sample_deck.pdf

# Check outputs
cat out/run.log
echo "=== Extracted terms ==="
head -20 out/deck_terms.txt
echo "=== Phrase set ==="
jq '.phraseSets[0].phrases | length' out/phrase_set.json
```

Expected output structure:

```
out/
├── claude_raw.json          # Full Claude response with metadata
├── deck_stream.jsonl        # (if large deck) chunked input
├── deck_terms.txt           # 50-120 terms, one per line
├── deck_text.txt            # Normalized extraction
├── lmm_candidates.json      # Claude-suggested terms
├── phrase_set.json          # Google v2 format
├── run.log                  # Timestamped pipeline log
├── seeds.json               # Deterministic seed terms
└── verified_terms.json      # Final verified & ranked terms
```

---

[1]: https://code.claude.com/docs/en/headless "Headless mode - Claude Code Docs"
[2]: https://code.claude.com/docs/en/overview "Claude Code overview - Claude Code Docs"
[3]: https://code.claude.com/docs/en/common-workflows "Common workflows - Claude Code Docs"
[4]: https://code.claude.com/docs/en/cli-reference "CLI reference - Claude Code Docs"
[5]: https://cookbook.openai.com/examples/whisper_prompting_guide "Whisper prompting guide - OpenAI Cookbook"
[6]: https://cloud.google.com/speech-to-text/v2/docs/phrase-set "Speech-to-Text v2 PhraseSet - Google Cloud"
[7]: https://code.claude.com/docs/en/cli-reference#system-prompt-flags "System prompt flags - Claude Code CLI reference"
