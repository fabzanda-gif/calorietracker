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
        """
        Move a weight measurement to another date safely.

        The old Streamlit implementation deleted the entire original
        `daily_logs` row before upserting the new date. That could erase steps
        or day-planning data stored in that row.

        This implementation:
        1. clears only the old row's weight;
        2. upserts the weight on the new date.
        """
        try:
            (
                self.table
                .update({"weight": None})
                .eq("id", row_id)
                .eq("user_id", user_id)
                .execute()
            )

            response = (
                self.table
                .upsert(
                    {
                        "user_id": user_id,
                        "date": str(new_date),
                        "weight": float(weight),
                    },
                    on_conflict="user_id,date",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to move weight: {exc}"
            ) from exc

