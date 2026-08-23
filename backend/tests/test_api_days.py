import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user, 
    get_daily_logs_repository,
    get_meals_repository,
)
from backend.api.main import app


class FakeMealsRepository:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return []


class FakeDailyLogsRepository:
    def __init__(self):
        self.last_get = None
        self.last_range = None

    def get_for_date_compatible(self, user_id, log_date):
        self.last_get = (user_id, str(log_date))
        return {
            "id": "daily-1",
            "date": str(log_date),
            "weight": 80.1,
            "steps": 7000,
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        }

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        self.last_range = (
            user_id,
            str(start_date),
            str(end_date),
        )
        return []


fake_repo = FakeDailyLogsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_repo():
    return fake_repo


def override_meals_repo():
    return FakeMealsRepository()


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = override_repo
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_day_route_is_registered():
    paths = app.openapi()["paths"]

    assert "/days/{day_date}" in paths


def test_get_day_builds_product_level_day_model():
    response = client.get("/days/2026-08-25")

    assert response.status_code == 200
    payload = response.json()

    assert fake_repo.last_get == (
        "authenticated-user",
        "2026-08-25",
    )

    assert payload["date"] == "2026-08-25"
    assert payload["context"] == {
        "value": "Ufficio",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }
    assert payload["activity_plan"] == {
        "value": "Attiva",
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }
    assert payload["actual"] == {
        "weight": 80.1,
        "steps": 7000,
    }

    assert payload["meals"]["breakfast"]["state"] == "unknown"
    assert payload["meals"]["breakfast"]["value"] is None
