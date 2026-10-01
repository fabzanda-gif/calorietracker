from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


INGREDIENT_COLUMNS = (
    "id,user_id,name,normalized_name,"
    "calories_per_100g,protein_per_100g,"
    "carbs_per_100g,fat_per_100g,"
    "default_unit,grams_per_unit,default_quantity,"
    "kind,meal_slots,created_at"
)


class IngredientsRepository(BaseRepository):
    table_name = "ingredients"

    def list_for_user(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(INGREDIENT_COLUMNS)
                .eq("user_id", user_id)
                .order("name")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load ingredients: {exc}"
            ) from exc

    def get_by_normalized_name(
        self,
        normalized_name: str,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(INGREDIENT_COLUMNS)
                .eq("user_id", user_id)
                .eq(
                    "normalized_name",
                    normalized_name,
                )
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load ingredient by name: {exc}"
            ) from exc

    def get_by_id(
        self,
        ingredient_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(INGREDIENT_COLUMNS)
                .eq("id", ingredient_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load ingredient: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create ingredient: {exc}"
            ) from exc

    def update(
        self,
        ingredient_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", ingredient_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update ingredient: {exc}"
            ) from exc

    def delete(
        self,
        ingredient_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", ingredient_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete ingredient: {exc}"
            ) from exc
