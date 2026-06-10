"""Tool detection unit tests: word-boundary alias matching from registry data,
with negative patterns shielding lookalikes (Microsoft Copilot et al.)."""

import pytest
from ingestion.detection import ToolMatcher

# Mirrors the shape of sql/seeds/tools.sql: slug -> aliases.
ALIASES = {
    "chatgpt": ["chatgpt", "gpt", "openai chatgpt"],
    "github-copilot": ["copilot", "gh copilot", "github copilot"],
    "cursor": ["cursor", "cursor ai", "cursor editor"],
    "claude-code": ["claude code", "claudecode", "cc"],
}


@pytest.fixture
def matcher() -> ToolMatcher:
    return ToolMatcher(ALIASES)


def test_detects_single_tool(matcher):
    assert matcher.detect("I switched to Cursor last week") == {"cursor"}


def test_detects_multiple_tools(matcher):
    text = "Cursor vs GitHub Copilot: which one wins?"
    assert matcher.detect(text) == {"cursor", "github-copilot"}


def test_case_insensitive(matcher):
    assert matcher.detect("CURSOR is great") == {"cursor"}


def test_no_match_returns_empty_set(matcher):
    assert matcher.detect("I prefer handwritten assembly") == set()


def test_empty_text(matcher):
    assert matcher.detect("") == set()


def test_word_boundary_blocks_substrings(matcher):
    # "cursor" inside a larger word is not a mention.
    assert matcher.detect("the precursors of modern IDEs") == set()


def test_gpt_alias_does_not_fire_inside_chatgpt(matcher):
    # "ChatGPT" must resolve via the chatgpt alias only — the embedded "gpt"
    # has no word boundary before it. (Same slug here, but the regex must not
    # rely on that coincidence.)
    assert matcher.detect("ChatGPT wrote my tests") == {"chatgpt"}


def test_gpt_alias_matches_standalone_and_hyphenated(matcher):
    assert matcher.detect("GPT is overhyped") == {"chatgpt"}
    # A hyphen is a word boundary: "GPT-4" contains the word "gpt".
    assert matcher.detect("GPT-4 is impressive") == {"chatgpt"}


def test_copilot_alone_means_github_copilot(matcher):
    assert matcher.detect("Copilot suggested the whole function") == {"github-copilot"}


def test_microsoft_copilot_is_not_github_copilot(matcher):
    assert matcher.detect("Microsoft Copilot now ships with Windows") == set()
    assert matcher.detect("Copilot Studio adds agents") == set()
    assert matcher.detect("M365 Copilot summarizes meetings") == set()


def test_negative_pattern_does_not_shadow_genuine_mention(matcher):
    text = "Microsoft Copilot is not GitHub Copilot, and Copilot the coding tool rules"
    assert matcher.detect(text) == {"github-copilot"}


def test_multiword_alias_tolerates_extra_whitespace(matcher):
    assert matcher.detect("claude  code feels native") == {"claude-code"}


def test_short_alias_needs_word_boundaries(matcher):
    assert matcher.detect("just use cc for the heavy lifting") == {"claude-code"}
    assert matcher.detect("gcc compiles fine") == set()
