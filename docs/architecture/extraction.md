# Extraction Details

- PyMuPDF is preferred; pdfminer.six is the fallback for text-layer PDFs.
- OCR fallback (pytesseract + Pillow) is triggered when both extractors return empty text or `--enable-ocr` is passed.
- PPTX extraction walks slides, shapes, and tables while tagging `[Slide N]` markers.
- OCR normalization applies regex replacements + alias substitution (`Liam Nguyn`→`Liam Nguyen`, `Al`→`AI`).
- Text is normalized via `unicodedata.normalize`, newline cleanup, and whitespace collapsing.
