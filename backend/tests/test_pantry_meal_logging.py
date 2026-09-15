from datetime import date

import pytest

from backend.services.pantry_meal_logging import (
    PantryMealLoggingService,
    PantryMealUnavailableError,
)


class PantryRepo:
    def __init__(self, item):
        self.item = dict(item)
        self.deleted = False

    def get_by_id(self, item_id, user_id):
        return dict(self.item)

    def update(self, item_id, user_id, payload):
        self.item.update(payload)
        return dict(self.item)

    def delete(self, item_id, user_id):
        self.deleted = True
        return True


class IngredientRepo:
    def get_by_id(self, ingredient_id, user_id):
        return {
            "id": ingredient_id,
            "name": "Burger",
            "calories_per_100g": 200,
            "protein_per_100g": 10,
            "carbs_per_100g": 20,
            "fat_per_100g": 8,
        }


class MealsRepo:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, payload):
        item = {**payload, "id": "meal-1"}
        self.created.append(item)
        return item

    def delete(self, meal_id, user_id):
        self.deleted.append(meal_id)
        return True


class MealIngredientsRepo:
    def create(self, payload):
        return {**payload, "id": "component-1"}


def service(item):
    pantry = PantryRepo(item)
    meals = MealsRepo()

    return (
        PantryMealLoggingService(
            pantry_repo=pantry,
            ingredients_repo=IngredientRepo(),
            meals_repo=meals,
            meal_ingredients_repo=MealIngredientsRepo(),
        ),
        pantry,
        meals,
    )


def test_logs_one_portion_and_decrements_pantry():
    svc, pantry, meals = service(
        {
            "id": "pantry-1",
            "ingredient_id": "ingredient-1",
            "quantity": 4,
            "quantity_mode": "portion",
            "unit": "portion",
            "grams_per_portion": 120,
        }
    )

    result = svc.log(
        user_id="user-1",
        pantry_item_id="pantry-1",
        meal_date=date(2026, 9, 7),
        meal_type="Colazione",
        quantity_g=120,
    )

    assert result["logged"] is True
    assert pantry.item["quantity"] == pytest.approx(3)
    assert len(meals.created) == 1
    assert meals.created[0]["calories"] == 240


def test_rejects_more_than_available():
    svc, pantry, meals = service(
        {
            "id": "pantry-1",
            "ingredient_id": "ingredient-1",
            "quantity": 100,
            "quantity_mode": "weight",
            "unit": "g",
            "grams_per_portion": None,
        }
    )

    with pytest.raises(PantryMealUnavailableError):
        svc.log(
            user_id="user-1",
            pantry_item_id="pantry-1",
            meal_date=date(2026, 9, 7),
            meal_type="Snack",
            quantity_g=150,
        )

    assert pantry.item["quantity"] == 100
    assert meals.created == []



class FailingMealIngredientsRepo:
    def __init__(self):
        self.cleared_meal_ids = []

    def create(self, payload):
        raise RuntimeError(
            "simulated ingredient link failure"
        )

    def delete_for_meal(self, meal_id):
        self.cleared_meal_ids.append(meal_id)
        return True


def test_rolls_back_meal_when_ingredient_link_fails():
    pantry = PantryRepo(
        {
            "id": "pantry-1",
            "ingredient_id": "ingredient-1",
            "quantity": 4,
            "quantity_mode": "portion",
            "unit": "portion",
            "grams_per_portion": 120,
        }
    )
    meals = MealsRepo()
    meal_ingredients = FailingMealIngredientsRepo()

    svc = PantryMealLoggingService(
        pantry_repo=pantry,
        ingredients_repo=IngredientRepo(),
        meals_repo=meals,
        meal_ingredients_repo=meal_ingredients,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated ingredient link failure",
    ):
        svc.log(
            user_id="user-1",
            pantry_item_id="pantry-1",
            meal_date=date(2026, 9, 7),
            meal_type="Colazione",
            quantity_g=120,
        )

    assert pantry.item["quantity"] == 4
    assert pantry.deleted is False
    assert meals.deleted == ["meal-1"]
    assert meal_ingredients.cleared_meal_ids == [
        "meal-1"
    ]
