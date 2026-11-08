from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class WeightRepository(BaseRepository):
    """
    Weight is stored in `daily_logs`, matching the existing SanoSync schema.

    Important: a daily_logs row may also contain steps and planning data.
    Weight deletion/movement therefore clears only the `weight` field and
    never deletes the whole daily row.
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

    def history_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select("id,date,weight")
                .eq("user_id", user_id)
                .not_.is_("weight", "null")
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .order("date", desc=False)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load ranged weight history: {exc}"
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

    def save(
        self,
        user_id: str,
        log_date: Any,
        weight: float,
    ) -> dict | None:
        payload = {
            "user_id": user_id,
            "date": str(log_date),
            "weight": float(weight),
        }
        try:
            response = (
                self.table
                .upsert(
                    payload,
                    on_conflict="user_id,date",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to save weight: {exc}"
            ) from exc

    def update_weight(
        self,
        row_id: Any,
        user_id: str,
        weight: float,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update({"weight": float(weight)})
                .eq("id", row_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update weight: {exc}"
            ) from exc

    def delete_weight(
        self,
        row_id: Any,
        user_id: str,
    ) -> dict | None:
        """
        Clear only weight. Never delete a daily_logs row because it may also
        contain steps/day_type/activity_plan.
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

    def move_weight(
        self,
        row_id: Any,
        user_id: str,
        new_date: Any,
        weight: float,
    ) -> dict | None:
        """Move only weight in one database transaction, preserving daily data."""
        try:
            response = (
                self.supabase.rpc("move_weight_atomic", {
                    "p_row_id": row_id,
                    "p_user_id": user_id,
                    "p_new_date": str(new_date),
                    "p_weight": float(weight),
                })
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to move weight: {exc}"
            ) from exc
