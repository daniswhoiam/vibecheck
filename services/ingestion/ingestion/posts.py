"""The canonical post every fetcher maps into.

Field-for-field the worker's PostMessage minus `tools` — detection assigns
those later, and the publisher joins the two into the wire format.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FetchedPost:
    source: str
    source_id: str
    content: str
    published_at: dt.datetime  # always timezone-aware; the contract refuses naive
    author: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
