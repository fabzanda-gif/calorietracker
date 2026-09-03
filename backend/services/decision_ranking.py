from __future__ import annotations

from typing import Any

from backend.services.decision_feedback import DecisionFeedbackService


class DecisionRankingService:
    """
    Rank compatible meal candidates through three distinct product lenses.

    Learned decision feedback may add only a small bounded score bonus.
    Eligibility, calorie fit, protein fit and food-waste logic remain primary.
    """

    LENSES = ("calorie", "balanced", "taste")

    def rank(
        self,
        *,
        candidates: list[dict[str, Any]],
        available_kcal: float | None,
        protein_remaining_g: float | None = None,
        mode: str = "auto",
        preferred_lens: str | None = None,
        preferred_mode: str | None = None,
        max_main_meal_kcal: float = 1000.0,
    ) -> dict:
        eligible = [
            self._normalize(item)
            for item in candidates
            if self._is_eligible(
                item,
                available_kcal=available_kcal,
                max_main_meal_kcal=max_main_meal_kcal,
            )
        ]

        if not eligible:
            return {
                "available_kcal": available_kcal,
                "protein_remaining_g": protein_remaining_g,
                "day_context": self._day_context(
                    available_kcal=available_kcal,
                    protein_remaining_g=protein_remaining_g,
                ),
                "options": [],
            }

        scored = {
            lens: sorted(
                eligible,
                key=lambda item: self._score(
                    item,
                    lens=lens,
                    available_kcal=available_kcal,
                    protein_remaining_g=protein_remaining_g,
                    mode=mode,
                    preferred_lens=preferred_lens,
                    preferred_mode=preferred_mode,
                ),
                reverse=True,
            )
            for lens in self.LENSES
        }

        selected = []
        used_keys = set()

        for lens in self.LENSES:
            pick = self._first_distinct(
                scored[lens],
                used_keys,
            )

            if pick is None:
                continue

            used_keys.add(self._identity(pick))

            selected.append(
                {
                    "lens": lens,
                    "label": self._label(lens),
                    "candidate": pick,
                    "score": round(
                        self._score(
                            pick,
                            lens=lens,
                            available_kcal=available_kcal,
                            protein_remaining_g=protein_remaining_g,
                            mode=mode,
                            preferred_lens=preferred_lens,
                            preferred_mode=preferred_mode,
                        ),
                        4,
                    ),
                    "reason": self._reason(
                        pick,
                        lens=lens,
                    ),
                }
            )

        return {
            "available_kcal": available_kcal,
            "protein_remaining_g": protein_remaining_g,
            "day_context": self._day_context(
                available_kcal=available_kcal,
                protein_remaining_g=protein_remaining_g,
            ),
            "options": selected,
        }

    @staticmethod
    def _day_context(
        *,
        available_kcal: float | None,
        protein_remaining_g: float | None,
    ) -> dict[str, str]:
        if available_kcal is None:
            return {
                "kind": "balanced",
                "title": "Scelte equilibrate",
                "message": (
                    "Le alternative tengono conto di "
                    "proteine, gusto e preferenze."
                ),
            }

        available = float(available_kcal)

        if available <= 500:
            return {
                "kind": "tight_budget",
                "title": "Oggi il margine è più stretto",
                "message": (
                    "Le alternative danno più peso "
                    "alle opzioni leggere."
                ),
            }

        if (
            protein_remaining_g is not None
            and float(protein_remaining_g) >= 50
        ):
            return {
                "kind": "protein_focus",
                "title": "Ti restano proteine da coprire",
                "message": (
                    "Le alternative bilanciate "
                    "favoriscono anche pasti più proteici."
                ),
            }

        if available >= 900:
            return {
                "kind": "flexible",
                "title": "Oggi hai più flessibilità",
                "message": (
                    "C'è abbastanza margine per dare "
                    "più spazio anche a gusto e preferenze."
                ),
            }

        return {
            "kind": "balanced",
            "title": "Scelte adatte alla tua giornata",
            "message": (
                "Le alternative bilanciano il margine "
                "rimasto, le proteine e le preferenze."
            ),
        }

    def _score(
        self,
        item: dict,
        *,
        lens: str,
        available_kcal: float | None,
        protein_remaining_g: float | None,
        mode: str,
        preferred_lens: str | None,
        preferred_mode: str | None,
    ) -> float:
        calories = item["calories"]
        protein = item["protein_g"]
        taste = item["taste_score"]

        calorie_efficiency = self._calorie_efficiency(
            calories,
            available_kcal,
        )
        protein_fit = self._protein_fit(
            protein,
            protein_remaining_g,
        )
        taste_norm = taste / 10.0
        waste_bonus = self._waste_bonus(
            item.get("waste_risk")
        )
        ready_bonus = (
            0.15
            if (
                mode == "auto"
                and item.get("source") == "meal_prep"
            )
            else 0.0
        )

        if lens == "calorie":
            base = (
                0.70 * calorie_efficiency
                + 0.20 * protein_fit
                + 0.10 * waste_bonus
            )
        elif lens == "taste":
            base = (
                0.65 * taste_norm
                + 0.20 * calorie_efficiency
                + 0.10 * protein_fit
                + 0.05 * waste_bonus
            )
        else:
            base = (
                0.40 * calorie_efficiency
                + 0.30 * protein_fit
                + 0.20 * taste_norm
                + 0.10 * waste_bonus
            )

        feedback = DecisionFeedbackService().score_boost(
            candidate=item,
            lens=lens,
            mode=mode,
            preferred_lens=preferred_lens,
            preferred_mode=preferred_mode,
        )

        return base + ready_bonus + feedback

    @staticmethod
    def _is_eligible(
        item: dict[str, Any],
        *,
        available_kcal: float | None,
        max_main_meal_kcal: float = 1000.0,
    ) -> bool:
        try:
            calories = float(item.get("calories") or 0)
        except (TypeError, ValueError):
            return False

        if calories < 0:
            return False

        meal_type = str(
            item.get("meal_type") or ""
        ).strip()

        if (
            meal_type in {"Pranzo", "Cena"}
            and (
                calories < 500.0
                or calories > max_main_meal_kcal
            )
        ):
            return False

        if available_kcal is not None and meal_type not in {"Pranzo", "Cena"}:
            available = float(available_kcal)

            # Calorie availability is a strong preference, not a
            # razor-thin hard cutoff. A real meal slightly above the
            # remaining budget can still be a useful suggestion.
            max_reasonable = max(
                available + 250.0,
                available * 1.5,
            )

            if calories > max_reasonable:
                return False

        return bool(item.get("name"))

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict:
        result = dict(item)

        def number(key: str) -> float:
            try:
                return max(0.0, float(result.get(key) or 0))
            except (TypeError, ValueError):
                return 0.0

        result["calories"] = number("calories")
        result["protein_g"] = number("protein_g")

        try:
            taste = float(result.get("taste_score"))
        except (TypeError, ValueError):
            taste = 5.0

        result["taste_score"] = min(10.0, max(0.0, taste))
        return result

    @staticmethod
    def _calorie_efficiency(
        calories: float,
        available_kcal: float | None,
    ) -> float:
        if available_kcal is None or available_kcal <= 0:
            return 1.0 / (1.0 + calories / 500.0)

        ratio = calories / available_kcal

        if ratio <= 1.0:
            return 1.0 - ratio

        # Keep calorie fit informative even when every realistic
        # meal is above the remaining budget. Do not flatten all
        # over-budget candidates to zero: a smaller excess should
        # still rank better than a larger one.
        return 1.0 / (1.0 + ratio)

    @staticmethod
    def _protein_fit(
        protein: float,
        protein_remaining_g: float | None,
    ) -> float:
        if protein_remaining_g is None or protein_remaining_g <= 0:
            return min(1.0, protein / 40.0)

        return min(
            1.0,
            protein / protein_remaining_g,
        )

    @staticmethod
    def _waste_bonus(waste_risk: Any) -> float:
        return {
            "high": 1.0,
            "medium": 0.5,
            "low": 0.2,
        }.get(str(waste_risk).lower(), 0.0)

    @staticmethod
    def _identity(item: dict) -> tuple:
        return (
            item.get("id"),
            item.get("source"),
            item.get("name"),
        )

    def _first_distinct(
        self,
        items: list[dict],
        used_keys: set[tuple],
    ) -> dict | None:
        for item in items:
            if self._identity(item) not in used_keys:
                return item
        return None

    @staticmethod
    def _label(lens: str) -> str:
        return {
            "calorie": "Più margine",
            "balanced": "Bilanciata",
            "taste": "Più gusto",
        }[lens]

    @staticmethod
    def _reason(
        item: dict,
        *,
        lens: str,
    ) -> str:
        if (
            item.get("source") == "meal_prep"
            and item.get("waste_risk") == "high"
        ):
            return "Usa qualcosa che hai già prima che vada sprecato"

        if lens == "calorie":
            return "Lascia più margine nel budget della giornata"

        if lens == "taste":
            return "Privilegia ciò che ti piace di più restando compatibile"

        return "Compromesso tra budget, proteine e preferenza"
