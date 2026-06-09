-- DEV-ONLY demo facts for manual API verification. NOT applied in CI.
-- Idempotent on posts(source, source_id). Targets the seeded 'cursor' tool,
-- so sql/seeds/tools.sql must have been applied first.
WITH t AS (SELECT id FROM tools WHERE slug = 'cursor'),
ins_post AS (
    INSERT INTO posts (source, source_id, content, author, url, published_at, metadata)
    VALUES
        ('demo', 'demo-1', 'Cursor is great', 'alice', NULL, now() - interval '2 days', '{}'),
        ('demo', 'demo-2', 'Cursor crashed today', 'bob', NULL, now() - interval '1 day', '{}')
    ON CONFLICT (source, source_id) DO UPDATE SET source = excluded.source
    RETURNING id
),
ins_mention AS (
    INSERT INTO mentions (post_id, tool_id)
    SELECT p.id, t.id FROM ins_post p, t
    ON CONFLICT (post_id, tool_id) DO UPDATE SET post_id = excluded.post_id
    RETURNING id, post_id
)
INSERT INTO analysis_results (mention_id, model_name, score, label)
SELECT m.id, 'demo-model',
       CASE WHEN p.source_id = 'demo-1' THEN 0.9 ELSE 0.2 END,
       CASE WHEN p.source_id = 'demo-1' THEN 'positive' ELSE 'negative' END
FROM ins_mention m JOIN posts p ON p.id = m.post_id
ON CONFLICT (mention_id, model_name, model_version) DO UPDATE SET model_name = excluded.model_name;
