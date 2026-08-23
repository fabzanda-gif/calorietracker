from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository


def _known_value(value: Any) -> dict:
    if value is None or value == "":
        return {
            "value": None,
            "state": "unknown",
            "source": None,
            "confidence": None,
        }

    return {
        "value": value,
        "state": "confirmed",
        "source": "user",
        "confidence": 1.0,
    }


class DayService:
    """
    Product-level representation of a SanoSync day.

    Day Model v0.1 interprets existing daily_logs values without changing
    the database schema. Prediction states will be introduced later by the
    Memory Engine.
    """

    def __init__(self, daily_logs_repo: DailyLogsRepository):
        self.daily_logs_repo = daily_logs_repo

    def build_day(self, user_id: str, day_date: date) -> dict:
        row = self.daily_logs_repo.get_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        )
        row = row or {}

        return {
            "date": str(day_date),
            "context": _known_value(row.get("day_type")),
            "activity_plan": _known_value(row.get("activity_plan")),
            "actual": {
                "weight": row.get("weight"),
                "steps": row.get("steps"),
            },
        }
