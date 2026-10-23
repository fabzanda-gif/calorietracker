from __future__ import annotations

from .base import BaseRepository, RepositoryError


class DayBriefingsRepository(BaseRepository):
    table_name = "day_briefings"

    def get(self, user_id: str, day_date, moment: str, mode: str):
        try:
            response = (
                self.table.select("*")
                .eq("user_id", user_id)
                .eq("date", str(day_date))
                .eq("moment", moment)
                .eq("mode", mode)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to load day briefing: {exc}") from exc

    def save(self, payload: dict):
        try:
            response = self.table.upsert(
                payload,
                on_conflict="user_id,date,moment,mode",
            ).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to save day briefing: {exc}") from exc
