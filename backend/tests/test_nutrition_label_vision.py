from backend.services.nutrition_label_vision import (
    NutritionLabelResult,
    normalize_to_100g,
)


def test_per_100g_is_kept():
    result = NutritionLabelResult(
        name="Protein Pancakes",
        basis="per_100g",
        calories=250,
        protein=20,
        carbs=30,
        fat=6,
        confidence="high",
    )

    normalized = normalize_to_100g(
        result
    )

    assert normalized["calories"] == 250
    assert normalized["protein"] == 20
    assert normalized["ready_for_form"] is True


def test_per_serving_is_converted_when_weight_known():
    result = NutritionLabelResult(
        basis="per_serving",
        serving_size_g=50,
        calories=125,
        protein=10,
        carbs=15,
        fat=3,
    )

    normalized = normalize_to_100g(
        result
    )

    assert normalized["basis"] == "per_100g"
    assert normalized["calories"] == 250
    assert normalized["protein"] == 20
    assert normalized["carbs"] == 30
    assert normalized["fat"] == 6
    assert normalized["ready_for_form"] is True


def test_per_serving_without_weight_is_not_converted():
    result = NutritionLabelResult(
        basis="per_serving",
        calories=125,
        protein=10,
        carbs=15,
        fat=3,
    )

    normalized = normalize_to_100g(
        result
    )

    assert normalized["basis"] == "per_serving"
    assert normalized["ready_for_form"] is False
