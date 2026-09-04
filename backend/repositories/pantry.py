from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import BaseRepository, RepositoryError


PANTRY_COLUMNS = (
    "id,user_id,ingredient_id,quantity,unit,"
    "expires_at,created_at,updated_at,ingredients(name)"
)


class PantryRepository(BaseRepository):
    table_name = "pantry_items"

    def list_for_user(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select(PANTRY_COLUMNS)
                .eq("user_id", user_id)
                .order("expires_at")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load pantry: {exc}"
            ) from exc

    def get_by_id(
        self,
        item_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(PANTRY_COLUMNS)
                .eq("id", item_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load pantry item: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create pantry item: {exc}"
            ) from exc

    def update(
        self,
        item_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            payload = {
                **payload,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            response = (
                self.table
                .update(payload)
                .eq("id", item_id)
                .eq("user_id", user_id)
                .execute()
            )

            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update pantry item: {exc}"
            ) from exc

    def delete(
        self,
        item_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", item_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete pantry item: {exc}"
            ) from exc
