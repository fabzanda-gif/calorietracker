# SanoSync Release Candidate — Phase 1–8 operational handoff

Date: 2026-11-08 (Europe/Rome). Integration branch: `codex/release-candidate-phase1-8-20261108`; integration PR #31 targeting `main` remains **draft** until backend/frontend deployment can be coordinated. Production reference before release: Git SHA `2d03d4049edc82fea6a1fbd1d6d2e066a041f04d`.

## What has been integrated

- Phase 1 PR #20 merged **into the release candidate only** via PR #29.
- Phase 2 PR #21 merged **into the release candidate only** via PR #30.
- Phases 3–8 from the checked Phase 8 stacked branch, including no-delete strength-plan replacement and the requirement to explicitly accept Coach/macro changes.
- Additional read-only demo protection in all onboarding mutation endpoints.
- New HTTP integration test `backend/tests/test_release_candidate_authenticated_journey.py` simulates three bearer identities (owner A, owner B, read-only demo) through onboarding, food/training setup, free gym session with autosaved set, Athlete State, Program Generator v2 (expected no-hinge block), Coach reconciliation, Training ↔ Nutrition, Gym ↔ Running and Adaptive Macros. **Dependency overrides and in-memory repositories are used**. Do not describe this as production Supabase JWT/RLS E2E.

## Supabase migrations — deployment performed in 5 controlled steps

Seven baseline migrations that differed by timestamp in the repository have been compared **byte-for-byte** with the SQL stored in `supabase_migrations.schema_migrations.statements`. All seven match exactly. Their repository filenames have been renamed on this release candidate to the previously applied live versions without changing their Git blobs.

Five new migrations have been applied to the existing SanoSync Supabase project in this exact order:

| Supabase applied version | Name |
| --- | --- |
| `20261107233829` | `curate_exercise_library_phase1_batch1` |
| `20261107233923` | `curate_exercise_library_phase1_batch2` |
| `20261107233939` | `curate_exercise_library_phase1_batch3` |
| `20261107233949` | `curate_exercise_library_phase1_batch4` |
| `20261107234007` | `add_training_exercise_preferences` |

The batch 1 CTE name `symmetric` was rejected by PostgreSQL and renamed `symmetric_edges`. The batch 2 all-null similarity field was rejected as `text` and explicitly cast to `numeric`. Both rejected attempts were verified to leave no partial changes. Each successful applied migration's statement content was subsequently compared byte-for-byte with its Git source. The five repository migration filenames on this RC match these generated live versions; **never replay the earlier versions**.

Post-migration checks: **155 classified active exercises**, **61 directional substitution relations**, **10 generator-approved** (unchanged), **11/11 SQL preflight checks passed**. A transaction-scoped test with simulated authenticated PostgreSQL roles checked select/insert/update/delete user ownership and ended in `ROLLBACK`. Verified: **0 residual test users, 0 test preferences, 391 existing meals unchanged**. These database checks do not prove application JWT tokens or the published API endpoints.

## Remaining gates before merging to main

1. Latest-head GitHub Actions backend, TypeScript, Next.js build and Playwright green.
2. **Backend production owner/workspace selection:** Render exposes two workspaces (`sanosync` and `My Workspace`); connector requires explicit workspace selection to inspect and coordinate backend services. Do not choose silently. Confirm backend auto-deploy or perform backend deployment explicitly after selecting workspace.
3. Run an actual JWT-authenticated smoke flow through API + Supabase with two real test accounts; verify RLS, preference isolation, gym write/read, plan preview and read-only demo. The suite in CI is simulated HTTP, not a proof against the real data API.
4. The release candidate now filters future `planned` workouts belonging to paused/completed strength plans out of date-range queries used by calendars and Coach, preserving historical completed workouts. Regression tests cover active/paused/free/unknown-plan behavior. **Still verify against live API after backend deployment**; the replacement write path remains non-atomic.
5. Decide on minimal editorial approval of an appropriate hinge exercise before enabling Program Generator v2 creation; current 10 approved records do **not** cover hinge, and v2 intentionally blocks incomplete programs.
6. Verify project security advisories for two pre-existing public SECURITY DEFINER RPC functions (special-period triggers). These are not caused by Phase 1 migrations; review grants before broad rollout.
7. Capture and confirm a recoverable database snapshot and have an operator validate the application rollback path before production merge. Existing Auth has 8 accounts and meals table has 391 records even if there are no active customers.

## Coordinated rollout order

1. Keep `main` unchanged until the above gates.
2. Confirm all migrations already applied and no drift: `list_migrations` and schema assertions; never issue a blind `db push`.
3. Verify Render heavy and core API service settings (environment variables, branch and auto-deploy), then plan the backend release and health checks. User must confirm the Render workspace.
4. Coordinate backend deploy with frontend. Vercel production currently points to `main` SHA `2d03d4049edc82fea6a1fbd1d6d2e066a041f04d` via ready deployment `dpl_DHgDpKt2aGu1P2dyeKDxZW3ioDxS`. Preview deployments from the release candidate have been generated automatically but are not production deployments.
5. Merge **only the integrated release candidate** PR #31 once gates are green; do not separately merge Phase 1–8 PRs again and do not merge superseded Coach PR #19.
6. Validate signed-in E2E after deploy, verify calorie budget unchanged and counts of meals/auth/workout logs, and watch API logs.
7. If deployment fails, restore Vercel's known previous production deployment and redeploy/revert the backend to its previous ready version; keep **additive** Supabase schema and data in place to preserve user information. Do not delete the preference table, classifications or logged workouts as an automatic SQL rollback.

## Additional release-candidate hardening

- `StrengthWorkoutsRepository.list_date_range` now treats planned sessions from non-active strength plans as inactive, while retaining completed historical sessions and independent free sessions. Regression tests explicitly check the owner-scoped plan query and fail-closed behavior if a plan cannot be read.
- The latest source branch is under CI again after this correction. No merge to `main` or backend/frontend deployment has occurred.
- Backend deployment coordination is not yet authorized: the connected Render account has both `sanosync` and `My Workspace`. The Render connector requires the user to identify which workspace to operate in before its services can be inspected or deployed.
- Production Supabase contains 8 Auth accounts and 391 existing meals; both existed before these migrations. No destructive rollback of the catalog or preference schema should be attempted.

## Verification record

- Auth IDs used in the SQL RLS rollback test are reserved dummy UUIDs; no production user credentials were created or retained.
- This runbook is a release gate record, not a declaration that frontend/backend Phase 1–8 has been released.
