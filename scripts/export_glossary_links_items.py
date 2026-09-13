"""Генератор поэлементных data/raw/*_items/ для glossary.json/links.json
(issue #131). Одноразовый скрипт, не для регулярного запуска.

Каждый термин/ссылка -> отдельный <slug>.json + <slug>.md в
data/raw/glossary_items/ и data/raw/links_items/, готовые для
`python -m src.adapter.cli glossary_items` / `links_items` (ds_ingestion).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from src.metadata.glossary_links_mapping import map_glossary_item, map_link_item

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGE = "Все возрасты"


def slugify(text: str, fallback: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-zа-я0-9]+", "-", text, flags=re.IGNORECASE)
    text = text.strip("-")
    return text or fallback


def write_item(out_dir: Path, slug: str, meta: dict, body: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    meta = dict(meta, content_path=str(out_dir / f"{slug}.md"))
    (out_dir / f"{slug}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def build_glossary_items() -> int:
    items = json.loads((ROOT / "data" / "exports" / "glossary.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "data" / "raw" / "glossary_items"
    n = 0
    for it in items:
        mapped = map_glossary_item(it)
        slug = f"glossary-{it['id']:03d}-" + slugify(it["term"], str(it["id"]))
        body = f"# {it['term']}\n\n{it['definition']}\n"
        if it.get("en"):
            body += f"\nEnglish: {it['en']}\n"
        meta = {
            "source_url": f"internal://ds_search/glossary/{it['id']}",
            "source_domain": "ds_search",
            "title": it["term"],
            "license": "own_generated",
            "target_audience": mapped["target_audience"],
            "age": mapped["age"] or DEFAULT_AGE,
            "direction": mapped["direction"],
            "category": mapped["category"],
            "doc_type": mapped["doc_type"],
        }
        write_item(out_dir, slug, meta, body)
        n += 1
    return n


def build_link_items() -> int:
    items = json.loads((ROOT / "data" / "exports" / "links.json").read_text(encoding="utf-8"))
    out_dir = ROOT / "data" / "raw" / "links_items"
    n = 0
    for idx, it in enumerate(items, start=1):
        mapped = map_link_item(it)
        domain = urlparse(it["url"]).netloc or "unknown"
        slug = f"link-{idx:03d}-" + slugify(it["name"], str(idx))
        body = f"# {it['name']}\n\n{it.get('description', '')}\n\nСсылка: {it['url']}\n"
        meta = {
            "source_url": it["url"],
            "source_domain": domain,
            "title": it["name"],
            "license": "own_generated",
            "target_audience": mapped["target_audience"],
            "age": mapped["age"] or DEFAULT_AGE,
            "direction": mapped["direction"],
            "category": mapped["category"],
            "doc_type": mapped["doc_type"],
        }
        write_item(out_dir, slug, meta, body)
        n += 1
    return n


if __name__ == "__main__":
    g = build_glossary_items()
    l = build_link_items()
    print(f"glossary_items: {g}, links_items: {l}")
