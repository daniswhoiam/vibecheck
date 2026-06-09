#!/usr/bin/env bash
# Regenerate the committed OpenAPI spec from the live FastAPI app.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -c "
import json
from api.main import app
with open('services/api/openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2, sort_keys=True)
    f.write('\n')
"
echo "Wrote services/api/openapi.json"
