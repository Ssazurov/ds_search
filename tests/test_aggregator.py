"""issue #194, ADR-0012: извлечение ссылки на первоисточник из текста
статьи агрегатора (wildcar.ru и т.п.)."""
from src.news.aggregator import extract_primary_source_url, primary_source_domain


def test_extracts_ru_source_line():
    text = (
        "какой-то текст статьи...\n\n"
        "Источник: [sonoticiaboa.com.br]"
        "(https://www.sonoticiaboa.com.br/2026/09/12/dj-down-rock-in-rio)\n\n"
        "Подпишитесь:"
    )
    assert extract_primary_source_url(text) == (
        "https://www.sonoticiaboa.com.br/2026/09/12/dj-down-rock-in-rio"
    )


def test_returns_none_when_no_source_line():
    assert extract_primary_source_url("просто текст без источника") is None


def test_primary_source_domain():
    assert primary_source_domain("https://www.sonoticiaboa.com.br/x") == "www.sonoticiaboa.com.br"
