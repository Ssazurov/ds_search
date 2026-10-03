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
