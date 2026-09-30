from src.crawler.slug import norm_domain


def test_norm_domain():
    assert norm_domain("WWW.Pravmir.ru:8080") == "pravmir.ru"
    assert norm_domain("miloserdie.ru") == "miloserdie.ru"
