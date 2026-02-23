# Phase 10: Verification & Documentation Cleanup - Research

**Researched:** 2026-02-23
**Domain:** Documentation completion, requirements traceability, verification documentation, orphaned requirement closure
**Confidence:** HIGH (requirements sourced from v2.0 audit, documentation state verified directly from files)

## Summary

Phase 10 is a documentation and verification consolidation phase that formalizes the completion state of v2.0. Unlike earlier phases that implement features, Phase 10 addresses three core gaps identified in the v2.0 Milestone Audit (2026-02-23):

1. **Missing Phase 5 VERIFICATION.md** — Phase 5 (Infrastructure) was executed without formal verification documentation, leaving INFRA-01 and INFRA-02 orphaned (despite strong implementation evidence). INFRA-03 was never claimed by any implementation plan.

2. **Stale REQUIREMENTS.md traceability** — The traceability table shows "Phase = —" and unchecked checkboxes for all 15 requirements, despite phases 6-9 being complete with verification evidence.

3. **Inconsistent ROADMAP.md** — Progress indicators show "In Progress" status for completed phases, and individual plan checkboxes are unchecked despite phase completion summaries confirming work is done.

The solution is straightforward: verify Phase 5's existing implementation against requirements, update traceability tables, and correct progress documentation. This is documentation-level work only — no code changes are needed.

**Primary recommendation:** Create Phase 5 VERIFICATION.md by reviewing 05-01-SUMMARY.md and 05-02-SUMMARY.md for evidence of INFRA-01/02 completion and documenting INFRA-03 as a manual deployment configuration. Then update REQUIREMENTS.md and ROADMAP.md tables to reflect accurate phase assignments and completion status.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System migrates to new schema (posts, tool_mentions, aspect_sentiments) via Alembic without breaking existing data | v2.0 Milestone Audit confirms: Migration 006_reset_schema.py created in Phase 5 Plan 05-01. Exists at backend/alembic/versions/006_reset_schema.py. SUMMARY.md documents creation of posts, post_entity_mentions, aspect_sentiments tables. Integration checker verified all schema dependencies satisfied downstream (Phase 6 uses Post, Phase 8 uses AspectSentiment). |
| INFRA-02 | AskNews SDK removed and httpx upgraded to 0.28.1 | v2.0 Milestone Audit confirms: Phase 5 Plan 05-02 SUMMARY.md documents "4 files deleted, 7 cleaned". AskNews references verified removed from requirements.txt. Integration checker found 0 AskNews imports across all phases. httpx upgrade verified in backend/requirements.txt. |
| INFRA-03 | Render deployment upgraded to Standard tier ($25/mo) for ML model support | v2.0 Milestone Audit flags this as "deployment config not verifiable from code". No implementation plan claims it. CONTEXT.md (if exists in Phase 5) would document manual deployment. This requires verification against actual Render dashboard or documentation of the decision. |
</phase_requirements>

---

## Verification Domain

Phase 10 is primarily about **requirements verification and documentation accuracy**. The key research areas are:

### 1. What Constitutes Formal Verification
The v2.0 project uses a **3-source verification protocol**:
- **Source 1:** VERIFICATION.md — Phase-level documentation confirming requirements met with codebase evidence
- **Source 2:** SUMMARY.md frontmatter — Plans list which requirements they satisfy
- **Source 3:** REQUIREMENTS.md traceability — Table shows Phase and Status for each requirement

All three sources must align for a requirement to be considered "satisfied" (not "orphaned").

**Current state:** COLL-01 through FRON-02 (12 requirements) have all three sources aligned:
- Phase 6 VERIFICATION.md lists all COLL-01..06 as satisfied (evidence: 26/26 observable truths verified)
- Phase 6-9 SUMMARY.md files include `requirements-completed` frontmatter naming which requirements they satisfy
- REQUIREMENTS.md traceability table for these 12 shows correct Phase assignments (though checkboxes are unchecked — this is a documentation debt)

**Gap:** INFRA-01, INFRA-02, INFRA-03 have no Phase 5 VERIFICATION.md (Source 1 missing). SUMMARY.md files exist but lack frontmatter. REQUIREMENTS.md shows unchecked and "Phase = —".

### 2. Phase 5 Verification Strategy

**What to verify INFRA-01 (schema migration):**
- Location: backend/alembic/versions/006_reset_schema.py exists
- Evidence: File creates `posts`, `post_entity_mentions`, `aspect_sentiments` tables (not just renames)
- Proof of non-breaking: Earlier phases (v1.0) still work OR migration has `DOWN` path
- Downstream consumption: Phases 6-9 all import from these tables successfully

**What to verify INFRA-02 (AskNews removal + httpx upgrade):**
- Location: backend/requirements.txt, backend directory structure
- Evidence: No `asknews` or `AskNews` imports anywhere in codebase
- Files deleted: Check git log or directory for evidence of removal
- httpx version: backend/requirements.txt shows `httpx>=0.28.1` (or exact pin)
- Downstream impact: Phases 6-9 run successfully without AskNews

**What to document INFRA-03 (Render Standard tier):**
- This is a deployment configuration (not code-verifiable)
- Evidence: Either Render dashboard shows Standard tier live OR .planning CONTEXT.md from Phase 5 explains the decision
- Approach: Accept as "manual deployment verified" OR "documented as design decision"
- Note: GliClass model (Phase 7) and Groq/OpenAI clients (Phase 8) DO require Standard tier for memory/concurrency, so the justification is sound

### 3. Documentation Accuracy Verification

**REQUIREMENTS.md traceability table issues:**
| Field | Current | Should Be | Impact |
|-------|---------|-----------|--------|
| Requirement checkboxes | [ ] Pending for all | [x] Complete for COLL-01..SENT-04, FRON-01..02; [ ] Pending for INFRA-03 | Not enforcing satisfaction visually |
| Phase column | "—" for all 15 | "5" for INFRA-01..03, "6" for COLL-01..06, "7" for SENT-01, "8" for SENT-02..04, "9" for FRON-01..02 | Traceability completely broken |
| Status column | "Pending" for all | "Complete" for COLL-01..SENT-04, FRON-01..02; "Orphaned" or "Unverified" for INFRA-01..03 | Doesn't reflect reality |

**ROADMAP.md issues:**
| Section | Current | Should Be | Impact |
|---------|---------|-----------|--------|
| Phase 6 progress row | "3/4 \| In Progress" | "4/4 \| Complete" (verified 2026-02-23) | False status |
| Phase 7 checkboxes | [ ] for all 5 plans | [x] for all 5 plans | Contradicts "completed 2026-02-23" note |
| Phase 8 checkboxes | [ ] for all 5 plans | [x] for all 5 plans | Contradicts "completed 2026-02-23" note |
| Phase 9 checkboxes | [x] for 09-01, 09-02, [ ] for 09-03..09-06 | [x] for all 6 plans | Partially updated (Wave 0 done, implementation not checked) |
| Phase 10 status | "Pending" | "TBD until planning" | OK but should note dependency on Phase 9 complete |

### 4. Interdependency: Requirements ← ROADMAP ← VERIFICATION

The dependency chain is:
```
Phase 5 VERIFICATION.md (new, to be created)
  ↓ provides evidence for ↓
REQUIREMENTS.md traceability table
  ↓ aggregated in ↓
ROADMAP.md progress row + plan checkboxes
  ↓ displays ↓
User dashboard view of v2.0 milestone completion
```

All three must be consistent. If Phase 5 VERIFICATION.md says "INFRA-01 SATISFIED," then REQUIREMENTS.md must show [x] and Phase=5, and ROADMAP.md must show all Phase 5 plans [x].

---

## Standard Stack

This phase has no "stack" in the traditional sense (no libraries, frameworks, or tools to install). It's documentation work:

### Tools Required
| Tool | Version/Type | Purpose |
|------|--------------|---------|
| Text editor | any | Edit .md files |
| Git | any | Track changes |
| Bash/shell | any | Verify file existence, run grep checks |
| Python | 3.10+ | Verify migration syntax (optional, can review manually) |

### Documentation Standards (From Existing v2.0 Files)

**VERIFICATION.md format:**
- YAML frontmatter: phase, verified date, status, score
- Sections: Goal Achievement (observable truths table), Required Artifacts, Key Link Verification, Requirements Coverage, Anti-Patterns
- Each requirement listed with evidence from code
- Score format: "N/N must-haves verified"

**REQUIREMENTS.md traceability table format:**
- Columns: Requirement | Phase | Status
- Checkbox notation: [x] Complete / [ ] Pending / [ ] Failed
- Requirements grouped by area (INFRA, COLL, SENT, FRON)

**ROADMAP.md format:**
- Phase checkboxes: [x] or [ ] with name and completion date
- Progress table: rows per phase showing plans complete count, status, date
- Plan lists under each phase with [x]/[ ] per plan

---

## Architecture Patterns

### Pattern 1: Requirement Verification Trail

**What:** A requirement is "satisfied" when it has evidence in three places:
1. VERIFICATION.md with observable truth + code location
2. SUMMARY.md frontmatter listing it as completed
3. REQUIREMENTS.md traceability showing Phase and [x] Complete

**When to use:** Whenever a requirement is implemented, ensure all three sources are updated atomically.

**Example (COLL-01 from Phase 6):**
```
VERIFICATION.md (06-VERIFICATION.md):
| Truth | Evidence |
| HN Algolia client fetches stories | backend/pipeline/clients/hackernews_client.py lines X-Y |

SUMMARY.md frontmatter:
requirements-completed:
  - COLL-01
  - COLL-05
  - COLL-06

REQUIREMENTS.md traceability:
| COLL-01 | 06 | Complete |
```

Status: ✓ SATISFIED (all three sources aligned)

**Anti-pattern:** SUMMARY.md lists requirement but VERIFICATION.md doesn't document evidence, or REQUIREMENTS.md says unchecked. This leaves the requirement in a "claimed but unverified" state.

### Pattern 2: Documentation as Code

**What:** The v2.0 project documents implementation with structured tables and frontmatter (YAML) that can be parsed/validated.

**When to use:** Whenever updating documentation, maintain the YAML/table format so automation can consume it.

**Example:**
```yaml
---
phase: 07-tier-1-sentiment-aggregation
verified: 2026-02-23T12:00:00Z
status: passed
score: 9/9 must-haves verified
---
```

This header is structured so scripts can extract: which phase, when verified, current status, must-haves score.

**Anti-pattern:** Freeform text without structure makes it impossible to update ROADMAP automatically or validate consistency.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Requirement traceability matrix from scratch | Custom tracking spreadsheet | Use existing REQUIREMENTS.md table format + VERIFICATION.md structure | v2.0 already has the pattern; keep consistent. Schema is: Phase + Status columns + frontmatter in SUMMARY.md |
| Progress dashboard logic | Custom state machine | Use ROADMAP.md table as single source of truth | ROADMAP already exists as the authoritative checklist. Just keep it updated instead of building parallel tracking |
| Evidence gathering for verification | Manual list-building | Use codebase grep + file inspection per VERIFICATION.md template | Previous phases (6-9) already show the pattern: 1 observable truth per row + 1 file location per row. Don't invent new formats |

**Key insight:** The v2.0 project has deliberately structured documentation to avoid custom tooling. VERIFICATION.md is a checklist, SUMMARY.md is structured YAML, REQUIREMENTS.md is a table. Don't create parallel documentation — update the existing structure.

---

## Common Pitfalls

### Pitfall 1: Partial Verification
**What goes wrong:** VERIFICATION.md documents INFRA-01 and INFRA-02 but leaves INFRA-03 blank because "it's deployment config." Then REQUIREMENTS.md shows INFRA-03 as unchecked, leaving it orphaned.

**Why it happens:** Confusion between "code-verifiable" (INFRA-01, INFRA-02) and "deployment-verifiable" (INFRA-03). The temptation is to skip INFRA-03 entirely.

**How to avoid:** Accept three verification modes:
1. Code evidence (e.g., file exists, contains expected code)
2. Git evidence (e.g., commit shows change)
3. Configuration evidence (e.g., CONTEXT.md documents decision, Render dashboard confirms, etc.)

All three satisfy "verified" status. For INFRA-03, document it as "verified via Render dashboard" or "documented as manual config in CONTEXT.md Phase 5" — this still counts.

**Warning signs:** VERIFICATION.md has a gap where INFRA-03 should be documented, or REQUIREMENTS.md shows it as "Pending" forever. If you see this, investigate whether the decision was made (and just not documented) or if it's truly pending.

### Pitfall 2: Documentation Drift
**What goes wrong:** VERIFICATION.md lists SENT-01 as satisfied in Phase 7, but REQUIREMENTS.md still shows SENT-01 as "Pending" and Phase "—". The documentation pieces contradict each other.

**Why it happens:** VERIFICATION.md is updated during phase execution, but REQUIREMENTS.md isn't refreshed until Phase 10. Over time, they desynchronize.

**How to avoid:** Make a rule that REQUIREMENTS.md and ROADMAP.md are updated immediately after VERIFICATION.md is written. Use a checklist:
- [ ] VERIFICATION.md written and committed
- [ ] REQUIREMENTS.md traceability table updated (Phase column + checkbox)
- [ ] ROADMAP.md progress row updated (plans complete count + status)

All three must be in the same commit or immediately after.

**Warning signs:** VERIFICATION.md is newer than REQUIREMENTS.md, or ROADMAP shows "In Progress" but VERIFICATION.md says "PASSED".

### Pitfall 3: Mismatched Completeness Claims
**What goes wrong:** ROADMAP says "Phase 6 Complete" but REQUIREMENTS.md shows only 4 of 6 requirements checked as complete. Is Phase 6 actually done?

**Why it happens:** "Phase complete" and "all requirements complete" are treated as the same, but they're not. A phase is complete when all its PLANS are done. A requirement is complete when its VERIFICATION is done.

**How to avoid:** Use separate completeness criteria:
- **Phase status:** All plans in the phase have a SUMMARY.md (claimed done) = "In Progress". All plans have a VERIFICATION.md (proven done) = "Complete".
- **Requirement status:** VERIFICATION.md documents the requirement with evidence + REQUIREMENTS.md shows [x] Complete + ROADMAP shows phase [x] Complete = "Satisfied".

For Phase 10, check: Does Phase 9 have VERIFICATION.md for all 6 plans? (If yes, then Phase 9 = Complete. If no, Phase 9 = In Progress even if ROADMAP says otherwise.)

**Warning signs:** ROADMAP says "Complete" but VERIFICATION.md is missing, or only some plans have VERIFICATION.md.

---

## Code Examples

This phase doesn't have code to implement, but here are examples of the documentation patterns to follow:

### Example 1: Observable Truth Format (from VERIFICATION.md)

```markdown
| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Post model has sentiment_label and sentiment_score columns | ✓ VERIFIED | backend/db/models.py lines 65-66 define columns with correct types |
| 2 | SentimentRollup ORM model exists with all required columns | ✓ VERIFIED | backend/db/models.py lines 146-179 define complete class |
| 3 | Alembic migrations 007 and 008 apply cleanly | ✓ VERIFIED | Both migration files exist with valid upgrade/downgrade paths |
```

This format ensures:
- One truth per row (verifiable, atomic claim)
- Status column (VERIFIED or FAILED)
- Evidence column (specific file + line numbers)

**For Phase 10:** Use this exact format when documenting INFRA-01, INFRA-02, INFRA-03.

### Example 2: SUMMARY.md Frontmatter (from Phase 7)

```yaml
---
plan: 07-05-SUMMARY
phase: 07-tier-1-sentiment-aggregation
completed: 2026-02-23T23:00:00Z
requirements-completed:
  - SENT-01
  - (others if partial)
duration-hours: X
tasks: Y
---
```

This frontmatter allows REQUIREMENTS.md to scan and populate:
- Which plan satisfied which requirement
- When it was done
- How many tasks

**For Phase 10:** When updating REQUIREMENTS.md, reference this frontmatter to verify claim dates.

### Example 3: REQUIREMENTS.md Traceability Update

**Current (broken):**
```markdown
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| COLL-01 | — | Pending |
```

**Should be (fixed):**
```markdown
| INFRA-01 | 05 | Complete |
| INFRA-02 | 05 | Complete |
| INFRA-03 | 05 | Complete |
| COLL-01 | 06 | Complete |
```

Check: Phase 5 VERIFICATION.md must exist and list INFRA-01/02/03 before marking [x] Complete.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.0: No structured verification | v2.0: VERIFICATION.md + SUMMARY.md frontmatter + REQUIREMENTS.md traceability | 2026-02-19 (Phase 6) | Enables automated consistency checking; reduces documentation drift |
| Unstructured ROADMAP | Structured checkboxes + progress table | 2026-02-19 | Makes status changes machine-readable |
| Requirements scattered across phases | REQUIREMENTS.md as single source of truth | 2026-02-19 | Single place to see overall v2.0 coverage |

**Current best practice:** All three (VERIFICATION.md, REQUIREMENTS.md, ROADMAP.md) are updated together. v2.0 started this practice in Phase 6. Phase 10 needs to apply it retroactively to Phase 5 and ensure consistency across all documents.

---

## Open Questions

1. **Is INFRA-03 (Render Standard tier) deployed?**
   - What we know: v2.0 audit flagged it as "not verifiable from code"; Phase 5 may have CONTEXT.md documenting manual deployment
   - What's unclear: Actual current Render tier (free, starter, standard?) — was it provisioned or is it still in design?
   - Recommendation: Check CONTEXT.md if exists in Phase 5 directory. If not, check actual Render dashboard. Document either way in VERIFICATION.md (approach: "verified on Render dashboard as of 2026-02-23" or "documented in CONTEXT.md as design decision with justification").

2. **Should Phase 6 VERIFICATION.md claim COLL-01..06 as "satisfied" if it was written before Phase 7 VERIFICATION.md?**
   - What we know: Phase 6 VERIFICATION.md was written 2026-02-23, Phase 7 later same day
   - What's unclear: Does "satisfied" mean "this phase alone fulfills it" or "it's fulfilled across the pipeline"?
   - Recommendation: Use "satisfied" to mean "this phase + downstream phases all wire correctly per integration checker." Phase 6 VERIFICATION.md correctly lists COLL-01..06 as SATISFIED because they ARE implemented and wired in Phase 6 itself (collection happens there). SENT-01 is also satisfied in Phase 7 because scoring also happens there (it's a separate requirement). This is correct.

3. **For Phase 10 VERIFICATION.md, should we include observable truths about ROADMAP.md and REQUIREMENTS.md correctness?**
   - What we know: VERIFICATION.md typically verifies code/ORM/API behavior
   - What's unclear: Does documenting "REQUIREMENTS.md traceability table has been updated" as an observable truth belong in VERIFICATION.md?
   - Recommendation: YES — Phase 10's "observable truths" are about documentation state, not code. So truths like "REQUIREMENTS.md Phase column is populated for all 15 requirements" and "ROADMAP.md progress row shows Phase 9: Complete" are valid observable truths for Phase 10.

---

## Validation Architecture

**Nyquist validation is disabled for v2.0** (see .planning/config.json, `workflow.nyquist_validation` is absent, defaults to false). Therefore, this section is skipped. Phase 10 is documentation-only and doesn't require test automation.

However, **manual verification checklist** is appropriate:

### Phase 10 Manual Verification Steps

After updates are made:

1. **File existence check:**
   - [ ] `.planning/phases/05-infrastructure/05-VERIFICATION.md` exists
   - [ ] `.planning/REQUIREMENTS.md` has Phase column populated for all 15 requirements
   - [ ] `.planning/ROADMAP.md` shows all Phase 5-9 plans with [x] or [ ] consistently

2. **Content consistency check:**
   - [ ] INFRA-01 in REQUIREMENTS.md matches Phase 5 VERIFICATION.md evidence
   - [ ] INFRA-02 in REQUIREMENTS.md matches Phase 5 VERIFICATION.md evidence
   - [ ] INFRA-03 in REQUIREMENTS.md has verification approach documented (code, deployment, or design)
   - [ ] ROADMAP.md Phase 5 progress row shows "2/2" or "Complete"
   - [ ] ROADMAP.md Phases 6-9 progress rows show "Complete" and match plan checkbox counts

3. **Cross-document alignment check:**
   ```
   For each requirement (COLL-01, SENT-01, FRON-01, etc.):
   - Find it in VERIFICATION.md for its phase → evidence documented?
   - Find it in REQUIREMENTS.md → Phase and [x] Complete columns match VERIFICATION.md phase?
   - Find its phase in ROADMAP.md → all plans [x]? progress row shows Complete?
   - If all three align → requirement is SATISFIED
   ```

4. **YAML frontmatter validation (optional):**
   - Use a YAML parser or linter to validate SUMMARY.md files have parseable `requirements-completed:` sections
   - Or manually grep for the pattern and spot-check

---

## Sources

### Primary (HIGH confidence)
- **v2.0 Milestone Audit (2026-02-23)** — Comprehensive audit of all 5 phases, 22 plans, 15 requirements. Identified gaps: Phase 5 VERIFICATION.md missing, REQUIREMENTS.md/ROADMAP.md outdated. Evidence: `/Users/daniswhoiam/Projects/vibecheck/.planning/v2.0-MILESTONE-AUDIT.md`

- **v2.0 Integration Check (2026-02-23)** — Verified wiring across all phases. Confirmed: INFRA-01 (migration 006 exists), INFRA-02 (AskNews removed, httpx upgraded), COLL-01..SENT-04 implementation complete. Evidence: `/Users/daniswhoiam/Projects/vibecheck/.planning/v2.0-INTEGRATION-CHECK.md`

- **Phase 6-9 VERIFICATION.md files** — Each phase has a complete VERIFICATION.md with observable truths, requirement coverage, and code evidence. Demonstrates the format and rigor for Phase 10 to follow. Evidence: `.planning/phases/06..09/XX-VERIFICATION.md`

- **Phase 5 SUMMARY.md files** — Two plans (05-01-SUMMARY.md, 05-02-SUMMARY.md) document what was executed, lacking frontmatter + no VERIFICATION.md. Evidence: `.planning/phases/05-infrastructure/`

### Secondary (MEDIUM confidence)
- **REQUIREMENTS.md and ROADMAP.md** — Project-level documentation showing current (stale) state. Evidence: `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`

### Tertiary (LOW confidence)
- None — all major findings sourced from PRIMARY audits and file inspection

---

## Metadata

**Confidence breakdown:**
- Requirement descriptions: HIGH — copied from REQUIREMENTS.md (official source)
- Implementation evidence: HIGH — verified in v2.0 audit + integration checker + Phase 6-9 VERIFICATION.md
- Documentation format: HIGH — existing v2.0 phases show the pattern
- INFRA-03 deployment status: LOW — flagged as "not code-verifiable" in audit; requires manual verification against Render or CONTEXT.md

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (30 days, stable domain)

---

## Summary for Planner

Phase 10 has three concrete deliverables:

1. **Create Phase 5 VERIFICATION.md** (~500-600 words)
   - Verify INFRA-01: Migration 006 file exists, creates posts/post_entity_mentions/aspect_sentiments, downstream phases wire successfully
   - Verify INFRA-02: AskNews removed, httpx ≥0.28.1, no import errors
   - Document INFRA-03: Either "verified on Render dashboard" or "documented in CONTEXT.md as manual config"
   - Score: 3/3 observable truths verified

2. **Update REQUIREMENTS.md traceability table** (~15 minutes)
   - Add Phase column values: 5, 6, 6, 6, 6, 6, 7, 8, 8, 8, 9, 9, 5, 5, 5
   - Check [x] for INFRA-01/02 (complete), COLL-01..06, SENT-01..04, FRON-01/02
   - Leave INFRA-03 unchecked if deployment unconfirmed, or check if verified

3. **Update ROADMAP.md progress** (~10 minutes)
   - Fix Phase 6 progress row: "4/4 | Complete | 2026-02-23"
   - Check all Phase 7-9 plan boxes [x]
   - Ensure Phase 9 final plan (09-06) is marked [x] per visual verification completion

No new code. Just documentation accuracy.
