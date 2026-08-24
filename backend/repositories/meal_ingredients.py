from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


MEAL_INGREDIENT_COLUMNS = (
    "id,meal_id,ingredient_id,name_snapshot,"
    "quantity,unit,quantity_g,"
    "calories,protein,carbs,fat,created_at"
)


class MealIngredientsRepository(BaseRepository):
    table_name = "meal_ingredients"

    def list_for_meal(
        self,
        meal_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_INGREDIENT_COLUMNS)
                .eq("meal_id", meal_id)
                .order("created_at")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meal ingredients: {exc}"
            ) from exc

    def create(
        self,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .insert(payload)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create meal ingredient: {exc}"
            ) from exc

    def delete_for_meal(
        self,
        meal_id: Any,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("meal_id", meal_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to clear meal ingredients: {exc}"
            ) from exc
