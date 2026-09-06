from backend.api.routers.days import (
    _deterministic_primary_recommendation,
)


def candidate(source, name, expires_at=None):
    return {
        "id": f"{source}:{name}",
        "source": source,
        "name": name,
        "meal_type": "Pranzo",
        "calories": 600,
        "protein_g": 30,
        "taste_score": 5,
        "expires_at": expires_at,
    }


def test_home_breakfast_prefers_recurring_routine():
    fallback = candidate("recipe", "Fallback")
    routine = candidate("routine", "Yogurt e avena")
    inventory = candidate(
        "meal_prep",
        "Porridge pronto",
        "2026-09-05",
    )

    result = _deterministic_primary_recommendation(
        meal_slot="breakfast",
        day_context="Casa",
        mode="auto",
        candidates=[inventory, routine],
        fallback=fallback,
    )

    assert result is routine


def test_free_day_is_not_treated_as_home_priority():
    fallback = candidate("recipe", "Fallback")
    routine = candidate("routine", "Yogurt e avena")

    result = _deterministic_primary_recommendation(
        meal_slot="breakfast",
        day_context="Libero",
        mode="auto",
        candidates=[routine],
        fallback=fallback,
    )

    assert result is fallback


def test_lunch_prefers_available_meal_prep():
    fallback = candidate("recipe", "Chicken rice")
    routine = candidate("routine", "Pasta abituale")
    inventory = candidate(
        "meal_prep",
        "Chili",
        "2026-09-06",
    )

    result = _deterministic_primary_recommendation(
        meal_slot="lunch",
        day_context="Ufficio",
        mode="auto",
        candidates=[routine, inventory],
        fallback=fallback,
    )

    assert result is inventory


def test_lunch_uses_nearest_inventory_expiry():
    later = candidate(
        "meal_prep",
        "Riso e pollo",
        "2026-09-08",
    )
    sooner = candidate(
        "meal_prep",
        "Chili",
        "2026-09-05",
    )
    fallback = candidate("routine", "Pasta abituale")

    result = _deterministic_primary_recommendation(
        meal_slot="lunch",
        day_context="Casa",
        mode="auto",
        candidates=[later, sooner],
        fallback=fallback,
    )

    assert result is sooner


def test_non_auto_mode_keeps_existing_replanner_result():
    fallback = candidate("recipe", "Ordine scelto")
    inventory = candidate(
        "meal_prep",
        "Chili",
        "2026-09-05",
    )

    result = _deterministic_primary_recommendation(
        meal_slot="lunch",
        day_context="Casa",
        mode="order",
        candidates=[inventory],
        fallback=fallback,
    )

    assert result is fallback


def test_dinner_keeps_existing_replanner_result():
    fallback = candidate("routine", "Cena abituale")
    inventory = candidate(
        "meal_prep",
        "Chili",
        "2026-09-05",
    )

    result = _deterministic_primary_recommendation(
        meal_slot="dinner",
        day_context="Casa",
        mode="auto",
        candidates=[inventory],
        fallback=fallback,
    )

    assert result is fallback
