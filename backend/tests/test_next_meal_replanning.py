from backend.services.next_meal_replanning import (
    NextMealReplanningService,
)


def next_slot(logged):
    return NextMealReplanningService().next_slot(
        logged_meal_types=logged,
    )


def test_breakfast_is_next_when_nothing_logged():
    assert next_slot([]) == "breakfast"


def test_lunch_is_next_after_breakfast():
    assert next_slot(["Colazione"]) == "lunch"


def test_snack_is_next_after_breakfast_and_lunch():
    assert next_slot(
        ["Colazione", "Pranzo"]
    ) == "snack"


def test_dinner_is_next_after_snack():
    assert next_slot(
        ["Colazione", "Pranzo", "Snack"]
    ) == "dinner"


def test_historical_spuntino_advances_to_dinner():
    assert next_slot(
        ["Colazione", "Pranzo", "Spuntino"]
    ) == "dinner"


def test_no_next_meal_after_full_day():
    assert next_slot(
        [
            "Colazione",
            "Pranzo",
            "Snack",
            "Cena",
        ]
    ) is None


def test_order_of_logged_rows_does_not_matter():
    assert next_slot(
        ["Snack", "Colazione", "Pranzo"]
    ) == "dinner"


def test_snack_alone_does_not_skip_breakfast():
    assert next_slot(["Snack"]) == "breakfast"
