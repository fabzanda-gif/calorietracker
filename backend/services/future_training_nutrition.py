from __future__ import annotations

from datetime import date, timedelta
from typing import Any


class FutureTrainingNutritionService:
    """
    Translate tomorrow's planned running session into
    a small deterministic nutrition context.

    Tomorrow's estimated exercise calories are deliberately
    NOT added to today's calorie budget.
    """

    def build(
        self,
        *,
        day_date: date,
        planned_activities: list[dict[str, Any]],
    ) -> dict:
        tomorrow = day_date + timedelta(days=1)

        sessions = [
            item
            for item in planned_activities
            if (
                str(item.get("scheduled_date") or "")
                == str(tomorrow)
                and str(
                    item.get("status") or "planned"
                ) == "planned"
                and bool(
                    item.get("training_plan_id")
                )
            )
        ]

        if not sessions:
            return self._empty(tomorrow)

        scored = [
            (
                self._load_score(item),
                item,
            )
            for item in sessions
        ]

        score, primary = max(
            scored,
            key=lambda pair: pair[0],
        )

        if score >= 2:
            level = "high"
            carb_focus = True
        elif score == 1:
            level = "moderate"
            carb_focus = True
        else:
            level = "low"
            carb_focus = False

        return {
            "date": str(tomorrow),
            "level": level,
            "carb_focus": carb_focus,
            "session_count": len(sessions),
            "primary_session": {
                "id": primary.get("id"),
                "title": primary.get("title"),
                "session_kind": primary.get(
                    "session_kind"
                ),
                "distance_meters": self._number(
                    primary.get("distance_meters")
                ),
                "duration_minutes": self._number(
                    primary.get("duration_minutes")
                ),
                "training_week": primary.get(
                    "training_week"
                ),
            },
        }

    @classmethod
    def _load_score(
        cls,
        activity: dict[str, Any],
    ) -> int:
        kind = str(
            activity.get("session_kind") or ""
        ).strip().lower()

        distance = cls._number(
            activity.get("distance_meters")
        )
        duration = cls._number(
            activity.get("duration_minutes")
        )

        if kind == "race":
            return 2

        if kind == "long" and distance >= 10000:
            return 2

        if distance >= 12000:
            return 2

        if duration >= 75:
            return 2

        if kind in {"tempo", "interval"}:
            return 1

        if kind == "long":
            return 1

        if duration >= 45:
            return 1

        return 0

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
    def _empty(tomorrow: date) -> dict:
        return {
            "date": str(tomorrow),
            "level": "none",
            "carb_focus": False,
            "session_count": 0,
            "primary_session": None,
        }
