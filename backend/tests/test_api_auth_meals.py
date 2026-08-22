from fastapi.testclient import TestClient

from backend.api.dependencies import CurrentUser, get_current_user, get_meals_repository
from backend.api.main import app


class FakeMealsRepository:
    def list_for_date_compatible(self, user_id, log_date):
        assert user_id == "authenticated-user"
        assert str(log_date) == "2026-08-22"
        return [{"id": 1, "name": "Colazione Casa", "calories": 185}]


def override_current_user():
    return CurrentUser(id="authenticated-user", access_token="fake-token")


def override_meals_repo():
    return FakeMealsRepository()


def test_authenticated_meals():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    client = TestClient(app)
    response = client.get("/meals/2026-08-22")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    app.dependency_overrides.clear()


def test_missing_token_returns_401():
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    client = TestClient(app)
    response = client.get("/meals/2026-08-22")
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_invalid_date_returns_422_when_authenticated():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    client = TestClient(app)
    response = client.get("/meals/not-a-date")
    assert response.status_code == 422
    app.dependency_overrides.clear()
