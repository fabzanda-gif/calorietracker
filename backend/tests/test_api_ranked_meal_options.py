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
    def list_history_compatible(self, user_id):
        # This test predates order-history candidates. Keep its original
        # scenario unchanged by explicitly providing no order history.
        return ([], True)

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
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

    def list_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
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
                "name": "Meal prep chili",
                "status": "available",
                "portions_remaining": 2,
                "expires_at": "2026-09-02",
                "calories_per_portion": 450,
                "protein_per_portion": 40,
                "carbs_per_portion": 45,
                "fat_per_portion": 12,
                "taste_score": 8,
            }
        ]


class FakeRecipesRepository:
    def list_available(self, user_id):
        return [
            {
                "id": "r1",
                "name": "Chicken rice",
                "meal_type": "Pranzo",
                "calories": 550,
                "protein": 45,
                "carbs": 60,
                "fat": 14,
                "taste_score": 7,
            },
            {
                "id": "r2",
                "name": "Favourite pasta",
                "meal_type": "Pranzo",
                "calories": 700,
                "protein": 30,
                "carbs": 90,
                "fat": 20,
                "taste_score": 10,
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


def test_ranked_options_route_is_registered():
    assert (
        "/days/{day_date}/meals/{meal_slot}/options"
        in app.openapi()["paths"]
    )


def test_ranked_options_uses_real_candidate_sources():
    response = client.get(
        "/days/2026-09-01/meals/lunch/options"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["meal_type"] == "Pranzo"
    assert payload["candidate_count"] == 4

    sources = {
        item["source"]
        for item in payload["candidates"]
    }

    assert sources == {
        "meal_prep",
        "routine",
        "recipe",
    }

    assert len(payload["options"]) == 3

    lenses = [
        item["lens"]
        for item in payload["options"]
    ]

    assert lenses == [
        "calorie",
        "balanced",
        "taste",
    ]


def test_options_are_distinct():
    response = client.get(
        "/days/2026-09-01/meals/lunch/options"
    )

    options = response.json()["options"]
    names = [
        item["candidate"]["name"]
        for item in options
    ]

    assert len(names) == len(set(names))


def test_unknown_slot_returns_404():
    response = client.get(
        "/days/2026-09-01/meals/brunch/options"
    )

    assert response.status_code == 404


def test_auto_mode_exposes_replanned_recommendation():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "recommended" in payload
    assert payload["recommended"] is not None

    recommended = payload["recommended"]

    assert "candidate" in recommended
    assert "strategy" in recommended
    assert "reason" in recommended
    assert "adaptation" in recommended


def test_explicit_mode_recommendation_respects_filtered_candidates():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "ready"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "recommended" in payload

    recommended = payload["recommended"]

    if recommended is not None:
        allowed_ids = {
            candidate.get("id")
            for candidate in payload["candidates"]
            if candidate.get("id") is not None
        }
        allowed_source_ids = {
            candidate.get("source_id")
            for candidate in payload["candidates"]
            if candidate.get("source_id") is not None
        }

        candidate = recommended["candidate"]

        assert candidate["source"] == "meal_prep"
        assert (
            candidate.get("id") in allowed_ids
            or candidate.get("source_id") in allowed_source_ids
        )
