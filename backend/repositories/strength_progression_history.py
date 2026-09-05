from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


STRENGTH_PROGRESSION_HISTORY_SELECT = (
    "id,user_id,strength_plan_id,"
    "source_workout_id,source_exercise_id,"
    "target_workout_id,target_exercise_id,"
    "exercise_key,outcome,action,"
    "observed_load_kg,before_load_kg,"
    "after_load_kg,created_at"
)


class StrengthProgressionHistoryRepository(
    BaseRepository
):
    table_name = "strength_progression_history"

    def get_for_source_exercise(
        self,
        user_id: str,
        source_exercise_id: Any,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    STRENGTH_PROGRESSION_HISTORY_SELECT
                )
                .eq("user_id", user_id)
                .eq(
                    "source_exercise_id",
                    source_exercise_id,
                )
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength "
                f"progression history: {exc}"
            ) from exc

    def get_for_target_exercise(
        self,
        user_id: str,
        target_exercise_id: Any,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    STRENGTH_PROGRESSION_HISTORY_SELECT
                )
                .eq("user_id", user_id)
                .eq(
                    "target_exercise_id",
                    target_exercise_id,
                )
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load target strength "
                f"progression history: {exc}"
            ) from exc

    def list_for_plan(
        self,
        user_id: str,
        plan_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(
                    STRENGTH_PROGRESSION_HISTORY_SELECT
                )
                .eq("user_id", user_id)
                .eq(
                    "strength_plan_id",
                    plan_id,
                )
                .order(
                    "created_at",
                    desc=True,
                )
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to list strength "
                f"progression history: {exc}"
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
                "Unable to create strength "
                f"progression history: {exc}"
            ) from exc

    def delete(
        self,
        history_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", history_id)
                .eq("user_id", user_id)
                .execute()
            )

            return True

        except Exception as exc:
            raise RepositoryError(
                "Unable to delete strength "
                f"progression history: {exc}"
            ) from exc
