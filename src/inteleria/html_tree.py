"""A lightweight HTML tree builder used for scraping without external deps."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Union


# HTML void elements that should not produce closing tags.
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


@dataclass
class Node:
    """Represents an element in the parsed HTML tree."""

    tag: str
    attrs: Dict[str, str]
    children: List[Union["Node", str]] = field(default_factory=list)

    def append(self, child: Union["Node", str]) -> None:
        self.children.append(child)

    def iter_nodes(self) -> Iterator["Node"]:
        """Depth-first traversal yielding element nodes."""

        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter_nodes()

    def find(self, predicate) -> Optional["Node"]:
        for node in self.iter_nodes():
            if predicate(node):
                return node
        return None

    def find_all(self, predicate) -> List["Node"]:
        return [node for node in self.iter_nodes() if predicate(node)]

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.attrs.get(name, default)

    def text(self) -> str:
        """Return concatenated text content under this node."""

        parts: List[str] = []
        self._collect_text(parts)
        return " ".join(part for part in parts if part).strip()

    def _collect_text(self, parts: List[str]) -> None:
        for child in self.children:
            if isinstance(child, str):
                text = child.strip()
                if text:
                    parts.append(text)
            else:
                child._collect_text(parts)

    def iter_child_nodes(self, *tags: str) -> Iterator["Node"]:
        desired = {tag.lower() for tag in tags}
        for child in self.children:
            if isinstance(child, Node) and (not desired or child.tag in desired):
                yield child


class TreeBuilder(HTMLParser):
    """Builds a simple HTML tree with :class:`Node` objects."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self._stack: List[Node] = [self.root]
        self._skip_text_stack: List[bool] = []

    def error(self, message: str) -> None:  # pragma: no cover - required override
        raise ValueError(message)

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attributes = {name: (value or "") for name, value in attrs}
        node = Node(tag, attributes)
        self._stack[-1].append(node)
        if tag in {"script", "style"}:
            self._skip_text_stack.append(True)
        else:
            self._skip_text_stack.append(False)
        if tag not in VOID_ELEMENTS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_text_stack:
            self._skip_text_stack.pop()
        # Pop until matching tag is found to keep tree consistent even with malformed HTML.
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_startendtag(self, tag: str, attrs: Sequence[tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._skip_text_stack:
            self._skip_text_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip_text_stack or not self._skip_text_stack[-1]:
            text = data.strip()
            if text:
                self._stack[-1].append(text)

    def handle_comment(self, data: str) -> None:  # pragma: no cover - comments ignored
        pass


def parse_html(html: str) -> Node:
    """Parse HTML into a :class:`Node` tree."""

    builder = TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root
