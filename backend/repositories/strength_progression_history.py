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

    def apply_atomic(
        self,
        *,
        user_id: str,
        strength_plan_id: Any,
        source_workout_id: Any,
        source_exercise_id: Any,
        target_workout_id: Any,
        target_exercise_id: Any,
        exercise_key: str,
        outcome: str,
        action: str,
        observed_load_kg: float,
        expected_before_load_kg: float | None,
        after_load_kg: float,
    ) -> dict:
        try:
            response = self.supabase.rpc(
                "apply_strength_progression_atomic",
                {
                    "p_user_id": user_id,
                    "p_strength_plan_id":
                        strength_plan_id,
                    "p_source_workout_id":
                        source_workout_id,
                    "p_source_exercise_id":
                        source_exercise_id,
                    "p_target_workout_id":
                        target_workout_id,
                    "p_target_exercise_id":
                        target_exercise_id,
                    "p_exercise_key":
                        exercise_key,
                    "p_outcome": outcome,
                    "p_action": action,
                    "p_observed_load_kg":
                        observed_load_kg,
                    "p_expected_before_load_kg":
                        expected_before_load_kg,
                    "p_after_load_kg":
                        after_load_kg,
                },
            ).execute()

            data = getattr(
                response,
                "data",
                None,
            )

            if isinstance(data, dict):
                return data

            if (
                isinstance(data, list)
                and data
                and isinstance(data[0], dict)
            ):
                return data[0]

            raise RepositoryError(
                "Atomic strength progression "
                "returned no result"
            )

        except RepositoryError:
            raise

        except Exception as exc:
            raise RepositoryError(
                "Unable to apply atomic strength "
                f"progression: {exc}"
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
