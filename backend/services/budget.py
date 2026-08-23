from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GoalMode = Literal["loss", "maintenance", "gain"]


@dataclass(frozen=True)
class BudgetInput:
    bmr: float
    activity_kcal: float = 0.0

    consumed_kcal: float = 0.0
    planned_kcal: float = 0.0

    protein_consumed_g: float = 0.0
    protein_target_g: float | None = None

    goal_mode: GoalMode = "maintenance"
    goal_adjustment_kcal: float = 0.0


class BudgetService:
    """
    Deterministic calorie-budget engine.

    v0.1 deliberately contains no Streamlit, FastAPI, Supabase or AI logic.

    Definitions:
    - maintenance_kcal = BMR + actual/planned activity contribution supplied
      by the caller.
    - daily_budget_kcal applies the selected objective:
        loss        -> maintenance - adjustment
        maintenance -> maintenance
        gain        -> maintenance + adjustment
    - available_kcal is what remains after food actually consumed.
    - unallocated_kcal additionally subtracts food already planned.

    Negative balances are preserved. Going over budget is information, not
    an error condition.
    """

    VALID_GOALS = {"loss", "maintenance", "gain"}

    def calculate(self, data: BudgetInput) -> dict:
        self._validate(data)

        bmr = float(data.bmr)
        activity = float(data.activity_kcal)
        consumed = float(data.consumed_kcal)
        planned = float(data.planned_kcal)
        adjustment = abs(float(data.goal_adjustment_kcal))

        maintenance = bmr + activity

        if data.goal_mode == "loss":
            daily_budget = maintenance - adjustment
        elif data.goal_mode == "gain":
            daily_budget = maintenance + adjustment
        else:
            daily_budget = maintenance
            adjustment = 0.0

        available = daily_budget - consumed
        unallocated = available - planned

        protein_consumed = max(0.0, float(data.protein_consumed_g or 0.0))

        protein_target = (
            max(0.0, float(data.protein_target_g))
            if data.protein_target_g is not None
            else None
        )

        protein_remaining = (
            max(0.0, protein_target - protein_consumed)
            if protein_target is not None
            else None
        )

        return {
            "goal_mode": data.goal_mode,
            "goal_adjustment_kcal": round(adjustment, 2),
            "maintenance_kcal": round(maintenance, 2),
            "daily_budget_kcal": round(daily_budget, 2),
            "consumed_kcal": round(consumed, 2),
            "planned_kcal": round(planned, 2),
            "available_kcal": round(available, 2),
            "unallocated_kcal": round(unallocated, 2),
            "protein_consumed_g": round(protein_consumed, 2),
            "protein_target_g": (
                round(protein_target, 2)
                if protein_target is not None
                else None
            ),
            "protein_remaining_g": (
                round(protein_remaining, 2)
                if protein_remaining is not None
                else None
            ),
        }

    def _validate(self, data: BudgetInput) -> None:
        if data.goal_mode not in self.VALID_GOALS:
            raise ValueError(
                "goal_mode must be one of: loss, maintenance, gain"
            )

        if float(data.bmr) < 0:
            raise ValueError("bmr cannot be negative")

        if float(data.activity_kcal) < 0:
            raise ValueError("activity_kcal cannot be negative")

        if float(data.consumed_kcal) < 0:
            raise ValueError("consumed_kcal cannot be negative")

        if float(data.planned_kcal) < 0:
            raise ValueError("planned_kcal cannot be negative")

        if float(data.goal_adjustment_kcal) < 0:
            raise ValueError("goal_adjustment_kcal cannot be negative")

        if float(data.protein_consumed_g or 0.0) < 0:
            raise ValueError("protein_consumed_g cannot be negative")

        if (
            data.protein_target_g is not None
            and float(data.protein_target_g) < 0
        ):
            raise ValueError("protein_target_g cannot be negative")
