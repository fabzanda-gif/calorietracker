import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
)
from backend.api.main import app


class FakeDailyLogsRepository:
    def get_for_date_compatible(self, user_id, log_date):
        return {
            "date": str(log_date),
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        }

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return [
            {"date": "2026-08-04", "day_type": "Ufficio"},
            {"date": "2026-08-11", "day_type": "Ufficio"},
            {"date": "2026-08-18", "day_type": "Ufficio"},
            {"date": "2026-08-25", "day_type": "Ufficio"},
        ]


class FakeMealsRepository:
    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return [
            {
                "date": "2026-08-04",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 300,
                "protein": 17,
            },
            {
                "date": "2026-08-11",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
            },
            {
                "date": "2026-08-18",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 320,
                "protein": 19,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
            },
        ]


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_daily_logs_repo():
    return FakeDailyLogsRepository()


def override_meals_repo():
    return FakeMealsRepository()


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = (
        override_daily_logs_repo
    )
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_day_endpoint_exposes_high_confidence_breakfast_prediction():
    response = client.get("/days/2026-09-01")

    assert response.status_code == 200
    payload = response.json()

    breakfast = payload["meals"]["breakfast"]

    assert breakfast["value"] == "Colazione Ufficio"
    assert breakfast["state"] == "predicted"
    assert breakfast["source"] == "routine"
    assert breakfast["confidence_level"] == "high"
    assert breakfast["day_context"] == "Ufficio"
    assert breakfast["estimated_calories"] == 310
    assert breakfast["estimated_protein_g"] == 18
