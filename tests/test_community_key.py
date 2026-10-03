from src.license.checker import community_key_for_url, normalize_domain


def test_normalize_keeps_community_key():
    assert normalize_domain("VK.ru:club216520775") == "vk.ru:club216520775"
    assert normalize_domain("example.org:8080") == "example.org"
    assert normalize_domain("https://www.example.org/x") == "example.org"


def test_community_key_for_url():
    assert community_key_for_url("https://vk.ru/wall-216520775_1589") == "vk.ru:club216520775"
    assert community_key_for_url("https://vk.com/club216520775") == "vk.ru:club216520775"
    assert community_key_for_url("https://example.org/club1") is None
