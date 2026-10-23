from __future__ import annotations

from datetime import date as Date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_planned_activities_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.planned_activities import PlannedActivitiesRepository
from backend.repositories.weight import WeightRepository
from backend.services.budget import BudgetInput, BudgetService
from backend.services.planned_activity_energy import summarize_planned_activity_energy
from backend.services.profile_goal import ProfileGoalService
from backend.services.special_periods import active_special_period


router = APIRouter(prefix="/home-summary", tags=["home-summary"])


def _meal_totals(meals: list[dict]) -> tuple[float, float]:
    calories = sum(float(item.get("calories") or 0) for item in meals)
    protein = sum(float(item.get("protein") or 0) for item in meals)
    return calories, protein


def _activity_buffer(value: Any) -> float:
    normalized = " ".join(
        str(value or "").strip().casefold().replace("_", " ").split()
    )
    if normalized in {"moderata", "moderato", "moderate"}:
        return 150.0
    if normalized in {
        "attiva",
        "attivo",
        "molto attiva",
        "molto attivo",
        "very active",
    }:
        return 300.0
    return 0.0


def _day_context(
    *,
    day_date: Date,
    metadata: dict,
    daily_log: dict,
    special_period: dict | None,
) -> str | None:
    if special_period is not None:
        return "vacation" if special_period.get("period_type") == "vacation" else "illness"

    explicit = daily_log.get("day_type")
    if explicit:
        return str(explicit)

    schedule = metadata.get("weekly_schedule")
    if isinstance(schedule, dict):
        names = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
        value = schedule.get(names[day_date.weekday()])
        return str(value) if value else None

    return None


def _hero(
    *,
    special_period: dict | None,
    planned_today: list[dict],
    budget: dict | None,
) -> dict:
    if special_period:
        if special_period.get("period_type") == "illness":
            return {
                "kind": "illness",
                "title": "Priorità al recupero",
                "message": "Sei in modalità malattia: allenamenti sospesi e giornata orientata al recupero.",
                "icon": "🤒",
            }
        return {
            "kind": "vacation",
            "title": "Sei in vacanza",
            "message": "Routine più flessibile: niente logica ufficio e più spazio per pasti fuori, senza sospendere gli allenamenti.",
            "icon": "🏖️",
        }

    if planned_today:
        first = planned_today[0]
        title = str(first.get("title") or first.get("activity_name") or "Allenamento")
        return {
            "kind": "training",
            "title": f"Allenamento oggi: {title}",
            "message": "Mantieni margine per energia, idratazione e recupero intorno alla sessione.",
            "icon": "🏃",
        }

    if budget:
        protein_target = budget.get("protein_target_g")
        protein_consumed = float(budget.get("protein_consumed_g") or 0)
        if protein_target and protein_consumed < float(protein_target) * 0.45:
            return {
                "kind": "protein",
                "title": "Proteine ancora basse",
                "message": "Nel prossimo pasto prova a dare priorità a una fonte proteica.",
                "icon": "◎",
            }

        available = float(budget.get("available_kcal") or 0)
        daily = float(budget.get("daily_budget_kcal") or 0)
        if daily > 0 and available < daily * 0.2:
            return {
                "kind": "budget",
                "title": "Budget quasi utilizzato",
                "message": "Per il resto della giornata punta su scelte semplici e sazianti.",
                "icon": "◔",
            }

    return {
        "kind": "normal",
        "title": "Giornata sotto controllo",
        "message": "Registra quello che fai e mangi: SanoSync aggiorna il quadro senza appesantire la Home.",
        "icon": "✦",
    }


@router.get("/{day_date}")
def get_home_summary(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    daily_logs_repo: DailyLogsRepository = Depends(get_daily_logs_repository),
    planned_repo: PlannedActivitiesRepository = Depends(get_planned_activities_repository),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    """Small, deterministic payload for the initial Home render.

    No AI, meal-memory, recipe/pantry reads, strength history, 30-day suggestion
    learning or weekly history are executed here.
    """
    try:
        meals = meals_repo.list_for_date_compatible(current_user.id, day_date)
        activity_window = activities_repo.list_date_range(
            current_user.id,
            day_date - timedelta(days=7),
            day_date,
        )
        latest_weight = weight_repo.latest(current_user.id)
        daily_log = daily_logs_repo.get_for_date_compatible(
            user_id=current_user.id,
            log_date=day_date,
        ) or {}
        planned = planned_repo.list_range(
            current_user.id,
            day_date,
            day_date + timedelta(days=1),
        )

        supabase = getattr(daily_logs_repo, "supabase", None)
        special_period = None
        if supabase is not None:
            try:
                special_period = active_special_period(
                    supabase,
                    user_id=current_user.id,
                    on_date=day_date,
                )
            except Exception:
                special_period = None

        today_activities = [
            item for item in activity_window
            if str(item.get("date") or "") == str(day_date)
        ]
        previous_activities = [
            item for item in activity_window
            if str(item.get("date") or "") != str(day_date)
        ]
        average_activity_7d = sum(
            float(item.get("burned_calories") or 0)
            for item in previous_activities
        ) / 7.0

        planned_today = [
            item for item in planned
            if str(item.get("scheduled_date") or "") == str(day_date)
            and str(item.get("status") or "planned") not in {"completed", "skipped", "suspended"}
        ]
        planned_energy = summarize_planned_activity_energy(
            planned_today,
            weight_kg=(
                float(latest_weight.get("weight"))
                if latest_weight and latest_weight.get("weight") is not None
                else None
            ),
        )

        consumed_kcal, protein_consumed = _meal_totals(meals)
        actual_activity_kcal = sum(
            float(item.get("burned_calories") or 0)
            for item in today_activities
        )

        activity_plan = daily_log.get("activity_plan")
        if special_period and special_period.get("training_policy") == "suspend":
            activity_plan = "rest"
        elif special_period and special_period.get("activity_bias") == "higher" and not activity_plan:
            activity_plan = "moderate"

        profile = ProfileGoalService().build(
            current_user.metadata,
            current_weight=(
                float(latest_weight.get("weight"))
                if latest_weight and latest_weight.get("weight") is not None
                else None
            ),
            on_date=day_date,
        )

        budget = None
        if profile["profile_complete_for_budget"]:
            exercise_kcal = (
                actual_activity_kcal
                if actual_activity_kcal > 0
                else average_activity_7d + _activity_buffer(activity_plan)
            ) + float(planned_energy.get("estimated_kcal") or 0)

            logged_types = {
                str(item.get("meal_type") or "").strip().casefold()
                for item in meals
            }
            dinner_logged = bool(logged_types.intersection({"cena", "dinner"}))
            dinner_reserve = (
                0.0
                if dinner_logged
                else min(750.0, max(600.0, float(profile["bmr"]) * 0.4))
            )

            budget = BudgetService().calculate(
                BudgetInput(
                    bmr=float(profile["bmr"]),
                    activity_kcal=max(0.0, exercise_kcal),
                    baseline_activity_factor=1.0,
                    consumed_kcal=max(0.0, consumed_kcal),
                    planned_kcal=0.0,
                    protein_consumed_g=max(0.0, protein_consumed),
                    protein_target_g=profile.get("protein_target_g"),
                    goal_mode=profile["goal_mode"],
                    goal_adjustment_kcal=profile["goal_adjustment_kcal"],
                    remaining_meal_reserve_kcal=dinner_reserve,
                )
            )

        context = _day_context(
            day_date=day_date,
            metadata=dict(current_user.metadata),
            daily_log=daily_log,
            special_period=special_period,
        )

        return {
            "date": str(day_date),
            "context": context,
            "special_period": special_period,
            "hero": _hero(
                special_period=special_period,
                planned_today=planned_today,
                budget=budget,
            ),
            "budget": budget,
            "profile_goal": profile,
            "latest_weight": latest_weight,
            "meals": meals,
            "activities": today_activities,
            "planned_today": planned_today,
            "planned_tomorrow": [
                item for item in planned
                if str(item.get("scheduled_date") or "") == str(day_date + timedelta(days=1))
                and str(item.get("status") or "planned") not in {"completed", "skipped", "suspended"}
            ],
            "meta": {
                "history_days_used": 7,
                "ai_calls": 0,
                "average_activity_kcal_7d": round(average_activity_7d, 2),
            },
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
