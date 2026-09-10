"""Тесты src/metadata/gar_mapping.py (issue #90)."""
from src.metadata import gar_mapping

MAPPING = {
    "example.org": {"direction": "razvitie-i-navyki"},
    "example.org/family_support": {
        "direction": "podderzhka-semi",
        "category": "issledovaniya-i-opyt-semey",
    },
}

FAKE_FIELDS = {
    "fields": [
        {"key": "direction", "active": True, "options": [
            {"id": "d1", "value": "podderzhka-semi", "active": True},
            {"id": "d2", "value": "razvitie-i-navyki", "active": True},
        ]},
        {"key": "category", "active": True, "options": [
            {"id": "c1", "value": "issledovaniya-i-opyt-semey", "active": True, "parent_option_id": "d1"},
        ]},
    ]
}


def test_resolve_defaults_domain_only():
    assert gar_mapping.resolve_defaults("example.org", mapping=MAPPING) == {
        "direction": "razvitie-i-navyki"
    }


def test_resolve_defaults_specific_overrides_domain():
    result = gar_mapping.resolve_defaults("example.org", "family_support", mapping=MAPPING)
    assert result["direction"] == "podderzhka-semi"
    assert result["category"] == "issledovaniya-i-opyt-semey"


def test_resolve_defaults_unknown_domain_returns_empty():
    assert gar_mapping.resolve_defaults("unknown.org", mapping=MAPPING) == {}


def test_resolve_defaults_unknown_dest_dir_falls_back_to_domain_level():
    result = gar_mapping.resolve_defaults("example.org", "no-such-dir", mapping=MAPPING)
    assert result == {"direction": "razvitie-i-navyki"}


def test_validate_mapping_ok():
    assert gar_mapping.validate_mapping(MAPPING, FAKE_FIELDS) == []


def test_validate_mapping_flags_invalid_value():
    bad = {"example.org": {"direction": "no-such-direction"}}
    errors = gar_mapping.validate_mapping(bad, FAKE_FIELDS)
    assert len(errors) == 1
    assert "no-such-direction" in errors[0]


def test_validate_mapping_flags_invalid_category_for_direction():
    bad = {"x": {"direction": "podderzhka-semi", "category": "not-a-real-category"}}
    errors = gar_mapping.validate_mapping(bad, FAKE_FIELDS)
    assert len(errors) == 1
    assert "category" in errors[0]


def test_real_gar_mapping_yaml_parses():
    mapping = gar_mapping.load_mapping()
    assert "downsideup.org" in mapping
    assert "downsideup.org/family_support" in mapping
