from src.discovery.classify import classify, load_keywords, _score_labels, _best_label


def test_load_keywords_missing_file(tmp_path):
    kw = load_keywords(tmp_path / "nope.yaml")
    assert kw == {"category": {}, "doc_type": {}, "target_audience": {}}


def test_score_labels_counts_occurrences():
    scores = _score_labels("речь речь логопед", {"speech": ["речь"], "motor": ["моторика"]})
    assert scores == {"speech": 2}


def test_best_label_empty():
    assert _best_label({}) is None


def test_best_label_picks_max():
    assert _best_label({"a": 1, "b": 3}) == "b"


def test_classify_empty_text_returns_all_none():
    result = classify(None, None)
    assert result == {
        "suggested_direction": None,
        "suggested_category": None,
        "suggested_doc_type": None,
        "suggested_target_audience": None,
    }


def test_classify_matches_category_direction_doc_type_audience():
    result = classify(
        "Логопедическое пособие для родителей",
        "Развитие речи у детей с синдромом Дауна: методичка для родителей",
    )
    assert result["suggested_category"] == "speech_development"
    assert result["suggested_direction"] == "methodology"
    assert result["suggested_doc_type"] == "guide"
    assert result["suggested_target_audience"] == "parents"


def test_classify_no_match_is_none_not_guessed():
    result = classify("Заголовок без ключевиков", "просто текст")
    assert result["suggested_category"] is None
    assert result["suggested_direction"] is None
