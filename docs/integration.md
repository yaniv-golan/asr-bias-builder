### Step 3 — **LLM pass via Claude Code** (headless, tool-assisted)

* Use **non-interactive mode** (`-p/--print`) and **JSON output** (`--output-format json`) so we can parse structured results. ([Claude Code][1])
* **Tool-assisted approach (recommended):** Enable `Read` tool so Claude can directly read `out/deck_text.txt` from the filesystem. This avoids context window limits and allows Claude to intelligently navigate large files. Use `--allowedTools "Read"` without `--permission-mode plan` restrictions. ([Claude Code][4])
* Provide a **system prompt** that enforces the JSON schema in `asr_bias_builder/llm/prompts/schema.md` using `--append-system-prompt "$(cat asr_bias_builder/llm/prompts/schema.md)"`. ([Claude Code][4])
* **Prompt structure:** Instruct Claude to use the Read tool to analyze `out/deck_text.txt`. Example: "Use the Read tool to open out/deck_text.txt. Extract all person names, organizations, products, acronyms, and technical terms that would be valuable for ASR biasing. Output only the JSON schema as specified below."
* **For very large decks (>200KB):** Use multi-turn approach with `--resume <session-id>` to let Claude work through the file in multiple passes (see examples below)
* **Fallback for small decks (<50KB):** Can send entire deck text via stdin if Read tool is not available

**Example headless run (tool-assisted, recommended):**

```bash
PROMPT="Use the Read tool to open out/deck_text.txt. $(cat asr_bias_builder/llm/prompts/schema.md)"

printf '%s\n' "$PROMPT" | claude --print \
  --model sonnet \
  --append-system-prompt "Return only the requested JSON schema. No prose." \
  --allowedTools "Read" \
  --output-format json \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example: Multi-turn for very large decks (>200KB):**

```bash
# First turn - start analysis
SESSION_ID=$(printf '%s\n' "Use the Read tool to analyze out/deck_text.txt. Begin extracting person names, organizations, and products." \
  | claude --print --model sonnet --allowedTools "Read" --output-format json \
  | jq -r '.session_id')

# Continue/refine if needed
printf '%s\n' "Continue extraction, focusing on acronyms and technical terms." \
  | claude --print --model sonnet --resume "$SESSION_ID" --output-format json \
  > /dev/null

# Final turn - get structured output
printf '%s\n' "$(cat asr_bias_builder/llm/prompts/schema.md)" \
  | claude --print --model sonnet --resume "$SESSION_ID" \
  --append-system-prompt "Return only the requested JSON schema. No prose." \
  --output-format json \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example: Fallback stdin approach for small decks (<50KB):**

```bash
# Send entire text via stdin (no Read tool)
DECK_TEXT=$(cat out/deck_text.txt)
PROMPT="Extract terms from this deck for ASR biasing:\n\n$DECK_TEXT\n\n$(cat asr_bias_builder/llm/prompts/schema.md)"

printf '%s\n' "$PROMPT" | claude --print --model sonnet \
  --append-system-prompt "Return only the requested JSON schema. No prose." \
  --output-format json \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

(Tool-assisted and multi-turn patterns based on production usage.) ([Claude Code][1])

**Model selection (optional):**

```bash
claude --model sonnet -p ...   # set model alias; see CLI --model flag
```

(Per CLI reference.) ([Claude Code][4])

