import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_recipes_repository,
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
                "meal_type": "Cena",
                "name": "Cena Routine",
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

    def list_history_compatible(self, user_id):
        # This legacy mode test intentionally has no order history.
        return ([], True)


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
                "name": "Chili pronto",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-09-02",
                "calories_per_portion": 500,
                "protein_per_portion": 35,
                "carbs_per_portion": 45,
                "fat_per_portion": 15,
                "taste_score": 8,
            }
        ]


class FakeRecipesRepository:
    def list_available(self, user_id):
        return [
            {
                "id": "r1",
                "name": "Pasta",
                "meal_type": "Cena",
                "calories": 600,
                "protein": 30,
                "carbs": 80,
                "fat": 15,
                "taste_score": 9,
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
def overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = lambda: FakeDailyLogsRepository()
    app.dependency_overrides[get_meals_repository] = lambda: FakeMealsRepository()
    app.dependency_overrides[get_activities_repository] = lambda: FakeActivitiesRepository()
    app.dependency_overrides[get_weight_repository] = lambda: FakeWeightRepository()
    app.dependency_overrides[get_meal_prep_repository] = lambda: FakeMealPrepRepository()
    app.dependency_overrides[get_recipes_repository] = lambda: FakeRecipesRepository()
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_default_mode_is_auto():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "auto"
    assert payload["mode_label"] == "Automatico"
    assert payload["candidate_count"] == 3


def test_ready_mode_keeps_only_meal_prep():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "ready"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["source"] == "meal_prep"


def test_cook_mode_excludes_ready_food():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "cook"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert {
        item["source"]
        for item in payload["candidates"]
    } == {"routine", "recipe"}


def test_order_mode_is_empty_without_order_history():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 0
    assert payload["empty_reason"] == "no_known_order_options"


def test_out_mode_is_empty_until_restaurant_sources_exist():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 0
    assert payload["empty_reason"] == "no_known_eating_out_options"


def test_invalid_mode_returns_422():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "whatever"},
    )
    assert response.status_code == 422
