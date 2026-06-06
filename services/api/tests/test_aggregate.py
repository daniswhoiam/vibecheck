import datetime as dt

import pytest
from api.aggregate import fold_buckets, truncate_to

UTC = dt.UTC


def test_truncate_to_day_is_identity() -> None:
    d = dt.datetime(2026, 5, 20, tzinfo=UTC)
    assert truncate_to(d, "day") == d


def test_truncate_to_week_is_iso_monday() -> None:
    # 2026-05-20 is a Wednesday; its ISO week starts Monday 2026-05-18.
    assert truncate_to(dt.datetime(2026, 5, 20, tzinfo=UTC), "week") == dt.datetime(
        2026, 5, 18, tzinfo=UTC
    )


def test_truncate_to_month_is_first() -> None:
    assert truncate_to(dt.datetime(2026, 5, 20, tzinfo=UTC), "month") == dt.datetime(
        2026, 5, 1, tzinfo=UTC
    )


def test_truncate_to_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        truncate_to(dt.datetime(2026, 5, 20, tzinfo=UTC), "fortnight")


def test_fold_week_is_weighted_not_mean_of_means() -> None:
    rows = [
        (dt.datetime(2026, 5, 18, tzinfo=UTC), 2, 0.8),  # same ISO week as 05-20
        (dt.datetime(2026, 5, 20, tzinfo=UTC), 1, 0.3),
        (dt.datetime(2026, 5, 27, tzinfo=UTC), 1, 0.1),  # next ISO week (05-25)
    ]
    out = fold_buckets(rows, "week")
    assert [b for b, _, _ in out] == [
        dt.datetime(2026, 5, 18, tzinfo=UTC),
        dt.datetime(2026, 5, 25, tzinfo=UTC),
    ]
    assert out[0][1] == 3
    assert out[0][2] == pytest.approx(1.9 / 3)  # weighted, not 0.55
    assert out[1] == (dt.datetime(2026, 5, 25, tzinfo=UTC), 1, pytest.approx(0.1))


def test_fold_day_is_passthrough_sorted() -> None:
    rows = [
        (dt.datetime(2026, 5, 20, tzinfo=UTC), 1, 0.3),
        (dt.datetime(2026, 5, 18, tzinfo=UTC), 2, 0.8),
    ]
    out = fold_buckets(rows, "day")
    assert [b for b, _, _ in out] == [
        dt.datetime(2026, 5, 18, tzinfo=UTC),
        dt.datetime(2026, 5, 20, tzinfo=UTC),
    ]
    assert out[0][1] == 2
    assert out[0][2] == pytest.approx(0.8)


def test_fold_single_row_week() -> None:
    rows = [(dt.datetime(2026, 5, 20, tzinfo=UTC), 1, 0.5)]
    out = fold_buckets(rows, "week")
    assert out == [(dt.datetime(2026, 5, 18, tzinfo=UTC), 1, pytest.approx(0.5))]


def test_fold_month_separates_adjacent_months() -> None:
    rows = [
        (dt.datetime(2026, 5, 31, tzinfo=UTC), 1, 0.9),
        (dt.datetime(2026, 6, 1, tzinfo=UTC), 3, 0.1),
    ]
    out = fold_buckets(rows, "month")
    assert [b for b, _, _ in out] == [
        dt.datetime(2026, 5, 1, tzinfo=UTC),
        dt.datetime(2026, 6, 1, tzinfo=UTC),
    ]
    assert out[0][1] == 1
    assert out[1] == (dt.datetime(2026, 6, 1, tzinfo=UTC), 3, pytest.approx(0.1))


def test_fold_empty() -> None:
    assert fold_buckets([], "week") == []
