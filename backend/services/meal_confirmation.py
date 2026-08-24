from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.meals import MealsRepository


class MealConfirmationError(ValueError):
    pass


class MealAlreadyLoggedError(MealConfirmationError):
    pass


class MealPredictionUnavailableError(MealConfirmationError):
    pass


class MealConfirmationService:
    """
    Convert an explicit user confirmation of a prediction into a real meal log.

    Generic across meal types. The service never auto-confirms and always
    writes through the existing MealsRepository.
    """

    def __init__(self, meals_repo: MealsRepository):
        self.meals_repo = meals_repo

    def confirm(
        self,
        *,
        user_id: str,
        day_date: date,
        prediction: dict[str, Any],
    ) -> dict:
        if (
            prediction.get("state") != "predicted"
            or not prediction.get("value")
            or not prediction.get("meal_type")
        ):
            raise MealPredictionUnavailableError(
                "No valid meal prediction is available to confirm"
            )

        meal_type = str(prediction["meal_type"])

        if self._meal_type_exists(
            user_id=user_id,
            day_date=day_date,
            meal_type=meal_type,
        ):
            raise MealAlreadyLoggedError(
                f"{meal_type} is already logged for this date"
            )

        payload = {
            "user_id": user_id,
            "date": str(day_date),
            "meal_type": meal_type,
            "name": str(prediction["value"]),
            "calories": self._nutrition_value(
                prediction.get("estimated_calories")
            ),
            "protein": self._nutrition_value(
                prediction.get("estimated_protein_g")
            ),
            "carbs": self._nutrition_value(
                prediction.get("estimated_carbs_g")
            ),
            "fat": self._nutrition_value(
                prediction.get("estimated_fat_g")
            ),
        }

        response = self.meals_repo.create_compatible(payload)
        rows = getattr(response, "data", None) or []

        item = rows[0] if rows else payload

        return {
            "confirmed": True,
            "date": str(day_date),
            "meal_type": meal_type,
            "item": item,
            "prediction": prediction,
        }

    def _meal_type_exists(
        self,
        *,
        user_id: str,
        day_date: date,
        meal_type: str,
    ) -> bool:
        # Keep compatibility with the existing specialized breakfast helper.
        if meal_type == "Colazione" and hasattr(
            self.meals_repo,
            "breakfast_exists",
        ):
            return bool(
                self.meals_repo.breakfast_exists(
                    user_id,
                    day_date,
                )
            )

        rows = self.meals_repo.list_for_date_compatible(
            user_id=user_id,
            log_date=day_date,
        )

        return any(
            row.get("meal_type") == meal_type
            for row in rows
        )

    @staticmethod
    def _nutrition_value(value: Any) -> int:
        if value in (None, ""):
            return 0

        try:
            return max(0, int(round(float(value))))
        except (TypeError, ValueError):
            return 0
