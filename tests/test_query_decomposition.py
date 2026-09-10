import pytest

from src.rag.query_decomposition import (
    DecomposedQuery,
    _count_topic_markers,
    _is_complex,
    _split_question,
    decompose_query,
)


class TestCountTopicMarkers:
    def test_single_conjunction_counts_as_one(self):
        assert _count_topic_markers("диагностика и лечение") == 1

    def test_two_conjunctions_count_as_two(self):
        assert _count_topic_markers("диагностика и лечение и реабилитация") == 2

    def test_semicolon_counts_as_one(self):
        assert _count_topic_markers("диагностика; лечение") == 1

    def test_two_commas_count_as_two(self):
        assert _count_topic_markers("диагностика, лечение, реабилитация") == 2

    def test_one_comma_counts_as_one(self):
        assert _count_topic_markers("диагностика, лечение") == 1

    def test_mixed_markers_sum(self):
        text = "диагностика, лечение и реабилитация"
        assert _count_topic_markers(text) == 2  # 1 comma + 1 "и"

    def test_case_insensitive(self):
        assert _count_topic_markers("Диагностика И Лечение") == 1

    def test_empty_returns_zero(self):
        assert _count_topic_markers("") == 0


class TestIsComplex:
    def test_simple_question_is_not_complex(self):
        assert not _is_complex("Что такое синдром Дауна?")

    def test_single_conjunction_is_not_complex(self):
        assert not _is_complex("Какие методы диагностики и лечения существуют?")

    def test_two_conjunctions_is_complex(self):
        assert _is_complex("Какие методы диагностики и лечения и реабилитации существуют?")

    def test_semicolon_makes_complex(self):
        assert _is_complex("Диагностика; лечение; реабилитация")

    def test_two_commas_make_complex(self):
        assert _is_complex("Диагностика, лечение, реабилитация")

    def test_empty_is_not_complex(self):
        assert not _is_complex("")

    def test_whitespace_only_is_not_complex(self):
        assert not _is_complex("   ")


class TestSplitQuestion:
    def test_splits_on_semicolon(self):
        parts = _split_question("диагностика; лечение; реабилитация")
        assert parts == ["диагностика", "лечение", "реабилитация"]

    def test_splits_on_conjunction(self):
        parts = _split_question("диагностика и лечение и реабилитация")
        assert parts == ["диагностика", "лечение", "реабилитация"]

    def test_splits_on_comma_when_three_parts(self):
        parts = _split_question("диагностика, лечение, реабилитация")
        assert parts == ["диагностика", "лечение", "реабилитация"]

    def test_does_not_split_on_single_comma(self):
        parts = _split_question("диагностика, лечение")
        assert parts == ["диагностика, лечение"]

    def test_preserves_order(self):
        parts = _split_question("первая; вторая; третья")
        assert parts == ["первая", "вторая", "третья"]

    def test_strips_whitespace(self):
        parts = _split_question("  диагностика  ;  лечение  ")
        assert parts == ["диагностика", "лечение"]

    def test_case_insensitive_conjunction(self):
        parts = _split_question("диагностика И лечение")
        assert parts == ["диагностика", "лечение"]

    def test_single_part_returns_original(self):
        parts = _split_question("простой вопрос")
        assert parts == ["простой вопрос"]


class TestDecomposeQuery:
    def test_simple_question_not_decomposed(self):
        result = decompose_query("Что такое синдром Дауна?")
        assert result.decomposed is False
        assert result.sub_queries == ("Что такое синдром Дауна?",)
        assert result.original == "Что такое синдром Дауна?"

    def test_complex_question_decomposed(self):
        result = decompose_query("Диагностика, лечение и реабилитация синдрома Дауна")
        assert result.decomposed is True
        assert len(result.sub_queries) >= 2
        assert result.original == "Диагностика, лечение и реабилитация синдрома Дауна"

    def test_empty_input(self):
        result = decompose_query("")
        assert result.decomposed is False
        assert result.sub_queries == ("",)

    def test_none_input(self):
        result = decompose_query(None)
        assert result.decomposed is False
        assert result.sub_queries == ("",)

    def test_whitespace_only(self):
        result = decompose_query("   ")
        assert result.decomposed is False
        assert result.sub_queries == ("   ",)

    def test_deduplicates_sub_queries(self):
        result = decompose_query("диагностика и диагностика и лечение")
        assert result.decomposed is True
        assert len(result.sub_queries) == 2
        assert "диагностика" in result.sub_queries
        assert "лечение" in result.sub_queries

    def test_clamps_to_max_sub_queries(self):
        question = "а, б, в, г, д, е, ж"
        result = decompose_query(question, max_sub_queries=3)
        assert len(result.sub_queries) == 3

    def test_single_conjunction_not_decomposed(self):
        result = decompose_query("диагностика и лечение")
        assert result.decomposed is False
        assert result.sub_queries == ("диагностика и лечение",)

    def test_preserves_original_when_single_result(self):
        # Even if heuristic says complex but split yields 1 part
        result = decompose_query("диагностика и лечение и реабилитация")
        # This should decompose into 3 parts
        assert result.decomposed is True

    def test_sub_queries_are_non_empty(self):
        result = decompose_query("диагностика, лечение, реабилитация")
        for q in result.sub_queries:
            assert q.strip()

    def test_dataclass_is_frozen(self):
        result = decompose_query("тест")
        with pytest.raises(AttributeError):
            result.original = "new"  # type: ignore[misc]
