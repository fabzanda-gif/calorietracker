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


@pytest.fixture(autouse=True)
def overrides():
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
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_options_work_without_supabase_learning_configuration(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200
    prefs = response.json()["decision_preferences"]

    assert prefs["preferred_mode"] is None
    assert prefs["preferred_lens"] is None
    assert prefs["preferred_source"] is None
    assert prefs["mode_learning_source"] is None
    assert prefs["lens_learning_source"] is None
    assert prefs["source_learning_source"] is None
    assert prefs["outcome_evidence"] == {
        "item_count": 0,
        "observed_count": 0,
    }
