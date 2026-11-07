import pytest
from fastapi import HTTPException

from backend.api.routers.coach import (
    _apply_running_changes,
    _apply_strength_changes,
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
