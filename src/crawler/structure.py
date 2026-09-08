"""Adaptive HTML structure detection for source-specific Markdown output.

The parser deliberately uses only the Python standard library.  Profiles are
data, so adding a site's alternative layout does not require changing the
conversion algorithm.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit
import re


@dataclass(frozen=True)
class StructureProfile:
    """Rules for turning visual heading markers into semantic HTML headings."""

    name: str
    heading_classes: tuple[str, ...] = ()
    question_container_classes: tuple[str, ...] = ()
    remove_classes: tuple[str, ...] = ()
    bold_heading_classes: tuple[str, ...] = ()
    bold_heading_pattern: str | None = None
    heading_level: int = 2


PROFILES = {"sindromlubvi.ru": StructureProfile(
    name="sindromlubvi",
    heading_classes=("sln-news-title", "sln-content-title"),
    question_container_classes=("sln-asks",),
    remove_classes=(
        "sln-mobile-menu",
        "sln-header-wrap",
        "sln-breadcrumb-wrap",
        "sln-back-2-2",
        "cookie-consent-banner",
        "cookie-consent-modal",
    ),
    bold_heading_classes=("sln-news-wrap",),
    # Bitrix article pages use <b> followed by <br> for section titles.
    bold_heading_pattern=r"^(почему|что важно|как|зачем|итоги|программа)\b",
)}


@dataclass
class _Node:
    tag: str
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    children: list["_Node | str"] = field(default_factory=list)
    parent: "_Node | None" = None

    def text(self) -> str:
        return " ".join(child if isinstance(child, str) else child.text() for child in self.children).strip()


_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("__root__")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        node = _Node(tag, attrs, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag.lower():
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _class_names(node: _Node) -> set[str]:
    return {item for key, value in node.attrs if key == "class" for item in (value or "").split()}


def _walk(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _replace_tag(node: _Node, tag: str) -> None:
    node.tag = tag
    node.attrs = [(key, value) for key, value in node.attrs if key not in {"class", "style"}]


def _remove_matching_nodes(node: _Node, classes: tuple[str, ...]) -> None:
    wanted = set(classes)
    kept = []
    for child in node.children:
        if isinstance(child, _Node) and _class_names(child).intersection(wanted):
            continue
        if isinstance(child, _Node):
            _remove_matching_nodes(child, classes)
        kept.append(child)
    node.children = kept


def _has_ancestor_class(node: _Node, classes: tuple[str, ...]) -> bool:
    current = node.parent
    wanted = set(classes)
    while current is not None:
        if _class_names(current).intersection(wanted):
            return True
        current = current.parent
    return False


def _serialize(node: _Node) -> str:
    result = []
    for child in node.children:
        if isinstance(child, str):
            result.append(escape(child, quote=False))
            continue
        attrs = "".join(f' {key}="{escape(value or "", quote=True)}"' for key, value in child.attrs)
        if child.tag in _VOID_TAGS:
            result.append(f"<{child.tag}{attrs}>")
        else:
            result.append(f"<{child.tag}{attrs}>{_serialize(child)}</{child.tag}>")
    return "".join(result)


def detect_structure_profile(url: str) -> StructureProfile | None:
    """Return the registered profile whose domain occurs in ``url``."""
    host = urlsplit(url).netloc.lower().split(":", 1)[0]
    return next((profile for domain, profile in PROFILES.items() if host == domain or host.endswith("." + domain)), None)


def normalize_headings(html: str, profile: StructureProfile | None = None) -> str:
    """Add semantic headings while retaining all meaningful source content."""
    if not html or profile is None:
        return html
    parser = _TreeParser()
    parser.feed(html)
    _remove_matching_nodes(parser.root, profile.remove_classes)
    for node in _walk(parser.root):
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            continue
        classes = _class_names(node)
        if classes.intersection(profile.heading_classes):
            _replace_tag(node, f"h{profile.heading_level}")
        elif node.tag == "div" and node.parent is not None and _has_ancestor_class(node, profile.question_container_classes):
            first = next((child for child in node.parent.children if isinstance(child, _Node)), None)
            if first is node and node.text().endswith("?"):
                _replace_tag(node, f"h{profile.heading_level}")
        elif node.tag == "b" and (
            classes.intersection(profile.bold_heading_classes)
            or _has_ancestor_class(node, profile.bold_heading_classes)
        ):
            text = re.sub(r"\s+", " ", node.text())
            if profile.bold_heading_pattern and re.search(profile.bold_heading_pattern, text, re.I):
                _replace_tag(node, f"h{profile.heading_level}")
    return _serialize(parser.root)


def normalize_headings_for_url(html: str, url: str) -> str:
    """Normalize headings using the profile selected by a page URL."""
    return normalize_headings(html, detect_structure_profile(url))
