import datetime as dt

import pytest
from api.periods import BUCKETS, parse_period, validate_bucket


def test_parse_period_days() -> None:
    assert parse_period("30d") == dt.timedelta(days=30)


def test_parse_period_weeks() -> None:
    assert parse_period("2w") == dt.timedelta(weeks=2)


@pytest.mark.parametrize("bad", ["invalid", "30", "d", "-5d", "0d", "30m", "1.5d", ""])
def test_parse_period_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_period(bad)


def test_validate_bucket_ok() -> None:
    assert validate_bucket("week") == "week"
    assert {"day", "week", "month"} == BUCKETS


@pytest.mark.parametrize("bad", ["fortnight", "year", "Day", ""])
def test_validate_bucket_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_bucket(bad)
