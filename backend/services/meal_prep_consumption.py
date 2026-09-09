from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository


class MealPrepConsistencyError(RuntimeError):
    """Meal and inventory could not be kept consistent."""


class MealPrepPortionConflictError(MealPrepConsistencyError):
    """The inventory changed before the portion could be consumed."""


@dataclass(frozen=True)
class MealPrepConsumptionResult:
    meal: dict[str, Any]
    inventory: dict[str, Any]


class MealPrepConsumptionService:
    """
    Create a meal and consume one prepared portion.

    When the inventory update fails, the newly created meal is deleted so
    the meal log and inventory continue to describe the same event.
    """

    def __init__(
        self,
        *,
        meal_prep_repo: MealPrepRepository,
        meals_repo: MealsRepository,
    ):
        self.meal_prep_repo = meal_prep_repo
        self.meals_repo = meals_repo

    def create_and_consume(
        self,
        *,
        user_id: str,
        batch_id: Any,
        batch: dict[str, Any],
        meal_payload: dict[str, Any],
    ) -> MealPrepConsumptionResult:
        create_compatible = getattr(
            self.meals_repo,
            "create_compatible",
            None,
        )

        if callable(create_compatible):
            response = create_compatible(meal_payload)
        else:
            response = self.meals_repo.create(meal_payload)

        rows = getattr(response, "data", None) or []

        if rows:
            meal = rows[0]
        elif isinstance(response, dict):
            meal = response
        else:
            meal = meal_payload

        meal_id = meal.get("id")
        if meal_id is None:
            raise MealPrepConsistencyError(
                "Meal was created without an id"
            )

        remaining = int(batch.get("portions_remaining") or 0)
        new_remaining = remaining - 1
        update = {
            "portions_remaining": new_remaining,
            "status": (
                "finished"
                if new_remaining == 0
                else "available"
            ),
        }

        try:
            consume_portion = getattr(
                self.meal_prep_repo,
                "consume_portion",
                None,
            )

            if callable(consume_portion):
                inventory = consume_portion(
                    batch_id,
                    user_id,
                    expected_remaining=remaining,
                )
            else:
                inventory = self.meal_prep_repo.update(
                    batch_id,
                    user_id,
                    update,
                )

            if inventory is None:
                raise MealPrepPortionConflictError(
                    "Meal prep portion was already consumed"
                )
        except Exception:
            delete_meal = getattr(
                self.meals_repo,
                "delete",
                None,
            )
            if callable(delete_meal):
                try:
                    delete_meal(meal_id, user_id)
                except Exception:
                    pass
            raise

        return MealPrepConsumptionResult(
            meal=meal,
            inventory=inventory,
        )
