-- Idempotent seed for the curated `tools` registry.
-- Re-runnable: anchored on `slug`, so re-running converges existing rows
-- (keeps each tool's UUID stable, never breaking existing mentions).
INSERT INTO tools (slug, display_name, aliases) VALUES
    ('cursor',         'Cursor',         ARRAY['cursor', 'cursor ai', 'cursor editor']),
    ('claude-code',    'Claude Code',    ARRAY['claude code', 'claudecode', 'cc']),
    ('github-copilot', 'GitHub Copilot', ARRAY['copilot', 'gh copilot', 'github copilot']),
    ('windsurf',       'Windsurf',       ARRAY['windsurf', 'codeium windsurf']),
    ('cline',          'Cline',          ARRAY['cline', 'claude dev']),
    ('aider',          'Aider',          ARRAY['aider', 'aider chat']),
    ('chatgpt',        'ChatGPT',        ARRAY['chatgpt', 'gpt', 'openai chatgpt']),
    ('kilo',           'Kilo Code',      ARRAY['kilo', 'kilo code', 'kilocode']),
    ('codex',          'Codex',          ARRAY['codex', 'openai codex', 'codex cli'])
ON CONFLICT (slug) DO UPDATE
SET display_name = EXCLUDED.display_name,
    aliases      = EXCLUDED.aliases;
