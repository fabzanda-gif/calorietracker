import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_optional_decision_selections_repository,
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
        return (
            [
                {
                    "date": "2026-08-30",
                    "meal_type": "Cena",
                    "name": "Poke",
                    "base_name": "Poke",
                    "category": "delivery",
                    "calories": 600,
                    "protein": 40,
                    "carbs": 65,
                    "fat": 18,
                },
                {
                    "date": "2026-08-20",
                    "meal_type": "Cena",
                    "name": "Pizza",
                    "base_name": "Pizza",
                    "category": "takeaway",
                    "calories": 650,
                    "protein": 30,
                    "carbs": 80,
                    "fat": 22,
                },
            ],
            True,
        )


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


class FakeDecisionSelectionsRepository:
    def list_for_user(self, user_id, *, limit=100):
        return [
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "source": "delivery",
                },
            },
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "source": "delivery",
                },
            },
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "source": "delivery",
                },
            },
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
    app.dependency_overrides[get_optional_decision_selections_repository] = (
        lambda: FakeDecisionSelectionsRepository()
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_options_expose_learned_decision_preferences():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200
    prefs = response.json()["decision_preferences"]

    assert prefs["preferred_mode"] == "order"
    assert prefs["preferred_lens"] == "taste"
    assert prefs["preferred_source"] == "delivery"


def test_preferred_source_candidate_is_enriched():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    candidates = response.json()["candidates"]

    delivery = next(
        item
        for item in candidates
        if item["source"] == "delivery"
    )

    # API response keeps raw mode candidates; ranked options contain feedback
    # enriched candidates.
    ranked_delivery = next(
        option["candidate"]
        for option in response.json()["options"]
        if option["candidate"]["source"] == "delivery"
    )

    assert "decision_feedback_boost" not in delivery
    assert ranked_delivery["decision_feedback_boost"] > 0
    assert (
        ranked_delivery["decision_feedback_reason"]
        == "preferred_source"
    )


def test_feedback_does_not_change_candidate_count():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    assert payload["candidate_count"] == len(
        payload["candidates"]
    )
