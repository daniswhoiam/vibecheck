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
q = dict(u.parse_qsl(p.query))
print(f'export PGHOST={shlex.quote(p.hostname or "localhost")}')
print(f'export PGPORT={shlex.quote(str(p.port or 5432))}')
print(f'export PGUSER={shlex.quote(p.username or "")}')
print(f'export PGPASSWORD={shlex.quote(p.password or "")}')
print(f'export PGDATABASE={shlex.quote((p.path or "/").lstrip("/"))}')
print(f'export PGSSLMODE={shlex.quote(q.get("sslmode", "prefer"))}')
PY
