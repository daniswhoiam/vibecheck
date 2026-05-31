-- Declarative desired-state schema for vibecheck.
-- Single source of truth: pgschema reconciles the database to this file
-- (scripts/db-apply.sh), and Scythe generates typed query code from it
-- (scripts/codegen.sh). Edit this file, then run both scripts.

CREATE TABLE tools (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug         varchar(50)  NOT NULL UNIQUE,
    display_name varchar(255) NOT NULL,
    aliases      text[]       NOT NULL DEFAULT '{}',
    created_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE posts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source       varchar(20)  NOT NULL,
    source_id    varchar(255) NOT NULL,
    content      text         NOT NULL,
    author       varchar(255),
    url          varchar(2048),
    published_at timestamptz  NOT NULL,
    metadata     jsonb        NOT NULL DEFAULT '{}',
    created_at   timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)
);
CREATE INDEX idx_posts_published_at ON posts (published_at);

CREATE TABLE mentions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tool_id    uuid NOT NULL REFERENCES tools(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (post_id, tool_id)
);
CREATE INDEX idx_mentions_tool_id ON mentions (tool_id);

CREATE TABLE analysis_results (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mention_id    uuid             NOT NULL REFERENCES mentions(id) ON DELETE CASCADE,
    model_name    varchar(100)     NOT NULL,
    model_version varchar(50),
    score         double precision NOT NULL,
    label         varchar(20)      NOT NULL,
    raw_output    jsonb,
    analyzed_at   timestamptz      NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (mention_id, model_name, model_version)
);
CREATE INDEX idx_analysis_mention ON analysis_results (mention_id, model_name, analyzed_at DESC);
