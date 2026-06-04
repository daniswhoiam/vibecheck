#!/usr/bin/env bash
# Reconcile the target database to the declarative schema (sql/schema.sql).
# pgschema takes discrete PG* connection vars, not a URL — derive them from
# DATABASE_URL (via scripts/pg-env.sh) so the repo keeps one DSN source.
# Extra args pass through to `pgschema apply` (e.g. --auto-approve, --lock-timeout 30s).
set -euo pipefail

cd "$(dirname "$0")/.."

eval "$(./scripts/pg-env.sh)"

pgschema apply --schema public --file sql/schema.sql "$@"
