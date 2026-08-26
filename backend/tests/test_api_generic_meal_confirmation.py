from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
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
