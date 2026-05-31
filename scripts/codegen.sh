#!/usr/bin/env bash
# Regenerate lib/db typed query code from the declarative schema + queries.
# Scythe parses sql/schema.sql statically (see scythe.toml) — NO database is
# required. To change the schema, edit sql/schema.sql then run this script.
#
# Requires Scythe >= 0.8.0, which emits `import uuid` / `from typing import Any`
# natively (earlier versions needed a post-generate import patch).
set -euo pipefail

# Always run from the repo root (parent of this script's dir).
cd "$(dirname "$0")/.."

GEN_DIR="lib/db/lib_db/generated"

# Generate Python from sql/schema.sql + sql/queries/*.sql.
scythe generate

# Make the generated dir an importable package.
touch "$GEN_DIR/__init__.py"

echo "Codegen complete -> $GEN_DIR/queries.py"
