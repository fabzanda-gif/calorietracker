from backend.services.order_candidates import (
    OrderCandidateService,
)


service = OrderCandidateService()


def test_builds_takeaway_candidate_from_logged_history():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Pizza Margherita",
                "category": "takeaway",
                "calories": 800,
                "protein": 30,
                "carbs": 100,
                "fat": 25,
            }
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert result[0]["source"] == "takeaway"
    assert result[0]["name"] == "Pizza Margherita"
    assert result[0]["known_order"] is True


def test_known_order_has_no_synthetic_taste_score():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Poke Salmone",
                "category": "delivery",
                "calories": 650,
            }
        ],
        meal_type="Cena",
    )

    assert "taste_score" not in result[0]


def test_delivery_candidate_is_supported():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Poke Salmone",
                "category": "delivery",
                "calories": 650,
            }
        ],
        meal_type="Cena",
    )

    assert result[0]["source"] == "delivery"


def test_repeated_orders_are_aggregated():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Pizza Margherita",
                "category": "takeaway",
                "calories": 800,
                "protein": 30,
            },
            {
                "date": "2026-08-08",
                "meal_type": "Cena",
                "name": "Pizza Margherita",
                "category": "takeaway",
                "calories": 840,
                "protein": 32,
            },
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert result[0]["order_count"] == 2
    assert result[0]["calories"] == 820
    assert result[0]["protein_g"] == 31
    assert result[0]["last_ordered_date"] == "2026-08-08"


def test_non_order_categories_are_ignored():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Pasta",
                "category": "home",
                "calories": 600,
            }
        ],
        meal_type="Cena",
    )

    assert result == []


def test_other_meal_types_are_ignored():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Pranzo",
                "name": "Poke",
                "category": "delivery",
                "calories": 600,
            }
        ],
        meal_type="Cena",
    )

    assert result == []


def test_base_name_is_used_when_available():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Pizza Margherita x1",
                "base_name": "Pizza Margherita",
                "category": "takeaway",
                "calories": 800,
            }
        ],
        meal_type="Cena",
    )

    assert result[0]["name"] == "Pizza Margherita"


def test_same_order_event_components_are_combined():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Burger",
                "category": "delivery",
                "calories": 650,
            },
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Patatine",
                "category": "delivery",
                "calories": 250,
            },
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert (
        result[0]["name"]
        == "Burger + Patatine"
    )
    assert result[0]["calories"] == 900
