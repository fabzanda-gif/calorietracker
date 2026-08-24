from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.recipes import RecipesRepository


VALID_STATUSES = {
    "available",
    "finished",
    "expired",
    "discarded",
}


class MealPrepError(ValueError):
    pass


class MealPrepNotFoundError(MealPrepError):
    pass


class MealPrepUnavailableError(MealPrepError):
    pass


class MealPrepService:
    """
    Operational meal-prep inventory.

    A batch snapshots recipe name and per-portion nutrition at preparation
    time. Later recipe edits therefore never rewrite what was actually cooked.

    v0.2 adds quick inventory corrections:
    - explicit remaining portions;
    - zero remaining -> finished;
    - positive remaining -> available again.
    """

    def __init__(
        self,
        meal_prep_repo: MealPrepRepository,
        recipes_repo: RecipesRepository,
    ):
        self.meal_prep_repo = meal_prep_repo
        self.recipes_repo = recipes_repo

    def create_from_recipe(
        self,
        *,
        user_id: str,
        recipe_id: Any,
        prepared_at: date,
        portions_prepared: int,
        expires_at: date | None = None,
    ) -> dict:
        if portions_prepared <= 0:
            raise MealPrepError(
                "portions_prepared must be greater than zero"
            )

        recipe = self.recipes_repo.get_personal_by_id(
            recipe_id,
            user_id,
        )
        if recipe is None:
            raise MealPrepNotFoundError("Recipe not found")

        recipe_servings = self._positive_float(
            recipe.get("recipe_servings")
        ) or 1.0

        payload = {
            "user_id": user_id,
            "recipe_id": recipe.get("id"),
            "name": recipe.get("name") or "Meal prep",
            "prepared_at": str(prepared_at),
            "expires_at": (
                str(expires_at)
                if expires_at is not None
                else None
            ),
            "portions_prepared": int(portions_prepared),
            "portions_remaining": int(portions_prepared),
            "calories_per_portion": self._per_portion(
                recipe.get("calories"),
                recipe_servings,
            ),
            "protein_per_portion": self._per_portion(
                recipe.get("protein"),
                recipe_servings,
            ),
            "carbs_per_portion": self._per_portion(
                recipe.get("carbs"),
                recipe_servings,
            ),
            "fat_per_portion": self._per_portion(
                recipe.get("fat"),
                recipe_servings,
            ),
            "status": "available",
        }

        item = self.meal_prep_repo.create(payload)
        return item if item is not None else payload

    def consume_portion(
        self,
        *,
        user_id: str,
        batch_id: Any,
        portions: int = 1,
    ) -> dict:
        if portions <= 0:
            raise MealPrepError(
                "portions must be greater than zero"
            )

        batch = self._get_batch(batch_id, user_id)

        if batch.get("status") != "available":
            raise MealPrepUnavailableError(
                "Meal prep batch is not available"
            )

        remaining = int(batch.get("portions_remaining") or 0)
        if remaining < portions:
            raise MealPrepUnavailableError(
                "Not enough portions remaining"
            )

        return self.set_remaining_portions(
            user_id=user_id,
            batch_id=batch_id,
            portions_remaining=remaining - portions,
        )

    def set_remaining_portions(
        self,
        *,
        user_id: str,
        batch_id: Any,
        portions_remaining: int,
    ) -> dict:
        """
        Fast correction for stale inventory.

        Example: the app says 4 portions remain, but the user knows only 2 do.
        """
        if portions_remaining < 0:
            raise MealPrepError(
                "portions_remaining cannot be negative"
            )

        batch = self._get_batch(batch_id, user_id)

        prepared = int(batch.get("portions_prepared") or 0)
        if portions_remaining > prepared:
            raise MealPrepError(
                "portions_remaining cannot exceed portions_prepared"
            )

        payload = {
            "portions_remaining": int(portions_remaining),
            "status": (
                "finished"
                if portions_remaining == 0
                else "available"
            ),
        }

        item = self.meal_prep_repo.update(
            batch_id,
            user_id,
            payload,
        )
        return item if item is not None else {
            **batch,
            **payload,
        }

    def set_status(
        self,
        *,
        user_id: str,
        batch_id: Any,
        status: str,
    ) -> dict:
        if status not in VALID_STATUSES:
            raise MealPrepError("Invalid meal prep status")

        batch = self._get_batch(batch_id, user_id)

        payload: dict[str, Any] = {"status": status}
        if status in {"finished", "expired", "discarded"}:
            payload["portions_remaining"] = 0

        item = self.meal_prep_repo.update(
            batch_id,
            user_id,
            payload,
        )
        return item if item is not None else {
            **batch,
            **payload,
        }

    def _get_batch(self, batch_id: Any, user_id: str) -> dict:
        batch = self.meal_prep_repo.get_by_id(
            batch_id,
            user_id,
        )
        if batch is None:
            raise MealPrepNotFoundError(
                "Meal prep batch not found"
            )
        return batch

    @staticmethod
    def _positive_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _per_portion(
        value: Any,
        servings: float,
    ) -> float:
        try:
            total = float(value or 0)
        except (TypeError, ValueError):
            total = 0.0
        return round(max(0.0, total / servings), 2)
