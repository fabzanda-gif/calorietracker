import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meal_prep_repository,
    get_meals_repository,
)
from backend.api.main import app


class FakeMealPrepRepository:
    def __init__(self):
        self.reset()

    def reset(self):
        self.item = {
            "id": "batch-1",
            "user_id": "authenticated-user",
            "name": "Chili",
            "status": "available",
            "portions_prepared": 3,
            "portions_remaining": 2,
            "calories_per_portion": 520,
            "protein_per_portion": 32,
            "carbs_per_portion": 58,
            "fat_per_portion": 15,
        }

    def get_by_id(self, batch_id, user_id):
        if (
            batch_id == self.item["id"]
            and user_id == self.item["user_id"]
        ):
            return self.item
        return None

    def update(self, batch_id, user_id, payload):
        self.item.update(payload)
        return self.item


class FakeMealsRepository:
    def __init__(self):
        self.created = None

    def create(self, payload):
        self.created = payload
        return {"id": "meal-1", **payload}


inventory = FakeMealPrepRepository()
meals = FakeMealsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def overrides():
    inventory.reset()
    meals.created = None
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_meal_prep_repository] = (
        lambda: inventory
    )
    app.dependency_overrides[get_meals_repository] = (
        lambda: meals
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_log_route_is_registered():
    assert (
        "/meal-prep/{batch_id}/log"
        in app.openapi()["paths"]
    )


def test_log_meal_prep_creates_meal_and_consumes_one():
    response = client.post(
        "/meal-prep/batch-1/log",
        json={
            "date": "2026-09-06",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["logged"] is True
    assert payload["meal"]["name"] == "Chili"
    assert payload["meal"]["date"] == "2026-09-06"
    assert payload["meal"]["meal_type"] == "Pranzo"
    assert payload["inventory"]["portions_remaining"] == 1


def test_missing_batch_returns_404():
    response = client.post(
        "/meal-prep/missing/log",
        json={
            "date": "2026-09-06",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 404
