from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_ingredients_repository,
    get_meal_ingredients_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_pantry_repository,
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

    def create_compatible(self, payload):
        return self.create(payload)

    def delete(self, meal_id, user_id):
        self.logged = [
            item
            for item in self.logged
            if not (
                item["id"] == meal_id
                and item["user_id"] == user_id
            )
        ]


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
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        # These scenarios do not provide historical activity.
        # Missing days count as zero in the 7-day baseline.
        return []

    def list_for_date(self, user_id, log_date):
        return []


class StatefulPantryRepository:
    def __init__(self):
        self.reset()

    def reset(self):
        self.item = {
            "id": "pantry-1",
            "user_id": "authenticated-user",
            "ingredient_id": "ingredient-1",
            "quantity": 400.0,
            "quantity_mode": "weight",
            "unit": "g",
        }

    def get_by_id(self, item_id, user_id):
        if (
            self.item is not None
            and item_id == self.item["id"]
            and user_id == self.item["user_id"]
        ):
            return self.item
        return None

    def update(self, item_id, user_id, payload):
        item = self.get_by_id(item_id, user_id)
        if item is None:
            return None
        item.update(payload)
        return item

    def delete(self, item_id, user_id):
        if self.get_by_id(item_id, user_id):
            self.item = None


class FakeIngredientsRepository:
    def get_by_id(self, ingredient_id, user_id):
        if ingredient_id != "ingredient-1":
            return None
        return {
            "id": "ingredient-1",
            "user_id": user_id,
            "name": "Lasagna funghi",
            "calories_per_100g": 187,
            "protein_per_100g": 10.5,
            "carbs_per_100g": 18,
            "fat_per_100g": 8.5,
        }


class StatefulMealIngredientsRepository:
    def __init__(self):
        self.reset()

    def reset(self):
        self.items = []

    def create(self, payload):
        item = {
            "id": f"component-{len(self.items) + 1}",
            **payload,
        }
        self.items.append(item)
        return item

    def delete_for_meal(self, meal_id):
        self.items = [
            item
            for item in self.items
            if item["meal_id"] != meal_id
        ]


class FakeWeightRepository:
    def latest(self, user_id):
        return {
            "id": "w1",
            "date": "2026-08-31",
            "weight": 80.0,
        }


inventory = StatefulMealPrepRepository()
meals = StatefulMealsRepository()
pantry = StatefulPantryRepository()
meal_ingredients = StatefulMealIngredientsRepository()


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
    pantry.reset()
    meal_ingredients.reset()

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
    app.dependency_overrides[get_pantry_repository] = (
        lambda: pantry
    )
    app.dependency_overrides[get_ingredients_repository] = (
        lambda: FakeIngredientsRepository()
    )
    app.dependency_overrides[get_meal_ingredients_repository] = (
        lambda: meal_ingredients
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



def test_pantry_log_consumes_inventory_and_updates_budget():
    budget_before = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget_before.status_code == 200
    available_before = (
        budget_before.json()["budget"]["available_kcal"]
    )

    logged = client.post(
        "/meals/pantry-log",
        json={
            "date": "2026-09-01",
            "meal_type": "Pranzo",
            "pantry_item_id": "pantry-1",
            "quantity_g": 200,
        },
    )

    assert logged.status_code == 201
    payload = logged.json()
    assert payload["meal"]["name"] == "Lasagna funghi"
    assert payload["meal"]["calories"] == 374
    assert payload["meal"]["protein"] == 21
    assert payload["inventory"]["quantity"] == 200
    assert payload["consumed_grams"] == 200
    assert len(meal_ingredients.items) == 1

    budget_after = client.get(
        "/days/2026-09-01/budget"
    )
    assert budget_after.status_code == 200
    budget = budget_after.json()

    assert budget["actual"]["meal_count"] == 1
    assert budget["actual"]["consumed_kcal"] == 374
    assert budget["actual"]["protein_consumed_g"] == 21
    assert budget["budget"]["available_kcal"] == (
        available_before - 374
    )


def test_pantry_log_rejects_unavailable_quantity_without_side_effects():
    response = client.post(
        "/meals/pantry-log",
        json={
            "date": "2026-09-01",
            "meal_type": "Cena",
            "pantry_item_id": "pantry-1",
            "quantity_g": 450,
        },
    )

    assert response.status_code == 409
    assert pantry.item["quantity"] == 400
    assert meals.logged == []
    assert meal_ingredients.items == []
