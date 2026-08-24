from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meal_prep_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.weight import WeightRepository
from backend.services.day import DayService
from backend.services.day_budget import DayBudgetService
from backend.services.meal_confirmation import (
    MealAlreadyLoggedError,
    MealConfirmationService,
    MealPredictionUnavailableError,
)
from backend.services.meal_decision import MealDecisionService
from backend.services.meal_memory import MealMemoryService


router = APIRouter(prefix="/days", tags=["days"])


MEAL_SLOT_TO_TYPE = {
    "breakfast": "Colazione",
    "lunch": "Pranzo",
    "dinner": "Cena",
}


def _meal_memory(
    meals_repo: MealsRepository,
    daily_logs_repo: DailyLogsRepository,
) -> MealMemoryService:
    return MealMemoryService(
        meals_repo=meals_repo,
        daily_logs_repo=daily_logs_repo,
    )


@router.get("/{day_date}/budget")
def get_day_budget(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        latest_weight = weight_repo.latest(current_user.id)
        current_weight = latest_weight.get("weight") if latest_weight else None

        return DayBudgetService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        ).build(
            user_id=current_user.id,
            day_date=day_date,
            metadata=current_user.metadata,
            current_weight=current_weight,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{day_date}/meals/{meal_slot}/decision")
def get_meal_decision(
    day_date: Date,
    meal_slot: str,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(get_daily_logs_repository),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    weight_repo: WeightRepository = Depends(get_weight_repository),
    meal_prep_repo: MealPrepRepository = Depends(get_meal_prep_repository),
):
    if meal_slot not in MEAL_SLOT_TO_TYPE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown meal slot",
        )

    try:
        day = DayService(
            daily_logs_repo=daily_logs_repo,
            meal_memory_service=_meal_memory(meals_repo, daily_logs_repo),
        ).build_day(
            user_id=current_user.id,
            day_date=day_date,
        )

        latest_weight = weight_repo.latest(current_user.id)
        current_weight = latest_weight.get("weight") if latest_weight else None

        budget_result = DayBudgetService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        ).build(
            user_id=current_user.id,
            day_date=day_date,
            metadata=current_user.metadata,
            current_weight=current_weight,
        )

        available_kcal = None
        if budget_result.get("budget") is not None:
            available_kcal = budget_result["budget"].get("available_kcal")

        return MealDecisionService().decide(
            day_date=day_date,
            meal_type=MEAL_SLOT_TO_TYPE[meal_slot],
            available_inventory=meal_prep_repo.list_available(current_user.id),
            available_kcal=available_kcal,
            routine_prediction=day["meals"][meal_slot],
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/{day_date}/meals/{meal_slot}/confirm")
def confirm_meal_prediction(
    day_date: Date,
    meal_slot: str,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(get_daily_logs_repository),
    meals_repo: MealsRepository = Depends(get_meals_repository),
):
    if meal_slot not in MEAL_SLOT_TO_TYPE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown meal slot",
        )

    try:
        day = DayService(
            daily_logs_repo=daily_logs_repo,
            meal_memory_service=_meal_memory(meals_repo, daily_logs_repo),
        ).build_day(
            user_id=current_user.id,
            day_date=day_date,
        )

        return MealConfirmationService(meals_repo).confirm(
            user_id=current_user.id,
            day_date=day_date,
            prediction=day["meals"][meal_slot],
        )
    except (MealPredictionUnavailableError, MealAlreadyLoggedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{day_date}")
def get_day(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(get_daily_logs_repository),
    meals_repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        return DayService(
            daily_logs_repo=daily_logs_repo,
            meal_memory_service=_meal_memory(meals_repo, daily_logs_repo),
        ).build_day(
            user_id=current_user.id,
            day_date=day_date,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
