from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository


class MealPrepLoggingError(ValueError):
    pass


class MealPrepBatchNotFoundError(MealPrepLoggingError):
    pass


class MealPrepBatchUnavailableError(MealPrepLoggingError):
    pass


class MealPrepLoggingService:
    """
    Close the meal-prep loop:
    one user action creates the real meal and consumes inventory.

    The meal is built from the batch nutrition snapshot, not from the current
    recipe, so later recipe edits cannot rewrite historical intake.
    """

    def __init__(
        self,
        *,
        meal_prep_repo: MealPrepRepository,
        meals_repo: MealsRepository,
    ):
        self.meal_prep_repo = meal_prep_repo
        self.meals_repo = meals_repo

    def log_portion(
        self,
        *,
        user_id: str,
        batch_id: Any,
        meal_date: date,
        meal_type: str,
    ) -> dict:
        batch = self.meal_prep_repo.get_by_id(batch_id, user_id)
        if batch is None:
            raise MealPrepBatchNotFoundError(
                "Meal prep batch not found"
            )

        remaining = int(batch.get("portions_remaining") or 0)
        if batch.get("status") != "available" or remaining <= 0:
            raise MealPrepBatchUnavailableError(
                "Meal prep batch is not available"
            )

        payload = {
            "user_id": user_id,
            "date": str(meal_date),
            "meal_type": meal_type,
            "name": batch.get("name") or "Meal prep",
            "base_name": batch.get("name") or "Meal prep",
            "quantity": 1,
            "is_per_100g": False,
            "base_calories": self._number(
                batch.get("calories_per_portion")
            ),
            "base_protein": self._number(
                batch.get("protein_per_portion")
            ),
            "base_carbs": self._number(
                batch.get("carbs_per_portion")
            ),
            "base_fat": self._number(
                batch.get("fat_per_portion")
            ),
            "calories": self._number(
                batch.get("calories_per_portion")
            ),
            "protein": self._number(
                batch.get("protein_per_portion")
            ),
            "carbs": self._number(
                batch.get("carbs_per_portion")
            ),
            "fat": self._number(
                batch.get("fat_per_portion")
            ),
            "notes": "Logged from meal prep inventory",
            "category": "meal_prep",
        }

        meal = self.meals_repo.create(payload)
        if meal is None:
            meal = payload

        new_remaining = remaining - 1
        batch_update = {
            "portions_remaining": new_remaining,
            "status": (
                "finished"
                if new_remaining == 0
                else "available"
            ),
        }

        updated_batch = self.meal_prep_repo.update(
            batch_id,
            user_id,
            batch_update,
        )
        if updated_batch is None:
            updated_batch = {
                **batch,
                **batch_update,
            }

        return {
            "logged": True,
            "meal": meal,
            "inventory": updated_batch,
        }

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, float(value or 0))
        except (TypeError, ValueError):
            return 0.0
