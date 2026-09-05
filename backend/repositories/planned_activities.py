from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


PLANNED_ACTIVITY_SELECT = (
    "id,user_id,scheduled_date,scheduled_time,"
    "title,activity_type,duration_minutes,"
    "distance_meters,intensity,notes,status,"
    "training_plan_id,training_week,session_kind,"
    "created_at,updated_at"
)


class PlannedActivitiesRepository(BaseRepository):
    table_name = "planned_activities"

    def list_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(PLANNED_ACTIVITY_SELECT)
                .eq("user_id", user_id)
                .gte("scheduled_date", str(start_date))
                .lte("scheduled_date", str(end_date))
                .order("scheduled_date")
                .order("scheduled_time")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load planned activities: {exc}"
            ) from exc

    def create(self, payload: dict) -> dict | None:
        try:
            response = self.table.insert(payload).execute()
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create planned activity: {exc}"
            ) from exc

    def create_many(
        self,
        payloads: list[dict],
    ) -> list[dict]:
        if not payloads:
            return []

        try:
            response = (
                self.table
                .insert(payloads)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create planned activities: {exc}"
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
                f"Unable to update planned activity: {exc}"
            ) from exc

    def delete(
        self,
        activity_id: Any,
        user_id: str,
    ) -> bool:
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
                f"Unable to delete planned activity: {exc}"
            ) from exc
