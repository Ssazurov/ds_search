from ui.sources_tab import site_url


def test_site_url():
    assert site_url("downsyndrome.ru") == "https://downsyndrome.ru"
    assert site_url(" vk.com/club1/ ") == "https://vk.com/club1"
    assert site_url("https://a.ru") == "https://a.ru"
