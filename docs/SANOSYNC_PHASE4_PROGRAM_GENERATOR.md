# SanoSync — Phase 4, Program Generator v2

## Roadmap and dependencies
- Phase 1: Training Profile + Exercise Library — PR #20 (not yet deployed)
- Phase 2: strength logger & free workouts — PR #21 (not yet deployed)
- Phase 3: Athlete State — PR #22 (base for this PR)
- **Phase 4: personalized Program Generator v2 — PR #23**
- Phase 5: Adaptive Coach

This is a stacked PR based on `codex/phase3-athlete-state-v1`. It should not be merged into the main branch independently before its prerequisites are integrated and verified.

## API and UX
- `POST /strength/plans/v2/preview` takes a start date, goal, 4–12 weeks and available equipment. It obtains the authenticated user's Training Profile and Athlete State server-side. The frontend cannot dictate experience, strength measurements or excluded exercise IDs.
- The first-week preview is visible alongside the existing plan builder in Activities, with explicit equipment selection and warnings when the approved catalog is incomplete.
- `POST /strength/plans/v2` **recomputes** a fresh approval-gated preview and refuses to write on missing movement coverage, missing equipment, missing Training Profile, or unavailable preference data.
- Users must explicitly confirm when replacing an active training plan. The older plan generator remains unchanged.
- Reuses the proven strength-plan persistence path and stores stable library `exercise_id` UUIDs for v2; no new tables or migrations.
- A Program v2 does not auto-set weights from limited Athlete State data. Existing logged sessions and progress are never overwritten by a preview.

## Hard approval gate
A complete strength program requires at least: squat, hinge, horizontal push, horizontal pull, vertical push and vertical pull. The generator must *never* substitute an unrelated movement because a pattern is missing. Each workout additionally requires its planned movement slots.

The live SanoSync catalog on 2026-11-07 had 317 exercises but only 10 approved for generation; **none were an approved hinge**. Therefore previews must currently show the missing hinge and activation must remain blocked, even though Phase 1 proposed classifications for a broader 154-exercise selection. Classification does not equal approval. Separately review/approve a balanced, technically validated hinge and other required patterns before opening activation; do not approve all 144 additions indiscriminately.

## Personalization
- Training Profile: experience, schedule frequency, duration, fixed weekdays and prioritized muscles
- Exercise Library: approved status, movement pattern, equipment and goal-specific suitability
- Preferences: excluded exercises are never selected; preferred ones sort ahead of comparable approved entries
- Athlete State: descriptive history/data-quality indicator; no unsafe extrapolation or automatic load increases

## Safety and verification
- Owner-scoped database access, with explicit per-user preference filtering
- Read-only demo accounts cannot activate plans
- Missing preference table (Phase 1 migration not deployed) causes a service error rather than silently ignoring exercise exclusions
- Missing or non-matching equipment causes an incomplete preview and blocked activation
- Incomplete preview returns a conflict on create; client-supplied workout payloads are not accepted
- Minimum 4 and maximum 12 weeks, 2 to 4 sessions per week, and valid weekday count enforced
- Test coverage for approved-only selection, exclusions, preference ranking, equipment, date schedule, blocked activation, demo access and absent Athlete State
- Latest-head CI includes Python unit tests, frontend typecheck, Next build and Playwright public checks; signed-in E2E smoke tests still required after staging release

## Release checklist
1. Review and merge/deploy prerequisites in order (Phase 1, 2 and 3).
2. Verify Phase 1 SQL migrations, Training Profile and user-scoped exercise preferences in staging.
3. Editorially review a minimal balanced selection including hinge; approve individually through an auditable separate migration or admin workflow. Retest preview readiness.
4. Authenticate with a test account, verify equipment filtering, priorities, excluded exercises and the 2/3/4-day schedules.
5. Test blocked preview and creation, existing active-program conflict and explicit replacement with separate test accounts.
6. Deploy backend/frontend together, ensure no existing logs or programs are unexpectedly modified.

## Next phase
The Adaptive Coach can use an activated v2 plan and validated Athlete State only **after** the approval and release gates. Do not auto-apply training changes from speculative readiness scores.
