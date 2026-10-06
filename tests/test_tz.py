from datetime import datetime, timezone

import pandas as pd

from src.tz import fmt_msk, msk_naive, msk_series, msk_to_utc_naive, now_msk


def test_naive_is_utc():
    assert fmt_msk("2026-10-06 04:22:33") == "06.10.2026 07:22"
    assert fmt_msk(datetime(2026, 10, 6, 21, 30)) == "07.10.2026 00:30"


def test_aware_and_iso():
    assert fmt_msk("2026-09-01T10:00:00+00:00") == "01.09.2026 13:00"
    assert fmt_msk("2026-09-01T10:00:00Z") == "01.09.2026 13:00"
    assert fmt_msk("2026-09-01T10:00:00+03:00") == "01.09.2026 10:00"
    assert fmt_msk(datetime(2026, 9, 1, 10, tzinfo=timezone.utc)) == "01.09.2026 13:00"


def test_date_only_not_shifted():
    assert fmt_msk("2026-09-01") == "01.09.2026 00:00"


def test_empty():
    assert fmt_msk(None) == "—" and fmt_msk("") == "—" and fmt_msk("мусор") == "—"
    assert fmt_msk(None, "") == ""


def test_roundtrip_input():
    assert msk_to_utc_naive(datetime(2026, 10, 6, 0, 30)) == datetime(2026, 10, 5, 21, 30)
    assert msk_naive(msk_to_utc_naive(datetime(2026, 10, 6, 10, 0))) == datetime(2026, 10, 6, 10, 0)


def test_series_with_nat():
    s = msk_series(pd.Series(["2026-09-29 10:00:00+00:00", None, ""]))
    assert s.iloc[0] == pd.Timestamp("2026-09-29 13:00")
    assert s.isna().tolist() == [False, True, True]


def test_now_msk_naive():
    assert now_msk().tzinfo is None
