# SanoSync — Phase 5: Adaptive Coach

## Original roadmap and release order
1. Phase 1 — Training Profile + Exercise Library, PR #20
2. Phase 2 — gym logging / free workouts, PR #21
3. Phase 3 — Athlete State, PR #22
4. Phase 4 — Program Generator v2, PR #23
5. **Phase 5 — Adaptive Coach, this branch / PR**

This branch is based on `codex/phase4-program-generator-v2`, **not on main**. It carries forward the substantive Adaptive Coach recovery and plan-integrity work from draft PR #19, but supersedes that branch for this roadmap. Do not merge PR #19 again after merging this phase without explicitly reviewing duplicated changes.

## What the Coach can do
- Reconcile recent completed running/strength activities with upcoming scheduled sessions, detecting training load overlap.
- Propose reducing prescribed loads, reducing set counts, or adjusting a running workout when closely spaced intense sessions conflict.
- Review skipped strength/running sessions and suggest recovery dates without moving a race.
- Use real saved gym logs, not guessed strength activity data.
- Respect explicit user priority `gym`, `balanced` or `running`; this choice is not a medical recovery measurement.
- Show a descriptive Athlete State snapshot (28-day sessions, set count and quality status) in the Coach panel, with graceful fallback if the snapshot is unavailable.
- Disallow acceptance of stale proposals after the session date, intensity, load, prescribed sets or other audited fields change.
- Support explicit acceptance or dismissal of proposals and explicit confirmation for missed-session rescheduling, with server-side revalidation.

## Consent and non-negotiable safeguards
- **Reconciliation never auto-applies a workout change.** Some historical recommendation objects still contain an `auto_apply` candidate hint, and previously persisted adjustments can have decision `auto_applied`. Newly generated proposals are always stored with decision `proposed` until the user confirms the /apply action.
- Viewing the Coach panel is never consent to reduce loads or move workouts.
- All write endpoints reject read-only/demo user accounts.
- Athlete State metrics are descriptive. Limited history does not imply a physiological recovery diagnosis or permission to change plans automatically.
- Stale proposal checks compare the current server state at apply time; no trust in previous preview alone.
- Recovering a skipped strength workout whose plan completed requires a conservative reactivation guard; partial changes use best-effort compensation. **This is not a database transaction.**
- The generator must only use approved exercises and explicit preferences. Phase 5 does not approve more exercises or override Program Generator v2's coverage gate.
- No new schema migrations in this branch, but Coach's preexisting preferences and adjustments tables must be present before rollout.

## QA and release
- Backend tests cover stale running/strength proposals, changed prescribed load/sets, calendar collision, strength plan reactivation/undo, skipped-session recovery and proposal-only reconciliation.
- Frontend/Next build/browser tests must pass on the **latest** branch head.
- Before deployment, authenticate with two distinct test users in a staging environment and confirm no cross-user proposals or recovery actions.
- Verify opening the Coach and refreshing the page never changes a planned workout. Confirm a recommendation only changes a workout after pressing Apply / Confirm.
- Confirm completed/free workouts and set logs are unchanged by analysis, and race sessions never get recovery dates.
- Deploy after Phase 1–4 dependencies have been integrated and verified; do not merge or deploy prematurely.

## Roadmap follow-up
Phase 6 adds nutrition training-day context and protein/macro awareness without speculative automatic macro changes. Running/nutrition integration must use real activity data and preserve the current module boundaries.
