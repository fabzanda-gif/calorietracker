from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


DECISION_SELECTION_COLUMNS = (
    "id,user_id,date,meal_slot,meal_type,mode,lens,option_index,"
    "selected_at,candidate,decision_context,created_at"
)


class DecisionSelectionsRepository(BaseRepository):
    table_name = "decision_selections"

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to save decision selection: {exc}"
            ) from exc

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(DECISION_SELECTION_COLUMNS)
                .eq("user_id", user_id)
                .order("selected_at", desc=True)
                .limit(limit)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load decision selections: {exc}"
            ) from exc

    def list_date_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(DECISION_SELECTION_COLUMNS)
                .eq("user_id", user_id)
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .order("selected_at", desc=False)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load decision selections in range: {exc}"
            ) from exc
