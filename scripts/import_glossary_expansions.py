"""Импорт сокращений из ds_glossary.xlsx в GAR (issue #30).

Запуск: python -m scripts.import_glossary_expansions [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = ROOT.parent / "data" / "ds_glossary.xlsx"


def _term_forms(term: str) -> tuple[str, list[str]] | None:
    match = re.match(r"^([^()]+?)\s*\(([^()]+)\)$", term.strip())
    if match:
        left, right = match.group(1).strip(), match.group(2).strip()
        left_acronym = bool(re.fullmatch(r"[А-ЯA-ZЁ][А-ЯA-ZЁ0-9.-]{1,11}", left))
        right_acronym = bool(re.fullmatch(r"[А-ЯA-ZЁ][А-ЯA-ZЁ0-9.-]{1,11}", right))
        if left_acronym:
            return left, [right] if right_acronym else []
        if right_acronym:
            return right, []
    if re.fullmatch(r"[А-ЯA-ZЁ][А-ЯA-ZЁ0-9.-]{1,11}", term.strip()):
        return term.strip(), []
    return None


def abbreviation_terms(path: Path = DEFAULT_XLSX) -> list[dict[str, object]]:
    """Выбирает только короткая форма -> полная форма из колонки definition."""
    from scripts.export_glossary_links import read_glossary

    result = []
    for row in read_glossary(path):
        term = str(row["term"])
        forms = _term_forms(term)
        if not forms:
            continue
        short, aliases = forms
        definition = str(row["definition"]).strip().rstrip(".")
        if not definition:
            continue
        result.append({"term": short, "expansion": definition, "aliases": aliases, "status": "manual", "active": True})
    return result


class GlossaryImportClient:
    def __init__(self, base_url: str, user_id: str, tenant_id: str | None = None):
        headers = {"X-User-ID": user_id}
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        self.client = httpx.Client(base_url=base_url, headers=headers, timeout=30)

    def close(self) -> None:
        self.client.close()

    def ensure_dataset(self, name: str) -> str:
        response = self.client.get("/ingestion/datasets")
        response.raise_for_status()
        for dataset in response.json().get("datasets", []):
            if dataset.get("name") == name:
                return dataset["id"]
        response = self.client.post("/ingestion/datasets", json={"name": name})
        response.raise_for_status()
        return response.json()["dataset"]["id"]

    def import_terms(self, dataset_id: str, terms: list[dict[str, object]], dry_run: bool = False) -> tuple[int, int]:
        existing = self.client.get(f"/datasets/{dataset_id}/glossary-terms")
        existing.raise_for_status()
        known = {str(item["term"]).casefold() for item in existing.json().get("terms", [])}
        created = 0
        skipped = 0
        for payload in terms:
            if str(payload["term"]).casefold() in known:
                skipped += 1
                continue
            if not dry_run:
                response = self.client.post(f"/datasets/{dataset_id}/glossary-terms", json=payload)
                response.raise_for_status()
            created += 1
        return created, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    terms = abbreviation_terms(args.xlsx)
    print(f"Найдено сокращений: {len(terms)}")
    if args.dry_run:
        for term in terms:
            print(f"{term['term']} -> {term['expansion']}")
        return
    client = GlossaryImportClient(
        os.environ.get("GAR_CORE_API_URL", "http://127.0.0.1:8100"),
        os.environ.get("GAR_USER_ID", "admin-ui"), os.environ.get("GAR_TENANT_ID"),
    )
    try:
        dataset_id = os.environ.get("GAR_DATASET_ID") or client.ensure_dataset(
            os.environ.get("GAR_DATASET_NAME", "sindrom-dauna")
        )
        created, skipped = client.import_terms(dataset_id, terms)
        print(f"Загружено: {created}, уже были: {skipped}, dataset_id: {dataset_id}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
