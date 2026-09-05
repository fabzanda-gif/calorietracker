import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    apply_strength_progression,
)


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def source_exercise():
    return {
        "id": "source-exercise",
        "exercise_key": "bench_press",
        "exercise_name": "Bench Press",
        "movement_pattern": "horizontal_push",
        "position": 1,
        "target_sets": 3,
        "target_reps_min": 8,
        "target_reps_max": 12,
        "target_rir": 2,
        "prescribed_load_kg": None,
    }


def target_exercise():
    return {
        **source_exercise(),
        "id": "target-exercise",
        "prescribed_load_kg": None,
    }


class FakeWorkoutsRepo:
    def __init__(self, with_future=True):
        self.with_future = with_future

    def get(self, user_id, workout_id):
        return {
            "id": workout_id,
            "strength_plan_id": "plan-1",
            "scheduled_date": "2026-09-01",
            "status": "completed",
        }

    def list_for_plan(self, user_id, plan_id):
        items = [
            {
                "id": "source-workout",
                "strength_plan_id": plan_id,
                "scheduled_date": "2026-09-01",
                "workout_index": 1,
                "status": "completed",
            }
        ]

        if self.with_future:
            items.append(
                {
                    "id": "target-workout",
                    "strength_plan_id": plan_id,
                    "scheduled_date": "2026-09-04",
                    "workout_index": 2,
                    "status": "planned",
                }
            )

        return items


class FakeExercisesRepo:
    def __init__(self):
        self.updated = []

    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        if workout_id == "source-workout":
            return [source_exercise()]

        if workout_id == "target-workout":
            return [target_exercise()]

        return []

    def update_prescribed_load(
        self,
        *,
        user_id,
        exercise_id,
        prescribed_load_kg,
    ):
        self.updated.append(
            (
                exercise_id,
                prescribed_load_kg,
            )
        )

        return {
            **target_exercise(),
            "prescribed_load_kg":
                prescribed_load_kg,
        }


class FakeWorkoutLogsRepo:
    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return {
            "id": "workout-log-1",
        }


class FakeSetLogsRepo:
    def __init__(
        self,
        reps=None,
        rir=3,
        load=80,
    ):
        self.reps = reps or [
            12,
            12,
            12,
        ]
        self.rir = rir
        self.load = load

    def list_for_workout_log(
        self,
        user_id,
        workout_log_id,
    ):
        return [
            {
                "strength_workout_exercise_id":
                    "source-exercise",
                "set_index": index,
                "reps": reps,
                "load_kg": self.load,
                "rir": self.rir,
            }
            for index, reps in enumerate(
                self.reps,
                start=1,
            )
        ]


class FakeHistoryRepo:
    def __init__(self):
        self.rows = []
        self.deleted = []

    def get_for_source_exercise(
        self,
        user_id,
        source_exercise_id,
    ):
        return next(
            (
                row
                for row in self.rows
                if row["source_exercise_id"]
                == source_exercise_id
            ),
            None,
        )

    def get_for_target_exercise(
        self,
        user_id,
        target_exercise_id,
    ):
        return next(
            (
                row
                for row in self.rows
                if row["target_exercise_id"]
                == target_exercise_id
            ),
            None,
        )

    def create(self, payload):
        item = {
            **payload,
            "id": "history-1",
        }

        self.rows.append(item)
        return item

    def delete(self, history_id, user_id):
        self.deleted.append(history_id)

        self.rows = [
            row
            for row in self.rows
            if row["id"] != history_id
        ]

        return True


def test_over_target_applies_next_load():
    exercises = FakeExercisesRepo()
    history = FakeHistoryRepo()

    result = apply_strength_progression(
        workout_id="source-workout",
        exercise_id="source-exercise",
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=exercises,
        workout_logs_repo=FakeWorkoutLogsRepo(),
        set_logs_repo=FakeSetLogsRepo(),
        history_repo=history,
    )

    assert result["applied"] is True

    assert result["proposal"]["action"] == (
        "increase_load"
    )

    assert exercises.updated == [
        (
            "target-exercise",
            82.5,
        )
    ]

    assert history.rows[0]["after_load_kg"] == (
        82.5
    )


def test_on_target_initializes_next_load():
    exercises = FakeExercisesRepo()
    history = FakeHistoryRepo()

    result = apply_strength_progression(
        workout_id="source-workout",
        exercise_id="source-exercise",
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=exercises,
        workout_logs_repo=FakeWorkoutLogsRepo(),
        set_logs_repo=FakeSetLogsRepo(
            reps=[10, 10, 10],
            rir=2,
            load=80,
        ),
        history_repo=history,
    )

    assert result["proposal"]["action"] == (
        "maintain"
    )

    assert exercises.updated == [
        (
            "target-exercise",
            80,
        )
    ]


def test_replay_is_blocked():
    history = FakeHistoryRepo()

    history.rows.append(
        {
            "id": "existing",
            "source_exercise_id":
                "source-exercise",
            "target_exercise_id":
                "target-exercise",
        }
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        apply_strength_progression(
            workout_id="source-workout",
            exercise_id="source-exercise",
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=(
                FakeWorkoutLogsRepo()
            ),
            set_logs_repo=FakeSetLogsRepo(),
            history_repo=history,
        )

    assert exc.value.status_code == 409


def test_missing_next_exposure_is_blocked():
    with pytest.raises(
        HTTPException
    ) as exc:
        apply_strength_progression(
            workout_id="source-workout",
            exercise_id="source-exercise",
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(
                with_future=False
            ),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=(
                FakeWorkoutLogsRepo()
            ),
            set_logs_repo=FakeSetLogsRepo(),
            history_repo=FakeHistoryRepo(),
        )

    assert exc.value.status_code == 409


def test_zero_load_is_not_applied():
    with pytest.raises(
        HTTPException
    ) as exc:
        apply_strength_progression(
            workout_id="source-workout",
            exercise_id="source-exercise",
            current_user=user(),
            workouts_repo=FakeWorkoutsRepo(),
            exercises_repo=FakeExercisesRepo(),
            workout_logs_repo=(
                FakeWorkoutLogsRepo()
            ),
            set_logs_repo=FakeSetLogsRepo(
                load=0
            ),
            history_repo=FakeHistoryRepo(),
        )

    assert exc.value.status_code == 409
