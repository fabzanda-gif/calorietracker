from __future__ import annotations

from datetime import date
from typing import Any


SPECIAL_PERIOD_PRESETS: dict[str, dict[str, str]] = {
    "vacation": {
        "training_policy": "keep",
        "activity_bias": "higher",
        "nutrition_mode": "flexible",
        "meal_context": "out_of_routine",
    },
    "illness": {
        "training_policy": "suspend",
        "activity_bias": "lower",
        "nutrition_mode": "recovery",
        "meal_context": "out_of_routine",
    },
}


def special_period_defaults(period_type: str) -> dict[str, str]:
    try:
        return dict(SPECIAL_PERIOD_PRESETS[period_type])
    except KeyError as exc:
        raise ValueError("Unsupported special period type") from exc


def active_special_period(
    client: Any,
    *,
    user_id: str,
    on_date: date,
) -> dict | None:
    result = (
        client.table("special_periods")
        .select(
            "id,user_id,period_type,start_date,end_date,training_policy,"
            "activity_bias,nutrition_mode,meal_context,notes"
        )
        .eq("user_id", user_id)
        .lte("start_date", str(on_date))
        .gte("end_date", str(on_date))
        .order("start_date", desc=True)
        .execute()
    )

    items = result.data or []
    if not items:
        return None

    # Illness has priority over vacation if periods overlap.
    items.sort(
        key=lambda item: 0 if item.get("period_type") == "illness" else 1
    )
    return items[0]


def apply_special_period_to_planned(
    items: list[dict],
    *,
    special_period: dict | None,
    target_date: date,
) -> list[dict]:
    if not special_period:
        return items

    if special_period.get("training_policy") != "suspend":
        return items

    output: list[dict] = []
    for item in items:
        enriched = dict(item)
        if str(item.get("scheduled_date") or "") == str(target_date):
            enriched["effective_status"] = "suspended"
            enriched["suspension_reason"] = special_period.get("period_type")
        output.append(enriched)
    return output
