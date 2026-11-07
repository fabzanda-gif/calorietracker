# SanoSync — Phase 8: Adaptive Macros v1

## Original roadmap continuity
- Phase 1: Training Profile + Exercise Library (PR #20)
- Phase 2: Gym logging and free workouts (PR #21)
- Phase 3: Athlete State (PR #22)
- Phase 4: Program Generator v2 (PR #23)
- Phase 5: Adaptive Coach (PR #24)
- Phase 6: Training ↔ Nutrition (PR #25)
- Phase 7: Gym ↔ Running (PR #26)
- **Phase 8: Adaptive Macros (this stacked PR on Phase 7)**

No PR in this stack is automatically merged or deployed; prior phases require authenticated staging validation and deliberate integration in order.

## What is implemented
- `GET /adaptive-macros/preview`: user-scoped, read-only analysis of the most recent 28 days. Optional past `as_of` date for examination; future days rejected.
- `POST /adaptive-macros/apply`: explicitly applies **only** the previously reviewed adjustment to `goal_adjustment_kcal` using the existing profile metadata update. The server recomputes the proposal, compares a digest of observed inputs and requires two explicit approvals (user confirms review + recent food logging completeness).
- Data sources: existing per-user meal logs, weight measurements, recorded activities and completed strength logs; no new tables.
- Weight rate uses robust median measurements from the beginning and end of the observation period, not a single weigh-in.
- At least 4 weigh-ins, >=2 in each of the first/last 7-day windows, >=21 days span, and >=20 days with meals recorded before any adjustment is proposed.
- If profile inputs for budget estimation are missing, or a weight change is unusually large, no adjustment is offered.
- In loss/gain modes, adjustment steps are capped at 100 kcal/day with bounded total goal adjustment. Maintenance mode is observation only.
- If recorded mean calories appear low, increased deficit is not proposed.
- The default result is **no change**, not an automatic adaptation.
- Training-day vs other-day carbohydrate averages are descriptive; no inferred carbohydrate/fat targets and no prescribed calorie burn.
- Protein is read only from the user's existing configured target. No invented gram-per-kilogram macro requirement.
- Frontend dashboard in Progressi: observed weight trend, data quality, training/non-training day context, explanation and two confirmation checkboxes.

## Important limitations
The 28-day meal coverage threshold does **not** guarantee all food was recorded. Users must explicitly attest to adequate completeness before accepting. Even when the threshold passes, the approximation is not a metabolic assessment and cannot establish true expenditure, diagnosis, or clinical nutrition needs.

The previously existing BudgetService remains authoritative and is unchanged. No workout or nutrition log is mutated. Only an explicit `goal_adjustment_kcal` update in user metadata is allowed on acceptance, and no new daily carbohydrate or fat goal is saved.

## Safety and release checklist
1. Confirm latest-head CI green: backend unit/API tests, TypeScript, Next.js build and Playwright.
2. Verify signed-in stage data with actual meal/weight logs, including missing days and malformed values.
3. Test two user accounts to ensure private data isolation.
4. Test stale preview after a new weigh-in, meal correction, or profile change; ensure `409` blocks acceptance.
5. Test demo account read-only restriction and that user cancellations cause no changes.
6. Confirm loss/gain/maintenance settings, bodyweight trend bounds, no proposal for incomplete data, and no unexpected budget recalculation.
7. Deploy prerequisites PR #20–#26 in order, with Phase 1 migration/RLS review. Deploy Phase 8 API + UI together.
8. Validate existing calorie budgets and protein goals are unchanged unless user explicitly accepts a new adjustment.

## Future versions
More advanced adaptive carbohydrate/fat targets, meal timing and training-specific macro strategy should require evidence of dietary preferences and explicit acceptance; this version intentionally stops short of deriving unverified hard macro targets.
