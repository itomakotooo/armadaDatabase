"""Data models for champion scraping and simulation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class StatRecord:
    """Represents a stat value extracted from the Stats tab.

    Attributes:
        key: Normalised stat key derived from the row label (e.g. ``"hp"``).
        variant: Optional variant for the stat (e.g. ``"level 60"`` or ``"ascended"``).
        label: Human readable label combining the row label and variant.
        raw_value: Raw textual value extracted from the table.
        numeric_value: Parsed numeric representation when available.
    """

    key: str
    variant: Optional[str]
    label: str
    raw_value: str
    numeric_value: Optional[float] = None

    def variant_key(self) -> str:
        """Return the variant value suitable for dictionary keys."""

        return self.variant or ""


@dataclass
class ChampionData:
    """Represents all champion information extracted from a page."""

    slug: str
    name: str
    basic_info: Dict[str, str] = field(default_factory=dict)
    stats: List[StatRecord] = field(default_factory=list)

    def stats_by_key(self) -> Dict[str, List[StatRecord]]:
        """Group stats by their normalised key."""

        grouped: Dict[str, List[StatRecord]] = {}
        for record in self.stats:
            grouped.setdefault(record.key, []).append(record)
        return grouped

    def all_stat_variants(self, key: str) -> Iterable[StatRecord]:
        """Iterate over stat records that match the provided key."""

        for record in self.stats:
            if record.key == key:
                yield record
