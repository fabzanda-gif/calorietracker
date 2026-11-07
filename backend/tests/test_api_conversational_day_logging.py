import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_weight_repository,
)
from backend.api.main import app


class FakeWeightRepository:
    def latest(self, user_id):
        assert user_id == "authenticated-user"
        return {
            "id": "weight-1",
            "date": "2026-09-07",
            "weight": 80.0,
        }


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
        metadata={},
    )


@pytest.fixture(autouse=True)
def overrides():
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_weight_repository] = (
        lambda: FakeWeightRepository()
    )

    yield

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )
    app.dependency_overrides.pop(
        get_weight_repository,
        None,
    )


client = TestClient(app)


def test_conversational_day_preview_route_is_registered():
    assert (
        "/meals/conversational/day-preview"
        in app.openapi()["paths"]
    )


def test_conversational_day_preview_requires_text():
    response = client.post(
        "/meals/conversational/day-preview",
        json={
            "text": "",
            "default_meal_type": "Pranzo",
        },
    )

    assert response.status_code == 422


def test_conversational_day_preview_supports_multiple_actions(
    monkeypatch,
):
    from backend.api.routers import meals as meals_router

    def fake_day_interpretation(
        *,
        text,
        default_meal_type,
        reference_date=None,
    ):
        assert (
            text
            == "Ho mangiato una piadina, corso 5 km e peso 77,4 kg"
        )
        assert default_meal_type == "Pranzo"

        return {
            "intents": [
                {
                    "kind": "meal",
                    "text": "Ho mangiato una piadina",
                    "meal_type": "Pranzo",
                },
                {
                    "kind": "activity",
                    "activity_name": "Corsa 5 km",
                    "activity_type": "Corsa",
                    "duration_seconds": 1800,
                    "distance_meters": 5000,
                    "burned_calories": None,
                },
                {
                    "kind": "weight",
                    "weight_kg": 77.4,
                },
            ]
        }

    def fake_meal_interpretation(
        *,
        text,
        meal_type,
    ):
        assert text == "Ho mangiato una piadina"
        assert meal_type == "Pranzo"

        return {
            "meal_type": "Pranzo",
            "items": [
                {
                    "name": "Piadina",
                    "quantity": 1,
                    "unit": "porzione",
                    "quantity_g": 250,
                    "calories": 500,
                    "protein": 28,
                    "carbs": 55,
                    "fat": 18,
                    "estimated": True,
                }
            ],
        }

    monkeypatch.setattr(
        meals_router,
        "interpret_day_log_text",
        fake_day_interpretation,
    )

    monkeypatch.setattr(
        meals_router,
        "interpret_meal_text",
        fake_meal_interpretation,
    )

    response = client.post(
        "/meals/conversational/day-preview",
        json={
            "text": (
                "Ho mangiato una piadina, "
                "corso 5 km e peso 77,4 kg"
            ),
            "default_meal_type": "Pranzo",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "preview"
    assert payload["requires_confirmation"] is True
    assert len(payload["actions"]) == 3

    meal = payload["actions"][0]
    activity = payload["actions"][1]
    weight = payload["actions"][2]

    assert meal["kind"] == "meal"
    assert meal["meal_type"] == "Pranzo"
    assert meal["totals"]["calories"] == 500.0

    assert activity["kind"] == "activity"
    assert activity["activity_type"] == "Corsa"
    assert activity["distance_meters"] == 5000.0
    assert activity["duration_seconds"] == 1800

    # 80 kg * 5 km * running factor 1.0.
    assert activity["burned_calories"] == 400
    assert activity["calories_estimated"] is True
    assert activity["needs_review"] is True

    assert weight["kind"] == "weight"
    assert weight["weight_kg"] == 77.4
