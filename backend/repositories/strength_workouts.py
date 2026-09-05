from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


STRENGTH_WORKOUT_SELECT = (
    "id,user_id,strength_plan_id,"
    "scheduled_date,training_week,"
    "workout_index,title,focus,status,"
    "estimated_duration_minutes,"
    "created_at,updated_at"
)

STRENGTH_EXERCISE_SELECT = (
    "id,user_id,strength_workout_id,"
    "position,exercise_key,exercise_name,"
    "movement_pattern,target_sets,"
    "target_reps_min,target_reps_max,"
    "target_rir,rest_seconds,"
    "prescribed_load_kg,created_at"
)


class StrengthWorkoutsRepository(BaseRepository):
    table_name = "strength_workouts"

    def list_for_plan(
        self,
        user_id: str,
        plan_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_WORKOUT_SELECT)
                .eq("user_id", user_id)
                .eq(
                    "strength_plan_id",
                    plan_id,
                )
                .order("scheduled_date")
                .order("workout_index")
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength workouts: "
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
                "Unable to create strength workouts: "
                f"{exc}"
            ) from exc


class StrengthWorkoutExercisesRepository(
    BaseRepository
):
    table_name = "strength_workout_exercises"

    def list_for_workout(
        self,
        user_id: str,
        workout_id: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_EXERCISE_SELECT)
                .eq("user_id", user_id)
                .eq(
                    "strength_workout_id",
                    workout_id,
                )
                .order("position")
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength workout "
                f"exercises: {exc}"
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
                "Unable to create strength workout "
                f"exercises: {exc}"
            ) from exc
