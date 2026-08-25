from backend.services.decision_ranking import (
    DecisionRankingService,
)


service = DecisionRankingService()


def candidate(
    name,
    kcal,
    protein,
    taste,
    *,
    source="recipe",
    waste_risk=None,
):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "source": source,
        "calories": kcal,
        "protein_g": protein,
        "taste_score": taste,
        "waste_risk": waste_risk,
    }


def test_returns_three_distinct_lenses():
    result = service.rank(
        candidates=[
            candidate("Light bowl", 400, 30, 6),
            candidate("Chicken rice", 600, 45, 8),
            candidate("Pizza", 750, 25, 10),
        ],
        available_kcal=900,
        protein_remaining_g=60,
    )

    assert [x["lens"] for x in result["options"]] == [
        "calorie",
        "balanced",
        "taste",
    ]

    names = [
        x["candidate"]["name"]
        for x in result["options"]
    ]
    assert len(names) == len(set(names))


def test_calorie_lens_prefers_lower_calorie_option():
    result = service.rank(
        candidates=[
            candidate("Light bowl", 350, 25, 5),
            candidate("Big bowl", 700, 40, 8),
        ],
        available_kcal=900,
        protein_remaining_g=50,
    )

    calorie = next(
        item
        for item in result["options"]
        if item["lens"] == "calorie"
    )

    assert calorie["candidate"]["name"] == "Light bowl"


def test_taste_lens_can_prefer_higher_calorie_option():
    result = service.rank(
        candidates=[
            candidate("Lean meal", 400, 35, 5),
            candidate("Favourite pasta", 650, 30, 10),
            candidate("Middle", 500, 35, 7),
        ],
        available_kcal=800,
        protein_remaining_g=60,
    )

    taste = next(
        item
        for item in result["options"]
        if item["lens"] == "taste"
    )

    assert taste["candidate"]["name"] == "Favourite pasta"


def test_excessively_over_budget_candidates_are_excluded():
    result = service.rank(
        candidates=[
            candidate("Too large", 1200, 40, 10),
            candidate("Compatible", 500, 30, 7),
        ],
        available_kcal=700,
        protein_remaining_g=50,
    )

    assert all(
        option["candidate"]["name"] != "Too large"
        for option in result["options"]
    )


def test_high_waste_risk_can_help_meal_prep_rank():
    result = service.rank(
        candidates=[
            candidate(
                "Meal prep chili",
                520,
                35,
                7,
                source="meal_prep",
                waste_risk="high",
            ),
            candidate(
                "Fresh recipe",
                500,
                35,
                7,
            ),
            candidate(
                "Tasty",
                600,
                25,
                9,
            ),
        ],
        available_kcal=800,
        protein_remaining_g=60,
    )

    assert any(
        option["candidate"]["name"] == "Meal prep chili"
        for option in result["options"]
    )


def test_high_risk_meal_prep_gets_food_waste_reason_when_selected():
    result = service.rank(
        candidates=[
            candidate(
                "Meal prep chili",
                450,
                40,
                8,
                source="meal_prep",
                waste_risk="high",
            ),
            candidate("Other", 700, 20, 6),
        ],
        available_kcal=900,
        protein_remaining_g=50,
    )

    meal_prep_option = next(
        option
        for option in result["options"]
        if option["candidate"]["name"] == "Meal prep chili"
    )

    assert "sprecato" in meal_prep_option["reason"]


def test_single_candidate_is_not_duplicated_three_times():
    result = service.rank(
        candidates=[
            candidate("Only choice", 500, 30, 8),
        ],
        available_kcal=700,
        protein_remaining_g=50,
    )

    assert len(result["options"]) == 1
    assert result["options"][0]["candidate"]["name"] == "Only choice"


def test_missing_taste_score_defaults_to_neutral():
    result = service.rank(
        candidates=[
            {
                "id": "a",
                "name": "Known nutrition",
                "source": "recipe",
                "calories": 500,
                "protein_g": 30,
            }
        ],
        available_kcal=700,
        protein_remaining_g=50,
    )

    assert result["options"][0]["candidate"]["taste_score"] == 5.0


def test_empty_or_incompatible_candidates_returns_empty_options():
    result = service.rank(
        candidates=[
            candidate("Too large", 1000, 40, 10),
        ],
        available_kcal=500,
        protein_remaining_g=50,
    )

    assert result["options"] == []
