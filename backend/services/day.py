from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository
from backend.services.memory import MemoryService


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

    v0.2 keeps explicit daily_logs planning authoritative and only asks the
    MemoryService for a context prediction when no user-confirmed day_type
    exists for the requested day.
    """

    def __init__(
        self,
        daily_logs_repo: DailyLogsRepository,
        memory_service: MemoryService | None = None,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.memory_service = memory_service or MemoryService(daily_logs_repo)

    def build_day(self, user_id: str, day_date: date) -> dict:
        row = self.daily_logs_repo.get_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        )
        row = row or {}

        context = _known_value(row.get("day_type"))

        if context["state"] == "unknown":
            prediction = self.memory_service.predict_context(
                user_id=user_id,
                day_date=day_date,
            )
            if prediction["state"] == "predicted":
                context = prediction

        return {
            "date": str(day_date),
            "context": context,
            "activity_plan": _known_value(row.get("activity_plan")),
            "actual": {
                "weight": row.get("weight"),
                "steps": row.get("steps"),
            },
        }
