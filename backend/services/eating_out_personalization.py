from __future__ import annotations

from datetime import date
from typing import Any


class EatingOutPersonalizationService:
    """
    Convert eating-out history into an implicit preference signal.

    Uses:
    - visit frequency;
    - recency of the last visit.

    Known eating-out candidates do not require an explicit rating.
    Generic/future fallback candidates remain neutral.
    """

    def enrich(
        self,
        *,
        candidates: list[dict[str, Any]],
        on_date: date,
    ) -> list[dict]:
        return [
            self._enrich_one(
                candidate=item,
                on_date=on_date,
            )
            for item in candidates
        ]

    def _enrich_one(
        self,
        *,
        candidate: dict[str, Any],
        on_date: date,
    ) -> dict:
        result = dict(candidate)

        if not result.get("known_eating_out"):
            result.setdefault("taste_score", 5.0)
            result["implicit_taste_score"] = float(
                result.get("taste_score") or 5.0
            )
            result["personalization_strength"] = 0.0
            result["personalization_reason"] = (
                "generic_or_unlearned_option"
            )
            return result

        frequency = self._frequency_score(
            result.get("visit_count")
        )
        recency = self._recency_score(
            last_visited_date=result.get(
                "last_visited_date"
            ),
            on_date=on_date,
        )

        strength = (
            0.65 * frequency
            + 0.35 * recency
        )

        implicit_taste = 5.0 + 4.0 * strength

        explicit_present = result.get(
            "taste_score"
        ) not in (None, "")

        if explicit_present:
            explicit = self._bounded_taste(
                result.get("taste_score")
            )
            final_taste = (
                0.75 * explicit
                + 0.25 * implicit_taste
            )
        else:
            final_taste = implicit_taste

        result["implicit_taste_score"] = round(
            implicit_taste,
            2,
        )
        result["taste_score"] = round(
            final_taste,
            2,
        )
        result["personalization_strength"] = round(
            strength,
            4,
        )
        result["personalization_reason"] = self._reason(
            frequency=frequency,
            recency=recency,
        )

        return result

    @staticmethod
    def _frequency_score(value: Any) -> float:
        try:
            count = max(0, int(value or 0))
        except (TypeError, ValueError):
            count = 0

        return min(1.0, count / 4.0)

    @staticmethod
    def _recency_score(
        *,
        last_visited_date: Any,
        on_date: date,
    ) -> float:
        if not last_visited_date:
            return 0.0

        try:
            last_date = date.fromisoformat(
                str(last_visited_date)
            )
        except ValueError:
            return 0.0

        days = max(
            0,
            (on_date - last_date).days,
        )

        if days <= 7:
            return 1.0
        if days <= 21:
            return 0.75
        if days <= 45:
            return 0.5
        if days <= 90:
            return 0.25

        return 0.0

    @staticmethod
    def _bounded_taste(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 5.0

        return min(
            10.0,
            max(0.0, score),
        )

    @staticmethod
    def _reason(
        *,
        frequency: float,
        recency: float,
    ) -> str:
        if frequency >= 0.75 and recency >= 0.75:
            return "frequent_and_recent_eating_out"

        if frequency >= 0.75:
            return "frequent_eating_out"

        if recency >= 0.75:
            return "recent_eating_out"

        return "known_eating_out"
