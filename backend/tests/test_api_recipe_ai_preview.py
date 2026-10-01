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
    )


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[
        get_current_user
    ] = override_current_user

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_recipe_ai_preview_calculates_totals(monkeypatch):
    from backend.api.routers import recipes as recipes_router

    def fake_interpret(self, *, text):
        assert "pollo" in text.lower()

        ingredients = [
            {
                "name": "Petto di pollo",
                "quantity": 500,
                "unit": "g",
                "quantity_g": 500,
                "calories_per_100g": 110,
                "protein_per_100g": 23,
                "carbs_per_100g": 0,
                "fat_per_100g": 1.5,
                "confidence": "high",
                "estimated": False,
                "notes": None,
            },
            {
                "name": "Riso",
                "quantity": 200,
                "unit": "g",
                "quantity_g": 200,
                "calories_per_100g": 360,
                "protein_per_100g": 7,
                "carbs_per_100g": 80,
                "fat_per_100g": 1,
                "confidence": "high",
                "estimated": False,
                "notes": None,
            },
            {
                "name": "Olio",
                "quantity": 20,
                "unit": "g",
                "quantity_g": 20,
                "calories_per_100g": 900,
                "protein_per_100g": 0,
                "carbs_per_100g": 0,
                "fat_per_100g": 100,
                "confidence": "high",
                "estimated": False,
                "notes": None,
            },
        ]

        ingredient_weight_g = sum(
            item["quantity_g"]
            for item in ingredients
        )

        totals = {
            "calories": round(
                sum(
                    item["calories_per_100g"]
                    * item["quantity_g"]
                    / 100
                    for item in ingredients
                ),
                2,
            ),
            "protein": round(
                sum(
                    item["protein_per_100g"]
                    * item["quantity_g"]
                    / 100
                    for item in ingredients
                ),
                2,
            ),
            "carbs": round(
                sum(
                    item["carbs_per_100g"]
                    * item["quantity_g"]
                    / 100
                    for item in ingredients
                ),
                2,
            ),
            "fat": round(
                sum(
                    item["fat_per_100g"]
                    * item["quantity_g"]
                    / 100
                    for item in ingredients
                ),
                2,
            ),
        }

        return {
            "name": "Pollo e riso",
            "servings": 4,
            "final_weight_g": 1100,
            "ingredients": ingredients,
            "ingredient_weight_g": ingredient_weight_g,
            "calculation_weight_g": 1100,
            "weight_source": "explicit_final_weight",
            "totals": totals,
            "per_100g": {
                key: round(
                    value * 100 / 1100,
                    2,
                )
                for key, value in totals.items()
            },
            "per_serving": {
                key: round(
                    value / 4,
                    2,
                )
                for key, value in totals.items()
            },
            "needs_final_weight_confirmation": False,
            "needs_review": False,
            "requires_confirmation": True,
        }

    monkeypatch.setattr(
        recipes_router.RecipeAIInterpreter,
        "interpret",
        fake_interpret,
    )

    response = client.post(
        "/recipes/ai-preview",
        json={
            "text": (
                "Pollo e riso: 500 g pollo, "
                "200 g riso, 20 g olio. "
                "Peso finale 1100 g, 4 porzioni."
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()["result"]

    assert payload["name"] == "Pollo e riso"
    assert payload["final_weight_g"] == 1100
    assert payload["servings"] == 4
    assert len(payload["ingredients"]) == 3

    assert payload["totals"]["calories"] == 1450.0
    assert payload["totals"]["protein"] == 129.0
    assert payload["totals"]["carbs"] == 160.0
    assert payload["totals"]["fat"] == 29.5

    assert payload["per_100g"]["calories"] == 131.82
    assert payload["per_serving"]["calories"] == 362.5

    assert payload["needs_final_weight_confirmation"] is False
    assert payload["requires_confirmation"] is True
