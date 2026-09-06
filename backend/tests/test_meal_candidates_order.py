from datetime import date

from backend.services.meal_candidates import (
    MealCandidateService,
)


def test_order_candidates_are_added_to_candidate_pool():
    result = MealCandidateService().build(
        day_date=date(2026, 9, 1),
        meal_type="Cena",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[],
        order_candidates=[
            {
                "id": "delivery:poke",
                "source": "delivery",
                "source_id": None,
                "name": "Poke",
                "meal_type": "Cena",
                "calories": 650,
                "protein_g": 35,
                "carbs_g": 70,
                "fat_g": 20,
                "taste_score": 5,
                "waste_risk": None,
                "order_count": 3,
                "known_order": True,
            }
        ],
    )

    assert len(result) == 1
    assert result[0]["source"] == "delivery"
    assert result[0]["name"] == "Poke"


def test_lunch_order_candidate_can_be_used_for_dinner():
    result = MealCandidateService().build(
        day_date=date(2026, 9, 1),
        meal_type="Cena",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[],
        order_candidates=[
            {
                "id": "delivery:poke",
                "source": "delivery",
                "name": "Poke",
                "meal_type": "Pranzo",
            }
        ],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Poke"
    assert result[0]["meal_type"] == "Cena"
