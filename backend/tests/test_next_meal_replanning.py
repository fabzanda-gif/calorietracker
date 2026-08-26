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


def test_dinner_is_next_after_breakfast_and_lunch():
    assert next_slot(
        ["Colazione", "Pranzo"]
    ) == "dinner"


def test_no_next_meal_after_full_day():
    assert next_slot(
        ["Colazione", "Pranzo", "Cena"]
    ) is None


def test_extra_meal_does_not_change_normal_sequence():
    assert next_slot(
        ["Spuntino", "Colazione"]
    ) == "lunch"


def test_order_of_logged_rows_does_not_matter():
    assert next_slot(
        ["Pranzo", "Colazione"]
    ) == "dinner"


def test_extra_meal_does_not_advance_standard_sequence():
    service = NextMealReplanningService()

    assert service.next_slot(
        logged_meal_types=["Spuntino"],
    ) == "breakfast"

    assert service.next_slot(
        logged_meal_types=["Colazione", "Spuntino"],
    ) == "lunch"

    assert service.next_slot(
        logged_meal_types=[
            "Colazione",
            "Spuntino",
            "Pranzo",
        ],
    ) == "dinner"
