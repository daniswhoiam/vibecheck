-- @name CreateMention
-- @returns one
INSERT INTO mentions (post_id, tool_id)
VALUES ($1, $2)
ON CONFLICT (post_id, tool_id) DO NOTHING
RETURNING id, post_id, tool_id, created_at;
