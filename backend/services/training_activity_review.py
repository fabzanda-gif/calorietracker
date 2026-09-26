from __future__ import annotations

from datetime import date, datetime
import json
from math import asin, cos, radians, sin, sqrt
from statistics import mean, pstdev
from typing import Any


class TrainingActivityReviewService:
    RUNNING_TYPES = {
        "corsa",
        "running",
        "run",
        "jogging",
    }

    EASY_SESSION_KINDS = {
        "easy",
        "recovery",
        "long",
    }

    def build(
        self,
        *,
        activity: dict[str, Any],
        planned: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        plan_sessions: list[dict[str, Any]] | None = None,
        recent_activities: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        activity_type = self._normalized(
            activity.get("activity_type")
            or activity.get("activity_name")
        )

        if activity_type not in self.RUNNING_TYPES:
            return {
                "available": False,
                "reason": "not_running",
            }

        activity_date = self._date(
            activity.get("date")
        )

        distance_m = self._number(
            activity.get("distance_meters")
        )
        duration_s = self._number(
            activity.get("duration_seconds")
        )

        actual_pace = self._pace_seconds_per_km(
            distance_m,
            duration_s,
        )

        planned_distance = self._number(
            (planned or {}).get("distance_meters")
        )
        planned_duration_s = (
            self._number(
                (planned or {}).get(
                    "duration_minutes"
                )
            )
            * 60
        )

        load_ratio = None

        if (
            planned_distance > 0
            and distance_m > 0
        ):
            load_ratio = (
                distance_m / planned_distance
            )
        elif (
            planned_duration_s > 0
            and duration_s > 0
        ):
            load_ratio = (
                duration_s / planned_duration_s
            )

        session_kind = str(
            (planned or {}).get(
                "session_kind"
            )
            or ""
        ).strip().lower()

        target_date = self._date(
            (plan or {}).get("target_date")
        )

        days_to_race = None

        if (
            activity_date is not None
            and target_date is not None
        ):
            days_to_race = (
                target_date - activity_date
            ).days

        target_pace = self._number(
            (plan or {}).get(
                "target_pace_seconds_per_km"
            )
        )

        pace_variability = (
            self._pace_variability_pct(
                activity.get("route_points")
            )
        )

        recent_distance = sum(
            self._number(
                item.get("distance_meters")
            )
            for item in (
                recent_activities or []
            )
            if self._normalized(
                item.get("activity_type")
                or item.get("activity_name")
            )
            in self.RUNNING_TYPES
        )

        signals: list[str] = []
        recommendations: list[str] = []

        if (
            load_ratio is not None
            and load_ratio > 1.20
        ):
            signals.append(
                "over_planned_load"
            )
            recommendations.append(
                "Hai fatto più volume del previsto: "
                "proteggi il recupero prima del prossimo "
                "lavoro intenso."
            )

        if (
            load_ratio is not None
            and load_ratio < 0.80
        ):
            signals.append(
                "under_planned_load"
            )
            recommendations.append(
                "Il volume è rimasto sotto il previsto: "
                "non serve recuperarlo tutto insieme."
            )

        if (
            days_to_race is not None
            and 0 <= days_to_race <= 3
            and session_kind != "race"
            and (
                distance_m >= 5000
                or duration_s >= 1800
            )
        ):
            signals.append(
                "substantial_run_close_to_race"
            )
            recommendations.append(
                f"La gara è tra {days_to_race} giorni: "
                "evita altro carico importante e privilegia "
                "recupero e freschezza."
            )

        if (
            target_pace > 0
            and actual_pace is not None
            and session_kind
            in self.EASY_SESSION_KINDS
            and actual_pace
            <= target_pace * 1.02
        ):
            signals.append(
                "too_fast_for_easy_session"
            )
            recommendations.append(
                "Per una seduta facile o lunga sei andato "
                "molto vicino al ritmo gara: prova a partire "
                "più controllato."
            )

        if (
            pace_variability is not None
            and pace_variability >= 12
        ):
            signals.append(
                "pace_variability_high"
            )
            recommendations.append(
                "Il passo è stato piuttosto irregolare: "
                "prova a distribuire meglio lo sforzo e a "
                "ridurre le accelerazioni non previste."
            )

        if not signals:
            recommendations.append(
                "La seduta non mostra segnali evidenti di "
                "scostamento dal programma."
            )

        return {
            "available": True,
            "activity_date": (
                str(activity_date)
                if activity_date
                else None
            ),
            "planned_session": (
                {
                    "title": planned.get("title"),
                    "session_kind": session_kind,
                    "distance_meters": (
                        planned_distance
                    ),
                    "duration_minutes": (
                        planned_duration_s / 60
                        if planned_duration_s
                        else None
                    ),
                }
                if planned
                else None
            ),
            "race": (
                {
                    "target_date": str(
                        target_date
                    ),
                    "days_to_race": (
                        days_to_race
                    ),
                    "target_distance_meters":
                        self._number(
                            plan.get(
                                "target_distance_meters"
                            )
                        ),
                    "target_pace_seconds_per_km":
                        target_pace or None,
                }
                if plan and target_date
                else None
            ),
            "actual": {
                "distance_meters": distance_m,
                "duration_seconds": duration_s,
                "pace_seconds_per_km":
                    actual_pace,
                "pace_variability_pct":
                    pace_variability,
            },
            "load_ratio": (
                round(load_ratio, 3)
                if load_ratio is not None
                else None
            ),
            "recent_7d_distance_meters": (
                round(recent_distance, 1)
            ),
            "signals": signals,
            "recommendations":
                recommendations[:3],
        }

    def _pace_variability_pct(
        self,
        raw_points: Any,
    ) -> float | None:
        points = self._points(raw_points)

        if len(points) < 4:
            return None

        chunk_paces: list[float] = []
        chunk_distance = 0.0
        chunk_time = 0.0

        for first, second in zip(
            points,
            points[1:],
        ):
            distance = self._distance(
                first,
                second,
            )

            first_time = self._datetime(
                first.get("time")
            )
            second_time = self._datetime(
                second.get("time")
            )

            if (
                first_time is None
                or second_time is None
            ):
                continue

            seconds = (
                second_time - first_time
            ).total_seconds()

            if (
                distance <= 0
                or seconds <= 0
                or seconds > 180
            ):
                continue

            chunk_distance += distance
            chunk_time += seconds

            if chunk_distance >= 500:
                pace = (
                    chunk_time
                    / (chunk_distance / 1000)
                )

                if 120 <= pace <= 900:
                    chunk_paces.append(pace)

                chunk_distance = 0
                chunk_time = 0

        if len(chunk_paces) < 3:
            return None

        average = mean(chunk_paces)

        if average <= 0:
            return None

        return round(
            pstdev(chunk_paces)
            / average
            * 100,
            1,
        )

    @staticmethod
    def _points(value: Any) -> list[dict]:
        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                return []

            if isinstance(parsed, list):
                return [
                    item
                    for item in parsed
                    if isinstance(item, dict)
                ]

        return []

    @staticmethod
    def _distance(
        first: dict,
        second: dict,
    ) -> float:
        try:
            lat1 = radians(
                float(first["latitude"])
            )
            lat2 = radians(
                float(second["latitude"])
            )
            delta_lat = lat2 - lat1
            delta_lon = radians(
                float(second["longitude"])
                - float(first["longitude"])
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return 0.0

        value = (
            sin(delta_lat / 2) ** 2
            + cos(lat1)
            * cos(lat2)
            * sin(delta_lon / 2) ** 2
        )

        return (
            2
            * 6_371_000
            * asin(min(1.0, sqrt(value)))
        )

    @staticmethod
    def _pace_seconds_per_km(
        distance_m: float,
        duration_s: float,
    ) -> float | None:
        if (
            distance_m <= 0
            or duration_s <= 0
        ):
            return None

        return round(
            duration_s
            / (distance_m / 1000),
            1,
        )

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

    @staticmethod
    def _datetime(
        value: Any,
    ) -> datetime | None:
        if not value:
            return None

        normalized = str(value)

        if normalized.endswith("Z"):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        try:
            return datetime.fromisoformat(
                normalized
            )
        except ValueError:
            return None
