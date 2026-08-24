from datetime import date

import pytest

from backend.services.meal_prep_logging import (
    MealPrepBatchNotFoundError,
    MealPrepBatchUnavailableError,
    MealPrepLoggingService,
)


class FakeMealPrepRepository:
    def __init__(self, remaining=2, status="available"):
        self.item = {
            "id": "batch-1",
            "user_id": "u1",
            "name": "Chili",
            "status": status,
            "portions_prepared": 4,
            "portions_remaining": remaining,
            "calories_per_portion": 500,
            "protein_per_portion": 30,
            "carbs_per_portion": 55,
            "fat_per_portion": 14,
        }

    def get_by_id(self, batch_id, user_id):
        if batch_id == "batch-1" and user_id == "u1":
            return self.item
        return None

    def update(self, batch_id, user_id, payload):
        self.item.update(payload)
        return self.item


class FakeMealsRepository:
    def __init__(self):
        self.created = None

    def create(self, payload):
        self.created = payload
        return {"id": "meal-1", **payload}


def build(remaining=2, status="available"):
    inventory = FakeMealPrepRepository(remaining, status)
    meals = FakeMealsRepository()
    service = MealPrepLoggingService(
        meal_prep_repo=inventory,
        meals_repo=meals,
    )
    return service, inventory, meals


def test_logging_portion_creates_real_meal():
    service, inventory, meals = build()

    result = service.log_portion(
        user_id="u1",
        batch_id="batch-1",
        meal_date=date(2026, 9, 6),
        meal_type="Pranzo",
    )

    assert result["logged"] is True
    assert result["meal"]["name"] == "Chili"
    assert result["meal"]["calories"] == 500.0
    assert result["meal"]["protein"] == 30.0
    assert meals.created["category"] == "meal_prep"


def test_logging_portion_decrements_inventory():
    service, inventory, meals = build(remaining=2)

    result = service.log_portion(
        user_id="u1",
        batch_id="batch-1",
        meal_date=date(2026, 9, 6),
        meal_type="Cena",
    )

    assert result["inventory"]["portions_remaining"] == 1
    assert result["inventory"]["status"] == "available"


def test_last_portion_marks_batch_finished():
    service, inventory, meals = build(remaining=1)

    result = service.log_portion(
        user_id="u1",
        batch_id="batch-1",
        meal_date=date(2026, 9, 6),
        meal_type="Pranzo",
    )

    assert result["inventory"]["portions_remaining"] == 0
    assert result["inventory"]["status"] == "finished"


def test_unavailable_batch_is_rejected():
    service, inventory, meals = build(
        remaining=0,
        status="finished",
    )

    with pytest.raises(MealPrepBatchUnavailableError):
        service.log_portion(
            user_id="u1",
            batch_id="batch-1",
            meal_date=date(2026, 9, 6),
            meal_type="Pranzo",
        )

    assert meals.created is None


def test_missing_batch_is_rejected():
    service, inventory, meals = build()

    with pytest.raises(MealPrepBatchNotFoundError):
        service.log_portion(
            user_id="u1",
            batch_id="missing",
            meal_date=date(2026, 9, 6),
            meal_type="Pranzo",
        )
