from __future__ import annotations

from datetime import date
from typing import Any


class TrainingLoadService:
    RUNNING_TYPES = {
        "corsa",
        "running",
        "run",
        "jogging",
    }

    LOWER_CARDIO_TYPES = {
        "ciclismo",
        "cycling",
        "bike",
        "bicicletta",
        "padel",
        "tennis",
        "calcio",
        "football",
        "soccer",
    }

    LOWER_PATTERNS = {
        "squat",
        "hinge",
        "single_leg",
        "legs",
        "calf",
    }

    UPPER_PATTERNS = {
        "horizontal_push",
        "vertical_push",
        "horizontal_pull",
        "vertical_pull",
    }

    def activity_event(
        self,
        *,
        activity: dict[str, Any],
        planned: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        activity_type = self._normalized(
            activity.get("activity_type")
            or activity.get("activity_name")
        )

        if activity_type in {"passi", "steps", "walking steps"}:
            return None

        source_date = self._date(
            activity.get("date")
        )
        source_id = activity.get("id")

        if source_date is None or source_id is None:
            return None

        duration_minutes = (
            self._number(
                activity.get("duration_seconds")
            )
            / 60.0
        )
        distance_meters = self._number(
            activity.get("distance_meters")
        )

        planned_intensity = self._normalized(
            (planned or {}).get("intensity")
        )

        intensity = self._activity_intensity(
            activity_type=activity_type,
            duration_minutes=duration_minutes,
            distance_meters=distance_meters,
            planned_intensity=planned_intensity,
        )

        if (
            activity_type in self.RUNNING_TYPES
            or activity_type
            in self.LOWER_CARDIO_TYPES
        ):
            scope = "lower"
        else:
            scope = "cardio"

        modality = (
            "running"
            if activity_type in self.RUNNING_TYPES
            else "cardio"
        )

        score = self._score(
            duration_minutes=duration_minutes,
            intensity=intensity,
            fallback=self._number(
                activity.get("burned_calories")
            )
            / 8.0,
        )

        return {
            "source_kind": "activity",
            "source_id": str(source_id),
            "date": str(source_date),
            "title": (
                activity.get("activity_name")
                or "Attività"
            ),
            "modality": modality,
            "scope": scope,
            "intensity": intensity,
            "load_score": score,
            "duration_minutes": round(
                duration_minutes,
                1,
            ),
            "distance_meters": round(
                distance_meters,
                1,
            ),
            "planned_activity_id":
                activity.get(
                    "planned_activity_id"
                ),
        }

    def strength_event(
        self,
        *,
        workout: dict[str, Any],
        workout_log: dict[str, Any],
        exercises: list[dict[str, Any]],
        set_logs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if (
            workout_log.get("status")
            not in {None, "completed"}
        ):
            return None

        source_date = self._date(
            workout_log.get("performed_date")
        )
        source_id = workout.get("id")

        if source_date is None or source_id is None:
            return None

        scope = self._strength_scope(
            workout=workout,
            exercises=exercises,
        )

        duration_minutes = self._number(
            workout_log.get("duration_minutes")
        )
        set_count = len(set_logs)
        volume_load = sum(
            self._number(item.get("load_kg"))
            * self._number(item.get("reps"))
            for item in set_logs
        )

        feelings = {
            self._normalized(item.get("feeling"))
            for item in set_logs
            if item.get("feeling")
        }

        intensity = self._strength_intensity(
            duration_minutes=duration_minutes,
            set_count=set_count,
            feelings=feelings,
        )

        base = max(
            duration_minutes,
            set_count * 4.0,
        )

        score = self._score(
            duration_minutes=base,
            intensity=intensity,
            fallback=0.0,
        )

        return {
            "source_kind": "strength_workout",
            "source_id": str(source_id),
            "date": str(source_date),
            "title": (
                workout.get("title")
                or "Workout palestra"
            ),
            "modality": "strength",
            "scope": scope,
            "intensity": intensity,
            "load_score": score,
            "duration_minutes": round(
                duration_minutes,
                1,
            ),
            "set_count": set_count,
            "volume_load": round(
                volume_load,
                1,
            ),
            "workout_kind": (
                workout.get("workout_kind")
                or "planned"
            ),
        }

    def _strength_scope(
        self,
        *,
        workout: dict[str, Any],
        exercises: list[dict[str, Any]],
    ) -> str:
        focus = self._normalized(
            workout.get("focus")
        )

        if focus in {"lower", "legs"}:
            return "lower"

        if focus in {
            "upper",
            "push",
            "pull",
        }:
            return "upper"

        if focus == "full body":
            return "full_body"

        patterns = {
            self._normalized(
                item.get("movement_pattern")
            ).replace(" ", "_")
            for item in exercises
        }

        has_lower = bool(
            patterns & self.LOWER_PATTERNS
        )
        has_upper = bool(
            patterns & self.UPPER_PATTERNS
        )

        if has_lower and has_upper:
            return "full_body"
        if has_lower:
            return "lower"
        if has_upper:
            return "upper"

        return "full_body"

    def _activity_intensity(
        self,
        *,
        activity_type: str,
        duration_minutes: float,
        distance_meters: float,
        planned_intensity: str,
    ) -> str:
        if planned_intensity in {"hard", "race"}:
            return "high"

        if planned_intensity == "moderate":
            return "moderate"

        if planned_intensity == "low":
            return "low"

        if activity_type in self.RUNNING_TYPES:
            if (
                distance_meters >= 9000
                or duration_minutes >= 55
            ):
                return "high"

            if (
                distance_meters >= 5000
                or duration_minutes >= 30
            ):
                return "moderate"

            return "low"

        if duration_minutes >= 60:
            return "high"

        if duration_minutes >= 30:
            return "moderate"

        return "low"

    @staticmethod
    def _strength_intensity(
        *,
        duration_minutes: float,
        set_count: int,
        feelings: set[str],
    ) -> str:
        if (
            "too hard" in feelings
            or "too_hard" in feelings
            or duration_minutes >= 65
            or set_count >= 16
        ):
            return "high"

        if (
            "hard" in feelings
            or duration_minutes >= 35
            or set_count >= 8
        ):
            return "moderate"

        return "low"

    @staticmethod
    def _score(
        *,
        duration_minutes: float,
        intensity: str,
        fallback: float,
    ) -> float:
        multiplier = {
            "low": 1.0,
            "moderate": 1.5,
            "high": 2.0,
        }.get(intensity, 1.0)

        base = (
            duration_minutes
            if duration_minutes > 0
            else fallback
        )

        return round(
            max(0.0, base) * multiplier,
            1,
        )

    @staticmethod
    def _normalized(value: Any) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .split()
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, date):
            return value

        if not value:
            return None

        try:
            return date.fromisoformat(
                str(value)[:10]
            )
        except ValueError:
            return None
