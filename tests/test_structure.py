from src.crawler.structure import detect_structure_profile, normalize_headings_for_url


def test_sindromlubvi_profile_detected_for_subdomain():
    assert detect_structure_profile("https://sindromlubvi.ru/news/a/").name == "sindromlubvi"
    assert detect_structure_profile("https://www.sindromlubvi.ru/news/a/").name == "sindromlubvi"


def test_existing_semantic_headings_are_preserved():
    html = "<h1>Заголовок</h1><p>Текст</p>"
    assert normalize_headings_for_url(html, "https://sindromlubvi.ru/a") == html


def test_visual_article_subheading_becomes_h2():
    html = '<div class="sln-news-wrap"><p><b>Почему мы вводим платные услуги?</b><br>Текст</p></div>'
    result = normalize_headings_for_url(html, "https://sindromlubvi.ru/news/a")
    assert "<h2>Почему мы вводим платные услуги?</h2>" in result


def test_unknown_source_is_unchanged():
    html = '<div class="sln-news-wrap"><p><b>Почему это важно?</b></p></div>'
    assert normalize_headings_for_url(html, "https://example.org/a") == html


def test_headings_shift_up_when_h2_skipped():
    html = "<h1>T</h1><h3>A</h3><p>x</p><h4>B</h4>"
    assert normalize_headings_for_url(html, "https://downsideup.org/a") == "<h1>T</h1><h2>A</h2><p>x</p><h3>B</h3>"


def test_headings_not_shifted_when_h2_present():
    html = "<h2>A</h2><h3>B</h3>"
    assert normalize_headings_for_url(html, "https://example.org/a") == html
