# SanoSync — Phase 1 Exercise Library: Supabase migration preflight

Audit date: **2026-11-08**. Scope: Exercise Library Phase 1 metadata batches, substitute relationships and RLS for `training_exercise_preferences`. No production changes.

## Verification performed (read-only on existing Supabase project)

- Four migration batches contain **18 + 43 + 53 + 30 = 144 distinct curated source IDs**; 10 previously approved golden exercises complete the intended 154-item curated set.
- All **144** source IDs exist in the current live catalog, are active, and are not generator-approved. All source IDs named by the **33 proposed directional relationship pairs** exist as active catalog entries. Across classification rows and relationship endpoints there are **152 distinct source IDs**, all found.
- Substitutes are mirrored as intended, regressions and progressions remain directional. The four migrations propose **61 distinct directed relationship rows** (15 + 18 + 18 + 10). No self-pairs or duplicate direction/relationship keys in each INSERT.
- Existing `public.exercises.id` and linked foreign keys are UUID. `public.exercise_relationships.similarity_score` is nullable, with 0–1 check. The relationship type check permits `close_substitute`, `substitute`, `regression`, `progression`, `similar`.
- Proposed values for `movement_pattern`, `training_role`, fatigue, complexity and stability match the existing SQL enums. Metadata batches do not toggle `approved_for_generation=true`.
- Live catalog: **317 active exercises, 10 generator-approved, 0 relationships** before the proposed batches; preference table is not currently present.
- On existing `exercises` and `exercise_relationships` tables, RLS is enabled; authenticated users have SELECT but no INSERT/UPDATE on exercises, and `anon` cannot SELECT either table. Ownership RLS on the **new** preference table is verified statically only; its runtime behavior is NOT verified yet.

### Migration history drift: blocking

The live `supabase_migrations.schema_migrations` already contains original Exercise Library versions:
`20261107190642` (schema), `20261107190715` (seed), `20261107190911` (golden), `20261107191043` (indexes); workout logger versions also differ from the timestamps of equivalent-named repository files. Repository `main` uses `20261107191500`, `191600`, `191700`, `191800` for the corresponding Exercise Library files.

**Never run a blanket `supabase db push` against production until the exact migration contents and history are reconciled.** File-name similarity is insufficient proof of identical SQL. Do not mark old migrations applied blindly and do not modify the live history during testing.

## Artifacts added to PR #20

- `supabase/tests/exercise_library_phase1_staging_validation.sql`: SELECT-only checks to run after migrations on a disposable database. Asserts all 144 metadata rows match their intended values, 61 relationship rows, appropriate grants, schema RLS, four ownership policies and no inadvertent exercise approvals. Expected outcome: **every returned `passed` is true**.
- `supabase/tests/exercise_library_preference_rls_rollback.sql`: executable transaction-only, **staging-only** two-test-user RLS test. Confirms owner can insert/read; cross-user SELECT, INSERT, UPDATE and DELETE are denied; the transaction ends with `ROLLBACK`, removing all test users/preferences. Do not execute this on production.
- `backend/tests/test_exercise_library_release_preflight.py`: CI regression tests to keep the staging assertion queries synchronized with the four versioned curation batches, relationship types, enum checks and the preference RLS definition.

## How to run the isolated validation

**Precondition: authorization for branch compute billing and selected Supabase organization.** The Supabase API quoted **USD 0.01344 per hour** on 2026-11-08 for a branch in the organization's current project; no branch has been created or charged as part of this audit.

1. Create an isolated Supabase development branch from project `inhmvbdujpxrqrlcgmqw` **without copying production users or production data**. Confirm the branch has a different project ID, project URL and API keys from live.
2. Check the branch migration history and contents with `list_migrations`. Validate that pre-existing schema, seed and golden exercise objects are present (or seed a staging-only catalog from reviewed versioned SQL). Confirm `exercises` has the expected source IDs.
3. Apply **only the five pending Phase 1 migrations** with version timestamps `20261107210000`, `20261107211000`, `20261107212000`, `20261107213000`, `20261107214000` **on the branch**. Do not replay baseline migrations with conflicting timestamps until reconciled.
4. Run `exercise_library_phase1_staging_validation.sql` on the branch. Every check must be true. Check SQL migration logs for constraints and unexpected skipped rows.
5. Run `exercise_library_preference_rls_rollback.sql` on the branch using a privileged SQL session; the scenario temporarily creates two dummy auth users then rolls back. Confirm the transaction completed successfully and the two test users are absent afterward.
6. Separately test actual client JWT/RLS behavior for two users via the authenticated API. Ensure one user's favorite/exclusion is invisible to the other; anonymous users must have no library read access.
7. Reapply the four curation migrations on **a fresh, disposable branch or inside a rolled-back transaction** to verify idempotent metadata and relationship upserts without duplicate keys, and compare pre/post generator-approved exercise IDs.
8. Run security and performance advisors on the branch. Capture outcomes and compare with tests/CI.
9. Only after these gates are green, prepare a **separate** migration-history reconciliation plan for production and have it reviewed before any live deployment.

### Acceptance criteria and limitations

**Static/schema checks currently pass; isolated runtime migration and JWT/RLS tests are not yet executed.** Until the charged branch is explicitly authorized, this preflight is deliberately incomplete. Do not assert the migration is deployable based on CI alone.

No production SQL writes, deploys, merges, or role changes were performed.
