from backend.services.conversational_meal_confirmation import (
    ConversationalMealConfirmationService,
)


class FakeMealsRepository:
    def create(self, payload):
        return {
            "id": "meal-1",
            **payload,
        }

    def delete(self, meal_id, user_id):
        return True


class FakeIngredientsRepository:
    def __init__(self):
        self.item = {
            "id": "ingredient-1",
            "name": "Piadina",
            "normalized_name": "piadina",
            "calories_per_100g": 200,
            "protein_per_100g": 10,
            "carbs_per_100g": 30,
            "fat_per_100g": 5,
        }

    def get_by_normalized_name(
        self,
        normalized_name,
        user_id,
    ):
        return self.item

    def get_by_id(
        self,
        ingredient_id,
        user_id,
    ):
        return self.item


class FakeMealIngredientsRepository:
    def create(self, payload):
        return {
            "id": "meal-ingredient-1",
            **payload,
        }


class FakePantryRepository:
    def __init__(self, items):
        self.items = items
        self.updated = []
        self.deleted = []

    def list_for_user(self, user_id):
        return self.items

    def update(
        self,
        item_id,
        user_id,
        payload,
    ):
        self.updated.append(
            (item_id, payload)
        )
        return {
            "id": item_id,
            **payload,
        }

    def delete(
        self,
        item_id,
        user_id,
    ):
        self.deleted.append(item_id)
        return True


def build_service(pantry):
    return ConversationalMealConfirmationService(
        meals_repo=FakeMealsRepository(),
        ingredients_repo=FakeIngredientsRepository(),
        meal_ingredients_repo=FakeMealIngredientsRepository(),
        pantry_repo=pantry,
    )


def test_consumes_weight_pantry_and_keeps_remainder():
    pantry = FakePantryRepository(
        [
            {
                "id": "pantry-1",
                "ingredient_id": "ingredient-1",
                "quantity": 300,
                "unit": "g",
                "quantity_mode": "weight",
                "grams_per_portion": None,
            }
        ]
    )

    result = build_service(pantry).confirm(
        user_id="user-1",
        meal_payload={
            "date": "2026-09-07",
            "meal_type": "Pranzo",
            "name": "Piadina",
        },
        items=[
            {
                "name": "Piadina",
                "quantity_g": 200,
                "calories": 400,
                "protein": 20,
                "carbs": 60,
                "fat": 10,
            }
        ],
    )

    assert pantry.deleted == []
    assert pantry.updated == [
        (
            "pantry-1",
            {
                "quantity": 100.0,
            },
        )
    ]

    assert result["pantry_consumption"] == [
        {
            "pantry_item_id": "pantry-1",
            "ingredient_id": "ingredient-1",
            "consumed_g": 200.0,
        }
    ]


def test_consumes_portion_pantry_and_deletes_when_empty():
    pantry = FakePantryRepository(
        [
            {
                "id": "pantry-1",
                "ingredient_id": "ingredient-1",
                "quantity": 2,
                "unit": "portion",
                "quantity_mode": "portion",
                "grams_per_portion": 100,
            }
        ]
    )

    result = build_service(pantry).confirm(
        user_id="user-1",
        meal_payload={
            "date": "2026-09-07",
            "meal_type": "Pranzo",
            "name": "Piadina",
        },
        items=[
            {
                "name": "Piadina",
                "quantity_g": 200,
                "calories": 400,
                "protein": 20,
                "carbs": 60,
                "fat": 10,
            }
        ],
    )

    assert pantry.updated == []
    assert pantry.deleted == [
        "pantry-1",
    ]

    assert result["pantry_consumption"][0][
        "consumed_g"
    ] == 200.0


def test_ignores_unrelated_pantry_items():
    pantry = FakePantryRepository(
        [
            {
                "id": "pantry-other",
                "ingredient_id": "ingredient-other",
                "quantity": 500,
                "unit": "g",
                "quantity_mode": "weight",
                "grams_per_portion": None,
            }
        ]
    )

    result = build_service(pantry).confirm(
        user_id="user-1",
        meal_payload={
            "date": "2026-09-07",
            "meal_type": "Pranzo",
            "name": "Piadina",
        },
        items=[
            {
                "name": "Piadina",
                "quantity_g": 150,
                "calories": 300,
                "protein": 15,
                "carbs": 45,
                "fat": 8,
            }
        ],
    )

    assert pantry.updated == []
    assert pantry.deleted == []
    assert result["pantry_consumption"] == []
