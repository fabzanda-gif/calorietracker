from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


STRENGTH_WORKOUT_SELECT = (
    "id,user_id,strength_plan_id,"
    "scheduled_date,training_week,"
    "workout_index,title,focus,status,"
    "workout_kind,estimated_duration_minutes,"
    "created_at,updated_at"
)

STRENGTH_EXERCISE_SELECT = (
    "id,user_id,strength_workout_id,"
    "position,exercise_id,exercise_key,exercise_name,"
    "movement_pattern,target_sets,"
    "target_reps_min,target_reps_max,"
    "target_rir,rest_seconds,"
    "prescribed_load_kg,is_user_added,"
    "substituted_from_exercise_id,"
    "prescription_source,created_at"
)


class StrengthWorkoutsRepository(BaseRepository):
    table_name = "strength_workouts"

    def list_recent_free(
        self, user_id: str, *, limit: int = 30
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_WORKOUT_SELECT)
                .eq("user_id", user_id)
                .eq("workout_kind", "free")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load free strength workouts: {exc}"
            ) from exc

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

    def list_date_range(
        self,
        user_id: str,
        start_date: Any,
        end_date: Any,
    ) -> list[dict]:
        try:
            response = (
                self.table
                .select(STRENGTH_WORKOUT_SELECT)
                .eq("user_id", user_id)
                .gte(
                    "scheduled_date",
                    str(start_date),
                )
                .lte(
                    "scheduled_date",
                    str(end_date),
                )
                .order("scheduled_date")
                .order("workout_index")
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength workouts "
                f"for date range: {exc}"
            ) from exc

    def get(
        self,
        user_id: str,
        workout_id: Any,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(STRENGTH_WORKOUT_SELECT)
                .eq("user_id", user_id)
                .eq("id", workout_id)
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength workout: "
                f"{exc}"
            ) from exc


    def reschedule_skipped(
        self,
        *,
        workout_id: Any,
        user_id: str,
        original_date: str,
        new_date: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update({
                    "scheduled_date": new_date,
                    "status": "planned",
                })
                .eq("id", workout_id)
                .eq("user_id", user_id)
                .eq("status", "skipped")
                .eq("scheduled_date", original_date)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to reschedule skipped strength workout: {exc}"
            ) from exc

    def undo_recovery(
        self,
        *,
        workout_id: Any,
        user_id: str,
        original_date: str,
        recovered_date: str,
    ) -> dict | None:
        """Best-effort compensation if plan reactivation fails."""
        try:
            response = (
                self.table
                .update({
                    "scheduled_date": original_date,
                    "status": "skipped",
                })
                .eq("id", workout_id)
                .eq("user_id", user_id)
                .eq("status", "planned")
                .eq("scheduled_date", recovered_date)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                f"Unable to undo strength recovery: {exc}"
            ) from exc

    def update_status(
        self,
        *,
        user_id: str,
        workout_id: Any,
        status: str,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update({"status": status})
                .eq("user_id", user_id)
                .eq("id", workout_id)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to update strength workout: "
                f"{exc}"
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
                "Unable to create strength workout: "
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

    def get(
        self,
        user_id: str,
        exercise_id: Any,
    ) -> dict | None:
        try:
            response = (
                self.table
                .select(STRENGTH_EXERCISE_SELECT)
                .eq("user_id", user_id)
                .eq("id", exercise_id)
                .limit(1)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to load strength exercise: "
                f"{exc}"
            ) from exc

    def update(
        self,
        *,
        user_id: str,
        exercise_id: Any,
        payload: dict[str, Any],
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(payload)
                .eq("user_id", user_id)
                .eq("id", exercise_id)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to update strength "
                f"exercise: {exc}"
            ) from exc

    def update_prescribed_load(
        self,
        *,
        user_id: str,
        exercise_id: Any,
        prescribed_load_kg: float,
    ) -> dict | None:
        try:
            response = (
                self.table
                .update(
                    {
                        "prescribed_load_kg":
                            prescribed_load_kg,
                    }
                )
                .eq("user_id", user_id)
                .eq("id", exercise_id)
                .execute()
            )

            rows = self._data(response)

            return rows[0] if rows else None

        except Exception as exc:
            raise RepositoryError(
                "Unable to update prescribed "
                f"strength load: {exc}"
            ) from exc

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

    def create(
        self,
        payload: dict[str, Any],
    ) -> dict | None:
        created = self.create_many([payload])
        return created[0] if created else None

    def create_many(
        self,
        payloads: list[dict[str, Any]],
    ) -> list[dict]:
        if not payloads:
            return []

        enriched = [
            dict(payload)
            for payload in payloads
        ]

        legacy_keys = sorted({
            str(payload.get("exercise_key"))
            for payload in enriched
            if payload.get("exercise_key")
            and not payload.get("exercise_id")
        })

        if legacy_keys:
            try:
                response = (
                    self.supabase
                    .table("exercises")
                    .select("id,legacy_key")
                    .in_("legacy_key", legacy_keys)
                    .execute()
                )
                library_by_key = {
                    str(item["legacy_key"]):
                        str(item["id"])
                    for item in self._data(response)
                    if item.get("legacy_key")
                    and item.get("id")
                }

                for payload in enriched:
                    key = payload.get(
                        "exercise_key"
                    )
                    if (
                        key
                        and not payload.get(
                            "exercise_id"
                        )
                        and str(key)
                        in library_by_key
                    ):
                        payload["exercise_id"] = (
                            library_by_key[
                                str(key)
                            ]
                        )
            except Exception:
                # Rollout compatibility: plans remain
                # valid even before Exercise Library
                # metadata is available.
                pass

        try:
            response = (
                self.table
                .insert(enriched)
                .execute()
            )

            return self._data(response)

        except Exception as exc:
            raise RepositoryError(
                "Unable to create strength workout "
                f"exercises: {exc}"
            ) from exc
