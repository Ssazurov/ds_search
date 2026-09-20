from collections import Counter

from ui.sources_tab import build_rows, filter_rows

REG = {
    "a.org": {"status": "allow"},
    "b.org": {"status": "pending_manual_review"},
    "agg.ru": {"status": "deny", "is_aggregator": True},
}
COUNTS = Counter({"b.org": 2, "c.org": 1, "a.org": 5})


def test_build_rows_pending_with_findings_first():
    rows = build_rows(REG, COUNTS)
    assert [r["domain"] for r in rows][:2] == ["b.org", "c.org"]
    assert next(r for r in rows if r["domain"] == "c.org")["pending"] is True


def test_filter_rows():
    rows = build_rows(REG, COUNTS)
    assert {r["domain"] for r in filter_rows(rows, "pending", "")} == {"b.org", "c.org"}
    assert [r["domain"] for r in filter_rows(rows, "agg", "")] == ["agg.ru"]
    assert [r["domain"] for r in filter_rows(rows, "all", "A.o")] == ["a.org"]
    assert {r["domain"] for r in filter_rows(rows, "found", "")} == {"a.org", "b.org", "c.org"}
