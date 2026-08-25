from datetime import date

from backend.services.meal_candidates import (
    MealCandidateService,
)


def historical_meal(
    name: str,
    *,
    reusable: bool | None = True,
) -> dict:
    item = {
        "id": name.lower().replace(" ", "-"),
        "date": "2026-08-24",
        "meal_type": "Cena",
        "name": name,
        "calories": 600,
        "protein": 40,
        "carbs": 60,
        "fat": 20,
    }

    if reusable is not None:
        item["is_reusable"] = reusable

    return item


def build(history: list[dict]) -> list[dict]:
    return MealCandidateService().build(
        day_date=date(2026, 8, 25),
        meal_type="Cena",
        meal_prep_items=[],
        routine_prediction=None,
        recipes=[],
        historical_meals=history,
    )


def test_one_off_meal_is_not_reused_as_candidate():
    candidates = build(
        [
            historical_meal(
                "BBQ PadelDam",
                reusable=False,
            ),
            historical_meal(
                "Pasta normale",
                reusable=True,
            ),
        ]
    )

    names = {
        item["name"]
        for item in candidates
        if item["source"] == "meal_history"
    }

    assert "BBQ PadelDam" not in names
    assert "Pasta normale" in names


def test_old_meals_without_flag_remain_reusable():
    candidates = build(
        [
            historical_meal(
                "Cena legacy",
                reusable=None,
            ),
        ]
    )

    names = {
        item["name"]
        for item in candidates
        if item["source"] == "meal_history"
    }

    assert "Cena legacy" in names
