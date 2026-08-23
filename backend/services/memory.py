from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from backend.repositories.daily_logs import DailyLogsRepository


LOW = "low"
MEDIUM = "medium"
HIGH = "high"


class MemoryService:
    """
    Deterministic context-memory service.

    v0.1 predicts a day's context from confirmed historical `day_type` values
    recorded on the same weekday.

    Design rules:
    - no AI / ML;
    - no persistence of predictions yet;
    - missing day_type values are ignored;
    - high confidence requires at least 4 matching weekly observations;
    - explicit day data always wins elsewhere in DayService.
    """

    def __init__(
        self,
        daily_logs_repo: DailyLogsRepository,
        *,
        lookback_weeks: int = 12,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.lookback_weeks = lookback_weeks

    def predict_context(
        self,
        user_id: str,
        day_date: date,
    ) -> dict:
        start_date = day_date - timedelta(weeks=self.lookback_weeks)
        end_date = day_date - timedelta(days=1)

        rows = self.daily_logs_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        same_weekday = []
        for row in rows:
            raw_date = row.get("date")
            day_type = row.get("day_type")

            if not raw_date or not day_type:
                continue

            try:
                row_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            if row_date.weekday() == day_date.weekday():
                same_weekday.append(day_type)

        if not same_weekday:
            return {
                "value": None,
                "state": "unknown",
                "source": None,
                "confidence": None,
                "confidence_level": None,
                "evidence": {
                    "observations": 0,
                    "matches": 0,
                },
            }

        counts = Counter(same_weekday)
        value, matches = counts.most_common(1)[0]
        observations = len(same_weekday)
        probability = matches / observations

        return {
            "value": value,
            "state": "predicted",
            "source": "routine",
            "confidence": round(probability, 4),
            "confidence_level": self._confidence_level(
                observations=observations,
                matches=matches,
                probability=probability,
            ),
            "evidence": {
                "observations": observations,
                "matches": matches,
            },
        }

    @staticmethod
    def _confidence_level(
        *,
        observations: int,
        matches: int,
        probability: float,
    ) -> str:
        # SanoSync must earn the right to assume.
        # Even 100% consistency cannot be "high" before 4 weekly matches.
        if observations >= 4 and matches >= 4 and probability >= 0.80:
            return HIGH

        if observations >= 3 and matches >= 3 and probability >= 0.75:
            return MEDIUM

        return LOW
