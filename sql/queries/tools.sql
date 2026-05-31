-- @name ListTools
-- @returns many
SELECT id, slug, display_name, aliases, created_at
FROM tools
ORDER BY slug;
