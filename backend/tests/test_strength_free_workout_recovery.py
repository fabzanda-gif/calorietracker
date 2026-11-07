from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api.core_main import app as core_app
from backend.api.dependencies import CurrentUser
from backend.api.routers import strength


def user(user_id="user-1", read_only=False):
    return CurrentUser(
        id=user_id,
        access_token="token",
        read_only=read_only,
    )


class Workouts:
    def __init__(self):
        self.rows = [{
            "id": "workout-1",
            "user_id": "user-1",
            "workout_kind": "free",
            "status": "planned",
            "title": "Free workout",
            "scheduled_date": "2026-11-06",
        }]
        self.calls = []
        self.created = False

    def list_recent_free(self, user_id, limit=30):
        self.calls.append(("list_recent_free", user_id, limit))
        return list(self.rows) if user_id == "user-1" else []

    def get(self, user_id, workout_id):
        self.calls.append(("get", user_id, workout_id))
        return next(
            (row for row in self.rows
             if row["id"] == workout_id and row["user_id"] == user_id),
            None,
        )

    def create(self, payload):
        self.created = True
        return {"id": "new", **payload}


class Exercises:
    def list_for_workout(self, user_id, workout_id):
        return ([{
            "id": "exercise-1",
            "strength_workout_id": workout_id,
            "exercise_name": "Bench press",
        }] if user_id == "user-1" else [])


class Logs:
    def __init__(self):
        self.rows = [{
            "id": "log-1",
            "strength_workout_id": "workout-1",
            "user_id": "user-1",
            "performed_date": "2026-11-06",
            "status": "draft",
        }]
        self.calls = []

    def list_for_workout_ids(self, user_id, ids):
        self.calls.append((user_id, ids))
        return [row for row in self.rows if row["user_id"] == user_id
                and row["strength_workout_id"] in ids]

    def get_for_workout(self, user_id, workout_id):
        return next(
            (row for row in self.rows
             if row["user_id"] == user_id
             and row["strength_workout_id"] == workout_id),
            None,
        )


class Sets:
    def list_for_workout_log(self, user_id, workout_log_id):
        return ([{
            "strength_workout_exercise_id": "exercise-1",
            "set_index": 1, "reps": 8, "load_kg": 75,
        }] if user_id == "user-1" else [])


def test_recent_free_history_returns_owned_draft_and_uses_batch_query():
    workouts, logs = Workouts(), Logs()
    result = strength.list_recent_free_strength_workouts(
        current_user=user(),
        workouts_repo=workouts,
        workout_logs_repo=logs,
    )
    assert result["count"] == 1
    assert result["items"][0]["workout_log"]["status"] == "draft"
    assert logs.calls == [("user-1", ["workout-1"])]
    assert workouts.calls == [("list_recent_free", "user-1", 30)]


def test_free_recovery_detail_returns_owner_scoped_saved_sets():
    result = strength.get_strength_workout_detail(
        workout_id="workout-1",
        current_user=user(),
        workouts_repo=Workouts(),
        exercises_repo=Exercises(),
        workout_logs_repo=Logs(),
        set_logs_repo=Sets(),
    )
    assert result["workout"]["exercises"][0]["exercise_name"] == "Bench press"
    assert result["workout_log"]["performed_date"] == "2026-11-06"
    assert result["sets"][0]["reps"] == 8


def test_other_user_cannot_read_free_workout_or_sets():
    result = strength.list_recent_free_strength_workouts(
        current_user=user("intruder"),
        workouts_repo=Workouts(),
        workout_logs_repo=Logs(),
    )
    assert result["count"] == 0
    with pytest.raises(HTTPException) as exc:
        strength.get_strength_workout_detail(
            workout_id="workout-1",
            current_user=user("intruder"),
            workouts_repo=Workouts(),
            exercises_repo=Exercises(),
            workout_logs_repo=Logs(),
            set_logs_repo=Sets(),
        )
    assert exc.value.status_code == 404


def test_demo_read_only_cannot_start_free_workout():
    workouts = Workouts()
    with pytest.raises(HTTPException) as exc:
        strength.create_free_strength_workout(
            request=strength.StrengthFreeWorkoutRequest(title="Attempt"),
            current_user=user(read_only=True),
            workouts_repo=workouts,
        )
    assert exc.value.status_code == 403
    assert workouts.created is False


def test_phase2_routes_are_published():
    paths = core_app.openapi()["paths"]
    assert "/strength/workouts/free/recent" in paths
    assert "/strength/workouts/{workout_id}/detail" in paths


def test_cannot_substitute_exercise_after_saving_sets():
    class ExerciseRows:
        updated = False

        def get(self, user_id, exercise_id):
            return {
                "id": exercise_id,
                "strength_workout_id": "workout-1",
                "exercise_id": "library-1",
            }

        def update(self, **kwargs):
            self.updated = True
            return {}

    class HasSets:
        def has_logged_sets_for_exercise(
            self, user_id, workout_log_id, exercise_id
        ):
            assert (user_id, workout_log_id, exercise_id) == (
                "user-1", "log-1", "exercise-1"
            )
            return True

    class Library:
        def get_exercise(self, identifier, language="it"):
            raise AssertionError(
                "Should reject before loading replacement"
            )

    exercises = ExerciseRows()
    with pytest.raises(HTTPException) as exc:
        strength.substitute_strength_exercise(
            workout_id="workout-1",
            exercise_id="exercise-1",
            request=strength.StrengthExerciseSubstituteRequest(
                library_exercise_id="replacement-1"
            ),
            current_user=user(),
            workouts_repo=Workouts(),
            exercises_repo=exercises,
            library_repo=Library(),
            workout_logs_repo=Logs(),
            set_logs_repo=HasSets(),
        )
    assert exc.value.status_code == 409
    assert exercises.updated is False
