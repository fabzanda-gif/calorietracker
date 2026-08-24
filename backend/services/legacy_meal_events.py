from __future__ import annotations

from collections import defaultdict
from typing import Any


class LegacyMealEventService:
    """
    Reconstruct historical meal events from legacy meal rows.

    Old data may contain either:
    - one row representing the whole meal;
    - several rows representing individual components.

    Rows sharing date + meal_type are interpreted as one meal event.
    """

    SINGLE_ROW_MIN_KCAL = 300.0
    MULTI_ROW_MIN_KCAL = 200.0

    def build(
        self,
        *,
        meals: list[dict[str, Any]],
        meal_type: str,
    ) -> list[dict[str, Any]]:
        grouped: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = defaultdict(list)

        for meal in meals:
            if meal.get("meal_type") != meal_type:
                continue

            raw_date = meal.get("date")

            if not raw_date:
                continue

            name = self._name(meal)

            if not name:
                continue

            grouped[
                (str(raw_date), meal_type)
            ].append(meal)

        events = []

        for (day_date, grouped_type), rows in grouped.items():
            event = self._build_event(
                day_date=day_date,
                meal_type=grouped_type,
                rows=rows,
            )

            if event is not None:
                events.append(event)

        events.sort(
            key=lambda item: item["date"],
            reverse=True,
        )

        return events

    def _build_event(
        self,
        *,
        day_date: str,
        meal_type: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        calories = sum(
            self._number(row.get("calories"))
            for row in rows
        )

        protein = sum(
            self._number(row.get("protein"))
            for row in rows
        )

        carbs = sum(
            self._number(row.get("carbs"))
            for row in rows
        )

        fat = sum(
            self._number(row.get("fat"))
            for row in rows
        )

        if len(rows) == 1:
            # Legacy ambiguity:
            # a single row might be a complete meal or just one
            # ingredient/drink. Keep only substantial standalone
            # entries here. Restaurant/order candidates are handled
            # independently by their dedicated services.
            if calories < self.SINGLE_ROW_MIN_KCAL:
                return None

            name = self._name(rows[0])

        else:
            if calories < self.MULTI_ROW_MIN_KCAL:
                return None

            names = []

            for row in rows:
                name = self._name(row)

                if (
                    name
                    and name.casefold()
                    not in {
                        existing.casefold()
                        for existing in names
                    }
                ):
                    names.append(name)

            name = " + ".join(names)

        if not name:
            return None

        return {
            "date": day_date,
            "meal_type": meal_type,
            "name": name,
            "calories": round(calories, 2),
            "protein": round(protein, 2),
            "carbs": round(carbs, 2),
            "fat": round(fat, 2),
            "component_count": len(rows),
            "components": [
                {
                    "name": self._name(row),
                    "calories": self._number(
                        row.get("calories")
                    ),
                    "protein": self._number(
                        row.get("protein")
                    ),
                    "carbs": self._number(
                        row.get("carbs")
                    ),
                    "fat": self._number(
                        row.get("fat")
                    ),
                }
                for row in rows
            ],
        }

    @staticmethod
    def _name(meal: dict[str, Any]) -> str:
        return str(
            meal.get("base_name")
            or meal.get("name")
            or ""
        ).strip()

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0
