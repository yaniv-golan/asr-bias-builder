"""Logging utilities."""
from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: Optional[str] = None) -> None:
    """Configure structured logging once per process."""
    if getattr(configure_logging, "_configured", False):
        return
    logging.basicConfig(
        level=getattr(logging, str(level or "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    configure_logging._configured = True


__all__ = ["configure_logging"]
