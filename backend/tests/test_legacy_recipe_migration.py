from backend.services.legacy_recipe_migration import (
    LegacyRecipeMigrationService,
)


class FakeRecipesRepository:
    def list_personal(self, user_id):
        return [
            {
                "id": "recipe-1",
                "name": "Chicken Rice",
                "ingredients_json": [
                    {
                        "name": "Basmati Rice",
                        "quantity_g": 80,
                        "calories_per_100g": 350,
                        "protein_per_100g": 7,
                        "carbs_per_100g": 78,
                        "fat_per_100g": 0.6,
                    },
                    {
                        "name": "Chicken Breast",
                        "quantity_g": 125,
                        "calories_per_100g": 105,
                        "protein_per_100g": 23,
                        "carbs_per_100g": 0,
                        "fat_per_100g": 1.5,
                    },
                ],
            }
        ]


class FakeIngredientsRepository:
    def __init__(self):
        self.items = {}
        self.created = []

    def get_by_normalized_name(
        self,
        normalized_name,
        user_id,
    ):
        return self.items.get(
            normalized_name
        )

    def create(self, payload):
        item = {
            "id": (
                f"ingredient-"
                f"{len(self.created) + 1}"
            ),
            **payload,
        }

        self.created.append(item)
        self.items[
            payload["normalized_name"]
        ] = item

        return item


class FakeRecipeIngredientsRepository:
    def __init__(self):
        self.links = []

    def list_for_recipe(self, recipe_id):
        return [
            row
            for row in self.links
            if row["recipe_id"] == recipe_id
        ]

    def create(self, payload):
        item = {
            "id": (
                f"link-"
                f"{len(self.links) + 1}"
            ),
            **payload,
        }
        self.links.append(item)
        return item


def test_migrates_legacy_recipe():
    ingredients = (
        FakeIngredientsRepository()
    )
    links = (
        FakeRecipeIngredientsRepository()
    )

    result = LegacyRecipeMigrationService(
        recipes_repo=FakeRecipesRepository(),
        ingredients_repo=ingredients,
        recipe_ingredients_repo=links,
    ).migrate_user(
        user_id="u1",
    )

    assert result["migrated_recipes"] == 1
    assert result["created_ingredients"] == 2
    assert result["created_links"] == 2

    assert (
        links.links[0]["quantity_g"]
        == 80
    )


def test_migration_is_idempotent():
    ingredients = (
        FakeIngredientsRepository()
    )
    links = (
        FakeRecipeIngredientsRepository()
    )

    service = LegacyRecipeMigrationService(
        recipes_repo=FakeRecipesRepository(),
        ingredients_repo=ingredients,
        recipe_ingredients_repo=links,
    )

    first = service.migrate_user(
        user_id="u1"
    )
    second = service.migrate_user(
        user_id="u1"
    )

    assert first["created_links"] == 2

    assert second[
        "migrated_recipes"
    ] == 0

    assert second[
        "created_ingredients"
    ] == 0

    assert second[
        "created_links"
    ] == 0

    assert len(ingredients.created) == 2
    assert len(links.links) == 2


def test_existing_ingredient_is_reused():
    ingredients = (
        FakeIngredientsRepository()
    )

    ingredients.items[
        "basmati rice"
    ] = {
        "id": "existing-rice",
        "name": "Basmati Rice",
        "normalized_name":
            "basmati rice",
    }

    links = (
        FakeRecipeIngredientsRepository()
    )

    result = LegacyRecipeMigrationService(
        recipes_repo=FakeRecipesRepository(),
        ingredients_repo=ingredients,
        recipe_ingredients_repo=links,
    ).migrate_user(
        user_id="u1",
    )

    assert (
        result["created_ingredients"]
        == 1
    )

    rice = next(
        item
        for item in links.links
        if item["quantity_g"] == 80
    )

    assert (
        rice["ingredient_id"]
        == "existing-rice"
    )
