from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.api.main import app


class FakeDailyLogsRepository:
    def get_for_date_compatible(self, user_id, log_date):
        return {
            "date": str(log_date),
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        }

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {"date": "2026-08-04", "day_type": "Ufficio"},
            {"date": "2026-08-11", "day_type": "Ufficio"},
            {"date": "2026-08-18", "day_type": "Ufficio"},
            {"date": "2026-08-25", "day_type": "Ufficio"},
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
        return {"weight": 80}


class FakeMealsRepository:
    def __init__(self):
        self.created = []

    def reset(self):
        self.created.clear()

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        rows = []
        for meal_type, name, kcal in [
            ("Colazione", "Colazione Ufficio", 300),
            ("Pranzo", "Pranzo Ufficio", 700),
            ("Cena", "Cena Standard", 600),
        ]:
            for d in [
                "2026-08-04",
                "2026-08-11",
                "2026-08-18",
                "2026-08-25",
            ]:
                rows.append(
                    {
                        "date": d,
                        "meal_type": meal_type,
                        "name": name,
                        "calories": kcal,
                        "protein": 30,
                        "carbs": 50,
                        "fat": 15,
                    }
                )
        return rows

    def list_for_date_compatible(self, user_id, log_date):
        return [
            item
            for item in self.created
            if item["user_id"] == user_id
            and item["date"] == str(log_date)
        ]

    def breakfast_exists(self, user_id, log_date):
        return any(
            item["meal_type"] == "Colazione"
            for item in self.list_for_date_compatible(
                user_id,
                log_date,
            )
        )

    def create_compatible(self, payload):
        item = {
            "id": f"meal-{len(self.created) + 1}",
            **payload,
        }
        self.created.append(item)
        return SimpleNamespace(data=[item])


fake_meals = FakeMealsRepository()


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


def override_daily_logs():
    return FakeDailyLogsRepository()


def override_meals():
    return fake_meals


@pytest.fixture(autouse=True)
def api_overrides():
    fake_meals.reset()

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = override_daily_logs
    app.dependency_overrides[get_meals_repository] = override_meals
    app.dependency_overrides[
        get_activities_repository
    ] = lambda: FakeActivitiesRepository()
    app.dependency_overrides[
        get_weight_repository
    ] = lambda: FakeWeightRepository()

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


@pytest.mark.parametrize(
    "slot,expected_type,expected_name",
    [
        ("breakfast", "Colazione", "Colazione Ufficio"),
        ("lunch", "Pranzo", "Pranzo Ufficio"),
        ("dinner", "Cena", "Cena Standard"),
    ],
)
def test_generic_confirmation_route_logs_requested_meal(
    slot,
    expected_type,
    expected_name,
):
    response = client.post(
        f"/days/2026-09-01/meals/{slot}/confirm"
    )

    assert response.status_code == 200
    item = response.json()["item"]

    assert item["meal_type"] == expected_type
    assert item["name"] == expected_name


def test_duplicate_lunch_confirmation_is_rejected():
    first = client.post(
        "/days/2026-09-01/meals/lunch/confirm"
    )
    second = client.post(
        "/days/2026-09-01/meals/lunch/confirm"
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_unknown_meal_slot_is_404():
    response = client.post(
        "/days/2026-09-01/meals/brunch/confirm"
    )

    assert response.status_code == 404


def test_confirmation_can_log_replanned_quantity():
    response = client.post(
        "/days/2026-09-01/meals/dinner/confirm",
        json={
            "recommendation": {
                "name": "Fit Lasagna",
                "quantity": 1.5,
                "calories": 578,
                "protein_g": 32.25,
                "carbs_g": 99,
                "fat_g": 24,
            }
        },
    )

    assert response.status_code == 200

    item = response.json()["item"]

    assert item["meal_type"] == "Cena"
    assert item["name"] == "Fit Lasagna"

    assert item["base_name"] == "Fit Lasagna"
    assert item["quantity"] == 1.5

    assert item["calories"] == 578
    assert item["protein"] == 32
    assert item["carbs"] == 99
    assert item["fat"] == 24


def test_next_meal_route_starts_with_breakfast():
    response = client.get(
        "/days/2026-09-01/next-meal"
    )

    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-09-01",
        "next_slot": "breakfast",
        "next_meal_type": "Colazione",
    }


def test_next_meal_route_advances_after_confirmation():
    breakfast = client.post(
        "/days/2026-09-01/meals/breakfast/confirm"
    )

    assert breakfast.status_code == 200

    response = client.get(
        "/days/2026-09-01/next-meal"
    )

    assert response.status_code == 200
    assert response.json()["next_slot"] == "lunch"
    assert response.json()["next_meal_type"] == "Pranzo"


def test_extra_meal_reduces_budget_without_advancing_next_slot():
    breakfast = fake_meals.create_compatible(
        {
            "user_id": "authenticated-user",
            "date": "2026-09-01",
            "meal_type": "Colazione",
            "name": "Colazione",
            "calories": 300,
            "protein": 20,
            "carbs": 30,
            "fat": 10,
        }
    )

    assert breakfast.data

    before_budget = client.get(
        "/days/2026-09-01/budget"
    )
    before_next = client.get(
        "/days/2026-09-01/next-meal"
    )

    assert before_budget.status_code == 200
    assert before_next.status_code == 200
    assert before_next.json()["next_slot"] == "lunch"

    before_available = (
        before_budget.json()["budget"]["available_kcal"]
    )

    snack = fake_meals.create_compatible(
        {
            "user_id": "authenticated-user",
            "date": "2026-09-01",
            "meal_type": "Spuntino",
            "name": "Snack test",
            "calories": 250,
            "protein": 10,
            "carbs": 25,
            "fat": 8,
        }
    )

    assert snack.data

    after_budget = client.get(
        "/days/2026-09-01/budget"
    )
    after_next = client.get(
        "/days/2026-09-01/next-meal"
    )

    assert after_budget.status_code == 200
    assert after_next.status_code == 200

    assert after_next.json()["next_slot"] == "lunch"

    after_available = (
        after_budget.json()["budget"]["available_kcal"]
    )

    assert after_available == before_available - 250

def test_component_reduction_confirms_only_remaining_meal():
    response = client.post(
        "/days/2026-09-01/meals/dinner/confirm",
        json={
            "recommendation": {
                "name": "Riso con pollo",
                "quantity": 1,
                "calories": 520,
                "protein_g": 42,
                "carbs_g": 61,
                "fat_g": 12,
                "strategy": "component_reduction",
                "components": [
                    {
                        "name": "Riso con pollo",
                        "calories": 520,
                        "protein_g": 42,
                        "carbs_g": 61,
                        "fat_g": 12,
                    }
                ],
                "removed_components": [
                    {
                        "name": "Mela",
                        "calories": 80,
                        "protein_g": 0,
                        "carbs_g": 20,
                        "fat_g": 0,
                    }
                ],
            }
        },
    )

    assert response.status_code == 200

    payload = response.json()
    item = payload["item"]
    prediction = payload["prediction"]

    assert item["meal_type"] == "Cena"
    assert item["name"] == "Riso con pollo"
    assert item["calories"] == 520
    assert "mela" not in item["name"].lower()

    assert (
        prediction["replanning_strategy"]
        == "component_reduction"
    )
    assert prediction["components"] == [
        {
            "name": "Riso con pollo",
            "calories": 520,
            "protein_g": 42,
            "carbs_g": 61,
            "fat_g": 12,
        }
    ]
    assert prediction["removed_components"][0]["name"] == "Mela"

    assert len(fake_meals.created) == 1
    assert fake_meals.created[0]["name"] == "Riso con pollo"
    assert "mela" not in fake_meals.created[0]["name"].lower()
