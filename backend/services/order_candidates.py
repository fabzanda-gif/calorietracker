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
    Build order candidates from historical order events.

    Multiple rows logged for the same date + meal type are interpreted
    as components of the same order before repeated orders are learned.
    """

    def build(
        self,
        *,
        meals: list[dict[str, Any]],
        meal_type: str,
    ) -> list[dict]:
        event_rows: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for meal in meals:
            if meal.get("meal_type") != meal_type:
                continue

            category = self._category(
                meal.get("category")
            )

            if category not in ORDER_CATEGORIES:
                continue

            raw_date = meal.get("date")

            if not raw_date:
                continue

            event_rows[
                (str(raw_date), meal_type)
            ].append(meal)

        events = []

        for (day_date, _), rows in event_rows.items():
            event = self._build_event(
                rows=rows,
                day_date=day_date,
                meal_type=meal_type,
            )

            if event is not None:
                events.append(event)

        grouped: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for event in events:
            grouped[event["name"]].append(
                event
            )

        candidates = []

        for name, rows in grouped.items():
            source = self._source(rows)

            candidates.append(
                {
                    "id": (
                        f"{source}:"
                        f"{self._slug(name)}"
                    ),
                    "source": source,
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
                    "order_count": len(rows),
                    "known_order": True,
                    "last_ordered_date":
                        self._latest_date(rows),
                }
            )

        candidates.sort(
            key=lambda item: (
                item["order_count"],
                item["last_ordered_date"]
                or "",
            ),
            reverse=True,
        )

        return candidates

    def _build_event(
        self,
        *,
        rows: list[dict[str, Any]],
        day_date: str,
        meal_type: str,
    ) -> dict[str, Any] | None:
        names = []

        for row in rows:
            name = (
                row.get("base_name")
                or row.get("name")
            )

            name = str(
                name or ""
            ).strip()

            if (
                name
                and name.casefold()
                not in {
                    item.casefold()
                    for item in names
                }
            ):
                names.append(name)

        if not names:
            return None

        return {
            "date": day_date,
            "meal_type": meal_type,
            "name": " + ".join(names),
            "category": (
                rows[0].get("category")
            ),
            "calories": self._sum(
                rows,
                "calories",
            ),
            "protein": self._sum(
                rows,
                "protein",
            ),
            "carbs": self._sum(
                rows,
                "carbs",
            ),
            "fat": self._sum(
                rows,
                "fat",
            ),
        }

    @staticmethod
    def _category(value: Any) -> str:
        return str(
            value or ""
        ).strip().lower()

    @staticmethod
    def _source(
        rows: list[dict[str, Any]],
    ) -> str:
        categories = {
            str(
                row.get("category") or ""
            ).strip().lower()
            for row in rows
        }

        if "delivery" in categories:
            return "delivery"

        return "takeaway"

    @staticmethod
    def _sum(
        rows: list[dict[str, Any]],
        field: str,
    ) -> float:
        total = 0.0

        for row in rows:
            try:
                total += max(
                    0.0,
                    float(
                        row.get(field) or 0
                    ),
                )
            except (TypeError, ValueError):
                continue

        return round(total, 2)

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
                        float(
                            row.get(field)
                            or 0
                        ),
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
