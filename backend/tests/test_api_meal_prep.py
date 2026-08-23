import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meal_prep_repository,
    get_recipes_repository,
)
from backend.api.main import app


class FakeRecipesRepository:
    def get_personal_by_id(self, recipe_id, user_id):
        return {
            "id": recipe_id,
            "user_id": user_id,
            "name": "Chili",
            "recipe_servings": 4,
            "calories": 2000,
            "protein": 120,
            "carbs": 240,
            "fat": 60,
        }


class FakeMealPrepRepository:
    def __init__(self):
        self.items = {}

    def reset(self):
        self.items.clear()

    def list_all(self, user_id):
        return list(self.items.values())

    def list_available(self, user_id):
        return [
            item for item in self.items.values()
            if item["status"] == "available"
            and item["portions_remaining"] > 0
        ]

    def create(self, payload):
        item = {"id": "batch-1", **payload}
        self.items["batch-1"] = item
        return item

    def get_by_id(self, batch_id, user_id):
        item = self.items.get(batch_id)
        if item and item["user_id"] == user_id:
            return item
        return None

    def update(self, batch_id, user_id, payload):
        item = self.get_by_id(batch_id, user_id)
        if item is None:
            return None
        item.update(payload)
        return item


repo = FakeMealPrepRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_meal_prep():
    return repo


def override_recipes():
    return FakeRecipesRepository()


@pytest.fixture(autouse=True)
def api_overrides():
    repo.reset()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meal_prep_repository] = override_meal_prep
    app.dependency_overrides[get_recipes_repository] = override_recipes
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_meal_prep_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "/meal-prep" in paths
    assert "/meal-prep/{batch_id}/consume" in paths
    assert "/meal-prep/{batch_id}/status" in paths


def test_create_and_consume_batch():
    created = client.post(
        "/meal-prep",
        json={
            "recipe_id": "r1",
            "prepared_at": "2026-09-01",
            "portions_prepared": 3,
            "expires_at": "2026-09-05",
        },
    )

    assert created.status_code == 201
    assert created.json()["item"]["portions_remaining"] == 3

    consumed = client.post(
        "/meal-prep/batch-1/consume",
        json={"portions": 1},
    )

    assert consumed.status_code == 200
    assert consumed.json()["item"]["portions_remaining"] == 2


def test_quick_expired_update_removes_available_portions():
    client.post(
        "/meal-prep",
        json={
            "recipe_id": "r1",
            "prepared_at": "2026-09-01",
            "portions_prepared": 4,
        },
    )

    response = client.patch(
        "/meal-prep/batch-1/status",
        json={"status": "expired"},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["status"] == "expired"
    assert item["portions_remaining"] == 0


def test_available_only_excludes_finished_inventory():
    client.post(
        "/meal-prep",
        json={
            "recipe_id": "r1",
            "prepared_at": "2026-09-01",
            "portions_prepared": 1,
        },
    )

    client.post(
        "/meal-prep/batch-1/consume",
        json={"portions": 1},
    )

    response = client.get(
        "/meal-prep",
        params={"available_only": True},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0
