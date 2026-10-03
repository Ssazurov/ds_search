"""VK API client (issue #462, epic #465).

Доступ — user-token (OAuth), не сервисный: wall.search/newsfeed.search
недоступны сервисному ключу сообщества. Токен — VK_USER_TOKEN,
получение описано в docs/vk_token.md.
"""
from __future__ import annotations

import os

import httpx

VK_API_URL = "https://api.vk.com/method"
VK_API_VERSION = "5.199"


class VkAuthError(Exception):
    """Токен не задан или VK API вернул ошибку авторизации."""


class VkClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("VK_USER_TOKEN")

    def _call(self, method: str, **params) -> dict:
        if not self.token:
            raise VkAuthError("VK_USER_TOKEN не задан")
        params = {
            **params,
            "access_token": self.token,
            "v": VK_API_VERSION,
        }
        resp = httpx.get(f"{VK_API_URL}/{method}", params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise VkAuthError(f"VK API {method}: {err.get('error_msg')} (code {err.get('error_code')})")
        return data["response"]

    def wall_search(self, query: str, count: int = 20, owner_id: int | None = None,
                    domain: str | None = None) -> dict:
        """Поиск по стене конкретного сообщества/пользователя (issue #464).
        Задать owner_id (отрицательный для сообщества) или domain (screen_name)."""
        if (owner_id is None) == (domain is None):
            raise ValueError("wall_search: нужен ровно один из owner_id / domain")
        params = {"query": query, "count": count}
        if owner_id is not None:
            params["owner_id"] = owner_id
        else:
            params["domain"] = domain
        return self._call("wall.search", **params)

    def newsfeed_search(self, query: str, count: int = 20) -> dict:
        """Поиск по теме во всей VK (issue #463), требует user-token."""
        return self._call("newsfeed.search", q=query, count=count)
