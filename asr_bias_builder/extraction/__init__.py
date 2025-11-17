"""Deck text extraction pipeline."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Iterable, Optional

from ..config import load_config
from .ocr import apply_ocr_normalization
from .pdf import extract_pdf_via_ocr, extract_pdf_via_pdfminer, extract_pdf_via_pymupdf
from .pptx import extract_pptx
from .sections import normalize_text

LOGGER = logging.getLogger("asr_bias_builder.extraction")


def extract_text(path: Path, enable_ocr: bool = False, config: Optional[dict] = None) -> str:
    """Extract and normalize deck text from PDF or PPTX."""
    cfg = config or load_config()
    auto_ocr = bool(cfg.get("auto_ocr", True))
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        strategies = (
            extract_pdf_via_pymupdf,
            extract_pdf_via_pdfminer,
        )
        for strategy in strategies:
            try:
                text = strategy(path)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("%s extraction failed: %s", strategy.__name__, exc)
                continue
            if text and text.strip():
                return normalize_text(apply_ocr_normalization(text, cfg))
        if enable_ocr or auto_ocr:
            LOGGER.info("Falling back to OCR for %s", path.name)
            text = extract_pdf_via_ocr(path)
            return normalize_text(apply_ocr_normalization(text, cfg))
        raise RuntimeError("Unable to extract PDF text; consider --enable-ocr")
    if suffix == ".pptx":
        text = extract_pptx(path)
        return normalize_text(apply_ocr_normalization(text, cfg))
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
        return normalize_text(apply_ocr_normalization(text, cfg))
    raise ValueError(f"Unsupported deck type: {suffix}")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract normalized text from deck files")
    parser.add_argument("deck", type=Path, help="Path to deck (.pdf or .pptx)")
    parser.add_argument("--enable-ocr", action="store_true", help="Allow OCR fallback for PDF with no text layer")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "WARNING"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    text = extract_text(args.deck, enable_ocr=args.enable_ocr)
    print(text)
    return 0


__all__ = ["extract_text", "main", "normalize_text"]
