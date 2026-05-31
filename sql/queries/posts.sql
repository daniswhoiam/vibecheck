-- @name CreatePost
-- @returns one
-- Idempotent insert-or-get on (source, source_id). The no-op DO UPDATE (set a
-- key column to itself) exists only so a conflict still counts as a write and
-- RETURNING emits the existing row; no content/metadata is overwritten. This is
-- race-free (the DB serializes the conflict) and always returns a usable row.
INSERT INTO posts (
    source, source_id, content, author, url, published_at, metadata
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (source, source_id) DO UPDATE SET source_id = excluded.source_id
RETURNING
    id, source, source_id, content, author, url, published_at, metadata, created_at;

-- @name GetPostsByToolAndRange
-- @returns many
SELECT
    p.id,
    p.source,
    p.source_id,
    p.content,
    p.author,
    p.url,
    p.published_at,
    p.metadata,
    p.created_at
FROM posts p
JOIN mentions m ON m.post_id = p.id
JOIN tools t ON t.id = m.tool_id
WHERE t.slug = $1 AND p.published_at >= $2 AND p.published_at < $3
ORDER BY p.published_at DESC
LIMIT $4;
