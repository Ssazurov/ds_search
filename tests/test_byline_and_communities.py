"""issue #474: строка «Автор | Город», фильтр и группировка сообществ под доменом."""
from collections import Counter

from src.license.checker import LicenseCheckResult, LicenseStatus
from ui.sources_tab import build_rows, filter_rows


def _res(**kw) -> LicenseCheckResult:
    return LicenseCheckResult(status=LicenseStatus.ALLOW, reason="", **kw)


def test_byline_both_fields():
    assert _res(author="Иван Петров", city="Москва").byline() == "Иван Петров | Москва"


def test_byline_skips_empty_fields():
    assert _res(author="Иван Петров").byline() == "Иван Петров"
    assert _res(city="Москва").byline() == "Москва"
    assert _res().byline() == ""


def test_communities_grouped_under_their_domain():
    registry = {
        "vk.ru": {"status": "allow"},
        "asi.org.ru": {"status": "allow"},
        "vk.ru/sundetiekb": {"status": "allow", "source_type": "community"},
        "vk.ru/other": {"status": "allow", "source_type": "community"},
    }
    keys = [r["domain"] for r in build_rows(registry, Counter())]
    vk = keys.index("vk.ru")
    assert set(keys[vk + 1: vk + 3]) == {"vk.ru/sundetiekb", "vk.ru/other"}


def test_community_filter_returns_only_communities():
    registry = {
        "vk.ru": {"status": "allow"},
        "vk.ru/sundetiekb": {"status": "allow", "source_type": "community"},
    }
    rows = build_rows(registry, Counter())
    assert [r["domain"] for r in filter_rows(rows, "community", "")] == ["vk.ru/sundetiekb"]
