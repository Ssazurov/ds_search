# VK user-token

Нужен для `VkClient` (`src/search/vk_client.py`) — `wall.search` и
`newsfeed.search` недоступны сервисному ключу сообщества, только
user-token.

## Получение

1. Создать Standalone-приложение: https://vk.com/editapp?act=create
2. ID приложения → ссылка implicit flow:
   `https://oauth.vk.com/authorize?client_id=<APP_ID>&display=page&scope=wall,offline&response_type=token&v=5.199`
3. Открыть в браузере под живым аккаунтом, разрешить доступ.
4. VK редиректит на `https://oauth.vk.com/blank.html#access_token=...&expires_in=0&user_id=...`
   — `access_token` из фрагмента URL и есть токен (`expires_in=0` при `scope=offline` — бессрочный).

## Хранение

`.env` → `VK_USER_TOKEN=<token>` (аналогично `BRAVE_API_KEY`/`TAVILY_API_KEY`).

## Ограничения

- Токен привязан к живому аккаунту — не сервисный, деавторизация/смена
  пароля аккаунта token инвалидирует.
- Rate-limit VK API: 3 запроса/сек на пользователя.
