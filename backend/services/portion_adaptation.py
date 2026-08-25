from __future__ import annotations

from typing import Any


class PortionAdaptationService:
    """
    Adapt a meal candidate to a realistic portion multiplier.

    V1 rules:
    - normal portion is 1.0x;
    - supported steps are quarter portions;
    - do not shrink below 0.5x;
    - do not automatically increase above 1.5x;
    - small calorie overshoots are tolerated;
    - the input candidate is never mutated.
    """

    PORTION_STEPS = (
        0.5,
        0.75,
        1.0,
        1.25,
        1.5,
    )

    TOLERANCE_KCAL = 25.0

    def adapt(
        self,
        *,
        candidate: dict[str, Any],
        available_kcal: float | None,
    ) -> dict[str, Any] | None:
        result = dict(candidate)

        calories = self._number(
            candidate.get("calories")
        )

        if calories <= 0:
            return None

        if available_kcal is None:
            return self._scaled(
                result,
                multiplier=1.0,
            )

        available = max(
            0.0,
            self._number(available_kcal),
        )

        # Keep the normal portion when it already fits.
        if calories <= available + self.TOLERANCE_KCAL:
            return self._scaled(
                result,
                multiplier=1.0,
            )

        # Find the largest human-friendly portion that is
        # compatible with the remaining budget.
        compatible = [
            multiplier
            for multiplier in self.PORTION_STEPS
            if (
                multiplier <= 1.0
                and calories * multiplier
                <= available + self.TOLERANCE_KCAL
            )
        ]

        if not compatible:
            return None

        multiplier = max(compatible)

        return self._scaled(
            result,
            multiplier=multiplier,
        )

    @classmethod
    def _scaled(
        cls,
        candidate: dict[str, Any],
        *,
        multiplier: float,
    ) -> dict[str, Any]:
        result = dict(candidate)

        result["portion_multiplier"] = multiplier

        for field in (
            "calories",
            "protein_g",
            "carbs_g",
            "fat_g",
        ):
            value = cls._number(
                candidate.get(field)
            )

            result[field] = cls._rounded(
                value * multiplier
            )

        return result

    @staticmethod
    def _number(
        value: Any,
    ) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _rounded(
        value: float,
    ) -> float:
        rounded = round(value, 2)

        if rounded.is_integer():
            return int(rounded)

        return rounded
