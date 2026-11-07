from __future__ import annotations

from datetime import date
from typing import Any

from .base import BaseRepository, RepositoryError


WEEKLY_SCHEDULE_COLUMNS = (
    "id,user_id,week_start,day_of_week,context,created_at,updated_at"
)


class WeeklyScheduleRepository(BaseRepository):
    table_name = "weekly_schedule"

    def list_for_week(
        self,
        user_id: str,
        week_start: date,
    ) -> list[dict[str, Any]]:
        try:
            response = (
                self.table
                .select(WEEKLY_SCHEDULE_COLUMNS)
                .eq("user_id", user_id)
                .eq("week_start", week_start.isoformat())
                .order("day_of_week")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load weekly schedule: {exc}"
            ) from exc

    def upsert_day(
        self,
        user_id: str,
        week_start: date,
        day_of_week: int,
        context: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.table
                .upsert(
                    {
                        "user_id": user_id,
                        "week_start": week_start.isoformat(),
                        "day_of_week": day_of_week,
                        "context": context,
                    },
                    on_conflict="user_id,week_start,day_of_week",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to save weekly schedule day: {exc}"
            ) from exc

    def delete_day(
        self,
        user_id: str,
        week_start: date,
        day_of_week: int,
    ) -> bool:
        try:
            self.table.delete().eq(
                "user_id", user_id
            ).eq(
                "week_start", week_start.isoformat()
            ).eq(
                "day_of_week", day_of_week
            ).execute()

            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete weekly schedule day: {exc}"
            ) from exc
