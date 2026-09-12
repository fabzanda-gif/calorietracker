from __future__ import annotations

from typing import Any


class MealComponentAdaptationService:
    """
    Prova a far rientrare un bundle nel budget rimuovendo
    un solo componente chiaramente opzionale.

    Non modifica quantità e non smonta ricette/ingredienti.
    """

    OPTIONAL_TERMS = {
        "mela",
        "apple",
        "dessert",
        "dolce",
        "frutta",
        "fruit",
        "gelato",
        "ice cream",
        "budino",
        "pudding",
        "biscotto",
        "biscotti",
        "cookie",
        "cioccolato",
        "chocolate",
    }

    NUTRIENT_FIELDS = (
        ("calories", "calories"),
        ("protein_g", "protein"),
        ("carbs_g", "carbs"),
        ("fat_g", "fat"),
    )

    def adapt(
        self,
        *,
        candidate: dict[str, Any],
        available_kcal: float | None,
    ) -> dict[str, Any] | None:
        if available_kcal is None:
            return None

        total = self._number(
            candidate.get("calories")
        )
        available = self._number(
            available_kcal
        )

        if total <= available:
            return None

        components = candidate.get(
            "components"
        )

        if (
            not isinstance(components, list)
            or len(components) < 2
        ):
            return None

        optional = [
            (index, component)
            for index, component in enumerate(
                components
            )
            if (
                isinstance(component, dict)
                and self._is_optional(
                    component.get("name")
                )
                and self._number(
                    component.get("calories")
                ) > 0
            )
        ]

        # Minimo intervento: tra gli extra, prova prima
        # quello con meno calorie.
        optional.sort(
            key=lambda item: self._number(
                item[1].get("calories")
            )
        )

        for removed_index, removed in optional:
            removed_kcal = self._number(
                removed.get("calories")
            )

            if total - removed_kcal > available:
                continue

            remaining = [
                dict(component)
                for index, component in enumerate(
                    components
                )
                if (
                    index != removed_index
                    and isinstance(component, dict)
                )
            ]

            if not remaining:
                continue

            result = dict(candidate)
            result["components"] = remaining
            result["removed_components"] = [
                dict(removed)
            ]

            remaining_names = [
                str(
                    component.get("name") or ""
                ).strip()
                for component in remaining
                if str(
                    component.get("name") or ""
                ).strip()
            ]

            if remaining_names:
                result["name"] = " + ".join(
                    remaining_names
                )

            for target, component_field in (
                self.NUTRIENT_FIELDS
            ):
                original = self._number(
                    candidate.get(target)
                )
                removed_value = self._number(
                    removed.get(component_field)
                )
                result[target] = round(
                    max(
                        0.0,
                        original - removed_value,
                    ),
                    2,
                )

            return result

        return None

    @classmethod
    def _is_optional(
        cls,
        name: object,
    ) -> bool:
        normalized = " ".join(
            str(name or "")
            .strip()
            .casefold()
            .replace("-", " ")
            .split()
        )

        return any(
            term in normalized
            for term in cls.OPTIONAL_TERMS
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
