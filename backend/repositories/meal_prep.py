from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


MEAL_PREP_COLUMNS = (
    "id,user_id,recipe_id,name,prepared_at,expires_at,"
    "portions_prepared,portions_remaining,"
    "calories_per_portion,protein_per_portion,"
    "carbs_per_portion,fat_per_portion,status,created_at"
)


class MealPrepRepository(BaseRepository):
    table_name = "meal_prep_batches"

    def list_all(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_PREP_COLUMNS)
                .eq("user_id", user_id)
                .order("prepared_at", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meal prep inventory: {exc}"
            ) from exc

    def list_available(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(MEAL_PREP_COLUMNS)
                .eq("user_id", user_id)
                .eq("status", "available")
                .gt("portions_remaining", 0)
                .order("expires_at", desc=False)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load available meal prep: {exc}"
            ) from exc

    def get_by_id(
        self,
        batch_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(MEAL_PREP_COLUMNS)
                .eq("id", batch_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load meal prep batch: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create meal prep batch: {exc}"
            ) from exc

    def update(
        self,
        batch_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", batch_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update meal prep batch: {exc}"
            ) from exc
