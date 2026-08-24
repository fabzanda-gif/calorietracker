import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_decision_selections_repository,
)
from backend.api.main import app


class FakeDecisionSelectionsRepository:
    def __init__(self):
        self.created = None

    def create(self, payload):
        self.created = payload
        return {"id": "selection-1", **payload}


repo = FakeDecisionSelectionsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def overrides():
    repo.created = None
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[
        get_decision_selections_repository
    ] = lambda: repo
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_selection_route_is_registered():
    assert (
        "/days/{day_date}/meals/{meal_slot}/selection"
        in app.openapi()["paths"]
    )


def test_selection_event_is_persisted():
    response = client.post(
        "/days/2026-09-01/meals/dinner/selection",
        json={
            "mode": "order",
            "lens": "taste",
            "option_index": 2,
            "candidate": {
                "id": "delivery:poke",
                "source": "delivery",
                "name": "Poke Salmone",
                "calories": 650,
                "protein_g": 40,
                "taste_score": 9,
                "known_order": True,
                "personalization_strength": 1.0,
            },
            "available_kcal": 900,
            "protein_remaining_g": 60,
        },
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["saved"] is True
    assert payload["item"]["id"] == "selection-1"
    assert repo.created["user_id"] == "authenticated-user"
    assert repo.created["meal_type"] == "Cena"
    assert repo.created["mode"] == "order"
    assert repo.created["lens"] == "taste"


def test_unknown_meal_slot_returns_404():
    response = client.post(
        "/days/2026-09-01/meals/brunch/selection",
        json={
            "mode": "order",
            "lens": "taste",
            "option_index": 0,
            "candidate": {
                "source": "delivery",
                "name": "Poke",
            },
        },
    )
    assert response.status_code == 404


def test_invalid_mode_returns_422():
    response = client.post(
        "/days/2026-09-01/meals/dinner/selection",
        json={
            "mode": "magic",
            "lens": "taste",
            "option_index": 0,
            "candidate": {
                "source": "delivery",
                "name": "Poke",
            },
        },
    )
    assert response.status_code == 422
