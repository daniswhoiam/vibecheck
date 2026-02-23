"""Keyword relevance filter for VibeCheck data collection.

Implements ambiguity-aware matching:
- Unambiguous entity names (ChatGPT, Copilot, GPT-4o) match bare as whole words
- Ambiguous names (Claude, Cursor, Gemini, Llama, Mistral) require a context
  word to appear within ±150 characters to avoid false positives.

Usage:
    from pipeline.services.filter_service import is_relevant
    if is_relevant(title + " " + (body or "")):
        # store the post
"""
import re

# Character window for ambiguous name context matching
CONTEXT_WINDOW = 150

# Unambiguous names: bare word-boundary match is sufficient
# Note: lowercase here; input text will be lowercased before matching
UNAMBIGUOUS_NAMES: list[str] = [
    "chatgpt",
    "gpt-4o",
    "gpt-4",
    "gpt-3.5",
    "github copilot",
    "copilot",
    "lovable",
    "replit",
    "v0.dev",
]

# Ambiguous names: require at least one context word nearby
# Context words are matched with word boundaries to avoid substring false positives
# (e.g., "ai" must not match inside "painted" or "trained")
AMBIGUOUS_NAMES: dict[str, list[str]] = {
    "claude": [
        "llm", "ai", "model", "anthropic", "coding", "sonnet", "haiku",
        "opus", "assistant", "chatbot", "prompt",
    ],
    "cursor": [
        "ai", "editor", "ide", "coding", "llm", "vibe", "autocomplete",
        "codebase", "composer", "tab completion",
    ],
    "gemini": [
        "google", "ai", "llm", "model", "gemini pro", "gemini flash",
        "deepmind", "bard",
    ],
    "llama": [
        "meta", "llm", "model", "ollama", "local", "open source",
        "fine-tun", "hugging",
    ],
    "mistral": [
        "llm", "model", "ai", "mistral ai", "mixtral", "open source",
        "fine-tun",
    ],
}

# Pre-compile unambiguous patterns once at module load
_UNAMBIGUOUS_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b' + re.escape(name) + r'\b')
    for name in UNAMBIGUOUS_NAMES
]

# Pre-compile ambiguous name patterns once at module load
_AMBIGUOUS_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(r'\b' + re.escape(name) + r'\b')
    for name in AMBIGUOUS_NAMES
}

# Pre-compile context word patterns using word boundaries to prevent substring matches.
# Example: "ai" must match as a standalone word, not inside "painted" or "trained".
# Multi-word context phrases (e.g., "tab completion") use a plain \b boundary on each end.
_CONTEXT_PATTERNS: dict[str, list[re.Pattern]] = {
    name: [re.compile(r'\b' + re.escape(ctx) + r'\b') for ctx in ctx_words]
    for name, ctx_words in AMBIGUOUS_NAMES.items()
}


def is_relevant(text: str) -> bool:
    """Return True if the text is relevant to any tracked entity.

    Args:
        text: Combined title + body text. Caller should concatenate
              title and body before passing (e.g., f"{title} {body}").

    Returns:
        True if the post appears to be about a tracked AI tool or model.
        False if the post is unrelated.
    """
    if not text:
        return False

    text_lower = text.lower()

    # 1. Check unambiguous names — bare word match is sufficient
    for pattern in _UNAMBIGUOUS_PATTERNS:
        if pattern.search(text_lower):
            return True

    # 2. Check ambiguous names — require context word within ±CONTEXT_WINDOW chars
    for name, context_words in AMBIGUOUS_NAMES.items():
        name_pattern = _AMBIGUOUS_PATTERNS[name]
        ctx_patterns = _CONTEXT_PATTERNS[name]
        for match in name_pattern.finditer(text_lower):
            start = max(0, match.start() - CONTEXT_WINDOW)
            end = min(len(text_lower), match.end() + CONTEXT_WINDOW)
            window = text_lower[start:end]
            # Use word-boundary patterns to avoid substring false positives
            if any(ctx_pat.search(window) for ctx_pat in ctx_patterns):
                return True

    return False
