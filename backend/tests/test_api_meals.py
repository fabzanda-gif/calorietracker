import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meals_repository,
)
from backend.api.main import app


class FakeMealsRepository:
    def list_for_date_compatible(self, user_id, log_date):
        assert user_id == "test-user"
        return [
            {
                "id": 1,
                "meal_type": "Colazione",
                "name": "Colazione Casa",
                "calories": 185,
            }
        ]


def override_current_user():
    return CurrentUser(
        id="test-user",
        access_token="fake-token",
    )


def override_meals_repo():
    return FakeMealsRepository()


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_get_meals_for_date():
    response = client.get("/meals/2026-08-22")
    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-08-22"
    assert payload["count"] == 1
    assert payload["items"][0]["name"] == "Colazione Casa"


def test_invalid_date_returns_422():
    response = client.get("/meals/not-a-date")
    assert response.status_code == 422
