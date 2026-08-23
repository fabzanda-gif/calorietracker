from types import SimpleNamespace

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

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {"date": "2026-08-04", "day_type": "Ufficio"},
            {"date": "2026-08-11", "day_type": "Ufficio"},
            {"date": "2026-08-18", "day_type": "Ufficio"},
            {"date": "2026-08-25", "day_type": "Ufficio"},
        ]


class FakeMealsRepository:
    def __init__(self):
        self.created = []
        self.exists = False

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {
                "date": "2026-08-04",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 300,
                "protein": 17,
                "carbs": 34,
                "fat": 9,
            },
            {
                "date": "2026-08-11",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 35,
                "fat": 10,
            },
            {
                "date": "2026-08-18",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 320,
                "protein": 19,
                "carbs": 36,
                "fat": 11,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 35,
                "fat": 10,
            },
        ]

    def breakfast_exists(self, user_id, log_date):
        return self.exists

    def create_compatible(self, payload):
        self.created.append(payload)
        self.exists = True
        return SimpleNamespace(
            data=[
                {
                    "id": "new-breakfast",
                    **payload,
                }
            ]
        )


fake_meals = FakeMealsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_daily_logs():
    return FakeDailyLogsRepository()


def override_meals():
    return fake_meals


@pytest.fixture(autouse=True)
def api_overrides():
    fake_meals.created.clear()
    fake_meals.exists = False

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = override_daily_logs
    app.dependency_overrides[get_meals_repository] = override_meals

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_confirm_breakfast_route_is_registered():
    assert (
        "/days/{day_date}/meals/breakfast/confirm"
        in app.openapi()["paths"]
    )


def test_confirm_predicted_breakfast_creates_meal():
    response = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["confirmed"] is True
    assert payload["item"]["name"] == "Colazione Ufficio"
    assert payload["item"]["calories"] == 310
    assert payload["item"]["protein"] == 18
    assert payload["item"]["carbs"] == 35
    assert payload["item"]["fat"] == 10

    assert len(fake_meals.created) == 1


def test_second_confirmation_is_rejected_as_duplicate():
    first = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )
    second = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(fake_meals.created) == 1
