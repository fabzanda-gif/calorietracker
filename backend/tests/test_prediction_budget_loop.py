from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.api.main import app


class StatefulMealsRepository:
    """
    Shared fake repository so a confirmed prediction becomes visible to the
    budget endpoint in the same test, mirroring the real database flow.
    """

    def __init__(self):
        self.created = []
        self.breakfast_logged = False

    def reset(self):
        self.created.clear()
        self.breakfast_logged = False

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        # Historical routine used by MealMemoryService.
        return [
            {
                "date": "2026-08-04",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 300,
                "protein": 17,
                "carbs": 34,
                "fat": 9,
            },
            {
                "date": "2026-08-11",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 35,
                "fat": 10,
            },
            {
                "date": "2026-08-18",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 320,
                "protein": 19,
                "carbs": 36,
                "fat": 11,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 35,
                "fat": 10,
            },
        ]

    def list_for_date_compatible(self, user_id, log_date):
        return [
            item
            for item in self.created
            if item["user_id"] == user_id
            and item["date"] == str(log_date)
        ]

    def breakfast_exists(self, user_id, log_date):
        return self.breakfast_logged

    def create_compatible(self, payload):
        item = {
            "id": f"meal-{len(self.created) + 1}",
            **payload,
        }
        self.created.append(item)

        if payload.get("meal_type") == "Colazione":
            self.breakfast_logged = True

        return SimpleNamespace(data=[item])


class FakeDailyLogsRepository:
    def get_for_date_compatible(self, user_id, log_date):
        return {
            "date": str(log_date),
            "day_type": "Ufficio",
            "activity_plan": "Riposo",
        }

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {"date": "2026-08-04", "day_type": "Ufficio"},
            {"date": "2026-08-11", "day_type": "Ufficio"},
            {"date": "2026-08-18", "day_type": "Ufficio"},
            {"date": "2026-08-25", "day_type": "Ufficio"},
        ]


class FakeActivitiesRepository:
    def list_for_date(self, user_id, log_date):
        return []


class FakeWeightRepository:
    def latest(self, user_id):
        return {
            "id": "weight-1",
            "date": "2026-08-31",
            "weight": 80.0,
        }


meals_repo = StatefulMealsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
        metadata={
            "height": 180,
            "birth_date": "1990-01-01",
            "gender": "Uomo",
            "goal_mode": "maintenance",
            "protein_goal_enabled": True,
            "protein_goal_g": 150,
        },
    )


def override_meals():
    return meals_repo


def override_daily_logs():
    return FakeDailyLogsRepository()


def override_activities():
    return FakeActivitiesRepository()


def override_weight():
    return FakeWeightRepository()


@pytest.fixture(autouse=True)
def api_overrides():
    meals_repo.reset()

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals
    app.dependency_overrides[get_daily_logs_repository] = override_daily_logs
    app.dependency_overrides[get_activities_repository] = override_activities
    app.dependency_overrides[get_weight_repository] = override_weight

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_confirmed_prediction_immediately_reduces_available_budget():
    before = client.get("/days/2026-09-01/budget")
    assert before.status_code == 200

    before_payload = before.json()
    before_available = before_payload["budget"]["available_kcal"]

    assert before_payload["actual"]["consumed_kcal"] == 0
    assert before_payload["actual"]["protein_consumed_g"] == 0

    confirm = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )
    assert confirm.status_code == 200

    confirmed = confirm.json()["item"]

    assert confirmed["name"] == "Colazione Ufficio"
    assert confirmed["calories"] == 310
    assert confirmed["protein"] == 18

    after = client.get("/days/2026-09-01/budget")
    assert after.status_code == 200

    after_payload = after.json()
    after_budget = after_payload["budget"]

    assert after_payload["actual"]["consumed_kcal"] == 310
    assert after_payload["actual"]["protein_consumed_g"] == 18

    assert after_budget["available_kcal"] == (
        before_available - 310
    )
    assert after_budget["protein_remaining_g"] == 132


def test_prediction_confirmation_and_budget_share_single_meal_source_of_truth():
    confirm = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )
    assert confirm.status_code == 200

    assert len(meals_repo.created) == 1

    budget_response = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget_response.status_code == 200

    payload = budget_response.json()

    assert payload["actual"]["meal_count"] == 1
    assert payload["actual"]["consumed_kcal"] == 310

    # No copy or secondary budget-side log is created.
    assert len(meals_repo.created) == 1


def test_second_confirmation_does_not_change_budget_twice():
    first = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )
    assert first.status_code == 200

    budget_after_first = client.get(
        "/days/2026-09-01/budget"
    ).json()["budget"]["available_kcal"]

    second = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )
    assert second.status_code == 409

    budget_after_second = client.get(
        "/days/2026-09-01/budget"
    ).json()["budget"]["available_kcal"]

    assert budget_after_second == budget_after_first
    assert len(meals_repo.created) == 1
