from __future__ import annotations

from typing import Any

from backend.repositories.ingredients import (
    IngredientsRepository,
)
from backend.repositories.recipe_ingredients import (
    RecipeIngredientsRepository,
)
from backend.repositories.recipes import (
    RecipesRepository,
)
from backend.services.ingredient_names import (
    normalize_ingredient_name,
)


class LegacyRecipeMigrationService:
    """
    Upgrade legacy ingredients_json into structured
    ingredients + recipe_ingredients.

    Safe to run repeatedly:
    - ingredients are reused by normalized name;
    - recipes already containing structured links are skipped.
    """

    def __init__(
        self,
        *,
        recipes_repo: RecipesRepository,
        ingredients_repo: IngredientsRepository,
        recipe_ingredients_repo: RecipeIngredientsRepository,
    ):
        self.recipes_repo = recipes_repo
        self.ingredients_repo = ingredients_repo
        self.recipe_ingredients_repo = recipe_ingredients_repo

    def migrate_user(
        self,
        *,
        user_id: str,
    ) -> dict[str, int]:
        recipes = self.recipes_repo.list_personal(
            user_id
        )

        migrated_recipes = 0
        created_ingredients = 0
        created_links = 0
        skipped_recipes = 0

        for recipe in recipes:
            recipe_id = recipe.get("id")

            if recipe_id is None:
                continue

            existing_links = (
                self.recipe_ingredients_repo.list_for_recipe(
                    recipe_id
                )
            )

            existing_ingredient_ids = {
                str(link.get("ingredient_id"))
                for link in existing_links
                if link.get("ingredient_id") is not None
            }

            legacy = recipe.get(
                "ingredients_json"
            )

            if not isinstance(legacy, list) or not legacy:
                skipped_recipes += 1
                continue

            recipe_links = 0

            for legacy_item in legacy:
                if not isinstance(
                    legacy_item,
                    dict,
                ):
                    continue

                name = str(
                    legacy_item.get("name")
                    or ""
                ).strip()

                if not name:
                    continue

                quantity_g = self._positive(
                    legacy_item.get(
                        "quantity_g"
                    )
                )

                if quantity_g is None:
                    continue

                normalized = (
                    normalize_ingredient_name(
                        name
                    )
                )

                ingredient = (
                    self.ingredients_repo
                    .get_by_normalized_name(
                        normalized,
                        user_id,
                    )
                )

                if ingredient is None:
                    ingredient = (
                        self.ingredients_repo.create(
                            {
                                "user_id": user_id,
                                "name": name,
                                "normalized_name": normalized,
                                "calories_per_100g": self._number(
                                    legacy_item.get(
                                        "calories_per_100g"
                                    )
                                ),
                                "protein_per_100g": self._number(
                                    legacy_item.get(
                                        "protein_per_100g"
                                    )
                                ),
                                "carbs_per_100g": self._number(
                                    legacy_item.get(
                                        "carbs_per_100g"
                                    )
                                ),
                                "fat_per_100g": self._number(
                                    legacy_item.get(
                                        "fat_per_100g"
                                    )
                                ),
                                "default_unit": "g",
                            }
                        )
                    )

                    if ingredient is not None:
                        created_ingredients += 1

                if (
                    ingredient is None
                    or ingredient.get("id") is None
                ):
                    continue

                ingredient_id = str(
                    ingredient["id"]
                )

                if (
                    ingredient_id
                    in existing_ingredient_ids
                ):
                    continue

                link = (
                    self.recipe_ingredients_repo.create(
                        {
                            "recipe_id": recipe_id,
                            "ingredient_id": ingredient[
                                "id"
                            ],
                            "quantity": quantity_g,
                            "unit": "g",
                            "quantity_g": quantity_g,
                        }
                    )
                )

                if link is not None:
                    created_links += 1
                    recipe_links += 1
                    existing_ingredient_ids.add(
                        ingredient_id
                    )

            if recipe_links:
                migrated_recipes += 1
            else:
                skipped_recipes += 1

        return {
            "migrated_recipes":
                migrated_recipes,
            "created_ingredients":
                created_ingredients,
            "created_links":
                created_links,
            "skipped_recipes":
                skipped_recipes,
        }

    @staticmethod
    def _number(
        value: Any,
    ) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _positive(
        value: Any,
    ) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if number <= 0:
            return None

        return number
