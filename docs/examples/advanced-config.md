# Advanced Configuration Example

Apply `config/examples/advanced.yml` to enable spaCy POS filtering and alias inclusion:

```bash
asr-bias-builder pipeline deck.pdf \
  --config config/examples/advanced.yml
```

This enables stricter prompt ordering (PERSON→ORG→PRODUCT→TECH) and ensures alias-only terms still appear when `--allow-llm-aliases` is used during verification.
