"""Verification package exports."""

from .matcher import consolidate, main as verify_cli
from .scorer import TermRecord

__all__ = ["consolidate", "verify_cli", "TermRecord"]
