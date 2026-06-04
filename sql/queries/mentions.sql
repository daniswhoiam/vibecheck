-- @name CreateMention
-- @returns one
-- Idempotent insert-or-get on (post_id, tool_id); no-op DO UPDATE returns the
-- existing row on conflict. See posts.sql CreatePost for rationale.
INSERT INTO mentions (post_id, tool_id)
VALUES ($1, $2)
ON CONFLICT (post_id, tool_id) DO UPDATE SET tool_id = excluded.tool_id
RETURNING id, post_id, tool_id, created_at;
