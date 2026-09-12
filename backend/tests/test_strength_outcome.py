import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    get_strength_workout_outcome,
)
from backend.services.strength_outcome import (
    StrengthOutcomeService,
)


def planned(
    exercise_id,
    *,
    position=1,
    sets=3,
    reps_min=8,
    reps_max=12,
    rir=2,
):
    return {
        "id": exercise_id,
        "exercise_key": exercise_id,
        "exercise_name": exercise_id,
        "position": position,
        "target_sets": sets,
        "target_reps_min": reps_min,
        "target_reps_max": reps_max,
        "target_rir": rir,
    }


def actual(
    exercise_id,
    reps,
    *,
    rir=2,
    load=50,
):
    return [
        {
            "strength_workout_exercise_id":
                exercise_id,
            "set_index": index,
            "reps": value,
            "load_kg": load,
            "rir": rir,
        }
        for index, value in enumerate(
            reps,
            start=1,
        )
    ]


def test_exercise_on_target():
    result = StrengthOutcomeService().evaluate(
        planned_exercises=[
            planned("exercise-1")
        ],
        set_logs=actual(
            "exercise-1",
            [10, 10, 9],
            rir=2,
        ),
    )

    exercise = result["exercises"][0]

    assert exercise["outcome"] == "on_target"
    assert result["outcome"] == "on_target"


def test_missing_set_is_under_target():
    result = StrengthOutcomeService().evaluate(
        planned_exercises=[
            planned("exercise-1")
        ],
        set_logs=actual(
            "exercise-1",
            [10, 10],
            rir=2,
        ),
    )

    exercise = result["exercises"][0]

    assert exercise["outcome"] == (
        "under_target"
    )
    assert result["outcome"] == (
        "under_target"
    )


def test_reps_below_min_are_under_target():
    result = StrengthOutcomeService().evaluate(
        planned_exercises=[
            planned("exercise-1")
        ],
        set_logs=actual(
            "exercise-1",
            [10, 7, 9],
            rir=2,
        ),
    )

    assert (
        result["exercises"][0]["outcome"]
        == "under_target"
    )


def test_exercise_over_target_requires_reps_and_rir():
    result = StrengthOutcomeService().evaluate(
        planned_exercises=[
            planned("exercise-1")
        ],
        set_logs=actual(
            "exercise-1",
            [12, 12, 12],
            rir=3,
        ),
    )

    exercise = result["exercises"][0]

    assert exercise["outcome"] == (
        "over_target"
    )

    assert result["outcome"] == (
        "over_target"
    )


def test_top_reps_without_extra_rir_is_on_target():
    result = StrengthOutcomeService().evaluate(
        planned_exercises=[
            planned("exercise-1")
        ],
        set_logs=actual(
            "exercise-1",
            [12, 12, 12],
            rir=2,
        ),
    )

    assert (
        result["exercises"][0]["outcome"]
        == "on_target"
    )


def test_one_under_makes_workout_under_target():
    plans = [
        planned(
            "exercise-1",
            position=1,
        ),
        planned(
            "exercise-2",
            position=2,
        ),
    ]

    logs = (
        actual(
            "exercise-1",
            [12, 12, 12],
            rir=3,
        )
        + actual(
            "exercise-2",
            [10, 7, 8],
            rir=2,
        )
    )

    result = StrengthOutcomeService().evaluate(
        planned_exercises=plans,
        set_logs=logs,
    )

    assert result["over_target_count"] == 1
    assert result["under_target_count"] == 1
    assert result["outcome"] == (
        "under_target"
    )


def test_majority_over_makes_workout_over_target():
    plans = [
        planned(
            "exercise-1",
            position=1,
        ),
        planned(
            "exercise-2",
            position=2,
        ),
        planned(
            "exercise-3",
            position=3,
        ),
        planned(
            "exercise-4",
            position=4,
        ),
    ]

    logs = (
        actual(
            "exercise-1",
            [12, 12, 12],
            rir=3,
        )
        + actual(
            "exercise-2",
            [12, 12, 12],
            rir=3,
        )
        + actual(
            "exercise-3",
            [10, 10, 10],
            rir=2,
        )
        + actual(
            "exercise-4",
            [9, 10, 10],
            rir=2,
        )
    )

    result = StrengthOutcomeService().evaluate(
        planned_exercises=plans,
        set_logs=logs,
    )

    assert result["over_target_count"] == 2
    assert result["under_target_count"] == 0
    assert result["outcome"] == (
        "over_target"
    )


class FakeWorkoutsRepo:
    def __init__(self, exists=True):
        self.exists = exists

    def get(self, user_id, workout_id):
        if not self.exists:
            return None

        return {
            "id": workout_id,
            "status": "completed",
        }


class FakeExercisesRepo:
    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return [
            planned("exercise-1")
        ]


class FakeWorkoutLogsRepo:
    def __init__(self, exists=True):
        self.exists = exists

    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        if not self.exists:
            return None

        return {
            "id": "log-1",
            "strength_workout_id":
                workout_id,
        }


class FakeSetLogsRepo:
    def list_for_workout_log(
        self,
        user_id,
        workout_log_id,
    ):
        return actual(
            "exercise-1",
            [10, 10, 10],
            rir=2,
        )


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def test_endpoint_returns_pending_before_log():
    result = get_strength_workout_outcome(
        workout_id="workout-1",
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=FakeWorkoutLogsRepo(
            exists=False
        ),
        set_logs_repo=FakeSetLogsRepo(),
    )

    assert result["status"] == "pending"
    assert result["outcome"] is None


def test_endpoint_evaluates_logged_workout():
    result = get_strength_workout_outcome(
        workout_id="workout-1",
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=FakeWorkoutLogsRepo(),
        set_logs_repo=FakeSetLogsRepo(),
    )

    assert result["status"] == "evaluated"
    assert (
        result["outcome"]["outcome"]
        == "on_target"
    )


def test_endpoint_returns_404_for_unknown_workout():
    with pytest.raises(
        HTTPException
    ) as exc:
        get_strength_workout_outcome(
            workout_id="missing",
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(
                exists=False
            ),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=FakeWorkoutLogsRepo(),
            set_logs_repo=FakeSetLogsRepo(),
        )

    assert exc.value.status_code == 404
