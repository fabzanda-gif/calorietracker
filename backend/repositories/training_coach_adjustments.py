from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


TRAINING_COACH_ADJUSTMENT_SELECT = (
    "id,user_id,source_kind,source_id,source_date,"
    "target_kind,target_id,target_date,action,severity,"
    "scope,decision,title,message,proposed_changes,"
    "before_state,after_state,created_at,updated_at"
)


class TrainingCoachAdjustmentsRepository(
    BaseRepository
):
    table_name = "training_coach_adjustments"

    def get(
        self,
        adjustment_id: Any,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    TRAINING_COACH_ADJUSTMENT_SELECT
                )
                .eq("id", adjustment_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load training coach "
                f"adjustment: {exc}"
            ) from exc

    def get_for_signal(
        self,
        *,
        user_id: str,
        source_kind: str,
        source_id: str,
        target_kind: str,
        target_id: Any,
        action: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    TRAINING_COACH_ADJUSTMENT_SELECT
                )
                .eq("user_id", user_id)
                .eq("source_kind", source_kind)
                .eq("source_id", source_id)
                .eq("target_kind", target_kind)
                .eq("target_id", target_id)
                .eq("action", action)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load training coach "
                f"signal: {exc}"
            ) from exc

    def list_recent(
        self,
        *,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(
                    TRAINING_COACH_ADJUSTMENT_SELECT
                )
                .eq("user_id", user_id)
                .gte("target_date", str(start_date))
                .lte("target_date", str(end_date))
                .order("created_at", desc=True)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                "Unable to list training coach "
                f"adjustments: {exc}"
            ) from exc

    def get_for_target_action(
        self,
        *,
        user_id: str,
        target_kind: str,
        target_id: Any,
        action: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    TRAINING_COACH_ADJUSTMENT_SELECT
                )
                .eq("user_id", user_id)
                .eq("target_kind", target_kind)
                .eq("target_id", target_id)
                .eq("action", action)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load target training "
                f"coach adjustment: {exc}"
            ) from exc

    def create(
        self,
        payload: dict[str, Any],
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
                "Unable to save training coach "
                f"adjustment: {exc}"
            ) from exc

    def update(
        self,
        *,
        adjustment_id: Any,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", adjustment_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to update training coach "
                f"adjustment: {exc}"
            ) from exc
