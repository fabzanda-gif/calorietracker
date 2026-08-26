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
    def __init__(self):
        self.today_meals = []

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
        return list(self.today_meals)


class FakeActivitiesRepository:
    def __init__(self):
        self.today_activities = []

    def list_for_date(self, user_id, log_date):
        return list(self.today_activities)


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


fake_meals = FakeMealsRepository()
fake_activities = FakeActivitiesRepository()


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
    fake_meals.today_meals.clear()
    fake_activities.today_activities.clear()

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_daily_logs_repository] = (
        lambda: FakeDailyLogsRepository()
    )
    app.dependency_overrides[get_meals_repository] = (
        lambda: fake_meals
    )
    app.dependency_overrides[get_activities_repository] = (
        lambda: fake_activities
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


def test_snack_replans_lunch_without_changing_routine_identity():
    fake_meals.today_meals.append(
        {
            "date": "2026-09-01",
            "meal_type": "Colazione",
            "name": "Breakfast",
            "calories": 300,
            "protein": 20,
            "carbs": 35,
            "fat": 8,
        }
    )

    before_budget_response = client.get(
        "/days/2026-09-01/budget"
    )
    before_options_response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert before_budget_response.status_code == 200
    assert before_options_response.status_code == 200

    before_budget = before_budget_response.json()["budget"]
    before_recommendation = (
        before_options_response.json()["recommended"]
    )

    assert before_recommendation is not None
    assert before_recommendation["strategy"] == "routine"
    assert before_recommendation["portion_multiplier"] == 1.0

    fake_meals.today_meals.append(
        {
            "date": "2026-09-01",
            "meal_type": "Spuntino",
            "name": "Large snack",
            "calories": 900,
            "protein": 10,
            "carbs": 100,
            "fat": 30,
        }
    )

    after_budget_response = client.get(
        "/days/2026-09-01/budget"
    )
    after_options_response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert after_budget_response.status_code == 200
    assert after_options_response.status_code == 200

    after_budget = after_budget_response.json()["budget"]
    after_recommendation = (
        after_options_response.json()["recommended"]
    )

    assert after_recommendation is not None

    assert (
        after_budget["available_kcal"]
        == before_budget["available_kcal"] - 900
    )

    assert (
        after_recommendation["strategy"]
        == "adapted_routine"
    )

    assert (
        after_recommendation["portion_multiplier"]
        < before_recommendation["portion_multiplier"]
    )

    assert (
        after_recommendation["candidate"]["calories"]
        < before_recommendation["candidate"]["calories"]
    )


def test_activity_can_relax_lunch_replanning():
    fake_meals.today_meals.extend(
        [
            {
                "date": "2026-09-01",
                "meal_type": "Colazione",
                "name": "Breakfast",
                "calories": 300,
                "protein": 20,
                "carbs": 35,
                "fat": 8,
            },
            {
                "date": "2026-09-01",
                "meal_type": "Spuntino",
                "name": "Large snack",
                "calories": 900,
                "protein": 10,
                "carbs": 100,
                "fat": 30,
            },
        ]
    )

    before_budget_response = client.get(
        "/days/2026-09-01/budget"
    )
    before_options_response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert before_budget_response.status_code == 200
    assert before_options_response.status_code == 200

    before_budget = before_budget_response.json()["budget"]
    before_recommendation = (
        before_options_response.json()["recommended"]
    )

    assert before_recommendation is not None
    assert (
        before_recommendation["strategy"]
        == "adapted_routine"
    )

    fake_activities.today_activities.append(
        {
            "date": "2026-09-01",
            "name": "Workout",
            "burned_calories": 500,
        }
    )

    after_budget_response = client.get(
        "/days/2026-09-01/budget"
    )
    after_options_response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert after_budget_response.status_code == 200
    assert after_options_response.status_code == 200

    after_budget = after_budget_response.json()["budget"]
    after_recommendation = (
        after_options_response.json()["recommended"]
    )

    assert after_recommendation is not None

    assert (
        after_budget["available_kcal"]
        == before_budget["available_kcal"] + 500
    )

    assert (
        after_recommendation["portion_multiplier"]
        >=
        before_recommendation["portion_multiplier"]
    )

    assert (
        after_recommendation["candidate"]["calories"]
        >=
        before_recommendation["candidate"]["calories"]
    )


def test_snack_exposes_food_replanning_context():
    fake_meals.today_meals.extend(
        [
            {
                "date": "2026-09-01",
                "meal_type": "Colazione",
                "name": "Breakfast",
                "calories": 300,
                "protein": 20,
                "carbs": 35,
                "fat": 8,
            },
            {
                "date": "2026-09-01",
                "meal_type": "Spuntino",
                "name": "Large snack",
                "calories": 900,
                "protein": 10,
                "carbs": 100,
                "fat": 30,
            },
        ]
    )

    response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["recommended"] is not None
    assert (
        payload["recommended"]["strategy"]
        == "adapted_routine"
    )

    assert payload["replanning_context"] == {
        "direction": "reduced",
        "driver": "food",
        "portion_changed": True,
        "available_kcal": payload[
            "replanning_context"
        ]["available_kcal"],
        "title": "Porzione adattata alla giornata",
        "message": (
            "Quello che hai già registrato oggi lascia "
            "meno margine per questo pasto."
        ),
    }


def test_activity_exposes_positive_replanning_context():
    fake_meals.today_meals.extend(
        [
            {
                "date": "2026-09-01",
                "meal_type": "Colazione",
                "name": "Breakfast",
                "calories": 300,
                "protein": 20,
                "carbs": 35,
                "fat": 8,
            },
            {
                "date": "2026-09-01",
                "meal_type": "Spuntino",
                "name": "Large snack",
                "calories": 900,
                "protein": 10,
                "carbs": 100,
                "fat": 30,
            },
        ]
    )

    fake_activities.today_activities.append(
        {
            "date": "2026-09-01",
            "name": "Workout",
            "burned_calories": 500,
        }
    )

    response = client.get(
        "/days/2026-09-01/meals/lunch/options",
        params={"mode": "auto"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["recommended"] is not None

    context = payload["replanning_context"]

    assert context["driver"] == "activity"
    assert context["direction"] == "expanded"
    assert context["title"] == "Più margine disponibile"
    assert (
        context["message"]
        == "L'attività registrata oggi ha aumentato "
        "il margine disponibile."
    )
