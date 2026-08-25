from backend.services.budget import (
    BudgetInput,
    BudgetService,
)
from backend.services.decision_ranking import (
    DecisionRankingService,
)


def candidate(
    name: str,
    calories: float,
    protein: float,
    taste: float = 7.0,
) -> dict:
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "meal_type": "Cena",
        "source": "recipe",
        "calories": calories,
        "protein_g": protein,
        "taste_score": taste,
        "waste_risk": "low",
    }


DINNERS = [
    candidate(
        "Cena leggera",
        calories=350,
        protein=30,
        taste=6,
    ),
    candidate(
        "Cena bilanciata",
        calories=550,
        protein=45,
        taste=8,
    ),
    candidate(
        "Cena abbondante",
        calories=750,
        protein=55,
        taste=9,
    ),
]


def make_budget(
    *,
    consumed: float,
    activity: float = 0,
    protein_consumed: float = 60,
) -> dict:
    return BudgetService().calculate(
        BudgetInput(
            bmr=1800,
            activity_kcal=activity,
            consumed_kcal=consumed,
            planned_kcal=0,
            protein_consumed_g=protein_consumed,
            protein_target_g=140,
            goal_mode="maintenance",
            goal_adjustment_kcal=0,
        )
    )


def option_for_lens(
    result: dict,
    lens: str,
) -> dict:
    return next(
        item
        for item in result["options"]
        if item["lens"] == lens
    )


def test_more_food_reduces_available_budget():
    light_day = make_budget(
        consumed=600,
    )
    heavy_day = make_budget(
        consumed=1200,
    )

    assert (
        heavy_day["available_kcal"]
        <
        light_day["available_kcal"]
    )


def test_activity_increases_available_budget():
    without_activity = make_budget(
        consumed=1000,
        activity=0,
    )
    with_activity = make_budget(
        consumed=1000,
        activity=500,
    )

    assert (
        with_activity["available_kcal"]
        >
        without_activity["available_kcal"]
    )

    assert (
        with_activity["available_kcal"]
        -
        without_activity["available_kcal"]
        == 500
    )


def test_more_food_pushes_calorie_lens_lighter():
    ranking = DecisionRankingService()

    light_day = make_budget(
        consumed=600,
    )
    heavy_day = make_budget(
        consumed=1500,
    )

    light_result = ranking.rank(
        candidates=DINNERS,
        available_kcal=light_day[
            "available_kcal"
        ],
        protein_remaining_g=light_day[
            "protein_remaining_g"
        ],
    )

    heavy_result = ranking.rank(
        candidates=DINNERS,
        available_kcal=heavy_day[
            "available_kcal"
        ],
        protein_remaining_g=heavy_day[
            "protein_remaining_g"
        ],
    )

    light_pick = option_for_lens(
        light_result,
        "calorie",
    )["candidate"]

    heavy_pick = option_for_lens(
        heavy_result,
        "calorie",
    )["candidate"]

    assert (
        heavy_pick["calories"]
        <=
        light_pick["calories"]
    )


def test_low_protein_changes_balanced_preference():
    ranking = DecisionRankingService()

    low_need = ranking.rank(
        candidates=DINNERS,
        available_kcal=1000,
        protein_remaining_g=20,
    )

    high_need = ranking.rank(
        candidates=DINNERS,
        available_kcal=1000,
        protein_remaining_g=100,
    )

    low_need_pick = option_for_lens(
        low_need,
        "balanced",
    )["candidate"]

    high_need_pick = option_for_lens(
        high_need,
        "balanced",
    )["candidate"]

    assert (
        high_need_pick["protein_g"]
        >=
        low_need_pick["protein_g"]
    )


def test_ranking_reports_current_constraints():
    ranking = DecisionRankingService()

    result = ranking.rank(
        candidates=DINNERS,
        available_kcal=640,
        protein_remaining_g=72,
    )

    assert result["available_kcal"] == 640
    assert result["protein_remaining_g"] == 72
