from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


STRENGTH_WORKOUT_LOG_SELECT = (
    "id,user_id,strength_workout_id,"
    "performed_date,duration_minutes,"
    "notes,status,started_at,completed_at,"
    "created_at,updated_at"
)

STRENGTH_SET_LOG_SELECT = (
    "id,user_id,strength_workout_log_id,"
    "strength_workout_exercise_id,"
    "set_index,reps,load_kg,rir,feeling,"
    "created_at,updated_at"
)


class StrengthWorkoutLogsRepository(
    BaseRepository
):
    table_name = "strength_workout_logs"

    def get_for_workout(
        self,
        user_id: str,
        workout_id: Any,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(
                    STRENGTH_WORKOUT_LOG_SELECT
                )
                .eq("user_id", user_id)
                .eq(
                    "strength_workout_id",
                    workout_id,
                )
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength "
                f"workout log: {exc}"
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
                .select(
                    STRENGTH_WORKOUT_LOG_SELECT
                )
                .eq("user_id", user_id)
                .eq("status", "completed")
                .gte(
                    "performed_date",
                    str(start_date),
                )
                .lte(
                    "performed_date",
                    str(end_date),
                )
                .order(
                    "performed_date",
                    desc=True,
                )
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                "Unable to load completed strength "
                f"workout logs: {exc}"
            ) from exc

    def list_recent_sessions(
        self,
        user_id: str,
        *,
        status: str,
        limit: int = 30,
    ) -> list[dict]:
        if status not in ("draft", "completed"):
            raise ValueError("Invalid strength session status")
        try:
            response = (
                self.table
                .select(STRENGTH_WORKOUT_LOG_SELECT)
                .eq("user_id", user_id)
                .eq("status", status)
                .order("performed_date", desc=True)
                .limit(limit)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load recent strength sessions: {exc}"
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
                f"workout log: {exc}"
            ) from exc

    def update(
        self,
        log_id: Any,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("id", log_id)
                .eq("user_id", user_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to update strength "
                f"workout log: {exc}"
            ) from exc

    def delete(
        self,
        log_id: Any,
        user_id: str,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("id", log_id)
                .eq("user_id", user_id)
                .execute()
            )

            return True

        except Exception as exc:
            raise RepositoryError(
                "Unable to delete strength "
                f"workout log: {exc}"
            ) from exc


class StrengthSetLogsRepository(
    BaseRepository
):
    table_name = "strength_set_logs"

    def upsert_set(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.table
                .upsert(
                    payload,
                    on_conflict=(
                        "strength_workout_log_id,"
                        "strength_workout_exercise_id,"
                        "set_index"
                    ),
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to save strength set: "
                f"{exc}"
            ) from exc

    def delete_set(
        self,
        *,
        user_id: str,
        workout_log_id: Any,
        exercise_id: Any,
        set_index: int,
    ) -> bool:
        try:
            (
                self.table
                .delete()
                .eq("user_id", user_id)
                .eq(
                    "strength_workout_log_id",
                    workout_log_id,
                )
                .eq(
                    "strength_workout_exercise_id",
                    exercise_id,
                )
                .eq("set_index", set_index)
                .execute()
            )
            return True
        except Exception as exc:
            raise RepositoryError(
                "Unable to delete strength set: "
                f"{exc}"
            ) from exc

    def create_many(
        self,
        payloads: list[dict[str, Any]],
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
                "Unable to create strength "
                f"set logs: {exc}"
            ) from exc

    def list_for_workout_log(
        self,
        user_id: str,
        workout_log_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_SET_LOG_SELECT)
                .eq("user_id", user_id)
                .eq(
                    "strength_workout_log_id",
                    workout_log_id,
                )
                .order(
                    "strength_workout_exercise_id"
                )
                .order("set_index")
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength "
                f"set logs: {exc}"
            ) from exc
