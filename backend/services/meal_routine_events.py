from __future__ import annotations

from collections import defaultdict
from typing import Any


class MealRoutineEventService:
    """
    Raggruppa tutte le righe con stessa data e tipo
    in un unico evento alimentare.
    """

    def build(
        self,
        *,
        meals: list[dict[str, Any]],
        meal_type: str,
    ) -> list[dict[str, Any]]:
        grouped: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for meal in meals:
            if meal.get("meal_type") != meal_type:
                continue

            day_date = str(
                meal.get("date") or ""
            ).strip()
            name = self._name(meal)

            if not day_date or not name:
                continue

            grouped[day_date].append(meal)

        events = [
            self._event(
                day_date=day_date,
                rows=rows,
            )
            for day_date, rows in grouped.items()
        ]

        return sorted(
            events,
            key=lambda item: item["date"],
        )

    def _event(
        self,
        *,
        day_date: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        names: list[str] = []

        for row in rows:
            name = self._name(row)

            if name.casefold() not in {
                item.casefold()
                for item in names
            }:
                names.append(name)

        # L'identità ordinata rende uguali combinazioni
        # registrate in ordine diverso.
        identity_names = sorted(
            names,
            key=str.casefold,
        )
        identity = " + ".join(identity_names)

        if len(rows) == 1:
            event = dict(rows[0])
            event.update(
                {
                    "date": day_date,
                    "name": identity,
                    "identity": identity.casefold(),
                    "components": [
                        self._component(rows[0])
                    ],
                }
            )
            return event

        return {
            "date": day_date,
            "name": identity,
            "identity": identity.casefold(),
            "quantity": None,
            "is_per_100g": None,
            "base_calories": None,
            "base_protein": None,
            "base_carbs": None,
            "base_fat": None,
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
            "components": [
                self._component(row)
                for row in rows
            ],
        }

    @classmethod
    def _component(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "name": cls._name(row),
            "quantity": row.get("quantity"),
            "calories": cls._number(
                row.get("calories")
            ),
            "protein": cls._number(
                row.get("protein")
            ),
            "carbs": cls._number(
                row.get("carbs")
            ),
            "fat": cls._number(
                row.get("fat")
            ),
        }

    @staticmethod
    def _name(row: dict[str, Any]) -> str:
        return str(
            row.get("base_name")
            or row.get("name")
            or ""
        ).strip()

    @classmethod
    def _sum(
        cls,
        rows: list[dict[str, Any]],
        field: str,
    ) -> float:
        return round(
            sum(
                cls._number(row.get(field))
                for row in rows
            ),
            2,
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
