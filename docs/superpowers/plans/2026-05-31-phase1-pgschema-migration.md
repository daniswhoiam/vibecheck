# Phase 1 — Migrate Data Layer from dbmate to pgschema — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the imperative dbmate migration pipeline with declarative pgschema, making `sql/schema.sql` the single source of truth that both pgschema (apply) and Scythe (codegen) consume — then rewrite the branch history so it reads pgschema-native.

**Architecture:** The data layer's source of truth flips from a *sequence of migrations* to a *desired-state schema file*. pgschema reconciles a live database to that file (`plan` → `apply`); Scythe parses the same file statically to generate typed query code. Because Scythe never needed a database — only a flat DDL file — removing dbmate collapses the codegen pipeline from 5 steps to 2 and eliminates the pg_dump `\restrict`-strip hack. CI gains a `pgschema apply` step (replacing `dbmate up`) and lints the generated `pgschema plan` SQL with squawk for unsafe-DDL safety.

**Tech Stack:** PostgreSQL 18, pgschema 1.10.0 (declarative schema), Scythe 0.8.0 (`python-psycopg3` codegen → `lib/db`), squawk (plan-safety lint), psycopg3 async, uv workspace.

**Pre-verified by spikes (2026-05-31):**
- Scythe parses a hand-authored declarative `schema.sql` and produces **byte-identical** `queries.py` to the current committed output (modulo the 2 patched imports).
- `pgschema apply` to a blank schema succeeds; a follow-up `pgschema plan` reports "No changes detected" (idempotent).
- `pgschema dump` preserves `UNIQUE NULLS NOT DISTINCT`, `text[] DEFAULT '{}'`, the descending composite index, and FK cascades — with no `\restrict`, no `public.` qualification, no `schema_migrations`.

**Decisions locked in (2026-05-31):**
- **Branch strategy:** stay on `phase-1-schema-data-layer`, **rewrite history** (Task 7) so the final state looks pgschema-native; force-push with `--force-with-lease`.
- **Migration safety:** squawk lints the `pgschema plan` SQL output (not migration files, which no longer exist).

---

## Conventions used throughout

- **Run all commands from the repo root** (`/Users/daniswhoiam/Projects/vibecheck`) unless stated.
- **Tools assumed installed locally:** `pgschema` 1.10.0, `scythe` 0.8.0, `squawk`, `psql`, `docker`, `uv`. (CI installs them itself — Task 5.)
  - During the spike, the pgschema binary was placed at `/tmp/pgschema`. For local execution, install it permanently first: `brew tap pgplex/pgschema && brew install pgschema` (or copy `/tmp/pgschema` to `/usr/local/bin/pgschema`). Verify: `pgschema --help`.
- **Local Postgres:** `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres`. Default DSN: `postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable`.
- **pgschema connection:** pgschema takes discrete flags / `PG*` env vars (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGSSLMODE`) — **not** a `DATABASE_URL`. `scripts/db-apply.sh` (Task 3) derives `PG*` from `DATABASE_URL` so the repo keeps one DSN source.

## File structure

| File | Action | Responsibility after this plan |
|------|--------|--------------------------------|
| `sql/schema.sql` | **Create** | The single declarative source of truth. Consumed by both pgschema (apply) and Scythe (codegen). |
| `sql/migrations/20260521192052_create_core_schema.sql` | **Delete** | Imperative migration — no longer the source of truth. |
| `sql/migrations/` (dir) | **Delete** | Empty after the migration is removed. |
| `sql/schema.scythe.sql` | **Delete** | Was a derived pg_dump snapshot; `sql/schema.sql` replaces it as Scythe's input. |
| `scythe.toml` | **Modify** | Point `schema` at `sql/schema.sql`. |
| `scripts/codegen.sh` | **Modify** | Collapse to `scythe generate` + import-patch. No DB, no dbmate, no dump, no strip. |
| `scripts/db-apply.sh` | **Create** | Reconcile a target DB to `sql/schema.sql` via pgschema. Used locally and by CI. |
| `.github/workflows/ci.yml` | **Modify** | Drop dbmate + migration-squawk; add pgschema install, schema-apply, plan-lint; adjust freshness gate. |
| `docs/superpowers/specs/2026-05-20-phase1-schema-data-layer-design.md` | **Modify** | Rewrite the migrations / codegen-pipeline / CI sections to describe pgschema. |
| `lib/db/**`, `sql/queries/*.sql`, `sql/seeds/tools.sql`, `tests/test_smoke.py`, `pyproject.toml`s, `.pre-commit-config.yaml` | **Unchanged** | Spikes proved codegen output is identical; the data layer carries over verbatim. |

---

### Task 1: Replace migrations with a declarative schema file

**Files:**
- Create: `sql/schema.sql`
- Modify: `scythe.toml`
- Delete: `sql/migrations/20260521192052_create_core_schema.sql`, `sql/schema.scythe.sql`

- [ ] **Step 1: Create the declarative schema file**

Create `sql/schema.sql` with the exact DDL below. This is the `migrate:up` body verbatim (the spike proved this style yields identical codegen), with no `migrate:up/down` markers, no `public.` qualification, and no `schema_migrations` table.

```sql
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
```

- [ ] **Step 2: Repoint Scythe at the declarative file**

Modify `scythe.toml` — change only the `schema` line:

```toml
[scythe]
version = "1"

[[sql]]
name = "main"
engine = "postgresql"
schema = ["sql/schema.sql"]
queries = ["sql/queries/*.sql"]

[[sql.gen]]
backend = "python-psycopg3"
output = "lib/db/lib_db/generated"
```

- [ ] **Step 3: Delete the migration and the old dump snapshot**

```bash
git rm sql/migrations/20260521192052_create_core_schema.sql sql/schema.scythe.sql
rmdir sql/migrations 2>/dev/null || true
```

Expected: the two files are staged for deletion; `sql/migrations/` is gone if empty.

- [ ] **Step 4: Sanity-check the schema parses and applies (pgschema)**

Ensure local Postgres is running, then verify the declarative file applies to a blank schema and is idempotent:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
export PGPASSWORD=vibecheck PGHOST=127.0.0.1 PGUSER=vibecheck PGDATABASE=vibecheck
psql -v ON_ERROR_STOP=1 -q -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
pgschema apply --host 127.0.0.1 --user vibecheck --db vibecheck --schema public --file sql/schema.sql --auto-approve
pgschema plan  --host 127.0.0.1 --user vibecheck --db vibecheck --schema public --file sql/schema.sql
```

Expected: apply succeeds ("Changes applied successfully!"); plan prints **"No changes detected."**

- [ ] **Step 5: Commit**

```bash
git add sql/schema.sql scythe.toml
git commit -m "feat(db): add declarative schema (sql/schema.sql), drop dbmate migration"
```

---

### Task 2: Collapse the codegen pipeline (no DB, no dbmate)

**Files:**
- Modify: `scripts/codegen.sh`

- [ ] **Step 1: Rewrite `scripts/codegen.sh`**

Replace the entire file with the version below. Scythe reads `sql/schema.sql` statically, so the Postgres preflight, `dbmate up`, `dbmate dump`, and the `\`-strip step are all removed. Scythe 0.8.0 emits `import uuid` / `from typing import Any` natively, so the post-generate import-patch (former gotcha #2) is gone too; a version preflight guard replaces it so an older local install fails fast instead of regenerating incompatible code. The package-marker `touch` is retained.

```bash
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
```

- [ ] **Step 2: Run codegen and verify the generated code is unchanged**

```bash
./scripts/codegen.sh
git diff --exit-code lib/db/lib_db/generated/
```

Expected: "Codegen complete -> lib/db/lib_db/generated/queries.py" and `git diff --exit-code` returns **exit 0** (no changes — the spike proved byte-identical output). If the diff is non-empty, STOP and investigate before continuing.

- [ ] **Step 3: Confirm the generated code still imports and exposes all 6 functions**

```bash
uv run python -c "from lib_db import queries; print(sorted(n for n in dir(queries) if not n.startswith('_')))"
```

Expected: includes `create_post`, `create_mention`, `create_analysis_result`, `get_sentiment_by_tool_bucket`, `get_posts_by_tool_and_range`, `list_tools`.

> If this fails because `lib-db` isn't installed, run `uv sync --all-packages --all-groups` first, then retry.

- [ ] **Step 4: Confirm ruff and mypy still pass**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
```

Expected: all pass (the generated dir exclusions in `pyproject.toml` are unchanged).

- [ ] **Step 5: Commit**

```bash
git add scripts/codegen.sh
git commit -m "feat(db): collapse codegen to DB-free scythe generate (no dbmate/dump)"
```

---

### Task 3: Add the pgschema apply helper

**Files:**
- Create: `scripts/pg-env.sh`
- Create: `scripts/db-apply.sh`

- [ ] **Step 1a: Write `scripts/pg-env.sh`**

The `PG*` derivation lives in its own sourced helper so the repo keeps one DSN source and any tool that needs discrete `PG*` vars (not just `db-apply.sh`) can reuse it. Values are shell-quoted and percent-decoded so metacharacters in a password/host can't break the `eval`.

```bash
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
```

- [ ] **Step 1b: Write `scripts/db-apply.sh`**

Create the file below. It sources `scripts/pg-env.sh` to derive `PG*` connection env vars from `DATABASE_URL`, then applies. Extra args pass through to `pgschema apply` (e.g. `--auto-approve` in CI).

```bash
#!/usr/bin/env bash
# Reconcile the target database to the declarative schema (sql/schema.sql).
# pgschema takes discrete PG* connection vars, not a URL — derive them from
# DATABASE_URL (via scripts/pg-env.sh) so the repo keeps one DSN source.
# Extra args pass through to `pgschema apply` (e.g. --auto-approve, --lock-timeout 30s).
set -euo pipefail

cd "$(dirname "$0")/.."

eval "$(./scripts/pg-env.sh)"

pgschema apply --schema public --file sql/schema.sql "$@"
```

- [ ] **Step 2: Make them executable**

```bash
chmod +x scripts/pg-env.sh scripts/db-apply.sh
```

- [ ] **Step 3: Verify it reconciles a blank DB and is idempotent**

```bash
export PGPASSWORD=vibecheck PGHOST=127.0.0.1 PGUSER=vibecheck PGDATABASE=vibecheck
psql -v ON_ERROR_STOP=1 -q -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE PGSSLMODE  # prove the script derives them from DATABASE_URL
DATABASE_URL="postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable" ./scripts/db-apply.sh --auto-approve
DATABASE_URL="postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable" ./scripts/db-apply.sh --auto-approve
```

Expected: first run applies the schema; second run reports no changes ("Changes applied successfully!" with an empty/no-op plan, or "No changes detected").

- [ ] **Step 4: Commit**

```bash
git add scripts/db-apply.sh
git commit -m "feat(db): add pgschema apply helper (DATABASE_URL -> PG* derivation)"
```

---

### Task 4: Rewire CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace the dbmate install step with a pgschema install step**

In `.github/workflows/ci.yml`, replace the entire `Install dbmate` step (lines ~79–85) with:

```yaml
      - name: Install pgschema
        run: |
          set -euo pipefail
          sudo curl -fsSL -o /usr/local/bin/pgschema \
            https://github.com/pgplex/pgschema/releases/download/v1.10.0/pgschema-1.10.0-linux-amd64
          sudo chmod +x /usr/local/bin/pgschema
          pgschema --help >/dev/null && echo "pgschema installed"
```

> `pgschema` has no `--version` subcommand; `--help` prints the version banner and exits 0.

- [ ] **Step 2: Replace the migration-safety step with a plan-lint step**

Replace the `Squawk (migration safety)` step (lines ~105–106) with the step below. It applies the schema to the blank service DB, captures the plan SQL, and lints it with squawk. (On a fresh CI DB the plan is the full schema creation; squawk still flags any unsafe patterns in the generated DDL. Full incremental-safety value requires planning against a representative baseline, which CI-from-blank does not have — documented in the spec.)

```yaml
      - name: Apply schema (pgschema)
        run: DATABASE_URL="$DATABASE_URL" ./scripts/db-apply.sh --auto-approve

      - name: Squawk (plan safety)
        run: |
          set -euo pipefail
          export PGPASSWORD=vibecheck PGHOST=localhost PGPORT=5432 PGUSER=vibecheck PGDATABASE=vibecheck
          pgschema plan --schema public --file sql/schema.sql --output-sql /tmp/plan.sql
          if [ -s /tmp/plan.sql ]; then
            squawk /tmp/plan.sql
          else
            echo "Empty plan (DB already matches schema) — nothing to lint."
          fi
```

> Note: after `Apply schema`, the DB matches `sql/schema.sql`, so the plan in `Squawk (plan safety)` is empty — which proves idempotency. To lint a *non-empty* plan you would point `pgschema plan` at a baseline DB holding the previous schema; that is out of scope for greenfield CI. Keeping the step makes the gate present and ready; the spec records the limitation.

- [ ] **Step 3: Update the codegen freshness gate**

Replace the `Codegen freshness` step (lines ~108–111) with the version below — it no longer diffs `sql/schema.scythe.sql` (deleted) and no longer needs a DB:

```yaml
      - name: Codegen freshness
        run: |
          ./scripts/codegen.sh
          git diff --exit-code lib/db/lib_db/generated/
```

- [ ] **Step 4: Verify the `Seed tools` and `Pytest` steps are correctly ordered**

The `Seed tools` (psql) and `Pytest` steps (lines ~116–120) are unchanged, but they now depend on the new `Apply schema (pgschema)` step having created the tables (previously `dbmate up` inside `codegen.sh` did this). Confirm the step order in the final file is:

```text
Install pgschema → Install squawk → Install psql client → Ruff check → Ruff format
→ Scythe lint → Scythe fmt check → Apply schema (pgschema) → Squawk (plan safety)
→ Codegen freshness → Mypy → Seed tools → Pytest
```

- [ ] **Step 5: Sanity-check the YAML locally**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```

Expected: "YAML OK". Also grep to confirm no dbmate/migration references remain:

```bash
! grep -niE 'dbmate|sql/migrations|schema\.scythe' .github/workflows/ci.yml && echo "no stale refs"
```

Expected: "no stale refs".

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: replace dbmate with pgschema apply + plan-lint; fix freshness gate"
```

---

### Task 5: Update the design spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-20-phase1-schema-data-layer-design.md`

- [ ] **Step 1: Rewrite the "Migrations" section**

Replace the `## Migrations — dbmate + squawk` section (around line 142) with a `## Schema management — pgschema (declarative)` section stating:
- Source of truth is `sql/schema.sql` (desired state); pgschema reconciles a DB to it via `plan` → `apply` (`scripts/db-apply.sh`). No migration files, no `schema_migrations` table.
- **Why pgschema over dbmate:** Scythe needs only a flat DDL file, not a database; declarative makes that file the authored artifact, removing the `dbmate up`/`dump`/`\`-strip steps and the pg18 `\restrict` parser crash (former gotcha #1).
- **Atlas note:** keep/adjust the existing note — declarative alignment with Scythe was always desirable; pgschema delivers it free (vs Atlas Pro), which is why dbmate's rejection reason no longer holds.
- **Migration safety:** squawk lints the `pgschema plan` SQL output in CI (replaces linting migration files). Note the CI-from-blank limitation.
- **Rollback:** revert `sql/schema.sql` and re-apply; pgschema computes the reverse diff (acceptable for greenfield; data-loss diffs are gated by `plan` review).

- [ ] **Step 2: Rewrite the "Codegen pipeline" section**

Update `## Codegen pipeline — Scythe (pinned 0.8.0)` (around line 151):
- Change the pipeline diagram to: `edit sql/schema.sql → scythe generate → patch imports` (2 steps, no DB).
- Update `scythe.toml` references from `schema = ["sql/schema.scythe.sql"]` to `schema = ["sql/schema.sql"]`.
- Remove the "Strip psql meta-commands" sub-section (no longer applicable; pgschema/authored SQL has no `\restrict`).
- Keep the import-patch (gotcha #2) and jsonb-dumper (gotcha #3) notes — still required.

- [ ] **Step 3: Update the workflow/CI table**

In the table around lines 217–220:
- `pre-commit`: unchanged.
- `CI — codegen freshness gate`: `./scripts/codegen.sh` then `git diff --exit-code lib/db/lib_db/generated/` (drop `sql/schema.scythe.sql`).
- Replace `CI — migration safety` row: `squawk` lints `pgschema plan --output-sql` output; note the CI-from-blank caveat.
- Add a `CI — schema apply` row: `scripts/db-apply.sh --auto-approve` creates the schema before seed/pytest (replaces `dbmate up`).
- `seed` row: `psql -f sql/seeds/tools.sql` after `pgschema apply` (was "after `dbmate up`").

- [ ] **Step 4: Update the verification/summary line**

Update the closing verification line (around line 299) to: `edit sql/schema.sql → scythe generate (python-psycopg3) → patch imports → psycopg3 round-trip; pgschema apply + idempotent plan verified`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-20-phase1-schema-data-layer-design.md
git commit -m "docs: rewrite Phase 1 design for pgschema declarative schema"
```

---

### Task 6: Full local verification

**Files:** none (verification only)

- [ ] **Step 1: Clean end-to-end run from a blank database**

```bash
export PGPASSWORD=vibecheck PGHOST=127.0.0.1 PGUSER=vibecheck PGDATABASE=vibecheck
psql -v ON_ERROR_STOP=1 -q -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE PGSSLMODE
export DATABASE_URL="postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable"

./scripts/db-apply.sh --auto-approve          # create schema
psql "$DATABASE_URL" -f sql/seeds/tools.sql    # seed
./scripts/codegen.sh                           # regenerate (DB-free)
git diff --exit-code lib/db/lib_db/generated/  # must be clean
uv run ruff check . && uv run ruff format --check . && uv run mypy .
uv run pytest
```

Expected: schema applies; 9 tools seeded; codegen diff empty; ruff/mypy clean; pytest passes (`test_data_layer_roundtrip`).

- [ ] **Step 2: Confirm no dbmate/migration residue anywhere**

```bash
grep -rniE 'dbmate|sql/migrations|schema\.scythe' \
  --include='*.yml' --include='*.toml' --include='*.sh' --include='*.md' . \
  | grep -v docs/superpowers/plans/2026-05-31-phase1-pgschema-migration.md \
  | grep -v docs/superpowers/plans/2026-05-21-phase1-schema-data-layer.md \
  || echo "no residue"
```

Expected: "no residue" (the two plan docs are allowed to mention the old terms historically).

---

### Task 7: Rewrite branch history (pgschema-native) and push

**Files:** none (git history only)

> This squashes the 12 dbmate-era commits + the Task 1–6 commits into a clean pgschema-native sequence using `git reset --soft` (interactive rebase is unavailable in this environment). All working-tree content is preserved; only commit history changes.

- [ ] **Step 1: Safety checkpoint — confirm working tree is clean and tests pass**

```bash
git status --short        # expect empty (all Task 1–6 work committed)
git log --oneline main..HEAD
```

Expected: no uncommitted changes; the log shows the dbmate-era commits plus the Task 1–6 commits.

- [ ] **Step 2: Back up the current branch tip**

```bash
git branch backup/phase-1-dbmate-pre-pgschema
```

This preserves the full pre-rewrite history locally in case the rewrite needs to be undone (`git reset --hard backup/phase-1-dbmate-pre-pgschema`).

- [ ] **Step 3: Soft-reset to main, keeping all files staged**

```bash
git reset --soft main
git restore --staged .
git status --short
```

Expected: every Phase 1 file shows as a change (untracked/modified) but nothing is committed — `HEAD` is now at `main` with the full final state in the working tree.

- [ ] **Step 4: Re-commit as a clean pgschema-native sequence**

```bash
# 1) Design spec
git add docs/superpowers/specs/2026-05-20-phase1-schema-data-layer-design.md
git commit -m "docs: Phase 1 schema & data layer design (pgschema declarative)"

# 2) This implementation plan
git add docs/superpowers/plans/2026-05-31-phase1-pgschema-migration.md
git commit -m "docs: Phase 1 pgschema migration plan"

# 3) Declarative schema + tools seed
git add sql/schema.sql sql/seeds/tools.sql
git commit -m "feat(db): add declarative schema and idempotent tools seed"

# 4) Query files + scythe config
git add sql/queries/ scythe.toml
git commit -m "feat(db): add scythe query files and scythe.toml"

# 5) Codegen + generated code + apply helper
git add scripts/codegen.sh scripts/db-apply.sh lib/db/lib_db/generated/
git commit -m "feat(db): add DB-free codegen, pgschema apply helper, generated queries"

# 6) Pool layer + public API + package deps
git add lib/db/lib_db/pool.py lib/db/lib_db/__init__.py lib/db/pyproject.toml pyproject.toml uv.lock
git commit -m "feat(db): add async pool factory with jsonb dumper and re-export queries"

# 7) Smoke test
git add tests/
git commit -m "test(db): add end-to-end data-layer smoke test"

# 8) Pre-commit + CI
git add .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "ci: lint/type/codegen-freshness gates + pgschema apply and plan-lint"
```

- [ ] **Step 5: Verify nothing was lost in the rewrite**

```bash
git diff backup/phase-1-dbmate-pre-pgschema HEAD --stat
```

Expected: the diff is **only** the dbmate→pgschema delta (deleted migration + `schema.scythe.sql`, changed `codegen.sh`/`scythe.toml`/`ci.yml`/spec, added `schema.sql`/`db-apply.sh`/this plan). No unexpected file content differences in `lib/db`, queries, seed, or tests. Also re-run the Task 6 Step 1 verification once more to be safe.

- [ ] **Step 6: Force-push the rewritten branch**

```bash
git push --force-with-lease origin phase-1-schema-data-layer
```

`--force-with-lease` refuses to overwrite if someone else pushed in the meantime. Expected: push succeeds.

- [ ] **Step 7: Clean up the backup branch (optional)**

Once CI is green on the pushed branch, the local backup can be removed:

```bash
git branch -D backup/phase-1-dbmate-pre-pgschema
```

> The original dbmate exploration also remains recoverable from the reflog and from any earlier remote state until GC.

---

## Self-review (completed by plan author)

**Spec coverage** (against the assessment decisions):
- Declarative source of truth `sql/schema.sql` feeding both pgschema and Scythe → Task 1. ✓
- DB-free codegen collapse, gotcha #1 removed, gotchas #2/#3 retained → Task 2. ✓
- pgschema apply helper with DATABASE_URL→PG* derivation → Task 3. ✓
- CI: pgschema install, apply step (replaces `dbmate up`), squawk-on-plan (the chosen migration-safety approach), freshness gate fix → Task 4. ✓
- Design spec rewritten for pgschema → Task 5. ✓
- Full local verification from a blank DB → Task 6. ✓
- History rewrite to pgschema-native + force-push (the chosen branch strategy) → Task 7. ✓

**Placeholder scan:** no TBD/TODO; every code/edit step shows concrete content or exact commands. The spec rewrite (Task 5) describes precise section replacements rather than verbatim prose, since it edits an existing 307-line document — acceptable as targeted edits, not placeholders.

**Type/name consistency:** `sql/schema.sql`, `scripts/db-apply.sh`, `scripts/codegen.sh`, env var names (`PGHOST` etc.), and the generated function names (`create_post`, `create_mention`, `create_analysis_result`, `get_sentiment_by_tool_bucket`, `get_posts_by_tool_and_range`, `list_tools`) are used consistently across tasks.

**Known caveat carried into the spec:** squawk-on-plan in CI-from-blank lints only the full-create DDL; incremental-change safety requires a baseline DB. Documented in Task 4 Step 2 and Task 5 Step 1.
