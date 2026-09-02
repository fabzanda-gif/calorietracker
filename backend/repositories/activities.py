from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


ACTIVITY_SELECT = (
    "id,user_id,date,activity_name,burned_calories,"
    "source,activity_type,started_at,duration_seconds,"
    "distance_meters,average_cadence,"
    "average_heart_rate,route_points,series_points,"
    "original_point_count,gpx_file_name,estimated_steps"
)


class ActivitiesRepository(BaseRepository):
    table_name = "activities"

    def list_for_date(self, user_id: str, log_date: Any) -> list[dict]:
        try:
            response = (
                self.table
                .select(ACTIVITY_SELECT)
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load activities for {log_date}: {exc}"
            ) from exc

    def list_date_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(ACTIVITY_SELECT)
                .eq("user_id", user_id)
                .gte("date", str(start_date))
                .lte("date", str(end_date))
                .order("date")
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load activities from {start_date} to {end_date}: {exc}"
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
                .select(ACTIVITY_SELECT)
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

    def delete_named_for_date(
        self,
        *,
        user_id: str,
        log_date: Any,
        activity_name: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("user_id", user_id)
                .eq("date", str(log_date))
                .eq(
                    "activity_name",
                    activity_name,
                )
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                "Unable to delete automatic "
                f"activity '{activity_name}': {exc}"
            ) from exc

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
