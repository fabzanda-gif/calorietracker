# SanoSync — Phase 3: Athlete State v1

## Position in the original roadmap
- Phase 1 — Training Profile and curated Exercise Library: PR #20 (separate)
- Phase 2 — gym logging and resumable free workouts: PR #21 (separate)
- **Phase 3 — Athlete State v1: PR #22**
- Phase 4 — Program Generator v2
- Phase 5 — Adaptive Coach
- Phase 6+ — nutrition and cross-training connections

## Data model
Athlete State v1 is **computed, read-only**. It does not create a duplicate log, mutate existing sets, or write a health score. Data comes from existing `strength_workout_logs` completed records, `strength_set_logs`, `strength_workout_exercises`, `strength_workouts` and optional `training_profiles`.

`GET /athlete-state?as_of=YYYY-MM-DD` returns:
- `data_status`: `limited` or `available`; never a medical or readiness classification
- last 7, 28, 56 days of completed gym sessions, sets, duration and volume load (kg × repetitions)
- previous seven-day comparison and eight week-by-week counts
- days since latest completed session
- optional adherence ratio relative to the declared Training Profile sessions/week (null when none)
- most logged movements and workout history coverage flags

The calculation uses `performed_date` rather than creation date. Draft sessions and future sessions are excluded. Series for out-of-window sessions are excluded even if accidentally returned by the data layer. Exercise identity is based on `exercise_id` where present, with older exercise key fallback; no longitudinal comparisons of different machines or movements are inferred.

## Reliability and privacy
- Every Supabase query includes an authenticated `user_id` filter and is scoped to 56 days maximum.
- Up to 400 completed sessions are considered; paged set reads are bounded and checked to avoid silent partial statistics.
- A gap or truncated history causes a `limited` status.
- No training loads, strength prescriptions, workout plans or logged sets are modified.
- Bodyweight-only sets typically have `load_kg=0`, so volume load is not total exercise effort.
- If a workout is completed with zero sets, the quality flags show that limitation.
- A ratio of 100% means the stated frequency target was met or exceeded, not a judgment of athletic ability or readiness.

## QA and rollout
1. Latest PR-head CI (Python tests, TypeScript, Next build, browser checks).
2. Signed-in staging test with at least one free and one planned strength workout; verify only completed sessions appear.
3. Two-account privacy test.
4. Test older history around calendar boundaries, empty history, and current day.
5. Deploy heavy API and frontend together; no database migration needed.
6. Only after Phase 3 accuracy is confirmed should a future Program Generator v2 read these descriptors.

## Future development
Expanded Athlete State can incorporate running/cycling through the existing activity event model. That must be a distinct data-source integration with explicit de-duplication and evidence. Do not fabricate recovery or injury scores from simple workout frequency.
