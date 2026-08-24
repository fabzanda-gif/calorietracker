from __future__ import annotations

from collections import defaultdict
from typing import Any


ORDER_CATEGORIES = {
    "takeaway",
    "delivery",
    "take away",
    "ordine",
    "ordinato",
}


class OrderCandidateService:
    """
    Build order-mode candidates from meals the user has actually logged.

    Known historical orders deliberately do NOT receive a synthetic
    taste_score. Taste is learned later by OrderPersonalizationService from
    frequency and recency. This prevents a neutral placeholder (5/10) from
    being mistaken for an explicit user rating.

    A future explicit rating can be added as a separate persisted signal.
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

            category = self._category(meal.get("category"))
            if category not in ORDER_CATEGORIES:
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
            source = self._source(rows)

            candidates.append(
                {
                    "id": f"{source}:{self._slug(name)}",
                    "source": source,
                    "source_id": None,
                    "name": name,
                    "meal_type": meal_type,
                    "calories": self._average(rows, "calories"),
                    "protein_g": self._average(rows, "protein"),
                    "carbs_g": self._average(rows, "carbs"),
                    "fat_g": self._average(rows, "fat"),
                    "waste_risk": None,
                    "order_count": len(rows),
                    "known_order": True,
                    "last_ordered_date": self._latest_date(rows),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["order_count"],
                item["last_ordered_date"] or "",
            ),
            reverse=True,
        )

        return candidates

    @staticmethod
    def _category(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _source(rows: list[dict[str, Any]]) -> str:
        categories = {
            str(row.get("category") or "").strip().lower()
            for row in rows
        }

        if "delivery" in categories:
            return "delivery"

        return "takeaway"

    @staticmethod
    def _average(
        rows: list[dict[str, Any]],
        field: str,
    ) -> float:
        values = []

        for row in rows:
            try:
                values.append(
                    max(0.0, float(row.get(field) or 0))
                )
            except (TypeError, ValueError):
                continue

        if not values:
            return 0.0

        return round(sum(values) / len(values), 2)

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
