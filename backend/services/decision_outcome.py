from __future__ import annotations

from datetime import date
from typing import Any


class DecisionOutcomeService:
    """
    Match a persisted decision selection to a meal that was actually logged.

    v0.1 is deliberately deterministic and conservative:
    - same calendar date;
    - compatible meal slot/type;
    - normalized candidate/meal name match;
    - optional calorie proximity as supporting evidence.

    No fuzzy semantic matching is used yet, to avoid teaching the learning
    loop from uncertain outcomes.
    """

    SLOT_TO_MEAL_TYPE = {
        "breakfast": "Colazione",
        "lunch": "Pranzo",
        "dinner": "Cena",
        "snack": "Spuntino",
    }

    def evaluate(
        self,
        *,
        selection: dict[str, Any],
        meals: list[dict[str, Any]],
    ) -> dict:
        candidate = selection.get("candidate") or {}
        candidate_name = self._normalize_name(
            candidate.get("name")
        )

        if not candidate_name:
            return self._result(
                status="unresolved",
                reason="candidate_name_missing",
            )

        selected_date = self._selection_date(selection)
        expected_type = self._meal_type(selection)

        compatible = [
            meal
            for meal in meals
            if self._meal_is_compatible(
                meal,
                selected_date=selected_date,
                expected_type=expected_type,
            )
        ]

        exact = [
            meal
            for meal in compatible
            if self._normalize_name(
                meal.get("base_name") or meal.get("name")
            )
            == candidate_name
        ]

        if len(exact) == 1:
            return self._matched(
                exact[0],
                reason="exact_name_match",
                confidence=1.0,
            )

        if len(exact) > 1:
            closest = self._closest_calorie_match(
                candidate,
                exact,
            )
            if closest is not None:
                return self._matched(
                    closest,
                    reason="exact_name_and_calorie_match",
                    confidence=1.0,
                )

            return self._result(
                status="ambiguous",
                reason="multiple_exact_name_matches",
            )

        return self._result(
            status="not_observed",
            reason="no_matching_logged_meal",
        )

    def _meal_is_compatible(
        self,
        meal: dict[str, Any],
        *,
        selected_date: str | None,
        expected_type: str | None,
    ) -> bool:
        if selected_date is not None:
            meal_date = meal.get("date")
            if meal_date is not None and str(meal_date) != selected_date:
                return False

        if expected_type is not None:
            meal_type = meal.get("meal_type")
            if meal_type and str(meal_type) != expected_type:
                return False

        return True

    def _meal_type(
        self,
        selection: dict[str, Any],
    ) -> str | None:
        explicit = selection.get("meal_type")
        if explicit:
            return str(explicit)

        slot = str(
            selection.get("meal_slot") or ""
        ).strip().lower()

        return self.SLOT_TO_MEAL_TYPE.get(slot)

    @staticmethod
    def _selection_date(
        selection: dict[str, Any],
    ) -> str | None:
        value = (
            selection.get("day_date")
            or selection.get("date")
        )

        if value is None:
            return None

        if isinstance(value, date):
            return value.isoformat()

        return str(value)

    def _closest_calorie_match(
        self,
        candidate: dict[str, Any],
        meals: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        target = self._number(
            candidate.get("calories")
        )

        if target is None:
            return None

        scored = []

        for meal in meals:
            calories = self._number(
                meal.get("calories")
            )
            if calories is None:
                continue

            scored.append(
                (
                    abs(calories - target),
                    meal,
                )
            )

        if not scored:
            return None

        scored.sort(
            key=lambda item: item[0]
        )

        if (
            len(scored) > 1
            and scored[0][0] == scored[1][0]
        ):
            return None

        return scored[0][1]

    @staticmethod
    def _normalize_name(value: Any) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .lower()
            .split()
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _matched(
        self,
        meal: dict[str, Any],
        *,
        reason: str,
        confidence: float,
    ) -> dict:
        return self._result(
            status="observed",
            reason=reason,
            confidence=confidence,
            meal={
                "id": meal.get("id"),
                "date": meal.get("date"),
                "meal_type": meal.get("meal_type"),
                "name": meal.get("name"),
                "base_name": meal.get("base_name"),
                "calories": meal.get("calories"),
            },
        )

    @staticmethod
    def _result(
        *,
        status: str,
        reason: str,
        confidence: float = 0.0,
        meal: dict[str, Any] | None = None,
    ) -> dict:
        return {
            "status": status,
            "reason": reason,
            "confidence": confidence,
            "meal": meal,
        }
