from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class ActivitiesRepository(BaseRepository):
    table_name = "activities"

    def list_for_date(self, user_id: str, log_date: Any) -> list[dict]:
        try:
            response = (
                self.table
                .select("id,user_id,date,activity_name,burned_calories")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load activities for {log_date}: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create activity: {exc}"
            ) from exc

    def delete(self, activity_id: Any, user_id: str) -> bool:
        try:
            self.table.delete().eq("id", activity_id).eq(
                "user_id", user_id
            ).execute()
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete activity: {exc}"
            ) from exc
