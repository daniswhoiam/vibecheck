#!/usr/bin/env bash
# Regenerate lib/db typed query code from the declarative schema + queries.
# Scythe parses sql/schema.sql statically (see scythe.toml) — NO database is
# required. To change the schema, edit sql/schema.sql then run this script.
#
# Requires Scythe >= 0.8.0, which emits `import uuid` / `from typing import Any`
# natively (earlier versions needed a post-generate import patch).
set -euo pipefail

# Preflight: enforce the documented minimum Scythe version. An older local
# install can silently regenerate incompatible code that only fails later in CI.
required_scythe="0.8.0"
installed_scythe="$(scythe --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
if [ -z "$installed_scythe" ]; then
    echo "error: could not determine scythe version (is scythe installed?)" >&2
    exit 1
fi
if [ "$(printf '%s\n%s\n' "$required_scythe" "$installed_scythe" | sort -V | head -1)" != "$required_scythe" ]; then
    echo "error: scythe >= $required_scythe required, found $installed_scythe" >&2
    exit 1
fi

# Always run from the repo root (parent of this script's dir).
cd "$(dirname "$0")/.."

GEN_DIR="lib/db/lib_db/generated"

# Generate Python from sql/schema.sql + sql/queries/*.sql.
scythe generate

# Make the generated dir an importable package.
touch "$GEN_DIR/__init__.py"

echo "Codegen complete -> $GEN_DIR/queries.py"
