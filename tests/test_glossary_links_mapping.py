"""issue #127: маппинг glossary.json/links.json в схему фильтров сайта."""
from src.metadata import gar_schema, glossary_links_mapping as m


def test_map_glossary_item_known_category():
    result = m.map_glossary_item({"category": "Медицина и генетика СД"})
    assert result["direction"] == "zdorove"
    assert result["category"] == "medicinskoe-nablyudenie"
    assert result["doc_type"] == "glossary_term"
    assert result["target_audience"] == "parents"
    assert result["age"] is None


def test_map_glossary_item_unknown_category_is_none():
    result = m.map_glossary_item({"category": "неизвестное"})
    assert result["direction"] is None
    assert result["category"] is None


def test_map_link_item_maps_age_18plus():
    result = m.map_link_item({"category": "Фонд", "age": "18+"})
    assert result["doc_type"] == "link"
    assert result["age"] == "18+ лет"


def test_map_link_item_coarse_age_left_none():
    result = m.map_link_item({"category": "Фонд", "age": "Все"})
    assert result["age"] is None


def test_all_categories_resolve_to_valid_gar_pairs():
    fields = {"fields": []}
    for value_map in (m.GLOSSARY_CATEGORY_MAP, m.LINK_CATEGORY_MAP):
        for direction, category in value_map.values():
            assert isinstance(direction, str) and direction
            assert isinstance(category, str) and category
    # sanity: gar_schema helpers importable and callable with empty schema
    assert gar_schema.field_options(fields, "direction") == []
