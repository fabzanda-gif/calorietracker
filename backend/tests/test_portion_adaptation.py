from backend.services.portion_adaptation import (
    PortionAdaptationService,
)


service = PortionAdaptationService()


def candidate(
    name="Lasagna Fit",
    calories=700,
    protein_g=45,
):
    return {
        "id": "recipe:1",
        "source": "recipe",
        "source_id": "1",
        "name": name,
        "meal_type": "Cena",
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": 60,
        "fat_g": 25,
        "taste_score": 8,
    }


def test_keeps_normal_portion_when_it_fits():
    result = service.adapt(
        candidate=candidate(calories=500),
        available_kcal=600,
    )

    assert result is not None
    assert result["portion_multiplier"] == 1.0
    assert result["calories"] == 500


def test_reduces_portion_when_reasonable():
    result = service.adapt(
        candidate=candidate(calories=700),
        available_kcal=520,
    )

    assert result is not None
    assert result["portion_multiplier"] == 0.75
    assert result["calories"] == 525


def test_does_not_create_tiny_portion():
    result = service.adapt(
        candidate=candidate(calories=1000),
        available_kcal=300,
    )

    assert result is None


def test_scales_macros_with_portion():
    result = service.adapt(
        candidate=candidate(
            calories=700,
            protein_g=40,
        ),
        available_kcal=520,
    )

    assert result is not None
    assert result["portion_multiplier"] == 0.75
    assert result["protein_g"] == 30


def test_original_candidate_is_not_mutated():
    original = candidate(calories=700)

    service.adapt(
        candidate=original,
        available_kcal=520,
    )

    assert original["calories"] == 700
    assert "portion_multiplier" not in original


def test_no_budget_keeps_normal_portion():
    result = service.adapt(
        candidate=candidate(calories=700),
        available_kcal=None,
    )

    assert result is not None
    assert result["portion_multiplier"] == 1.0
    assert result["calories"] == 700
