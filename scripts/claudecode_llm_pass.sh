#!/usr/bin/env bash
set -euo pipefail

SCHEMA_FILE="${1:?schema.md path missing}"
DECK_TEXT_FILE="${2:?deck_text.txt path missing}"
OUTPUT_JSON="${3:-out/claude_raw.json}"
MODEL="${MODEL:-sonnet}"
PERMISSION_FLAGS=(${PERMISSION_FLAGS:---dangerously-skip-permissions})
STREAM_THRESHOLD="${STREAM_THRESHOLD_BYTES:-80000}"
STREAM_INPUT_JSONL="${STREAM_INPUT_JSONL:-out/deck_stream.jsonl}"
STREAM_EVENTS_JSONL="${STREAM_EVENTS_JSONL:-out/claude_stream.jsonl}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

mkdir -p "$(dirname "$OUTPUT_JSON")"

STAT_SIZE_FMT="-f%z"
if stat $STAT_SIZE_FMT "$DECK_TEXT_FILE" >/dev/null 2>&1; then
  TEXT_BYTES=$(stat $STAT_SIZE_FMT "$DECK_TEXT_FILE")
else
  TEXT_BYTES=$(stat -c%s "$DECK_TEXT_FILE")
fi

if (( TEXT_BYTES > STREAM_THRESHOLD )); then
  "$PYTHON_BIN" -m asr_bias_builder.llm.claude "$DECK_TEXT_FILE" > "$STREAM_INPUT_JSONL"
  cat "$STREAM_INPUT_JSONL" | claude --print \
    --model "$MODEL" \
    --system-prompt-file "$SCHEMA_FILE" \
    --input-format stream-json \
    --output-format stream-json \
    --include-partial-messages \
    "${PERMISSION_FLAGS[@]}" \
    | tee "$STREAM_EVENTS_JSONL" >/dev/null
  "$PYTHON_BIN" -m asr_bias_builder.llm.parser "$STREAM_EVENTS_JSONL" > "$OUTPUT_JSON"
  jq -r '.result' "$OUTPUT_JSON"
else
  claude --print \
    --model "$MODEL" \
    --system-prompt-file "$SCHEMA_FILE" \
    --output-format json \
    "${PERMISSION_FLAGS[@]}" \
    <<< "$(cat "$DECK_TEXT_FILE")" \
    | tee "$OUTPUT_JSON" \
    | jq -r '.result'
fi
