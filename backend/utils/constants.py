"""Application constants for VibeCheck.

Defines curated entity list and aspect sentiment categories.
"""

# Fixed curated entity list for consistent tracking (from PROJECT.md)
# AI Models: GPT-4o, Claude, Gemini, Llama, Mistral
# AI Tools: Cursor, Lovable, v0, GitHub Copilot, Replit
CURATED_ENTITIES = [
    {"name": "GPT-4o", "category": "model"},
    {"name": "Claude", "category": "model"},
    {"name": "Gemini", "category": "model"},
    {"name": "Llama", "category": "model"},
    {"name": "Mistral", "category": "model"},
    {"name": "Cursor", "category": "tool"},
    {"name": "Lovable", "category": "tool"},
    {"name": "v0", "category": "tool"},
    {"name": "GitHub Copilot", "category": "tool"},
    {"name": "Replit", "category": "tool"},
]

# Valid aspect categories for aspect-level sentiment scoring
# Used by Tier 2 LLM extraction (Phase 8) and API validation
VALID_ASPECTS = frozenset({
    "performance",
    "cost",
    "reliability",
    "ux",
    "speed",
    "code_quality",
    "context_window",
})

# Score boundaries for aspect sentiment (enforced at application level)
ASPECT_SCORE_MIN = -1.0
ASPECT_SCORE_MAX = 1.0
