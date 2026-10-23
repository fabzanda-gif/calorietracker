from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


TRAINING_PLAN_SELECT = (
    "id,user_id,sport,start_date,target_date,"
    "current_distance_meters,"
    "current_pace_seconds_per_km,"
    "target_distance_meters,"
    "target_pace_seconds_per_km,"
    "sessions_per_week,long_run_weekday,"
    "total_weeks,status,created_at,updated_at"
)


class TrainingPlansRepository(BaseRepository):
    table_name = "training_plans"

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(TRAINING_PLAN_SELECT)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load training plans: {exc}"
            ) from exc

    def create(
        self,
        payload: dict,
    ) -> dict | None:
        try:
            response = (
                self.table
                .insert(payload)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to create training plan: {exc}"
            ) from exc

    def delete(
        self,
        plan_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", plan_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                f"Unable to delete training plan: {exc}"
            ) from exc
