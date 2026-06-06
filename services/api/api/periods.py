"""Period parsing for the sentiment endpoint's window length.

The query-string format is enforced natively by ``PERIOD_PATTERN`` at the
FastAPI boundary (yielding a standard 422), so this module only maps an
already-validated period such as ``"30d"`` or ``"2w"`` onto a timedelta.
"""

import datetime as dt

# <positive int, 1-4 digits><d|w>. The leading [1-9] forbids zero and leading
# zeros; the 4-digit cap keeps the resulting timedelta well in range (max
# 9999 weeks), so it can never OverflowError on construction.
PERIOD_PATTERN = r"^[1-9]\d{0,3}[dw]$"

_UNIT = {"d": "days", "w": "weeks"}


def parse_period(period: str) -> dt.timedelta:
    """Map a ``PERIOD_PATTERN``-valid period string onto a timedelta."""
    return dt.timedelta(**{_UNIT[period[-1]]: int(period[:-1])})
