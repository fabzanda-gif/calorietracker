from backend.services.decision_commit import (
    DecisionCommitService,
)


class Response:
    def __init__(self, data):
        self.data = data


class FakeSelections:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, payload):
        item = {
            "id": "selection-1",
            **payload,
        }
        self.created.append(item)
        return item

    def delete(self, selection_id, user_id):
        self.deleted.append(
            (selection_id, user_id)
        )
        return True


class FakeMeals:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.created = []

    def list_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
        return self.existing

    def create_compatible(self, payload):
        item = {
            "id": "meal-1",
            **payload,
        }
        self.created.append(item)
        return Response([item])


def candidate():
    return {
        "name": "Poke Salmone",
        "source": "delivery",
        "calories": 650,
        "protein_g": 40,
        "carbs_g": 70,
        "fat_g": 20,
    }


def test_commit_creates_selection_and_meal():
    selections = FakeSelections()
    meals = FakeMeals()

    result = DecisionCommitService(
        selections,
        meals,
    ).commit(
        user_id="u1",
        day_date="2026-08-24",
        meal_slot="dinner",
        mode="order",
        lens="taste",
        option_index=0,
        candidate=candidate(),
        available_kcal=1000,
        protein_remaining_g=100,
    )

    assert result["committed"] is True
    assert result["already_committed"] is False
    assert len(selections.created) == 1
    assert len(meals.created) == 1

    meal = meals.created[0]
    assert meal["meal_type"] == "Cena"
    assert meal["name"] == "Poke Salmone"
    assert meal["calories"] == 650
    assert meal["protein"] == 40
    assert meal["carbs"] == 70
    assert meal["fat"] == 20


def test_same_meal_is_idempotent():
    existing = {
        "id": "existing-meal",
        "date": "2026-08-24",
        "meal_type": "Cena",
        "name": "Poke Salmone",
        "base_name": "Poke Salmone",
    }

    selections = FakeSelections()
    meals = FakeMeals(
        existing=[existing]
    )

    result = DecisionCommitService(
        selections,
        meals,
    ).commit(
        user_id="u1",
        day_date="2026-08-24",
        meal_slot="dinner",
        mode="order",
        lens="taste",
        option_index=0,
        candidate=candidate(),
    )

    assert result["already_committed"] is True
    assert result["meal"]["id"] == "existing-meal"
    assert selections.created == []
    assert meals.created == []
