"""Scoring utilities for verified terms."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class TermRecord:
    """Intermediate representation of a merged term."""

    canonical: str
    variants: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    source: str = "unknown"
    priority: float = 0.5
    present_in_deck: bool = False
    frequency: int = 0
    notes: str = ""

    def to_payload(self) -> Dict[str, object]:
        score = min(
            1.0,
            max(
                0.0,
                0.4 * self.priority
                + 0.3 * min(self.frequency / 5, 1.0)
                + 0.3 * (1 if self.present_in_deck else 0),
            ),
        )
        return {
            "canonical": self.canonical,
            "variants": sorted(set(self.variants)) if self.variants else [],
            "classes": self.classes,
            "source": self.source,
            "present_in_deck": self.present_in_deck,
            "frequency": self.frequency,
            "priority": round(self.priority, 3),
            "score": round(score, 3),
            "notes": self.notes,
        }


def assess_seed_quality(
    seeds: Optional[List[Dict[str, object]]],
    llm_terms: List[Dict[str, object]],
    canonicalize: Callable[[str], str],
    normalize: Callable[[str], str],
) -> Tuple[bool, Dict[str, float]]:
    """Heuristically determine whether deterministic seeds are reliable."""
    stats = {
        "seed_count": float(len(seeds) if seeds else 0),
        "llm_count": float(len(llm_terms)),
        "overlap_ratio": 0.0,
        "seed_llm_ratio": float("inf"),
    }
    if not seeds or not llm_terms:
        stats["seed_llm_ratio"] = stats["seed_count"] / stats["llm_count"] if stats["llm_count"] else float("inf")
        return False, stats

    seed_set = {
        canonicalize(normalize(str(entry.get("term", "")))).lower()
        for entry in seeds
        if entry.get("term")
    }
    llm_set = {
        canonicalize(normalize(str(item.get("canonical", "")))).lower()
        for item in llm_terms
        if item.get("canonical")
    }
    overlap = seed_set.intersection(llm_set)
    stats["overlap_ratio"] = (len(overlap) / len(llm_set)) if llm_set else 0.0
    stats["seed_llm_ratio"] = (len(seed_set) / len(llm_set)) if llm_set else float("inf")
    fallback = stats["seed_llm_ratio"] > 20 or stats["overlap_ratio"] < 0.2
    return fallback, stats


__all__ = ["TermRecord", "assess_seed_quality"]
