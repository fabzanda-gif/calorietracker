import pytest

from backend.services.meal_text_interpreter import (
    MealInterpretationError,
    MealTextInterpreter,
)


def interpreter():
    return MealTextInterpreter()


def test_normalizes_ai_interpretation():
    result = interpreter().normalize(
        {
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
    )

    assert result["meal_type"] == "Pranzo"
    assert len(result["items"]) == 2
    assert result["items"][0]["name"] == "Carbonara"
    assert result["items"][1]["calories"] == 80.0


def test_missing_quantity_is_marked_uncertain():
    result = interpreter().normalize(
        {
            "meal_type": "Pranzo",
            "items": [
                {
                    "name": "Riso",
                    "quantity": 150,
                    "unit": "g",
                    "calories": 195,
                    "protein": 4,
                    "carbs": 42,
                    "fat": 0.5,
                    "estimated": True,
                    "uncertainty": "quantity",
                }
            ],
        }
    )

    item = result["items"][0]

    assert item["estimated"] is True
    assert item["uncertainty"] == "quantity"


def test_missing_optional_macros_default_to_zero():
    result = interpreter().normalize(
        {
            "meal_type": "Spuntino",
            "items": [
                {
                    "name": "Mela",
                    "quantity": 1,
                    "unit": "pezzo",
                    "calories": 80,
                    "estimated": True,
                }
            ],
        }
    )

    item = result["items"][0]

    assert item["protein"] == 0.0
    assert item["carbs"] == 0.0
    assert item["fat"] == 0.0


def test_rejects_item_without_name():
    with pytest.raises(MealInterpretationError):
        interpreter().normalize(
            {
                "meal_type": "Pranzo",
                "items": [
                    {
                        "quantity": 1,
                        "unit": "porzione",
                        "calories": 500,
                    }
                ],
            }
        )


def test_rejects_negative_nutrition():
    with pytest.raises(MealInterpretationError):
        interpreter().normalize(
            {
                "meal_type": "Pranzo",
                "items": [
                    {
                        "name": "Pasta",
                        "quantity": 1,
                        "unit": "porzione",
                        "calories": -500,
                    }
                ],
            }
        )


def test_empty_items_are_allowed_for_unclear_input():
    result = interpreter().normalize(
        {
            "meal_type": "Pranzo",
            "items": [],
        }
    )

    assert result["items"] == []
