# LLM Integration

Refer to `docs/integration.md` for the full Claude CLI playbook. Highlights:
- Use `--system-prompt-file asr_bias_builder/llm/prompts/schema.md` to enforce JSON schema.
- Switch to streaming JSON for decks >80KB and parse with `asr_bias_builder.llm.parser.parse_stream`.
- Tool-assisted runs allow the `Read` tool to open `out/deck_text.txt`.
- Multi-turn sessions rely on `claude --resume <session-id>`.
