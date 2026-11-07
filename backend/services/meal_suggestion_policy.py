from __future__ import annotations

from typing import Any


class MealSuggestionPolicy:
    """
    Shared hard constraints for candidate generation, ranking and
    replanning. Scoring preferences deliberately remain outside this
    class.
    """

    MAIN_MEAL_TYPES = frozenset({"Pranzo", "Cena"})
    LIGHT_MEAL_TYPES = frozenset({"Colazione", "Snack"})
    DEFAULT_MIN_MAIN_MEAL_KCAL = 500.0
    DEFAULT_MAX_MAIN_MEAL_KCAL = 1000.0

    @classmethod
    def is_main_meal(
        cls,
        meal_type: object,
    ) -> bool:
        return (
            str(meal_type or "").strip()
            in cls.MAIN_MEAL_TYPES
        )

    @classmethod
    def compatible_meal_types(
        cls,
        meal_type: str,
    ) -> set[str]:
        """
        Lunch and dinner may swap. Every other slot remains isolated,
        so snacks and breakfast cannot leak into main meals.
        """
        normalized = str(meal_type or "").strip()

        if cls.is_main_meal(normalized):
            return set(cls.MAIN_MEAL_TYPES)

        if normalized in cls.LIGHT_MEAL_TYPES:
            return set(cls.LIGHT_MEAL_TYPES)

        return {normalized}

    @classmethod
    def main_meal_calories_are_valid(
        cls,
        calories: Any,
        *,
        max_kcal: float = DEFAULT_MAX_MAIN_MEAL_KCAL,
    ) -> bool:
        value = cls._number(calories)

        return (
            cls.DEFAULT_MIN_MAIN_MEAL_KCAL
            <= value
            <= float(max_kcal)
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
