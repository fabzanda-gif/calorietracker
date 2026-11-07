"""Release-candidate authenticated HTTP journey using isolated in-memory stores.

This simulates distinct bearer-authenticated identities end-to-end through the
FastAPI routing/dependency layer. It is deliberately NOT proof of live JWT or
database RLS; those need independent production smoke checks.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser, get_current_user, get_onboarding_repository,
    get_exercise_library_repository, get_strength_plans_repository,
    get_strength_workouts_repository, get_strength_workout_exercises_repository,
    get_strength_workout_logs_repository, get_strength_set_logs_repository,
    get_authenticated_supabase, get_meals_repository, get_activities_repository,
    get_planned_activities_repository, get_weight_repository,
    get_training_coach_adjustments_repository,
    get_training_coach_preferences_repository,
)
from backend.api.main import app
from backend.api.routers import program_v2, coach as coach_router
from backend.api.routers.athlete_state import get_athlete_state_repo


TODAY = date.today()
DAY = TODAY.isoformat()
A = "e2e-user-a"
B = "e2e-user-b"
DEMO = "e2e-demo"


class Store:
    def __init__(self):
        self.prefs = {}
        self.food = {}
        self.training = {}
        self.days = {}
        self.muscles = {}
        self.exercise_prefs = defaultdict(dict)
        self.workouts = {}
        self.workout_exercises = {}
        self.logs = {}
        self.sets = {}
        self.plans = {}
        self.changes = []
        self.next_id = 0
        self.hinge_approved = False
        self.catalog = [
            self.exercise(pattern) for pattern in (
                "squat", "hinge", "horizontal_push", "horizontal_pull",
                "vertical_push", "vertical_pull", "core", "isolation"
            )
        ]
        self.meals = {
            A: [{"id": "meal-a", "date": DAY, "calories": 1750,
                 "protein": 110, "carbs": 210, "fat": 50}],
            B: [{"id": "meal-b", "date": DAY, "calories": 1050,
                 "protein": 55, "carbs": 115, "fat": 35}],
        }

    def id(self, prefix):
        self.next_id += 1
        return f"{prefix}-{self.next_id}"

    @staticmethod
    def exercise(pattern):
        return {
            "id": f"library-{pattern}",
            "slug": pattern.replace("_", "-"),
            "legacy_key": pattern,
            "name": pattern.replace("_", " ").title(),
            "name_default": pattern,
            "movement_pattern": pattern,
            "training_role": "secondary",
            "active": True,
            "approved_for_generation": pattern != "hinge",
            "strength_score": 4,
            "hypertrophy_score": 4,
            "general_fitness_score": 4,
            "body_part": "back",
            "target_muscle": "lats",
            "equipment": [{"key": "dumbbell", "role": "required"}],
        }


class Onboarding:
    def __init__(self, s): self.s = s
    def get_preferences(self, owner): return self.s.prefs.get(owner)
    def get_nutrition_profile(self, owner): return self.s.food.get(owner)
    def get_training_profile(self, owner): return self.s.training.get(owner)
    def list_preferred_days(self, owner): return self.s.days.get(owner, [])
    def list_muscle_priorities(self, owner): return self.s.muscles.get(owner, [])
    def upsert_preferences(self, data):
        self.s.prefs[data["user_id"]] = dict(data)
        return dict(data)
    def upsert_nutrition_profile(self, data):
        self.s.food[data["user_id"]] = dict(data)
        return dict(data)
    def upsert_training_profile(self, data):
        self.s.training[data["user_id"]] = dict(data)
        return dict(data)
    def replace_preferred_days(self, owner, weekdays): self.s.days[owner] = list(weekdays)
    def replace_muscle_priorities(self, owner, keys): self.s.muscles[owner] = list(keys)


class Library:
    def __init__(self, s): self.s = s
    def get_exercise(self, identifier, **kwargs):
        return next((x for x in self.s.catalog if identifier in
                     (x["id"], x["slug"], x["legacy_key"])), None)
    def list_exercises(self, **kwargs):
        return [
            {**x, "approved_for_generation": (
                x["approved_for_generation"] or (
                    x["movement_pattern"] == "hinge" and self.s.hinge_approved
                ))}
            for x in self.s.catalog
            if not kwargs.get("approved_only") or x["approved_for_generation"]
            or (x["movement_pattern"] == "hinge" and self.s.hinge_approved)
        ]
    def list_user_preferences(self, owner):
        return [
            {"exercise_id": eid, "preference": pref}
            for eid, pref in self.s.exercise_prefs[owner].items()
        ]
    def save_user_preference(self, owner, eid, preference):
        self.s.exercise_prefs[owner][eid] = preference
        return {"exercise_id": eid, "preference": preference}
    def remove_user_preference(self, owner, eid):
        self.s.exercise_prefs[owner].pop(eid, None)


class Workouts:
    def __init__(self, s): self.s = s
    def create(self, payload):
        item = {"id": self.s.id("workout"), **payload}
        self.s.workouts[item["id"]] = item
        return dict(item)
    def create_many(self, data): return [self.create(item) for item in data]
    def get(self, owner, workout_id):
        item = self.s.workouts.get(workout_id)
        return dict(item) if item and item["user_id"] == owner else None
    def update_status(self, *, user_id, workout_id, status):
        item = self.s.workouts.get(workout_id)
        if not item or item["user_id"] != user_id: return None
        item["status"] = status
        return dict(item)
    def list_date_range(self, owner, start, end):
        return [dict(w) for w in self.s.workouts.values()
                if w["user_id"] == owner and
                str(start) <= w["scheduled_date"] <= str(end)]


class WorkoutExercises:
    def __init__(self, s): self.s = s
    def create(self, payload):
        item = {"id": self.s.id("exercise"), **payload}
        self.s.workout_exercises[item["id"]] = item
        return dict(item)
    def create_many(self, data): return [self.create(item) for item in data]
    def list_for_workout(self, owner, wid):
        return [dict(x) for x in self.s.workout_exercises.values()
                if x["user_id"] == owner and x["strength_workout_id"] == wid]
    def get(self, owner, eid):
        item = self.s.workout_exercises.get(eid)
        return dict(item) if item and item["user_id"] == owner else None


class Logs:
    def __init__(self, s): self.s = s
    def get_for_workout(self, owner, wid):
        return next((dict(x) for x in self.s.logs.values()
                     if x["user_id"] == owner and
                     x["strength_workout_id"] == wid), None)
    def create(self, payload):
        item = {"id": self.s.id("log"), **payload}
        self.s.logs[item["id"]] = item
        return dict(item)
    def update(self, log_id, owner, payload):
        item = self.s.logs.get(log_id)
        if not item or item["user_id"] != owner: return None
        item.update(payload)
        return dict(item)
    def list_date_range(self, owner, start, end):
        return [dict(x) for x in self.s.logs.values()
                if x["user_id"] == owner and
                str(start) <= x["performed_date"] <= str(end)]


class Sets:
    def __init__(self, s): self.s = s
    def upsert_set(self, payload):
        key = (
            payload["user_id"], payload["strength_workout_log_id"],
            payload["strength_workout_exercise_id"], payload["set_index"]
        )
        self.s.sets[key] = {"id": self.s.id("set"), **payload}
        return dict(self.s.sets[key])
    def list_for_workout_log(self, owner, log_id):
        return [dict(x) for x in self.s.sets.values()
                if x["user_id"] == owner and
                x["strength_workout_log_id"] == log_id]


class Plans:
    def __init__(self, s): self.s = s
    def create(self, payload):
        item = {"id": self.s.id("plan"), "status": "active", **payload}
        self.s.plans[item["id"]] = item
        return dict(item)
    def list_for_user(self, owner):
        return [dict(x) for x in self.s.plans.values() if x["user_id"] == owner]
    def update_status(self, *, plan_id, user_id, status):
        item = self.s.plans.get(plan_id)
        if item and item["user_id"] == user_id:
            item["status"] = status
            return dict(item)
    def delete(self, plan_id, owner):
        item = self.s.plans.get(plan_id)
        if item and item["user_id"] == owner: self.s.plans.pop(plan_id)


class Athlete:
    def __init__(self, s): self.s = s
    def training_profile(self, owner): return self.s.training.get(owner)
    def completed_strength_history(self, owner, *, as_of, days):
        lower = (as_of - timedelta(days=days - 1)).isoformat()
        filtered = [dict(x) for x in self.s.logs.values()
                    if x["user_id"] == owner and
                    x.get("status") == "completed" and
                    lower <= x["performed_date"] <= as_of.isoformat()]
        ids = {x["id"] for x in filtered}
        selected_sets = [dict(x) for x in self.s.sets.values()
                         if x["user_id"] == owner and
                         x["strength_workout_log_id"] in ids]
        return {
            "logs": filtered,
            "sets": selected_sets,
            "exercises": [dict(x) for x in self.s.workout_exercises.values()
                          if x["user_id"] == owner],
            "workouts": [dict(x) for x in self.s.workouts.values()
                         if x["user_id"] == owner],
        }


class ListRepo:
    def __init__(self, s, kind): self.s, self.kind = s, kind
    def list_date_range(self, owner, start, end, columns=None):
        if self.kind == "meals":
            return [dict(x) for x in self.s.meals.get(owner, [])
                    if str(start) <= x["date"] <= str(end)]
        return []
    def list_range(self, owner, start, end): return []


class Weight:
    def latest(self, owner): return {"weight": 80}
    def history_range(self, owner, start, end): return []


class Priority:
    def get_priority(self, owner): return "balanced"


class Adjustments:
    def __init__(self, s): self.s = s
    def get_for_signal(self, **kwargs): return None
    def get_for_target_action(self, **kwargs): return None
    def list_recent(self, **kwargs): return [
        dict(x) for x in self.s.changes if x["user_id"] == kwargs["user_id"]
    ]
    def create(self, data):
        item = {"id": self.s.id("advice"), **data}
        self.s.changes.append(item)
        return dict(item)


class PreferenceQuery:
    def __init__(self, s): self.s, self.owner = s, None
    def select(self, columns): return self
    def eq(self, column, value):
        assert column == "user_id"
        self.owner = value
        return self
    def execute(self):
        return SimpleNamespace(data=[
            {"exercise_id": eid, "preference": pref}
            for eid, pref in self.s.exercise_prefs[self.owner].items()
        ])


class FakeSupabase:
    def __init__(self, s): self.s = s
    def table(self, name):
        assert name == "training_exercise_preferences"
        return PreferenceQuery(self.s)


@pytest.fixture
def http_journey(monkeypatch):
    monkeypatch.delenv("DEMO_ACCOUNT_USER_ID", raising=False)
    monkeypatch.delenv("DEMO_SOURCE_USER_ID", raising=False)
    s = Store()
    o = Onboarding(s)
    lib = Library(s)
    workout = Workouts(s)
    exercises = WorkoutExercises(s)
    logs = Logs(s)
    sets = Sets(s)
    plans = Plans(s)
    athlete = Athlete(s)

    def authenticate(authorization: str | None = Header(default=None)):
        tokens = {
            "Bearer e2e-a": CurrentUser(id=A, access_token="e2e-a"),
            "Bearer e2e-b": CurrentUser(id=B, access_token="e2e-b"),
            "Bearer e2e-demo": CurrentUser(
                id=DEMO, access_token="e2e-demo",
                read_only=True,
            ),
        }
        if authorization not in tokens:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return tokens[authorization]

    overrides = {
        get_current_user: authenticate,
        get_onboarding_repository: lambda: o,
        get_exercise_library_repository: lambda: lib,
        get_strength_plans_repository: lambda: plans,
        get_strength_workouts_repository: lambda: workout,
        get_strength_workout_exercises_repository: lambda: exercises,
        get_strength_workout_logs_repository: lambda: logs,
        get_strength_set_logs_repository: lambda: sets,
        get_athlete_state_repo: lambda: athlete,
        get_authenticated_supabase: lambda: FakeSupabase(s),
        get_meals_repository: lambda: ListRepo(s, "meals"),
        get_activities_repository: lambda: ListRepo(s, "activities"),
        get_planned_activities_repository: lambda: ListRepo(s, "planned"),
        get_weight_repository: lambda: Weight(),
        get_training_coach_adjustments_repository: lambda: Adjustments(s),
        get_training_coach_preferences_repository: lambda: Priority(),
    }
    app.dependency_overrides.update(overrides)
    monkeypatch.setattr(program_v2, "OnboardingRepository", lambda _: o)
    monkeypatch.setattr(program_v2, "AthleteStateRepository", lambda _: athlete)
    monkeypatch.setattr(coach_router, "_coach_context", lambda **kw: {
        "as_of": DAY,
        "recent_start": DAY,
        "future_end": DAY,
        "events": [],
        "recovery_alerts": [],
        "proposals": [],
    })
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, s
    finally:
        for key in overrides: app.dependency_overrides.pop(key, None)


def call(client, method, path, token="e2e-a", **kwargs):
    return client.request(
        method, path, headers={"Authorization": f"Bearer {token}"},
        **kwargs,
    )


def test_complete_authenticated_two_user_journey(http_journey):
    client, store = http_journey
    assert client.get("/onboarding/status").status_code == 401

    first = call(client, "GET", "/onboarding/status")
    assert first.status_code == 200, first.text
    assert first.json()["next_step"] == "core"

    core = call(client, "PUT", "/onboarding/core", json={
        "primary_goal": "hypertrophy",
        "food_enabled": True,
        "training_enabled": True,
    })
    assert core.status_code == 200, core.text
    assert core.json()["next_step"] == "food_setup"

    food = call(client, "PUT", "/onboarding/nutrition", json={
        "weight_strategy": "maintenance",
        "calorie_adjustment_kcal": 0,
        "protein_target_mode": "manual",
        "protein_target_g": 130,
        "macro_tracking_enabled": True,
    })
    assert food.status_code == 200, food.text
    assert food.json()["next_step"] == "training_setup"

    training = call(client, "PUT", "/onboarding/training", json={
        "experience_level": "beginner",
        "sessions_per_week": 2,
        "session_duration_minutes": 60,
        "planning_horizon": "weekly",
        "schedule_flexibility": "flexible",
        "priority_muscles": ["back"],
    })
    assert training.status_code == 200, training.text
    assert training.json()["completed"] is True

    pref = call(client, "PUT", "/exercises/horizontal-push/preference",
                json={"preference": "excluded"})
    assert pref.status_code == 200, pref.text
    own = call(client, "GET", "/exercises/preferences")
    other = call(client, "GET", "/exercises/preferences", token="e2e-b")
    assert len(own.json()["items"]) == 1
    assert other.json()["items"] == []

    free = call(client, "POST", "/strength/workouts/free",
                json={"title": "E2E palestra", "performed_date": DAY})
    assert free.status_code == 201, free.text
    wid = free.json()["workout"]["id"]
    created_exercise = call(
        client, "POST", f"/strength/workouts/{wid}/exercises",
        json={"library_exercise_id": "squat", "target_sets": 3},
    )
    assert created_exercise.status_code == 201, created_exercise.text
    eid = created_exercise.json()["exercise"]["id"]

    started = call(client, "POST", f"/strength/workouts/{wid}/session",
                   json={"performed_date": DAY})
    assert started.status_code == 200, started.text
    assert started.json()["workout_log"]["status"] == "draft"

    saved = call(client, "PUT",
                 f"/strength/workouts/{wid}/exercises/{eid}/sets/1",
                 json={"reps": 8, "load_kg": 40, "feeling": "right"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["set"]["reps"] == 8

    complete = call(client, "POST", f"/strength/workouts/{wid}/complete",
                    json={"duration_minutes": 45})
    assert complete.status_code == 200, complete.text
    assert complete.json()["set_count"] == 1
    assert complete.json()["workout_log"]["status"] == "completed"

    state = call(client, "GET", f"/athlete-state?as_of={DAY}")
    other_state = call(client, "GET", f"/athlete-state?as_of={DAY}", token="e2e-b")
    assert state.status_code == 200, state.text
    assert state.json()["last_28_days"]["completed_sessions"] == 1
    assert state.json()["last_28_days"]["total_sets"] == 1
    assert other_state.status_code == 200, other_state.text
    assert other_state.json()["last_28_days"]["completed_sessions"] == 0

    # The current real catalog has no approved hinge. Fail closed.
    inp = {
        "start_date": DAY,
        "goal": "hypertrophy",
        "total_weeks": 4,
        "allowed_equipment": ["dumbbell"],
    }
    preview = call(client, "POST", "/strength/plans/v2/preview", json=inp)
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready_for_activation"] is False
    assert "hinge" in preview.json()["missing_movement_patterns"]
    blocked = call(client, "POST", "/strength/plans/v2", json=inp)
    assert blocked.status_code == 409, blocked.text
    assert store.plans == {}

    # A reviewed, approved hinge unlocks plan generation in test data.
    store.hinge_approved = True
    reopened = call(client, "POST", "/strength/plans/v2/preview", json=inp)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["ready_for_activation"] is False
    assert "horizontal_push" in reopened.json()["missing_movement_patterns"]
    assert all(
        x["exercise_id"] != "library-horizontal_push"
        for w in reopened.json()["workouts"] for x in w["exercises"]
    )
    store.exercise_prefs[A].clear()
    reopened = call(client, "POST", "/strength/plans/v2/preview", json=inp)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["ready_for_activation"] is True
    activated = call(client, "POST", "/strength/plans/v2", json=inp)
    assert activated.status_code == 201, activated.text
    assert activated.json()["created"] is True
    assert activated.json()["workout_count"] == 8

    # Coach analyzes but does not change workouts on reconciliation.
    before = {
        k: dict(v) for k, v in store.workouts.items()
    }
    reconciled = call(client, "POST", "/coach/reconcile",
                      json={"as_of": DAY})
    assert reconciled.status_code == 200, reconciled.text
    assert store.workouts == before

    food_context = call(client, "GET",
                        f"/training-nutrition/week?start_date={DAY}&days=1")
    assert food_context.status_code == 200, food_context.text
    assert food_context.json()["days"][0]["logged_macros"]["protein_g"] == 110

    cross = call(client, "GET",
                 f"/cross-training/timeline?start_date={DAY}&days=1")
    assert cross.status_code == 200, cross.text
    assert cross.json()["summary"]["strength_sessions"] >= 1

    adaptive = call(client, "GET", "/adaptive-macros/preview")
    assert adaptive.status_code == 200, adaptive.text
    assert adaptive.json()["proposal"] is None
    assert adaptive.json()["policy"]["auto_apply"] is False

    # A second user cannot access the first user's workout, log or preference.
    other_workout = call(
        client, "POST", f"/strength/workouts/{wid}/session",
        token="e2e-b", json={"performed_date": DAY},
    )
    assert other_workout.status_code == 404, other_workout.text
    assert store.workouts[wid]["user_id"] == A
    assert all(x["user_id"] == A for x in store.logs.values())


def test_demo_is_read_only_through_mutating_http_endpoints(http_journey):
    client, state = http_journey
    writes = [
        ("PUT", "/onboarding/core", {
            "primary_goal": "strength",
            "food_enabled": False, "training_enabled": True,
        }),
        ("PUT", "/onboarding/nutrition", {
            "weight_strategy": "maintenance",
        }),
        ("PUT", "/onboarding/training", {
            "experience_level": "beginner", "sessions_per_week": 2,
            "session_duration_minutes": 60, "planning_horizon": "weekly",
        }),
        ("PUT", "/exercises/squat/preference", {"preference": "preferred"}),
        ("POST", "/strength/workouts/free", {"title": "should not create"}),
        ("POST", "/strength/plans/v2", {
            "start_date": DAY, "goal": "strength",
            "allowed_equipment": ["dumbbell"],
        }),
        ("POST", "/coach/reconcile", {"as_of": DAY}),
        ("POST", "/adaptive-macros/apply", {
            "preview_id": "a" * 64, "confirm": True,
            "logging_complete_confirmed": True,
        }),
    ]
    for method, path, body in writes:
        response = call(client, method, path, token="e2e-demo", json=body)
        assert response.status_code == 403, (path, response.status_code, response.text)
    assert state.workouts == {}
    assert state.logs == {}
    assert state.prefs == {}
    assert state.exercise_prefs[DEMO] == {}
