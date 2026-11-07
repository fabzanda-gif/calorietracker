"""Phase 5 security regressions: reconciling cannot mutate workout plans."""
from datetime import date

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers import coach as coach_router


class AdjustmentStore:
    def __init__(self):
        self.created = []
        self.updated = []

    def get_for_signal(self, **kwargs):
        return None

    def get_for_target_action(self, **kwargs):
        return None

    def create(self, payload):
        row = {"id": "proposal-1", **payload}
        self.created.append(row)
        return row

    def update(self, **kwargs):
        self.updated.append(kwargs)
        raise AssertionError("Reconciliation must never auto-apply")

    def list_recent(self, **kwargs):
        return []


class PreferenceStore:
    def get_priority(self, user_id):
        assert user_id == "user-1"
        return "balanced"


class NoWorkoutWrites:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected workout write: {name}")


def user(*, read_only=False):
    return CurrentUser(
        id="user-1", access_token="token", read_only=read_only,
    )


def test_reconcile_stores_auto_candidate_as_proposal_only(monkeypatch):
    proposal = {
        "source_kind": "strength_workout",
        "source_id": "previous-session",
        "source_date": "2026-11-07",
        "target_kind": "strength_workout",
        "target_id": "future-session",
        "target_date": "2026-11-09",
        "action": "reduce_load",
        "severity": "high",
        "scope": "lower",
        "title": "Carico protetto",
        "message": "Proposta da confermare.",
        "proposed_changes": {
            "exercise_updates": [{
                "exercise_id": "squat",
                "before_load_kg": 100.0,
                "prescribed_load_kg": 95.0,
            }],
        },
        "before_state": {},
        "auto_apply": True,
    }
    monkeypatch.setattr(coach_router, "_coach_context", lambda **kwargs: {
        "as_of": "2026-11-07",
        "recent_start": "2026-11-04",
        "future_end": "2026-11-10",
        "events": [],
        "recovery_alerts": [],
        "proposals": [proposal],
    })
    repo = AdjustmentStore()
    # Reconciliation only reads the source repos through patched context.
    # If automatic application is attempted, the fake will reject it.
    result = coach_router.reconcile_training_coach(
        request=coach_router.CoachReconcileRequest(
            as_of=date(2026, 11, 7),
        ),
        current_user=user(),
        activities_repo=NoWorkoutWrites(),
        planned_repo=NoWorkoutWrites(),
        workouts_repo=NoWorkoutWrites(),
        exercises_repo=NoWorkoutWrites(),
        workout_logs_repo=NoWorkoutWrites(),
        set_logs_repo=NoWorkoutWrites(),
        adjustment_repo=repo,
        preferences_repo=PreferenceStore(),
    )
    assert len(repo.created) == 1
    assert repo.updated == []
    assert result["summary"]["auto_applied"] == 0
    assert result["summary"]["proposed"] == 1
    assert result["adjustments"][0]["decision"] == "proposed"


def test_read_only_user_cannot_trigger_reconciliation_writes():
    with pytest.raises(HTTPException) as exc:
        coach_router.reconcile_training_coach(
            request=coach_router.CoachReconcileRequest(
                as_of=date(2026, 11, 7)
            ),
            current_user=user(read_only=True),
            activities_repo=NoWorkoutWrites(),
            planned_repo=NoWorkoutWrites(),
            workouts_repo=NoWorkoutWrites(),
            exercises_repo=NoWorkoutWrites(),
            workout_logs_repo=NoWorkoutWrites(),
            set_logs_repo=NoWorkoutWrites(),
            adjustment_repo=NoWorkoutWrites(),
            preferences_repo=NoWorkoutWrites(),
        )
    assert exc.value.status_code == 403
