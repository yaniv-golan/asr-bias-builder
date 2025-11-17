#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DECK="${1:?Usage: make_bias.sh <deck.(pdf|pptx)>}"
CONFIG_FILE="${CONFIG_FILE:-config/default.yml}"
OUT_DIR="out"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
RUN_LOG="$OUT_DIR/run.log"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi
export PYTHON_BIN

log(){
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$RUN_LOG"
}

preflight_check(){
  command -v claude >/dev/null || { log "ERROR: claude CLI not found"; exit 1; }
  command -v jq >/dev/null || { log "ERROR: jq not found"; exit 1; }
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ required")
PY
}

run_step(){
  local step=$1
  shift
  log "step=$step status=start"
  local start=$(date +%s)
  if "$@"; then
    local end=$(date +%s)
    log "step=$step status=success duration=$((end-start))s"
  else
    local code=$?
    local end=$(date +%s)
    log "step=$step status=fail code=$code duration=$((end-start))s"
    exit $code
  fi
}

preflight_check

log "python_version=$($PYTHON_BIN --version)"
log "claude_cli_version=$(claude --version 2>/dev/null || echo unknown)"
log "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"

DECK_BASENAME=$(basename "$DECK")
DECK_ID=$(echo "$DECK_BASENAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g' | sed -E 's/^_|_$//g')
export BIAS_DECK_ID="$DECK_ID"
log "deck_id=$BIAS_DECK_ID"

if [[ -f "$CONFIG_FILE" ]]; then
  export BIAS_CONFIG_FILE="$CONFIG_FILE"
  log "loading config from $CONFIG_FILE"
  eval "$({ python3 - "$CONFIG_FILE" <<'PY'
import shlex, sys
try:
    import yaml
except ImportError:
    sys.exit(0)
data = yaml.safe_load(open(sys.argv[1])) or {}
for key in (
    "google_phrase_boost",
    "max_prompt_terms",
    "min_freq_in_deck",
    "allow_llm_aliases",
    "model",
    "claude_permission_flags",
):
    if key in data:
        env = key.upper()
        print(f"{env}={shlex.quote(str(data[key]))}")
PY
  })"
else
  export BIAS_CONFIG_FILE="config/default.yml"
  log "config file not found, using defaults"
fi

GOOGLE_PHRASE_BOOST="${GOOGLE_PHRASE_BOOST:-8.0}"
MAX_PROMPT_TERMS="${MAX_PROMPT_TERMS:-120}"
MIN_FREQ_IN_DECK="${MIN_FREQ_IN_DECK:-1}"
ALLOW_LLM_ALIASES="${ALLOW_LLM_ALIASES:-false}"
CLAUDE_MODEL="${MODEL:-${CLAUDE_MODEL:-sonnet}}"
CLAUDE_PERMISSION_FLAGS="${CLAUDE_PERMISSION_FLAGS:---dangerously-skip-permissions}"
SUMMARY_CSV="${SUMMARY_CSV:-pipeline_results/summary.csv}"
STREAM_THRESHOLD_BYTES="${STREAM_THRESHOLD_BYTES:-80000}"

ALLOW_ALIAS_FLAG=""
shopt -s nocasematch
if [[ "$ALLOW_LLM_ALIASES" == "true" ]]; then
  ALLOW_ALIAS_FLAG="--allow-llm-aliases"
fi
shopt -u nocasematch

"$PYTHON_BIN" -m pip freeze > "$OUT_DIR/pip-freeze.txt"
log "pip_freeze=$OUT_DIR/pip-freeze.txt"

EXTRACT_CMD="\"$PYTHON_BIN\" -m asr_bias_builder.extraction \"$DECK\" > \"$OUT_DIR/deck_text.txt\""
MINE_CMD="\"$PYTHON_BIN\" -m asr_bias_builder.mining.seeds \"$OUT_DIR/deck_text.txt\" --stats-file \"$OUT_DIR/mine_terms_stats.json\" > \"$OUT_DIR/seeds.json\""
CLAUDE_CMD="env MODEL=\"$CLAUDE_MODEL\" PERMISSION_FLAGS=\"$CLAUDE_PERMISSION_FLAGS\" STREAM_THRESHOLD_BYTES=\"$STREAM_THRESHOLD_BYTES\" PYTHON_BIN=\"$PYTHON_BIN\" bash scripts/claudecode_llm_pass.sh asr_bias_builder/llm/prompts/schema.md \"$OUT_DIR/deck_text.txt\" \"$OUT_DIR/claude_raw.json\" > \"$OUT_DIR/lmm_candidates.json\""
VERIFY_CMD="\"$PYTHON_BIN\" -m asr_bias_builder.verification.matcher --deck-text \"$OUT_DIR/deck_text.txt\" --seeds \"$OUT_DIR/seeds.json\" --llm \"$OUT_DIR/lmm_candidates.json\" --stats-file \"$OUT_DIR/verify_stats.json\" --learned-aliases \"$OUT_DIR/aliases_learned.yaml\""
if [[ -n "$ALLOW_ALIAS_FLAG" ]]; then
  VERIFY_CMD+=" $ALLOW_ALIAS_FLAG"
fi
VERIFY_CMD+=" > \"$OUT_DIR/verified_terms.json\""
PROMPT_CMD="\"$PYTHON_BIN\" -m asr_bias_builder.artifacts.whisper \"$OUT_DIR/verified_terms.json\" --max-terms \"$MAX_PROMPT_TERMS\" > \"$OUT_DIR/deck_terms.txt\""
PHRASE_CMD="\"$PYTHON_BIN\" -m asr_bias_builder.artifacts.google_stt \"$OUT_DIR/verified_terms.json\" --boost \"$GOOGLE_PHRASE_BOOST\" > \"$OUT_DIR/phrase_set.json\""

run_step extract_text bash -c "$EXTRACT_CMD"
run_step mine_terms bash -c "$MINE_CMD"
run_step claude_pass bash -c "$CLAUDE_CMD"
run_step verify bash -c "$VERIFY_CMD"
run_step build_prompt bash -c "$PROMPT_CMD"
run_step build_phrase bash -c "$PHRASE_CMD"
run_step review_summary "$PYTHON_BIN" -m asr_bias_builder.reporting.summary \
  --deck-id "$BIAS_DECK_ID" \
  --deck-name "$DECK_BASENAME" \
  --output-dir "$OUT_DIR" \
  --summary-csv "$SUMMARY_CSV"

archive_results(){
  local dest_root="pipeline_results/$BIAS_DECK_ID"
  local stamp=$(date -u +%Y%m%dT%H%M%SZ)
  local target="$dest_root/$stamp"
  mkdir -p "$target"
  rsync -a --delete "$OUT_DIR/" "$target/"
  ln -sfn "$target" "$dest_root/latest"
  log "archived_run=$target"
}

run_step archive_results archive_results

log "Done. Artifacts in $OUT_DIR"
