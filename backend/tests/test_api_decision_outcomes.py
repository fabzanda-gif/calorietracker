import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_decision_selections_repository,
    get_meals_repository,
)
from backend.api.main import app


class FakeDecisionSelectionsRepository:
    def __init__(self):
        self.last_range = None

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        self.last_range = (
            user_id,
            str(start_date),
            str(end_date),
        )

        return [
            {
                "id": "selection-1",
                "date": str(end_date),
                "meal_slot": "dinner",
                "meal_type": "Cena",
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "name": "Poke Salmone",
                    "calories": 650,
                    "source": "delivery",
                },
            }
        ]


class FakeMealsRepository:
    def __init__(self):
        self.last_range = None

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        self.last_range = (
            user_id,
            str(start_date),
            str(end_date),
        )

        return [
            {
                "id": "meal-1",
                "date": str(end_date),
                "meal_type": "Cena",
                "name": "Poke Salmone",
                "calories": 650,
            }
        ]


selections_repo = FakeDecisionSelectionsRepository()
meals_repo = FakeMealsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def overrides():
    selections_repo.last_range = None
    meals_repo.last_range = None

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[
        get_decision_selections_repository
    ] = lambda: selections_repo
    app.dependency_overrides[
        get_meals_repository
    ] = lambda: meals_repo

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_decision_outcomes_route_is_registered():
    assert (
        "/insights/decision-outcomes"
        in app.openapi()["paths"]
    )


def test_decision_outcomes_reconstruct_observed_meal():
    response = client.get(
        "/insights/decision-outcomes",
        params={"days": 30},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["user_id"] == "authenticated-user"
    assert payload["days"] == 30
    assert payload["selection_count"] == 1
    assert payload["status_counts"]["observed"] == 1
    assert payload["observed_share"] == 1.0

    assert (
        payload["items"][0]["outcome"]["meal"]["id"]
        == "meal-1"
    )


def test_repository_ranges_are_user_scoped():
    response = client.get(
        "/insights/decision-outcomes",
        params={"days": 7},
    )

    assert response.status_code == 200

    assert selections_repo.last_range[0] == (
        "authenticated-user"
    )
    assert meals_repo.last_range[0] == (
        "authenticated-user"
    )

    assert selections_repo.last_range[1:] == (
        meals_repo.last_range[1:]
    )


def test_days_validation_rejects_zero():
    response = client.get(
        "/insights/decision-outcomes",
        params={"days": 0},
    )

    assert response.status_code == 422
