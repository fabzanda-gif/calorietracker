from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.main import app
from backend.api.routers import athlete_state
from backend.repositories.athlete_state import AthleteStateRepository
from backend.services.athlete_state import AthleteStateService


def log(id, day, status="completed"):
    return {
        "id": id, "strength_workout_id": f"w-{id}", "performed_date": day,
        "status": status, "duration_minutes": 45,
    }


def test_state_excludes_drafts_and_outside_window():
    as_of = date(2026, 11, 7)
    history = {
        "logs": [
            log("a", "2026-11-07"),
            log("b", "2026-11-01"),
            log("c", "2026-10-22"),
            log("old", "2026-09-01"),
            log("draft", "2026-11-06", "draft"),
            log("future", "2026-11-08"),
        ],
        "sets": [
            {"strength_workout_log_id": "a", "strength_workout_exercise_id": "ex-a",
             "reps": 10, "load_kg": 40, "feeling": "hard"},
            {"strength_workout_log_id": "b", "strength_workout_exercise_id": "ex-a",
             "reps": 8, "load_kg": 45, "feeling": "right"},
            {"strength_workout_log_id": "draft", "strength_workout_exercise_id": "ex-a",
             "reps": 50, "load_kg": 150, "feeling": "hard"},
        ],
        "exercises": [
            {"id": "ex-a", "exercise_id": "library-1",
             "exercise_name": "Squat", "movement_pattern": "squat"}
        ],
        "workouts": [],
    }
    state = AthleteStateService().build(
        history=history, as_of=as_of, profile={"sessions_per_week": 3}
    )
    assert state["last_56_days"]["completed_sessions"] == 3
    assert state["recent_7_days"]["completed_sessions"] == 2
    assert state["last_28_days"]["volume_load_kg"] == 760
    assert state["recent_7_days"]["total_sets"] == 2
    assert state["most_logged_exercises"][0]["sessions"] == 2
    assert state["most_logged_exercises"][0]["best_load_kg"] == 45
    assert state["target_sessions_per_week"] == 3
    assert len(state["weekly"]) == 8
    assert state["last_completed_date"] == "2026-11-07"
    assert state["data_status"] == "limited"  # Third completed session has no saved sets.
    assert state["quality"]["sessions_without_sets"] == 1


def test_empty_history_is_explicitly_limited_not_a_fatigue_score():
    result = AthleteStateService().build(
        history={"logs": [], "sets": [], "exercises": []},
        as_of=date(2026, 11, 7),
    )
    assert result["data_status"] == "limited"
    assert result["consistency_ratio_last_4_weeks"] is None
    assert result["last_completed_date"] is None
    assert result["last_28_days"]["total_sets"] == 0
    assert result["scope"] == "strength_only"
    assert "recupero fisiologico" in result["note"]



def test_completed_session_without_sets_downgrades_data_quality():
    history = {
        "logs": [
            log("a", "2026-11-07"),
            log("b", "2026-11-05"),
            log("c", "2026-11-03"),
        ],
        "sets": [
            {"strength_workout_log_id": "a", "reps": 8, "load_kg": 40},
            {"strength_workout_log_id": "b", "reps": 8, "load_kg": 40},
        ],
        "exercises": [],
    }
    state = AthleteStateService().build(
        history=history, as_of=date(2026, 11, 7),
    )
    assert state["quality"]["sessions_without_sets"] == 1
    assert state["data_status"] == "limited"


def test_old_sessions_and_future_sets_never_leak_into_recent_windows():
    history = {
        "logs": [
            log("old", "2026-08-01"),
            log("now", "2026-11-07"),
        ],
        "sets": [
            {"strength_workout_log_id": "old", "reps": 1000, "load_kg": 1000},
            {"strength_workout_log_id": "now", "reps": 5, "load_kg": 10},
            {"strength_workout_log_id": "outside", "reps": 500, "load_kg": 100},
        ],
        "exercises": [],
    }
    state = AthleteStateService().build(
        history=history, as_of=date(2026, 11, 7),
    )
    assert state["last_56_days"]["volume_load_kg"] == 50.0
    assert state["last_56_days"]["total_sets"] == 1


class FakeRepository:
    def __init__(self):
        self.request = None

    def completed_strength_history(self, user_id, *, as_of, days):
        self.request = (user_id, as_of, days)
        return {"logs": [], "sets": [], "exercises": []}

    def training_profile(self, user_id):
        assert user_id == "user-1"
        return {"sessions_per_week": 3}


def test_athlete_state_endpoint_scopes_all_reads_to_authenticated_user():
    repo = FakeRepository()
    response = athlete_state.get_athlete_state(
        as_of=date(2026, 11, 7),
        current_user=CurrentUser(id="user-1", access_token="token"),
        repo=repo,
    )
    assert repo.request == ("user-1", date(2026, 11, 7), 56)
    assert response["target_sessions_per_week"] == 3
    assert "/athlete-state" in app.openapi()["paths"]


def test_athlete_state_rejects_future_date():
    with pytest.raises(HTTPException) as exc:
        athlete_state.get_athlete_state(
            as_of=date.today() + timedelta(days=1),
            current_user=CurrentUser(id="user-1", access_token="token"),
            repo=FakeRepository(),
        )
    assert exc.value.status_code == 422


class Query:
    def __init__(self, table, rows, calls):
        self.table = table
        self.rows = rows
        self.calls = calls
        self.filters = []

    def select(self, columns):
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def in_(self, name, values):
        self.filters.append((name, set(values)))
        return self

    def gte(self, name, value):
        return self

    def lte(self, name, value):
        return self

    def order(self, name, desc=False):
        return self

    def range(self, start, end):
        return self

    def limit(self, value):
        return self

    def execute(self):
        self.calls.append((self.table, self.filters.copy()))
        items = self.rows.get(self.table, [])
        for field, value in self.filters:
            if isinstance(value, set):
                items = [x for x in items if x.get(field) in value]
            else:
                items = [x for x in items if x.get(field) == value]
        return SimpleNamespace(data=items)


class Client:
    def __init__(self):
        self.calls = []
        self.rows = {
            "strength_workout_logs": [
                {**log("a", "2026-11-07"), "user_id": "user-1"},
                {**log("b", "2026-11-07"), "user_id": "other"},
            ],
            "strength_set_logs": [
                {"user_id": "user-1", "strength_workout_log_id": "a",
                 "strength_workout_exercise_id": "ex-1"},
                {"user_id": "other", "strength_workout_log_id": "b",
                 "strength_workout_exercise_id": "ex-2"},
            ],
            "strength_workouts": [
                {"id": "w-a", "user_id": "user-1"},
                {"id": "w-b", "user_id": "other"},
            ],
            "strength_workout_exercises": [
                {"id": "ex-1", "strength_workout_id": "w-a", "user_id": "user-1"},
                {"id": "ex-2", "strength_workout_id": "w-b", "user_id": "other"},
            ],
        }

    def table(self, name):
        return Query(name, self.rows, self.calls)


def test_repository_does_not_load_other_users_strength_data():
    client = Client()
    data = AthleteStateRepository(client).completed_strength_history(
        "user-1", as_of=date(2026, 11, 7)
    )
    assert [x["id"] for x in data["logs"]] == ["a"]
    assert len(data["sets"]) == 1
    assert [x["id"] for x in data["workouts"]] == ["w-a"]
    assert [x["id"] for x in data["exercises"]] == ["ex-1"]
    assert all(
        ("user_id", "user-1") in filters
        for _, filters in client.calls
    )
