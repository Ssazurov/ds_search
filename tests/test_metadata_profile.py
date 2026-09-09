from src.metadata.profile import build_ingestion_metadata


def test_build_ingestion_metadata_adds_adr_0002_defaults():
    metadata = build_ingestion_metadata(
        source_url="https://example.test/a", source_domain="example.test",
        title="Документ", license="allow", date_indexed="2026-09-09",
    )

    assert metadata["date_indexed"] == "2026-09-09"
    assert metadata["category"] == "basic"
    assert metadata["lifecycle_stage"] == "unspecified"
    assert metadata["comorbidity_tags"] == ""
    assert metadata["reviewed_by"] == ""


def test_build_ingestion_metadata_preserves_curation_values():
    metadata = build_ingestion_metadata(
        source_url="https://example.test/a", source_domain="example.test",
        title="Документ", license="allow", date_indexed="2026-09-09",
        category="comorbidities", lifecycle_stage="medical",
        comorbidity_tags="cardiology,endocrinology", reviewed_by="editor",
    )

    assert metadata["category"] == "comorbidities"
    assert metadata["lifecycle_stage"] == "medical"
    assert metadata["comorbidity_tags"] == "cardiology,endocrinology"
    assert metadata["reviewed_by"] == "editor"
