"""Pure time-bucket aggregation for the sentiment endpoint.

The data layer returns DAY buckets with (n, avg). To present coarser
granularities we re-aggregate days into weeks/months. A mean is NOT
composable, so we roll up via the (sum, count) sufficient statistic:
weighted_avg = sum(nᵢ·avgᵢ) / sum(nᵢ) — never a mean of means.
"""

import datetime as dt


def truncate_to(day_start: dt.datetime, granularity: str) -> dt.datetime:
    """Truncate a UTC day-start to the start of its day/week/month bucket.

    'week' is ISO (Monday-anchored), matching Postgres date_trunc('week', ...).
    """
    if granularity == "day":
        return day_start
    if granularity == "week":
        return day_start - dt.timedelta(days=day_start.weekday())
    if granularity == "month":
        return day_start.replace(day=1)
    raise ValueError(f"invalid granularity: {granularity!r}")


def fold_buckets(
    day_rows: list[tuple[dt.datetime, int, float]],
    granularity: str,
) -> list[tuple[dt.datetime, int, float]]:
    """Roll up (day_start, n, avg) rows into (bucket_start, n, weighted_avg).

    Sorted ascending by bucket_start. Buckets with no data never appear (sparse).
    """
    sums: dict[dt.datetime, float] = {}
    counts: dict[dt.datetime, int] = {}
    for day_start, n, avg in day_rows:
        bucket_start = truncate_to(day_start, granularity)
        sums[bucket_start] = sums.get(bucket_start, 0.0) + avg * n
        counts[bucket_start] = counts.get(bucket_start, 0) + n
    return [(b, counts[b], sums[b] / counts[b]) for b in sorted(sums)]
