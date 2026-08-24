from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.api.main import app


class StatefulMealPrepRepository:
    def __init__(self):
        self.reset()

    def reset(self):
        self.item = {
            "id": "batch-1",
            "user_id": "authenticated-user",
            "recipe_id": "recipe-1",
            "name": "Chili",
            "status": "available",
            "portions_prepared": 2,
            "portions_remaining": 2,
            "prepared_at": "2026-09-01",
            "expires_at": "2026-09-02",
            "calories_per_portion": 500,
            "protein_per_portion": 35,
            "carbs_per_portion": 45,
            "fat_per_portion": 15,
        }

    def list_available(self, user_id):
        if (
            self.item["user_id"] == user_id
            and self.item["status"] == "available"
            and self.item["portions_remaining"] > 0
        ):
            return [self.item]
        return []

    def get_by_id(self, batch_id, user_id):
        if (
            batch_id == self.item["id"]
            and user_id == self.item["user_id"]
        ):
            return self.item
        return None

    def update(self, batch_id, user_id, payload):
        item = self.get_by_id(batch_id, user_id)
        if item is None:
            return None
        item.update(payload)
        return item


class StatefulMealsRepository:
    def __init__(self):
        self.reset()

    def reset(self):
        self.logged = []

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        # Historical routine intentionally empty:
        # the first recommendation should come from inventory alone.
        return []

    def list_for_date_compatible(self, user_id, log_date):
        return [
            item
            for item in self.logged
            if item["user_id"] == user_id
            and item["date"] == str(log_date)
        ]

    def create(self, payload):
        item = {
            "id": f"meal-{len(self.logged) + 1}",
            **payload,
        }
        self.logged.append(item)
        return item


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
        return []


class FakeActivitiesRepository:
    def list_for_date(self, user_id, log_date):
        return []


class FakeWeightRepository:
    def latest(self, user_id):
        return {
            "id": "w1",
            "date": "2026-08-31",
            "weight": 80.0,
        }


inventory = StatefulMealPrepRepository()
meals = StatefulMealsRepository()


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


@pytest.fixture(autouse=True)
def overrides():
    inventory.reset()
    meals.reset()

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_daily_logs_repository] = (
        lambda: FakeDailyLogsRepository()
    )
    app.dependency_overrides[get_meals_repository] = (
        lambda: meals
    )
    app.dependency_overrides[get_activities_repository] = (
        lambda: FakeActivitiesRepository()
    )
    app.dependency_overrides[get_weight_repository] = (
        lambda: FakeWeightRepository()
    )
    app.dependency_overrides[get_meal_prep_repository] = (
        lambda: inventory
    )

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_decision_to_log_to_budget_loop():
    decision_before = client.get(
        "/days/2026-09-01/meals/lunch/decision"
    )
    assert decision_before.status_code == 200

    before_payload = decision_before.json()
    recommendation = before_payload["recommended"]

    assert recommendation["source"] == "meal_prep"
    assert recommendation["batch_id"] == "batch-1"
    assert recommendation["name"] == "Chili"
    assert recommendation["portions_remaining"] == 2
    assert recommendation["waste_risk"] == "high"

    budget_before_response = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget_before_response.status_code == 200
    budget_before = budget_before_response.json()

    assert budget_before["actual"]["consumed_kcal"] == 0
    available_before = budget_before["budget"]["available_kcal"]

    logged = client.post(
        "/meal-prep/batch-1/log",
        json={
            "date": "2026-09-01",
            "meal_type": "Pranzo",
        },
    )
    assert logged.status_code == 200

    log_payload = logged.json()
    assert log_payload["meal"]["name"] == "Chili"
    assert log_payload["meal"]["calories"] == 500
    assert log_payload["inventory"]["portions_remaining"] == 1

    budget_after_response = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget_after_response.status_code == 200
    budget_after = budget_after_response.json()

    assert budget_after["actual"]["consumed_kcal"] == 500
    assert budget_after["actual"]["protein_consumed_g"] == 35
    assert budget_after["budget"]["available_kcal"] == (
        available_before - 500
    )

    decision_after = client.get(
        "/days/2026-09-01/meals/lunch/decision"
    )
    assert decision_after.status_code == 200

    after_recommendation = decision_after.json()["recommended"]
    assert after_recommendation["source"] == "meal_prep"
    assert after_recommendation["portions_remaining"] == 1


def test_last_logged_portion_removes_batch_from_future_decisions():
    inventory.item["portions_remaining"] = 1

    first_decision = client.get(
        "/days/2026-09-01/meals/dinner/decision"
    )
    assert first_decision.status_code == 200
    assert (
        first_decision.json()["recommended"]["source"]
        == "meal_prep"
    )

    logged = client.post(
        "/meal-prep/batch-1/log",
        json={
            "date": "2026-09-01",
            "meal_type": "Cena",
        },
    )
    assert logged.status_code == 200

    assert logged.json()["inventory"]["status"] == "finished"
    assert logged.json()["inventory"]["portions_remaining"] == 0

    next_decision = client.get(
        "/days/2026-09-01/meals/dinner/decision"
    )
    assert next_decision.status_code == 200

    payload = next_decision.json()
    assert payload["inventory_candidates"] == []
    assert payload["recommended"] is None


def test_meal_prep_log_uses_one_source_of_truth():
    response = client.post(
        "/meal-prep/batch-1/log",
        json={
            "date": "2026-09-01",
            "meal_type": "Pranzo",
        },
    )
    assert response.status_code == 200

    assert len(meals.logged) == 1
    assert inventory.item["portions_remaining"] == 1

    budget = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget.status_code == 200

    payload = budget.json()
    assert payload["actual"]["meal_count"] == 1
    assert payload["actual"]["consumed_kcal"] == 500

    # Budget reads the real meal; it does not create a second copy.
    assert len(meals.logged) == 1
