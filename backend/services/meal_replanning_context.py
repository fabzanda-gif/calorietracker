from __future__ import annotations

from typing import Any


class MealReplanningContextService:
    """
    Explain how the current day context relates to a meal
    recommendation.

    V1 intentionally stays descriptive rather than claiming
    strict causality:
    - a reduced portion with food already logged is described
      as food pressure;
    - activity with an unchanged/full recommendation is
      exposed as additional available margin;
    - otherwise the recommendation is described as compatible
      with the normal day context.
    """

    def build(
        self,
        *,
        recommendation: dict[str, Any] | None,
        actual: dict[str, Any] | None,
        budget: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(recommendation, dict):
            return None

        actual = actual if isinstance(actual, dict) else {}
        budget = budget if isinstance(budget, dict) else {}

        multiplier = self._number(
            recommendation.get("portion_multiplier"),
            default=1.0,
        )
        consumed_kcal = self._number(
            actual.get("consumed_kcal")
        )
        activity_kcal = self._number(
            actual.get("actual_activity_kcal")
        )

        available_kcal = self._optional_number(
            budget.get("available_kcal")
        )

        portion_changed = multiplier != 1.0
        adaptation = recommendation.get(
            "adaptation"
        )
        adaptation = (
            adaptation
            if isinstance(adaptation, dict)
            else {}
        )
        removed_components = adaptation.get(
            "removed_components"
        )
        removed_components = (
            removed_components
            if isinstance(
                removed_components,
                list,
            )
            else []
        )

        strategy = str(
            recommendation.get("strategy") or ""
        ).strip()

        if strategy == "inventory_priority":
            return {
                "direction": "unchanged",
                "driver": "inventory",
                "portion_changed": portion_changed,
                "available_kcal": available_kcal,
                "title": "Prima quello che hai già pronto",
                "message": (
                    "Per il pranzo do priorità a un pasto "
                    "disponibile nell'inventario."
                ),
            }

        if removed_components:
            removed_names = [
                str(
                    component.get("name") or ""
                ).strip()
                for component in removed_components
                if isinstance(component, dict)
                and str(
                    component.get("name") or ""
                ).strip()
            ]

            removed_label = ", ".join(
                removed_names
            ) or "un extra"

            return {
                "direction": "reduced",
                "driver": "food",
                "portion_changed": False,
                "available_kcal": available_kcal,
                "title": "Pasto alleggerito, porzioni invariate",
                "message": (
                    f"Rimuovo {removed_label} e mantengo "
                    "invariato il piatto principale."
                ),
                "removed_components": removed_names,
            }

        if multiplier < 1.0 and consumed_kcal > 0:
            return {
                "direction": "reduced",
                "driver": "food",
                "portion_changed": True,
                "available_kcal": available_kcal,
                "title": "Porzione adattata alla giornata",
                "message": (
                    "Quello che hai già registrato oggi lascia "
                    "meno margine per questo pasto."
                ),
            }

        if activity_kcal > 0 and multiplier >= 1.0:
            return {
                "direction": "unchanged",
                "driver": "activity",
                "portion_changed": portion_changed,
                "available_kcal": available_kcal,
                "title": "Attività registrata",
                "message": (
                    "L'attività di oggi resta un dato osservato; "
                    "il budget usa la baseline degli ultimi 7 giorni."
                ),
            }

        return {
            "direction": "unchanged",
            "driver": "normal",
            "portion_changed": portion_changed,
            "available_kcal": available_kcal,
            "title": "In linea con la giornata",
            "message": (
                "Il pasto abituale è compatibile con "
                "il margine disponibile."
            ),
        }

    @staticmethod
    def _number(
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        try:
            return max(
                0.0,
                float(
                    default
                    if value is None
                    else value
                ),
            )
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_number(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        number = max(0.0, number)

        if number.is_integer():
            return int(number)

        return round(number, 2)
