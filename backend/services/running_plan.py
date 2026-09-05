from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math


SESSION_KINDS = {
    "easy",
    "recovery",
    "tempo",
    "interval",
    "long",
    "race",
}


@dataclass(frozen=True)
class RunningPlanInput:
    start_date: date
    target_date: date
    current_distance_meters: float
    current_pace_seconds_per_km: int
    target_distance_meters: float
    target_pace_seconds_per_km: int
    sessions_per_week: int
    long_run_weekday: int = 6


def _round_distance(value: float) -> int:
    return max(
        1000,
        int(round(value / 500.0) * 500),
    )


def _pace_label(seconds: int) -> str:
    minutes, remainder = divmod(
        max(1, int(seconds)),
        60,
    )
    return f"{minutes}:{remainder:02d}/km"


def _phase(
    week_index: int,
    total_weeks: int,
) -> str:
    ratio = week_index / max(1, total_weeks)

    if ratio < 0.35:
        return "base"
    if ratio < 0.70:
        return "build"
    if ratio < 0.90:
        return "specific"
    return "taper"


def _quality_kind(
    week_index: int,
    total_weeks: int,
) -> str:
    ratio = week_index / max(1, total_weeks)

    if ratio < 0.25:
        return "easy"

    if ratio < 0.65:
        return (
            "tempo"
            if week_index % 2 == 0
            else "interval"
        )

    return (
        "tempo"
        if week_index % 3 != 0
        else "interval"
    )


def _session_offsets(
    sessions_per_week: int,
) -> list[int]:
    if sessions_per_week == 2:
        return [-3, 0]

    if sessions_per_week == 3:
        return [-5, -3, 0]

    if sessions_per_week == 4:
        return [-6, -4, -2, 0]

    return [-6, -5, -3, -2, 0]


def _long_run_for_week(
    *,
    week_index: int,
    total_weeks: int,
    current_distance: float,
    target_distance: float,
) -> int:
    if week_index == total_weeks:
        return _round_distance(target_distance)

    phase = _phase(
        week_index,
        total_weeks,
    )

    start_long = max(
        current_distance * 1.15,
        current_distance + 1000,
    )

    peak = max(
        start_long,
        target_distance * 0.90,
    )

    if phase == "taper":
        remaining = (
            total_weeks - week_index
        )

        if remaining <= 1:
            return _round_distance(
                max(
                    current_distance,
                    target_distance * 0.55,
                )
            )

        return _round_distance(
            max(
                current_distance,
                target_distance * 0.70,
            )
        )

    build_weeks = max(
        1,
        math.ceil(total_weeks * 0.88),
    )

    progress = min(
        1.0,
        (week_index - 1) /
        max(1, build_weeks - 1),
    )

    value = (
        start_long +
        (peak - start_long) * progress
    )

    # Every fourth week is deliberately lighter.
    if week_index % 4 == 0:
        value *= 0.82

    return _round_distance(value)


def build_running_plan(
    plan: RunningPlanInput,
) -> list[dict]:
    if plan.target_date <= plan.start_date:
        raise ValueError(
            "Target date must be after start date"
        )

    total_days = (
        plan.target_date -
        plan.start_date
    ).days

    total_weeks = max(
        1,
        math.ceil(total_days / 7),
    )

    if total_weeks < 8:
        raise ValueError(
            "Running plan requires at least 8 weeks"
        )

    if not 2 <= plan.sessions_per_week <= 5:
        raise ValueError(
            "sessions_per_week must be between 2 and 5"
        )

    if not 0 <= plan.long_run_weekday <= 6:
        raise ValueError(
            "long_run_weekday must be between 0 and 6"
        )

    first_long = plan.start_date

    days_until_long = (
        plan.long_run_weekday -
        first_long.weekday()
    ) % 7

    first_long = (
        first_long +
        timedelta(days=days_until_long)
    )

    sessions: list[dict] = []

    pace_delta = (
        plan.current_pace_seconds_per_km -
        plan.target_pace_seconds_per_km
    )

    for week_index in range(
        1,
        total_weeks + 1,
    ):
        long_date = (
            first_long +
            timedelta(
                weeks=week_index - 1,
            )
        )

        if long_date > plan.target_date:
            long_date = plan.target_date

        long_distance = _long_run_for_week(
            week_index=week_index,
            total_weeks=total_weeks,
            current_distance=(
                plan.current_distance_meters
            ),
            target_distance=(
                plan.target_distance_meters
            ),
        )

        phase = _phase(
            week_index,
            total_weeks,
        )

        offsets = _session_offsets(
            plan.sessions_per_week
        )

        for position, offset in enumerate(
            offsets
        ):
            session_date = (
                long_date +
                timedelta(days=offset)
            )

            if session_date < plan.start_date:
                continue

            if session_date > plan.target_date:
                continue

            is_final = (
                week_index == total_weeks
                and offset == 0
            )

            if is_final:
                kind = "race"

                # The goal session must preserve the
                # user's exact target distance.
                # Intermediate training sessions remain
                # rounded to practical 500 m increments.
                distance = int(
                    round(
                        plan.target_distance_meters
                    )
                )

                pace = (
                    plan.target_pace_seconds_per_km
                )
                title = (
                    f"Obiettivo "
                    f"{distance / 1000:g} km"
                )
                intensity = "race"

            elif offset == 0:
                kind = "long"
                distance = long_distance
                pace = (
                    plan.current_pace_seconds_per_km
                    + 50
                )
                title = (
                    f"Lungo "
                    f"{distance / 1000:g} km"
                )
                intensity = "low"

            elif (
                position ==
                len(offsets) - 2
            ):
                kind = _quality_kind(
                    week_index,
                    total_weeks,
                )

                if kind == "easy":
                    distance = _round_distance(
                        max(
                            4000,
                            long_distance * 0.55,
                        )
                    )
                    pace = (
                        plan.current_pace_seconds_per_km
                        + 45
                    )
                    title = "Corsa facile"
                    intensity = "low"

                elif kind == "tempo":
                    progress = min(
                        1.0,
                        week_index /
                        max(
                            1,
                            total_weeks * 0.85,
                        ),
                    )

                    pace = round(
                        plan.current_pace_seconds_per_km
                        -
                        pace_delta *
                        progress *
                        0.80
                    )

                    distance = _round_distance(
                        max(
                            5000,
                            long_distance * 0.48,
                        )
                    )
                    title = "Corsa a ritmo"
                    intensity = "moderate"

                else:
                    pace = max(
                        plan.target_pace_seconds_per_km,
                        plan.current_pace_seconds_per_km
                        - 20,
                    )
                    distance = _round_distance(
                        max(
                            4500,
                            long_distance * 0.42,
                        )
                    )
                    title = "Lavoro di qualità"
                    intensity = "hard"

            else:
                kind = (
                    "recovery"
                    if (
                        plan.sessions_per_week >= 4
                        and position == 0
                    )
                    else "easy"
                )

                distance = _round_distance(
                    max(
                        3500,
                        long_distance *
                        (
                            0.38
                            if kind == "recovery"
                            else 0.50
                        ),
                    )
                )

                pace = (
                    plan.current_pace_seconds_per_km
                    + (
                        70
                        if kind == "recovery"
                        else 50
                    )
                )

                title = (
                    "Recupero"
                    if kind == "recovery"
                    else "Corsa facile"
                )
                intensity = "low"

            duration_minutes = max(
                15,
                round(
                    (
                        distance / 1000
                    ) *
                    pace /
                    60
                ),
            )

            sessions.append(
                {
                    "scheduled_date":
                        str(session_date),
                    "scheduled_time": None,
                    "title": title,
                    "activity_type": "Corsa",
                    "duration_minutes":
                        duration_minutes,
                    "distance_meters":
                        distance,
                    "intensity":
                        intensity,
                    "notes": (
                        f"Fase {phase}. "
                        f"Ritmo indicativo "
                        f"{_pace_label(pace)}."
                    ),
                    "status": "planned",
                    "training_week":
                        week_index,
                    "session_kind":
                        kind,
                }
            )

    sessions.sort(
        key=lambda item: (
            item["scheduled_date"],
            item["scheduled_time"] or "",
        )
    )

    return sessions
