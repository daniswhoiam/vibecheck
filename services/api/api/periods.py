"""Pure parsing/validation for the sentiment endpoint's query params.

No HTTP, no DB — so it is unit-testable in isolation. Callers translate the
ValueErrors raised here into HTTP 422 at the FastAPI boundary.
"""

import datetime as dt
import re

BUCKETS = {"day", "week", "month"}

_PERIOD_RE = re.compile(r"^(\d+)([dw])$")
_UNIT = {"d": "days", "w": "weeks"}


def parse_period(period: str) -> dt.timedelta:
    """Parse a window length like ``"30d"`` or ``"2w"`` into a timedelta.

    Grammar: ``<positive int><d|w>``. Raises ValueError on anything else.
    """
    match = _PERIOD_RE.match(period)
    if match is None:
        raise ValueError(f"invalid period: {period!r} (expected e.g. '30d' or '2w')")
    value = int(match.group(1))
    if value <= 0:
        raise ValueError(f"invalid period: {period!r} (must be positive)")
    return dt.timedelta(**{_UNIT[match.group(2)]: value})


def validate_bucket(bucket: str) -> str:
    """Return ``bucket`` if it is a supported granularity, else raise ValueError."""
    if bucket not in BUCKETS:
        raise ValueError(f"invalid bucket: {bucket!r} (expected one of {sorted(BUCKETS)})")
    return bucket
