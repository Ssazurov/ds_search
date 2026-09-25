"""Общий профиль sidecar-метаданных для документов RAG (issue #33, ADR-0002)."""
from __future__ import annotations

from datetime import date


# issue #186: раньше был захардкожен DEFAULT_CATEGORY = "basic" — значение,
# не входящее в опции controlled-поля category в текущей GAR-схеме (у
# category нет собственного варианта для direction=news, например). Без
# явного category лучше не проставлять поле вовсе, чем подставлять
# невалидное значение и ловить 422 "unknown value for controlled field".
def build_ingestion_metadata(
    *,
    source_url: str,
    source_domain: str,
    title: str,
    license: str,
    category: str | None = None,
    comorbidity_tags: str | None = None,
    reviewed_by: str | None = None,
    date_indexed: str | None = None,
    **metadata: object,
) -> dict:
    """Build mandatory ADR-0002 fields without inferring medical facts.

    Tags and reviewer are text fields compatible with GAR's metadata API.
    lifecycle_stage removed (ADR-0002-amend-1): field was never wired to
    live retrieval, dropped from the contract instead of staying unused.
    """
    result = {
        "source_url": source_url,
        "source_domain": source_domain,
        "title": title,
        "license": license,
        "date_indexed": date_indexed or date.today().isoformat(),
        "category": category,
        "comorbidity_tags": comorbidity_tags or "",
        "reviewed_by": reviewed_by or "",
    }
    result.update(metadata)
    return result
