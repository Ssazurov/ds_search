"""Маппинг полей glossary.json/links.json в общую схему фильтров ds_site
(direction/category/doc_type/age/target_audience) — issue #127, эпик #126,
ADR-0004.

Источники (`scripts/export_glossary_links.py`) отдают произвольные текстовые
поля (category на русском, age как "Все"/"Дети"/"18+", region, relevance),
несовместимые с активными опциями GAR (см. `gar_schema.py`). Здесь —
статические таблицы соответствия, подобранные вручную по смыслу (не через
LLM: справочник маленький и стабильный, 6 категорий глоссария + 25 у ссылок).

Известные ограничения (сознательно, не баг):
- `age` в links.json — это условная "целевая аудитория по возрасту", а не
  жизненный этап человека (схема GAR ожидает "Беременность".."18+ лет").
  Однозначно мапится только "18+" -> "18+ лет"; "Все"/"Дети"/"Взрослые"
  слишком широкие — оставляем None (needs_review), не угадываем.
- `region` и `relevance` (Активен/Архивный/Проверить) не входят в целевую
  схему фильтров сайта (direction/category/doc_type/age/target_audience) —
  сознательно не переносятся. `relevance` может использоваться отдельно
  в #128 (например, чтобы не индексировать "Архивный"), это не задача #127.
- `target_audience` в исходном профиле glossary/links был некорректной
  comma-строкой ("parents,specialists") — поле в GAR single-select, поэтому
  здесь везде одно значение "parents" (основная аудитория сайта).
- `doc_type` значения "glossary_term"/"link" по требованию issue #127, но их
  ещё нет среди активных опций поля doc_type в GAR (см.
  config/gar_schema_cache.json) — блокер для #128, заводить/активировать
  опции нужно на стороне GAR раньше индексации.
"""
from __future__ import annotations

DOC_TYPE_GLOSSARY = "glossary_term"
DOC_TYPE_LINK = "link"

DEFAULT_TARGET_AUDIENCE = "parents"

GLOSSARY_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "Медицина и генетика СД": ("zdorove", "medicinskoe-nablyudenie"),
    "Диагностика и скрининг": (
        "zdorove", "prenatalnaya-diagnostika-i-pervye-nedeli-posle-diagnoza",
    ),
    "Медицина, когнитивное развитие и реабилитация": (
        "razvitie-i-navyki", "kognitivnoe-razvitie",
    ),
    "Психолого-педагогическое сопровождение": (
        "razvitie-i-navyki", "metodiki-obucheniya-i-korrekcii-povedeniya",
    ),
    "Ассистивные технологии и ПО": ("razvitie-i-navyki", "assistivnye-tehnologii"),
    "Организации и методики": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
}

# Соц.сети/каналы -> "Досуг и сообщества" (otnosheniya-i-socialnaya-zhizn).
_SOCIAL = ("LiveJournal", "Rutube", "Telegram", "VK", "YouTube", "Одноклассники", "Дзен")

LINK_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    **{s: ("otnosheniya-i-socialnaya-zhizn", "dosug-i-soobschestva") for s in _SOCIAL},
    "Фонд": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "НКО": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "НКО / статья": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "НКО / творчество": ("otnosheniya-i-socialnaya-zhizn", "dosug-i-soobschestva"),
    "Ассоциация": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "Библиотека": ("razvitie-i-navyki", "metodiki-obucheniya-i-korrekcii-povedeniya"),
    "Госресурс": ("vzroslaya-zhizn-i-prava", "prava-lgoty-vyplaty"),
    "Донат-платформа": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "Журнал": ("podderzhka-semi", "issledovaniya-i-opyt-semey"),
    "Каталог": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "Медиа": ("podderzhka-semi", "issledovaniya-i-opyt-semey"),
    "Мероприятие": ("otnosheniya-i-socialnaya-zhizn", "dosug-i-soobschestva"),
    "Портал": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "Портал / СМИ": ("podderzhka-semi", "issledovaniya-i-opyt-semey"),
    "Ресурс": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "СМИ / статья": ("podderzhka-semi", "issledovaniya-i-opyt-semey"),
    "Сайт": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
    "Сервис": ("razvitie-i-navyki", "assistivnye-tehnologii"),
    "Форум": ("podderzhka-semi", "soobschestva-i-vzaimopomosch"),
}

# links.json age -> активная опция GAR-поля age. Только однозначные случаи.
LINK_AGE_MAP: dict[str, str] = {
    "18+": "18+ лет",
}


def map_glossary_item(item: dict) -> dict:
    """glossary.json entry -> {direction, category, doc_type, target_audience,
    age}. category/direction = None, если исходная категория не из таблицы
    (needs_review при последующей интеграции с #93-подобным пайплайном)."""
    direction, category = GLOSSARY_CATEGORY_MAP.get(item.get("category", ""), (None, None))
    return {
        "direction": direction,
        "category": category,
        "doc_type": DOC_TYPE_GLOSSARY,
        "target_audience": DEFAULT_TARGET_AUDIENCE,
        "age": None,
    }


def map_link_item(item: dict) -> dict:
    """links.json entry -> {direction, category, doc_type, target_audience,
    age}. region/relevance сознательно не переносятся (см. модуль docstring)."""
    direction, category = LINK_CATEGORY_MAP.get(item.get("category", ""), (None, None))
    age = LINK_AGE_MAP.get(item.get("age", ""))
    return {
        "direction": direction,
        "category": category,
        "doc_type": DOC_TYPE_LINK,
        "target_audience": DEFAULT_TARGET_AUDIENCE,
        "age": age,
    }
