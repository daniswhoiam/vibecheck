"""Authored public response contract — deliberately decoupled from the
generated DB row dataclasses (internal ids/timestamps are not exposed)."""

import datetime as dt

from pydantic import BaseModel


class Tool(BaseModel):
    slug: str
    display_name: str
    aliases: list[str]


class SentimentPoint(BaseModel):
    bucket_start: dt.datetime
    n: int
    avg_score: float


class SentimentSeries(BaseModel):
    tool: str
    period: str
    bucket: str
    start: dt.datetime
    end: dt.datetime
    series: list[SentimentPoint]
