from src.license.checker import LicenseCheckResult, LicenseStatus, default_attribution_template
from src.metadata.meta_extract import strip_site_suffix

SITE = "Православный журнал «Фома»"


def test_suffix_stripped():
    assert strip_site_suffix(f"Что делать? - {SITE}", SITE) == "Что делать?"


def test_other_separators_and_case():
    assert strip_site_suffix(f"Заголовок | {SITE.upper()}", SITE) == "Заголовок"


def test_no_site_name_keeps_title():
    assert strip_site_suffix(f"Заголовок - {SITE}", "") == f"Заголовок - {SITE}"


def test_title_equal_to_site_name_kept():
    assert strip_site_suffix(f"x - {SITE}", SITE) == "x"
    assert strip_site_suffix(SITE, SITE) == SITE


def test_default_template_keeps_title_placeholder():
    r = LicenseCheckResult(
        status=LicenseStatus.ATTRIBUTION_REQUIRED, reason="t",
        attribution_template=default_attribution_template("foma.ru"),
    )
    assert r.build_attribution(title="T", source_url="https://foma.ru/a") == "Источник: T (https://foma.ru/a), foma.ru"


def test_derive_site_name_from_template():
    from src.license.checker import derive_site_name
    assert derive_site_name("Источник: Православный журнал «Фома» ({source_url})") == SITE
    assert derive_site_name(default_attribution_template("foma.ru")) == ""
    assert derive_site_name(None) == ""


def test_registry_without_site_name_strips_suffix(monkeypatch):
    import src.license.checker as c

    class S:
        def get(self, d):
            return {"status": "attribution_required",
                    "attribution_template": f"Источник: {SITE} ({{source_url}})"}

        def ensure(self, *a):
            return None

    monkeypatch.setattr(c, "_check_robots", lambda *a, **k: True)
    r = c.check_license("foma.ru", "https://foma.ru/", registry_store=S())
    assert strip_site_suffix(f"Во! - {SITE}", r.site_name) == "Во!"
