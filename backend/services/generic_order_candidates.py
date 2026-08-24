from __future__ import annotations

from typing import Any


GENERIC_ORDER_CATALOG = {
    "Colazione": [
        {
            "name": "Yogurt greco, frutta e granola",
            "calories": 450,
            "protein_g": 25,
            "carbs_g": 55,
            "fat_g": 14,
        },
        {
            "name": "Porridge con frutta",
            "calories": 500,
            "protein_g": 18,
            "carbs_g": 75,
            "fat_g": 14,
        },
        {
            "name": "Toast con uova e avocado",
            "calories": 550,
            "protein_g": 25,
            "carbs_g": 45,
            "fat_g": 28,
        },
    ],
    "Pranzo": [
        {
            "name": "Poke salmone",
            "calories": 650,
            "protein_g": 35,
            "carbs_g": 75,
            "fat_g": 22,
        },
        {
            "name": "Poke pollo",
            "calories": 600,
            "protein_g": 42,
            "carbs_g": 70,
            "fat_g": 16,
        },
        {
            "name": "Sushi misto",
            "calories": 700,
            "protein_g": 32,
            "carbs_g": 95,
            "fat_g": 18,
        },
        {
            "name": "Insalatona con pollo",
            "calories": 500,
            "protein_g": 40,
            "carbs_g": 35,
            "fat_g": 20,
        },
    ],
    "Cena": [
        {
            "name": "Pizza Margherita",
            "calories": 800,
            "protein_g": 28,
            "carbs_g": 105,
            "fat_g": 28,
        },
        {
            "name": "Poke salmone",
            "calories": 650,
            "protein_g": 35,
            "carbs_g": 75,
            "fat_g": 22,
        },
        {
            "name": "Sushi misto",
            "calories": 700,
            "protein_g": 32,
            "carbs_g": 95,
            "fat_g": 18,
        },
        {
            "name": "Burger con contorno leggero",
            "calories": 750,
            "protein_g": 38,
            "carbs_g": 70,
            "fat_g": 34,
        },
    ],
}


class GenericOrderCandidateService:
    """
    Generic fallback for order mode.

    These candidates are not learned from the user. They exist only to avoid
    an empty experience while SanoSync is still building order history.

    Nutrition is intentionally marked as estimated so the product can explain
    the difference between known historical orders and generic suggestions.
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

        for item in GENERIC_ORDER_CATALOG.get(
            meal_type,
            [],
        ):
            if self._key(item["name"]) in known_names:
                continue

            result.append(
                {
                    "id": (
                        "generic_order:"
                        f"{self._slug(item['name'])}"
                    ),
                    "source": "generic_order",
                    "source_id": None,
                    "name": item["name"],
                    "meal_type": meal_type,
                    "calories": float(item["calories"]),
                    "protein_g": float(item["protein_g"]),
                    "carbs_g": float(item["carbs_g"]),
                    "fat_g": float(item["fat_g"]),
                    "taste_score": 5.0,
                    "waste_risk": None,
                    "known_order": False,
                    "generic_fallback": True,
                    "nutrition_estimated": True,
                    "provenance": "generic_order_catalog",
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
