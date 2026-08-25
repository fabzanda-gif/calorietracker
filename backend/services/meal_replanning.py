from __future__ import annotations

from typing import Any

from backend.services.portion_adaptation import (
    PortionAdaptationService,
)


class MealReplanningService:
    """
    Choose a realistic recommendation for the current
    state of the day.

    In auto mode the caller may supply the routine as the
    preferred starting point. Explicit modes can omit it and
    rely only on already-ranked compatible alternatives.
    """

    def __init__(self) -> None:
        self.portions = PortionAdaptationService()

    def recommend(
        self,
        *,
        routine_candidate: dict[str, Any] | None,
        ranked_options: list[dict[str, Any]],
        available_kcal: float | None,
    ) -> dict[str, Any] | None:
        routine_result = self._adapt_candidate(
            candidate=routine_candidate,
            available_kcal=available_kcal,
        )

        if routine_result is not None:
            multiplier = float(
                routine_result["portion_multiplier"]
            )

            return self._recommendation(
                candidate=routine_result,
                multiplier=multiplier,
                strategy=(
                    "routine"
                    if multiplier == 1.0
                    else "adapted_routine"
                ),
                original_candidate=routine_candidate,
            )

        for option in ranked_options:
            candidate = option.get("candidate")

            alternative_result = self._adapt_candidate(
                candidate=candidate,
                available_kcal=available_kcal,
            )

            if alternative_result is None:
                continue

            multiplier = float(
                alternative_result[
                    "portion_multiplier"
                ]
            )

            return self._recommendation(
                candidate=alternative_result,
                multiplier=multiplier,
                strategy=(
                    "alternate_candidate"
                    if multiplier == 1.0
                    else "adapted_alternative"
                ),
                original_candidate=candidate,
            )

        return None

    def _adapt_candidate(
        self,
        *,
        candidate: Any,
        available_kcal: float | None,
    ) -> dict[str, Any] | None:
        if not isinstance(candidate, dict):
            return None

        return self.portions.adapt(
            candidate=candidate,
            available_kcal=available_kcal,
        )

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

        return {
            "candidate": candidate,
            "portion_multiplier": multiplier,
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
            "adapted_routine": (
                "La routine resta una buona scelta, "
                "con una porzione adattata al margine di oggi."
            ),
            "alternate_candidate": (
                "La routine richiederebbe una porzione poco "
                "realistica, quindi conviene un'altra opzione."
            ),
            "adapted_alternative": (
                "Un'alternativa è più adatta alla giornata, "
                "con una porzione leggermente adattata."
            ),
        }[strategy]

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0
