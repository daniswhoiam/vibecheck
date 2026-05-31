#!/usr/bin/env bash
# Print `export PG*=...` lines derived from DATABASE_URL, for tools that take
# discrete PG* connection vars instead of a URL (pgschema). Values are
# shell-quoted so metacharacters in a password/host can't break the eval.
# Usage:  eval "$(./scripts/pg-env.sh)"
set -euo pipefail

cd "$(dirname "$0")/.."

DATABASE_URL="${DATABASE_URL:-postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable}"

python3 - "$DATABASE_URL" <<'PY'
import shlex
import sys
import urllib.parse as u

p = u.urlparse(sys.argv[1])
# urlparse does NOT percent-decode userinfo/path, so a valid URL-encoded
# credential like p%40ss must be unquoted to p@ss before export. parse_qsl
# already decodes query params, so PGSSLMODE needs no unquote.
q = dict(u.parse_qsl(p.query))
print(f'export PGHOST={shlex.quote(u.unquote(p.hostname) if p.hostname else "localhost")}')
print(f'export PGPORT={shlex.quote(str(p.port or 5432))}')
print(f'export PGUSER={shlex.quote(u.unquote(p.username) if p.username else "")}')
print(f'export PGPASSWORD={shlex.quote(u.unquote(p.password) if p.password else "")}')
print(f'export PGDATABASE={shlex.quote(u.unquote((p.path or "/").lstrip("/")))}')
print(f'export PGSSLMODE={shlex.quote(q.get("sslmode", "prefer"))}')
PY
