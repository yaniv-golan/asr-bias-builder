# Troubleshooting

- **Python version errors:** ensure Python 3.11+; earlier revisions referenced tomllib incorrectly (see `docs/internal/ASR-bias-artifacts-review.md`).
- **Claude stream empty:** verify `claudecode_llm_pass.sh` piping order; the fixed version first saves `deck_stream.jsonl`, then parses it via `extract_claude_result.py`.
- **Broken CLI pipeline:** confirm `pip install -e .` succeeded and that `claude` binary is on `$PATH`.
- **OCR noise:** extend `ocr_aliases`/`ocr_normalizations` in `config.yml` and rerun `scripts/merge_aliases.py` to merge learned variants.
- **Permission prompts:** pass `--permission-flag --dangerously-skip-permissions` or other Claude CLI permission flags to the `pipeline` command.
