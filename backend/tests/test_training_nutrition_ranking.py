from backend.services.decision_ranking import (
    DecisionRankingService,
)


def candidate(
    name: str,
    *,
    carbs: float,
    protein: float,
    fat: float,
) -> dict:
    return {
        "id": name,
        "source": "recipe",
        "name": name,
        "meal_type": "Colazione",
        "calories": 500,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "taste_score": 5,
    }


def test_pre_race_favours_high_carb_meal():
    result = DecisionRankingService().rank(
        candidates=[
            {
                **candidate(
                    "Light meal",
                    carbs=5,
                    protein=2,
                    fat=2,
                ),
                "calories": 100,
            },
            candidate(
                "Carb meal",
                carbs=90,
                protein=15,
                fat=10,
            ),
            candidate(
                "Fat meal",
                carbs=20,
                protein=15,
                fat=40,
            ),
        ],
        available_kcal=1000,
        protein_remaining_g=80,
        future_training_context={
            "phase": "pre_race",
            "priority": "race",
            "hours_to_start": 2.5,
            "carbs_target_g": {
                "min": 140,
                "max": 210,
            },
            "protein_target_g": None,
            "carb_focus": True,
            "protein_focus": False,
        },
    )

    balanced = next(
        item
        for item in result["options"]
        if item["lens"] == "balanced"
    )

    assert (
        balanced["candidate"]["name"]
        == "Carb meal"
    )


def test_recovery_favours_carbs_and_protein():
    result = DecisionRankingService().rank(
        candidates=[
            {
                **candidate(
                    "Light meal",
                    carbs=5,
                    protein=2,
                    fat=2,
                ),
                "calories": 100,
            },
            candidate(
                "Recovery meal",
                carbs=75,
                protein=30,
                fat=12,
            ),
            candidate(
                "Low protein meal",
                carbs=75,
                protein=5,
                fat=12,
            ),
        ],
        available_kcal=1000,
        protein_remaining_g=80,
        future_training_context={
            "phase": "recovery",
            "priority": "high",
            "hours_to_start": None,
            "carbs_target_g": {
                "min": 70,
                "max": 84,
            },
            "protein_target_g": {
                "min": 18,
                "max": 21,
            },
            "carb_focus": True,
            "protein_focus": True,
        },
    )

    balanced = next(
        item
        for item in result["options"]
        if item["lens"] == "balanced"
    )

    assert (
        balanced["candidate"]["name"]
        == "Recovery meal"
    )


def test_pre_race_day_context_is_specific():
    result = DecisionRankingService().rank(
        candidates=[
            candidate(
                "Carb meal",
                carbs=90,
                protein=15,
                fat=10,
            )
        ],
        available_kcal=1000,
        protein_remaining_g=80,
        future_training_context={
            "phase": "pre_race",
            "priority": "race",
            "hours_to_start": 2.5,
            "session": {
                "title": "Mezza maratona",
            },
            "carbs_target_g": {
                "min": 140,
                "max": 210,
            },
            "protein_target_g": None,
            "carb_focus": True,
            "protein_focus": False,
        },
    )

    assert (
        result["day_context"]["title"]
        == "Fuel per la gara di oggi"
    )
