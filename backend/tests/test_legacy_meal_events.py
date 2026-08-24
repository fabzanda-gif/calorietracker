from backend.services.legacy_meal_events import (
    LegacyMealEventService,
)


def test_components_same_date_become_one_meal_event():
    events = LegacyMealEventService().build(
        meal_type="Cena",
        meals=[
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Riso",
                "calories": 280,
                "protein": 6,
            },
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Pollo",
                "calories": 220,
                "protein": 40,
            },
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Verdure",
                "calories": 70,
                "protein": 3,
            },
        ],
    )

    assert len(events) == 1

    event = events[0]

    assert event["name"] == "Riso + Pollo + Verdure"
    assert event["calories"] == 570
    assert event["protein"] == 49
    assert event["component_count"] == 3


def test_single_beer_is_not_a_structured_meal():
    events = LegacyMealEventService().build(
        meal_type="Cena",
        meals=[
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Birra Hertog Jan 33cl",
                "calories": 284,
                "protein": 2,
            },
        ],
    )

    assert events == []


def test_single_chicken_component_is_not_a_structured_meal():
    events = LegacyMealEventService().build(
        meal_type="Cena",
        meals=[
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Chicken breast",
                "calories": 214,
                "protein": 40,
            },
        ],
    )

    assert events == []


def test_single_complete_legacy_meal_is_preserved():
    events = LegacyMealEventService().build(
        meal_type="Pranzo",
        meals=[
            {
                "date": "2026-08-20",
                "meal_type": "Pranzo",
                "name": "Basmati - Mango Curry Chicken - Spinach",
                "calories": 614,
                "protein": 40,
            },
        ],
    )

    assert len(events) == 1
    assert (
        events[0]["name"]
        == "Basmati - Mango Curry Chicken - Spinach"
    )


def test_other_meal_types_are_not_mixed():
    events = LegacyMealEventService().build(
        meal_type="Cena",
        meals=[
            {
                "date": "2026-08-20",
                "meal_type": "Pranzo",
                "name": "Pranzo",
                "calories": 600,
            },
            {
                "date": "2026-08-20",
                "meal_type": "Cena",
                "name": "Cena completa",
                "calories": 500,
            },
        ],
    )

    assert len(events) == 1
    assert events[0]["name"] == "Cena completa"
