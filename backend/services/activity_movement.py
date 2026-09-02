from __future__ import annotations

from typing import Any


STEP_CALORIES = 0.04

ACTIVITY_PROFILES: dict[str, dict[str, Any]] = {
    "Padel": {
        "icon": "🎾",
        "step_cadence": 105,
        "suggested_kcal_per_hour": 500,
    },
    "Corsa": {
        "icon": "🏃",
        "step_cadence": 165,
        "suggested_kcal_per_hour": 650,
    },
    "Tennis": {
        "icon": "🎾",
        "step_cadence": 100,
        "suggested_kcal_per_hour": 480,
    },
    "Palestra": {
        "icon": "🏋️",
        "step_cadence": 0,
        "suggested_kcal_per_hour": 350,
    },
    "Calcio": {
        "icon": "⚽",
        "step_cadence": 120,
        "suggested_kcal_per_hour": 600,
    },
    "Nuoto": {
        "icon": "🏊",
        "step_cadence": 0,
        "suggested_kcal_per_hour": 500,
    },
    "Escursione": {
        "icon": "🥾",
        "step_cadence": 105,
        "suggested_kcal_per_hour": 400,
    },
    "Camminata": {
        "icon": "🚶",
        "step_cadence": 100,
        "suggested_kcal_per_hour": 280,
    },
    "Altro": {
        "icon": "🔥",
        "step_cadence": 0,
        "suggested_kcal_per_hour": 300,
    },
}


def _number(value: Any) -> float:
    if value in (None, ""):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_activity_type(
    value: Any,
) -> str:
    normalized = str(value or "").strip().lower()

    aliases = {
        "padel": "Padel",
        "tennis": "Tennis",
        "corsa": "Corsa",
        "running": "Corsa",
        "jogging": "Corsa",
        "palestra": "Palestra",
        "pesi": "Palestra",
        "calcio": "Calcio",
        "football": "Calcio",
        "nuoto": "Nuoto",
        "swimming": "Nuoto",
        "escursione": "Escursione",
        "trekking": "Escursione",
        "hiking": "Escursione",
        "camminata": "Camminata",
        "walking": "Camminata",
    }

    for fragment, activity_type in aliases.items():
        if fragment in normalized:
            return activity_type

    return "Altro"


def activity_profile(
    activity_type: Any,
) -> dict[str, Any]:
    normalized = normalize_activity_type(
        activity_type
    )

    return {
        "activity_type": normalized,
        **ACTIVITY_PROFILES[normalized],
    }


def suggested_activity_calories(
    *,
    activity_type: Any,
    duration_seconds: Any,
) -> int:
    duration = max(
        0.0,
        _number(duration_seconds),
    )
    profile = activity_profile(activity_type)

    return round(
        duration
        / 3600
        * profile["suggested_kcal_per_hour"]
    )


def estimated_activity_steps(
    *,
    activity_type: Any,
    duration_seconds: Any,
    average_cadence: Any = None,
) -> int:
    duration = max(
        0.0,
        _number(duration_seconds),
    )

    if duration <= 0:
        return 0

    profile = activity_profile(activity_type)
    cadence = _number(average_cadence)

    if cadence <= 0:
        cadence = float(
            profile["step_cadence"]
        )

    # Alcuni dispositivi registrano per la corsa
    # la cadenza di una sola gamba.
    if (
        profile["activity_type"] == "Corsa"
        and 45 <= cadence < 120
    ):
        cadence *= 2

    if cadence <= 0:
        return 0

    return round(
        cadence * duration / 60
    )


def movement_step_summary(
    *,
    total_steps: Any,
    activities: list[dict[str, Any]],
) -> dict[str, int | float]:
    gross_steps = max(
        0,
        round(_number(total_steps)),
    )
    estimated_training_steps = 0

    for activity in activities:
        name = str(
            activity.get("activity_name") or ""
        ).strip().lower()

        if (
            name.startswith("passi")
            or name.startswith("steps")
        ):
            continue

        stored_estimate = _number(
            activity.get("estimated_steps")
        )

        if stored_estimate > 0:
            estimate = round(stored_estimate)
        else:
            estimate = estimated_activity_steps(
                activity_type=(
                    activity.get("activity_type")
                    or activity.get("activity_name")
                ),
                duration_seconds=activity.get(
                    "duration_seconds"
                ),
                average_cadence=activity.get(
                    "average_cadence"
                ),
            )

        estimated_training_steps += max(
            0,
            estimate,
        )

    applied_offset = min(
        gross_steps,
        estimated_training_steps,
    )
    net_steps = max(
        0,
        gross_steps - applied_offset,
    )

    return {
        "total_steps": gross_steps,
        "estimated_training_steps":
            estimated_training_steps,
        "applied_step_offset": applied_offset,
        "net_daily_steps": net_steps,
        "step_calories": round(
            net_steps * STEP_CALORIES
        ),
    }
