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

    v0.2 predicts a day's context from historical `day_type` values recorded
    on the same weekday, while allowing recent behavior to overtake older
    routines.

    Design rules:
    - no AI / ML;
    - no persistence of predictions yet;
    - missing day_type values are ignored;
    - high confidence requires at least 4 matching weekly observations;
    - the latest 4 matching weekday observations form the strongest signal;
    - one-off deviations do not immediately rewrite an established routine;
    - explicit user data remains authoritative in DayService.
    """

    def __init__(
        self,
        daily_logs_repo: DailyLogsRepository,
        *,
        lookback_weeks: int = 16,
        recent_window: int = 4,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.lookback_weeks = lookback_weeks
        self.recent_window = recent_window

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

        observations = self._same_weekday_observations(
            rows=rows,
            weekday=day_date.weekday(),
        )

        if not observations:
            return self._unknown()

        values = [item["day_type"] for item in observations]
        recent_values = values[-self.recent_window :]

        # Strong routine-change rule:
        # four consecutive recent same-weekday observations with the same
        # context are allowed to replace an older historical pattern.
        if (
            len(recent_values) >= self.recent_window
            and len(set(recent_values)) == 1
        ):
            value = recent_values[-1]
            recent_matches = len(recent_values)

            return {
                "value": value,
                "state": "predicted",
                "source": "routine",
                "confidence": 1.0,
                "confidence_level": HIGH,
                "evidence": {
                    "observations": len(values),
                    "matches": values.count(value),
                    "recent_observations": len(recent_values),
                    "recent_matches": recent_matches,
                    "change_detected": self._historical_mode_differs(
                        older_values=values[:-self.recent_window],
                        recent_value=value,
                    ),
                },
            }

        # Otherwise use a recency-weighted vote. Recent observations matter
        # more, but isolated deviations cannot instantly dominate the history.
        weighted_scores: dict[str, float] = {}
        for index, value in enumerate(values):
            distance_from_latest = len(values) - 1 - index

            if distance_from_latest < self.recent_window:
                weight = 2.0
            else:
                weight = 0.5

            weighted_scores[value] = weighted_scores.get(value, 0.0) + weight

        value = max(
            weighted_scores,
            key=lambda item: (weighted_scores[item], values.count(item)),
        )

        matches = values.count(value)
        probability = matches / len(values)

        return {
            "value": value,
            "state": "predicted",
            "source": "routine",
            "confidence": round(probability, 4),
            "confidence_level": self._confidence_level(
                observations=len(values),
                matches=matches,
                probability=probability,
            ),
            "evidence": {
                "observations": len(values),
                "matches": matches,
                "recent_observations": len(recent_values),
                "recent_matches": recent_values.count(value),
                "change_detected": False,
            },
        }

    @staticmethod
    def _same_weekday_observations(
        *,
        rows: list[dict],
        weekday: int,
    ) -> list[dict]:
        observations = []

        for row in rows:
            raw_date = row.get("date")
            day_type = row.get("day_type")

            if not raw_date or not day_type:
                continue

            try:
                row_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            if row_date.weekday() != weekday:
                continue

            observations.append(
                {
                    "date": row_date,
                    "day_type": day_type,
                }
            )

        observations.sort(key=lambda item: item["date"])
        return observations

    @staticmethod
    def _historical_mode_differs(
        *,
        older_values: list[str],
        recent_value: str,
    ) -> bool:
        if not older_values:
            return False

        historical_mode = Counter(older_values).most_common(1)[0][0]
        return historical_mode != recent_value

    @staticmethod
    def _confidence_level(
        *,
        observations: int,
        matches: int,
        probability: float,
    ) -> str:
        if observations >= 4 and matches >= 4 and probability >= 0.80:
            return HIGH

        if observations >= 3 and matches >= 3 and probability >= 0.75:
            return MEDIUM

        return LOW

    @staticmethod
    def _unknown() -> dict:
        return {
            "value": None,
            "state": "unknown",
            "source": None,
            "confidence": None,
            "confidence_level": None,
            "evidence": {
                "observations": 0,
                "matches": 0,
                "recent_observations": 0,
                "recent_matches": 0,
                "change_detected": False,
            },
        }
