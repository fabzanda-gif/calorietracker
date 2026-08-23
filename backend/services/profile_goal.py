from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from backend.services.nutrition import (
    calculate_bmr,
    normalize_deficit_plan,
)


VALID_GOAL_MODES = {"loss", "maintenance", "gain"}


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ProfileGoalService:
    """
    Translate SanoSync profile metadata into Budget Engine inputs.

    v0.1 is deliberately pure:
    - no Supabase access;
    - no FastAPI dependency;
    - no Streamlit imports.

    Compatibility rules:
    1. New metadata (`goal_mode`, `goal_adjustment_kcal`) wins when valid.
    2. Otherwise legacy `deficit_plan` / `deficit_target_kcal` are mapped to:
         maintenance -> maintenance
         positive deficit -> loss
    3. Legacy metadata cannot represent gain; gain becomes available as soon
       as the new fields are written by a future profile API/UI.
    """

    def build(
        self,
        metadata: Mapping[str, Any],
        *,
        current_weight: float | None,
        on_date: date | None = None,
    ) -> dict:
        goal_mode, goal_adjustment = self._resolve_goal(metadata)

        bmr = self._resolve_bmr(
            metadata,
            current_weight=current_weight,
            on_date=on_date,
        )

        protein_enabled = bool(
            metadata.get("protein_goal_enabled", False)
        )
        protein_value = _safe_float(
            metadata.get("protein_goal_g")
        )

        protein_target = (
            protein_value
            if protein_enabled
            and protein_value is not None
            and protein_value > 0
            else None
        )

        return {
            "goal_mode": goal_mode,
            "goal_adjustment_kcal": round(goal_adjustment, 2),
            "bmr": bmr,
            "protein_target_g": (
                round(protein_target, 2)
                if protein_target is not None
                else None
            ),
            "profile_complete_for_budget": bmr is not None,
        }

    def _resolve_goal(
        self,
        metadata: Mapping[str, Any],
    ) -> tuple[str, float]:
        explicit_mode = str(
            metadata.get("goal_mode") or ""
        ).strip().casefold()

        explicit_adjustment = _safe_float(
            metadata.get("goal_adjustment_kcal")
        )

        if explicit_mode in VALID_GOAL_MODES:
            adjustment = max(
                0.0,
                explicit_adjustment or 0.0,
            )

            if explicit_mode == "maintenance":
                adjustment = 0.0

            return explicit_mode, adjustment

        legacy_plan = normalize_deficit_plan(
            metadata.get("deficit_plan")
        )

        legacy_deficit = _safe_float(
            metadata.get("deficit_target_kcal")
        )

        deficit = max(
            0.0,
            legacy_deficit or 0.0,
        )

        if legacy_plan == "maintenance" or deficit == 0:
            return "maintenance", 0.0

        return "loss", deficit

    def _resolve_bmr(
        self,
        metadata: Mapping[str, Any],
        *,
        current_weight: float | None,
        on_date: date | None,
    ) -> float | None:
        weight = _safe_float(current_weight)
        height = _safe_float(metadata.get("height"))
        birth_date = metadata.get("birth_date")
        gender = metadata.get("gender")

        if (
            weight is None
            or weight <= 0
            or height is None
            or height <= 0
            or not birth_date
            or not gender
        ):
            return None

        bmr = calculate_bmr(
            weight=weight,
            height=height,
            birth_date_value=birth_date,
            gender=str(gender),
            on_date=on_date,
        )

        return float(bmr) if bmr is not None else None
