"""Content deduplication utilities.

Article-specific functions removed in Phase 5.
Post deduplication will use content_hash in the new schema.
"""
import hashlib
import logging

logger = logging.getLogger(__name__)


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content for deduplication.

    Args:
        content: Content string to hash (URL, body text, etc.)

    Returns:
        64-character hexadecimal hash string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
