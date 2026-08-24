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

        # Frequent and recent Poke.
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
                    "name": "Poke Salmone",
                    "base_name": "Poke Salmone",
                    "category": "delivery",
                    "calories": 650,
                    "protein": 40,
                    "carbs": 70,
                    "fat": 20,
                }
            )

        # Rare, older Pizza.
        rows.append(
            {
                "date": "2026-06-01",
                "meal_type": "Cena",
                "name": "Pizza Margherita",
                "base_name": "Pizza Margherita",
                "category": "takeaway",
                "calories": 800,
                "protein": 30,
                "carbs": 100,
                "fat": 25,
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
            "protein_goal_enabled": True,
            "protein_goal_g": 150,
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


def test_known_orders_are_enriched_with_personalization():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200
    candidates = response.json()["candidates"]

    poke = next(
        item
        for item in candidates
        if item["name"] == "Poke Salmone"
    )

    pizza = next(
        item
        for item in candidates
        if item["name"] == "Pizza Margherita"
    )

    assert poke["known_order"] is True
    assert poke["personalization_strength"] > pizza["personalization_strength"]
    assert poke["taste_score"] > pizza["taste_score"]


def test_frequent_recent_order_is_promoted_by_personalized_ranking():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    ranked_poke = next(
        option
        for option in payload["options"]
        if option["candidate"]["name"] == "Poke Salmone"
    )

    assert (
        ranked_poke["candidate"]["personalization_reason"]
        == "frequent_and_recent_order"
    )
    assert ranked_poke["candidate"]["personalization_strength"] == 1.0
    assert ranked_poke["candidate"]["taste_score"] > 8.0

    # Ranking intentionally avoids duplicating the same candidate across
    # the three lenses. Poke may therefore occupy calorie/balanced before
    # the taste lens is assigned.
    names = [
        option["candidate"]["name"]
        for option in payload["options"]
    ]
    assert len(names) == len(set(names))


def test_generic_fallback_remains_unpersonalized():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    generic = next(
        item
        for item in response.json()["candidates"]
        if item["source"] == "generic_order"
    )

    assert "personalization_strength" not in generic
    assert generic["taste_score"] == 5.0
