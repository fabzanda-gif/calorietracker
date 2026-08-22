from fastapi.testclient import TestClient

from backend.api.dependencies import get_meals_repository
from backend.api.main import app


class FakeMealsRepository:
    def list_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
        assert user_id == "test-user"
        assert str(log_date) == "2026-08-22"
        return [
            {
                "id": 1,
                "meal_type": "Colazione",
                "name": "Colazione Casa",
                "calories": 185,
                "protein": 6.0,
                "carbs": 40.0,
                "fat": 6.0,
            }
        ]


def override_meals_repo():
    return FakeMealsRepository()


app.dependency_overrides[
    get_meals_repository
] = override_meals_repo

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_meals_for_date():
    response = client.get(
        "/meals/2026-08-22",
        params={"user_id": "test-user"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["date"] == "2026-08-22"
    assert payload["count"] == 1
    assert payload["items"][0]["name"] == "Colazione Casa"


def test_invalid_date_returns_422():
    response = client.get(
        "/meals/not-a-date",
        params={"user_id": "test-user"},
    )
    assert response.status_code == 422


def test_missing_user_id_returns_422():
    response = client.get(
        "/meals/2026-08-22"
    )
    assert response.status_code == 422
