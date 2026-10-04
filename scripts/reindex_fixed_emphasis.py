"""Реиндексация в GAR документов, исправленных миграцией emphasis (bold-merge).

Читает gar_document_id из sidecar .json и вызывает /reload_by_gar_id.
Без внешних зависимостей. Запуск: python3 scripts/reindex_fixed_tables.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

RAW_ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"
PAUSE_S = 4.0  # /reload: 20/мин глобально (ADR-0008)
URL = os.environ.get("DS_INGESTION_URL", "http://127.0.0.1:8200")

FILES = [
    "foma.ru/1438163b9e439b03",
    "news.un.org/fba4c1535adf0d30",
    "downsideup.org/o-tekh-komu-ya-klanyayus-do-zemli",
    "downsideup.org/seme-neobkhodim-marshrut-puti-i-podderzhka",
    "downsideup.org/darya-oykiz-moya-nezhnost",
    "downsideup.org/lekarstvo-ot-ksenofobii",
]


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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ok = fail = 0
    for rel in FILES:
        jp = RAW_ROOT / f"{rel}.json"
        try:
            gar_id = json.loads(jp.read_text(encoding="utf-8")).get("gar_document_id")
            if not gar_id:
                raise RuntimeError("нет gar_document_id в sidecar")
            if args.dry_run:
                print(f"DRY {rel} -> {gar_id}")
                continue
            rep = _reload(gar_id)
            print(f"OK  {rel} -> {gar_id}: {rep.get('changed_fields')}")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {rel}: {exc}")
            fail += 1
        time.sleep(PAUSE_S)
    print(f"ok={ok} err={fail}")


if __name__ == "__main__":
    main()
