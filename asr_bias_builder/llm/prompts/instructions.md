### Step 3 — **LLM pass via Claude Code** (headless, stdin-based)

* Use **non-interactive mode** (`-p/--print`) and **JSON output** (`--output-format json`) so we can parse structured results. ([Claude Code][1])
* **Default approach (stdin, recommended):** Send deck text via stdin using `printf '%s\n' "$prompt" | claude ...` This is the proven CConductor pattern—simple, reliable, no tool permissions needed. Works for decks up to model context limit (~200KB).
* Provide a **system prompt** that enforces the JSON schema in `prompts/deck_terms_schema.md` using `--append-system-prompt "$(cat prompts/deck_terms_schema.md)"`. ([Claude Code][4])
* **Prompt structure:** Combine schema with deck text in stdin. Example: "Extract terms for ASR biasing from this deck text below. Output only valid JSON matching the schema.\n\n[deck text]\n\n[schema]"
* **For very large decks (>200KB):** Use **multi-turn with `--resume`** to work through content in multiple passes (still stdin-based for each turn)
* **Optional/Experimental: Read tool mode** - Can enable `--allowedTools "Read"` (set `USE_READ_TOOL=1`) to let Claude access files directly, but requires testing in headless environments and may have permission issues. Not recommended for production.

**Example headless run (stdin, default):**

```bash
DECK_TEXT=$(cat out/deck_text.txt)
SCHEMA=$(cat prompts/deck_terms_schema.md)
PROMPT="Extract ASR bias terms from this deck. Return only JSON.\n\nDeck:\n${DECK_TEXT}\n\nSchema:\n${SCHEMA}"

printf '%s\n' "$PROMPT" | claude --print \
  --model sonnet \
  --append-system-prompt "Return only the requested JSON schema. No prose." \
  --output-format json \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example: Multi-turn for very large decks (>200KB):**

```bash
DECK_TEXT=$(cat out/deck_text.txt)
SCHEMA=$(cat prompts/deck_terms_schema.md)

# First turn - start extraction
SESSION_ID=$(printf '%s\n' "Analyze this deck and extract key terms:\n\n${DECK_TEXT:0:100000}" \
  | claude --print --model sonnet --output-format json \
  | jq -r '.session_id')

# Continue with remaining content
printf '%s\n' "Continue analyzing:\n\n${DECK_TEXT:100000}" \
  | claude --print --model sonnet --resume "$SESSION_ID" --output-format json \
  > /dev/null

# Final turn - get structured output
printf '%s\n' "Now output all extracted terms using this schema:\n\n${SCHEMA}" \
  | claude --print --model sonnet --resume "$SESSION_ID" \
  --append-system-prompt "Return only the requested JSON schema. No prose." \
  --output-format json \
  | tee out/claude_raw.json \
  | jq -r '.result' > out/lmm_candidates.json
```

**Example: Read tool mode (experimental, optional):**

```bash
SCHEMA=$(cat prompts/deck_terms_schema.md)
PROMPT="Use the Read tool to open out/deck_text.txt and extract terms. ${SCHEMA}"

# Only use if USE_READ_TOOL=1 is set
if [[ "${USE_READ_TOOL:-0}" == "1" ]]; then
  printf '%s\n' "$PROMPT" | claude --print \
    --model sonnet \
    --allowedTools "Read" \
    --append-system-prompt "Return only the requested JSON schema. No prose." \
    --output-format json \
    | tee out/claude_raw.json \
    | jq -r '.result' > out/lmm_candidates.json
fi
```

(Stdin and multi-turn patterns based on production CConductor usage.) ([Claude Code][1])

**Model selection:**

```bash
claude --model sonnet -p ...   # set model alias; see CLI --model flag
```

(Per CLI reference.) ([Claude Code][4])

