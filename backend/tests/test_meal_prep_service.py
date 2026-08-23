from datetime import date

import pytest

from backend.services.meal_prep import (
    MealPrepNotFoundError,
    MealPrepService,
    MealPrepUnavailableError,
)


class FakeRecipesRepository:
    def get_personal_by_id(self, recipe_id, user_id):
        if recipe_id == "missing":
            return None
        return {
            "id": recipe_id,
            "user_id": user_id,
            "name": "Chili",
            "recipe_servings": 4,
            "calories": 2000,
            "protein": 120,
            "carbs": 240,
            "fat": 60,
        }


class FakeMealPrepRepository:
    def __init__(self):
        self.items = {}
        self.created = []

    def create(self, payload):
        item = {"id": "batch-1", **payload}
        self.items["batch-1"] = item
        self.created.append(item)
        return item

    def get_by_id(self, batch_id, user_id):
        item = self.items.get(batch_id)
        if item and item["user_id"] == user_id:
            return item
        return None

    def update(self, batch_id, user_id, payload):
        item = self.get_by_id(batch_id, user_id)
        if item is None:
            return None
        item.update(payload)
        return item


def service():
    return MealPrepService(
        meal_prep_repo=FakeMealPrepRepository(),
        recipes_repo=FakeRecipesRepository(),
    )


def test_create_snapshots_recipe_and_per_portion_nutrition():
    s = service()

    item = s.create_from_recipe(
        user_id="u1",
        recipe_id="r1",
        prepared_at=date(2026, 9, 1),
        portions_prepared=5,
        expires_at=date(2026, 9, 5),
    )

    assert item["recipe_id"] == "r1"
    assert item["name"] == "Chili"
    assert item["portions_prepared"] == 5
    assert item["portions_remaining"] == 5
    assert item["calories_per_portion"] == 500
    assert item["protein_per_portion"] == 30
    assert item["status"] == "available"


def test_missing_recipe_is_rejected():
    s = service()

    with pytest.raises(MealPrepNotFoundError):
        s.create_from_recipe(
            user_id="u1",
            recipe_id="missing",
            prepared_at=date(2026, 9, 1),
            portions_prepared=4,
        )


def test_consume_one_portion_reduces_inventory():
    s = service()
    s.create_from_recipe(
        user_id="u1",
        recipe_id="r1",
        prepared_at=date(2026, 9, 1),
        portions_prepared=3,
    )

    item = s.consume_portion(
        user_id="u1",
        batch_id="batch-1",
    )

    assert item["portions_remaining"] == 2
    assert item["status"] == "available"


def test_consuming_last_portion_marks_finished():
    s = service()
    s.create_from_recipe(
        user_id="u1",
        recipe_id="r1",
        prepared_at=date(2026, 9, 1),
        portions_prepared=1,
    )

    item = s.consume_portion(
        user_id="u1",
        batch_id="batch-1",
    )

    assert item["portions_remaining"] == 0
    assert item["status"] == "finished"


def test_cannot_consume_more_than_remaining():
    s = service()
    s.create_from_recipe(
        user_id="u1",
        recipe_id="r1",
        prepared_at=date(2026, 9, 1),
        portions_prepared=2,
    )

    with pytest.raises(MealPrepUnavailableError):
        s.consume_portion(
            user_id="u1",
            batch_id="batch-1",
            portions=3,
        )


@pytest.mark.parametrize(
    "new_status",
    ["finished", "expired", "discarded"],
)
def test_terminal_status_zeroes_remaining(new_status):
    s = service()
    s.create_from_recipe(
        user_id="u1",
        recipe_id="r1",
        prepared_at=date(2026, 9, 1),
        portions_prepared=4,
    )

    item = s.set_status(
        user_id="u1",
        batch_id="batch-1",
        status=new_status,
    )

    assert item["status"] == new_status
    assert item["portions_remaining"] == 0
