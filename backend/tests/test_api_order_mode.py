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

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return []


class FakeMealsRepository:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return []

    def list_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
        return []

    def list_history_compatible(self, user_id):
        return (
            [
                {
                    "date": "2026-08-01",
                    "meal_type": "Cena",
                    "name": "Pizza Margherita",
                    "base_name": "Pizza Margherita",
                    "category": "takeaway",
                    "calories": 800,
                    "protein": 30,
                    "carbs": 100,
                    "fat": 25,
                },
                {
                    "date": "2026-08-08",
                    "meal_type": "Cena",
                    "name": "Pizza Margherita",
                    "base_name": "Pizza Margherita",
                    "category": "takeaway",
                    "calories": 840,
                    "protein": 32,
                    "carbs": 105,
                    "fat": 26,
                },
                {
                    "date": "2026-08-15",
                    "meal_type": "Cena",
                    "name": "Poke Salmone",
                    "base_name": "Poke Salmone",
                    "category": "delivery",
                    "calories": 650,
                    "protein": 40,
                    "carbs": 70,
                    "fat": 20,
                },
            ],
            True,
        )


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
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_daily_logs_repository] = (
        lambda: FakeDailyLogsRepository()
    )
    app.dependency_overrides[get_meals_repository] = (
        lambda: FakeMealsRepository()
    )
    app.dependency_overrides[get_activities_repository] = (
        lambda: FakeActivitiesRepository()
    )
    app.dependency_overrides[get_weight_repository] = (
        lambda: FakeWeightRepository()
    )
    app.dependency_overrides[get_meal_prep_repository] = (
        lambda: FakeMealPrepRepository()
    )
    app.dependency_overrides[get_recipes_repository] = (
        lambda: FakeRecipesRepository()
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_order_mode_returns_known_takeaway_and_delivery():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["mode"] == "order"
    assert payload["candidate_count"] == 2
    assert payload["known_order_count"] == 2
    assert payload["empty_reason"] is None

    assert {
        item["source"]
        for item in payload["candidates"]
    } == {
        "takeaway",
        "delivery",
    }


def test_repeated_takeaway_is_aggregated_in_api():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    pizza = next(
        item
        for item in payload["candidates"]
        if item["name"] == "Pizza Margherita"
    )

    assert pizza["order_count"] == 2
    assert pizza["calories"] == 820
    assert pizza["protein_g"] == 31


def test_order_mode_is_ranked_with_three_lenses_when_possible():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    # Only two known unique orders exist, so ranking correctly returns two
    # distinct options rather than duplicating one to force three cards.
    assert len(payload["options"]) == 2
    assert len({
        option["candidate"]["name"]
        for option in payload["options"]
    }) == 2


def test_non_order_mode_still_excludes_order_sources():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "cook"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["candidate_count"] == 0
    assert all(
        item["source"] not in {"takeaway", "delivery"}
        for item in payload["candidates"]
    )
