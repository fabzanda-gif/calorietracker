from backend.services.conversational_meal_logging import (
    ConversationalMealLoggingService,
)


def service():
    return ConversationalMealLoggingService()


def test_builds_preview_without_logging_anything():
    result = service().build_preview(
        text="Ho mangiato una carbonara e una mela",
        meal_type="Pranzo",
        interpreted_items=[
            {
                "name": "Carbonara",
                "quantity": 1,
                "unit": "porzione",
                "calories": 700,
                "protein": 30,
                "carbs": 80,
                "fat": 28,
                "estimated": True,
            },
            {
                "name": "Mela",
                "quantity": 1,
                "unit": "pezzo",
                "calories": 80,
                "protein": 0.5,
                "carbs": 21,
                "fat": 0.2,
                "estimated": True,
            },
        ],
    )

    assert result["status"] == "preview"
    assert result["meal_type"] == "Pranzo"
    assert result["original_text"] == (
        "Ho mangiato una carbonara e una mela"
    )

    assert len(result["items"]) == 2

    assert result["totals"] == {
        "calories": 780,
        "protein": 30.5,
        "carbs": 101,
        "fat": 28.2,
    }

    assert result["requires_confirmation"] is True


def test_marks_uncertain_quantity_for_user_review():
    result = service().build_preview(
        text="Ho mangiato del riso",
        meal_type="Pranzo",
        interpreted_items=[
            {
                "name": "Riso",
                "quantity": 150,
                "unit": "g",
                "calories": 195,
                "protein": 4,
                "carbs": 42,
                "fat": 0.5,
                "estimated": True,
                "uncertainty": "quantity",
            }
        ],
    )

    assert result["items"][0]["estimated"] is True
    assert (
        result["items"][0]["uncertainty"]
        == "quantity"
    )
    assert result["needs_review"] is True


def test_explicit_quantities_do_not_require_review():
    result = service().build_preview(
        text="Ho mangiato 200 grammi di yogurt",
        meal_type="Colazione",
        interpreted_items=[
            {
                "name": "Yogurt",
                "quantity": 200,
                "unit": "g",
                "calories": 120,
                "protein": 10,
                "carbs": 12,
                "fat": 3,
                "estimated": False,
            }
        ],
    )

    assert result["needs_review"] is False


def test_empty_interpretation_cannot_be_confirmed():
    result = service().build_preview(
        text="Non so cosa ho mangiato",
        meal_type="Pranzo",
        interpreted_items=[],
    )

    assert result["status"] == "needs_input"
    assert result["requires_confirmation"] is False
    assert result["items"] == []


def test_preview_preserves_structured_items_for_future_confirmation():
    result = service().build_preview(
        text="Due uova e una fetta di pane",
        meal_type="Colazione",
        interpreted_items=[
            {
                "name": "Uova",
                "quantity": 2,
                "unit": "pezzi",
                "calories": 156,
                "protein": 13,
                "carbs": 1,
                "fat": 11,
                "estimated": False,
            },
            {
                "name": "Pane",
                "quantity": 1,
                "unit": "fetta",
                "calories": 90,
                "protein": 3,
                "carbs": 17,
                "fat": 1,
                "estimated": True,
            },
        ],
    )

    assert result["items"][0]["name"] == "Uova"
    assert result["items"][0]["quantity"] == 2
    assert result["items"][1]["name"] == "Pane"
    assert result["items"][1]["unit"] == "fetta"
