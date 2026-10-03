"""Тесты vk_search (issue #463: topic-поиск по всей VK через newsfeed.search)."""
from datetime import datetime

from src.search.vk_search import vk_search


class FakeVkClient:
    def __init__(self, token="t", items=None, raise_exc=None):
        self.token = token
        self._items = items if items is not None else []
        self._raise = raise_exc
        self.calls = []

    def newsfeed_search(self, query, count=10):
        self.calls.append((query, count))
        if self._raise:
            raise self._raise
        return {"items": self._items}


def test_no_token_returns_none():
    assert vk_search("даун синдром", client=FakeVkClient(token=None)) is None


def test_maps_posts_to_hits_with_date_and_url():
    items = [{"owner_id": -216520775, "id": 1589, "text": "Привет мир", "date": 1700000000}]
    hits = vk_search("даун синдром", client=FakeVkClient(items=items))
    assert len(hits) == 1
    h = hits[0]
    assert h.url == "https://vk.ru/wall-216520775_1589"
    assert h.title == "Привет мир"
    assert isinstance(h.published_at, datetime)


def test_post_without_text_is_skipped():
    items = [{"owner_id": 1, "id": 2, "text": "", "date": 1}]
    assert vk_search("q", client=FakeVkClient(items=items)) == []


def test_api_error_returns_none():
    from src.search.vk_client import VkAuthError
    assert vk_search("q", client=FakeVkClient(raise_exc=VkAuthError("boom"))) is None


# --- issue #464: поиск по одному сообществу (wall.search) ---

import pytest

from src.search.vk_search import parse_vk_community, vk_community_search


class FakeWallClient(FakeVkClient):
    def wall_search(self, query, count=20, owner_id=None, domain=None):
        self.calls.append((query, count, owner_id, domain))
        if self._raise:
            raise self._raise
        return {"items": self._items}


@pytest.mark.parametrize("raw, expected", [
    ("https://vk.com/club216520775", {"owner_id": -216520775}),
    ("vk.ru/public123", {"owner_id": -123}),
    ("-216520775", {"owner_id": -216520775}),
    ("216520775", {"owner_id": -216520775}),
    ("id42", {"owner_id": 42}),
    ("https://vk.com/downsyndrome_ru?w=wall", {"domain": "downsyndrome_ru"}),
    ("  ", None),
    ("!!", None),
])
def test_parse_vk_community(raw, expected):
    assert parse_vk_community(raw) == expected


def test_community_search_returns_only_its_posts():
    items = [{"owner_id": -216520775, "id": 7, "text": "Пост сообщества", "date": 1700000000}]
    client = FakeWallClient(items=items)
    hits = vk_community_search("даун синдром", "https://vk.com/club216520775", client=client)
    assert [h.url for h in hits] == ["https://vk.ru/wall-216520775_7"]
    assert client.calls[0][2] == -216520775


def test_community_search_by_screen_name_uses_domain_param():
    client = FakeWallClient(items=[])
    assert vk_community_search("q", "downsyndrome_ru", client=client) == []
    assert client.calls[0][3] == "downsyndrome_ru"


def test_community_search_no_token_returns_none():
    assert vk_community_search("q", "club1", client=FakeWallClient(token=None)) is None


def test_community_search_api_error_returns_none():
    from src.search.vk_client import VkAuthError
    assert vk_community_search("q", "club1", client=FakeWallClient(raise_exc=VkAuthError("x"))) is None

