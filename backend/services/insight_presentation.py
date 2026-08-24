from __future__ import annotations

from typing import Any


WEEKDAY_LABELS_IT = {
    "Monday": "Lunedì",
    "Tuesday": "Martedì",
    "Wednesday": "Mercoledì",
    "Thursday": "Giovedì",
    "Friday": "Venerdì",
    "Saturday": "Sabato",
    "Sunday": "Domenica",
}

MEAL_LABELS_IT = {
    "Colazione": "colazione",
    "Pranzo": "pranzo",
    "Cena": "cena",
}


class InsightPresentationService:
    """
    Convert learned-insight data into UI-ready cards.

    Keeps copy/presentation out of the frontend while preserving the
    underlying structured evidence for future explainability.
    """

    def present(self, payload: dict[str, Any]) -> dict:
        return {
            "generated_for": payload.get("generated_for"),
            "learned": [
                self._card(item, learned=True)
                for item in payload.get("learned", [])
            ],
            "learning": [
                self._card(item, learned=False)
                for item in payload.get("learning", [])
            ],
        }

    def _card(
        self,
        insight: dict[str, Any],
        *,
        learned: bool,
    ) -> dict:
        kind = insight.get("kind")
        weekday = WEEKDAY_LABELS_IT.get(
            insight.get("weekday_name"),
            insight.get("weekday_name") or "",
        )
        value = insight.get("value")

        if kind == "day_context":
            title = f"{weekday} → {value}"
            text = (
                f"Di solito il {weekday.lower()} sei in modalità {value}."
                if learned
                else f"Sto ancora capendo se il {weekday.lower()} tende a essere {value}."
            )
            icon = "calendar"

        elif kind == "activity_plan":
            title = f"{weekday} → {value}"
            text = (
                f"Il {weekday.lower()} tende a essere una giornata {str(value).lower()}."
                if learned
                else f"Sto ancora osservando il tuo livello di attività del {weekday.lower()}."
            )
            icon = "activity"

        elif kind == "meal":
            meal_type = insight.get("meal_type")
            meal_label = MEAL_LABELS_IT.get(
                meal_type,
                str(meal_type or "").lower(),
            )
            title = f"{weekday} · {meal_type} → {value}"

            context = insight.get("day_context")
            context_part = (
                f" quando sei in modalità {context}"
                if context
                else ""
            )

            text = (
                f"Il {weekday.lower()} a {meal_label}{context_part} scegli spesso {value}."
                if learned
                else f"Sto ancora verificando se {value} è una tua abitudine del {weekday.lower()} a {meal_label}."
            )
            icon = "meal"

        else:
            title = str(value or "Pattern")
            text = "Pattern osservato."
            icon = "insight"

        return {
            "kind": kind,
            "title": title,
            "text": text,
            "icon": icon,
            "confidence_level": insight.get("confidence_level"),
            "confidence": insight.get("confidence"),
            "evidence": insight.get("evidence"),
            "raw": insight,
        }
