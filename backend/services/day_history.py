from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from backend.repositories.activities import ActivitiesRepository
from backend.repositories.daily_logs import DailyLogsRepository


DAY_TYPES = ("office", "home", "free")


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_day_type(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"office", "ufficio", "work", "lavoro"}:
        return "office"

    if normalized in {"home", "casa", "wfh"}:
        return "home"

    if normalized in {"free", "free_day", "rest", "riposo", "libero"}:
        return "free"

    return None


class DayHistoryService:
    """
    Historical activity profile grouped by day type.

    Uses only completed daily logs with an explicit day_type.
    Activity calories are aggregated per day before calculating
    the historical statistics, so a day with multiple activities
    is counted once.
    """

    def __init__(
        self,
        daily_logs_repo: DailyLogsRepository,
        activities_repo: ActivitiesRepository,
    ):
        self.daily_logs_repo = daily_logs_repo
        self.activities_repo = activities_repo

    def average_activity_kcal(
        self,
        *,
        user_id: str,
        end_date: date,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """
        Average burned calories across complete calendar days.

        Days without recorded activity count as zero.
        """
        lookback_days = max(1, int(lookback_days))
        start_date = end_date - timedelta(days=lookback_days - 1)

        activities = self.activities_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        calories_by_date: dict[str, float] = defaultdict(float)

        for activity in activities:
            raw_date = activity.get("date")
            if raw_date is None:
                continue

            try:
                activity_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            if not start_date <= activity_date <= end_date:
                continue

            calories_by_date[str(activity_date)] += max(
                0.0,
                _number(activity.get("burned_calories")),
            )

        total = sum(
            calories_by_date.get(
                str(start_date + timedelta(days=offset)),
                0.0,
            )
            for offset in range(lookback_days)
        )

        return {
            "lookback_days": lookback_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_burned_calories": round(total, 2),
            "average_burned_calories": round(
                total / lookback_days,
                2,
            ),
        }

    def activity_profile_by_day_type(
        self,
        user_id: str,
        end_date: date | None = None,
        lookback_days: int = 180,
    ) -> dict[str, dict[str, Any]]:
        if end_date is None:
            end_date = date.today()

        start_date = end_date - timedelta(
            days=max(1, lookback_days) - 1
        )

        daily_logs = self.daily_logs_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        activities = self.activities_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        day_type_by_date: dict[str, str] = {}

        for row in daily_logs:
            day_date = row.get("date")
            day_type = _normalize_day_type(
                row.get("day_type")
            )

            if day_date is None or day_type is None:
                continue

            day_type_by_date[str(day_date)] = day_type

        calories_by_date: dict[str, float] = defaultdict(float)

        for activity in activities:
            activity_date = activity.get("date")

            if activity_date is None:
                continue

            date_key = str(activity_date)

            if date_key not in day_type_by_date:
                continue

            calories_by_date[date_key] += max(
                0.0,
                _number(activity.get("burned_calories")),
            )

        result: dict[str, dict[str, Any]] = {}

        for day_type in DAY_TYPES:
            daily_values = [
                round(calories, 2)
                for date_key, calories in calories_by_date.items()
                if day_type_by_date.get(date_key) == day_type
            ]

            result[day_type] = {
                "day_type": day_type,
                "days": len(daily_values),
                "average_burned_calories": (
                    round(
                        sum(daily_values) / len(daily_values),
                        2,
                    )
                    if daily_values
                    else None
                ),
                "median_burned_calories": (
                    round(median(daily_values), 2)
                    if daily_values
                    else None
                ),
                "min_burned_calories": (
                    min(daily_values)
                    if daily_values
                    else None
                ),
                "max_burned_calories": (
                    max(daily_values)
                    if daily_values
                    else None
                ),
            }

        return {
            "lookback_days": lookback_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "profiles": result,
        }
    def activity_profile_by_activity_plan(
        self,
        user_id: str,
        end_date: date | None = None,
        lookback_days: int = 180,
    ) -> dict[str, Any]:
        """
        Historical activity profile grouped by activity_plan.

        Each day with an explicit activity_plan is counted once.
        Multiple activities on the same day are aggregated first.

        Days with an explicit activity_plan but no recorded activities
        are represented as zero activity calories.
        """
        if end_date is None:
            end_date = date.today()

        lookback_days = max(1, lookback_days)

        start_date = end_date - timedelta(
            days=lookback_days - 1
        )

        daily_logs = self.daily_logs_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        activities = self.activities_repo.list_date_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        activity_plan_by_date: dict[str, str] = {}

        for row in daily_logs:
            raw_date = row.get("date")
            raw_plan = row.get("activity_plan")

            if raw_date is None or raw_plan is None:
                continue

            plan = str(raw_plan).strip()

            if not plan:
                continue

            activity_plan_by_date[str(raw_date)] = plan

        calories_by_date: dict[str, float] = defaultdict(float)
        activity_count_by_date: dict[str, int] = defaultdict(int)

        for activity in activities:
            raw_date = activity.get("date")

            if raw_date is None:
                continue

            date_key = str(raw_date)

            if date_key not in activity_plan_by_date:
                continue

            calories_by_date[date_key] += max(
                0.0,
                _number(activity.get("burned_calories")),
            )

            activity_count_by_date[date_key] += 1

        dates_by_plan: dict[str, list[str]] = defaultdict(list)

        for date_key, plan in activity_plan_by_date.items():
            dates_by_plan[plan].append(date_key)

        profiles: dict[str, dict[str, Any]] = {}

        for plan, dates in sorted(dates_by_plan.items()):
            daily_values = [
                round(calories_by_date.get(date_key, 0.0), 2)
                for date_key in dates
            ]

            days_with_activity = sum(
                1
                for date_key in dates
                if activity_count_by_date.get(date_key, 0) > 0
            )

            profiles[plan] = {
                "activity_plan": plan,
                "days": len(daily_values),
                "days_with_activity": days_with_activity,
                "days_without_activity": (
                    len(daily_values) - days_with_activity
                ),
                "average_burned_calories": (
                    round(
                        sum(daily_values) / len(daily_values),
                        2,
                    )
                    if daily_values
                    else None
                ),
                "median_burned_calories": (
                    round(median(daily_values), 2)
                    if daily_values
                    else None
                ),
                "min_burned_calories": (
                    min(daily_values)
                    if daily_values
                    else None
                ),
                "max_burned_calories": (
                    max(daily_values)
                    if daily_values
                    else None
                ),
            }

        return {
            "lookback_days": lookback_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "profiles": profiles,
        }
