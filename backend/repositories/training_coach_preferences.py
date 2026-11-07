from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


TRAINING_COACH_PRIORITY_VALUES = {
    "gym",
    "balanced",
    "running",
}


class TrainingCoachPreferencesRepository(
    BaseRepository
):
    table_name = "training_coach_preferences"

    def get(
        self,
        user_id: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    "user_id,priority,"
                    "created_at,updated_at"
                )
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load training coach "
                f"preferences: {exc}"
            ) from exc

    def get_priority(
        self,
        user_id: str,
    ) -> str:
        item = self.get(user_id)

        priority = str(
            (item or {}).get("priority")
            or "balanced"
        ).strip().lower()

        if priority not in (
            TRAINING_COACH_PRIORITY_VALUES
        ):
            return "balanced"

        return priority

    def upsert(
        self,
        *,
        user_id: str,
        priority: str,
        updated_at: Any,
    ) -> dict | None:
        normalized = str(
            priority
        ).strip().lower()

        if normalized not in (
            TRAINING_COACH_PRIORITY_VALUES
        ):
            raise ValueError(
                "Unsupported training coach priority"
            )

        try:
            response = (
                self.table
                .upsert(
                    {
                        "user_id": user_id,
                        "priority": normalized,
                        "updated_at": updated_at,
                    },
                    on_conflict="user_id",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to save training coach "
                f"preferences: {exc}"
            ) from exc
