import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    get_strength_plan_history,
)


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


class PlansRepo:
    def __init__(self, exists=True):
        self.exists = exists

    def get(self, plan_id, user_id):
        if not self.exists:
            return None

        return {
            "id": plan_id,
            "user_id": user_id,
        }


class WorkoutsRepo:
    def list_for_plan(self, user_id, plan_id):
        return [
            {
                "id": "workout-1",
                "strength_plan_id": plan_id,
                "scheduled_date": "2026-09-01",
                "training_week": 1,
                "workout_index": 1,
                "title": "Upper A",
                "focus": "upper",
                "status": "completed",
            },
            {
                "id": "workout-2",
                "strength_plan_id": plan_id,
                "scheduled_date": "2026-09-04",
                "training_week": 1,
                "workout_index": 2,
                "title": "Lower A",
                "focus": "lower",
                "status": "planned",
            },
        ]


class ExercisesRepo:
    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return [
            {
                "id": "exercise-1",
                "strength_workout_id":
                    workout_id,
                "exercise_key": "bench_press",
                "exercise_name": "Bench Press",
                "movement_pattern":
                    "horizontal_push",
                "position": 1,
                "target_sets": 3,
                "target_reps_min": 8,
                "target_reps_max": 12,
                "target_rir": 2,
            }
        ]


class WorkoutLogsRepo:
    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return {
            "id": "log-1",
            "strength_workout_id":
                workout_id,
            "performed_date": "2026-09-01",
            "duration_minutes": 55,
            "notes": "Buona seduta",
        }


class SetLogsRepo:
    def list_for_workout_log(
        self,
        user_id,
        workout_log_id,
    ):
        return [
            {
                "strength_workout_exercise_id":
                    "exercise-1",
                "set_index": 1,
                "reps": 10,
                "load_kg": 80,
                "rir": 2,
            },
            {
                "strength_workout_exercise_id":
                    "exercise-1",
                "set_index": 2,
                "reps": 10,
                "load_kg": 80,
                "rir": 2,
            },
            {
                "strength_workout_exercise_id":
                    "exercise-1",
                "set_index": 3,
                "reps": 10,
                "load_kg": 80,
                "rir": 2,
            },
        ]


class HistoryRepo:
    def list_for_plan(
        self,
        user_id,
        plan_id,
    ):
        return [
            {
                "id": "progression-1",
                "source_workout_id":
                    "workout-1",
                "source_exercise_id":
                    "exercise-1",
                "target_exercise_id":
                    "exercise-next",
                "exercise_key":
                    "bench_press",
                "action": "maintain",
                "before_load_kg": None,
                "after_load_kg": 80,
            }
        ]


def test_returns_completed_workout_history():
    result = get_strength_plan_history(
        plan_id="plan-1",
        current_user=user(),
        plans_repo=PlansRepo(),
        workouts_repo=WorkoutsRepo(),
        exercises_repo=ExercisesRepo(),
        workout_logs_repo=WorkoutLogsRepo(),
        set_logs_repo=SetLogsRepo(),
        history_repo=HistoryRepo(),
    )

    assert result["count"] == 1

    item = result["items"][0]

    assert (
        item["workout"]["id"]
        == "workout-1"
    )

    assert (
        item["workout_log"][
            "duration_minutes"
        ]
        == 55
    )

    assert len(
        item["exercises"][0]["sets"]
    ) == 3

    assert (
        item["outcome"]["outcome"]
        == "on_target"
    )

    assert len(
        item["progressions"]
    ) == 1


def test_unknown_plan_is_404():
    with pytest.raises(
        HTTPException
    ) as exc:
        get_strength_plan_history(
            plan_id="missing",
            current_user=user(),
            plans_repo=PlansRepo(
                exists=False
            ),
            workouts_repo=WorkoutsRepo(),
            exercises_repo=ExercisesRepo(),
            workout_logs_repo=(
                WorkoutLogsRepo()
            ),
            set_logs_repo=SetLogsRepo(),
            history_repo=HistoryRepo(),
        )

    assert exc.value.status_code == 404
