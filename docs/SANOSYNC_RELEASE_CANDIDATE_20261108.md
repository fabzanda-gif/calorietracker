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
2. **Backend Render target is confirmed:** use `My Workspace` / `sanosync-api`. Auto-deploy is OFF and the service tracks `codex/landing-redesign`, not `main`. Operator must switch Render branch to verified release code before manually deploying; `trigger_deploy` alone would otherwise publish the wrong branch.
3. Run an actual JWT-authenticated smoke flow through API + Supabase with two real test accounts; verify RLS, preference isolation, gym write/read, plan preview and read-only demo. The suite in CI is simulated HTTP, not a proof against the real data API.
4. The release candidate now filters future `planned` workouts belonging to paused/completed strength plans out of date-range queries used by calendars and Coach, preserving historical completed workouts. Regression tests cover active/paused/free/unknown-plan behavior. **Still verify against live API after backend deployment**; the replacement write path remains non-atomic.
5. Decide on minimal editorial approval of an appropriate hinge exercise before enabling Program Generator v2 creation; current 10 approved records do **not** cover hinge, and v2 intentionally blocks incomplete programs.
6. Verify project security advisories for two pre-existing public SECURITY DEFINER RPC functions (special-period triggers). These are not caused by Phase 1 migrations; review grants before broad rollout.
7. Capture and confirm a recoverable database snapshot and have an operator validate the application rollback path before production merge. Existing Auth has 8 accounts and meals table has 391 records even if there are no active customers.

## Render backend deployment target confirmed

The owner confirmed **Render My Workspace** (not the separately available `sanosync` workspace).

| Item | Verified value |
| --- | --- |
| Workspace | `My Workspace` / `tea-da7gnr942hec73booka0` |
| Backend web service | `sanosync-api` / `srv-da7gqeh42hec73bp2bmg` |
| Service dashboard | https://dashboard.render.com/web/srv-da7gqeh42hec73bp2bmg |
| Public backend URL | https://sanosync-api.onrender.com |
| Health endpoint | `/health` |
| Deployment branch currently configured | `codex/landing-redesign` |
| Auto-deploy | **off** |
| Last known live Render deploy | `dep-dbnn8sbm8hqs73cmm2m0` |
| Live Render commit (before release) | `da8521fc6f6773439d11434b5ef49d064c005d4e` |
| Deployment configuration | `pip install -r requirements.txt` then `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT` |

**Critical release dependency:** A GitHub merge to `main` alone will NOT update Render. It tracks a different branch with manual deploys. In addition, the Render connector currently has no supported direct service-branch edit operation. Before deployment an operator must change the service Git branch to the merged release SHA's `main` or equivalent verified release branch in the Render dashboard, then trigger/confirm one deliberate deployment. Merely clicking Render's “Deploy latest commit” while the branch remains `codex/landing-redesign` will deploy the WRONG code.

Known rollback: redeploy the previous live Render build/commit `da8521f` (or first reestablish the old branch if needed), and restore the known working Vercel production deployment `dpl_DHgDpKt2aGu1P2dyeKDxZW3ioDxS` (SHA `2d03d404...`). Keep additive Supabase tables and exercise data intact.

**Vercel:** The project is `calorietracker` in team `SanoSync`; Git previews for this candidate are READY, but production is still `main` SHA `2d03d4049edc82fea6a1fbd1d6d2e066a041f04d`. Its latest pre-release production deployment is `dpl_DHgDpKt2aGu1P2dyeKDxZW3ioDxS`. This is the explicitly identified frontend rollback target.

## Real-JWT acceptance gate

Added `backend/tests/test_live_authenticated_release_gate.py` as a **manual-run**, normally skipped test suite; the existing `test_release_candidate_authenticated_journey.py` uses mocked authentication and is not proof of real Auth/RLS. The manual test authenticates **two different dedicated Supabase accounts** using the public password-token endpoint, verifies real JWT requests to the selected backend, checks onboard/profile preferences, Athlete State, Training ↔ Nutrition, Gym ↔ Running, Adaptive Macros and safe Program Generator preview, plus missing/invalid-token rejection. The default is read-only except the nonpersisting Generator preview.

Setup environment variables locally or in a private CI-secret configuration (do not paste passwords into tickets, repository files, chat messages or CI logs):
- `LIVE_E2E_SUPABASE_URL`: SanoSync Supabase Auth URL
- `LIVE_E2E_SUPABASE_PUBLISHABLE_KEY`: a publishable key (never the service role key)
- `LIVE_E2E_API_BASE_URL`: verified deployed or self-hosted backend URL
- `LIVE_E2E_USER_A_EMAIL`, `LIVE_E2E_USER_A_PASSWORD`: disposable user A
- `LIVE_E2E_USER_B_EMAIL`, `LIVE_E2E_USER_B_PASSWORD`: disposable user B
- Optional `LIVE_E2E_DEMO_EMAIL` / `LIVE_E2E_DEMO_PASSWORD`: read-only demo identity
- Optional `LIVE_E2E_MUTATIONS=true`: ONLY when explicitly using disposable test accounts; checks a preference write, user isolation, and restores the prior preference. Default is off.

Run `python -m pytest -q backend/tests/test_live_authenticated_release_gate.py` from the repo root with required variables configured. Two actual identities must yield different Supabase Auth IDs. A full real-browser end-to-end journey still requires test account credentials and a backend serving the candidate API, which has **not** been deployed. Do not confuse a READY Vercel preview with candidate backend availability.

No passwords, test users or Auth secrets have been created by the preflight work.

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
- The user has confirmed Render `My Workspace`. The backend service and its deployed commit have been inspected read-only. Actual branch switching, backend deployment and GitHub merge remain pending the real-JWT acceptance gate.
- Production Supabase contains 8 Auth accounts and 391 existing meals; both existed before these migrations. No destructive rollback of the catalog or preference schema should be attempted.

## Verification record

- Auth IDs used in the SQL RLS rollback test are reserved dummy UUIDs; no production user credentials were created or retained.
- This runbook is a release gate record, not a declaration that frontend/backend Phase 1–8 has been released.
