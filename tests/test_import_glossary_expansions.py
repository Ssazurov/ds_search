import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from scripts.import_glossary_expansions import _term_forms


def test_short_form_from_parentheses():
    assert _term_forms("АДК (AAC)") == ("АДК", ["AAC"])


def test_short_form_plain_acronym():
    assert _term_forms("ЗПРР") == ("ЗПРР", [])


def test_full_term_is_ignored():
    assert _term_forms("Синдром Дауна") is None


def test_parenthetical_abbreviation_is_short_form():
    assert _term_forms("Биопсия хориона (БВХ)") == ("БВХ", [])
