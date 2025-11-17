"""PDF extraction helpers."""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
except ImportError:  # pragma: no cover
    pdfminer_extract_text = None  # type: ignore

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore


def extract_pdf_via_pymupdf(path: Path) -> str:
    """Extract text via PyMuPDF."""
    if fitz is None:
        raise RuntimeError("PyMuPDF not installed")
    doc = fitz.open(path)
    texts: List[str] = []
    for page in doc:
        text = page.get_text("text")
        if text:
            texts.append(text)
    doc.close()
    return "\n".join(texts)


def extract_pdf_via_pdfminer(path: Path) -> str:
    """Extract text with pdfminer.six."""
    if pdfminer_extract_text is None:
        raise RuntimeError("pdfminer.six not installed")
    return pdfminer_extract_text(str(path))


def extract_pdf_via_ocr(path: Path) -> str:
    """Fallback to OCR when the PDF lacks a text layer."""
    if pytesseract is None or Image is None or fitz is None:
        raise RuntimeError("pytesseract + pillow + PyMuPDF required for OCR")
    doc = fitz.open(path)
    ocr_texts: List[str] = []
    for page in doc:
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_texts.append(pytesseract.image_to_string(img))
    doc.close()
    return "\n".join(ocr_texts)


__all__ = ["extract_pdf_via_pymupdf", "extract_pdf_via_pdfminer", "extract_pdf_via_ocr"]
