from datetime import date

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    StrengthPlanRequest,
    _generate_strength_plan,
    _persist_strength_plan,
    create_strength_plan,
)


class FakePlansRepo:
    def __init__(self, active=None):
        self.active = list(
            active or []
        )
        self.created = []
        self.deleted = []

    def list_for_user(self, user_id):
        return list(self.active)

    def create(self, payload):
        item = {
            **payload,
            "id": "plan-new",
        }
        self.created.append(item)
        return item

    def delete(self, plan_id, user_id):
        self.deleted.append(plan_id)
        return True


class FakeWorkoutsRepo:
    def __init__(self):
        self.created = []

    def create_many(self, payloads):
        self.created = [
            {
                **item,
                "id": (
                    "workout-"
                    f"{item['training_week']}-"
                    f"{item['workout_index']}"
                ),
            }
            for item in payloads
        ]

        return list(self.created)


class FakeExercisesRepo:
    def __init__(self, fail=False):
        self.created = []
        self.fail = fail

    def create_many(self, payloads):
        if self.fail:
            raise RuntimeError(
                "exercise insert failed"
            )

        self.created = [
            {
                **item,
                "id": f"exercise-{index}",
            }
            for index, item in enumerate(
                payloads,
                start=1,
            )
        ]

        return list(self.created)


def request(**changes):
    payload = {
        "start_date": date(
            2026,
            9,
            7,
        ),
        "goal": "hypertrophy",
        "experience_level":
            "intermediate",
        "sessions_per_week": 3,
        "total_weeks": 4,
        "replace_active": False,
    }

    payload.update(changes)

    return StrengthPlanRequest(
        **payload
    )


def test_preview_is_deterministic():
    first = _generate_strength_plan(
        request()
    )

    second = _generate_strength_plan(
        request()
    )

    assert first == second
    assert first["workout_count"] == 12


def test_persist_creates_plan_workouts_and_exercises():
    generated = _generate_strength_plan(
        request()
    )

    plans = FakePlansRepo()
    workouts = FakeWorkoutsRepo()
    exercises = FakeExercisesRepo()

    result = _persist_strength_plan(
        user_id="user-1",
        generated=generated,
        plans_repo=plans,
        workouts_repo=workouts,
        exercises_repo=exercises,
    )

    assert result["plan"]["id"] == "plan-new"
    assert result["workout_count"] == 12
    assert result["exercise_count"] == 72

    assert len(workouts.created) == 12
    assert len(exercises.created) == 72

    assert {
        item["strength_workout_id"]
        for item in exercises.created
    } == {
        item["id"]
        for item in workouts.created
    }


def test_persist_rolls_back_plan_on_child_failure():
    generated = _generate_strength_plan(
        request()
    )

    plans = FakePlansRepo()
    workouts = FakeWorkoutsRepo()
    exercises = FakeExercisesRepo(
        fail=True
    )

    with pytest.raises(
        RuntimeError,
        match="exercise insert failed",
    ):
        _persist_strength_plan(
            user_id="user-1",
            generated=generated,
            plans_repo=plans,
            workouts_repo=workouts,
            exercises_repo=exercises,
        )

    assert plans.deleted == [
        "plan-new"
    ]


def test_create_rejects_second_active_plan():
    plans = FakePlansRepo(
        active=[
            {
                "id": "existing",
                "status": "active",
            }
        ]
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        create_strength_plan(
            request=request(),
            current_user=CurrentUser(
                id="user-1",
                access_token="token",
            ),
            plans_repo=plans,
            workouts_repo=(
                FakeWorkoutsRepo()
            ),
            exercises_repo=(
                FakeExercisesRepo()
            ),
        )

    assert exc.value.status_code == 409
    assert not plans.created


def test_create_can_replace_active_plan():
    plans = FakePlansRepo(
        active=[
            {
                "id": "old-plan",
                "status": "active",
            }
        ]
    )

    result = create_strength_plan(
        request=request(
            replace_active=True
        ),
        current_user=CurrentUser(
            id="user-1",
            access_token="token",
        ),
        plans_repo=plans,
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
    )

    assert result["created"] is True

    assert result[
        "replaced_plan_ids"
    ] == [
        "old-plan"
    ]

    assert plans.deleted == [
        "old-plan"
    ]
