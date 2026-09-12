from __future__ import annotations

from typing import Any, Iterable

from backend.services.activity_movement import estimated_gpx_calories


def estimate_planned_activity_kcal(
    activity: dict[str, Any],
    *,
    weight_kg: float | None,
) -> int:
    """Return a deterministic, conservative estimate for a planned session."""
    return max(
        0,
        estimated_gpx_calories(
            activity_type=activity.get("activity_type"),
            duration_seconds=float(activity.get("duration_minutes") or 0) * 60,
            distance_meters=activity.get("distance_meters"),
            weight_kg=weight_kg,
        ),
    )


def summarize_planned_activity_energy(
    activities: Iterable[dict[str, Any]],
    *,
    weight_kg: float | None,
) -> dict[str, Any]:
    planned = [
        item
        for item in activities
        if str(item.get("status") or "planned").strip().casefold()
        == "planned"
    ]
    estimates = [
        estimate_planned_activity_kcal(item, weight_kg=weight_kg)
        for item in planned
    ]
    total = sum(estimates)

    if total >= 600:
        level = "high"
    elif total > 0:
        level = "moderate"
    else:
        level = None

    return {
        "count": len(planned),
        "estimated_kcal": total,
        "activity_level": level,
        "items": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "activity_type": item.get("activity_type"),
                "duration_minutes": item.get("duration_minutes"),
                "distance_meters": item.get("distance_meters"),
                "estimated_kcal": estimate,
            }
            for item, estimate in zip(planned, estimates)
        ],
    }
