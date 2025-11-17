# Installation

## Requirements
- Python 3.11+
- Claude Code CLI v1.0.54+
- System packages: `tesseract-ocr`, `jq`, `stat`
- Python libs: PyMuPDF, pdfminer.six, python-pptx, pytesseract, Pillow, PyYAML

## Steps
1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `pip install -e .`
4. Install Claude CLI:
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude  # first run prompts for login
   ```
5. Verify versions:
   ```bash
   asr-bias-builder --help
   claude --version
   ```
