#!/usr/bin/env bash
set -euo pipefail

SUMMARY="pipeline_results/summary.csv"
CONFIG="config/examples/advanced.yml"
OUTPUT_ROOT="out"

for deck in "$@"; do
  name=$(basename "$deck")
  echo "Processing $name"
  asr-bias-builder pipeline "$deck" \
    --config "$CONFIG" \
    --output-dir "$OUTPUT_ROOT" \
    --summary-csv "$SUMMARY"
  rsync -a "$OUTPUT_ROOT/" "pipeline_results/${name%.*}/$(date -u +%Y%m%dT%H%M%SZ)/"
  rm -rf "$OUTPUT_ROOT"
done
