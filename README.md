# ASR Bias Builder

> Build ASR bias artifacts from presentation decks for Whisper and Google Speech-to-Text

[![CI](https://github.com/yaniv-golan/asr-bias-builder/workflows/CI/badge.svg)](https://github.com/yaniv-golan/asr-bias-builder/actions)
[![PyPI](https://img.shields.io/pypi/v/asr-bias-builder)](https://pypi.org/project/asr-bias-builder/)
[![Python](https://img.shields.io/pypi/pyversions/asr-bias-builder)](https://pypi.org/project/asr-bias-builder/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ASR Bias Builder extracts high-value entities from PDF/PPTX decks and produces:

- `deck_terms.txt` – Whisper `initial_prompt` hotwords
- `phrase_set.json` – Google Speech-to-Text v2 Speech Adaptation PhraseSet
- Structured LLM candidates + verification telemetry for auditability

## Quick Start

```bash
pip install -e .
asr-bias-builder pipeline deck.pdf
```

Artifacts land in `./asr-bias-output/<deck-name>/` by default (deck text, seeds, verified terms, prompt list, phrase set, review markdown) and the cross-run summary lives at `./asr-bias-summary.csv`. Override the locations any time via `--output-dir` / `--summary-csv`.

## Features

- Deterministic PDF/PPTX extraction with OCR normalization
- Seed mining with configurable filters, section weighting, and per-deck overrides
- LLM integration via Claude Code CLI (stdin, streaming JSON, read tool)
- Verification layer merges deterministic + LLM terms with alias tracking
- Artifact builders for Whisper prompts and Google Speech Adaptation PhraseSets
- Review markdown + CSV summaries for production runs
- Docker, CI/CD, docs, tests, and examples ready for GitHub publishing

## Repository Layout

```
asr-bias-builder/
├── asr_bias_builder/        # Python package
├── config/                  # Default + example configs
├── docs/                    # User + architecture docs
├── examples/                # Synthetic sample decks & configs
├── scripts/                 # Shell helpers (make_bias.sh, claudecode, etc.)
├── tests/                   # Pytest suite and fixtures
├── docker/                  # Dockerfiles & compose for dev/prod
└── .github/                 # Workflows, templates, Dependabot
```

See the [docs](docs/README.md) for detailed installation, configuration, and architecture notes.
