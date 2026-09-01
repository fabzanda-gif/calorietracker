from backend.services.conversational_meal_confirmation import (
    ConversationalMealConfirmationService,
)


class FakeMealsRepository:
    def __init__(self):
        self.created = None

    def create(self, payload):
        self.created = dict(payload)
        return {"id": "meal-1", **payload}

    def delete(self, meal_id, user_id):
        return True


class FakeIngredientsRepository:
    def __init__(self):
        self.items = {}
        self.created = []

    def get_by_normalized_name(self, name, user_id):
        return next(
            (
                item
                for item in self.items.values()
                if item["normalized_name"] == name
            ),
            None,
        )

    def create(self, payload):
        item = {
            "id": f"ingredient-{len(self.items) + 1}",
            **payload,
        }
        self.items[item["id"]] = item
        self.created.append(item)
        return item

    def get_by_id(self, ingredient_id, user_id):
        return self.items.get(ingredient_id)


class FakeMealIngredientsRepository:
    def __init__(self):
        self.created = []

    def create(self, payload):
        item = {
            "id": f"component-{len(self.created) + 1}",
            **payload,
        }
        self.created.append(item)
        return item


def test_confirmation_creates_editable_ingredient_snapshots():
    meals = FakeMealsRepository()
    ingredients = FakeIngredientsRepository()
    components = FakeMealIngredientsRepository()
    service = ConversationalMealConfirmationService(
        meals_repo=meals,
        ingredients_repo=ingredients,
        meal_ingredients_repo=components,
    )

    result = service.confirm(
        user_id="u1",
        meal_payload={
            "date": "2026-09-01",
            "meal_type": "Pranzo",
            "name": "Carbonara + Mela",
        },
        items=[
            {
                "name": "Carbonara",
                "quantity": 1,
                "unit": "porzione",
                "quantity_g": 350,
                "calories": 700,
                "protein": 30,
                "carbs": 80,
                "fat": 28,
            },
            {
                "name": "Mela",
                "quantity": 1,
                "unit": "pezzo",
                "quantity_g": 150,
                "calories": 78,
                "protein": 0.4,
                "carbs": 21,
                "fat": 0.2,
            },
        ],
    )

    assert result["meal"]["id"] == "meal-1"
    assert len(ingredients.created) == 2
    assert len(components.created) == 2
    assert components.created[0]["quantity_g"] == 350
    assert components.created[1]["quantity_g"] == 150
    assert meals.created["calories"] == 778


def test_confirmation_reuses_existing_canonical_ingredient():
    meals = FakeMealsRepository()
    ingredients = FakeIngredientsRepository()
    components = FakeMealIngredientsRepository()
    existing = ingredients.create(
        {
            "user_id": "u1",
            "name": "Mela",
            "normalized_name": "mela",
            "calories_per_100g": 52,
            "protein_per_100g": 0.3,
            "carbs_per_100g": 14,
            "fat_per_100g": 0.2,
        }
    )
    ingredients.created.clear()

    service = ConversationalMealConfirmationService(
        meals_repo=meals,
        ingredients_repo=ingredients,
        meal_ingredients_repo=components,
    )
    service.confirm(
        user_id="u1",
        meal_payload={
            "date": "2026-09-01",
            "meal_type": "Spuntino",
            "name": "Mela",
        },
        items=[
            {
                "name": "Mela",
                "quantity": 1,
                "unit": "pezzo",
                "quantity_g": 150,
                "calories": 80,
                "protein": 0.5,
                "carbs": 21,
                "fat": 0.2,
            }
        ],
    )

    assert ingredients.created == []
    assert components.created[0]["ingredient_id"] == existing["id"]
    assert meals.created["calories"] == 78
