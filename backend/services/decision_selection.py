from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


VALID_MODES = {
    "auto",
    "ready",
    "cook",
    "order",
    "out",
}

VALID_LENSES = {
    "calorie",
    "balanced",
    "taste",
}


class DecisionSelectionError(ValueError):
    pass


class DecisionSelectionService:
    """
    Build a structured event when the user chooses one ranked meal option.

    This service is intentionally persistence-agnostic.

    It captures enough information for future learning without coupling the
    selection event to the meal log itself:
    - day / meal slot / meal type;
    - decision mode;
    - selected lens;
    - selected candidate provenance;
    - candidate position;
    - nutritional snapshot;
    - personalization / fallback metadata when available.

    v0.1 does not infer preference changes yet. It only creates a clean,
    deterministic event that can be persisted in the next step.
    """

    def build_event(
        self,
        *,
        user_id: str,
        day_date: date,
        meal_slot: str,
        meal_type: str,
        mode: str,
        lens: str,
        candidate: dict[str, Any],
        option_index: int,
        available_kcal: float | None = None,
        protein_remaining_g: float | None = None,
        selected_at: datetime | None = None,
    ) -> dict:
        normalized_mode = str(mode or "").strip().lower()
        normalized_lens = str(lens or "").strip().lower()

        if normalized_mode not in VALID_MODES:
            raise DecisionSelectionError(
                "mode must be one of: auto, ready, cook, order, out"
            )

        if normalized_lens not in VALID_LENSES:
            raise DecisionSelectionError(
                "lens must be one of: calorie, balanced, taste"
            )

        if option_index < 0:
            raise DecisionSelectionError(
                "option_index cannot be negative"
            )

        name = str(candidate.get("name") or "").strip()
        source = str(candidate.get("source") or "").strip()

        if not name:
            raise DecisionSelectionError(
                "candidate name is required"
            )

        if not source:
            raise DecisionSelectionError(
                "candidate source is required"
            )

        timestamp = selected_at or datetime.now(timezone.utc)

        return {
            "user_id": user_id,
            "date": str(day_date),
            "meal_slot": meal_slot,
            "meal_type": meal_type,
            "mode": normalized_mode,
            "lens": normalized_lens,
            "option_index": int(option_index),
            "selected_at": self._iso(timestamp),
            "candidate": {
                "id": candidate.get("id"),
                "source": source,
                "source_id": candidate.get("source_id"),
                "name": name,
                "calories": self._number_or_none(
                    candidate.get("calories")
                ),
                "protein_g": self._number_or_none(
                    candidate.get("protein_g")
                ),
                "carbs_g": self._number_or_none(
                    candidate.get("carbs_g")
                ),
                "fat_g": self._number_or_none(
                    candidate.get("fat_g")
                ),
                "taste_score": self._number_or_none(
                    candidate.get("taste_score")
                ),
                "waste_risk": candidate.get("waste_risk"),
                "known_order": candidate.get("known_order"),
                "known_eating_out": candidate.get(
                    "known_eating_out"
                ),
                "generic_fallback": candidate.get(
                    "generic_fallback"
                ),
                "personalization_strength": (
                    self._number_or_none(
                        candidate.get(
                            "personalization_strength"
                        )
                    )
                ),
                "personalization_reason": candidate.get(
                    "personalization_reason"
                ),
            },
            "decision_context": {
                "available_kcal": self._number_or_none(
                    available_kcal
                ),
                "protein_remaining_g": self._number_or_none(
                    protein_remaining_g
                ),
            },
        }

    @staticmethod
    def _number_or_none(value: Any) -> float | None:
        if value is None or value == "":
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(
            timezone.utc
        ).isoformat().replace("+00:00", "Z")
