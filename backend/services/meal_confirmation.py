from __future__ import annotations

from datetime import date
from typing import Any

from backend.repositories.meal_prep import MealPrepRepository
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

    Generic across meal types. When the confirmed recommendation comes from
    meal-prep inventory, exactly one inventory portion is consumed.
    """

    def __init__(
        self,
        meals_repo: MealsRepository,
        meal_prep_repo: MealPrepRepository | None = None,
    ):
        self.meals_repo = meals_repo
        self.meal_prep_repo = meal_prep_repo

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

        source = prediction.get("recommendation_source")
        source_id = prediction.get("recommendation_source_id")

        meal_prep_batch = None

        if source == "meal_prep":
            if self.meal_prep_repo is None or not source_id:
                raise MealPredictionUnavailableError(
                    "Meal prep inventory reference is missing"
                )

            meal_prep_batch = self.meal_prep_repo.get_by_id(
                source_id,
                user_id,
            )

            if meal_prep_batch is None:
                raise MealPredictionUnavailableError(
                    "Meal prep batch is no longer available"
                )

            remaining = int(
                meal_prep_batch.get("portions_remaining") or 0
            )

            if (
                meal_prep_batch.get("status") != "available"
                or remaining <= 0
            ):
                raise MealPredictionUnavailableError(
                    "Meal prep batch is no longer available"
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

        estimated_quantity = prediction.get(
            "estimated_quantity"
        )

        if source == "meal_prep":
            payload.update(
                {
                    "base_name": str(prediction["value"]),
                    "quantity": 1,
                    "is_per_100g": False,
                    "base_calories": payload["calories"],
                    "base_protein": payload["protein"],
                    "base_carbs": payload["carbs"],
                    "base_fat": payload["fat"],
                    "category": "meal_prep",
                    "notes": (
                        "Confirmed from meal prep inventory; "
                        f"Meal prep batch: {source_id}"
                    ),
                }
            )

        elif estimated_quantity not in (None, ""):
            try:
                quantity = float(estimated_quantity)
            except (TypeError, ValueError):
                quantity = 0.0

            if quantity > 0:
                payload.update(
                    {
                        "base_name": str(
                            prediction["value"]
                        ),
                        "quantity": quantity,
                        "base_calories": round(
                            payload["calories"] / quantity,
                            2,
                        ),
                        "base_protein": round(
                            payload["protein"] / quantity,
                            2,
                        ),
                        "base_carbs": round(
                            payload["carbs"] / quantity,
                            2,
                        ),
                        "base_fat": round(
                            payload["fat"] / quantity,
                            2,
                        ),
                    }
                )

        response = self.meals_repo.create_compatible(payload)
        rows = getattr(response, "data", None) or []
        item = rows[0] if rows else payload

        updated_inventory = None

        if meal_prep_batch is not None:
            remaining = int(
                meal_prep_batch.get("portions_remaining") or 0
            )

            new_remaining = remaining - 1

            update = {
                "portions_remaining": new_remaining,
                "status": (
                    "finished"
                    if new_remaining == 0
                    else "available"
                ),
            }

            updated_inventory = self.meal_prep_repo.update(
                source_id,
                user_id,
                update,
            )

            if updated_inventory is None:
                updated_inventory = {
                    **meal_prep_batch,
                    **update,
                }

        result = {
            "confirmed": True,
            "date": str(day_date),
            "meal_type": meal_type,
            "item": item,
            "prediction": prediction,
        }

        if updated_inventory is not None:
            result["inventory"] = updated_inventory

        return result

    def _meal_type_exists(
        self,
        *,
        user_id: str,
        day_date: date,
        meal_type: str,
    ) -> bool:
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
