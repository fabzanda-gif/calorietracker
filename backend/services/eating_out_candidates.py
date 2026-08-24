from __future__ import annotations

from collections import defaultdict
from typing import Any


EATING_OUT_CATEGORIES = {
    "restaurant",
    "ristorante",
    "eating_out",
    "eating out",
    "fuori",
    "fuori_casa",
    "fuori casa",
}


class EatingOutCandidateService:
    """
    Build eating-out candidates from meals the user has actually logged.

    v0.1:
    - uses only real meal history;
    - aggregates repeated restaurant/out-of-home choices;
    - averages nutrition from matching logs;
    - keeps frequency and recency for later personalization.

    No venue discovery is attempted here. This service only represents what
    SanoSync already knows from the user's own history.
    """

    def build(
        self,
        *,
        meals: list[dict[str, Any]],
        meal_type: str,
    ) -> list[dict]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for meal in meals:
            if meal.get("meal_type") != meal_type:
                continue

            category = self._category(
                meal.get("category")
            )
            if category not in EATING_OUT_CATEGORIES:
                continue

            name = (
                meal.get("base_name")
                or meal.get("name")
            )
            if not name:
                continue

            grouped[str(name).strip()].append(meal)

        candidates = []

        for name, rows in grouped.items():
            candidates.append(
                {
                    "id": f"restaurant:{self._slug(name)}",
                    "source": "restaurant",
                    "source_id": None,
                    "name": name,
                    "meal_type": meal_type,
                    "calories": self._average(
                        rows,
                        "calories",
                    ),
                    "protein_g": self._average(
                        rows,
                        "protein",
                    ),
                    "carbs_g": self._average(
                        rows,
                        "carbs",
                    ),
                    "fat_g": self._average(
                        rows,
                        "fat",
                    ),
                    "waste_risk": None,
                    "visit_count": len(rows),
                    "known_eating_out": True,
                    "last_visited_date": self._latest_date(
                        rows
                    ),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["visit_count"],
                item["last_visited_date"] or "",
            ),
            reverse=True,
        )

        return candidates

    @staticmethod
    def _category(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _average(
        rows: list[dict[str, Any]],
        field: str,
    ) -> float:
        values = []

        for row in rows:
            try:
                values.append(
                    max(
                        0.0,
                        float(row.get(field) or 0),
                    )
                )
            except (TypeError, ValueError):
                continue

        if not values:
            return 0.0

        return round(
            sum(values) / len(values),
            2,
        )

    @staticmethod
    def _latest_date(
        rows: list[dict[str, Any]],
    ) -> str | None:
        dates = [
            str(row.get("date"))
            for row in rows
            if row.get("date")
        ]

        return max(dates) if dates else None

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(
            value.lower().strip().split()
        )
