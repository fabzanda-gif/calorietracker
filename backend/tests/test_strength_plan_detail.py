import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    get_strength_plan_detail,
)


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


class FakePlansRepo:
    def __init__(self, exists=True):
        self.exists = exists

    def get(self, plan_id, user_id):
        if not self.exists:
            return None

        return {
            "id": plan_id,
            "user_id": user_id,
            "goal": "strength",
            "status": "active",
        }


class FakeWorkoutsRepo:
    def list_for_plan(
        self,
        user_id,
        plan_id,
    ):
        return [
            {
                "id": "workout-1",
                "strength_plan_id": plan_id,
                "scheduled_date": "2026-09-07",
                "workout_index": 1,
                "status": "planned",
                "title": "Upper A",
            },
            {
                "id": "workout-2",
                "strength_plan_id": plan_id,
                "scheduled_date": "2026-09-10",
                "workout_index": 2,
                "status": "planned",
                "title": "Lower A",
            },
        ]


class FakeExercisesRepo:
    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return [
            {
                "id": f"{workout_id}-exercise-1",
                "strength_workout_id":
                    workout_id,
                "exercise_key": "bench_press",
                "exercise_name": "Bench Press",
                "position": 1,
                "target_sets": 3,
                "target_reps_min": 6,
                "target_reps_max": 8,
                "target_rir": 2,
            }
        ]


def test_returns_plan_with_nested_workouts():
    result = get_strength_plan_detail(
        plan_id="plan-1",
        current_user=user(),
        plans_repo=FakePlansRepo(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
    )

    assert result["plan"]["id"] == "plan-1"
    assert result["workout_count"] == 2
    assert len(
        result["workouts"][0]["exercises"]
    ) == 1


def test_unknown_plan_is_404():
    with pytest.raises(
        HTTPException
    ) as exc:
        get_strength_plan_detail(
            plan_id="missing",
            current_user=user(),
            plans_repo=FakePlansRepo(
                exists=False
            ),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
        )

    assert exc.value.status_code == 404
