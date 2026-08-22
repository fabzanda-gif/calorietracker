from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class WeightRepository(BaseRepository):
    """
    Weight remains stored in `daily_logs`, matching the current database schema.
    """

    table_name = "daily_logs"

    def history(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select("id,date,weight")
                .eq("user_id", user_id)
                .not_.is_("weight", "null")
                .order("date", desc=False)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load weight history: {exc}"
            ) from exc

    def latest(self, user_id: str) -> dict | None:
        try:
            response = (
                self.table
                .select("id,date,weight")
                .eq("user_id", user_id)
                .not_.is_("weight", "null")
                .order("date", desc=True)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load latest weight: {exc}"
            ) from exc

    def save(self, user_id: str, log_date: Any, weight: float) -> dict | None:
        payload = {
            "user_id": user_id,
            "date": str(log_date),
            "weight": float(weight),
        }
        try:
            response = (
                self.table
                .upsert(payload, on_conflict="user_id,date")
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to save weight: {exc}"
            ) from exc

    def delete_weight(self, row_id: Any, user_id: str) -> dict | None:
        """
        Do not delete the entire daily_log row: steps/day-plan may share it.
        Clear only the weight column.
        """
        try:
            response = (
                self.table
                .update({"weight": None})
                .eq("id", row_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to clear weight: {exc}"
            ) from exc
