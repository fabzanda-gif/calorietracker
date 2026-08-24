import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.api.main import app


class FakeDailyLogsRepository:
    def get_for_date_compatible(self, user_id, log_date):
        return {
            "date": str(log_date),
            "day_type": "Ufficio",
            "activity_plan": "Riposo",
        }

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return [
            {"date": d, "day_type": "Ufficio"}
            for d in [
                "2026-08-04",
                "2026-08-11",
                "2026-08-18",
                "2026-08-25",
            ]
        ]


class FakeMealsRepository:
    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return [
            {
                "date": d,
                "meal_type": "Pranzo",
                "name": "Pranzo Ufficio",
                "calories": 650,
                "protein": 35,
                "carbs": 70,
                "fat": 18,
            }
            for d in [
                "2026-08-04",
                "2026-08-11",
                "2026-08-18",
                "2026-08-25",
            ]
        ]

    def list_for_date_compatible(self, user_id, log_date):
        return []


class FakeActivitiesRepository:
    def list_for_date(self, user_id, log_date):
        return []


class FakeWeightRepository:
    def latest(self, user_id):
        return {
            "id": "w1",
            "date": "2026-08-31",
            "weight": 80.0,
        }


class FakeMealPrepRepository:
    def list_available(self, user_id):
        return [
            {
                "id": "batch-1",
                "recipe_id": "recipe-1",
                "name": "Chili",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-09-02",
                "calories_per_portion": 500,
                "protein_per_portion": 35,
                "carbs_per_portion": 45,
                "fat_per_portion": 15,
            }
        ]


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
        metadata={
            "height": 180,
            "birth_date": "1990-01-01",
            "gender": "Uomo",
            "goal_mode": "maintenance",
        },
    )


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = lambda: FakeDailyLogsRepository()
    app.dependency_overrides[get_meals_repository] = lambda: FakeMealsRepository()
    app.dependency_overrides[get_activities_repository] = lambda: FakeActivitiesRepository()
    app.dependency_overrides[get_weight_repository] = lambda: FakeWeightRepository()
    app.dependency_overrides[get_meal_prep_repository] = lambda: FakeMealPrepRepository()
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_meal_decision_route_is_registered():
    assert (
        "/days/{day_date}/meals/{meal_slot}/decision"
        in app.openapi()["paths"]
    )


def test_lunch_decision_prefers_available_meal_prep():
    response = client.get(
        "/days/2026-09-01/meals/lunch/decision"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meal_type"] == "Pranzo"
    assert payload["recommended"]["source"] == "meal_prep"
    assert payload["recommended"]["name"] == "Chili"
    assert payload["recommended"]["priority"] == "high"
    assert payload["prediction"]["source"] == "routine"
    assert payload["prediction"]["value"] == "Pranzo Ufficio"


def test_unknown_slot_is_404():
    response = client.get(
        "/days/2026-09-01/meals/brunch/decision"
    )
    assert response.status_code == 404
