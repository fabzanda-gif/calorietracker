from datetime import date
from types import SimpleNamespace

import pytest

from backend.services.meal_confirmation import (
    MealAlreadyLoggedError,
    MealConfirmationService,
    MealPredictionUnavailableError,
)


DAY = date(2026, 9, 1)


class FakeMealsRepository:
    def __init__(self, *, breakfast_exists=False):
        self.breakfast_already_exists = breakfast_exists
        self.created = []

    def breakfast_exists(self, user_id, log_date):
        return self.breakfast_already_exists

    def create_compatible(self, payload):
        self.created.append(payload)
        return SimpleNamespace(
            data=[
                {
                    "id": "meal-1",
                    **payload,
                }
            ]
        )


def prediction():
    return {
        "meal_type": "Colazione",
        "value": "Colazione Ufficio",
        "state": "predicted",
        "source": "routine",
        "confidence": 1.0,
        "confidence_level": "high",
        "day_context": "Ufficio",
        "estimated_calories": 310,
        "estimated_protein_g": 18,
        "estimated_carbs_g": 35,
        "estimated_fat_g": 10,
        "evidence": {
            "observations": 4,
            "matches": 4,
            "recent_observations": 4,
            "recent_matches": 4,
        },
    }


def test_prediction_confirmation_creates_real_meal():
    repo = FakeMealsRepository()
    result = MealConfirmationService(repo).confirm(
        user_id="u1",
        day_date=DAY,
        prediction=prediction(),
    )

    assert result["confirmed"] is True
    assert result["item"]["id"] == "meal-1"

    assert repo.created == [
        {
            "user_id": "u1",
            "date": "2026-09-01",
            "meal_type": "Colazione",
            "name": "Colazione Ufficio",
            "calories": 310.0,
            "protein": 18.0,
            "carbs": 35.0,
            "fat": 10.0,
        }
    ]


def test_existing_breakfast_is_not_duplicated():
    repo = FakeMealsRepository(
        breakfast_exists=True,
    )

    with pytest.raises(MealAlreadyLoggedError):
        MealConfirmationService(repo).confirm(
            user_id="u1",
            day_date=DAY,
            prediction=prediction(),
        )

    assert repo.created == []


def test_unknown_prediction_cannot_be_confirmed():
    repo = FakeMealsRepository()

    with pytest.raises(MealPredictionUnavailableError):
        MealConfirmationService(repo).confirm(
            user_id="u1",
            day_date=DAY,
            prediction={
                "meal_type": "Colazione",
                "value": None,
                "state": "unknown",
            },
        )

    assert repo.created == []


def test_missing_macro_estimates_are_written_as_zero_not_invented():
    repo = FakeMealsRepository()
    p = prediction()
    p["estimated_carbs_g"] = None
    p["estimated_fat_g"] = None

    result = MealConfirmationService(repo).confirm(
        user_id="u1",
        day_date=DAY,
        prediction=p,
    )

    assert result["item"]["carbs"] == 0
    assert result["item"]["fat"] == 0


def test_structured_prediction_preserves_quantity_identity():
    repo = FakeMealsRepository()

    p = prediction()
    p.update(
        {
            "value": "Fit Lasagna",
            "estimated_quantity": 2,
            "estimated_calories": 696,
            "estimated_protein_g": 60,
            "estimated_carbs_g": 80,
            "estimated_fat_g": 24,
        }
    )

    result = MealConfirmationService(repo).confirm(
        user_id="u1",
        day_date=DAY,
        prediction=p,
    )

    item = result["item"]

    assert item["name"] == "Fit Lasagna"
    assert item["base_name"] == "Fit Lasagna"
    assert item["quantity"] == 2
    assert item["base_calories"] == 348
    assert item["base_protein"] == 30
    assert item["base_carbs"] == 40
    assert item["base_fat"] == 12

    assert item["calories"] == 696
    assert item["protein"] == 60
    assert item["carbs"] == 80
    assert item["fat"] == 24
