import datetime as dt
import re

import pytest
from api.periods import PERIOD_PATTERN, parse_period

_period = re.compile(PERIOD_PATTERN)


def test_parse_period_days() -> None:
    assert parse_period("30d") == dt.timedelta(days=30)


def test_parse_period_weeks() -> None:
    assert parse_period("2w") == dt.timedelta(weeks=2)


def test_parse_period_max_bounded_value_does_not_overflow() -> None:
    # The 4-digit cap keeps the largest accepted period well within timedelta's
    # range — the OverflowError path is unreachable by construction.
    assert parse_period("9999w") == dt.timedelta(weeks=9999)


@pytest.mark.parametrize("ok", ["1d", "30d", "2w", "9999d", "9999w", "1000d"])
def test_pattern_accepts_valid_periods(ok: str) -> None:
    assert _period.match(ok)


@pytest.mark.parametrize(
    "bad",
    [
        "invalid",
        "30",
        "d",
        "-5d",
        "0d",
        "30m",
        "1.5d",
        "",
        "099d",  # leading zero
        "10000d",  # 5 digits — over the cap that prevents overflow
        "99999999999d",  # the historical OverflowError trigger
    ],
)
def test_pattern_rejects_invalid_periods(bad: str) -> None:
    assert _period.match(bad) is None
