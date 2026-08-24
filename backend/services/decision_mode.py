from __future__ import annotations

from typing import Any


VALID_MODES = {
    "auto",
    "ready",
    "cook",
    "order",
    "out",
}


MODE_LABELS = {
    "auto": "Automatico",
    "ready": "Già pronto",
    "cook": "Cucino",
    "order": "Ordino",
    "out": "Fuori",
}


class DecisionModeError(ValueError):
    pass


class DecisionModeService:
    """
    Filter a normalized candidate pool by the user's current eating mode.

    Generic order fallback is allowed in order mode but remains a distinct
    source from learned takeaway/delivery history.
    """

    SOURCE_GROUPS = {
        "ready": {
            "meal_prep",
        },
        "cook": {
            "recipe",
            "routine",
        },
        "order": {
            "takeaway",
            "delivery",
            "generic_order",
        },
        "out": {
            "restaurant",
            "eating_out",
        },
    }

    def apply(
        self,
        *,
        candidates: list[dict[str, Any]],
        mode: str = "auto",
    ) -> dict:
        normalized_mode = str(mode or "auto").strip().lower()

        if normalized_mode not in VALID_MODES:
            raise DecisionModeError(
                "mode must be one of: auto, ready, cook, order, out"
            )

        if normalized_mode == "auto":
            filtered = list(candidates)
        else:
            allowed = self.SOURCE_GROUPS[normalized_mode]
            filtered = [
                item
                for item in candidates
                if item.get("source") in allowed
            ]

        return {
            "mode": normalized_mode,
            "mode_label": MODE_LABELS[normalized_mode],
            "candidate_count": len(filtered),
            "candidates": filtered,
            "empty_reason": self._empty_reason(
                mode=normalized_mode,
                candidates=filtered,
            ),
        }

    @staticmethod
    def _empty_reason(
        *,
        mode: str,
        candidates: list[dict[str, Any]],
    ) -> str | None:
        if candidates:
            return None

        return {
            "auto": "no_compatible_candidates",
            "ready": "no_ready_food",
            "cook": "no_cook_candidates",
            "order": "no_order_options",
            "out": "no_known_eating_out_options",
        }[mode]
