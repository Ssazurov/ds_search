"""Link glossary terms found in assistant Markdown answers (issue #103)."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from urllib.parse import quote


def highlight_glossary_terms(
    answer: str,
    terms: Sequence[Mapping[str, object]],
    *,
    glossary_path: str = "/glossary",
) -> str:
    """Wrap glossary matches in Markdown links.

    Existing Markdown links, code spans, and fenced code blocks remain unchanged.
    Terms are matched case-insensitively on word boundaries, longest first.
    """
    if not answer or not terms:
        return answer

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in terms:
        term = str(item.get("term") or "").strip()
        term_id = str(item.get("id") or "").strip()
        key = term.casefold()
        if term and term_id and key not in seen:
            entries.append((term, term_id))
            seen.add(key)
    if not entries:
        return answer

    entries.sort(key=lambda entry: len(entry[0]), reverse=True)
    pattern = re.compile(
        r"(?<![\w])(" + "|".join(re.escape(term) for term, _ in entries) + r")(?![\w])",
        re.IGNORECASE,
    )
    ids = {term.casefold(): term_id for term, term_id in entries}
    protected = re.compile(r"(```[\s\S]*?```|`[^`]*`|\[[^\]]+\]\([^\)]+\))")
    def replace_plain(text: str) -> str:
        def replace_match(match: re.Match[str]) -> str:
            matched = match.group(1)
            key = matched.casefold()
            return f"[{matched}]({glossary_path.rstrip('/')}/{quote(ids[key], safe='')})"

        return pattern.sub(replace_match, text)

    parts: list[str] = []
    last = 0
    for match in protected.finditer(answer):
        parts.append(replace_plain(answer[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(replace_plain(answer[last:]))
    return "".join(parts)
