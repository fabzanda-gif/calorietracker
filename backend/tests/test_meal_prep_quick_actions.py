from datetime import date

import pytest

from backend.services.meal_prep import (
    MealPrepError,
    MealPrepService,
)


class FakeRecipesRepository:
    def get_personal_by_id(self, recipe_id, user_id):
        return {
            "id": recipe_id,
            "name": "Chili",
            "recipe_servings": 4,
            "calories": 2000,
            "protein": 120,
            "carbs": 240,
            "fat": 60,
        }


class FakeMealPrepRepository:
    def __init__(self):
        self.item = {
            "id": "batch-1",
            "user_id": "u1",
            "name": "Chili",
            "portions_prepared": 6,
            "portions_remaining": 4,
            "status": "available",
        }

    def get_by_id(self, batch_id, user_id):
        if (
            batch_id == self.item["id"]
            and user_id == self.item["user_id"]
        ):
            return self.item
        return None

    def update(self, batch_id, user_id, payload):
        self.item.update(payload)
        return self.item


def service():
    return MealPrepService(
        meal_prep_repo=FakeMealPrepRepository(),
        recipes_repo=FakeRecipesRepository(),
    )


def test_quick_correction_can_reduce_remaining_portions():
    item = service().set_remaining_portions(
        user_id="u1",
        batch_id="batch-1",
        portions_remaining=2,
    )

    assert item["portions_remaining"] == 2
    assert item["status"] == "available"


def test_setting_zero_remaining_marks_finished():
    item = service().set_remaining_portions(
        user_id="u1",
        batch_id="batch-1",
        portions_remaining=0,
    )

    assert item["portions_remaining"] == 0
    assert item["status"] == "finished"


def test_positive_remaining_can_restore_available_status():
    s = service()
    s.meal_prep_repo.item["status"] = "finished"
    s.meal_prep_repo.item["portions_remaining"] = 0

    item = s.set_remaining_portions(
        user_id="u1",
        batch_id="batch-1",
        portions_remaining=1,
    )

    assert item["status"] == "available"
    assert item["portions_remaining"] == 1


def test_remaining_cannot_exceed_original_batch_size():
    with pytest.raises(MealPrepError):
        service().set_remaining_portions(
            user_id="u1",
            batch_id="batch-1",
            portions_remaining=7,
        )
