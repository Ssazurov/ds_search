"""Настройки источников для краулера (issue #2, ADR-001)."""
from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    name: str
    domain: str
    seed_urls: list[str]
    keywords: list[str]  # для relevance-фильтра (BM25/keyword scorer)
    max_pages: int = 100
    allowed_formats: tuple[str, ...] = (".html", ".pdf")
    direction: str = "methodology"  # см. ADR-001 п.2 (enum направлений)
    # issue #8 / ADR-001 п.3b: конкретные RU-слаги источника (не общий
    # англоязычный список) — служебные/листинговые/интерактивные разделы.
    exclude_slugs: tuple[str, ...] = ()
    # issue #8 п.4: hard-cutoff порог релевантности перед сохранением —
    # переиспользует механизм issue #6 (PruningContentFilter -> fit_markdown).
    min_fit_markdown_chars: int = 200


DOWNSIDEUP = SourceConfig(
    name="downsideup",
    domain="downsideup.org",
    seed_urls=[
        "https://downsideup.org/",
        "https://downsideup.org/roditelyam/",
        "https://downsideup.org/biblioteka/",
    ],
    keywords=[
        "синдром дауна", "раннее развитие", "родителям",
        "трисомия", "особый ребёнок", "реабилитация",
        "коррекция", "логопед", "дефектолог",
    ],
    max_pages=100,
    direction="methodology",
    exclude_slugs=(
        "novosti", "kalendar-sobytiy", "forum", "registratsiya",
        "otzyvy", "politika-konfidentialnosti", "search",
        "dnevnik-razvitiya",
    ),
    min_fit_markdown_chars=200,
)

SOURCES = {"downsideup": DOWNSIDEUP}
