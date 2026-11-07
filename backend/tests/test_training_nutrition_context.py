from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from backend.api.dependencies import CurrentUser
from backend.api.main import app
from backend.api.routers.training_nutrition_context import get_training_nutrition_week
from backend.services.training_nutrition_context import TrainingNutritionContextService


START = date(2026, 11, 2)


def build(**overrides):
    data = dict(
        start_date=START,
        days=7,
        meals=[],
        planned_running=[],
        planned_strength=[],
        actual_activities=[],
        completed_strength=[],
        metadata={},
    )
    data.update(overrides)
    return TrainingNutritionContextService().build(**data)


def test_week_joins_real_training_and_existing_logged_macros_only():
    result = build(
        meals=[
            {"date": "2026-11-02", "calories": 550,
             "protein": 35, "carbs": 60, "fat": 18},
            {"date": "2026-11-02", "calories": 900,
             "protein": 50, "carbs": 95, "fat": 30},
        ],
        planned_running=[
            {"id": "run-1", "scheduled_date": "2026-11-02",
             "activity_type": "running", "status": "planned"},
        ],
        planned_strength=[
            {"id": "gym-1", "scheduled_date": "2026-11-03",
             "status": "planned"},
        ],
        actual_activities=[
            {"date": "2026-11-02", "activity_type": "running",
             "planned_activity_id": "run-1", "burned_calories": 700},
        ],
        completed_strength=[
            {"id": "log-1", "strength_workout_id": "gym-1",
             "performed_date": "2026-11-03", "status": "completed"},
        ],
        metadata={"protein_goal_enabled": True, "protein_goal_g": 120},
    )
    monday, tuesday = result["days"][:2]
    assert monday["training"]["running_completed"] == 1
    assert monday["training"]["running_planned"] == 0
    assert tuesday["training"]["strength_completed"] == 1
    assert tuesday["training"]["strength_planned"] == 0
    assert monday["logged_macros"] == {
        "calories_kcal": 1450, "protein_g": 85,
        "carbs_g": 155, "fat_g": 48,
    }
    assert monday["protein_target_g"] == 120
    assert monday["protein_remaining_g"] == 35
    assert tuesday["protein_remaining_g"] is None
    assert tuesday["protein_target_status"] == "not_logged"
    assert result["summary"]["completed_training_days"] == 2
    assert result["policy"]["calorie_target_changed"] is False
    assert result["policy"]["planned_activity_calories_added"] is False


def test_skipped_sessions_and_non_running_activities_do_not_count():
    result = build(
        planned_running=[
            {"id": "skipped", "scheduled_date": "2026-11-02",
             "activity_type": "running", "status": "skipped"},
            {"id": "cycling", "scheduled_date": "2026-11-02",
             "activity_type": "cycling", "status": "planned"},
        ],
        planned_strength=[
            {"id": "cancelled", "scheduled_date": "2026-11-02",
             "status": "cancelled"},
        ],
        actual_activities=[
            {"date": "2026-11-02", "activity_type": "steps"},
        ],
    )
    monday = result["days"][0]
    assert monday["training_context"] == "no_training_logged"
    assert result["summary"]["training_days"] == 0


def test_absent_meals_are_unknown_not_zero_intake_failure():
    result = build(
        planned_strength=[
            {"id": "gym", "scheduled_date": "2026-11-02", "status": "planned"},
        ],
        metadata={"protein_goal_enabled": True, "protein_goal_g": 100},
    )
    monday = result["days"][0]
    assert monday["training_context"] == "training_planned"
    assert monday["meal_count"] == 0
    assert monday["protein_remaining_g"] is None
    assert monday["protein_target_status"] == "not_logged"
    assert result["policy"]["macro_targets_changed"] is False


def test_unconfigured_protein_target_is_not_invented():
    result = build(
        meals=[{"date": "2026-11-02", "protein": 60}],
        metadata={"protein_goal_g": 145, "protein_goal_enabled": False},
    )
    assert result["days"][0]["protein_target_g"] is None
    assert result["days"][0]["protein_target_status"] == "not_configured"


def test_malformed_or_negative_values_cannot_inflate_intake():
    result = build(meals=[
        {"date": "2026-11-02", "protein": "-100",
         "carbs": "not a number", "fat": "nan", "calories": 250},
    ])
    assert result["days"][0]["logged_macros"] == {
        "calories_kcal": 250, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
    }


class FakeMealsRepo:
    def __init__(self):
        self.calls = []

    def list_date_range(self, user, start, end, columns=None):
        self.calls.append((user, str(start), str(end), columns))
        return []


class FakeRangeRepo:
    def __init__(self):
        self.calls = []

    def list_range(self, user, start, end):
        self.calls.append((user, str(start), str(end)))
        return []

    def list_date_range(self, user, start, end):
        self.calls.append((user, str(start), str(end)))
        return []


class FakeWeightRepo:
    def latest(self, user):
        assert user == "account-1"
        return None


def test_api_scopes_every_read_to_authenticated_user():
    meals = FakeMealsRepo()
    planned = FakeRangeRepo()
    strength = FakeRangeRepo()
    logs = FakeRangeRepo()
    actual = FakeRangeRepo()
    response = get_training_nutrition_week(
        start_date=START,
        days=7,
        current_user=CurrentUser(
            id="account-1", access_token="token",
        ),
        meals_repo=meals,
        planned_repo=planned,
        strength_repo=strength,
        logs_repo=logs,
        activities_repo=actual,
        weight_repo=FakeWeightRepo(),
    )
    assert len(response["days"]) == 7
    assert "/training-nutrition/week" in app.openapi()["paths"]
    assert meals.calls[0][:3] == (
        "account-1", "2026-11-02", "2026-11-08",
    )
    assert all(
        repo.calls == [("account-1", "2026-11-02", "2026-11-08")]
        for repo in [planned, strength, logs, actual]
    )
