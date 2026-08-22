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

    def get_named_for_date(
        self,
        user_id: str,
        log_date: Any,
        activity_name: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select("id,user_id,date,activity_name,burned_calories")
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .eq("activity_name", activity_name)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load activity '{activity_name}': {exc}"
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

    def update(
        self,
        activity_id: Any,
        user_id: str,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", activity_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to update activity: {exc}"
            ) from exc

    def set_named_calories(
        self,
        user_id: str,
        log_date: Any,
        activity_name: str,
        burned_calories: int,
    ) -> dict | None:
        row = self.get_named_for_date(user_id, log_date, activity_name)
        if row is None:
            return None
        return self.update(
            activity_id=row["id"],
            user_id=user_id,
            payload={"burned_calories": int(burned_calories)},
        )

    def upsert_named_for_date(
        self,
        user_id: str,
        log_date: Any,
        activity_name: str,
        burned_calories: int,
    ) -> dict | None:
        row = self.get_named_for_date(user_id, log_date, activity_name)
        if row is not None:
            return self.update(
                activity_id=row["id"],
                user_id=user_id,
                payload={"burned_calories": int(burned_calories)},
            )
        return self.create(
            {
                "user_id": user_id,
                "date": str(log_date),
                "activity_name": activity_name,
                "burned_calories": int(burned_calories),
            }
        )

    def delete(self, activity_id: Any, user_id: str) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", activity_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete activity: {exc}"
            ) from exc
