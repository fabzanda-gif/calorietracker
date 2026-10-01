from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable


def _day_type(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"office", "ufficio"}:
        return "office"
    if normalized in {"home", "casa", "wfh"}:
        return "home"
    if normalized in {"free", "libero", "rest", "riposo"}:
        return "free"
    return None


def _activity_name(value: Any) -> str:
    raw = " ".join(str(value or "").strip().split())
    normalized = raw.casefold()
    if "elettric" in normalized or "e-bike" in normalized or "ebike" in normalized:
        return "Bici elettrica"
    if "bici" in normalized or "biciclett" in normalized or "cycling" in normalized:
        return "Bicicletta"
    if "padel" in normalized:
        return "Padel"
    if "cors" in normalized or "running" in normalized:
        return "Corsa"
    return raw


def learn_activity_suggestion(
    *,
    day_date: date,
    day_context: str | None,
    activities: Iterable[dict[str, Any]],
    daily_logs: Iterable[dict[str, Any]],
    today_activities: Iterable[dict[str, Any]],
    planned_activities: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    """Suggest a recurring activity only after at least three matching days."""
    context = _day_type(day_context)
    context_by_date = {
        str(row.get("date")): _day_type(row.get("day_type"))
        for row in daily_logs
        if row.get("date") is not None
    }
    already_present = {
        _activity_name(item.get("activity_name") or item.get("title"))
        for item in [*today_activities, *planned_activities]
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in activities:
        name = _activity_name(item.get("activity_name"))
        if not name or name.casefold() in {"passi", "steps"}:
            continue
        try:
            item_date = date.fromisoformat(str(item.get("date")))
        except (TypeError, ValueError):
            continue
        same_context = context is not None and context_by_date.get(str(item_date)) == context
        if not same_context and item_date.weekday() != day_date.weekday():
            continue
        grouped[name].append(item)

    candidates = [
        (name, rows)
        for name, rows in grouped.items()
        if len({str(row.get("date")) for row in rows}) >= 3
        and name not in already_present
    ]
    if not candidates:
        return None

    name, rows = max(candidates, key=lambda item: len(item[1]))
    observations = len({str(row.get("date")) for row in rows})
    calories = round(sum(float(row.get("burned_calories") or 0) for row in rows) / len(rows))
    durations = [float(row.get("duration_seconds") or 0) for row in rows if float(row.get("duration_seconds") or 0) > 0]
    duration_minutes = round(sum(durations) / len(durations) / 60) if durations else None

    return {
        "activity_name": name,
        "burned_calories": max(0, calories),
        "duration_minutes": duration_minutes,
        "observations": observations,
        "reason": (
            f"Nei giorni {context or 'simili'} registri spesso questa attività."
        ),
    }
