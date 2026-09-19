import sqlite3
import pytest

from src.news import db
from src.news.manual import create_manual_draft


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "n.db"
    db.init_db(p)
    return p


def test_manual_without_url(dbp):
    i = create_manual_draft("Заг", "Текст " * 100, db_path=dbp)
    it = db.get_news_item(i, db_path=dbp)
    assert it["status"] == "draft" and it["source_name"] == "Редакция"
    assert it["source_url"].startswith("manual:") and len(it["summary"]) == 300


def test_manual_with_url_tags_and_duplicate(dbp):
    i = create_manual_draft("Заг", "Т", source_url="https://x.ru/1", source_name="X",
                            tags=["a", " b", ""], db_path=dbp)
    it = db.get_news_item(i, db_path=dbp)
    assert it["source_name"] == "X" and it["tags"] == ["a", "b"]
    with pytest.raises(ValueError):
        create_manual_draft("Заг2", "Т", source_url="https://x.ru/1", db_path=dbp)


def test_manual_validation(dbp):
    with pytest.raises(ValueError):
        create_manual_draft(" ", "Т", db_path=dbp)
    with pytest.raises(ValueError):
        create_manual_draft("З", "", db_path=dbp)
