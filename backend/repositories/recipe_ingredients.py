from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


RECIPE_INGREDIENT_COLUMNS = (
    "id,recipe_id,ingredient_id,"
    "quantity,unit,quantity_g,created_at"
)


class RecipeIngredientsRepository(BaseRepository):
    table_name = "recipe_ingredients"

    def list_for_recipe(
        self,
        recipe_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(
                    RECIPE_INGREDIENT_COLUMNS
                    + ",ingredients("
                    "id,name,normalized_name,"
                    "calories_per_100g,protein_per_100g,"
                    "carbs_per_100g,fat_per_100g,"
                    "default_unit"
                    ")"
                )
                .eq("recipe_id", recipe_id)
                .order("created_at")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load recipe ingredients: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create recipe ingredient: {exc}"
            ) from exc

    def update(
        self,
        row_id: Any,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", row_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update recipe ingredient: {exc}"
            ) from exc

    def delete(
        self,
        row_id: Any,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", row_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete recipe ingredient: {exc}"
            ) from exc

    def delete_for_recipe(
        self,
        recipe_id: Any,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("recipe_id", recipe_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to clear recipe ingredients: {exc}"
            ) from exc
