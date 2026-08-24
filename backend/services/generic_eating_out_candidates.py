from __future__ import annotations

from typing import Any


GENERIC_EATING_OUT_CATALOG = {
    "Colazione": [
        {
            "name": "Brunch con uova e pane",
            "calories": 650,
            "protein_g": 28,
            "carbs_g": 60,
            "fat_g": 32,
        },
        {
            "name": "Pancake con frutta",
            "calories": 700,
            "protein_g": 18,
            "carbs_g": 95,
            "fat_g": 26,
        },
        {
            "name": "Yogurt bowl e caffè",
            "calories": 500,
            "protein_g": 24,
            "carbs_g": 60,
            "fat_g": 18,
        },
    ],
    "Pranzo": [
        {
            "name": "Insalata con pollo",
            "calories": 550,
            "protein_g": 42,
            "carbs_g": 35,
            "fat_g": 24,
        },
        {
            "name": "Poke al ristorante",
            "calories": 650,
            "protein_g": 38,
            "carbs_g": 75,
            "fat_g": 20,
        },
        {
            "name": "Pasta al pomodoro",
            "calories": 700,
            "protein_g": 24,
            "carbs_g": 100,
            "fat_g": 20,
        },
    ],
    "Cena": [
        {
            "name": "Sushi",
            "calories": 750,
            "protein_g": 35,
            "carbs_g": 100,
            "fat_g": 20,
        },
        {
            "name": "Ramen",
            "calories": 800,
            "protein_g": 38,
            "carbs_g": 95,
            "fat_g": 28,
        },
        {
            "name": "Grigliata con contorno",
            "calories": 700,
            "protein_g": 50,
            "carbs_g": 35,
            "fat_g": 34,
        },
        {
            "name": "Pasta al ristorante",
            "calories": 850,
            "protein_g": 30,
            "carbs_g": 110,
            "fat_g": 30,
        },
    ],
}


class GenericEatingOutCandidateService:
    """
    Cold-start fallback for eating-out mode.

    These options are generic meal categories, not known venues or learned
    user preferences. Nutrition is explicitly marked as estimated.
    """

    def build(
        self,
        *,
        meal_type: str,
        known_candidates: list[dict[str, Any]],
        target_count: int = 3,
    ) -> list[dict]:
        if target_count <= 0:
            return []

        known_names = {
            self._key(item.get("name"))
            for item in known_candidates
            if item.get("name")
        }

        missing = max(
            0,
            target_count - len(known_candidates),
        )

        if missing == 0:
            return []

        result = []

        for item in GENERIC_EATING_OUT_CATALOG.get(
            meal_type,
            [],
        ):
            if self._key(item["name"]) in known_names:
                continue

            result.append(
                {
                    "id": (
                        "generic_eating_out:"
                        f"{self._slug(item['name'])}"
                    ),
                    "source": "generic_eating_out",
                    "source_id": None,
                    "name": item["name"],
                    "meal_type": meal_type,
                    "calories": float(item["calories"]),
                    "protein_g": float(item["protein_g"]),
                    "carbs_g": float(item["carbs_g"]),
                    "fat_g": float(item["fat_g"]),
                    "taste_score": 5.0,
                    "waste_risk": None,
                    "known_eating_out": False,
                    "generic_fallback": True,
                    "nutrition_estimated": True,
                    "provenance": "generic_eating_out_catalog",
                }
            )

            if len(result) >= missing:
                break

        return result

    @staticmethod
    def _key(value: Any) -> str:
        return " ".join(
            str(value or "").strip().lower().split()
        )

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(
            value.lower().strip().split()
        )
