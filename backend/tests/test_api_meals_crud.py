import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meals_repository,
)
from backend.api.main import app


class FakeMealsRepository:
    def __init__(self):
        self.last_create = None
        self.last_update = None
        self.last_delete = None

    def create_compatible(self, payload):
        self.last_create = payload
        return SimpleNamespace(data=[{"id": "meal-1", **payload}])

    def update(self, meal_id, user_id, payload):
        self.last_update = (meal_id, user_id, payload)
        return {"id": meal_id, **payload}

    def delete(self, meal_id, user_id):
        self.last_delete = (meal_id, user_id)
        return True


fake_repo = FakeMealsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_meals_repo():
    return fake_repo


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_create_meal_uses_authenticated_user():
    response = client.post(
        "/meals",
        json={
            "date": "2026-08-22",
            "meal_type": "Colazione",
            "name": "Colazione Casa",
            "calories": 185,
            "protein": 6,
            "carbs": 40,
            "fat": 6,
        },
    )
    assert response.status_code == 201
    assert fake_repo.last_create["user_id"] == "authenticated-user"


def test_update_meal_is_user_scoped():
    response = client.patch(
        "/meals/meal-1",
        json={"calories": 200},
    )
    assert response.status_code == 200
    assert fake_repo.last_update == (
        "meal-1",
        "authenticated-user",
        {"calories": 200},
    )


def test_update_meal_rejects_empty_body():
    response = client.patch("/meals/meal-1", json={})
    assert response.status_code == 400


def test_delete_meal_is_user_scoped():
    response = client.delete("/meals/meal-1")
    assert response.status_code == 200
    assert fake_repo.last_delete == (
        "meal-1",
        "authenticated-user",
    )
