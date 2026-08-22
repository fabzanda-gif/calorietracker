from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


MEAL_COLUMNS = (
    "id,user_id,date,meal_type,name,base_name,quantity,is_per_100g,"
    "base_calories,base_protein,base_carbs,base_fat,"
    "calories,protein,carbs,fat,notes,category,"
    "ingredients_json,recipe_servings,is_shared,image_url"
)


class MealsRepository(BaseRepository):
    table_name = "meals"

    def list_for_date(self, user_id: str, log_date: Any) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meals for {log_date}: {exc}"
            ) from exc

    def list_history(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_COLUMNS)
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meal history: {exc}"
            ) from exc

    def breakfast_exists(self, user_id: str, log_date: Any) -> bool:
        try:
            response = (
                self.table
                .select("id")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .eq("meal_type", "Colazione")
                .limit(1)
                .execute()
            )
            return bool(self._data(response))
        except Exception as exc:
            raise RepositoryError(
                f"Unable to check breakfast: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to create meal: {exc}") from exc

    def update(self, meal_id: Any, user_id: str, payload: dict) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", meal_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to update meal: {exc}") from exc

    def delete(self, meal_id: Any, user_id: str) -> bool:
        try:
            self.table.delete().eq("id", meal_id).eq(
                "user_id", user_id
            ).execute()
            return True
        except Exception as exc:
            raise RepositoryError(f"Unable to delete meal: {exc}") from exc
