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


def test_legacy_options_test_does_not_require_real_supabase():
    app.dependency_overrides[get_current_user] = override_current_user
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

    try:
        response = TestClient(app).get(
            "/days/2026-09-01/meals/dinner/options",
            params={"mode": "order"},
        )

        assert response.status_code == 200
        assert response.json()["decision_preferences"] == {
            "preferred_mode": None,
            "preferred_lens": None,
            "preferred_source": None,
        }
    finally:
        app.dependency_overrides.clear()
