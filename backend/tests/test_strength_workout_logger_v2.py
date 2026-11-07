from __future__ import annotations

from datetime import date

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    StrengthFreeWorkoutRequest,
    StrengthSessionStartRequest,
    StrengthSetAutosaveRequest,
    StrengthWorkoutCompleteRequest,
    autosave_strength_set,
    complete_strength_session,
    create_free_strength_workout,
    start_strength_session,
)


class FakeWorkoutsRepo:
    def __init__(self):
        self.workout = {
            "id": "workout-1",
            "user_id": "user-1",
            "strength_plan_id": None,
            "scheduled_date": "2026-11-07",
            "training_week": None,
            "workout_index": None,
            "title": "Workout libero",
            "focus": "free",
            "status": "planned",
            "workout_kind": "free",
            "estimated_duration_minutes": None,
        }

    def get(self, user_id, workout_id):
        if workout_id != self.workout["id"]:
            return None
        return dict(self.workout)

    def create(self, payload):
        self.workout = {
            **payload,
            "id": "free-1",
        }
        return dict(self.workout)

    def update_status(
        self,
        *,
        user_id,
        workout_id,
        status,
    ):
        self.workout["status"] = status
        return dict(self.workout)


class FakeExercisesRepo:
    def get(self, user_id, exercise_id):
        if exercise_id != "exercise-1":
            return None
        return {
            "id": "exercise-1",
            "strength_workout_id": "workout-1",
        }

    def list_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return [
            {
                "id": "exercise-1",
                "strength_workout_id": workout_id,
                "position": 1,
                "exercise_key": "bench_press",
                "exercise_name": "Bench Press",
                "movement_pattern":
                    "horizontal_push",
                "target_sets": 3,
                "target_reps_min": 8,
                "target_reps_max": 12,
                "target_rir": 2,
                "rest_seconds": 90,
                "prescribed_load_kg": 80,
            }
        ]


class FakeWorkoutLogsRepo:
    def __init__(self):
        self.item = None

    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        return (
            dict(self.item)
            if self.item
            else None
        )

    def create(self, payload):
        self.item = {
            **payload,
            "id": "log-1",
        }
        return dict(self.item)

    def update(
        self,
        log_id,
        user_id,
        payload,
    ):
        self.item = {
            **(self.item or {}),
            **payload,
            "id": log_id,
        }
        return dict(self.item)

    def delete(self, log_id, user_id):
        self.item = None
        return True


class FakeSetLogsRepo:
    def __init__(self):
        self.items = []

    def upsert_set(self, payload):
        self.items = [
            item
            for item in self.items
            if not (
                item[
                    "strength_workout_exercise_id"
                ]
                == payload[
                    "strength_workout_exercise_id"
                ]
                and item["set_index"]
                == payload["set_index"]
            )
        ]
        item = {
            **payload,
            "id": "set-1",
        }
        self.items.append(item)
        return dict(item)

    def list_for_workout_log(
        self,
        user_id,
        workout_log_id,
    ):
        return list(self.items)

    def delete_set(self, **kwargs):
        return True


class FakePlansRepo:
    pass


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def test_session_start_creates_resumable_draft():
    logs = FakeWorkoutLogsRepo()

    result = start_strength_session(
        workout_id="workout-1",
        request=StrengthSessionStartRequest(
            performed_date=date(2026, 11, 7),
        ),
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=logs,
        set_logs_repo=FakeSetLogsRepo(),
    )

    assert result["status"] == "draft"
    assert result["workout_log"]["status"] == "draft"
    assert result["exercises"][0]["id"] == "exercise-1"


def test_set_autosave_persists_simple_feeling():
    logs = FakeWorkoutLogsRepo()
    sets = FakeSetLogsRepo()

    result = autosave_strength_set(
        workout_id="workout-1",
        exercise_id="exercise-1",
        set_index=1,
        request=StrengthSetAutosaveRequest(
            reps=12,
            load_kg=80,
            feeling="easy",
        ),
        current_user=user(),
        workouts_repo=FakeWorkoutsRepo(),
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=logs,
        set_logs_repo=sets,
    )

    assert result["saved"] is True
    assert result["set"]["feeling"] == "easy"
    assert logs.item["status"] == "draft"


def test_complete_session_finishes_free_workout():
    workouts = FakeWorkoutsRepo()
    logs = FakeWorkoutLogsRepo()
    sets = FakeSetLogsRepo()

    logs.create(
        {
            "user_id": "user-1",
            "strength_workout_id": "workout-1",
            "performed_date": "2026-11-07",
            "status": "draft",
        }
    )
    sets.upsert_set(
        {
            "user_id": "user-1",
            "strength_workout_log_id": "log-1",
            "strength_workout_exercise_id":
                "exercise-1",
            "set_index": 1,
            "reps": 10,
            "load_kg": 80,
            "rir": None,
            "feeling": "right",
        }
    )

    result = complete_strength_session(
        workout_id="workout-1",
        request=StrengthWorkoutCompleteRequest(
            duration_minutes=50,
            notes="Buona seduta",
        ),
        current_user=user(),
        workouts_repo=workouts,
        plans_repo=FakePlansRepo(),
        workout_logs_repo=logs,
        set_logs_repo=sets,
    )

    assert result["completed"] is True
    assert result["workout"]["status"] == "completed"
    assert result["workout_log"]["status"] == "completed"


def test_create_free_workout_uses_shared_workout_model():
    workouts = FakeWorkoutsRepo()

    result = create_free_strength_workout(
        request=StrengthFreeWorkoutRequest(
            title="Extra upper",
            performed_date=date(2026, 11, 7),
        ),
        current_user=user(),
        workouts_repo=workouts,
    )

    assert result["created"] is True
    assert result["workout"]["workout_kind"] == "free"
    assert result["workout"]["strength_plan_id"] is None
    assert result["workout"]["focus"] == "free"


def test_autosave_preserves_historical_session_date():
    workouts = FakeWorkoutsRepo()
    logs = FakeWorkoutLogsRepo()
    sets = FakeSetLogsRepo()
    historical_date = date(2026, 10, 15)

    start_strength_session(
        workout_id="workout-1",
        request=StrengthSessionStartRequest(performed_date=historical_date),
        current_user=user(),
        workouts_repo=workouts,
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=logs,
        set_logs_repo=sets,
    )
    assert logs.item["performed_date"] == str(historical_date)

    autosave_strength_set(
        workout_id="workout-1",
        exercise_id="exercise-1",
        set_index=1,
        request=StrengthSetAutosaveRequest(
            reps=8,
            load_kg=60,
            feeling="right",
        ),
        current_user=user(),
        workouts_repo=workouts,
        exercises_repo=FakeExercisesRepo(),
        workout_logs_repo=logs,
        set_logs_repo=sets,
    )
    assert logs.item["performed_date"] == str(historical_date)
    assert sets.items[0]["reps"] == 8
