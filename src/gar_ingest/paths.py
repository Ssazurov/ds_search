"""Разрешение content_path sidecar-JSON (issue #400).

content_path бывает host-абсолютным, контейнерным (/app/...) или относительным;
если он не существует, ищем файл рядом с sidecar .json (тот же stem, .md/.pdf).
"""
from pathlib import Path


def resolve_content_path(doc_json_path, content_path) -> Path:
    p = Path(content_path)
    if p.exists():
        return p
    base = Path(doc_json_path)
    for ext in (p.suffix, ".md", ".pdf"):
        if not ext:
            continue
        cand = base.with_suffix(ext)
        if cand.exists():
            return cand
    return p
