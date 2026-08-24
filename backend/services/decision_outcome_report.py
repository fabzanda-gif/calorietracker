from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from backend.services.decision_outcome import (
    DecisionOutcomeService,
)


class DecisionOutcomeReportService:
    """
    Reconstruct observed outcomes for persisted decision selections.

    The caller supplies:
    - decision selections;
    - logged meals.

    This service groups meals by day and delegates conservative matching to
    DecisionOutcomeService. It never interprets `not_observed` as rejection.
    """

    def __init__(
        self,
        outcome_service: DecisionOutcomeService | None = None,
    ):
        self.outcome_service = (
            outcome_service or DecisionOutcomeService()
        )

    def build(
        self,
        *,
        selections: list[dict[str, Any]],
        meals: list[dict[str, Any]],
    ) -> dict:
        meals_by_date = self._group_meals(meals)

        items = []

        for selection in selections:
            selection_date = self._selection_date(
                selection
            )

            day_meals = (
                meals_by_date.get(selection_date, [])
                if selection_date is not None
                else meals
            )

            outcome = self.outcome_service.evaluate(
                selection=selection,
                meals=day_meals,
            )

            items.append(
                {
                    "selection_id": selection.get("id"),
                    "date": selection_date,
                    "meal_slot": selection.get("meal_slot"),
                    "meal_type": selection.get("meal_type"),
                    "mode": selection.get("mode"),
                    "lens": selection.get("lens"),
                    "candidate": selection.get("candidate"),
                    "outcome": outcome,
                }
            )

        counts = Counter(
            item["outcome"]["status"]
            for item in items
        )

        observed = counts.get("observed", 0)
        total = len(items)

        return {
            "selection_count": total,
            "status_counts": {
                "observed": observed,
                "not_observed": counts.get(
                    "not_observed",
                    0,
                ),
                "ambiguous": counts.get(
                    "ambiguous",
                    0,
                ),
                "unresolved": counts.get(
                    "unresolved",
                    0,
                ),
            },
            "observed_share": (
                round(observed / total, 4)
                if total
                else 0.0
            ),
            "items": items,
        }

    @staticmethod
    def _group_meals(
        meals: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = (
            defaultdict(list)
        )

        for meal in meals:
            value = meal.get("date")
            if value is None:
                continue

            result[str(value)].append(meal)

        return dict(result)

    @staticmethod
    def _selection_date(
        selection: dict[str, Any],
    ) -> str | None:
        value = (
            selection.get("date")
            or selection.get("day_date")
        )

        if value is None:
            return None

        if isinstance(value, date):
            return value.isoformat()

        return str(value)
