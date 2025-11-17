# Batch Processing

Use `scripts/make_bias.sh` inside a loop:

```bash
for deck in test-data/decks/*.pdf; do
  bash scripts/make_bias.sh "$deck"
  rsync -a out/ pipeline_results/$(basename "$deck" .pdf)/$(date -u +%Y%m%dT%H%M%SZ)/
  rm -rf out
done
```

For Python-only workflows, call `asr-bias-builder pipeline` per deck and point `--summary-csv` to a shared location.
