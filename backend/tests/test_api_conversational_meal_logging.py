import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
)
from backend.api.main import app


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
        metadata={},
    )


@pytest.fixture(autouse=True)
def authenticated_user_override():
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    yield
    app.dependency_overrides.pop(
        get_current_user,
        None,
    )


client = TestClient(app)


def test_conversational_preview_route_is_registered():
    assert (
        "/meals/conversational/preview"
        in app.openapi()["paths"]
    )


def test_conversational_preview_requires_text():
    response = client.post(
        "/meals/conversational/preview",
        json={
            "text": "",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 422


def test_conversational_preview_builds_preview_from_interpretation(
    monkeypatch,
):
    from backend.api.routers import meals as meals_router

    def fake_interpret_meal_text(*, text, meal_type):
        assert text == "Ho mangiato una carbonara e una mela"
        assert meal_type == "Pranzo"

        return {
            "meal_type": "Pranzo",
            "items": [
                {
                    "name": "Carbonara",
                    "quantity": 1,
                    "unit": "porzione",
                    "calories": 700,
                    "protein": 30,
                    "carbs": 80,
                    "fat": 28,
                    "estimated": True,
                },
                {
                    "name": "Mela",
                    "quantity": 1,
                    "unit": "pezzo",
                    "calories": 80,
                    "protein": 0.5,
                    "carbs": 21,
                    "fat": 0.2,
                    "estimated": True,
                },
            ],
        }

    monkeypatch.setattr(
        meals_router,
        "interpret_meal_text",
        fake_interpret_meal_text,
        raising=False,
    )

    response = client.post(
        "/meals/conversational/preview",
        json={
            "text": "Ho mangiato una carbonara e una mela",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "preview"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["name"] == "Carbonara"
    assert payload["items"][1]["name"] == "Mela"

    assert payload["totals"] == {
        "calories": 780.0,
        "protein": 30.5,
        "carbs": 101.0,
        "fat": 28.2,
    }

    assert payload["requires_confirmation"] is True
