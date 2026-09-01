from __future__ import annotations

from typing import Any


class MealReplanningService:
    """
    Choose the best realistic recommendation for the current
    state of the day.

    Rules:
    - in auto mode, keep the routine when its normal portion
      fits the available budget;
    - never change the portion of a candidate automatically;
    - when the routine does not fit, choose the best compatible
      candidate already supplied by the ranking layer;
    - if nothing is compatible, return None.
    """

    def recommend(
        self,
        *,
        routine_candidate: dict[str, Any] | None,
        ranked_options: list[dict[str, Any]],
        available_kcal: float | None,
    ) -> dict[str, Any] | None:
        """
        Prefer the normal routine when it fits.

        If the routine does not fit, fall back to the best
        already-ranked candidate that fits at its original
        portion.

        No candidate is ever portion-adapted here.
        """

        if isinstance(routine_candidate, dict):
            if self._fits_budget(
                routine_candidate,
                available_kcal,
            ):
                return self._recommendation(
                    candidate=dict(routine_candidate),
                    multiplier=1.0,
                    strategy="routine",
                    original_candidate=routine_candidate,
                )

        for option in ranked_options:
            candidate = option.get("candidate")

            if not isinstance(candidate, dict):
                continue

            if not self._fits_budget(
                candidate,
                available_kcal,
            ):
                continue

            return self._recommendation(
                candidate=dict(candidate),
                multiplier=1.0,
                strategy="alternate_candidate",
                original_candidate=candidate,
            )

        return None

    @classmethod
    def _fits_budget(
        cls,
        candidate: dict[str, Any],
        available_kcal: float | None,
    ) -> bool:
        if available_kcal is None:
            return True

        calories = cls._number(
            candidate.get("calories")
        )

        available = cls._number(
            available_kcal
        )

        return calories <= available

    @classmethod
    def _recommendation(
        cls,
        *,
        candidate: dict[str, Any],
        multiplier: float,
        strategy: str,
        original_candidate: Any,
    ) -> dict[str, Any]:
        original = (
            original_candidate
            if isinstance(original_candidate, dict)
            else {}
        )

        original_calories = cls._number(
            original.get("calories")
        )

        recommended_calories = cls._number(
            candidate.get("calories")
        )

        original_quantity = cls._number(
            original.get("quantity")
        )

        recommended_quantity = (
            round(
                original_quantity * multiplier,
                2,
            )
            if original_quantity > 0
            else None
        )

        return {
            "candidate": candidate,
            "portion_multiplier": multiplier,
            "recommended_quantity": recommended_quantity,
            "strategy": strategy,
            "reason": cls._reason(strategy),
            "adaptation": {
                "changed": multiplier != 1.0,
                "original_calories": original_calories,
                "recommended_calories": recommended_calories,
                "calorie_delta": round(
                    recommended_calories
                    - original_calories,
                    2,
                ),
            },
        }

    @staticmethod
    def _reason(strategy: str) -> str:
        return {
            "routine": (
                "La routine abituale è compatibile "
                "con la giornata di oggi."
            ),
            "alternate_candidate": (
                "La routine non entra nel margine disponibile, "
                "quindi scelgo la migliore alternativa "
                "compatibile nel pool di oggi."
            ),
        }.get(
            strategy,
            "Scelta selezionata dal motore.",
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0
