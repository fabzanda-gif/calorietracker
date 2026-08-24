from backend.services.decision_ranking import (
    DecisionRankingService,
)


service = DecisionRankingService()


def candidate(
    name,
    source,
    kcal,
    protein,
    taste,
    waste_risk=None,
):
    return {
        "id": name,
        "name": name,
        "source": source,
        "calories": kcal,
        "protein_g": protein,
        "taste_score": taste,
        "waste_risk": waste_risk,
    }


def test_auto_mode_boosts_ready_food():
    result = service.rank(
        candidates=[
            candidate(
                "Meal prep",
                "meal_prep",
                550,
                35,
                7,
            ),
            candidate(
                "Recipe",
                "recipe",
                500,
                35,
                7,
            ),
            candidate(
                "Taste",
                "recipe",
                650,
                25,
                10,
            ),
        ],
        available_kcal=900,
        protein_remaining_g=60,
        mode="auto",
    )

    assert any(
        x["candidate"]["source"] == "meal_prep"
        for x in result["options"]
    )


def test_non_auto_mode_does_not_apply_ready_bonus():
    auto = service.rank(
        candidates=[
            candidate(
                "Meal prep",
                "meal_prep",
                550,
                35,
                7,
            ),
            candidate(
                "Recipe",
                "recipe",
                500,
                35,
                7,
            ),
        ],
        available_kcal=900,
        protein_remaining_g=60,
        mode="auto",
    )

    cook = service.rank(
        candidates=[
            candidate(
                "Meal prep",
                "meal_prep",
                550,
                35,
                7,
            ),
            candidate(
                "Recipe",
                "recipe",
                500,
                35,
                7,
            ),
        ],
        available_kcal=900,
        protein_remaining_g=60,
        mode="cook",
    )

    auto_scores = {
        x["candidate"]["name"]: x["score"]
        for x in auto["options"]
    }
    cook_scores = {
        x["candidate"]["name"]: x["score"]
        for x in cook["options"]
    }

    assert auto_scores["Meal prep"] > cook_scores["Meal prep"]
