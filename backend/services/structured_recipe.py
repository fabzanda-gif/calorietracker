from __future__ import annotations

from typing import Any

from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.recipe_ingredients import (
    RecipeIngredientsRepository,
)
from backend.repositories.recipes import RecipesRepository
from backend.services.recipe_nutrition import (
    RecipeNutritionService,
)


class StructuredRecipeError(ValueError):
    pass


class StructuredRecipeService:
    """
    Create a recipe whose nutrition derives from structured ingredients.

    recipe_library remains the backwards-compatible recipe snapshot.
    recipe_ingredients stores the editable composition.
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

    def create(
        self,
        *,
        user_id: str,
        recipe_payload: dict[str, Any],
        structured_ingredients: list[dict[str, Any]],
    ) -> dict:
        if not structured_ingredients:
            raise StructuredRecipeError(
                "At least one structured ingredient is required"
            )

        components = []

        for component in structured_ingredients:
            ingredient_id = component.get("ingredient_id")

            ingredient = self.ingredients_repo.get_by_id(
                ingredient_id,
                user_id,
            )

            if ingredient is None:
                raise StructuredRecipeError(
                    f"Ingredient not found: {ingredient_id}"
                )

            components.append(
                {
                    "ingredient": ingredient,
                    "quantity": component.get("quantity"),
                    "unit": component.get("unit") or "g",
                    "quantity_g": component.get("quantity_g"),
                }
            )

        nutrition = RecipeNutritionService().calculate(
            components
        )

        payload = dict(recipe_payload)
        payload["user_id"] = user_id
        payload.update(nutrition["totals"])

        # Compatibility snapshot for legacy readers/UI.
        payload["ingredients_json"] = [
            {
                **item,
                "quantity": component["quantity"],
                "unit": component["unit"],
            }
            for item, component in zip(
                nutrition["ingredients"],
                components,
            )
        ]

        recipe = self.recipes_repo.create(payload)

        if recipe is None or recipe.get("id") is None:
            raise StructuredRecipeError(
                "Recipe was created without an id"
            )

        recipe_id = recipe["id"]
        links = []

        try:
            for component in components:
                link = self.recipe_ingredients_repo.create(
                    {
                        "recipe_id": recipe_id,
                        "ingredient_id": (
                            component["ingredient"]["id"]
                        ),
                        "quantity": component["quantity"],
                        "unit": component["unit"],
                        "quantity_g": component["quantity_g"],
                    }
                )

                if link is not None:
                    links.append(link)

        except Exception:
            # Best-effort rollback because repositories are not
            # operating inside one database transaction.
            try:
                self.recipes_repo.delete(
                    recipe_id,
                    user_id,
                )
            except RepositoryError:
                pass
            raise

        return {
            "recipe": recipe,
            "recipe_ingredients": links,
            "nutrition": nutrition,
        }


    def update(
        self,
        *,
        user_id: str,
        recipe_id: Any,
        recipe_payload: dict[str, Any],
        structured_ingredients: list[dict[str, Any]],
    ) -> dict:
        recipe = self.recipes_repo.get_personal_by_id(
            recipe_id,
            user_id,
        )

        if recipe is None:
            raise StructuredRecipeError(
                "Recipe not found"
            )

        if not structured_ingredients:
            raise StructuredRecipeError(
                "At least one structured ingredient is required"
            )

        components = []

        for component in structured_ingredients:
            ingredient_id = component.get("ingredient_id")

            ingredient = self.ingredients_repo.get_by_id(
                ingredient_id,
                user_id,
            )

            if ingredient is None:
                raise StructuredRecipeError(
                    f"Ingredient not found: {ingredient_id}"
                )

            components.append(
                {
                    "ingredient": ingredient,
                    "quantity": component.get("quantity"),
                    "unit": component.get("unit") or "g",
                    "quantity_g": component.get("quantity_g"),
                }
            )

        nutrition = RecipeNutritionService().calculate(
            components
        )

        existing_links = (
            self.recipe_ingredients_repo.list_for_recipe(
                recipe_id
            )
        )

        existing_by_ingredient = {
            str(item.get("ingredient_id")): item
            for item in existing_links
        }

        incoming_ids = {
            str(component["ingredient"]["id"])
            for component in components
        }

        saved_links = []

        # Update existing ingredients or add new ones.
        for component in components:
            ingredient_id = str(
                component["ingredient"]["id"]
            )

            payload = {
                "quantity": component["quantity"],
                "unit": component["unit"],
                "quantity_g": component["quantity_g"],
            }

            existing = existing_by_ingredient.get(
                ingredient_id
            )

            if existing is not None:
                saved = self.recipe_ingredients_repo.update(
                    existing["id"],
                    payload,
                )
            else:
                saved = self.recipe_ingredients_repo.create(
                    {
                        "recipe_id": recipe_id,
                        "ingredient_id": (
                            component["ingredient"]["id"]
                        ),
                        **payload,
                    }
                )

            if saved is not None:
                saved_links.append(saved)

        # Remove ingredients no longer part of the recipe.
        for existing in existing_links:
            if (
                str(existing.get("ingredient_id"))
                not in incoming_ids
            ):
                self.recipe_ingredients_repo.delete(
                    existing["id"]
                )

        payload = dict(recipe_payload)
        payload.update(nutrition["totals"])

        payload["ingredients_json"] = [
            {
                **item,
                "quantity": component["quantity"],
                "unit": component["unit"],
            }
            for item, component in zip(
                nutrition["ingredients"],
                components,
            )
        ]

        updated_recipe = self.recipes_repo.update(
            recipe_id,
            user_id,
            payload,
        )

        return {
            "recipe": (
                updated_recipe
                if updated_recipe is not None
                else {**recipe, **payload}
            ),
            "recipe_ingredients": saved_links,
            "nutrition": nutrition,
        }
