from backend.services.meal_suggestion_policy import (
    MealSuggestionPolicy,
)


def test_lunch_and_dinner_are_compatible():
    assert MealSuggestionPolicy.compatible_meal_types(
        "Pranzo"
    ) == {"Pranzo", "Cena"}
    assert MealSuggestionPolicy.compatible_meal_types(
        "Cena"
    ) == {"Pranzo", "Cena"}


def test_snacks_and_breakfast_are_compatible():
    assert MealSuggestionPolicy.compatible_meal_types(
        "Snack"
    ) == {"Colazione", "Snack"}
    assert MealSuggestionPolicy.compatible_meal_types(
        "Colazione"
    ) == {"Colazione", "Snack"}


def test_main_meal_calorie_boundaries_are_inclusive():
    assert MealSuggestionPolicy.main_meal_calories_are_valid(
        500
    )
    assert MealSuggestionPolicy.main_meal_calories_are_valid(
        1000
    )
    assert not MealSuggestionPolicy.main_meal_calories_are_valid(
        499.99
    )
    assert not MealSuggestionPolicy.main_meal_calories_are_valid(
        1000.01
    )


def test_dynamic_high_activity_limit_is_respected():
    assert MealSuggestionPolicy.main_meal_calories_are_valid(
        1200,
        max_kcal=1200,
    )
    assert not MealSuggestionPolicy.main_meal_calories_are_valid(
        1201,
        max_kcal=1200,
    )
