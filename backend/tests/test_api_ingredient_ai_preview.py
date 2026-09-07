from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.dependencies import (
    get_current_user,
)
from backend.api.main import app
from backend.services.ingredient_ai_interpreter import (
    IngredientAIInterpreter,
)


class FakeUser:
    id = "user-test"


def test_ingredient_ai_preview_returns_result(
    monkeypatch,
):
    def fake_interpret(self, *, text: str):
        assert "yogurt" in text.lower()

        return {
            "name": "Yogurt greco 0%",
            "calories_per_100g": 59,
            "protein_per_100g": 10.3,
            "carbs_per_100g": 3.6,
            "fat_per_100g": 0.2,
            "kind": "product",
            "meal_slots": [
                "breakfast",
                "snack",
            ],
            "default_unit": "g",
            "default_quantity": 170,
            "grams_per_unit": None,
            "confidence": "medium",
            "estimated": True,
            "notes": "Valori stimati.",
            "ready_for_form": True,
        }

    monkeypatch.setattr(
        IngredientAIInterpreter,
        "interpret",
        fake_interpret,
    )

    app.dependency_overrides[
        get_current_user
    ] = lambda: FakeUser()

    try:
        client = TestClient(app)

        response = client.post(
            "/ingredients/ai-preview",
            json={
                "text": (
                    "Yogurt greco 0%, "
                    "vasetto 170g"
                ),
            },
        )

        assert response.status_code == 200

        result = response.json()["result"]

        assert result["name"] == "Yogurt greco 0%"
        assert result["calories_per_100g"] == 59
        assert result["meal_slots"] == [
            "breakfast",
            "snack",
        ]
        assert result["ready_for_form"] is True
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )
