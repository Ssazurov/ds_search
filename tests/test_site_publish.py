"""Пересборка внешнего сайта из админки (ds_search#225)."""
from __future__ import annotations

import json
import os

import pytest

from src.site_publish import runner

LOG = (
    "articles: 3 выгружено, отброшено {\"not_set\": 5, \"denied\": 1}\n"
    "news: 0 выгружено, отброшено {}\n"
    "проверка секретов: 12 файлов чисто\n"
    "опубликовано: https://ssazurov.github.io/ds_site/\n"
)


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "STATE_DIR", tmp_path)
    return tmp_path


def test_parse_counts_and_url():
    rows = runner.parse_counts(LOG)
    assert rows == [
        {"name": "articles", "published": 3, "skipped": {"not_set": 5, "denied": 1}},
        {"name": "news", "published": 0, "skipped": {}},
    ]
    assert runner.parse_url(LOG) == "https://ssazurov.github.io/ds_site/"
    assert runner.parse_url("ничего") is None


def test_status_never_started(state_dir):
    assert runner.status().started_at is None


def test_status_finished_ok(state_dir):
    (state_dir / "state.json").write_text(json.dumps({"pid": 1, "started_at": 1.0, "dry_run": False}))
    (state_dir / "last.log").write_text(LOG, encoding="utf-8")
    (state_dir / "exit_code").write_text("0\n")
    st = runner.status()
    assert not st.running and st.exit_code == 0 and st.url and len(st.counts) == 2


def test_status_running_and_interrupted(state_dir):
    (state_dir / "state.json").write_text(json.dumps({"pid": os.getpid(), "started_at": 1.0}))
    assert runner.status().running
    (state_dir / "state.json").write_text(json.dumps({"pid": 0, "started_at": 1.0}))
    st = runner.status()
    assert not st.running and st.exit_code == -1


def test_check_env_missing_site(monkeypatch, tmp_path):
    monkeypatch.setenv("DS_SITE_DIR", str(tmp_path / "нет"))
    assert "ds_site" in runner.check_env()


def test_start_refuses_when_running(state_dir):
    (state_dir / "state.json").write_text(json.dumps({"pid": os.getpid(), "started_at": 1.0}))
    with pytest.raises(RuntimeError, match="уже выполняется"):
        runner.start()
