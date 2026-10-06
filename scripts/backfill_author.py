#!/usr/bin/env python3
"""issue #571: backfill author для статей с пустым author (resolve_author, #569).

python3 scripts/backfill_author.py [--domain D] [--ids id1,id2] [--limit N] [--fetch] [--llm]   # dry-run
python3 scripts/backfill_author.py ... --apply     # пишет json, список -> /tmp/author_fixed.txt
python3 scripts/backfill_author.py --reindex       # reload_by_gar_id для /tmp/author_fixed.txt
--fetch: скачивать HTML источника (нужен для HTML-правил и og:site_name); без него — только тело .md и config.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DS_AUTHOR_LLM", "0")
from src.metadata.author_resolver import default_author_llm, resolve_author  # noqa: E402
from src.metadata.meta_extract import extract_author_from_markdown  # noqa: E402

RAW = ROOT / "data" / "raw"
LIST = Path("/tmp/author_fixed.txt")
URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")
PAUSE_S = 4.0
UA = {"User-Agent": "Mozilla/5.0 (ds-backfill)"}


def _get_html(url: str) -> str:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        print(f"fetch ERR {url}: {exc}")
        return ""


def _reload(gar_id: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if os.environ.get("DS_INGESTION_API_KEY"):
        headers["X-Ingestion-Key"] = os.environ["DS_INGESTION_API_KEY"]
    body = json.dumps({"gar_document_id": gar_id, "recrawl": False}).encode()
    with urllib.request.urlopen(urllib.request.Request(f"{URL}/reload_by_gar_id", body, headers), timeout=120) as r:
        return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--domain")
    ap.add_argument("--ids", help="gar_document_id через запятую")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.reindex:
        ok = err = 0
        for rel in LIST.read_text().split():
            try:
                gid = json.loads((RAW / rel).read_text(encoding="utf-8")).get("gar_document_id")
                if gid:
                    _reload(gid)
                    ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {rel}: {exc}")
                err += 1
            time.sleep(PAUSE_S)
        print(f"reindexed ok={ok} err={err}")
        return
    ids = set(a.ids.split(",")) if a.ids else None
    changed: list[str] = []
    for jp in sorted(RAW.rglob("*.json")):
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(meta, dict) or meta.get("author") or meta.get("doc_type") != "article":
            continue
        if a.domain and meta.get("source_domain") != a.domain:
            continue
        if ids and meta.get("gar_document_id") not in ids:
            continue
        if a.limit and len(changed) >= a.limit:
            break
        md = jp.with_suffix(".md")
        text = md.read_text(encoding="utf-8") if md.exists() else ""
        html = _get_html(meta.get("source_url", "")) if a.fetch else ""
        if a.fetch:
            time.sleep(1.0)
        new = resolve_author(
            extract_author_from_markdown(text), html=html, markdown=text,
            domain=meta.get("source_domain", ""), llm=default_author_llm if a.llm else None,
        )
        if not new:
            continue
        rel = str(jp.relative_to(RAW))
        print(f"{rel}: {new}")
        changed.append(rel)
        if a.apply:
            meta["author"] = new
            jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"changed={len(changed)} applied={a.apply}")
    if a.apply:
        LIST.write_text("\n".join(changed))


if __name__ == "__main__":
    main()
