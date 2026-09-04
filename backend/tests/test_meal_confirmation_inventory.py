from datetime import date
from types import SimpleNamespace

import pytest

from backend.services.meal_confirmation import (
    MealAlreadyLoggedError,
    MealConfirmationService,
)


class FakeMealsRepository:
    def __init__(self):
        self.rows = []

    def list_for_date_compatible(self, *, user_id, log_date):
        return [
            row
            for row in self.rows
            if row["user_id"] == user_id
            and row["date"] == str(log_date)
        ]

    def create_compatible(self, payload):
        row = {"id": "meal-1", **payload}
        self.rows.append(row)
        return SimpleNamespace(data=[row])


class FakeMealPrepRepository:
    def __init__(self):
        self.batch = {
            "id": "batch-1",
            "user_id": "user-1",
            "name": "Lasagna",
            "portions_remaining": 2,
            "status": "available",
        }
        self.updates = []

    def get_by_id(self, batch_id, user_id):
        if (
            batch_id != self.batch["id"]
            or user_id != self.batch["user_id"]
        ):
            return None

        return dict(self.batch)

    def update(self, batch_id, user_id, payload):
        self.updates.append(
            (batch_id, user_id, dict(payload))
        )
        self.batch.update(payload)
        return dict(self.batch)


def prediction():
    return {
        "state": "predicted",
        "meal_type": "Pranzo",
        "value": "Lasagna",
        "estimated_calories": 500,
        "estimated_protein_g": 30,
        "estimated_carbs_g": 55,
        "estimated_fat_g": 18,
        "recommendation_source": "meal_prep",
        "recommendation_source_id": "batch-1",
    }


def test_confirming_meal_prep_consumes_exactly_one_portion():
    meals = FakeMealsRepository()
    inventory = FakeMealPrepRepository()

    result = MealConfirmationService(
        meals,
        inventory,
    ).confirm(
        user_id="user-1",
        day_date=date(2026, 9, 4),
        prediction=prediction(),
    )

    assert result["confirmed"] is True
    assert inventory.batch["portions_remaining"] == 1
    assert inventory.batch["status"] == "available"
    assert len(inventory.updates) == 1


def test_second_confirmation_does_not_consume_again():
    meals = FakeMealsRepository()
    inventory = FakeMealPrepRepository()
    service = MealConfirmationService(
        meals,
        inventory,
    )

    service.confirm(
        user_id="user-1",
        day_date=date(2026, 9, 4),
        prediction=prediction(),
    )

    with pytest.raises(MealAlreadyLoggedError):
        service.confirm(
            user_id="user-1",
            day_date=date(2026, 9, 4),
            prediction=prediction(),
        )

    assert inventory.batch["portions_remaining"] == 1
    assert len(inventory.updates) == 1


def test_last_portion_finishes_batch():
    meals = FakeMealsRepository()
    inventory = FakeMealPrepRepository()
    inventory.batch["portions_remaining"] = 1

    MealConfirmationService(
        meals,
        inventory,
    ).confirm(
        user_id="user-1",
        day_date=date(2026, 9, 4),
        prediction=prediction(),
    )

    assert inventory.batch["portions_remaining"] == 0
    assert inventory.batch["status"] == "finished"
