from datetime import date

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    StrengthExerciseLogRequest,
    StrengthSetLogRequest,
    StrengthWorkoutLogRequest,
    log_strength_workout,
)


class FakeWorkoutsRepo:
    def __init__(self):
        self.updated = []

    def get(self, user_id, workout_id):
        if workout_id == "missing":
            return None

        return {
            "id": workout_id,
            "user_id": user_id,
            "status": "planned",
        }

    def update_status(
        self,
        *,
        user_id,
        workout_id,
        status,
    ):
        self.updated.append(
            (workout_id, status)
        )

        return {
            "id": workout_id,
            "status": status,
        }


class FakeExercisesRepo:
    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return [
            {"id": "exercise-1"},
            {"id": "exercise-2"},
        ]


class FakeWorkoutLogsRepo:
    def __init__(self, existing=False):
        self.existing = existing
        self.deleted = []

    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        if self.existing:
            return {"id": "existing-log"}
        return None

    def create(self, payload):
        return {
            **payload,
            "id": "log-1",
        }

    def delete(self, log_id, user_id):
        self.deleted.append(log_id)
        return True


class FakeSetLogsRepo:
    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    def create_many(self, payloads):
        if self.fail:
            raise RuntimeError(
                "set insert failed"
            )

        self.created = [
            {
                **item,
                "id": f"set-{index}",
            }
            for index, item in enumerate(
                payloads,
                start=1,
            )
        ]

        return list(self.created)


def payload():
    return StrengthWorkoutLogRequest(
        performed_date=date(2026, 9, 5),
        duration_minutes=55,
        notes="Buona seduta",
        exercises=[
            StrengthExerciseLogRequest(
                exercise_id="exercise-1",
                sets=[
                    StrengthSetLogRequest(
                        reps=8,
                        load_kg=80,
                        rir=2,
                    ),
                    StrengthSetLogRequest(
                        reps=8,
                        load_kg=80,
                        rir=2,
                    ),
                ],
            ),
            StrengthExerciseLogRequest(
                exercise_id="exercise-2",
                sets=[
                    StrengthSetLogRequest(
                        reps=10,
                        load_kg=45,
                        rir=3,
                    ),
                ],
            ),
        ],
    )


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def test_logs_sets_and_completes_workout():
    workouts = FakeWorkoutsRepo()
    sets = FakeSetLogsRepo()

    result = log_strength_workout(
        workout_id="workout-1",
        request=payload(),
        current_user=user(),
        workouts_repo=workouts,
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=FakeWorkoutLogsRepo(),
        set_logs_repo=sets,
    )

    assert result["logged"] is True
    assert result["set_count"] == 3

    assert workouts.updated == [
        ("workout-1", "completed")
    ]

    assert [
        item["set_index"]
        for item in sets.created
    ] == [1, 2, 1]


def test_rejects_unknown_workout():
    with pytest.raises(
        HTTPException
    ) as exc:
        log_strength_workout(
            workout_id="missing",
            request=payload(),
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=FakeWorkoutLogsRepo(),
            set_logs_repo=FakeSetLogsRepo(),
        )

    assert exc.value.status_code == 404


def test_rejects_duplicate_log():
    with pytest.raises(
        HTTPException
    ) as exc:
        log_strength_workout(
            workout_id="workout-1",
            request=payload(),
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=FakeWorkoutLogsRepo(
                existing=True
            ),
            set_logs_repo=FakeSetLogsRepo(),
        )

    assert exc.value.status_code == 409


def test_rejects_foreign_exercise():
    request = payload()

    request.exercises[0].exercise_id = (
        "exercise-foreign"
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        log_strength_workout(
            workout_id="workout-1",
            request=request,
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=FakeWorkoutLogsRepo(),
            set_logs_repo=FakeSetLogsRepo(),
        )

    assert exc.value.status_code == 422


def test_rolls_back_log_if_sets_fail():
    logs = FakeWorkoutLogsRepo()

    with pytest.raises(
        RuntimeError,
        match="set insert failed",
    ):
        log_strength_workout(
            workout_id="workout-1",
            request=payload(),
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=logs,
            set_logs_repo=FakeSetLogsRepo(
                fail=True
            ),
        )

    assert logs.deleted == ["log-1"]
