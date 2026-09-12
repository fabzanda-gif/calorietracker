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
    def __init__(self, history=None):
        self.history = history or []

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return []

    def list_for_date_compatible(self, user_id, log_date):
        return []

    def list_history_compatible(self, user_id):
        return (self.history, True)


class FakeActivitiesRepository:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        # These scenarios do not provide historical activity.
        # Missing days count as zero in the 7-day baseline.
        return []

    def list_for_date(self, user_id, log_date):
        return []


class FakeWeightRepository:
    def latest(self, user_id):
        return {"id": "w1", "date": "2026-08-31", "weight": 80.0}


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


def install_overrides(history=None):
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = lambda: FakeDailyLogsRepository()
    app.dependency_overrides[get_meals_repository] = lambda: FakeMealsRepository(history)
    app.dependency_overrides[get_activities_repository] = lambda: FakeActivitiesRepository()
    app.dependency_overrides[get_weight_repository] = lambda: FakeWeightRepository()
    app.dependency_overrides[get_meal_prep_repository] = lambda: FakeMealPrepRepository()
    app.dependency_overrides[get_recipes_repository] = lambda: FakeRecipesRepository()


@pytest.fixture(autouse=True)
def overrides():
    install_overrides()
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def restaurant(name, log_date):
    return {
        "date": log_date,
        "meal_type": "Cena",
        "name": name,
        "base_name": name,
        "category": "restaurant",
        "calories": 700,
        "protein": 35,
        "carbs": 80,
        "fat": 25,
    }


def test_new_user_gets_three_generic_out_options():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["candidate_count"] == 3
    assert payload["known_eating_out_count"] == 0
    assert payload["generic_eating_out_count"] == 3
    assert all(
        item["source"] == "generic_eating_out"
        for item in payload["candidates"]
    )


def test_one_known_option_is_filled_to_three():
    install_overrides([restaurant("Bistecca", "2026-08-30")])

    payload = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    ).json()

    assert payload["candidate_count"] == 3
    assert payload["known_eating_out_count"] == 1
    assert payload["generic_eating_out_count"] == 2


def test_three_known_options_disable_generic_fallback():
    install_overrides([
        restaurant("Bistecca", "2026-08-30"),
        restaurant("Risotto", "2026-08-20"),
        restaurant("Tacos", "2026-08-10"),
    ])

    payload = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    ).json()

    assert payload["known_eating_out_count"] == 3
    assert payload["generic_eating_out_count"] == 0
    assert payload["candidate_count"] == 3


def test_generic_out_does_not_leak_into_auto_mode():
    payload = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "auto"},
    ).json()

    assert payload["generic_eating_out_count"] == 0
    assert all(
        item["source"] != "generic_eating_out"
        for item in payload["candidates"]
    )


def test_generic_out_does_not_leak_into_order_mode():
    payload = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    ).json()

    assert payload["generic_eating_out_count"] == 0
    assert all(
        item["source"] != "generic_eating_out"
        for item in payload["candidates"]
    )
