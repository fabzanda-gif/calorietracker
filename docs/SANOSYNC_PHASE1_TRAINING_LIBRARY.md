# SanoSync — Phase 1: Training Profile + Exercise Library v1

This document is the handoff for the original SanoSync roadmap, not a new roadmap.

## Roadmap order
- Phase 0: modular onboarding (existing)
- **Phase 1: Training Profile + Exercise Library v1 (this PR)**
- Phase 2: gym logging / free workout
- Phase 3: Athlete State
- Phase 4: Program Generator v2
- Phase 5: Adaptive Coach
- Phase 6+: nutrition and cross-training integration

Do not treat Coach PR #19 as a prerequisite for this work, or merge unrelated draft PRs into this branch.

## Existing foundation
- `GET /onboarding/status` and `PUT /onboarding/training`
- `GET /exercises` and `GET /exercises/{identifier}`
- Supabase exercise tables (taxonomy, equipment, muscles, media, translations, aliases)
- On 2026-11-07, the SanoSync database contained 317 catalog exercises, 10 already approved for generation, and 0 substitution links.

## Phase 1 implementation in PR #20
- Training Profile editing on the existing account Profile page (non-destructive).
- Searchable Exercise Preferences section on the Profile page. User may mark preferred, excluded or remove preference.
- Per-user `training_exercise_preferences` with auth.uid()-scoped RLS and a composite unique key.
- Authenticated API:
  - `GET /exercises/catalog/status` (read-only quality snapshot)
  - `GET /exercises/{identifier}/alternatives` (equipment filter; `requires_confirmation=true`)
  - `GET /exercises/preferences`
  - `PUT /exercises/{identifier}/preference`
  - `DELETE /exercises/{identifier}/preference`
- The alternatives endpoint excludes user-excluded exercises and prioritizes preferred ones. No workout, plan or set is modified by this endpoint.
- Curated four metadata batches: 18 + 44 + 53 + 30 = 145 new distinct exercises, plus 10 existing golden exercises, for **155 classified entries** after migration.
- Substitution relationships, regression / progression and close-substitutes are stored in their own directed relationship table.

## Scope and critical safeguards
- 155 **classified** is NOT the same as 155 **approved_for_generation**. Only the 10 already approved remain generator-approved after these migrations.
- Use the reviewed taxonomy only to suggest, search and enrich exercises until subsequent quality review explicitly approves them.
- The changes in this PR are unmerged and not deployed until explicitly verified.
- Never automatically swap a logged or scheduled workout because an alternative exists.
- The training profile update must not clear an existing history or plan.
- Preference writes are forbidden for the demo read-only account.
- RLS must allow only the owning user to read or write their preferences.
- Migration execution order: `20261107210000`, `211000`, `212000`, `213000`, `214000`. The exercise library foundational migrations precede these.
- Applying these migrations to a production Supabase instance is a separate release operation; CI runs unit/integration/TS/build/browser checks, not live migration execution.

## QA acceptance checklist
- [x] 145 distinct exercise source IDs in four batch migrations; no overlap with the ten golden exercises (static CI guard).
- [x] Query database for existence and inactive status of the newly curated identifiers (data checked in development session).
- [x] Backend API and repository tests for exercise alternatives, equipment filtering, missing and inactive exercises.
- [x] User-specific preference isolation test (another user's exclusion cannot leak).
- [x] Search, preferred/excluded, saved selections and profile editing UI implemented.
- [ ] CI green on latest commit of PR #20 (check workflow run, not older commits).
- [ ] Production/staging migration dry run and post-migration audit (not performed by PR CI).
- [ ] Authenticated end-to-end test of preference UI and RLS with separate user accounts.
- [ ] Exercise-classification editorial review, including caution around movement substitutions and fatigue before using in generated programs.
- [ ] Verify existing training plans and logs unchanged after deployment.

## Releasing
1. Review the PR diff for migration safety, user access boundaries and UI.
2. Confirm latest backend and frontend Actions runs are green.
3. Apply and verify database migrations in the deployment pipeline (or safe staging environment first).
4. Verify catalog status counts, alternative links and preference write/read isolation.
5. Deploy frontend and backend together to avoid a UI/backend mismatch.
6. Observe errors and revert application release if necessary. Database migrations should be backward compatible and retained if rolling back only the application.

## Unfinished work after Phase 1
Phase 2: use the stable exercise IDs in a real free-workout / gym-logging UI, validate substitutions with user confirmation and workout collision protections. Phase 4: use a separate approval process and score curation before expanding the generator beyond the ten golden entries.
