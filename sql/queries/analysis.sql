-- @name CreateAnalysisResult
-- @returns one
INSERT INTO analysis_results (
    mention_id, model_name, model_version, score, label, raw_output
)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING
    id, mention_id, model_name, model_version, score, label, raw_output, analyzed_at;

-- @name GetSentimentByToolBucket
-- @returns many
SELECT
    t.slug AS tool_slug,
    date_trunc('day', p.published_at) AS bucket,
    count(*) AS n,
    avg(a.score) AS avg_score
FROM analysis_results a
JOIN mentions m ON m.id = a.mention_id
JOIN posts p ON p.id = m.post_id
JOIN tools t ON t.id = m.tool_id
WHERE t.slug = $1 AND p.published_at >= $2 AND p.published_at < $3
GROUP BY t.slug, date_trunc('day', p.published_at)
ORDER BY bucket;
