"""issue #566: миграция — нормализует нумерованные списки в data/raw/**/*.md и переотправляет в GAR.

python3 scripts/migrate_fix_numbered_lists.py            # dry-run (счётчик)
python3 scripts/migrate_fix_numbered_lists.py --apply    # правит .md, пишет /tmp/nl_fixed.txt
python3 scripts/migrate_fix_numbered_lists.py --reindex  # reload_by_gar_id для /tmp/nl_fixed.txt
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LIST = Path("/tmp/nl_fixed.txt")
URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")
PAUSE_S = 4.0

_spec = importlib.util.spec_from_file_location("md_tables", ROOT / "src" / "crawler" / "md_tables.py")
_mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mt)


def _reload(gar_id: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if os.environ.get("DS_INGESTION_API_KEY"):
        headers["X-Ingestion-Key"] = os.environ["DS_INGESTION_API_KEY"]
    body = json.dumps({"gar_document_id": gar_id, "recrawl": False}).encode()
    req = urllib.request.Request(f"{URL}/reload_by_gar_id", body, headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reindex", action="store_true")
    a = ap.parse_args()
    if a.reindex:
        ok = err = 0
        for rel in LIST.read_text().split():
            jp = (RAW / rel).with_suffix(".json")
            try:
                gid = json.loads(jp.read_text(encoding="utf-8")).get("gar_document_id")
                if not gid:
                    continue  # не в GAR
                _reload(gid)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {rel}: {exc}")
                err += 1
            time.sleep(PAUSE_S)
        print(f"reindexed ok={ok} err={err}")
        return
    changed = []
    for p in sorted(RAW.rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        n = _mt.normalize_numbered_lists(t)
        if n != t:
            changed.append(str(p.relative_to(RAW)))
            if a.apply:
                p.write_text(n, encoding="utf-8")
    print(f"changed={len(changed)} applied={a.apply}")
    if a.apply:
        LIST.write_text("\n".join(changed))


if __name__ == "__main__":
    main()
