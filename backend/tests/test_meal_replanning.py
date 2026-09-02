from backend.services.meal_replanning import (
    MealReplanningService,
)


service = MealReplanningService()


def candidate(
    name,
    calories,
    *,
    source="recipe",
    protein_g=40,
):
    return {
        "id": f"{source}:{name}",
        "source": source,
        "source_id": name,
        "name": name,
        "meal_type": "Cena",
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": 50,
        "fat_g": 20,
        "taste_score": 8,
    }


def option(
    meal,
    *,
    lens="balanced",
    score=0.8,
):
    return {
        "lens": lens,
        "label": "Bilanciato",
        "candidate": meal,
        "score": score,
        "reason": "test",
    }


def test_keeps_routine_when_it_fits():
    routine = candidate(
        "Lasagna Fit",
        500,
        source="routine",
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(candidate("Alternative", 450)),
        ],
        available_kcal=600,
    )

    assert result is not None
    assert result["candidate"]["name"] == "Lasagna Fit"
    assert result["candidate"]["calories"] == 500
    assert result["portion_multiplier"] == 1.0
    assert result["strategy"] == "routine"


def test_does_not_shrink_routine_to_fit():
    routine = candidate(
        "Lasagna Fit",
        700,
        source="routine",
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(candidate("Chicken Bowl", 500)),
        ],
        available_kcal=520,
    )

    assert result is not None
    assert result["candidate"]["name"] == "Chicken Bowl"
    assert result["candidate"]["calories"] == 500
    assert result["portion_multiplier"] == 1.0
    assert result["strategy"] == "alternate_candidate"


def test_uses_ranked_alternative_at_original_portion():
    routine = candidate(
        "Huge Lasagna",
        1200,
        source="routine",
    )

    alternative = candidate(
        "Chicken Bowl",
        480,
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(alternative),
        ],
        available_kcal=500,
    )

    assert result is not None
    assert result["candidate"]["name"] == "Chicken Bowl"
    assert result["candidate"]["calories"] == 480
    assert result["portion_multiplier"] == 1.0
    assert result["strategy"] == "alternate_candidate"


def test_does_not_adapt_alternative_portion():
    routine = candidate(
        "Huge Lasagna",
        1400,
        source="routine",
    )

    alternative = candidate(
        "Salmon Bowl",
        650,
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(alternative),
        ],
        available_kcal=470,
    )

    assert result is None


def test_returns_none_when_nothing_is_compatible():
    routine = candidate(
        "Huge Lasagna",
        1400,
        source="routine",
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(candidate("Huge Bowl", 1200)),
        ],
        available_kcal=300,
    )

    assert result is None


def test_does_not_mutate_routine_or_ranked_candidate():
    routine = candidate(
        "Lasagna Fit",
        700,
        source="routine",
    )
    alternative = candidate(
        "Chicken Bowl",
        500,
    )

    service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(alternative),
        ],
        available_kcal=520,
    )

    assert routine["calories"] == 700
    assert "portion_multiplier" not in routine

    assert alternative["calories"] == 500
    assert "portion_multiplier" not in alternative

def test_removes_optional_apple_before_changing_main_meal():
    routine = candidate(
        "Pollo e riso + Mela",
        600,
        source="routine",
    )
    routine["components"] = [
        {
            "name": "Pollo e riso",
            "calories": 500,
            "protein": 42,
            "carbs": 55,
            "fat": 12,
        },
        {
            "name": "Mela",
            "calories": 100,
            "protein": 0,
            "carbs": 25,
            "fat": 0,
        },
    ]

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[],
        available_kcal=520,
    )

    assert result is not None
    assert result["strategy"] == "component_reduction"
    assert result["candidate"]["name"] == "Pollo e riso"
    assert result["candidate"]["calories"] == 500
    assert (
        result["adaptation"]["removed_components"][0]["name"]
        == "Mela"
    )
    assert result["portion_multiplier"] == 1.0


def test_does_not_remove_oat_latte_from_breakfast():
    routine = candidate(
        "Latte macchiato d'avena + Cheesecake",
        403,
        source="routine",
    )
    routine["meal_type"] = "Colazione"
    routine["components"] = [
        {
            "name": "Latte macchiato d'avena",
            "calories": 120,
            "protein": 2,
        },
        {
            "name": "Cheesecake",
            "calories": 283,
            "protein": 15,
        },
    ]

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[],
        available_kcal=300,
    )

    assert result is None


def test_optional_removal_must_be_enough_to_fit():
    routine = candidate(
        "Pollo e riso + Mela",
        700,
        source="routine",
    )
    routine["components"] = [
        {
            "name": "Pollo e riso",
            "calories": 600,
        },
        {
            "name": "Mela",
            "calories": 100,
        },
    ]

    alternative = candidate(
        "Piatto alternativo",
        450,
    )

    result = service.recommend(
        routine_candidate=routine,
        ranked_options=[
            option(alternative)
        ],
        available_kcal=500,
    )

    assert result is not None
    assert result["strategy"] == "alternate_candidate"
    assert result["candidate"]["name"] == "Piatto alternativo"


def test_component_adaptation_does_not_mutate_routine():
    routine = candidate(
        "Pollo e riso + Dessert",
        620,
        source="routine",
    )
    routine["components"] = [
        {
            "name": "Pollo e riso",
            "calories": 500,
        },
        {
            "name": "Dessert",
            "calories": 120,
        },
    ]

    service.recommend(
        routine_candidate=routine,
        ranked_options=[],
        available_kcal=520,
    )

    assert routine["calories"] == 620
    assert len(routine["components"]) == 2
    assert "removed_components" not in routine
