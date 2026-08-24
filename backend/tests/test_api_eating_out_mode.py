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
        return []


class FakeMealsRepository:
    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return []

    def list_for_date_compatible(self, user_id, log_date):
        return []

    def list_history_compatible(self, user_id):
        rows = []

        for d in [
            "2026-08-10",
            "2026-08-17",
            "2026-08-24",
            "2026-08-30",
        ]:
            rows.append(
                {
                    "date": d,
                    "meal_type": "Cena",
                    "name": "Ramen",
                    "base_name": "Ramen",
                    "category": "restaurant",
                    "calories": 750,
                    "protein": 35,
                    "carbs": 90,
                    "fat": 25,
                }
            )

        rows.append(
            {
                "date": "2026-06-01",
                "meal_type": "Cena",
                "name": "Sushi",
                "base_name": "Sushi",
                "category": "ristorante",
                "calories": 700,
                "protein": 30,
                "carbs": 95,
                "fat": 18,
            }
        )

        return (rows, True)


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
        return []


class FakeRecipesRepository:
    def list_available(self, user_id):
        return []


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


def test_out_mode_returns_known_eating_out_candidates():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["mode"] == "out"
    assert payload["candidate_count"] == 2
    assert payload["known_eating_out_count"] == 2
    assert payload["empty_reason"] is None

    assert all(
        item["source"] == "restaurant"
        for item in payload["candidates"]
    )


def test_frequent_recent_eating_out_is_personalized():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )

    ramen = next(
        item
        for item in response.json()["candidates"]
        if item["name"] == "Ramen"
    )

    sushi = next(
        item
        for item in response.json()["candidates"]
        if item["name"] == "Sushi"
    )

    assert ramen["personalization_strength"] > sushi["personalization_strength"]
    assert ramen["taste_score"] > sushi["taste_score"]


def test_out_mode_ranking_does_not_duplicate_candidates():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )

    options = response.json()["options"]

    names = [
        item["candidate"]["name"]
        for item in options
    ]

    assert len(names) == len(set(names))


def test_order_mode_does_not_include_restaurant_history():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200

    assert all(
        item["source"] != "restaurant"
        for item in response.json()["candidates"]
    )
