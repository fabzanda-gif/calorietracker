"""
SanoSync nutrition core.

First extracted domain module from the Streamlit prototype.

Design goals:
- no Streamlit imports
- no Supabase access
- deterministic/pure calculations
- preserve the current SanoSync nutrition behaviour
- make the same code reusable by Streamlit today and FastAPI tomorrow
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping


DEFICIT_PRESETS: dict[str, int] = {
    "maintenance": 0,
    "slow": 250,
    "medium": 500,
    "fast": 750,
    "custom": 0,
}


DEFICIT_PRESET_LABELS: dict[str, dict[str, str]] = {
    "Italiano": {
        "maintenance": "Mantenimento peso · 0 kcal",
        "custom": "Custom",
        "slow": "Lento · 250 kcal",
        "medium": "Medio · 500 kcal",
        "fast": "Veloce · 750 kcal",
    },
    "English": {
        "maintenance": "Weight maintenance · 0 kcal",
        "custom": "Custom",
        "slow": "Slow · 250 kcal",
        "medium": "Medium · 500 kcal",
        "fast": "Fast · 750 kcal",
    },
    "Nederlands": {
        "maintenance": "Gewicht behouden · 0 kcal",
        "custom": "Aangepast",
        "slow": "Langzaam · 250 kcal",
        "medium": "Gemiddeld · 500 kcal",
        "fast": "Snel · 750 kcal",
    },
    "Français": {
        "maintenance": "Maintien du poids · 0 kcal",
        "custom": "Personnalisé",
        "slow": "Lent · 250 kcal",
        "medium": "Moyen · 500 kcal",
        "fast": "Rapide · 750 kcal",
    },
}


def parse_birth_date(value: Any) -> date | None:
    """Convert a Supabase/profile birth-date value to ``datetime.date``."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def calculate_age(
    birth_date_value: Any,
    on_date: date | None = None,
) -> int | None:
    """Completed age on ``on_date``; defaults to today."""
    birth_date = parse_birth_date(birth_date_value)
    if birth_date is None:
        return None

    today = on_date or date.today()
    return (
        today.year
        - birth_date.year
        - (
            (today.month, today.day)
            < (birth_date.month, birth_date.day)
        )
    )


def deficit_preset_label(
    preset_key: str,
    language: str = "Italiano",
) -> str:
    """
    Return the translated label for a deficit preset.

    The Streamlit prototype used session state to obtain the language.
    The extracted core accepts language explicitly, making it framework-free.
    """
    labels = DEFICIT_PRESET_LABELS.get(
        language,
        DEFICIT_PRESET_LABELS["Italiano"],
    )
    return labels.get(preset_key, labels["custom"])


def normalize_deficit_plan(value: Any) -> str:
    """Compatibility with values stored by older SanoSync versions."""
    raw = str(value or "").strip().casefold()

    if raw in {
        "maintenance",
        "mantenimento",
        "mantenimento peso",
        "weight maintenance",
        "gewicht behouden",
        "maintien du poids",
    }:
        return "maintenance"
    if raw in {
        "custom",
        "aangepast",
        "personnalisé",
        "personalizzato",
    }:
        return "custom"
    if raw in {
        "slow",
        "lento",
        "langzaam",
        "lent",
    } or "250" in raw:
        return "slow"
    if raw in {
        "medium",
        "medio",
        "gemiddeld",
        "moyen",
    } or "500" in raw:
        return "medium"
    if raw in {
        "fast",
        "veloce",
        "snel",
        "rapide",
    } or "750" in raw:
        return "fast"
    return "custom"


def deficit_preset_from_value(value: Any) -> str:
    try:
        normalized = int(round(float(value)))
    except (TypeError, ValueError):
        return "custom"

    if normalized == 0:
        return "maintenance"

    for key, kcal in DEFICIT_PRESETS.items():
        if key == "custom":
            continue
        if kcal == normalized:
            return key
    return "custom"


def resolve_deficit_target(
    preset_key: str,
    entered_value: Any = None,
) -> int:
    """
    Resolve the base daily calorie deficit.

    Behaviour intentionally matches the current app:
    the manually entered kcal value is authoritative when valid;
    the preset is only the fallback/default.
    """
    try:
        return max(0, int(round(float(entered_value))))
    except (TypeError, ValueError):
        return int(DEFICIT_PRESETS.get(preset_key, 0))


def calculate_bmr(
    weight: float,
    height: float,
    birth_date_value: Any,
    gender: str,
    *,
    on_date: date | None = None,
) -> int | None:
    """
    Mifflin-St Jeor BMR.

    Male:
        10W + 6.25H - 5A + 5
    Female/default:
        10W + 6.25H - 5A - 161

    ``on_date`` is optional and exists primarily to make regression tests
    deterministic. Omitting it preserves the current app behaviour.
    """
    age = calculate_age(
        birth_date_value,
        on_date=on_date,
    )
    if age is None:
        return None

    weight = float(weight)
    height = float(height)

    if gender in {"Uomo", "Male", "Man"}:
        return int(
            round(
                (10 * weight)
                + (6.25 * height)
                - (5 * age)
                + 5
            )
        )

    return int(
        round(
            (10 * weight)
            + (6.25 * height)
            - (5 * age)
            - 161
        )
    )


def calculate_recipe_totals(
    ingredients: Iterable[Mapping[str, Any]],
) -> tuple[
    float,
    dict[str, float],
    dict[str, float],
]:
    """
    Calculate recipe weight, total nutrients and nutrient values per 100 g.

    Expected ingredient fields:
    - quantity_g
    - calories_per_100g
    - protein_per_100g
    - carbs_per_100g
    - fat_per_100g

    Behaviour matches the Streamlit implementation.
    """
    items = list(ingredients)

    total_weight = sum(
        float(item.get("quantity_g", 0))
        for item in items
    )

    totals = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }

    for item in items:
        factor = float(
            item.get("quantity_g", 0)
        ) / 100.0

        for key in totals:
            totals[key] += (
                float(
                    item.get(
                        f"{key}_per_100g",
                        0,
                    )
                    or 0
                )
                * factor
            )

    per100 = {
        key: (
            value / total_weight * 100
            if total_weight > 0
            else 0
        )
        for key, value in totals.items()
    }

    return total_weight, totals, per100
