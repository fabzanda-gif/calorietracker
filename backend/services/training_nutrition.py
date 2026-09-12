from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


class TrainingNutritionService:
    RUNNING_TYPES = {
        "corsa",
        "running",
        "run",
        "jogging",
    }

    def build(
        self,
        *,
        day_date: date,
        planned_activities: list[dict[str, Any]],
        actual_activities: list[dict[str, Any]] | None = None,
        weight_kg: float | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        actual_activities = actual_activities or []
        now = now or datetime.now()

        today_sessions = [
            item
            for item in planned_activities
            if (
                str(item.get("scheduled_date") or "")
                == str(day_date)
                and str(
                    item.get("status") or "planned"
                ).lower()
                == "planned"
            )
        ]

        tomorrow = date.fromordinal(
            day_date.toordinal() + 1
        )

        tomorrow_sessions = [
            item
            for item in planned_activities
            if (
                str(item.get("scheduled_date") or "")
                == str(tomorrow)
                and str(
                    item.get("status") or "planned"
                ).lower()
                == "planned"
            )
        ]

        completed_today = [
            item
            for item in actual_activities
            if str(item.get("date") or "") == str(day_date)
        ]

        primary_today = self._primary(
            today_sessions
        )
        primary_tomorrow = self._primary(
            tomorrow_sessions
        )

        completed_primary = self._primary_actual(
            completed_today
        )

        if completed_primary is not None:
            return self._recovery_context(
                activity=completed_primary,
                weight_kg=weight_kg,
            )

        if primary_today is not None:
            return self._pre_training_context(
                session=primary_today,
                weight_kg=weight_kg,
                day_date=day_date,
                now=now,
            )

        if primary_tomorrow is not None:
            return self._tomorrow_context(
                session=primary_tomorrow,
                weight_kg=weight_kg,
            )

        return {
            "phase": "normal",
            "priority": "normal",
            "message_key": "normal",
            "session": None,
            "hours_to_start": None,
            "carbs_target_g": None,
            "protein_target_g": None,
            "carb_focus": False,
            "protein_focus": False,
        }

    def _pre_training_context(
        self,
        *,
        session: dict[str, Any],
        weight_kg: float | None,
        day_date: date,
        now: datetime,
    ) -> dict[str, Any]:
        race = (
            str(
                session.get("session_kind")
                or ""
            ).lower()
            == "race"
        )

        distance_m = self._number(
            session.get("distance_meters")
        )
        duration_min = self._number(
            session.get("duration_minutes")
        )

        high_load = (
            race
            or distance_m >= 15000
            or duration_min >= 90
        )

        start = self._session_datetime(
            session,
            day_date,
        )

        hours_to_start = None

        if start is not None:
            hours_to_start = max(
                0.0,
                (
                    start - now
                ).total_seconds()
                / 3600,
            )

        grams_per_kg = self._pre_carbs_per_kg(
            hours_to_start=hours_to_start,
            high_load=high_load,
        )

        carbs = self._gram_range(
            weight_kg,
            grams_per_kg,
        )

        return {
            "phase": (
                "pre_race"
                if race
                else "pre_training"
            ),
            "priority": (
                "race"
                if race
                else (
                    "high"
                    if high_load
                    else "moderate"
                )
            ),
            "message_key": (
                "race_today"
                if race
                else "training_today"
            ),
            "session": self._session_payload(
                session
            ),
            "hours_to_start": (
                round(hours_to_start, 1)
                if hours_to_start is not None
                else None
            ),
            "carbs_target_g": carbs,
            "protein_target_g": None,
            "carb_focus": (
                high_load
                or grams_per_kg[1] >= 2
            ),
            "protein_focus": False,
            "guidance": [
                "prefer_familiar_foods",
                "limit_heavy_fat_near_start",
                "limit_excess_fibre_near_start",
                "hydrate_normally",
            ],
        }

    def _recovery_context(
        self,
        *,
        activity: dict[str, Any],
        weight_kg: float | None,
    ) -> dict[str, Any]:
        distance_m = self._number(
            activity.get("distance_meters")
        )
        duration_s = self._number(
            activity.get("duration_seconds")
        )

        substantial = (
            distance_m >= 10000
            or duration_s >= 3600
        )

        carbs = (
            self._gram_range(
                weight_kg,
                (1.0, 1.2),
            )
            if substantial
            else self._gram_range(
                weight_kg,
                (0.5, 0.8),
            )
        )

        protein = self._gram_range(
            weight_kg,
            (0.25, 0.3),
        )

        return {
            "phase": "recovery",
            "priority": (
                "high"
                if substantial
                else "moderate"
            ),
            "message_key": "post_training",
            "session": {
                "title": (
                    activity.get("activity_name")
                    or "Attività"
                ),
                "activity_type": (
                    activity.get("activity_type")
                ),
                "distance_meters": distance_m,
                "duration_minutes": (
                    round(duration_s / 60)
                    if duration_s
                    else None
                ),
                "session_kind": None,
            },
            "hours_to_start": None,
            "carbs_target_g": carbs,
            "protein_target_g": protein,
            "carb_focus": substantial,
            "protein_focus": True,
            "guidance": [
                "carbs_for_recovery",
                "protein_for_recovery",
                "replace_fluids",
            ],
        }

    def _tomorrow_context(
        self,
        *,
        session: dict[str, Any],
        weight_kg: float | None,
    ) -> dict[str, Any]:
        race = (
            str(
                session.get("session_kind")
                or ""
            ).lower()
            == "race"
        )

        distance_m = self._number(
            session.get("distance_meters")
        )
        duration_min = self._number(
            session.get("duration_minutes")
        )

        high_load = (
            race
            or distance_m >= 12000
            or duration_min >= 75
        )

        carbs = (
            self._gram_range(
                weight_kg,
                (4.0, 6.0),
            )
            if high_load
            else None
        )

        return {
            "phase": "tomorrow_prep",
            "priority": (
                "race"
                if race
                else (
                    "high"
                    if high_load
                    else "low"
                )
            ),
            "message_key": (
                "race_tomorrow"
                if race
                else "training_tomorrow"
            ),
            "session": self._session_payload(
                session
            ),
            "hours_to_start": None,
            "carbs_target_g": carbs,
            "protein_target_g": None,
            "carb_focus": high_load,
            "protein_focus": False,
            "guidance": (
                [
                    "spread_carbs_across_day",
                    "prefer_familiar_foods",
                    "hydrate_normally",
                ]
                if high_load
                else []
            ),
        }

    @staticmethod
    def _pre_carbs_per_kg(
        *,
        hours_to_start: float | None,
        high_load: bool,
    ) -> tuple[float, float]:
        if hours_to_start is None:
            return (
                (2.0, 3.0)
                if high_load
                else (1.0, 2.0)
            )

        if hours_to_start >= 4:
            return (
                (3.0, 4.0)
                if high_load
                else (2.0, 3.0)
            )

        if hours_to_start >= 2:
            return (2.0, 3.0)

        if hours_to_start >= 1:
            return (1.0, 2.0)

        return (0.5, 1.0)

    @classmethod
    def _primary(
        cls,
        sessions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not sessions:
            return None

        return max(
            sessions,
            key=cls._session_score,
        )

    @classmethod
    def _primary_actual(
        cls,
        activities: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        training = [
            item
            for item in activities
            if cls._normalized(
                item.get("activity_type")
                or item.get("activity_name")
            )
            not in {
                "passi",
                "steps",
            }
        ]

        if not training:
            return None

        return max(
            training,
            key=lambda item: (
                cls._number(
                    item.get("distance_meters")
                )
                + cls._number(
                    item.get("duration_seconds")
                )
            ),
        )

    @classmethod
    def _session_score(
        cls,
        item: dict[str, Any],
    ) -> float:
        kind = str(
            item.get("session_kind") or ""
        ).lower()

        race_bonus = (
            1_000_000
            if kind == "race"
            else 0
        )

        return (
            race_bonus
            + cls._number(
                item.get("distance_meters")
            )
            + cls._number(
                item.get("duration_minutes")
            )
            * 100
        )

    @staticmethod
    def _session_payload(
        session: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": session.get("id"),
            "title": session.get("title"),
            "activity_type": (
                session.get("activity_type")
            ),
            "session_kind": (
                session.get("session_kind")
            ),
            "scheduled_time": (
                session.get("scheduled_time")
            ),
            "distance_meters": (
                TrainingNutritionService._number(
                    session.get(
                        "distance_meters"
                    )
                )
            ),
            "duration_minutes": (
                TrainingNutritionService._number(
                    session.get(
                        "duration_minutes"
                    )
                )
            ),
        }

    @staticmethod
    def _session_datetime(
        session: dict[str, Any],
        day_date: date,
    ) -> datetime | None:
        raw = str(
            session.get("scheduled_time")
            or ""
        ).strip()

        if not raw:
            return None

        try:
            parsed = time.fromisoformat(
                raw
            )
        except ValueError:
            return None

        return datetime.combine(
            day_date,
            parsed,
        )

    @staticmethod
    def _gram_range(
        weight_kg: float | None,
        per_kg: tuple[float, float],
    ) -> dict[str, int] | None:
        try:
            weight = float(weight_kg or 0)
        except (TypeError, ValueError):
            return None

        if weight <= 0:
            return None

        return {
            "min": round(
                weight * per_kg[0]
            ),
            "max": round(
                weight * per_kg[1]
            ),
        }

    @staticmethod
    def _normalized(value: Any) -> str:
        return str(
            value or ""
        ).strip().casefold()

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0
