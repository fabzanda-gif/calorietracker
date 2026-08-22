from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class DailyLogsRepository(BaseRepository):
    table_name = "daily_logs"

    def get_for_date(self, user_id: str, log_date: Any) -> dict | None:
        try:
            response = (
                self.table
                .select("id,user_id,date,weight,steps,day_type,activity_plan")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load daily log for {log_date}: {exc}"
            ) from exc

    def upsert_for_date(
        self,
        user_id: str,
        log_date: Any,
        values: dict,
    ) -> dict | None:
        payload = {
            "user_id": user_id,
            "date": str(log_date),
            **values,
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
                f"Unable to save daily log: {exc}"
            ) from exc

    def update_by_id(
        self,
        row_id: Any,
        user_id: str,
        values: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(values)
                .eq("id", row_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update daily log: {exc}"
            ) from exc
