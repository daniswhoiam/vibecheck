-- @name ListTools
-- @returns many
SELECT id, slug, display_name, aliases, created_at
FROM tools
ORDER BY slug;

-- @name GetToolBySlug
-- @returns one
SELECT id, slug, display_name, aliases, created_at
FROM tools
WHERE slug = $1;
