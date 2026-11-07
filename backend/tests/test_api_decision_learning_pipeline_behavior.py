import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_optional_decision_selections_repository,
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

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {
                "id": "meal-poke",
                "date": "2026-08-30",
                "meal_type": "Cena",
                "name": "Poke",
                "calories": 600,
            }
        ]


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


class FakeSelectionsRepository:
    def list_for_user(self, user_id, *, limit=100):
        return [
            {
                "id": "s1",
                "date": "2026-08-30",
                "meal_slot": "dinner",
                "meal_type": "Cena",
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "name": "Poke",
                    "source": "delivery",
                    "calories": 600,
                },
            },
            {
                "id": "s2",
                "date": "2026-08-29",
                "meal_slot": "dinner",
                "meal_type": "Cena",
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "name": "Poke",
                    "source": "delivery",
                    "calories": 600,
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
    app.dependency_overrides[
        get_current_user
    ] = override_current_user
    app.dependency_overrides[
        get_daily_logs_repository
    ] = lambda: FakeDailyLogsRepository()
    app.dependency_overrides[
        get_meals_repository
    ] = lambda: FakeMealsRepository()
    app.dependency_overrides[
        get_activities_repository
    ] = lambda: FakeActivitiesRepository()
    app.dependency_overrides[
        get_weight_repository
    ] = lambda: FakeWeightRepository()
    app.dependency_overrides[
        get_meal_prep_repository
    ] = lambda: FakeMealPrepRepository()
    app.dependency_overrides[
        get_recipes_repository
    ] = lambda: FakeRecipesRepository()
    app.dependency_overrides[
        get_optional_decision_selections_repository
    ] = lambda: FakeSelectionsRepository()

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_refactor_preserves_outcome_aware_preferences():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    assert response.status_code == 200

    prefs = response.json()[
        "decision_preferences"
    ]

    assert prefs[
        "preferred_mode"
    ] == "order"
    assert prefs[
        "mode_learning_source"
    ] == "outcome"
    assert prefs[
        "preferred_source"
    ] == "delivery"
    assert prefs[
        "source_learning_source"
    ] == "outcome"
    assert prefs[
        "outcome_evidence"
    ] == {
        "item_count": 2,
        "observed_count": 1,
    }


def test_refactor_preserves_feedback_boost():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    ranked_delivery = next(
        option["candidate"]
        for option in response.json()["options"]
        if option["candidate"]["source"] == "delivery"
    )

    assert (
        ranked_delivery[
            "decision_feedback_boost"
        ]
        > 0
    )
