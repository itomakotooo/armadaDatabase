"""Parsers for extracting champion listings from HellHades tier list pages."""
from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, List, Tuple

from .html_tree import Node, parse_html
from .parser import normalize_whitespace, slugify

# Attributes commonly used by HellHades champion listing widgets.
CANDIDATE_SLUG_ATTRS = [
    "data-champion-slug",
    "data-champion",
    "data-slug",
    "data-slug-name",
]

CANDIDATE_NAME_ATTRS = [
    "data-champion-name",
    "data-name",
    "data-title",
]


def _slug_from_href(href: str) -> str | None:
    if not href:
        return None
    cleaned = href.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    if not cleaned:
        return None
    parts = cleaned.split("/")
    if not parts:
        return None
    last = parts[-1]
    if not last:
        return None
    return slugify(last)


def _iter_candidate_nodes(root: Node) -> Iterable[Node]:
    for node in root.iter_nodes():
        if node.tag in {"script", "style"}:
            continue
        yield node


def extract_champions(html: str) -> List[Tuple[str, str]]:
    """Return ``(slug, name)`` pairs for champions found in the HellHades tier list."""

    root = parse_html(html)
    champions: "OrderedDict[str, str]" = OrderedDict()

    for node in _iter_candidate_nodes(root):
        slug_value = None
        for attr in CANDIDATE_SLUG_ATTRS:
            if attr in node.attrs and node.attrs[attr].strip():
                slug_value = node.attrs[attr]
                break

        name_value = None
        for attr in CANDIDATE_NAME_ATTRS:
            if attr in node.attrs and node.attrs[attr].strip():
                name_value = node.attrs[attr]
                break

        text_value = normalize_whitespace(node.text())
        slug: str | None = None
        name: str | None = None

        if slug_value:
            slug = slugify(slug_value)
        if node.tag == "a" and not slug:
            slug = _slug_from_href(node.attrs.get("href", ""))
        if not slug and name_value:
            slug = slugify(name_value)
        if text_value:
            name = text_value
        elif name_value:
            name = normalize_whitespace(name_value)

        if slug and name and slug not in champions:
            champions[slug] = name

    return list(champions.items())


__all__ = ["extract_champions"]
