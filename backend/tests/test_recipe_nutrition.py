import pytest

from backend.services.recipe_nutrition import (
    RecipeNutritionError,
    RecipeNutritionService,
)


def test_calculates_recipe_from_structured_ingredients():
    result = RecipeNutritionService().calculate(
        [
            {
                "quantity_g": 80,
                "ingredient": {
                    "id": "rice",
                    "name": "Riso",
                    "calories_per_100g": 350,
                    "protein_per_100g": 7,
                    "carbs_per_100g": 78,
                    "fat_per_100g": 1,
                },
            },
            {
                "quantity_g": 180,
                "ingredient": {
                    "id": "chicken",
                    "name": "Pollo",
                    "calories_per_100g": 165,
                    "protein_per_100g": 31,
                    "carbs_per_100g": 0,
                    "fat_per_100g": 3.6,
                },
            },
        ]
    )

    assert result["totals"]["calories"] == 577
    assert result["totals"]["protein"] == 61.4
    assert result["totals"]["carbs"] == 62.4
    assert result["totals"]["fat"] == 7.28


def test_changing_one_quantity_changes_recipe_totals():
    service = RecipeNutritionService()

    original = service.calculate(
        [
            {
                "quantity_g": 80,
                "ingredient": {
                    "name": "Riso",
                    "calories_per_100g": 350,
                },
            }
        ]
    )

    changed = service.calculate(
        [
            {
                "quantity_g": 60,
                "ingredient": {
                    "name": "Riso",
                    "calories_per_100g": 350,
                },
            }
        ]
    )

    assert original["totals"]["calories"] == 280
    assert changed["totals"]["calories"] == 210


def test_zero_quantity_is_rejected():
    with pytest.raises(
        RecipeNutritionError,
        match="quantity_g must be greater than zero",
    ):
        RecipeNutritionService().calculate(
            [
                {
                    "quantity_g": 0,
                    "ingredient": {
                        "name": "Pollo",
                        "calories_per_100g": 165,
                    },
                }
            ]
        )
