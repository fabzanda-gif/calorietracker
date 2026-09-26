import pytest
from pydantic import ValidationError

from backend.api.routers.ingredients import (
    IngredientCreate,
    IngredientUpdate,
)


def test_food_classification_defaults_to_ingredient_only():
    item = IngredientCreate(name="Farina")

    assert item.kind == "ingredient"
    assert item.meal_slots == []


def test_food_can_have_multiple_meal_slots():
    item = IngredientCreate(
        name="Yogurt greco",
        kind="product",
        meal_slots=[
            "breakfast",
            "snack",
        ],
    )

    assert item.kind == "product"
    assert item.meal_slots == [
        "breakfast",
        "snack",
    ]


def test_invalid_food_kind_is_rejected():
    with pytest.raises(ValidationError):
        IngredientCreate(
            name="Test",
            kind="mystery",
        )


def test_invalid_meal_slot_is_rejected():
    with pytest.raises(ValidationError):
        IngredientUpdate(
            meal_slots=["midnight"],
        )
