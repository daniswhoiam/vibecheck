"""Which tracked tools does a text mention?

The matcher is built from the `tools` registry (slug -> aliases), so seeding a
new tool needs no code change. Matching is case-insensitive on word
boundaries: precise enough for "gpt" not to fire inside "ChatGPT", while
"GPT-4" still counts (a hyphen is a boundary). Lookalike phrases that contain
an alias but are a different product ("Microsoft Copilot") are blanked out of
the text before alias matching, so they neither match nor shadow a genuine
mention elsewhere in the same text.
"""

import re
from collections.abc import Iterable, Mapping

# Phrases that contain a tracked alias but refer to a different product.
# Matcher logic, not registry data — promote to the DB only if this ever
# needs per-deployment tuning.
NEGATIVE_PHRASES: tuple[str, ...] = (
    "microsoft copilot",
    "m365 copilot",
    "microsoft 365 copilot",
    "office copilot",
    "windows copilot",
    "copilot studio",
    "copilot+ pc",
)


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Compile a case-insensitive, word-bounded pattern for a phrase.

    Escaped whitespace becomes \\s+ so multi-word aliases tolerate formatting.
    Explicit lookarounds instead of \\b: an alias may end in a non-word char
    (e.g. "copilot+ pc"), where \\b would invert its meaning.
    """
    flexible = re.escape(phrase).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){flexible}(?!\w)", re.IGNORECASE)


class ToolMatcher:
    """Built once per ingestion cycle from the tools registry."""

    def __init__(self, aliases_by_slug: Mapping[str, Iterable[str]]) -> None:
        self._patterns: list[tuple[str, re.Pattern[str]]] = [
            (slug, _phrase_pattern(alias))
            for slug, aliases in aliases_by_slug.items()
            for alias in aliases
        ]
        self._negative = [_phrase_pattern(p) for p in NEGATIVE_PHRASES]

    def detect(self, text: str) -> set[str]:
        """Return the slugs of every tool the text mentions."""
        for pattern in self._negative:
            text = pattern.sub(" ", text)
        return {slug for slug, pattern in self._patterns if pattern.search(text)}
