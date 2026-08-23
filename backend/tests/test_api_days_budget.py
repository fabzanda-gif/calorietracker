import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_meals_repository,
    get_weight_repository,
)
from backend.api.main import app


class FakeMealsRepository:
    def list_for_date_compatible(self, user_id, log_date):
        return [
            {"calories": 500, "protein": 30},
            {"calories": 700, "protein": 40},
        ]


class FakeActivitiesRepository:
    def list_for_date(self, user_id, log_date):
        return [
            {"burned_calories": 450},
        ]


class FakeWeightRepository:
    def __init__(self, row=None):
        self.row = row or {
            "id": "w1",
            "date": "2026-08-24",
            "weight": 80.0,
        }
        self.calls = []

    def latest(self, user_id):
        self.calls.append(user_id)
        return self.row


fake_weight_repo = FakeWeightRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
        metadata={
            "height": 180,
            "birth_date": "1990-01-01",
            "gender": "Uomo",
            "goal_mode": "loss",
            "goal_adjustment_kcal": 500,
            "protein_goal_enabled": True,
            "protein_goal_g": 150,
        },
    )


def override_meals_repo():
    return FakeMealsRepository()


def override_activities_repo():
    return FakeActivitiesRepository()


def override_weight_repo():
    return fake_weight_repo


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meals_repository] = override_meals_repo
    app.dependency_overrides[get_activities_repository] = override_activities_repo
    app.dependency_overrides[get_weight_repository] = override_weight_repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_day_budget_route_is_registered():
    paths = app.openapi()["paths"]
    assert "/days/{day_date}/budget" in paths


def test_day_budget_endpoint_returns_budget():
    response = client.get("/days/2026-08-25/budget")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["date"] == "2026-08-25"

    assert payload["actual"]["consumed_kcal"] == 1200
    assert payload["actual"]["protein_consumed_g"] == 70
    assert payload["actual"]["actual_activity_kcal"] == 450

    budget = payload["budget"]
    assert budget["goal_mode"] == "loss"
    assert budget["goal_adjustment_kcal"] == 500
    assert budget["protein_target_g"] == 150
    assert budget["protein_remaining_g"] == 80

    assert fake_weight_repo.calls[-1] == "authenticated-user"


def test_day_budget_endpoint_uses_latest_weight():
    response = client.get("/days/2026-08-25/budget")

    assert response.status_code == 200
    payload = response.json()

    assert payload["profile"]["bmr"] is not None
    assert payload["profile"]["profile_complete_for_budget"] is True
