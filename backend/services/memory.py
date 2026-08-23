from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from backend.repositories.daily_logs import DailyLogsRepository


LOW = "low"
MEDIUM = "medium"
HIGH = "high"


class MemoryService:
    """
    Deterministic SanoSync routine memory.

    v0.3 predicts both:
    - day context from `day_type`
    - planned activity from `activity_plan`

    Both use the same weekday-based routine logic:
    - no AI / ML;
    - no prediction persistence yet;
    - missing values are ignored;
    - recent observations matter more;
    - four recent consistent weekly observations can establish or replace
      a high-confidence routine;
    - isolated deviations do not immediately rewrite established patterns.
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
        return self._predict_weekday_field(
            user_id=user_id,
            day_date=day_date,
            field_name="day_type",
        )

    def predict_activity_plan(
        self,
        user_id: str,
        day_date: date,
    ) -> dict:
        return self._predict_weekday_field(
            user_id=user_id,
            day_date=day_date,
            field_name="activity_plan",
        )

    def _predict_weekday_field(
        self,
        *,
        user_id: str,
        day_date: date,
        field_name: str,
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
            field_name=field_name,
        )

        if not observations:
            return self._unknown()

        values = [item["value"] for item in observations]
        recent_values = values[-self.recent_window :]

        if (
            len(recent_values) >= self.recent_window
            and len(set(recent_values)) == 1
        ):
            value = recent_values[-1]

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
                    "recent_matches": len(recent_values),
                    "change_detected": self._historical_mode_differs(
                        older_values=values[:-self.recent_window],
                        recent_value=value,
                    ),
                },
            }

        weighted_scores: dict[str, float] = {}
        for index, value in enumerate(values):
            distance_from_latest = len(values) - 1 - index
            weight = 2.0 if distance_from_latest < self.recent_window else 0.5
            weighted_scores[value] = weighted_scores.get(value, 0.0) + weight

        value = max(
            weighted_scores,
            key=lambda item: (
                weighted_scores[item],
                values.count(item),
            ),
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
        field_name: str,
    ) -> list[dict]:
        observations = []

        for row in rows:
            raw_date = row.get("date")
            value = row.get(field_name)

            if not raw_date or not value:
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
                    "value": value,
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
