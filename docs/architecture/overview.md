# Architecture Overview

The pipeline follows the flow documented in `docs/internal/ASR-bias-artifacts.md`:

1. **Extraction** – deterministic PDF/PPTX text extraction with OCR fallback.
2. **Mining** – regex-driven candidate discovery plus section-aware weighting.
3. **LLM pass** – Claude Code CLI via stdin or streaming JSON (see `docs/integration.md`).
4. **Verification** – Exact matching and alias handling to merge deterministic + LLM terms.
5. **Artifacts** – Whisper prompt list + Google STT PhraseSet builders with validation.
6. **Reporting** – Markdown review and CSV aggregation per run.
