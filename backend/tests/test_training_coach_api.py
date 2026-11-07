import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers import coach as coach_router
from backend.api.routers.coach import (
    CoachReconcileRequest,
    _apply_running_changes,
    _apply_strength_changes,
    reconcile_training_coach,
)


class WorkoutsRepo:
    def get(self, user_id, workout_id):
        if workout_id == "missing":
            return None

        return {
            "id": workout_id,
            "user_id": user_id,
            "status": "planned",
            "title": "Lower A",
        }


class ExercisesRepo:
    def __init__(self, foreign=False):
        self.foreign = foreign
        self.updated = []

    def get(self, user_id, exercise_id):
        return {
            "id": exercise_id,
            "strength_workout_id": (
                "other-workout"
                if self.foreign
                else "workout-1"
            ),
            "target_sets": 4,
            "prescribed_load_kg": 100,
        }

    def update(
        self,
        *,
        user_id,
        exercise_id,
        payload,
    ):
        item = {
            "id": exercise_id,
            **payload,
        }
        self.updated.append(item)
        return item


class PlannedRepo:
    def __init__(self):
        self.updated = []

    def get(self, activity_id, user_id):
        return {
            "id": activity_id,
            "user_id": user_id,
            "status": "planned",
            "distance_meters": 8000,
            "duration_minutes": 45,
            "intensity": "hard",
        }

    def update(
        self,
        activity_id,
        user_id,
        payload,
    ):
        item = {
            "id": activity_id,
            **payload,
        }
        self.updated.append(item)
        return item


def test_apply_strength_changes_is_target_scoped():
    exercises = ExercisesRepo()

    result = _apply_strength_changes(
        user_id="user-1",
        target_workout_id="workout-1",
        proposed_changes={
            "exercise_updates": [
                {
                    "exercise_id":
                        "exercise-1",
                    "prescribed_load_kg":
                        95,
                    "target_sets": 3,
                }
            ]
        },
        workouts_repo=WorkoutsRepo(),
        exercises_repo=exercises,
    )

    assert len(
        result["exercises"]
    ) == 1
    assert exercises.updated == [
        {
            "id": "exercise-1",
            "prescribed_load_kg": 95.0,
            "target_sets": 3,
        }
    ]


def test_apply_strength_changes_rejects_foreign_exercise():
    with pytest.raises(
        HTTPException
    ) as exc:
        _apply_strength_changes(
            user_id="user-1",
            target_workout_id="workout-1",
            proposed_changes={
                "exercise_updates": [
                    {
                        "exercise_id":
                            "exercise-1",
                        "target_sets": 3,
                    }
                ]
            },
            workouts_repo=WorkoutsRepo(),
            exercises_repo=ExercisesRepo(
                foreign=True
            ),
        )

    assert exc.value.status_code == 409


def test_apply_running_changes_only_allows_coach_fields():
    repo = PlannedRepo()

    result = _apply_running_changes(
        user_id="user-1",
        target_id="run-1",
        proposed_changes={
            "distance_meters": 6800,
            "duration_minutes": 38,
            "intensity": "moderate",
            "title": "should not change",
        },
        planned_repo=repo,
    )

    assert result["distance_meters"] == 6800
    assert "title" not in repo.updated[0]



class AdjustmentRepo:
    def __init__(self):
        self.created = []

    def get_for_signal(self, **kwargs):
        return None

    def get_for_target_action(self, **kwargs):
        return {
            "id": "guard-1",
            "decision": "auto_applied",
            "target_id": "workout-1",
            "action": "reduce_load",
        }

    def create(self, payload):
        self.created.append(payload)
        return {
            **payload,
            "id": "new-1",
        }

    def update(self, **kwargs):
        raise AssertionError(
            "existing auto guard must not be updated"
        )

    def list_recent(self, **kwargs):
        return []


def test_reconcile_does_not_stack_auto_guard(
    monkeypatch,
):
    proposal = {
        "source_kind": "activity",
        "source_id": "activity-2",
        "source_date": "2026-11-07",
        "target_kind": "strength_workout",
        "target_id": "workout-1",
        "target_date": "2026-11-08",
        "action": "reduce_load",
        "severity": "high",
        "scope": "lower",
        "title": "Protezione",
        "message": "Riduci il carico.",
        "proposed_changes": {
            "exercise_updates": [],
        },
        "before_state": {},
        "auto_apply": True,
    }

    monkeypatch.setattr(
        coach_router,
        "_coach_context",
        lambda **kwargs: {
            "as_of": "2026-11-07",
            "recent_start": "2026-11-04",
            "future_end": "2026-11-10",
            "events": [],
            "proposals": [proposal],
        },
    )

    adjustments = AdjustmentRepo()

    result = reconcile_training_coach(
        request=CoachReconcileRequest(
            as_of=None,
        ),
        current_user=CurrentUser(
            id="user-1",
            access_token="token",
        ),
        activities_repo=object(),
        planned_repo=object(),
        workouts_repo=object(),
        exercises_repo=object(),
        workout_logs_repo=object(),
        set_logs_repo=object(),
        adjustment_repo=adjustments,
    )

    assert adjustments.created == []
    assert (
        result["adjustments"][0]["id"]
        == "guard-1"
    )
    assert result["summary"]["auto_applied"] == 1
