from backend.services.eating_out_candidates import (
    EatingOutCandidateService,
)


service = EatingOutCandidateService()


def test_builds_restaurant_candidate_from_history():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Ramen",
                "category": "restaurant",
                "calories": 750,
                "protein": 35,
                "carbs": 90,
                "fat": 25,
            }
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert result[0]["source"] == "restaurant"
    assert result[0]["name"] == "Ramen"
    assert result[0]["known_eating_out"] is True


def test_italian_restaurant_category_is_supported():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Pasta",
                "category": "ristorante",
                "calories": 800,
            }
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert result[0]["source"] == "restaurant"


def test_fuori_category_is_supported():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Pranzo",
                "name": "Panino",
                "category": "fuori",
                "calories": 600,
            }
        ],
        meal_type="Pranzo",
    )

    assert len(result) == 1


def test_repeated_restaurant_meals_are_aggregated():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Ramen",
                "category": "restaurant",
                "calories": 700,
                "protein": 30,
            },
            {
                "date": "2026-08-10",
                "meal_type": "Cena",
                "name": "Ramen",
                "category": "restaurant",
                "calories": 800,
                "protein": 40,
            },
        ],
        meal_type="Cena",
    )

    assert len(result) == 1
    assert result[0]["visit_count"] == 2
    assert result[0]["calories"] == 750
    assert result[0]["protein_g"] == 35
    assert result[0]["last_visited_date"] == "2026-08-10"


def test_base_name_is_used_when_available():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Ramen grande",
                "base_name": "Ramen",
                "category": "restaurant",
                "calories": 800,
            }
        ],
        meal_type="Cena",
    )

    assert result[0]["name"] == "Ramen"


def test_non_eating_out_categories_are_ignored():
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
                "name": "Ramen",
                "category": "restaurant",
                "calories": 700,
            }
        ],
        meal_type="Cena",
    )

    assert result == []


def test_known_eating_out_has_no_synthetic_taste_score():
    result = service.build(
        meals=[
            {
                "date": "2026-08-01",
                "meal_type": "Cena",
                "name": "Sushi",
                "category": "restaurant",
                "calories": 700,
            }
        ],
        meal_type="Cena",
    )

    assert "taste_score" not in result[0]
