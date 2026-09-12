from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


DAILY_LOG_COLUMNS = (
    "id,user_id,date,weight,steps,day_type,activity_plan"
)
LEGACY_DAILY_LOG_COLUMNS = (
    "id,user_id,date,weight,steps"
)


class DailyLogsRepository(BaseRepository):
    """
    Repository for the shared `daily_logs` table.

    A single row can contain weight, steps and planning data. Writes are
    therefore partial upserts/updates so one feature never destroys fields
    belonging to another feature.
    """

    table_name = "daily_logs"

    def get_for_date_compatible(self, user_id: str, log_date: Any) -> dict | None:
        try:
            response = (
                self.table
                .select(DAILY_LOG_COLUMNS)
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception:
            try:
                response = (
                    self.table
                    .select(LEGACY_DAILY_LOG_COLUMNS)
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

    def get_for_date(self, user_id: str, log_date: Any) -> dict | None:
        return self.get_for_date_compatible(user_id, log_date)

    def upsert_for_date(
        self,
        user_id: str,
        log_date: Any,
        values: dict,
    ) -> dict | None:
        payload = {"user_id": user_id, "date": str(log_date), **values}
        try:
            response = (
                self.table
                .upsert(payload, on_conflict="user_id,date")
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to save daily log: {exc}") from exc

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
            raise RepositoryError(f"Unable to update daily log: {exc}") from exc

    def list_date_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
        columns: str = DAILY_LOG_COLUMNS,
    ) -> list[dict]:
        cache_key = (
            "list_date_range",
            str(user_id),
            str(start_date),
            str(end_date),
            str(columns),
        )

        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        try:
            response = (
                self.table
                .select(columns)
                .eq("user_id", user_id)
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .order("date", desc=False)
                .execute()
            )
            return self._store_cache(
                cache_key,
                self._data(response),
            )
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load daily logs in date range: {exc}"
            ) from exc

    def list_weight_history(self, user_id: str) -> list[dict]:
        try:
            response = (
                self.table
                .select("weight,date")
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

    def list_weight_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select("date,weight")
                .eq("user_id", user_id)
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .not_.is_("weight", "null")
                .order("date", desc=False)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(f"Unable to load weight range: {exc}") from exc

    def list_all(
        self,
        user_id: str,
        columns: str = DAILY_LOG_COLUMNS,
        *,
        ascending: bool = True,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(columns)
                .eq("user_id", user_id)
                .order("date", desc=not ascending)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(f"Unable to load daily logs: {exc}") from exc
