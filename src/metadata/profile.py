"""Общий профиль sidecar-метаданных для документов RAG (issue #33, ADR-0002)."""
from __future__ import annotations

from datetime import date


DEFAULT_CATEGORY = "basic"
LIFECYCLE_STAGES = [
    "unspecified", "prenatal", "early_development", "preschool_school",
    "medical", "legal_benefits", "adult_life",
]
UNSPECIFIED_LIFECYCLE_STAGE = LIFECYCLE_STAGES[0]


def build_ingestion_metadata(
    *,
    source_url: str,
    source_domain: str,
    title: str,
    license: str,
    category: str | None = None,
    lifecycle_stage: str | None = None,
    comorbidity_tags: str | None = None,
    reviewed_by: str | None = None,
    date_indexed: str | None = None,
    **metadata: object,
) -> dict:
    """Build mandatory ADR-0002 fields without inferring medical facts.

    ``unspecified`` marks a document that still needs lifecycle curation;
    it is intentionally not guessed from page text or source direction.
    Tags and reviewer are text fields compatible with GAR's metadata API.
    """
    result = {
        "source_url": source_url,
        "source_domain": source_domain,
        "title": title,
        "license": license,
        "date_indexed": date_indexed or date.today().isoformat(),
        "category": category or DEFAULT_CATEGORY,
        "lifecycle_stage": lifecycle_stage or UNSPECIFIED_LIFECYCLE_STAGE,
        "comorbidity_tags": comorbidity_tags or "",
        "reviewed_by": reviewed_by or "",
    }
    result.update(metadata)
    return result
