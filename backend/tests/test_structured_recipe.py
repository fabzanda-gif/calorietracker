import pytest

from backend.services.structured_recipe import (
    StructuredRecipeError,
    StructuredRecipeService,
)


class FakeRecipesRepository:
    def __init__(self):
        self.created = None
        self.deleted = []

    def create(self, payload):
        self.created = dict(payload)
        return {
            "id": "recipe-1",
            **payload,
        }

    def delete(self, recipe_id, user_id):
        self.deleted.append((recipe_id, user_id))
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

    def get_by_id(self, ingredient_id, user_id):
        return self.items.get(ingredient_id)


class FakeRecipeIngredientsRepository:
    def __init__(self):
        self.created = []

    def create(self, payload):
        item = {
            "id": f"link-{len(self.created) + 1}",
            **payload,
        }
        self.created.append(item)
        return item


def build_service():
    recipes = FakeRecipesRepository()
    ingredients = FakeIngredientsRepository()
    links = FakeRecipeIngredientsRepository()

    return (
        StructuredRecipeService(
            recipes_repo=recipes,
            ingredients_repo=ingredients,
            recipe_ingredients_repo=links,
        ),
        recipes,
        links,
    )


def test_structured_recipe_calculates_and_persists_nutrition():
    service, recipes, links = build_service()

    result = service.create(
        user_id="u1",
        recipe_payload={
            "name": "Chicken rice",
            "meal_type": "Cena",
            "recipe_servings": 1,
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

    assert recipes.created["calories"] == 577
    assert recipes.created["protein"] == 61.4
    assert recipes.created["carbs"] == 62.4
    assert recipes.created["fat"] == 7.28

    assert len(recipes.created["ingredients_json"]) == 2
    assert len(links.created) == 2
    assert result["recipe"]["name"] == "Chicken rice"


def test_structured_recipe_rejects_unknown_ingredient():
    service, recipes, links = build_service()

    with pytest.raises(
        StructuredRecipeError,
        match="Ingredient not found",
    ):
        service.create(
            user_id="u1",
            recipe_payload={"name": "Unknown"},
            structured_ingredients=[
                {
                    "ingredient_id": "missing",
                    "quantity": 100,
                    "unit": "g",
                    "quantity_g": 100,
                }
            ],
        )

    assert recipes.created is None
    assert links.created == []


def test_structured_recipe_requires_components():
    service, _, _ = build_service()

    with pytest.raises(
        StructuredRecipeError,
        match="At least one",
    ):
        service.create(
            user_id="u1",
            recipe_payload={"name": "Empty"},
            structured_ingredients=[],
        )


class FakeUpdatableRecipesRepository(FakeRecipesRepository):
    def __init__(self):
        super().__init__()
        self.recipe = {
            "id": "recipe-1",
            "user_id": "u1",
            "name": "Chicken rice",
            "calories": 577,
        }
        self.updated = None

    def get_personal_by_id(self, recipe_id, user_id):
        if recipe_id == "recipe-1" and user_id == "u1":
            return dict(self.recipe)
        return None

    def update(self, recipe_id, user_id, payload):
        self.updated = dict(payload)
        self.recipe.update(payload)
        return dict(self.recipe)


class FakeUpdatableLinksRepository:
    def __init__(self):
        self.rows = [
            {
                "id": "link-rice",
                "recipe_id": "recipe-1",
                "ingredient_id": "rice",
                "quantity": 80,
                "unit": "g",
                "quantity_g": 80,
            },
            {
                "id": "link-chicken",
                "recipe_id": "recipe-1",
                "ingredient_id": "chicken",
                "quantity": 180,
                "unit": "g",
                "quantity_g": 180,
            },
        ]

    def list_for_recipe(self, recipe_id):
        return [
            dict(row)
            for row in self.rows
            if row["recipe_id"] == recipe_id
        ]

    def update(self, row_id, payload):
        row = next(
            item
            for item in self.rows
            if item["id"] == row_id
        )
        row.update(payload)
        return dict(row)

    def create(self, payload):
        row = {
            "id": f"link-{len(self.rows) + 1}",
            **payload,
        }
        self.rows.append(row)
        return dict(row)

    def delete(self, row_id):
        self.rows = [
            row
            for row in self.rows
            if row["id"] != row_id
        ]
        return True


def test_update_changes_quantity_and_recalculates_recipe():
    recipes = FakeUpdatableRecipesRepository()
    ingredients = FakeIngredientsRepository()
    links = FakeUpdatableLinksRepository()

    service = StructuredRecipeService(
        recipes_repo=recipes,
        ingredients_repo=ingredients,
        recipe_ingredients_repo=links,
    )

    result = service.update(
        user_id="u1",
        recipe_id="recipe-1",
        recipe_payload={
            "name": "Chicken rice",
            "meal_type": "Cena",
        },
        structured_ingredients=[
            {
                "ingredient_id": "rice",
                "quantity": 60,
                "unit": "g",
                "quantity_g": 60,
            },
            {
                "ingredient_id": "chicken",
                "quantity": 180,
                "unit": "g",
                "quantity_g": 180,
            },
        ],
    )

    rice_link = next(
        row
        for row in links.rows
        if row["ingredient_id"] == "rice"
    )

    assert rice_link["quantity_g"] == 60

    # Rice: 210 kcal
    # Chicken: 297 kcal
    assert result["nutrition"]["totals"]["calories"] == 507
    assert recipes.updated["calories"] == 507
