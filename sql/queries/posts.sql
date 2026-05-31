-- @name CreatePost
-- @returns one
INSERT INTO posts (
    source, source_id, content, author, url, published_at, metadata
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (source, source_id) DO NOTHING
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
