import pytest

from backend.services.structured_meal import (
    StructuredMealError,
    StructuredMealService,
)


class FakeMealsRepository:
    def __init__(self):
        self.created = None
        self.deleted = []

    def create(self, payload):
        self.created = dict(payload)

        return {
            "id": 42,
            **payload,
        }

    def delete(self, meal_id, user_id):
        self.deleted.append(
            (meal_id, user_id)
        )
        return True


class FakeIngredientsRepository:
    def __init__(self):
        self.items = {
            "rice": {
                "id": "rice",
                "name": "Riso",
                "calories_per_100g": 350,
                "protein_per_100g": 7,
                "carbs_per_100g": 78,
                "fat_per_100g": 1,
            },
            "chicken": {
                "id": "chicken",
                "name": "Pollo",
                "calories_per_100g": 165,
                "protein_per_100g": 31,
                "carbs_per_100g": 0,
                "fat_per_100g": 3.6,
            },
        }

    def get_by_id(
        self,
        ingredient_id,
        user_id,
    ):
        return self.items.get(
            ingredient_id
        )


class FakeMealIngredientsRepository:
    def __init__(self):
        self.created = []

    def create(self, payload):
        item = {
            "id": (
                f"component-"
                f"{len(self.created) + 1}"
            ),
            **payload,
        }

        self.created.append(item)

        return item


def build_service():
    meals = FakeMealsRepository()
    ingredients = FakeIngredientsRepository()
    components = (
        FakeMealIngredientsRepository()
    )

    service = StructuredMealService(
        meals_repo=meals,
        ingredients_repo=ingredients,
        meal_ingredients_repo=components,
    )

    return service, meals, components


def test_structured_meal_creates_one_meal_with_components():
    service, meals, components = (
        build_service()
    )

    result = service.create(
        user_id="u1",
        meal_payload={
            "date": "2026-08-24",
            "meal_type": "Cena",
            "name": "Chicken Rice",
        },
        structured_ingredients=[
            {
                "ingredient_id": "rice",
                "quantity": 80,
                "unit": "g",
                "quantity_g": 80,
            },
            {
                "ingredient_id": "chicken",
                "quantity": 180,
                "unit": "g",
                "quantity_g": 180,
            },
        ],
    )

    assert meals.created["calories"] == 577
    assert meals.created["protein"] == 61

    assert len(components.created) == 2

    assert all(
        item["meal_id"] == 42
        for item in components.created
    )

    assert result["meal"]["name"] == "Chicken Rice"


def test_meal_components_store_nutrition_snapshots():
    service, _, components = (
        build_service()
    )

    service.create(
        user_id="u1",
        meal_payload={
            "date": "2026-08-24",
            "meal_type": "Cena",
            "name": "Chicken Rice",
        },
        structured_ingredients=[
            {
                "ingredient_id": "rice",
                "quantity": 80,
                "unit": "g",
                "quantity_g": 80,
            },
        ],
    )

    item = components.created[0]

    assert item["name_snapshot"] == "Riso"
    assert item["calories"] == 280
    assert item["protein"] == 5.6


def test_unknown_ingredient_is_rejected():
    service, meals, components = (
        build_service()
    )

    with pytest.raises(
        StructuredMealError,
        match="Ingredient not found",
    ):
        service.create(
            user_id="u1",
            meal_payload={
                "date": "2026-08-24",
                "meal_type": "Cena",
                "name": "Unknown meal",
            },
            structured_ingredients=[
                {
                    "ingredient_id": "missing",
                    "quantity": 100,
                    "unit": "g",
                    "quantity_g": 100,
                }
            ],
        )

    assert meals.created is None
    assert components.created == []


def test_structured_meal_requires_components():
    service, _, _ = build_service()

    with pytest.raises(
        StructuredMealError,
        match="At least one",
    ):
        service.create(
            user_id="u1",
            meal_payload={
                "date": "2026-08-24",
                "meal_type": "Cena",
                "name": "Empty",
            },
            structured_ingredients=[],
        )


def test_structured_meal_update_rebuilds_components():
    class UpdateMealsRepository(FakeMealsRepository):
        def __init__(self):
            super().__init__()
            self.updated = None

        def update(
            self,
            meal_id,
            user_id,
            payload,
        ):
            self.updated = (
                meal_id,
                user_id,
                dict(payload),
            )

            return {
                "id": meal_id,
                **payload,
            }

    class UpdateMealIngredientsRepository(
        FakeMealIngredientsRepository
    ):
        def __init__(self):
            super().__init__()
            self.deleted_for_meal = []
            self.existing = [
                {
                    "id": "old-component",
                    "meal_id": "meal-1",
                    "ingredient_id": "rice",
                    "name_snapshot": "Riso",
                    "quantity": 80,
                    "unit": "g",
                    "quantity_g": 80,
                    "calories": 280,
                    "protein": 5.6,
                    "carbs": 62.4,
                    "fat": 0.8,
                }
            ]

        def list_for_meal(self, meal_id):
            return list(self.existing)

        def delete_for_meal(self, meal_id):
            self.deleted_for_meal.append(
                meal_id
            )
            self.created = []
            return True

    meals = UpdateMealsRepository()
    ingredients = FakeIngredientsRepository()
    components = (
        UpdateMealIngredientsRepository()
    )

    service = StructuredMealService(
        meals_repo=meals,
        ingredients_repo=ingredients,
        meal_ingredients_repo=components,
    )

    result = service.update(
        user_id="u1",
        meal_id="meal-1",
        meal_payload={
            "name": "Chicken Rice",
        },
        structured_ingredients=[
            {
                "ingredient_id": "rice",
                "quantity": 100,
                "unit": "g",
                "quantity_g": 100,
            },
            {
                "ingredient_id": "chicken",
                "quantity": 150,
                "unit": "g",
                "quantity_g": 150,
            },
        ],
    )

    assert meals.updated is not None

    meal_id, user_id, payload = (
        meals.updated
    )

    assert meal_id == "meal-1"
    assert user_id == "u1"

    assert payload["calories"] == 598
    assert payload["protein"] == 54

    assert components.deleted_for_meal == [
        "meal-1"
    ]

    assert len(
        result["meal_ingredients"]
    ) == 2

    assert {
        item["ingredient_id"]
        for item in result[
            "meal_ingredients"
        ]
    } == {
        "rice",
        "chicken",
    }
