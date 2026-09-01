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

    assert (
        "/meals/conversational/confirm"
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
    assert payload["items"][0]["quantity_g"] == 100.0

    assert payload["totals"] == {
        "calories": 780.0,
        "protein": 30.5,
        "carbs": 101.0,
        "fat": 28.2,
    }

    assert payload["requires_confirmation"] is True


def test_photo_preview_route_is_registered():
    assert (
        "/meals/photo/preview"
        in app.openapi()["paths"]
    )


def test_photo_preview_builds_preview_from_interpretation(
    monkeypatch,
):
    import base64

    from backend.api.routers import meals as meals_router

    def fake_interpret(
        self,
        *,
        image_bytes,
        mime_type,
        meal_type,
    ):
        assert image_bytes == b"fake-image"
        assert mime_type == "image/jpeg"

        return {
            "meal_type": meal_type,
            "items": [
                {
                    "name": "Pasta al pomodoro",
                    "quantity": 250,
                    "unit": "g",
                    "calories": 420,
                    "protein": 14,
                    "carbs": 72,
                    "fat": 9,
                    "estimated": True,
                    "uncertainty": "photo",
                }
            ],
        }

    monkeypatch.setattr(
        meals_router.GroqMealVisionInterpreter,
        "interpret",
        fake_interpret,
    )

    response = client.post(
        "/meals/photo/preview",
        json={
            "image_base64": base64.b64encode(
                b"fake-image"
            ).decode("utf-8"),
            "mime_type": "image/jpeg",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["meal_type"] == "Pranzo"
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Pasta al pomodoro"
    assert data["items"][0]["calories"] == 420


def test_photo_preview_rejects_invalid_base64():
    response = client.post(
        "/meals/photo/preview",
        json={
            "image_base64": "not-valid-base64!!!",
            "mime_type": "image/jpeg",
            "meal_type": "Pranzo",
        },
    )

    assert response.status_code == 422
