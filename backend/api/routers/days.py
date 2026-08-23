from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.weight import WeightRepository
from backend.services.day import DayService
from backend.services.day_budget import DayBudgetService
from backend.services.meal_memory import MealMemoryService


router = APIRouter(prefix="/days", tags=["days"])


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
        current_weight = (
            latest_weight.get("weight")
            if latest_weight is not None
            else None
        )

        service = DayBudgetService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        )

        return service.build(
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


@router.get("/{day_date}")
def get_day(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(get_daily_logs_repository),
    meals_repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meal_memory = MealMemoryService(
            meals_repo=meals_repo,
            daily_logs_repo=daily_logs_repo,
        )

        service = DayService(
            daily_logs_repo=daily_logs_repo,
            meal_memory_service=meal_memory,
        )

        return service.build_day(
            user_id=current_user.id,
            day_date=day_date,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
