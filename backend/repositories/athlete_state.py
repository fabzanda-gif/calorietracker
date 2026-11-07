from __future__ import annotations

from datetime import date, timedelta

from .base import BaseRepository, RepositoryError


class AthleteStateRepository(BaseRepository):
    """Bounded, owner-scoped reads; no new persistence tables."""

    table_name = "strength_workout_logs"

    def completed_strength_history(
        self, user_id: str, *, as_of: date, days: int = 56
    ) -> dict:
        start = as_of - timedelta(days=days - 1)
        try:
            logs_response = (
                self.table
                .select("id,strength_workout_id,performed_date,status,duration_minutes")
                .eq("user_id", user_id)
                .eq("status", "completed")
                .gte("performed_date", start.isoformat())
                .lte("performed_date", as_of.isoformat())
                .order("performed_date", desc=True)
                .limit(400)
                .execute()
            )
            logs = self._data(logs_response)
            log_ids = [str(x["id"]) for x in logs]
            workout_ids = sorted({str(x["strength_workout_id"]) for x in logs})
            sets = []
            exercises = []
            workouts = []
            # Chunk ID lists to keep requests within PostgREST URL limits.
            for offset in range(0, len(log_ids), 80):
                ids = log_ids[offset:offset + 80]
                for first in range(0, 4000, 500):
                    page = self._data(
                        self.supabase.table("strength_set_logs")
                        .select(
                            "strength_workout_log_id,strength_workout_exercise_id,"
                            "set_index,reps,load_kg,rir,feeling"
                        )
                        .eq("user_id", user_id)
                        .in_("strength_workout_log_id", ids)
                        .order("id")
                        .range(first, first + 499)
                        .execute()
                    )
                    sets.extend(page)
                    if len(page) < 500:
                        break
                else:
                    raise RepositoryError("Too many sets to calculate reliable Athlete State")
            for offset in range(0, len(workout_ids), 80):
                ids = workout_ids[offset:offset + 80]
                workouts.extend(self._data(
                    self.supabase.table("strength_workouts")
                    .select("id,title,focus,workout_kind")
                    .eq("user_id", user_id)
                    .in_("id", ids)
                    .execute()
                ))
                exercises.extend(self._data(
                    self.supabase.table("strength_workout_exercises")
                    .select("id,strength_workout_id,exercise_id,exercise_key,exercise_name,movement_pattern")
                    .eq("user_id", user_id)
                    .in_("strength_workout_id", ids)
                    .execute()
                ))
            return {
                "logs": logs, "sets": sets,
                "workouts": workouts, "exercises": exercises,
                "truncated": len(logs) == 400,
            }
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError(f"Unable to load Athlete State history: {exc}") from exc

    def training_profile(self, user_id: str) -> dict | None:
        try:
            rows = self._data(
                self.supabase.table("training_profiles")
                .select("sessions_per_week,experience_level,coach_style")
                .eq("user_id", user_id).limit(1).execute()
            )
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(f"Unable to load training profile: {exc}") from exc
