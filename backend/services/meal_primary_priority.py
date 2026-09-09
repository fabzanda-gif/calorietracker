from __future__ import annotations

from typing import Any


class MealPrimaryPriorityService:
    """
    Apply the small, deterministic product priorities that precede
    the general ranking and replanning pipeline.

    Candidate generation remains responsible for availability,
    meal-slot compatibility and expiry validation.
    """

    HOME_CONTEXTS = {
        "home",
        "casa",
        "wfh",
        "work from home",
        "lavoro da casa",
    }

    def choose(
        self,
        *,
        meal_slot: str,
        day_context: object,
        mode: str,
        candidates: list[dict[str, Any]],
        fallback: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if self._normalize(mode) != "auto":
            return fallback

        if (
            meal_slot == "breakfast"
            and self._is_home(day_context)
        ):
            routine = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.get("source") == "routine"
                ),
                None,
            )

            if routine is not None:
                return routine

        if meal_slot == "lunch":
            inventory = [
                candidate
                for candidate in candidates
                if candidate.get("source") == "meal_prep"
            ]

            if inventory:
                return min(
                    inventory,
                    key=self._expiry_key,
                )

        return fallback

    @classmethod
    def _is_home(
        cls,
        value: object,
    ) -> bool:
        return cls._normalize(value) in cls.HOME_CONTEXTS

    @staticmethod
    def _normalize(value: object) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .split()
        )

    @staticmethod
    def _expiry_key(
        candidate: dict[str, Any],
    ) -> tuple[int, str]:
        expires_at = candidate.get("expires_at")

        if expires_at:
            return (0, str(expires_at))

        return (1, "")
