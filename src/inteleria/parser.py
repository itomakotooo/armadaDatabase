"""Parsing utilities for extracting champion data from Inteleria pages."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .html_tree import Node, parse_html
from .models import ChampionData, StatRecord


SECTION_TAGS = {"div", "section", "article", "main"}


@dataclass
class TableCell:
    text: str
    is_header: bool


@dataclass
class TableRow:
    cells: List[TableCell]

    def texts(self) -> List[str]:
        return [cell.text for cell in self.cells]

    def is_header_row(self) -> bool:
        return all(cell.is_header for cell in self.cells)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def canonical_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_variant(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = canonical_key(value)
    return cleaned or None


def slugify(value: str) -> str:
    cleaned = canonical_key(value)
    return cleaned.replace(" ", "-")


def parse_numeric(raw: str) -> Optional[float]:
    cleaned = raw.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "")
    percent = False
    if cleaned.endswith("%"):
        percent = True
        cleaned = cleaned[:-1]
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if percent:
        return value / 100.0
    return value


def parse_table(node: Node) -> List[TableRow]:
    rows: List[TableRow] = []
    for child in node.children:
        if isinstance(child, Node) and child.tag == "tr":
            cells: List[TableCell] = []
            for cell in child.children:
                if isinstance(cell, Node) and cell.tag in {"td", "th"}:
                    text = normalize_whitespace(cell.text())
                    cells.append(TableCell(text=text, is_header=(cell.tag == "th")))
            if cells:
                rows.append(TableRow(cells=cells))
    return rows


def find_section(root: Node, keywords: Sequence[str]) -> Optional[Node]:
    lowered_keywords = [kw.lower() for kw in keywords]
    for node in root.iter_nodes():
        if node.tag not in SECTION_TAGS and node.tag != "table":
            continue
        attributes = " ".join(node.attrs.values()).lower()
        if any(keyword in attributes for keyword in lowered_keywords):
            return node
    return None


def extract_basic_info(root: Node) -> Dict[str, str]:
    container = find_section(root, ["basic-info", "basic info"])
    table_node: Optional[Node] = None
    if container is not None:
        table_node = container.find(lambda node: node.tag == "table")
    if table_node is None:
        table_node = root.find(lambda node: node.tag == "table")
    if table_node is None:
        raise ValueError("Basic info table could not be located")

    rows = parse_table(table_node)
    basic_info: Dict[str, str] = {}
    for row in rows:
        texts = row.texts()
        if len(texts) >= 2:
            key = normalize_whitespace(texts[0])
            value = normalize_whitespace(" ".join(texts[1:]))
            if key:
                basic_info[key] = value
    return basic_info


def extract_stats(root: Node) -> List[StatRecord]:
    container = find_section(root, ["stats", "statistics"])
    table_node: Optional[Node] = None
    if container is not None:
        table_node = container.find(lambda node: node.tag == "table")
    if table_node is None:
        # Fallback to find the second table in the document if available.
        tables = [node for node in root.iter_nodes() if node.tag == "table"]
        if len(tables) >= 2:
            table_node = tables[1]
        elif tables:
            table_node = tables[0]
    if table_node is None:
        raise ValueError("Stats table could not be located")

    rows = parse_table(table_node)
    if not rows:
        return []

    header: Optional[List[str]] = None
    if rows[0].is_header_row():
        header = [normalize_whitespace(cell.text) for cell in rows[0].cells]
        rows = rows[1:]

    stats: List[StatRecord] = []
    for row in rows:
        values = row.texts()
        if not values:
            continue
        base_name = normalize_whitespace(values[0])
        if not base_name:
            continue
        key = canonical_key(base_name)
        if header and len(header) > 1:
            for index, raw in enumerate(values[1:], start=1):
                if index >= len(header):
                    variant_label = f"column-{index}"
                else:
                    variant_label = normalize_whitespace(header[index])
                variant = canonical_variant(variant_label)
                label = f"{base_name} ({variant_label})"
                numeric_value = parse_numeric(raw)
                stats.append(
                    StatRecord(
                        key=key,
                        variant=variant,
                        label=label,
                        raw_value=raw,
                        numeric_value=numeric_value,
                    )
                )
        else:
            value = values[1] if len(values) > 1 else ""
            numeric_value = parse_numeric(value)
            stats.append(
                StatRecord(
                    key=key,
                    variant=None,
                    label=base_name,
                    raw_value=value,
                    numeric_value=numeric_value,
                )
            )
    return stats


def extract_name(root: Node) -> str:
    heading = root.find(lambda node: node.tag in {"h1", "h2"})
    if heading is not None:
        text = heading.text()
        if text:
            return normalize_whitespace(text)
    title = root.find(lambda node: node.tag == "title")
    if title is not None:
        text = title.text()
        if text:
            return normalize_whitespace(text)
    raise ValueError("Champion name could not be determined")


def parse_champion(html: str, slug: Optional[str] = None) -> ChampionData:
    root = parse_html(html)
    name = extract_name(root)
    computed_slug = slug or slugify(name)
    basic_info = extract_basic_info(root)
    stats = extract_stats(root)
    return ChampionData(slug=computed_slug, name=name, basic_info=basic_info, stats=stats)


__all__ = [
    "parse_champion",
    "extract_basic_info",
    "extract_stats",
    "extract_name",
    "slugify",
]
