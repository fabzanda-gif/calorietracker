# SanoSync — Phase 2: Gym logging + workout libero

This is the original roadmap phase immediately following Phase 1 (Training Profile + Exercise Library), not a different roadmap.

## Phase sequencing

- Phase 0: modular onboarding
- Phase 1: Training Profile + Exercise Library v1 (PR #20, separate release)
- **Phase 2: Gym logging + free workout (PR #21)**
- Phase 3: Athlete State
- Phase 4: Program Generator v2
- Phase 5: Adaptive Coach
- Phases 6–8: nutrition context, cross-training, more adaptive macros

## Prior implementation reused

The main branch already has `StrengthWorkoutLoggerV2`, REST endpoints for starting sessions, saving/deleting sets, adding exercises, completing workouts, creating free workouts, and substituting exercises, with Supabase migrations:
- `20261107192900_restore_strength_workout_logs.sql`
- `20261107193000_add_workout_logger_v2.sql`
- `20261107193100_index_strength_set_logs_user.sql`

Phase 2 does not replace those foundations or require a new database migration. It closes the usage and safety gaps.

## Delivered in this PR

- `GET /strength/workouts/free/recent` — last 30 free workouts for the authenticated user, including planned/draft and completed. The associated logs are fetched in one batched query; no cross-user records.
- `GET /strength/workouts/{workout_id}/detail` — owner-scoped workout plus exercises, performed date, session status, notes and saved sets.
- UI: recover an unfinished free workout after navigating away, app/browser reload, or returning later. The original performed date and saved sets are restored from the backend.
- UI: free workout completed history with duration, notes, exercises and set details; these are read-only.
- UI: name/date a workout, avoid double-click duplicate creations, and leave a workout while preserving drafts.
- Session completion: disallow during in-flight autosaves and fail closed if pending set writes fail. Backend still enforces at least one persisted set.
- Substitution protection: reject replacement of a workout exercise that already has logged sets (409), maintaining the identity of historic effort.
- Demo read-only accounts cannot start/modify workout sessions, series, free workouts or substitutions.
- Local calendar date is used, avoiding UTC off-by-one dates at midnight.

## Test and safety contract

- [x] Python unit/API tests for history, exercise/detail ownership, saved-set recovery, demo write rejection and substitution guard.
- [x] Postgres schema read-only audit confirmed all required tables and columns exist (2026-11-07).
- [ ] Latest GitHub Actions CI passes backend tests, TypeScript, Next build and baseline Playwright.
- [ ] Authenticated browser verification on staging: create free workout, add exercise, save series, navigate away, reload, resume, edit another set, complete, inspect history.
- [ ] Multi-account staging check of RLS and ownership boundaries.
- [ ] Verify planned workout and running session unaffected before production merge/deploy.

## Important caveats

- API history is deliberately bounded to the most recent 30 free workouts.
- There is no new automatic coach decision, exercise approval, schedule rewrite, or nutrition integration.
- Completed workouts are not reopenable through this feature, and their series are displayed read-only.
- Workout changes stay user-driven; the substitution endpoint still requires an explicit selected replacement.
- This PR must not be deployed to production solely because static tests pass; perform authenticated staging smoke checks first.
- The future Phase 3 Athlete State should consume completed workout/set outcomes from the established sources, not create a second log model.

## Deployment

1. Verify current branch CI on the PR head commit, not a cancelled earlier run.
2. Review API ownership filters and that demo accounts have no write access.
3. Verify database already contains the Workout Logger v2 tables (no new migrations in this PR).
4. Verify the authenticated UI flows and RLS in staging.
5. Merge and deploy frontend and Heavy backend in the same release.
6. Confirm no existing planned gym/running sessions were altered and free-workout history is readable.
