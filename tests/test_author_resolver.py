"""issue #569: resolve_author."""
from src.metadata.author_resolver import author_from_html, resolve_author
from src.metadata.meta_extract import extract_author_from_markdown

SA = {"downsideup.org": "Благотворительный фонд «Даунсайд Ап»"}
HTML = ('<ul><li class="gallery-desc__item"> Автор: <a class="link" href="/a/">'
        ' Благотворительный фонд «Даунсайд Ап»</a> </li></ul>')


def test_body_author_underscore_with_role():
    md = "текст\n\n_Автор:__Виталий Свардовский - редактор сайта «Мир каратэ», председатель клуба_"
    assert extract_author_from_markdown(md) == "Виталий Свардовский"


def test_html_author_link():
    assert author_from_html(HTML) == "Благотворительный фонд «Даунсайд Ап»"


def test_html_ignores_authorization_and_prose():
    assert author_from_html("<a>Авторизация</a><p>Авторы использовали методы</p>") == ""


def test_jsonld_author():
    assert author_from_html('{"author": {"@type": "Person", "name": "Анна Петрова"}}') == "Анна Петрова"


def test_current_wins():
    assert resolve_author("Иван", html=HTML, llm=None, site_authors=SA) == "Иван"


def test_url_author_replaced_by_html():
    assert resolve_author("https://fb.com/x", html=HTML, llm=None, site_authors=SA).startswith("Благотворительный")


def test_llm_used_only_when_empty():
    calls = []
    def llm(md):
        calls.append(1)
        return "Мария Иванова"
    assert resolve_author("", html=HTML, llm=llm, site_authors=SA).startswith("Благотворительный")
    assert not calls
    assert resolve_author("", html="", markdown="x", llm=llm, site_authors=SA) == "Мария Иванова"


def test_fallback_config_then_site_name_then_og():
    assert resolve_author("", domain="downsideup.org", llm=None, site_authors=SA) == SA["downsideup.org"]
    assert resolve_author("", domain="x.ru", site_name="Журнал Икс", llm=None, site_authors=SA) == "Журнал Икс"
    og = '<meta property="og:site_name" content="Сайт Игрек"/>'
    assert resolve_author("", html=og, domain="y.ru", llm=None, site_authors=SA) == "Сайт Игрек"


def test_author_literal_unicode_escape_issue_571():
    from src.metadata.meta_extract import extract_page_meta

    meta = {"author": "\\u0420\\u0435\\u0434\\u0430\\u043a\\u0446\\u0438\\u044f"}
    assert extract_page_meta(meta, "")["author"] == "Редакция"
