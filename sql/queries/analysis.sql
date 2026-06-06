-- @name CreateAnalysisResult
-- @returns one
-- Idempotent insert-or-get on the (mention_id, model_name, model_version)
-- natural key. The no-op DO UPDATE (model_name = itself) returns the existing
-- verdict WITHOUT overwriting score/label/analyzed_at, so an identical rerun is
-- effectively a no-op that still hands the caller a usable row.
INSERT INTO analysis_results (
    mention_id, model_name, model_version, score, label, raw_output
)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (mention_id, model_name, model_version) DO UPDATE SET model_name
= excluded.model_name
RETURNING
    id, mention_id, model_name, model_version, score, label, raw_output, analyzed_at;

-- @name GetSentimentByToolBucket
-- @returns many
-- @param bucket text
-- Bucket in UTC explicitly: date_trunc on a timestamptz otherwise truncates in
-- the session TimeZone, so the same post could land in different daily buckets
-- across local/CI/prod. Converting to UTC and back keeps the bucket a
-- session-independent timestamptz anchored at UTC midnight.
SELECT
    t.slug AS tool_slug,
    date_trunc(
        $4::text, p.published_at AT TIME ZONE 'UTC'
    ) AT TIME ZONE 'UTC' AS bucket,
    count(*) AS n,
    avg(a.score)::double precision AS avg_score
FROM analysis_results a
JOIN mentions m ON m.id = a.mention_id
JOIN posts p ON p.id = m.post_id
JOIN tools t ON t.id = m.tool_id
WHERE t.slug = $1 AND p.published_at >= $2 AND p.published_at < $3
GROUP BY
    t.slug,
    date_trunc($4::text, p.published_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
ORDER BY bucket;
